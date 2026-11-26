# -*- coding: utf-8 -*-
"""Getting text out of a file without silently losing part of it.

Every reader here exists because the obvious one-liner **loses text without telling you**, and a
verification tool that reads 90% of a document reports the other 10% as fabricated.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re

from .normalize import alnum, normalise, strip_scrape_artifacts
from . import _pdfengine
from .repair import is_broken_type3


class MissingReader(RuntimeError):
    """Raised when a file's FORMAT needs an engine that is not installed.

    🔴 It exists so that "nothing was read" can never be mistaken for "nothing was found". Every
    third-party import in this package is optional on purpose - the audience includes machines
    where `pip install` is not allowed - but optional must mean *degraded loudly*, not *silent*.
    Before this, a bare install handed a PDF back as "", the checker saw an empty document, and the
    report said zero quotations with nothing wrong. Both external reviewers caught it in the same
    round; they were right and the packaging note that called `dependencies = []` safe was wrong.
    """


__all__ = ["MissingReader", "read_any", "read_pdf", "read_docx", "no_text_layer", "engines_available",
           "_choose_extraction", "_form_values", "EXTRACTOR_VERSION", "MIN_CHARS_PER_PAGE",
           "is_broken_type3", "text_layer", "ocr_label", "ocr_pages_cell", "OCR_PAGE_SHARE",
           "OCR_CHECK", "LAYER_VERSION", "page_table", "page_check", "PAGES_VERSION",
           "pdf_text_verdict", "STAMP_BAND", "PICTURE_COVER"]

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

# 🔴 K093: A SHORT PDF IS NOT A SCAN BECAUSE IT IS SHORT - AND A SHORT TYPESET TEXT IS NOT A
# DOCUMENT BECAUSE IT IS TYPESET.
#
# Until 0.26.0 every PDF under MIN_TEXT_LAYER was excluded as «a scan or a stub» and the user was
# told to OCR it, while a text file of the same length is indexed with a warning (corpus.py: «it may
# equally be a real short provision») - a one-paragraph typeset notice could never verify. The census
# that raised it (11 of 325 filed exhibit PDFs of a real matter: one page each, under 200 characters,
# typeset by render mode) was then read with a second instrument - Tesseract on each page rendered
# WITH its text, minus the words its text layer holds - and all 11 are PICTURES carrying a typeset
# label: each page shows 13 to 562 words its text layer lacks (typeset pages with no picture: 0-20
# on hundreds of words). Their 2-4 label lines stand in the outer tenth of the page on 10 of 11, and
# a picture covers 22-100 % of the page on 10 of 11 (the 11th draws its words as vector shapes, its
# label lines all in the margin). That is exactly the trap: a Bates stamp or an exhibit label over a
# scan is short TYPESET text, and so is a bot wall saved as a PDF. So a short PDF is indexed - as a
# short source, with the warning - only when it reads as a typeset document on every count:
#   * its text layer is typeset (K024's class): an OCR layer that thin is a scan the engine misread;
#   * no picture covers PICTURE_COVER of any page: a picture can hold the page's words;
#   * some text line stands inside the page body: a stamp, an exhibit label, a running header or a
#     browser's print header and footer sit in the outer STAMP_BAND of the page by construction.
# Anything else stays excluded, now with its reason. The geometry needs PyMuPDF; without it a short
# PDF is excluded as before and the reason says why. A bot wall that passes all three is still
# caught after this, by `corpus.looks_like_placeholder` - with «re-fetch it», not «OCR it».
STAMP_BAND = 0.10
PICTURE_COVER = 0.10

# 🔴 Bumped whenever extraction changes what it puts on disk. It is part of the sidecar freshness
# key, because a downloaded statute never changes and `mtime` alone therefore cannot notice that
# the reader got better - the fix would ship, the suite would pass, and every sidecar already on
# disk would stay exactly as wrong as before.
EXTRACTOR_VERSION = "3"

# 🔴 K024: AN OCR TEXT LAYER IS NOT TYPESET TEXT - AND UNTIL 0.22.0 NOTHING SAID SO.
#
# 38 of the 100 text PDFs in a real matter's law library are a scan with an invisible text layer
# drawn over it (504 pages; census of a copy, 2026-11-25). The words krokai compares there are what
# an OCR engine READ, not what the page says: two OCR copies of one decision disagreed on 11.7-13.8 %
# of their number tokens (audit 2026-11-23). A misread digit makes a wrong quotation verify and a
# right one fail - and the verdict looked exactly like a verdict on typeset text.
#
# How it is told apart, measured on that copy: OCR engines draw their text in render mode 3
# (neither filled nor stroked). Every OCR page there was 100 % invisible characters and every
# typeset page under 8 %, nothing in between, so OCR_PAGE_SHARE sits in an empty gap. pypdf (`Tr`
# tracked through q / Q on the operands of the text-showing operators) and PyMuPDF (get_texttrace
# span type 3) agreed on 1 539 of 1 539 pages. The pypdf count rides on the extraction that runs
# anyway: +3 % of its time, and the text came out byte-identical on 101 of 101 files.
#
# NOT seen by this test - stated so it is not mistaken for coverage: an OCR engine that draws its
# text VISIBLY (ABBYY «text over the page image», Acrobat ClearScan) makes a page that looks typeset;
# a typeset page carrying a small OCR'd image (a seal, a letterhead) stays under the page share by
# design. The Producer field is no substitute: «Paper Capture» named 3 typeset files and was absent
# from 30 of the 38 OCR files.
LAYER_VERSION = "1"
OCR_PAGE_SHARE = 0.5          # a page whose characters are at least half invisible is an OCR page
_LAYER_MIN_CHARS = 20         # fewer counted characters: a page with no text to judge
_INVISIBLE_TR = (3, 7)        # render modes that paint no glyph (7 only adds it to the clip path)
OCR_CHECK = "check every number, date and name against the page image"
_LAYER_MEMO = {}

# 🔴 K018: A PINCITE NAMES A PAGE, AND THE EXTRACTED TEXT HAD NONE.
#
# `read_pdf` joins the pages into one string, so a quotation standing verbatim on one page of a
# decision verified exactly like the same words cited to another page, and nothing could say where
# they stand. The boundaries survive in letters-and-digits space with the cleaning unchanged: on a
# copy of a real matter's law library `alnum(clean(pages joined)) == concat(alnum(clean(page)))`
# held for 100 of 100 text PDFs with both engines (audit 2026-11-23). So a page is a COUNT of
# letters and digits, kept beside the text cache with a hash of the pages' concatenation, and the
# corpus re-checks that hash against the text it actually indexed before it names a page: when the
# two disagree it says «page unknown», because a wrong page is worse than none. The number is the
# page INDEX in the PDF file (1 = its first page), not the printed page a citation names - the two
# differ wherever a decision starts in the middle of a volume.
PAGES_VERSION = "1"
_PAGES_MEMO = {}


class _TrCounter(object):
    """Characters a page draws visible / invisible, counted on the operands of the text-showing
    operators while the text render mode is tracked through `q` / `Q` and a form XObject (`Do`).

    🔴 It rides on the pypdf extraction that produces the corpus text, so it never raises: an
    exception inside pypdf's visitor would cost that page its text."""

    def __init__(self):
        self.pages = []
        self.start()

    def start(self):
        self.tr, self.stack, self.vis, self.inv = 0, [], 0, 0

    def stop(self):
        self.pages.append((self.vis, self.inv))

    def before(self, op, args, cm, tm):
        try:
            if op in (b"q", b"Do"):
                self.stack.append(self.tr)
            elif op == b"Q":
                if self.stack:
                    self.tr = self.stack.pop()
            elif op == b"Tr":
                self.tr = int(args[0])
            elif op == b"TJ":
                self._add(sum(len(x) for x in (args[0] if args else ())
                              if isinstance(x, (str, bytes))))
            elif op in (b"Tj", b"'", b'"'):
                s = args[-1] if args else ""
                self._add(len(s) if isinstance(s, (str, bytes)) else 0)
        except Exception:                                   # noqa: BLE001 - see the docstring
            pass

    def after(self, op, args, cm, tm):
        try:
            if op == b"Do" and self.stack:
                self.tr = self.stack.pop()
        except Exception:                                   # noqa: BLE001
            pass

    def _add(self, n):
        if self.tr in _INVISIBLE_TR:
            self.inv += n
        else:
            self.vis += n


