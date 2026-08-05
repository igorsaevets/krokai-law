# -*- coding: utf-8 -*-
"""Getting text out of a file without silently losing part of it.

Every reader here exists because the obvious one-liner **loses text without telling you**, and a
verification tool that reads 90% of a document reports the other 10% as fabricated.
"""
from __future__ import annotations

import hashlib
import html
import io
import os
import re

from .normalize import normalise, strip_scrape_artifacts

__all__ = ["read_any", "read_pdf", "read_docx", "no_text_layer", "engines_available",
           "_choose_extraction", "_form_values", "EXTRACTOR_VERSION", "MIN_CHARS_PER_PAGE"]

_PAGE_MARK = re.compile(r"\[\[Page\s+[\w.-]+\]\]")
_MD_FOOTNOTE = re.compile(r"\[\\?\[[^\]]*\\?\]\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")

MIN_TEXT_LAYER = 200          # fewer characters than this means "no usable text layer"

# 🔴 A DOCUMENT-WIDE FLOOR CANNOT SEE A LONG SCAN, and the markers added to make a hole visible are
# what hide it. Measured in the sister project on a real filing: a 41-page index, every page a
# scanned image, carried a ~124-character empty-page marker per page. One page of that is 124 < 200
# and lands in the OCR queue; forty-one pages is 5 084 >= 200 and reads as a document with a text
# layer. **The biggest scan in the matter was the one the manifest did not list.**
#
# Reproduced here on 2026-08-05: a 40-page PDF holding 7.8 characters a page - 310 in total - passed
# `no_text_layer` as readable. So the per-page rate is tested as well as the total, and only from
# three pages up, because a genuinely short one-page proclamation is not a scan.
MIN_CHARS_PER_PAGE = 40
PAGES_BEFORE_RATE_APPLIES = 3

# 🔴 Bumped whenever extraction changes what it puts on disk. It is part of the sidecar freshness
# key, because a downloaded statute never changes and `mtime` alone therefore cannot notice that
# the reader got better - the fix would ship, the suite would pass, and every sidecar already on
# disk would stay exactly as wrong as before.
EXTRACTOR_VERSION = "2"


def engines_available():
    """What is actually installed, for the doctor command. Reported, never assumed."""
    out = {}
    for mod, label in (("pypdf", "pypdf"), ("fitz", "PyMuPDF"), ("mammoth", "mammoth")):
        try:
            __import__(mod)
            out[label] = True
        except Exception:
            out[label] = False
    return out


def _cache_path(path, cache_dir):
    st = os.stat(path)
    key = "%s|%d|%d" % (os.path.abspath(path).lower(), st.st_size, int(st.st_mtime))
    return os.path.join(cache_dir, hashlib.sha1(key.encode("utf-8")).hexdigest() + ".txt")


def _alpha_tokens(s):
    return len(re.findall(r"[A-Za-z]+", s))


