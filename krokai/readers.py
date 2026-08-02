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

__all__ = ["read_any", "read_pdf", "read_docx", "no_text_layer", "engines_available"]

_PAGE_MARK = re.compile(r"\[\[Page\s+[\w.-]+\]\]")
_MD_FOOTNOTE = re.compile(r"\[\\?\[[^\]]*\\?\]\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")

MIN_TEXT_LAYER = 200          # fewer characters than this means "no usable text layer"


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

       Fewer tokens over the same pages means fewer split words, so the engine reporting fewer
       alphabetic tokens is the better reading. That is the whole test.

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

    text = primary
    if len(text.strip()) < MIN_TEXT_LAYER <= len(alt.strip()):
        text = alt                                  # primary dead, alternate alive
    elif alt.strip() and text.strip():
        if _alpha_tokens(text) > _alpha_tokens(alt) * 1.01:
            text = alt                              # primary split words

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
    return len(read_pdf(path, cache_dir).strip()) < MIN_TEXT_LAYER


def corpus_text(path, cache_dir=None):
    """Read a PRIMARY SOURCE and prepare it for indexing.

    The scrape-artefact strip runs here and not on the quotation side, and the asymmetry is the
    whole point - see ``normalize.strip_scrape_artifacts`` for the measurement that produced it.
    """
    return normalise(strip_scrape_artifacts(read_any(path, cache_dir)))