def _trace_counts(page):
    """The same count from PyMuPDF: a `get_texttrace()` span of type 3 is invisible text."""
    vis = inv = 0
    for sp in page.get_texttrace():
        n = len(sp.get("chars") or ())
        if sp.get("type") == 3:
            inv += n
        else:
            vis += n
    return vis, inv


def _ranges(nums):
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else "%d-%d" % (nums[i], nums[j]))
        i = j + 1
    return ", ".join(out)


def _classify(counts, engine):
    text = [k + 1 for k, (v, i) in enumerate(counts) if v + i >= _LAYER_MIN_CHARS]
    ocr = [k + 1 for k, (v, i) in enumerate(counts)
           if v + i >= _LAYER_MIN_CHARS and i >= OCR_PAGE_SHARE * (v + i)]
    cls = ("none" if not text else "typeset" if not ocr else
           "ocr" if len(ocr) == len(text) else "mixed")
    return {"v": LAYER_VERSION, "class": cls, "pages": len(counts), "text_pages": len(text),
            "ocr_pages": _ranges(ocr), "engine": engine,
            "source": "invisible text (render mode 3)" if ocr else ""}


def _repaired(pages):
    # The in-memory repair below replaces a broken Type 3 file's cipher with RapidOCR's reading:
    # the text the corpus then holds is OCR text whatever the original file's render modes say.
    return {"v": LAYER_VERSION, "class": "ocr", "pages": pages, "text_pages": pages,
            "ocr_pages": _ranges(list(range(1, pages + 1))), "engine": "RapidOCR",
            "source": "krokai's own OCR repair of a broken Type 3 file"}