def _form_values(path):
    """`field name = value` for every FILLED field of an AcroForm PDF. Empty string if none.

    🔴 The name, not the position. A reviewer of the sister project's equivalent left one warning
    worth carrying: the field NAME contains the item number (`Pt8Line16_YesNo`) and can be trusted;
    the on-page reading order cannot. On page 10 of an I-485 a naive text read shifts items 14-17 by
    one, which is the difference between *"have you worked without authorization"* and *"have you
    violated the terms of your status"*. So the pairing here is name-to-value and never
    position-to-value, and the name is emitted with the value so a human can see which is which.

    Checkboxes whose value is `/Off` are dropped: an unticked box is the absence of an answer, and
    writing "Off" into the corpus invents a word the document does not contain - the same class as
    a scraper artefact, which is why this reader exists.
    """
    try:
        import pypdf
    except Exception:
        return ""
    try:
        fields = pypdf.PdfReader(path).get_fields() or {}
    except Exception:
        return ""                      # not a form, encrypted, or malformed: silent is right here
    out = []
    for name, f in fields.items():
        try:
            v = f.get("/V")
            ftype = str(f.get("/FT") or "")
        except Exception:
            continue
        if v is None:
            continue
        # 🔴🔴 A SIGNATURE FIELD IS NOT AN ANSWER, AND ITS VALUE IS NOT A STRING.
        #
        # This reader was added in 0.6.0 to fix a real defect - a filled USCIS form reading as
        # blank - and it opened a new one, which is the shape worth remembering: fixing a false
        # negative by widening what gets indexed will widen it too far unless something says stop.
        #
        # A digitally signed PDF - every govinfo download is one - carries a `/Sig` field whose
        # `/V` is a DICTIONARY holding the PKCS#7 certificate chain. `str()` of it is kilobytes of
        # hex, and it went straight into the corpus. Measured here on a signed fixture: 4 267
        # characters of certificate, of which the phrase "U.S. Government Printing Office,
        # Washington" came back **VERIFIED as law**. The sister project measured the scale on a
        # real library: 9 files of 73, 454 KB, 16 % of its search index, with `Washington`
        # appearing 14 times and `Government` 22 times inside blobs whose documents contain
        # neither word.
        #
        # Both tests are needed, and they fail independently. `/FT` names the field type where the
        # writer set it; the scalar test catches a signature dictionary reached through a widget
        # annotation that did not. A real answer is always a string or a number - never a
        # container - so refusing containers cannot drop one.
        if ftype == "/Sig":
            continue
        if not isinstance(v, (str, int, float)):
            continue
        v = str(v).strip()
        # 🔴 `/Off` with the slash, and nothing else. A reviewer found the earlier form dropping
        # `"Off"` too - and `Off` is a legitimate value for a TEXT field ("Mode: Off"), so a real
        # answer disappeared from the corpus with no warning. The slash is what makes it a PDF name
        # object, i.e. the unticked state of a checkbox rather than a word somebody typed.
        if not v or v == "/Off":
            continue
        out.append("%s = %s" % (name, v.lstrip("/")))
    if not out:
        return ""
    return "[FORM FIELDS: %d filled]\n" % len(out) + "\n".join(out)


def _choose_extraction(primary, alt):
    """Which of two extractions of the SAME pages to keep, and why. Returns `(text, reason)`.

    Two opposite failure modes share this decision, and a rule tuned for one silently hands wins to
    the other:

    * **splitting** - the engine breaks words apart (`resu lt`), which INFLATES its token count.
      Measured on a real 66-PDF corpus: worst case +51 %, on a controlling opinion.
    * **truncation** - the engine returns a fragment that is still long enough to look alive.
      Measured in a sister project: a 50-word extraction beat a 5 000-word one, because the rule
      only knew "fewer tokens means fewer split words".

    🔴 Confirmed by probe against THIS file, 2026-08-03: a 50-token primary above the dead-text
    floor was kept over a 5 000-token alternate. The two failure modes are told apart on two
    DIFFERENT axes: truncation by character count (splitting only inserts spaces, so it cannot
    double the length; losing pages can), splitting by token count. A single shared threshold was
    tried first and a control sat exactly on it - the axes, not the number, are the fix.
    """
    p, a = primary.strip(), alt.strip()
    if len(p) < MIN_TEXT_LAYER <= len(a):
        return alt, "primary extraction dead"
    if not a or not p:
        return primary, ""
    tp, ta = _alpha_tokens(primary), _alpha_tokens(alt)
    # 🔴 Truncation needs BOTH axes to agree, and it is tested in BOTH directions. Two findings
    # from one outside review, each confirmed by execution before it was believed:
    #   * an alternate 1.8x longer (primary lost ~45 %) sat under a lone 2x character threshold;
    #   * worse, the split rule fired in the WRONG DIRECTION: with a complete primary and a
    #     truncated ALTERNATE, "more tokens than the other side" read as "primary split words"
    #     and the truncated copy won. "More tokens" means MORE TEXT unless the characters say
    #     otherwise - so the split diagnosis only stands when the character counts are close.
    # Splitting inserts separators: tokens rise, characters barely move. Losing text moves both.
    if len(a) > len(p) * 1.3 and ta > tp * 1.3:
        return alt, "primary truncated: %d chars against %d" % (len(p), len(a))
    if len(p) > len(a) * 1.3 and tp > ta * 1.3:
        return primary, ""                    # the ALTERNATE is the truncated one
    # 1.15, not 1.01. A reviewer built the counter-case for the hair trigger: a complete primary
    # with TWO line-break-hyphen splits (+2 tokens) lost to an alternate missing a whole
    # paragraph, because 102 > 101.0. Real word-splitting inflates tokens by half (measured
    # +51 %); a couple of artefacts is ~2 % and must never flip the choice to a shorter text.
    if tp > ta * 1.15:
        return alt, "primary split words: %d tokens against %d" % (tp, ta)
    return primary, ""


