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

from .normalize import alnum, normalise, strip_scrape_artifacts, _PAGE_MARK_RE
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
           "page_table_facts", "printed_span", "marker_table", "MARK_LEAD", "MARK_BROKEN",
           "zone_table", "ZONE_NONE", "ZONE_BROKEN",
           "pdf_text_verdict", "STAMP_BAND", "PICTURE_COVER", "picture_pages", "picture_pages_cell",
           "PICTURE_ADVICE", "BODY_TEXT_MIN", "SHAPES_MIN"]

_PAGE_MARK = _PAGE_MARK_RE          # one home: normalize (K018b widened it to the Statutes at Large)
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

# 🔴 K096: THE SAME LABELLED PICTURE ABOVE THE FLOOR WAS INDEXED SILENTLY - AND ITS WORDS NEVER WERE.
#
# K093 kept a scan, a photo or a screenshot of a document under a typeset exhibit label out of the
# corpus while its file stayed under MIN_TEXT_LAYER. The same page passed as soon as its file
# carried 200 characters - a multi-page exhibit, a longer label, a typeset page in front - and a
# quotation of the picture's words came back NOT FOUND, the fabrication signal, with nothing to say
# that those words were never in the text. Census of a real matter's copy (2026-11-26; Tesseract on
# each page rendered WITH its text, minus the words its text layer holds): 747 of the 2 071 pages
# of its 314 indexed exhibit PDFs that are not an OCR layer show 30 or more words their layer lacks.
# So every page of an indexed PDF is asked K093's question: fewer than BODY_TEXT_MIN characters
# stand in the page body (inside STAMP_BAND) while pictures cover PICTURE_COVER of the page, or the
# page draws SHAPES_MIN vector paths (words drawn as shapes). Measured there: 632 exhibit pages in
# 122 files flagged - 564 hold 30+ words the layer lacks, 68 are pictures with almost no readable
# words (photos: under 10 confident words on 61, read upright and turned); the flagged pages carry
# at most 43 layer words, so no typeset page is among them; and 0 of the law library's 1 498 pages.
# A floor of body characters rather than «no body line»: a one-line caption in the body over a
# scan is still a label (+12 pages, +2 photos). A page an OCR engine already read (K024's OCR page)
# is left to the OCR label: its engine looked at the picture (8 such pages, all wordless).
# NOT seen - stated so it is not mistaken for coverage (183 of the 747): a picture under 50+
# characters of body text (an embedded screenshot, a caption block over a scan - 143), a font that
# maps its glyphs to the wrong letters, a picture under a tenth of the page holding words (a
# letterhead, a seal). Docling's «picture not backed by text» test (base_ocr_model.py,
# TEXT_BACKED_MIN_COVERAGE) would have flagged 70 typeset pages of that copy - a warning that fires
# on a letterhead or a background picture teaches users to ignore it.
# 🔴 ONE COORDINATE SPACE. PyMuPDF returns text and image boxes for the UNROTATED page, while
# `page.rect` is the rotated one (docs, Page: «except Page.rect ... all coordinates returned by
# methods and attributes pertain to the unrotated page»). K093 compared them directly: on a
# /Rotate 90 or 270 page a body line could read as margin and a page-sized picture as 77 % (3
# exhibit pages of that copy). Every box goes through `rotation_matrix` first (_page_geometry).
BODY_TEXT_MIN = 50
SHAPES_MIN = 50
PICTURES_VERSION = "1"
_PICTURES_MEMO = {}
PICTURE_ADVICE = ("their words are in a picture (a scan, a photo or a screenshot of a document) or "
                  "drawn as shapes, and the text layer holds little more than a label there - a "
                  "quotation of those words comes back NOT FOUND. OCR those pages with an OCR engine "
                  "that also reads pages carrying some text (OCRmyPDF --redo-ocr keeps the label; "
                  "--skip-text passes such a page over because of it) - never a language model")

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
#
# 🔴 K018b: THE PRINTED PAGE IS WHAT A PAGE PRINTS - PROVEN BY THE FILE'S OWN SEQUENCE.
#
# A pincite names the page the reporter printed («21 I&N Dec. 296, 299»), and a reprint prints it on
# a line of its own: on a copy of a real matter's law library 238 of 264 pages of 30 I&N Dec. PDFs
# print P+i-1 that way. The other 26 print a number the OCR misread (996 for 496 - six pages) or no
# number in their text at all (first and last pages; every second page of one file). So a page's
# printed number is a number standing alone on one of its lines, accepted only when it fits the ONE
# offset (printed - file page) that most numbered pages of the file share; a page that prints no
# number of that run is counted only when pages that do stand on BOTH sides of it (a page cannot be
# missing between two pages whose numbers differ by their distance), and one outside the run's ends -
# a cover sheet, a last page - stays «printed page unknown», because a wrong page is worse than none.
# Two runs of similar strength (two parts numbered apart) name no printed page; a table of numbers on
# a few pages makes a plateau of weak offsets, not a peak, so it cannot outvote a real run. Never
# parsed from the file name: names are the user's.
PAGES_VERSION = "2"
_PAGES_MEMO = {}
PRINTED_LINE_RE = re.compile(r"(?m)^[ \t]*\[?(\d{1,5})\]?[ \t]*$")
PRINTED_MIN_RUN = 2
PRINTED_NONE = "its pages print no number on a line of their own"
PRINTED_FEW = "fewer than two of its pages print a number in one sequence"
PRINTED_TWO = "its pages print numbers in more than one sequence"
PRINTED_OUTSIDE = ("that page prints no number of the file's sequence and stands outside the "
                   "numbered pages")