def _layer_key(path):
    st = os.stat(path)
    return "%s|%d|%d" % (os.path.abspath(path).lower(), st.st_size, int(st.st_mtime))


def _layer_file(path, cache_dir):
    return _cache_path(path, cache_dir)[:-4] + ".layer.json"


def _write_layer(lp, facts):
    try:
        os.makedirs(os.path.dirname(lp), exist_ok=True)
        with io.open(lp, "w", encoding="utf-8") as fh:
            json.dump(facts, fh)
    except OSError:
        pass


def _page_facts(pages, engine, fields):
    """K018: letters and digits per page of the extraction the text came from, plus a hash of
    them all. `fields`: form-field values were appended after the last page (they have no page)."""
    al = [alnum(normalise(strip_scrape_artifacts(t or ""))) for t in pages]
    return {"v": PAGES_VERSION, "engine": engine, "alnum": [len(a) for a in al],
            "sha1": hashlib.sha1("".join(al).encode("utf-8")).hexdigest(), "fields": bool(fields)}


def _pages_file(path, cache_dir):
    return _cache_path(path, cache_dir)[:-4] + ".pages.json"


def page_check(facts, at):
    """K018: `(ends, "")` when the per-page counts in `facts` add up to `at` - the letters-and-digits
    text the corpus INDEXED for that file - where `ends[i]` is the offset in `at` at which page i+1
    ends; `(None, why)` otherwise. Only form-field values may stand after the last page."""
    if not facts or not facts.get("alnum"):
        return None, (facts or {}).get("why") or "the pages were not measured"
    ends, n = [], 0
    for k in facts["alnum"]:
        n += k
        ends.append(n)
    if n > len(at) or (n < len(at) and not facts.get("fields")):
        return None, ("its pages hold %d letters and digits, the indexed text %d - the clean-up "
                      "joined something across a page break" % (n, len(at)))
    if hashlib.sha1(at[:n].encode("utf-8")).hexdigest() != facts.get("sha1"):
        return None, "its pages do not add up to the indexed text"
    return ends, ""