def read_pdf(path, cache_dir=None):
    """Extract with **both** available engines and keep the one that did not break words apart.

    Two separate defects live here, and the second hid behind the first for a long time.

    1. **A dead extraction.** Some engines return almost nothing on a PDF another engine reads
       fine. Easy to detect: near-zero characters.

    2. 🔴 **A COMPLETE but word-broken extraction** - `resu lt`, `unauthor ized`, `per iod`. This
       passes a "did we get any text" gate and gets cached. Measured across a real 66-PDF corpus:
       four files where the first engine reports MORE alphabetic tokens than the second, i.e. it
       split words. The worst was a controlling court of appeals opinion at 3 295 tokens against
       2 179 - **51 % inflation** - and that case was one of three the whole argument rested on.

       Why it matters beyond tidiness: a verbatim quotation crossing such a break degrades to a
       punctuation-level verdict rather than a false miss, so it is not loud. But a degraded verdict
       is exactly what invites *"must be an extraction artefact"* - and that phrase is a
       **conclusion, not an explanation**. It is the bin where real errors hide.

       Fewer tokens over the same pages means fewer split words - UNLESS the shortfall is so large
       that it means lost text instead. Both readings of "fewer" are real and they point at
       opposite choices, so the decision lives in ``_choose_extraction`` with the arithmetic that
       separates them; the measured split inflation tops out near +51 %, while truncation loses
       text by multiples.

    🔴 A near-empty result is **never cached**. An earlier version wrote the empty result and keyed
    the cache on (path, size, mtime) alone, so installing the second engine tomorrow would change
    nothing: the poisoned entry would be served until the FILE changed, which for a downloaded
    statute is never.
    """
    if cache_dir:
        cp = _cache_path(path, cache_dir)
        if os.path.exists(cp):
            return io.open(cp, encoding="utf-8", errors="replace").read()

    primary = ""
    try:
        import pypdf
        r = pypdf.PdfReader(path)
        primary = "\n".join((p.extract_text() or "") for p in r.pages)
    except Exception:
        primary = ""

    alt = ""
    try:
        import fitz
        d = fitz.open(path)
        alt = "\n".join(pg.get_text() for pg in d)
        d.close()
    except Exception:
        alt = ""

    text, _why = _choose_extraction(primary, alt)

    # 🔴 A FILLED FORM IS NOT A BLANK ONE, AND THE TEXT LAYER CANNOT TELL THEM APART.
    #
    # In a fillable PDF - which is what every USCIS form is - the labels are in the page content and
    # the ANSWERS are not: they live in `/AcroForm /Fields` as `/V`. Extract the text layer alone
    # and a completed I-485 reads exactly like a blank one. Measured in the sister project on the
    # actually-filed form: **765 fields, 455 of them filled, none in the text layer.**
    #
    # Two consequences, and the second is the one that made this worth doing here. The obvious one
    # is that the content is missing. The quieter one is that a form PDF has a *thin* text layer, so
    # `no_text_layer()` calls it a scan and the tool advises OCR - advice that cannot work, for a
    # cause that is not the user's, on a file that has no image in it at all. That is the same
    # wrong-diagnosis shape as the short-source bug fixed the same day, in a different reader.
    fields = _form_values(path)
    if fields:
        text = (text or "") + "\n\n" + fields

    if cache_dir and len(text.strip()) >= MIN_TEXT_LAYER:
        os.makedirs(cache_dir, exist_ok=True)
        try:
            io.open(_cache_path(path, cache_dir), "w", encoding="utf-8").write(text)
        except OSError:
            pass
    return text