PRINTED_BETWEEN = "counted - that page prints no number of its own, the pages around it do"


def _printed_pages(pages, also=None):
    """K018b: the number each page prints, by the pages' own text (see the note above).

    `{"offset": d, "kinds": "ppbn…", "why": ""}` - page i (1-based) printed i+d when kinds[i-1] is
    "p" (it prints that number on a line of its own) or "b" (it prints none of the run, and pages of
    the run stand before and after it); "n" - unknown. `{"offset": None, "kinds": "", "why": …}` when
    the file shows no single run.

    `also`: the OTHER engine's texts of the same pages. A number either engine reads alone on a line
    counts: pypdf - the engine the corpus indexes in 67 of 68 law PDFs of a real matter - glues the
    page number to a neighbouring line in 20 of the 101 that PyMuPDF reads cleanly (K018b census), and
    a page is the same page whichever engine read it. The vote below still has to agree."""
    cands = [{int(x) for x in PRINTED_LINE_RE.findall(t or "")} for t in pages]
    if also is not None and len(also) == len(pages):
        for c, t in zip(cands, also):
            c.update(int(x) for x in PRINTED_LINE_RE.findall(t or ""))
    votes = {}
    for i, c in enumerate(cands, 1):
        for d in {x - i for x in c}:
            votes[d] = votes.get(d, 0) + 1
    if not votes:
        return {"offset": None, "kinds": "", "why": PRINTED_NONE}
    ranked = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
    d, k1 = ranked[0]
    k2 = ranked[1][1] if len(ranked) > 1 else 0
    if k1 < PRINTED_MIN_RUN:
        return {"offset": None, "kinds": "", "why": PRINTED_FEW}
    if k2 >= PRINTED_MIN_RUN and 2 * k2 >= k1:
        return {"offset": None, "kinds": "", "why": PRINTED_TWO}
    proven = [(i + d) in c for i, c in enumerate(cands, 1)]
    first = proven.index(True)
    last = len(proven) - 1 - proven[::-1].index(True)
    kinds = "".join("p" if p else ("b" if first < k < last else "n") for k, p in enumerate(proven))
    return {"offset": d, "kinds": kinds, "why": ""}


def printed_span(printed, a, b):
    """K018b: `([first, last], how)` - the printed pages of PDF pages a..b (1-based), `how` "page"
    when each page prints its own number, "between" when one of them is counted from its neighbours;
    `(None, why)` when they cannot be named."""
    if not printed or printed.get("offset") is None:
        return None, (printed or {}).get("why") or "its printed pages were not measured"
    ks = (printed.get("kinds") or "")[a - 1:b]
    if a < 1 or len(ks) != b - a + 1:
        return None, "its printed pages were not measured"
    if "n" in ks:
        return None, PRINTED_OUTSIDE
    d = printed["offset"]
    return [a + d, b + d], ("between" if "b" in ks else "page")


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