def _measure_pages(path, at):
    """K018: the pages of a PDF whose text cache was written before the pages file existed:
    re-read it page by page and keep the first engine whose pages add up to `at`. PyMuPDF first -
    the faster one; the cached text may have come from either."""
    fields, tried = bool(_form_values(path)), []
    try:
        fitz = _pdfengine.load()
    except ImportError:
        fitz = None
    if fitz is not None:
        try:
            d = fitz.open(path)
            try:
                got = _page_facts([pg.get_text() for pg in d], "PyMuPDF", fields)
            finally:
                d.close()
            if page_check(got, at)[0] is not None:
                return got
            tried.append("PyMuPDF")
        except Exception:                                   # noqa: BLE001 - advisory
            pass
    try:
        import pypdf
        got = _page_facts([(pg.extract_text() or "") for pg in pypdf.PdfReader(path).pages],
                          "pypdf", fields)
        if page_check(got, at)[0] is not None:
            return got
        tried.append("pypdf")
    except Exception:                                       # noqa: BLE001 - advisory
        pass
    return {"v": PAGES_VERSION, "alnum": None,
            "why": ("re-read with %s, its pages do not add up to the indexed text - the clean-up "
                    "joined something across a page break" % " and ".join(tried)) if tried
            else "no PDF engine could re-read its pages"}


def page_table(path, at, cache_dir=None):
    """K018: `(ends, why)` for the PDF `path` whose indexed letters-and-digits text is `at`
    (see `page_check`); `(None, why)` when the page of a match there cannot be told.

    The counts come from this run's extraction, else from the pages file beside the text cache,
    else from a re-read - and whichever it is, they are CHECKED against `at` before they are used:
    counts that do not add up to the text name no page. Only counts that add up are kept."""
    try:
        key = _layer_key(path)
    except OSError:
        return None, "the file is gone"
    lp = _pages_file(path, cache_dir) if cache_dir else None
    facts = _PAGES_MEMO.get(key)
    if facts is None and lp and os.path.exists(lp):
        try:
            with io.open(lp, encoding="utf-8") as fh:
                got = json.load(fh)
            if isinstance(got, dict) and got.get("v") == PAGES_VERSION:
                facts = got
        except (OSError, ValueError):
            facts = None
    if facts is not None:
        ends, _why = page_check(facts, at)
        if ends is not None:
            return ends, ""
    got = _measure_pages(path, at)
    ends, why = page_check(got, at)
    if ends is None:
        return None, got.get("why") or why
    _PAGES_MEMO[key] = got
    if lp:
        _write_layer(lp, got)
    return ends, ""


def _measure_layer(path):
    """The count for a file whose text came from the cache (written by an older version) or was
    never read in this run. PyMuPDF first - 4.7 s against pypdf's 30 s on the measured 101 files."""
    facts = None
    try:
        fitz = _pdfengine.load()
    except ImportError:
        fitz = None
    if fitz is not None:
        try:
            d = fitz.open(path)
            try:
                facts = _classify([_trace_counts(pg) for pg in d], "PyMuPDF")
            finally:
                d.close()
        except Exception:                                   # noqa: BLE001
            facts = None
    if facts is None:
        try:
            import pypdf
            trc = _TrCounter()
            for pg in pypdf.PdfReader(path).pages:
                trc.start()
                pg.extract_text(visitor_operand_before=trc.before,
                                visitor_operand_after=trc.after)
                trc.stop()
            facts = _classify(trc.pages, "pypdf")
        except Exception:                                   # noqa: BLE001
            return None
    # A cached text of a broken Type 3 file can only be the repair's output: `read_pdf` never
    # caches the cipher (a failed repair skips the write).
    if facts["class"] in ("typeset", "none") and is_broken_type3(path):
        facts = _repaired(facts["pages"])
    return facts


def text_layer(path, cache_dir=None):
    """What drew a PDF's text: typeset glyphs, an OCR layer, or a mix - and which pages.

    Returns a dict (`class` typeset / ocr / mixed / none, `pages`, `text_pages`, `ocr_pages`,
    `engine`, `source`), or None for a non-PDF, an unreadable file or a machine with no PDF
    engine. Kept beside the text cache under the same key, and in memory for the run; `read_pdf`
    fills both as a side effect of the extraction it does anyway (K024)."""
    if not path.lower().endswith(".pdf"):
        return None
    try:
        key = _layer_key(path)
    except OSError:
        return None
    got = _LAYER_MEMO.get(key)
    if got is not None:
        return got
    lp = _layer_file(path, cache_dir) if cache_dir else None
    if lp and os.path.exists(lp):
        try:
            with io.open(lp, encoding="utf-8") as fh:
                got = json.load(fh)
        except (OSError, ValueError):
            got = None
        if isinstance(got, dict) and got.get("v") == LAYER_VERSION:
            _LAYER_MEMO[key] = got
            return got
    got = _measure_layer(path)
    if got is None:
        return None
    _LAYER_MEMO[key] = got
    if lp:
        _write_layer(lp, got)
    return got