def read_docx(path):
    """Body text **plus** a raw-XML pass over the package.

    The popular one-liner drops **tables silently** - measured at -10 % of the text on a real set of
    case files - and also headers, footers, footnotes and unaccepted revisions. Those are precisely
    where a citation likes to sit: a footnote *is* the pincite.

    Both passes are concatenated. Duplication is harmless here, because the corpus is only ever
    searched, never displayed; a missing table is not harmless at all.
    """
    out = []
    try:
        import mammoth
        with open(path, "rb") as fh:
            out.append(mammoth.extract_raw_text(fh).value)
    except Exception:
        pass
    try:
        import zipfile
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith(".xml") and any(k in n for k in
                                              ("document", "footnote", "endnote", "header", "footer")):
                    out.append(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "replace")))
    except Exception:
        pass
    return "\n".join(out)


def read_any(path, cache_dir=None):
    """One entry point. Format-specific damage is repaired here and nowhere else."""
    low = path.lower()
    if low.endswith(".pdf"):
        return read_pdf(path, cache_dir)
    if low.endswith(".docx"):
        return read_docx(path)
    try:
        raw = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""
    if low.endswith((".xml", ".html", ".htm")):
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        # 🔴 Entities matter more than they look. Official XML stores the section sign as `&#xA7;`.
        # Without unescaping, `§ 103.2` in the corpus becomes `S 103.2` while the quotation still
        # says `§ 103.2`, and a provably correct quotation cannot be found. That single defect
        # depressed a whole verification run's numbers and inflated its "extraction artefact" bin.
        raw = html.unescape(raw)
    raw = _PAGE_MARK.sub(" ", raw)
    if low.endswith(".md"):
        raw = _MD_FOOTNOTE.sub(" ", raw)
        raw = _MD_LINK.sub(r"\1", raw)
        raw = raw.replace("\\[", "[").replace("\\]", "]")
    return raw


def no_text_layer(path, cache_dir=None):
    """True when a PDF is a scan with no OCR, or a stub page.

    🔴 This is reported to the human and **never** solved by asking a language model to read the
    scan. That prohibition is not squeamishness: a model transcribing an image produces plausible
    text, the plausible text goes into a quotation, and the quotation is then treated as the
    primary source. The failure is silent and it contaminates the one artefact the whole system
    exists to keep clean. OCR belongs to an OCR engine, run by a person who can see the page.

    🔴 A stub is more dangerous than a missing file. A 1.8 KB placeholder where a 60 KB chapter
    should be still *looks* downloaded: the index counts the topic as covered, and every quotation
    from that chapter comes back NOT FOUND with no hint that the library, not the quotation, is at
    fault.
    """
    if not path.lower().endswith(".pdf"):
        try:
            return len(io.open(path, encoding="utf-8", errors="replace").read().strip()) < MIN_TEXT_LAYER
        except OSError:
            return True
    # 🔴 A FILLED FORM IS NOT A SCAN. A blank fillable PDF carries only its labels, so its text
    # layer is thin - and this function used to answer "OCR it", which is advice that cannot be
    # followed: there is no image. Since `read_pdf` now appends the field values, the length test
    # below already sees them; the explicit check is here so the answer is right even when only the
    # labels are short and the fields carry everything.
    if _form_values(path):
        return False
    text = read_pdf(path, cache_dir).strip()
    if len(text) < MIN_TEXT_LAYER:
        return True
    # 🔴 THE RATE, NOT ONLY THE TOTAL - see MIN_CHARS_PER_PAGE. A document-wide floor is passed by
    # any scan long enough, because per-page furniture accumulates: page numbers, a running header,
    # an OCR engine's empty-page marker. The longer the scan, the safer it looks.
    pages = _page_count(path)
    if pages >= PAGES_BEFORE_RATE_APPLIES and len(text) / float(pages) < MIN_CHARS_PER_PAGE:
        return True
    return False


def _page_count(path):
    """Page count from whichever engine answers. 0 when neither does, which disables the rate test
    rather than inventing a denominator."""
    try:
        import pypdf
        return len(pypdf.PdfReader(path).pages)
    except Exception:
        pass
    try:
        import fitz
        d = fitz.open(path)
        n = d.page_count
        d.close()
        return n
    except Exception:
        return 0


def corpus_text(path, cache_dir=None):
    """Read a PRIMARY SOURCE and prepare it for indexing.

    The scrape-artefact strip runs here and not on the quotation side, and the asymmetry is the
    whole point - see ``normalize.strip_scrape_artifacts`` for the measurement that produced it.
    """
    return normalise(strip_scrape_artifacts(read_any(path, cache_dir)))