def _page_facts(pages, engine, fields, also=None):
    """K018: letters and digits per page of the extraction the text came from, plus a hash of
    them all. `fields`: form-field values were appended after the last page (they have no page).
    K018b: `printed` - the printed-page run of those pages, `also` the other engine's texts."""
    al = [alnum(normalise(strip_scrape_artifacts(t or ""))) for t in pages]
    return {"v": PAGES_VERSION, "engine": engine, "alnum": [len(a) for a in al],
            "sha1": hashlib.sha1("".join(al).encode("utf-8")).hexdigest(), "fields": bool(fields),
            "printed": _printed_pages(pages, also)}


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
    fields, tried, fp = bool(_form_values(path)), [], None
    try:
        fitz = _pdfengine.load()
    except ImportError:
        fitz = None
    if fitz is not None:
        try:
            d = fitz.open(path)
            try:
                fp = [pg.get_text() for pg in d]
            finally:
                d.close()
            got = _page_facts(fp, "PyMuPDF", fields)
            if page_check(got, at)[0] is not None:
                return got
            tried.append("PyMuPDF")
        except Exception:                                   # noqa: BLE001 - advisory
            pass
    try:
        import pypdf
        got = _page_facts([(pg.extract_text() or "") for pg in pypdf.PdfReader(path).pages],
                          "pypdf", fields, also=fp)
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
    (see `page_check`); `(None, why)` when the page of a match there cannot be told."""
    ends, why, _facts = page_table_facts(path, at, cache_dir)
    return ends, why


def page_table_facts(path, at, cache_dir=None):
    """`page_table` plus the accepted page facts (K018b: their "printed" run), `{}` with no ends.

    The counts come from this run's extraction, else from the pages file beside the text cache,
    else from a re-read - and whichever it is, they are CHECKED against `at` before they are used:
    counts that do not add up to the text name no page. Only counts that add up are kept."""
    try:
        key = _layer_key(path)
    except OSError:
        return None, "the file is gone", {}
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
            return ends, "", facts
    got = _measure_pages(path, at)
    ends, why = page_check(got, at)
    if ends is None:
        return None, got.get("why") or why, {}
    _PAGES_MEMO[key] = got
    if lp:
        _write_layer(lp, got)
    return ends, "", got


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
    pfacts = None if repair_failed else _page_facts(
        pages, pengine, fields,
        also=(None if repaired_pages is not None else fpages if pages is pparts else pparts))
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
        raw = _text_body(path, low)
    except OSError:
        return ""
    return _text_finish(raw, low)


def _text_body(path, low):
    """A text source as `read_any` reads it, with its GPO page markers still in it (K018b)."""
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    if low.endswith((".xml", ".html", ".htm")):
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<[^>]+>", " ", raw)
        # 🔴 Entities matter more than they look. Official XML stores the section sign as `&#xA7;`.
        # Without unescaping, `§ 103.2` in the corpus becomes `S 103.2` while the quotation still
        # says `§ 103.2`, and a provably correct quotation cannot be found. That single defect
        # depressed a whole verification run's numbers and inflated its "extraction artefact" bin.
        raw = html.unescape(raw)
    return raw


def _text_finish(raw, low):
    raw = _PAGE_MARK.sub(" ", raw)
    if low.endswith(".md"):
        raw = _MD_FOOTNOTE.sub(" ", raw)
        raw = _MD_LINK.sub(r"\1", raw)
        raw = raw.replace("\\[", "[").replace("\\]", "]")
    return raw


# 🔴 K018b: A GPO TEXT CARRIES ITS PRINTED PAGES AS MARKERS - AND `read_any` THROWS THEM AWAY.
#
# `[[Page 41300]]` (Federal Register) and `[[Page 110 STAT. 3009-547]]` (Statutes at Large) mark
# where a printed page begins; on a real matter's law shelf there are 1 999 of them in 23 files,
# 1 017 mid-sentence, so the clean-up must remove them. They are read here BEFORE that: the raw text
# is split at the markers, each piece is cleaned exactly as the corpus cleans a whole file, and the
# pieces' letters and digits must add up to the text the corpus indexed (K018's invariant,
# `page_check`) - or no page is named. The text before the first marker is GPO's header and, in an
# excerpt, the end of the page before it: it takes the page the source's own «[Pages N-M]» line
# names when N is the page just before the first marker's, and stays unknown otherwise.
_GPO_PAGES_RE = re.compile(r"\[Pages?\s+(\d+)(?:\s*-\s*\d+)?\]")
MARK_LEAD = "the words stand before the source's first page marker"
MARK_BROKEN = "its page markers do not add up to the indexed text"


def marker_table(path, at):
    """K018b: `(ends, labels, why)` for the text source `path` whose indexed letters-and-digits
    text is `at`: `ends[k]` - where its piece k ends (piece 0 is the text before the first marker),
    `labels[k]` - the printed page piece k stands on, as its marker writes it (None: unknown).
    `(None, None, "")` for a source with no page markers; `(None, None, why)` when they do not add
    up to `at`."""
    low = path.lower()
    if low.endswith((".pdf", ".docx", ".doc")):
        return None, None, ""
    try:
        raw = _text_body(path, low)
    except OSError:
        return None, None, "the file is gone"
    marks = list(_PAGE_MARK.finditer(raw))
    if not marks:
        return None, None, ""
    cuts = [0] + [m.end() for m in marks]
    stops = [m.start() for m in marks] + [len(raw)]
    al = [alnum(normalise(strip_scrape_artifacts(_text_finish(raw[s:e], low))))
          for s, e in zip(cuts, stops)]
    ends, _why = page_check({"alnum": [len(a) for a in al], "fields": False,
                             "sha1": hashlib.sha1("".join(al).encode("utf-8")).hexdigest()}, at)
    if ends is None:
        return None, None, MARK_BROKEN
    labels = [None] + [" ".join(m.group(1).split()) for m in marks]
    lead = _GPO_PAGES_RE.search(raw, 0, marks[0].start())
    if lead and labels[1].isdigit() and int(lead.group(1)) == int(labels[1]) - 1:
        labels[0] = lead.group(1)
    return ends, labels, ""


# 🔴 K018c (2026-11-27): THE ZONES OF A DECISION. A brief that quotes «Matter of X, 21 I&N Dec. 296, 299»
# may be quoting the HEADNOTE - the summary above the opinion, which EOIR adds when it prepares a decision
# for publication (EOIR Policy Manual, Part III, ch. 1.4: «Headnotes are added, and an I&N Decision
# citation is assigned») - or a DISSENT; both verify, because the words are in the file. Where they stand
# inside the decision is read from the lines the reporter prints between the parts. Measured on a copy of
# a real matter's law shelf (43 I&N Dec. files, `private` K018c census): the opinion opens at the first
# counsel / charge / panel line under the «Decided …» line - «FOR RESPONDENT:», «ON BEHALF OF SERVICE:»
# (and the OCR's «ON BEHALF* OF», «PNITHONER»), «CHARGE:», «BEFORE:», «BY:», an Attorney General's
# «BEFORE THE ATTORNEY GENERAL» - and a separate opinion at its own heading («DISSENTING OPINION: …»,
# «CONCURRING AND DISSENTING OPINION: …»). A Regional Commissioner's decision prints none of those
# lines: «zone unknown», never a guess. A file is read as a decision only by its own head («Interim
# Decision» or «I&N Dec.», and a «Decided … <year>» line) - never by its name, which is the user's.
# The boundaries are cut in the text `read_any` returns and must add up to the indexed text (K018's
# discipline): the letters and digits of the pieces, cleaned as the corpus cleans a file, joined, ARE
# the indexed text - or no zone is named.
# The census's own corrections, each a file of that shelf: the decision line also reads «Designated by Commissioner …»
# and «Decided October 20, 20101» (a footnote number on the year); a court of appeals writes «Decided: <date>» with
# a colon (and cites I&N Dec. in its body - the mark may not be required ABOVE the decision line: two Board reprints
# print «Interim Decision #…» below it); a file holding a Board
# decision and the Attorney General's review of it opens each part with «BEFORE THE BOARD» / «BEFORE THE ATTORNEY
# GENERAL», and a dissent printed between them ends there; a separate opinion is also headed «CONCURRING IN PART AND
# DISSENTING IN PART:» and «Maurice A. Roberts, Chairman, Dissenting:». The panel line's own «Dissenting Opinion:
# HEILMAN» (mixed case, mid-line) is not a heading.
ZONE_HEAD = 6000      # characters of a file's head that hold the marks of a decision and its opening line
_DEC_MARK_RE = re.compile(r"Interim\s+Decision|I\.?\s*&\s*N\.?\s+Dec\b", re.I)
_DECIDED_RE = re.compile(r"(?m)^[ \t>*_#]*(?:Decided|Designated)\b(?![ \t]*:)[^\n]{0,80}?(?:1[89]|20)\d\d")
_MAIN_RE = r"BEFORE[ \t]+THE[ \t]+(?:BOARD|ATTORNEY[ \t]+GENERAL)\b"
_OPENS_RE = re.compile(
    r"(?m)^[ \t>*_#]*(?:CHARGES?[ \t]*:|ON[ \t]+BEHALF\b|FOR[ \t]+[A-Z][A-Z .,'&/-]{2,90}:|BEFORE[ \t]*:|"
    r"B[Yy][ \t]*:|%s)" % _MAIN_RE)
_PARTS_RE = re.compile(
    r"(?m)^[ \t>*_#]*(?:(?P<main>%s)|(?:CONCURRING|DISSENTING)\b[A-Z ,]{0,60}?(?:OPINION\b|:)|"
    r"[A-Z][A-Za-z.' -]{1,60}(?:,[ \t]*[A-Z][A-Za-z .'-]{1,40})?,[ \t]*(?:Dissenting|Concurring)"
    r"(?:[ \t]+in[ \t]+[Pp]art)?[ \t]*:[ \t]*$)[^\n]*" % _MAIN_RE)
ZONE_NONE = "no counsel, charge or panel line under the decision's caption marks where the opinion begins"
ZONE_BROKEN = "its zones do not add up to the indexed text"


def zone_table(path, at, cache_dir=None):
    """K018c: `(zones, why)` for the file `path` whose indexed letters-and-digits text is `at`:
    `zones` - `[(start, kind, line)]` in `at`, kind «headnote» (from the top: caption and headnote),
    «opinion» (from the line that opens it) or «separate» (a dissenting or concurring opinion, from its
    heading), `line` the source's own line there. `(None, "")` for a file that is not a decision;
    `(None, why)` for a decision whose zones cannot be told."""
    raw = read_any(path, cache_dir)
    raw = raw if isinstance(raw, str) else ""
    head = raw[:ZONE_HEAD]
    dec = _DECIDED_RE.search(head)
    if not dec or not _DEC_MARK_RE.search(head):
        return None, ""
    opens = _OPENS_RE.search(head, dec.end())
    if not opens:
        return None, ZONE_NONE
    eol = raw.find("\n", opens.start())
    cuts = [(opens.start(), "opinion", raw[opens.start():eol if eol >= 0 else len(raw)])]
    cuts += [(m.start(), "opinion" if m.group("main") else "separate", m.group(0))
             for m in _PARTS_RE.finditer(raw, eol if eol >= 0 else len(raw))]
    bounds = [0] + [c for c, _k, _l in cuts] + [len(raw)]
    al = [alnum(normalise(strip_scrape_artifacts(raw[a:b]))) for a, b in zip(bounds, bounds[1:])]
    if "".join(al) != at:
        return None, ZONE_BROKEN
    zones, n = [(0, "headnote", "")], len(al[0])
    for (_c, kind, line), piece in zip(cuts, al[1:]):
        line = " ".join(line.replace("*", " ").split())
        zones.append((n, kind, line[:100]))
        n += len(piece)
    return zones, ""


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
                g = _page_geometry(fitz, pg, text=True)
                if g["cover"] >= PICTURE_COVER:
                    return ("%d characters of typeset text over a picture that covers %d %% of page "
                            "%d - the picture can hold the page's words" % (n, min(100, round(100 * g["cover"])),
                                                                         pg.number + 1))
                body = body or g["body"] > 0
        finally:
            d.close()
    except Exception as exc:                                # noqa: BLE001 - the answer stays «excluded»
        return "%d characters - its pages could not be measured (%s)" % (n, type(exc).__name__)
    if not body:
        return ("its only text (%d characters) stands in the page margin - a stamp, an exhibit label "
                "or a header; the page's own words are in a picture, drawn as shapes, or missing" % n)
    return ""


def _page_geometry(fitz, pg, text=False):
    """K093 / K096: what one PDF page draws that its text layer may not hold, in ONE coordinate space
    (every box through `rotation_matrix` - see BODY_TEXT_MIN): `cover` - the page's share under
    pictures (placements summed and clipped; overlapping ones can pass 1.0); `paths` - vector paths
    drawn, counted only while `cover` is under PICTURE_COVER; `body` / `edge` - characters whose
    centre stands inside / outside the page body (STAMP_BAND), read only when `text` is set or the
    page is a candidate (a picture or SHAPES_MIN paths) - the per-character trace is the costly part."""
    R, M = pg.rect, pg.rotation_matrix
    area = abs(R) or 1.0
    cover = sum(abs((fitz.Rect(im["bbox"]) * M) & R) for im in pg.get_image_info()) / area
    paths = 0
    if cover < PICTURE_COVER:
        paths = sum(1 for b in pg.get_bboxlog() if b[0] in ("fill-path", "stroke-path"))
    g = {"cover": cover, "paths": paths, "body": 0, "edge": 0}
    if not (text or cover >= PICTURE_COVER or paths >= SHAPES_MIN):
        return g
    w, h = R.width or 1.0, R.height or 1.0
    for sp in pg.get_texttrace():
        for ch in sp.get("chars") or ():
            if ch[0] in (9, 10, 13, 32):
                continue
            b = fitz.Rect(ch[3]) * M
            cx, cy = (b.x0 + b.x1) / 2.0 - R.x0, (b.y0 + b.y1) / 2.0 - R.y0
            if STAMP_BAND * w <= cx <= (1 - STAMP_BAND) * w and STAMP_BAND * h <= cy <= (1 - STAMP_BAND) * h:
                g["body"] += 1
            else:
                g["edge"] += 1
    return g


def _page_set(ranges):
    """`1-3, 5` -> {1, 2, 3, 5} (the inverse of `_ranges`)."""
    out = set()
    for part in (ranges or "").split(","):
        a, _, b = part.strip().partition("-")
        if a.isdigit():
            out.update(range(int(a), int(b) + 1) if b.isdigit() else (int(a),))
    return out


def picture_pages(path, cache_dir=None):
    """K096: the pages of the PDF `path` whose words are in a picture or drawn as shapes while its
    text layer holds next to nothing there (see BODY_TEXT_MIN). A dict - `pages` (the count),
    `flagged` ([[page, why], ...], page = the file's own page index from 1), `engine` - or None for a
    non-PDF, an unreadable file, or a machine without PyMuPDF (the geometry is PyMuPDF's). Kept
    beside the text cache under the same key, and in memory for the run."""
    if not path.lower().endswith(".pdf"):
        return None
    try:
        key = _layer_key(path)
    except OSError:
        return None
    got = _PICTURES_MEMO.get(key)
    if got is not None:
        return got
    lp = _cache_path(path, cache_dir)[:-4] + ".pictures.json" if cache_dir else None
    if lp and os.path.exists(lp):
        try:
            with io.open(lp, encoding="utf-8") as fh:
                got = json.load(fh)
        except (OSError, ValueError):
            got = None
        if isinstance(got, dict) and got.get("v") == PICTURES_VERSION:
            _PICTURES_MEMO[key] = got
            return got
    try:
        fitz = _pdfengine.load()
    except ImportError:
        return None
    ocr = _page_set((text_layer(path, cache_dir) or {}).get("ocr_pages"))
    flagged = []
    try:
        d = fitz.open(path)
        try:
            n = d.page_count
            for pg in d:
                if pg.number + 1 in ocr:                    # an OCR engine read it (K024's label)
                    continue
                g = _page_geometry(fitz, pg)
                if g["body"] >= BODY_TEXT_MIN:
                    continue
                held = ("no text" if not g["body"] + g["edge"] else
                        "only %d characters, at the page's edges" % g["edge"] if not g["body"] else
                        "only %d characters" % (g["body"] + g["edge"]))
                if g["cover"] >= PICTURE_COVER:
                    flagged.append([pg.number + 1, "a picture covers %d %% of the page; its text layer holds "
                                    "%s" % (min(100, round(100 * g["cover"])), held)])
                elif g["paths"] >= SHAPES_MIN:
                    flagged.append([pg.number + 1, "the page draws %d vector shapes; its text layer holds "
                                    "%s" % (g["paths"], held)])
        finally:
            d.close()
    except Exception:                                       # noqa: BLE001 - advisory
        return None
    got = {"v": PICTURES_VERSION, "engine": "PyMuPDF", "pages": n, "flagged": flagged}
    _PICTURES_MEMO[key] = got
    if lp:
        _write_layer(lp, got)
    return got


def picture_pages_cell(facts):
    """`all 3 pages` / `pages 2-3 of 5` - the short form for lists (K096)."""
    nums = [p for p, _ in facts.get("flagged") or ()]
    if len(nums) > 1 and len(nums) == facts.get("pages"):
        return "all %d pages" % len(nums)
    return "page%s %s of %d" % ("s" if len(nums) > 1 else "", _ranges(nums), facts.get("pages") or 0)


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