def ocr_pages_cell(facts):
    """`all 41 pages` / `pages 2-3 of 3` - the short form for lists."""
    if facts.get("class") == "mixed":
        return "pages %s of %d" % (facts.get("ocr_pages"), facts.get("pages") or 0)
    return "all %d pages" % (facts.get("pages") or 0)


def ocr_label(facts):
    """The one wording every surface prints beside a match in an OCR text layer; None otherwise."""
    if not facts or facts.get("class") not in ("ocr", "mixed"):
        return None
    who = ("krokai's own OCR repair" if "repair" in (facts.get("source") or "")
           else "an OCR engine")
    if facts["class"] == "mixed":
        return ("OCR TEXT LAYER on %s: a match there is what %s read from a scanned image, not "
                "typeset text - %s" % (ocr_pages_cell(facts), who, OCR_CHECK))
    return ("OCR TEXT LAYER (%s): the words matched what %s read from a scanned image, not "
            "typeset text - %s" % (ocr_pages_cell(facts), who, OCR_CHECK))


def engines_available():
    """What is actually installed, for the doctor command. Reported, never assumed."""
    out = {}
    for label, load in (("pypdf", lambda: __import__("pypdf")), ("PyMuPDF", _pdfengine.load),
                        ("mammoth", lambda: __import__("mammoth"))):
        try:
            load()
            out[label] = True
        except Exception:
            out[label] = False
    try:
        from rapidocr import RapidOCR  # noqa: F401
        out["RapidOCR"] = True
    except Exception:
        out["RapidOCR"] = False
    return out


def _cache_path(path, cache_dir):
    # 🔴 R76 (F3; grokbuild, kimik3, spark12cont converged): EXTRACTOR_VERSION was in the
    # SIDECAR key and not in this one - so a reader improvement shipped, the sidecar noticed
    # its stamp was stale, rebuilt - and `build()` read the poisoned cache below and re-wrote
    # the OLD text under the NEW stamp. A downloaded statute's mtime never changes; without
    # the version in this key a bad extraction was cached forever. Old-version cache files
    # become unreferenced and are left to the cache dir's own lifetime.
    st = os.stat(path)
    key = "%s|%d|%d|v%s" % (os.path.abspath(path).lower(), st.st_size, int(st.st_mtime),
                            EXTRACTOR_VERSION)
    return os.path.join(cache_dir, hashlib.sha1(key.encode("utf-8")).hexdigest() + ".txt")


def _alpha_tokens(s):
    return len(re.findall(r"[A-Za-z]+", s))


def _form_values_fitz(path):
    """The same question answered through PyMuPDF widgets, for installs that have fitz but not
    pypdf (R77, #355 / F5 - the field reader was single-engine while the text reader was dual).

    The `/Off` discipline is kept by TYPE here rather than by the slash: fitz strips the name-
    object slash, so an unticked checkbox reports the bare word `Off` - exactly the string a text
    field may legitimately contain. `field_type` says which is which; only checkbox/radio `Off`
    is the absence of an answer.
    """
    try:
        fitz = _pdfengine.load()
    except Exception:
        return ""
    try:
        doc = fitz.open(path)
    except Exception:
        return ""
    out = []
    try:
        boxes = {getattr(fitz, "PDF_WIDGET_TYPE_CHECKBOX", 2),
                 getattr(fitz, "PDF_WIDGET_TYPE_RADIOBUTTON", 5)}
        sig = getattr(fitz, "PDF_WIDGET_TYPE_SIGNATURE", 7)
        for page in doc:
            for w in (page.widgets() or []):
                try:
                    if w.field_type == sig:
                        continue
                    v = w.field_value
                except Exception:
                    continue
                if v is None or not isinstance(v, (str, int, float)):
                    continue
                v = str(v).strip()
                if not v or (w.field_type in boxes and v == "Off"):
                    continue
                out.append("%s = %s" % (w.field_name, v.lstrip("/")))
    finally:
        doc.close()
    if not out:
        return ""
    return "[FORM FIELDS: %d filled]\n" % len(out) + "\n".join(out)


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
        return _form_values_fitz(path)
    try:
        fields = pypdf.PdfReader(path).get_fields() or {}
    except Exception:
        # Not a form, encrypted, or malformed FOR THIS ENGINE - the other engine still gets to
        # answer before the silence. Silent stays right when both say nothing.
        return _form_values_fitz(path)
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
    # 🔴 K093: an EMPTY primary used to win here whenever the alternate was under the floor too - so
    # with pypdf absent (or failing on the file) a short PyMuPDF text came back '' and a real short
    # document read as «no text at all», while pypdf alone kept the same text (BACKLOG K010, found by
    # K003's fixture). Some text beats none; the length rules below are for two texts.
    if not p:
        return alt, ("primary extraction empty" if a else "")
    if not a:
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

    # 🔴 "NO ENGINE IS INSTALLED" AND "THIS PDF HAS NO TEXT" MUST NOT LOOK THE SAME.
    #
    # These blocks used to catch `Exception`, which swallows `ImportError` alongside a corrupt file.
    # So a plain `pip install krokai` with neither reader present returned "" from a PDF, silently,
    # and the document was then reported as checked with zero quotations found. That is the same
    # shape as the packs defect fixed in 0.7.5, one layer up: a tool that succeeds at nothing is
    # worse than one that fails, because nobody investigates a clean report.
    #
    # An empty text layer is a REAL and common answer here - a scanned statute - so it cannot be
    # turned into an error. The distinction has to be drawn at the import, not at the result.
    have_engine = False

    primary, pparts, fpages = "", [], []          # K018: the pages each engine's text came from
    counts = engine = None
    try:
        import pypdf
    except ImportError:
        pass
    else:
        have_engine = True
        try:
            r = pypdf.PdfReader(path)
            # K024: the render-mode count rides on this pass (see _TrCounter).
            trc = _TrCounter()
            parts = []
            for p in r.pages:
                trc.start()
                parts.append(p.extract_text(visitor_operand_before=trc.before,
                                            visitor_operand_after=trc.after) or "")
                trc.stop()
            primary, pparts = "\n".join(parts), parts
            counts, engine = trc.pages, "pypdf"
        except Exception:
            primary = ""

    alt = ""
    try:
        fitz = _pdfengine.load()
    except ImportError:
        pass
    else:
        have_engine = True
        try:
            d = fitz.open(path)
            fpages = [pg.get_text() for pg in d]
            alt = "\n".join(fpages)
            if counts is None:              # K024: no pypdf count - the same one from PyMuPDF
                try:
                    counts, engine = [_trace_counts(pg) for pg in d], "PyMuPDF"
                except Exception:           # noqa: BLE001
                    counts = None
            d.close()
        except Exception:
            alt = ""

    if not have_engine:
        raise MissingReader(
            "%s is a PDF and no PDF engine is installed, so its text was never read.\n"
            "This is NOT the same as 'the document contains no quotations' - nothing was examined.\n"
            "Install one:  pip install \"krokai[pdf]\"   (or krokai[all])" % os.path.basename(path))

    text, _why = _choose_extraction(primary, alt)
    # K018: `_choose_extraction` hands back one of the two objects it was given
    pages, pengine = (fpages, "PyMuPDF") if text is alt and text is not primary else (pparts, "pypdf")

    # 🔴 A BROKEN PSCRIPT5 PDF RETURNS TEXT THAT LOOKS ALIVE BUT IS A SUBSTITUTION CIPHER.
    #
    # Type 3 fonts from Windows virtual printers carry glyphs with no ToUnicode mapping. Both
    # engines extract *something* — often hundreds of characters — but the bytes bear no
    # relationship to what the page displays. The signature is Type 3 fonts plus a high ratio
    # of control characters (ord < 32). When detected, the repair module renders the page as an
    # image, runs OCR, and overlays a clean text layer. The repaired copy is cached so the next
    # read is fast.
    repair_failed = False
    repaired_pages = None
    if text and is_broken_type3(path):
        try:
            from .repair import fix_broken_pdf
            import tempfile
            fd, tmp = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                fix_broken_pdf(path, tmp)
                d2 = _pdfengine.load().open(tmp)
                pages, pengine = [pg.get_text() for pg in d2], "krokai's OCR repair"
                text = "\n".join(pages)
                repaired_pages = d2.page_count
                d2.close()
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except Exception as exc:
            # 🔴 R76 (F4; codex, orglm53, qwen38max, spark11 converged): this failure used to
            # be `pass` - silent - and the substitution-cipher text then passed the length
            # floor and was CACHED, so every later read served garbage without retrying, and
            # every quotation from the file read NOT_FOUND (the fabrication signal) for a
            # cause that was the corpus's. The failure is now printed and the cache write is
            # skipped so the next read retries the repair.
            repair_failed = True
            print("  !! Type 3 repair FAILED for %s (%s: %s) - broken text kept for this run, "
                  "NOT cached; quotations from this file will misread until the PDF is repaired "
                  "(`krokai fix-pdf`)"
                  % (os.path.basename(path), type(exc).__name__, exc))

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

    facts = (_repaired(repaired_pages) if repaired_pages is not None and not repair_failed
             else _classify(counts, engine) if counts is not None else None)
    if facts is not None:
        try:
            _LAYER_MEMO[_layer_key(path)] = facts
        except OSError:
            pass
    # K018: the pages of the extraction just chosen - counted here, checked where they are used
    pfacts = None if repair_failed else _page_facts(pages, pengine, fields)
    if pfacts is not None:
        try:
            _PAGES_MEMO[_layer_key(path)] = pfacts
        except OSError:
            pass
    if cache_dir and not repair_failed and len(text.strip()) >= MIN_TEXT_LAYER:
        os.makedirs(cache_dir, exist_ok=True)
        try:
            io.open(_cache_path(path, cache_dir), "w", encoding="utf-8").write(text)
        except OSError:
            pass
        if facts is not None:
            _write_layer(_layer_file(path, cache_dir), facts)
        if pfacts is not None:
            _write_layer(_pages_file(path, cache_dir), pfacts)
    return text


def read_docx(path):
    """Body text **plus** a raw-XML pass over the package.

    The popular one-liner drops **tables silently** - measured at -10 % of the text on a real set of
    case files - and also headers, footers, footnotes and unaccepted revisions. Those are precisely
    where a citation likes to sit: a footnote *is* the pincite.

    🔴 R77 (#345, agy31pro/lunapro) SUPERSEDES the old "duplication is harmless" note that stood
    here: the XML pass re-read `document.xml` even when mammoth had already returned the body -
    including its tables, probe-confirmed - so every body phrase existed twice in the corpus and
    every count over it measured the reader, not the document. The XML pass now takes the body
    only when mammoth produced nothing; footnotes, endnotes, headers and footers stay
    unconditional, because they are what the mammoth pass genuinely lacks and a pincite lives
    there.
    """
    out = []
    # Same distinction as read_pdf: a missing engine is not an empty document. See MissingReader.
    try:
        import mammoth
    except ImportError:
        raise MissingReader(
            "%s is a .docx and `mammoth` is not installed, so its text was never read.\n"
            "This is NOT the same as 'the document contains no quotations' - nothing was "
            "examined.\n"
            "Install it:  pip install \"krokai[docx]\"   (or krokai[all])" % os.path.basename(path))
    try:
        with open(path, "rb") as fh:
            out.append(mammoth.extract_raw_text(fh).value)
    except Exception:
        pass
    body_covered = bool(out and out[0].strip())
    xml_keys = ("footnote", "endnote", "header", "footer") + (() if body_covered else ("document",))
    try:
        import zipfile
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if n.endswith(".xml") and any(k in n for k in xml_keys):
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
    if low.endswith(".doc"):
        # 🔴 R77 (#350, grokbuild): pre-2007 binary Word fell through to the plain-text reader,
        # which decoded the OLE container with errors="replace" - probe-measured 3 798 characters
        # of soup from a 4 KB file, comfortably past every floor, indexed as a primary source.
        # Every honest quotation of the document then read NOT_FOUND, the fabrication signal.
        # No pure-Python .doc engine exists to install, so the honest answer is the loud one.
        raise MissingReader(
            "%s is a pre-2007 binary .doc and no reader for that format exists here, so its "
            "text was never read.\nThis is NOT the same as 'the document contains no "
            "quotations' - nothing was examined.\nConvert it once:  open in Word/LibreOffice "
            "and save as .docx (or export to PDF)." % os.path.basename(path))
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
    return pdf_text_verdict(path, cache_dir)[0]


def pdf_text_verdict(path, cache_dir=None):
    """`(True, why)` when the PDF `path` has no usable text layer - a scan without OCR, a stamp or a
    label over a picture, a stub - and `(False, "")` when its text can be indexed; a short one is then
    indexed WITH the short-source warning, as a short text file is (K093 - see STAMP_BAND)."""
    if _form_values(path):
        return False, ""
    text = read_pdf(path, cache_dir).strip()
    # 🔴 THE RATE, NOT ONLY THE TOTAL - see MIN_CHARS_PER_PAGE. A document-wide floor is passed by
    # any scan long enough, because per-page furniture accumulates: page numbers, a running header,
    # an OCR engine's empty-page marker. The longer the scan, the safer it looks.
    pages = _page_count(path)
    if pages >= PAGES_BEFORE_RATE_APPLIES and len(text) / float(pages) < MIN_CHARS_PER_PAGE:
        return True, ("%d characters over %d pages - fewer than %d a page: page furniture over "
                      "scanned pages" % (len(text), pages, MIN_CHARS_PER_PAGE))
    if len(text) < MIN_TEXT_LAYER:
        why = _short_pdf_why(path, len(text), cache_dir)
        return (True, why) if why else (False, "")
    return False, ""


def _short_pdf_why(path, n, cache_dir):
    """K093: "" when a PDF whose text is `n` (< MIN_TEXT_LAYER) characters reads as a real short
    typeset document; otherwise why it does not."""
    if not n:
        return "no text at all - a scan without OCR, or an empty page"
    cls = (text_layer(path, cache_dir) or {}).get("class")
    if cls in ("ocr", "mixed"):
        return ("an OCR text layer of %d characters - the words of a scan, and the OCR engine read "
                "almost none of them" % n)
    if cls != "typeset":
        return "%d characters - too few on any page to be a text layer" % n
    try:
        fitz = _pdfengine.load()
    except ImportError:
        return ("%d characters of typeset text - without PyMuPDF a stamp over a scan cannot be told "
                "from a short document" % n)
    body = False
    try:
        d = fitz.open(path)
        try:
            for pg in d:
                r = pg.rect
                area = abs(r) or 1.0
                cover = sum(abs(fitz.Rect(im["bbox"]) & r) for im in pg.get_image_info()) / area
                if cover >= PICTURE_COVER:
                    return ("%d characters of typeset text over a picture that covers %d %% of page "
                            "%d - the picture can hold the page's words" % (n, min(100, round(100 * cover)),
                                                                         pg.number + 1))
                w, h = r.width or 1.0, r.height or 1.0
                for blk in pg.get_text("dict").get("blocks", []):
                    for ln in blk.get("lines", []):
                        if not "".join(s.get("text", "") for s in ln.get("spans", [])).strip():
                            continue
                        x0, y0, x1, y1 = ln["bbox"]
                        cx, cy = (x0 + x1) / 2.0 - r.x0, (y0 + y1) / 2.0 - r.y0
                        if (STAMP_BAND * w <= cx <= (1 - STAMP_BAND) * w
                                and STAMP_BAND * h <= cy <= (1 - STAMP_BAND) * h):
                            body = True
        finally:
            d.close()
    except Exception as exc:                                # noqa: BLE001 - the answer stays «excluded»
        return "%d characters - its pages could not be measured (%s)" % (n, type(exc).__name__)
    if not body:
        return ("its only text (%d characters) stands in the page margin - a stamp, an exhibit label "
                "or a header; the page's own words are in a picture, drawn as shapes, or missing" % n)
    return ""


def _page_count(path):
    """Page count from whichever engine answers. 0 when neither does, which disables the rate test
    rather than inventing a denominator."""
    try:
        import pypdf
        return len(pypdf.PdfReader(path).pages)
    except Exception:
        pass
    try:
        fitz = _pdfengine.load()
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
