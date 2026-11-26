# -*- coding: utf-8 -*-
"""Cross-check exhibits and forms between petition documents and the filing folder.

Before printing, you need to know: does every exhibit the petition promises actually exist as
a file, and does every file in the exhibit folder actually get mentioned somewhere? The first
class (cited, no file) is the one that costs a filing — the adjudicator follows the reference
and finds nothing. The second class (file, no citation) is either a forgotten argument or dead
weight; a human decides.

Forms get the same treatment: the petition says "Form I-485 (Exhibit A-1)" and the forms folder
should contain a file whose name starts with "I-485" or "i-485".

The tool reads petition documents (.md, .txt, .docx, and .pdf where a PDF engine is installed)
and scans exhibit/form directories. Exhibit FILES are matched by filename only. 🔴 R77 (#334,
spark12cont + 3) SUPERSEDES the older "does NOT read PDF content" line: a petition saved as PDF
in a mixed folder used to contribute zero references, silently — the reconciliation then reported
its exhibits as FILE-NO-CITE and missed its broken references entirely. A petition file that
cannot be read is now a LOUD report row, never a quiet zero.
"""
from __future__ import annotations

import collections
import io
import os
import re
import unicodedata

from .corpus import walk_error
from .readers import MissingReader
# 🔴 R77 (F-C minor): sentinel imports moved inside `_is_tool_output` so module load does not
# eagerly import `.run` - a fork-cycle magnet (R76 F5 lesson: an undocumented near-twin is a
# fork ageing in silence, and eager cross-module imports are what make a future cycle silent).


def _is_tool_output(path):
    """A file stamped as this toolkit's own output (sidecars, dumps, reports). Content, not name:
    the sentinel doctrine from `run.py`, applied to the scanners here so a `X.text.md` sidecar
    sitting beside its PDF is not counted as an exhibit file or a petition (R77, #347 class).

    🔴 Deliberate near-twin of `run._is_tool_output`: same window (SENTINEL_HEAD), different
    admission gate. This one gates to .md/.txt so binaries are never opened; run.py's version
    classifies ANY draft file. Unify the WINDOW only, never the functions - R76 F5."""
    if not path.lower().endswith((".md", ".txt")):
        return False
    from .run import SENTINELS, SENTINEL_HEAD          # F-C minor: lazy sentinel imports
    try:
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(SENTINEL_HEAD)
        return any(s in head for s in SENTINELS)
    except OSError:
        return False


# ------------------------------------------------------------------------------- exhibit IDs

# Series letters allowed in exhibit IDs. Anything else that looks like "X-123" is noise
# (form numbers like G-1450, visa classes like H-1B, filing numbers like I-485).
# This default covers the conventions seen in real filings; callers can override.
DEFAULT_SERIES = "A B C D E F G H J K L M P V W X".split()

# Form numbers that LOOK like exhibit IDs but are not. Without this, "Form G-1145" in the
# petition text would register as exhibit G-1145 and then be reported missing from the exhibit
# folder — a false alarm on every run.
NOT_EXHIBIT = frozenset({
    "G-28", "G-325", "G-884", "G-1055", "G-1145", "G-1450",
    "F-1", "F-2", "F-3", "H-1", "H-1b", "H-2",
    "J-1", "J-2", "L-1", "L-1a", "L-1b",
})

# Series whose "exhibits" are the documents themselves (memoranda, legal-base appendices),
# not files in the exhibit tree. They live in the petition folder, not the exhibit folder.
DOC_SERIES = frozenset({"M", "W"})

# 🔴 K092 (2026-11-26): 23 files of the I-140 package carried a CYRILLIC letter where the Latin one is meant (21 «О»
# U+041E in series O, 2 «С» U+0421 in series C) - the eye cannot tell, a Russian keyboard types them, and every id
# reader saw no id. The table is Unicode's own: UTS #39 confusables.txt (version 18.0.0, 2026-08-06), the Cyrillic and
# Greek CAPITAL letters it maps to ONE Latin capital (a small letter folds through `.upper()`; reading is case-blind).
# A folded letter is read AND named in the report: the name still sorts, searches and prints as another letter.
LOOKALIKE = dict(zip(
    "АВСЕԌНЈКМОРԚЅТѴԜХУҮ"
    "ΑΒϹΕϜΗͿΚΜϺΝΟΡΤΧΥϒΖ",
    "ABCEGHJKMOPQSTVWXYY" "ABCEFHJKMMNOPTXYYZ"))
_LOOK = "".join(sorted(LOOKALIKE))


def _fold(ch):
    """The Latin capital a typed series letter stands for («О» U+041E -> «O», «k» -> «K»)."""
    up = ch.upper()
    return LOOKALIKE.get(up, up)


# Exhibit-ID extraction from document TEXT. The pattern must be strict: in prose, "I-485",
# "H-1B", "F-1" are visa/form codes, not exhibit numbers. Only the declared series match.
# Sub-exhibit suffixes (D-19a, D-19c) are captured. Leading zeros are stripped in canon().
#
# 🔴 K092 (2026-11-26), measured on a names copy of the AOS matter (`private\reports\K092\probe*.log`):
#  - the WORD decides. «(Exhibit J-1)», «(Exhibit F-1)», «(Exhibit L-1)» stood in the drafts 16-46 times each and were
#    dropped, because NOT_EXHIBIT (codes standing bare) was applied after the word «Exhibit» too - and the filed I-485
#    package HAS J-1, J-2, L-1, H-1 and 12 parts of H-2. After «Exhibit / Exhibits / Ex. / Exh.» any letter is an
#    exhibit id; a BARE token must still be a series letter and not a code (`text_ids`). Only the token right after
#    the word: «Exhibit D-1 - I-20» would chain the dash to a form number - 209 times in the drafts.
#  - «V-67-1» is part 1 of V-67: the old `(?![-–—\d])` refused the whole id - 3 filed copies «Cross Exhibit V-67-1 …»
#    had no id and 56 mentions in the drafts were not read. A date «A-12-2024» stays refused (a digit after the part).
#  - a letter of another script that looks Latin (LOOKALIKE) is read as the Latin one, and named.
_ANCH = r"(?P<anch>Exhibits?\s+|Exh\.\s*|Ex\.\s*)"
_TAIL = r"\s*[-–—]\s*0*(?P<num>\d{1,4})(?P<suf>[a-zA-Z]?\d?)(?:[-–—](?P<part>\d{1,2}))?(?![-–—]?\d)"


def _letter_class(series):
    """The Latin letters of `series` and every look-alike of them; `series` None = any letter."""
    if series is None:
        return "[A-Z%s]" % _LOOK
    lat = "".join(sorted({s.upper() for s in series if len(s) == 1}))
    return "[%s%s]" % (lat, "".join(c for c in sorted(LOOKALIKE) if LOOKALIKE[c] in lat))


def _build_id_re(series):
    """Ids of `series` in text, after the word Exhibit or bare; `series` None = any letter. Groups: anch, let, num,
    suf, part - canonical id = canon(_fold(let), num, suf)."""
    return re.compile(r"(?<![^\W\d_])" + _ANCH + "?(?P<let>" + _letter_class(series) + ")" + _TAIL, re.I)


_ID_TEXT_RE = _build_id_re(None)
# Right after the word Exhibit, any letter - `facts._masked` blanks these like series ids (their digits are no fact).
ANCHORED_ID_RE = re.compile(r"(?<![^\W\d_])" + _ANCH + "(?P<let>" + _letter_class(None) + ")" + _TAIL, re.I)

# K-series: often written WITHOUT hyphen ("K1", "K12") in some briefs.
_K_RE = re.compile(r"(?<![A-Za-z])\bK\s*[-–—]?\s*0*(\d{1,4})([a-zA-Z]?)(?![-–—\d])")

# Exhibit-ID extraction from FILENAMES. More lenient: the hyphen between letter and number
# is optional because some files are named "Exhibit P01 - ..." without the hyphen.
def _build_file_re(series):
    """Ids of `series` at the START of a file name; `series` None = any letter. Groups: let, num, suf."""
    return re.compile(r"^(?:Exhibit\s+)?(?P<let>" + _letter_class(series) + r")\s*[-–—]?\s*0*(?P<num>\d{1,4})"
                      r"(?P<suf>[a-zA-Z]?\d?)(?![0-9])", re.I)


_NAME_RE = _build_file_re(None)
# A USCIS form number standing bare - never an exhibit of a series learned from a folder (`text_ids`), and never a
# name that teaches a series (`declared_series`): a forms folder holds I-485, G-1450, N-400.
_FORM_SHAPED = re.compile(r"^(?:I-\d{2,4}|N-\d{3})(?![0-9])")
_FORM_NAME = re.compile(r"^(?:I-\d{2,4}|G-\d{2,4}|N-\d{3})(?![0-9])")
_SERIES_DIR = re.compile(r"^Exhibits?\s+(" + _letter_class(None) + r")\s*$", re.I)

# Multi-part file suffix: B-03_1, B-03_2 are parts of the same exhibit, not duplicates.
PART_RE = re.compile(r"[-_](\d{1,2})(?:\D|$)")

# Document file extensions. Sidecar files (.evidence.json, .unconfirmed.json, .progress.json,
# .txt sidecars) are auxiliary data, not exhibits. Including them inflates duplicate counts.
DOC_EXTS = frozenset({
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp",
    ".md", ".txt", ".rtf", ".odt", ".html", ".htm",
})

# Action markers left in filenames by humans — an unclosed task.
ACTION_RE = re.compile(
    r"(FIXME|TODO|ИСПРАВИТЬ|ОБНОВИТЬ|СДЕЛАТЬ|ПРОВЕРИТЬ|DRAFT|ЧЕРНОВИК)", re.I)


def canon(series, num, suf):
    """Canonicalize an exhibit ID: uppercase letter, stripped leading zeros, lowercase suffix."""
    return "%s-%s%s" % (series.upper(), num.lstrip("0") or "0", suf.lower())


def _canon_m(m):
    return canon(_fold(m.group("let")), m.group("num"), m.group("suf"))


def text_ids(text, series=None):
    """(canonical id, match) for every exhibit id `text` cites. After the word Exhibit / Exhibits / Ex. / Exh. any
    letter is an id (the word says so, codes included: «Exhibit J-1»); a BARE token needs a letter of `series`, and
    must be neither a code (NOT_EXHIBIT) nor a bare form number. The memoranda series (DOC_SERIES) never count."""
    act = {s.upper() for s in (DEFAULT_SERIES if series is None else series)}
    out = []
    for m in _ID_TEXT_RE.finditer(text or ""):
        letter = _fold(m.group("let"))
        eid = canon(letter, m.group("num"), m.group("suf"))
        if letter in DOC_SERIES:
            continue
        if not m.group("anch") and (letter not in act or eid in NOT_EXHIBIT or _FORM_SHAPED.match(eid)):
            continue
        out.append((eid, m))
    if "K" in act:
        for m in _K_RE.finditer(text or ""):
            out.append((canon("K", m.group(1), m.group(2)), m))
    return out


def ids_in_text(text, series=None):
    """Extract all exhibit IDs from document text. Returns a set of canonical IDs."""
    return {eid for eid, _m in text_ids(text, series)}


def id_of(s):
    """The first exhibit id in `s` with ANY series letter - a user who types `--exhibit Y-3` has named an exhibit."""
    m = _ID_TEXT_RE.search(s or "")
    if m:
        return _canon_m(m)
    m = _K_RE.search(s or "")
    return canon("K", m.group(1), m.group(2)) if m else None


def name_id(fn, series=None):
    """(canonical id, the letter as typed, match) read from a file NAME, or None: at the start («Exhibit O1 …», «Y-12
    …», the dash optional), else the first id of `series` - or any id right after the word Exhibit - in its first 50
    characters («Cross Exhibit V-67-1 …»). `series` None = any letter."""
    act = None if series is None else {s.upper() for s in series}
    m = _NAME_RE.match(fn)
    if m and (act is None or _fold(m.group("let")) in act):
        return _canon_m(m), m.group("let"), m
    for m in _ID_TEXT_RE.finditer(fn[:50]):
        if act is None or m.group("anch") or _fold(m.group("let")) in act:
            return _canon_m(m), m.group("let"), m
    return None


def declared_series(root):
    """The series a package declares itself (🔴 K092): a folder named «Exhibit Y» / «Exhibits Y», or a letter that
    starts the names of 2+ files with different numbers. A form-shaped name (I-485, G-1450, N-400) never teaches a
    series - a forms folder would declare I, G and N. Measured on the AOS copy: the I-140 package declares
    ABCDEFGHKNOQVXY (its folders «Exhibit N» … «Exhibit Y»), the I-485 package BCDEGHJKLPX, the forms folder nothing."""
    nums = {}
    found = set()
    if not os.path.isdir(root):
        return found
    for dp, dirs, fns in os.walk(root, onerror=walk_error):
        m = _SERIES_DIR.match(os.path.basename(os.path.normpath(dp)))
        if m:
            found.add(_fold(m.group(1)))
        for fn in fns:
            if os.path.splitext(fn)[1].lower() not in DOC_EXTS:
                continue
            m = _NAME_RE.match(fn)
            if not m or _FORM_NAME.match(_canon_m(m)):
                continue
            nums.setdefault(_fold(m.group("let")), set()).add(int(m.group("num")))
    return found | {s for s, v in nums.items() if len(v) >= 2}


# ------------------------------------------------------------------------------- the exhibit LIST (K045)

# 🔴 K045: a petition prints an exhibit LIST - table rows whose id column is headed «Exhibit» / «Ex.» / «No.», or lines
# that open with an id and a description («Exhibit K28 - Letter from …») - and its ARGUMENT cites exhibits in sentences.
# Before K045 every id counted as «cited», so an exhibit the list promises and no sentence ever uses, a citation the
# list forgot and a file the list never names were all invisible. Measured on the AOS copy (the filed petition, 11
# documents): 43 of 76 tables carry such a column and list 274 ids; a bare «J-1» / «H-2» under an «Exhibit» header is an
# exhibit (the header is the context word - E-1099); «X-13 (= P-07)» names one exhibit twice (an alias: a file under
# either id serves both); «(K60-K66)» cites K-60 … K-66 - the product read only K-66 (`_K_RE` refuses an id followed
# by a dash), so every range start and middle read as «never cited».
_ID_HEADER = re.compile(r"^\s*(?:exhibits?|exh\.?|ex\.?|tabs?|id|no\.?|#|№)\s*(?:no\.?|#|id)?\s*$", re.I)
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}")
_LIST_MARK = re.compile(r"^\s*(?:[-*+•]\s+|\d{1,3}[.)]\s+)?")
_DESC_SEP = re.compile(r"^\s*[—–:\-.)]\s*\S.{4,}")
_ALIAS_SEP = re.compile(r"=|\bsame\s+as\b", re.I)
INDEX_LINE_MAX = 300        # a list line is short; a paragraph that opens with «Exhibit B-3 - …» is an argument
RANGE_MAX = 50              # «B-1 through B-50» at most; a wider «range» is two unrelated ids
RANGE_RE = re.compile(
    r"(?<![^\W\d_])(?:Exhibits?\s+|Exh\.\s*|Ex\.\s*)?(?P<let>[A-Z])\s*[-–—]?\s*0*(?P<a>\d{1,4})"
    r"\s*(?:[-–—]|(?i:to|through|thru)\b)\s*(?:(?i:exhibits?)\s+)?(?P=let)\s*[-–—]?\s*0*(?P<b>\d{1,4})(?![-–—]?[\d\w])")


def _plain(s):
    """A markdown cell or line without emphasis and link targets: «**K28**» -> «K28», «[A-1](a.pdf)» -> «A-1»."""
    s = re.sub(r"\[([^\]\n]*)\]\([^)\n]*\)", r"\1", s or "")
    return re.sub(r"\*\*|__|`", "", s).replace(" ", " ")


def _cell_entries(cell, series, anchored):
    """[(id, [aliases])] for an id cell: «B-3» -> one entry; «X-13 (= P-07)» -> X-13 with the alias P-7; «B-1, B-2» ->
    two entries. Under an id-column header the cell reads as if «Exhibit» stood before it; the cell must OPEN with an
    id - a description that mentions an exhibit is not an id cell."""
    c = _plain(cell).strip()
    if not c:
        return []
    probe = c if (not anchored or re.match(r"(?i)ex", c)) else "Exhibit " + c
    found = sorted(text_ids(probe, series), key=lambda t: t[1].start())
    if not found or re.sub(r"(?i)\b(?:exhibits?|exh|ex|tabs?|no)\b\.?|[#\s.:(]", "", probe[:found[0][1].start()]):
        return []
    out = [(found[0][0], [])]
    for k in range(1, len(found)):
        if _ALIAS_SEP.search(probe[found[k - 1][1].end():found[k][1].start()]):
            out[-1][1].append(found[k][0])
        else:
            out.append((found[k][0], []))
    have = {e for e, _a in out} | {a for _e, al in out for a in al}
    out.extend((e, []) for e in sorted(range_ids(probe, series) - have))      # «B-1 – B-5» lists B-2 … B-4 too
    return out


def _runs(ids):
    """«K-1, K-2, K-3, K-5» -> «**K-1…K-3**, **K-5**»: a list of 100+ ids stays readable; a part («H-10a») stands
    alone. `ids` sorted by series and number."""
    out, i = [], 0
    while i < len(ids):
        m = re.match(r"^([A-Z])-(\d+)$", ids[i])
        j = i
        while m and j + 1 < len(ids):
            n = re.match(r"^([A-Z])-(\d+)$", ids[j + 1])
            if not (n and n.group(1) == m.group(1) and int(n.group(2)) == int(m.group(2)) + j + 1 - i):
                break
            j += 1
        out.extend([ids[i]] if j == i else [ids[i], ids[j]] if j == i + 1 else ["%s…%s" % (ids[i], ids[j])])
        i = j + 1
    return ", ".join("**%s**" % x for x in out)


def _fam(e):
    """An exhibit's family key: «H-10a» and «H-10» are one exhibit's part and whole."""
    return re.sub(r"(?<=\d)[a-z]\d?$", "", e)


def _covered(e, pool):
    """`e` is in `pool` itself, as its whole («H-10» covers «H-10a») or as a part («X-23a» answers «X-23»)."""
    return e in pool or _fam(e) in pool or any(_fam(x) == e for x in pool)


def _table_entries(rows, series):
    """[(line number, id, aliases)] of one table: the column headed «Exhibit» / «Ex.» / «No.» (any letter there is an
    id), else column 0 when most rows open with an id. A .docx table arrives as «| a | b |» rows with no separator."""
    cells = [r.strip().strip("|").split("|") for _n, r in rows]
    col, anchored, start = None, False, 0
    if cells and any(_ID_HEADER.match(_plain(c)) for c in cells[0]):
        col = next(k for k, c in enumerate(cells[0]) if _ID_HEADER.match(_plain(c)))
        anchored, start = True, 1
    data = [(n, c) for (n, r), c in list(zip(rows, cells))[start:] if not _TABLE_SEP.match(r)]
    if col is None:
        if cells and len(rows) > 1 and _TABLE_SEP.match(rows[1][1]):
            data = data[1:] if data and data[0][0] == rows[0][0] else data      # a markdown header with no id word
        firsts = sum(1 for _n, c in data if c and _cell_entries(c[0], series, False))
        if len(data) < 2 or firsts < 0.6 * len(data):
            return []
        col = 0
    out = []
    for n, c in data:
        if col < len(c):
            for eid, al in _cell_entries(c[col], series, anchored):
                out.append((n, eid, al))
    return out


def exhibit_list(text, series=None):
    """The exhibit LIST a document prints (🔴 K045): ([(line number, id, aliases)], {line numbers of the list}). A list
    entry is a row of a table with an id column (`_table_entries`) or a line (<= INDEX_LINE_MAX characters, after a
    bullet) that opens with an id followed by a dash / colon and a description. Every other mention is a citation."""
    act = DEFAULT_SERIES if series is None else series
    lines = (text or "").splitlines()
    entries, used = [], set()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            got = _table_entries([(n + 1, lines[n]) for n in range(i, j)], act)
            entries.extend(got)
            used.update(n for n, _e, _a in got)
            i = j
            continue
        s = _plain(lines[i])
        if len(s.strip()) <= INDEX_LINE_MAX:
            pos = _LIST_MARK.match(s).end()
            found = sorted(text_ids(s, act), key=lambda t: t[1].start())
            pos += re.match(r"(?:Exhibits?\s+|Exh\.\s*|Ex\.\s*)?", s[pos:], re.I).end()      # «Exhibit K28 - …»
            if found and found[0][1].start() <= pos and _DESC_SEP.match(s[found[0][1].end():]):
                entries.append((i + 1, found[0][0], []))
                used.add(i + 1)
        i += 1
    return entries, used


def range_ids(text, series=None):
    """Every id a range names, both ends included: «Exhibits B-1 through B-5», «B-1 – B-5», «(K60-K66)» (🔴 K045 - the
    same letter on both ends, rising, at most RANGE_MAX apart; a part «V-67-1» or a date «A-12-2024» is not a range)."""
    act = {s.upper() for s in (DEFAULT_SERIES if series is None else series)}
    out = set()
    for m in RANGE_RE.finditer(text or ""):
        let, a, b = _fold(m.group("let")), int(m.group("a")), int(m.group("b"))
        if let in DOC_SERIES or (let not in act and not re.match(r"(?i)ex", m.group(0))) or not a < b <= a + RANGE_MAX:
            continue
        out.update("%s-%d" % (let, k) for k in range(a, b + 1))
    return out


# ------------------------------------------------------------------------------- form IDs

# Form references in text: "Form I-485", "Forms I-20", "Form G-1450", "Form ETA-9089"
FORM_TEXT_RE = re.compile(
    r"Forms?\s+((?:I|G|N|ETA)[-–—]?\d{2,5}[A-Z]?)", re.I)

# Form ID from filename: starts with form number pattern (case-insensitive)
FORM_FILE_RE = re.compile(
    r"^((?:I|G|N|ETA)[-–—]?\d{2,5}[A-Z]?)", re.I)


def canon_form(raw):
    """Canonicalize a form ID: uppercase, ensure hyphen after letter prefix."""
    s = raw.upper().replace("–", "-").replace("—", "-")
    if re.match(r"^[A-Z]{1,3}\d", s):
        m = re.match(r"^([A-Z]{1,3})(\d.*)$", s)
        if m:
            s = m.group(1) + "-" + m.group(2)
    return s


def forms_in_text(text):
    """Extract all form IDs from document text."""
    out = set()
    for m in FORM_TEXT_RE.finditer(text):
        out.add(canon_form(m.group(1)))
    return out


# ------------------------------------------------------------------------------- file reading

def _read_docx(path):
    """Extract text from a .docx file using only stdlib (zipfile + xml.etree).

    🔴 R77 (#335, agy31pro): runs are concatenated WITHOUT an invented separator, paragraphs
    with a newline. The old form space-joined every `<w:t>` piece, and Word freely splits a
    word across runs at a spell-check or formatting boundary - probe-proven: «Exhibit D-19»
    stored as `Exh` + `ibit D-19` came out as «Exh ibit D-19», so the ID regex never saw it
    and the reference silently vanished from the reconciliation. Word keeps real spaces
    INSIDE the runs; inventing one at every boundary breaks words instead of separating them.
    (grok420's «tables are dropped» half was wrong - `iter()` is recursive and reaches table
    cells; the paragraph walk below keeps that property, since `w:p` inside `w:tc` is found.)
    """
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        paras = []

        def ptext(p):
            pieces = []
            for el in p.iter():
                if el.tag == ns + "t" and el.text:
                    pieces.append(el.text)
                elif el.tag in (ns + "tab", ns + "br"):
                    pieces.append(" ")
            return "".join(pieces)

        # 🔴 K045: a table row is ONE line «| a | b |» - the exhibit list of a Word petition is a table, and a row read
        # as one line per cell lost which id stands in the «Exhibit» column (`exhibit_list`). Paragraphs keep their
        # order; content controls and other wrappers are walked into.
        def walk(node):
            for ch in node:
                if ch.tag == ns + "p":
                    t = ptext(ch)
                    if t:
                        paras.append(t)
                elif ch.tag == ns + "tbl":
                    for tr in ch.findall(ns + "tr"):
                        cells = [" ".join(t for t in (ptext(p) for p in tc.iter(ns + "p")) if t)
                                 for tc in tr.findall(ns + "tc")]
                        paras.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
                else:
                    walk(ch)
        walk(tree.getroot())
        return "\n".join(paras)
    except Exception as exc:
        # 🔴 R77 (#F-D, agy37flash MAJOR, probe-proven): a parse failure used to be swallowed to
        # "" and the petition's references vanished silently. zipfile and ElementTree are stdlib,
        # so any exception here is a parse problem (corrupt file, not-actually-a-.docx), not a
        # missing engine. Raise MissingReader with conversion advice so the caller lands it in
        # the loud "PETITION FILES NOT READ" section (F-D reconcile move below).
        raise MissingReader("corrupt or not a .docx (%s) - re-save it from Word "
                            "('Save As' .docx) and re-run" % type(exc).__name__)


# 🔴 R77 (F-D): text formats we read from directly; anything else is either sent to a reader
# (.docx/.pdf), refused loudly (.doc), or silently skipped by design (images, archives,
# spreadsheets — not petition text, do not open as soup and search).
_TEXT_EXTS = (".md", ".txt", ".markdown", ".htm", ".html")


def _read_text(path):
    """Text of a petition document. Empty string only for formats this tool does not handle;
    a HANDLED format that cannot be read raises `MissingReader` so the caller reports it loudly
    (R77 #334 - a silent "" here is how a PDF petition's references vanished; R77 F-D - a .doc
    silently returned "" and unknown binaries were decoded as soup and searched for IDs)."""
    low = path.lower()
    if low.endswith(".docx"):
        return _read_docx(path)                # raises MissingReader on a corrupt/not-a-docx file
    if low.endswith(".pdf"):
        from .readers import read_pdf
        return read_pdf(path)                  # raises MissingReader when no engine is installed
    if low.endswith(".doc"):
        # 🔴 R77 (#F-D, grokbuild + probe-proven): a binary Word file has no stdlib reader; the
        # old code silently returned "" and the references inside vanished from every count.
        # Loud beats lucky. The advice is one step: save as .docx once. Optional python-docx or
        # mammoth would not help — .doc needs antiword or a COM automation call, not those.
        raise MissingReader("legacy .doc has no stdlib reader - open in Word and 'Save As' "
                            ".docx once, then re-run.")
    if low.endswith(_TEXT_EXTS):
        try:
            return io.open(path, encoding="utf-8", errors="replace").read()
        except Exception:
            return ""
    # Everything else — images (.jpg/.png/.tif/…), archives (.zip/.7z/.rar), spreadsheets
    # (.xls/.xlsx/.pptx/…), unknown binaries — is not petition text and stays silently
    # skipped BY DESIGN. Do NOT open with errors="replace" and search: probe-proven with a
    # .sqlite file, an unknown binary decoded that way hit an exhibit ID by luck and blessed
    # a wrong file (R77 F-D, agy31pro finding on the soup-search shape).
    return ""


# ------------------------------------------------------------------------------- scanning

def scan_exhibit_dir(root, series=None):
    """Walk an exhibit directory tree and extract exhibit IDs from filenames.

    Returns:
        files: dict mapping canonical exhibit ID to list of full file paths
        problems: list of (kind, path) tuples for files with issues
    """
    if series is None:
        series = DEFAULT_SERIES
    files = {}
    problems = []
    if not os.path.isdir(root):
        return files, problems
    declared = declared_series(root)
    active = {s.upper() for s in series} | declared
    for dp, dirs, fns in os.walk(root, onerror=walk_error):
        dirs.sort()
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext not in DOC_EXTS:
                continue
            if _is_tool_output(full):
                continue                     # a sidecar beside its PDF is not a second exhibit
            got = name_id(fn, active)
            if not got:
                problems.append(("NO-ID", full))
                continue
            eid, typed = got[0], got[1]
            letter = eid.split("-")[0]
            # 🔴 K092: a code-shaped NAME (H-1, J-1, L-1, F-2, G-28) is an exhibit when the package itself uses the
            # series. The filed I-485 package holds 18 such files (J-1, J-2, L-1, H-1, 12 parts of H-2), the I-140
            # package 10 (F-2, F-3, G-28, H-1, H-2) - all 28 were dropped as NOT-EXHIBIT with no line in the report.
            # A forms folder declares no series, so «G-1450.pdf» there stays a form (and is listed).
            if letter in DOC_SERIES or (eid in NOT_EXHIBIT and letter not in declared):
                problems.append(("NOT-EXHIBIT", full))
                continue
            files.setdefault(eid, []).append(full)
            if typed.upper() in LOOKALIKE:
                problems.append(("LOOKALIKE", full))
            if ACTION_RE.search(fn):
                problems.append(("ACTION-MARKER", full))
    return files, problems


def scan_form_dir(root):
    """Walk a forms directory and extract form IDs from filenames.

    Returns:
        files: dict mapping canonical form ID to list of full file paths
        problems: list of (kind, path) tuples
    """
    files = {}
    problems = []
    if not os.path.isdir(root):
        return files, problems
    for dp, dirs, fns in os.walk(root, onerror=walk_error):
        dirs.sort()
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            # 🔴 R77 (#347, goog37flash): this walker had NO extension filter, so
            # `I-485.forms.txt` - this toolkit's own field dump, named after the form it dumps -
            # registered as a second copy of the form, and so did every sidecar JSON. Same
            # DOC_EXTS gate as the exhibit walker, the sentinel test for stamped output, and a
            # name-suffix skip for dumps written before the stamp existed.
            ext = os.path.splitext(fn)[1].lower()
            if ext not in DOC_EXTS:
                continue
            if fn.lower().endswith(".forms.txt") or _is_tool_output(full):
                continue
            m = FORM_FILE_RE.match(fn)
            if not m:
                problems.append(("NO-FORM-ID", full))
                continue
            fid = canon_form(m.group(1))
            files.setdefault(fid, []).append(full)
    return files, problems


# ------------------------------------------------------------------------------- reconcile

def reconcile(petition_paths, exhibit_dirs, form_dirs=None, series=None, out=None):
    """Cross-check petition references against exhibit/form directories.

    Args:
        petition_paths: list of paths to petition documents (.md, .txt, .docx)
        exhibit_dirs: list of paths to exhibit directories
        form_dirs: optional list of paths to form directories
        series: exhibit series letters (default: DEFAULT_SERIES)
        out: optional path to write the report

    Returns:
        dict with keys: cited_no_file, file_no_cite, duplicates, matched,
                        form_cited_no_file, form_file_no_cite, form_matched,
                        problems, report_lines
    """
    if series is None:
        series = DEFAULT_SERIES
    L = []

    def say(s=""):
        L.append(s)

    say("# Exhibit / Form reconciliation: documents vs. disk")
    say("")
    # 🔴 K092: the series the exhibit folders declare themselves (`declared_series`) are read in the petition's text
    # too - a bare «Y-3» in an exhibit table cites the I-140 package's series Y.
    declared = set()
    for d in exhibit_dirs:
        declared |= declared_series(d)
    active = {s.upper() for s in series} | declared
    looks = collections.Counter()

    # --- read petition documents ---
    cited = set()
    cited_forms = set()
    per_doc = {}
    per_doc_forms = {}
    docs_read = 0
    # 🔴 R77 (#334): a petition file this tool SHOULD read but could not is a report row, never
    # a silent zero. The mixed-folder case is the dangerous one: with one readable .md beside
    # three unreadable PDFs, `docs_read` was 1, the REFUSED guard below stayed quiet, and every
    # reference living only in the PDFs was simply absent from the reconciliation.
    unread = []
    listed, argued, aliases = {}, {}, {}

    def _take(fp, fn):
        nonlocal docs_read
        if _is_tool_output(fp):
            return
        try:
            text = _read_text(fp)
        except MissingReader as exc:
            unread.append((fn, str(exc).splitlines()[0]))
            return
        if not text:
            low = fp.lower()
            if low.endswith(".pdf"):
                unread.append((fn, "the PDF has no usable text layer (a scan?) - OCR it, "
                                   "or supply the petition as .docx/.md"))
            elif low.endswith(".docx"):
                # 🔴 R77 (F-D move 3): mirror the .pdf branch. The old code only rowed the
                # .pdf side of empty-text; a valid-but-empty .docx (empty document.xml) fell
                # through as a silent zero, so its supposed refs simply were not counted.
                unread.append((fn, "the .docx produced no text - empty document or extraction "
                                   "failure; re-save it from Word and re-run"))
            return
        found = text_ids(text, active)
        refs = {eid for eid, _m in found} | range_ids(text, active)
        # 🔴 K045: the exhibit LIST this document prints, and the ids its sentences cite (the list lines blanked)
        entries, list_lines = exhibit_list(text, active)
        for _n, eid, al in entries:
            listed.setdefault(eid, set()).add(fn)
            for a in al:
                aliases.setdefault(eid, set()).add(a)
                aliases.setdefault(a, set()).add(eid)
        body = "\n".join("" if k + 1 in list_lines else ln for k, ln in enumerate(text.splitlines()))
        for eid in {e for e, _m in text_ids(body, active)} | range_ids(body, active):
            argued.setdefault(eid, set()).add(fn)
        for eid, m in found:
            typed = m.groupdict().get("let") or ""
            if typed.upper() in LOOKALIKE:
                looks[(fn, typed, eid)] += 1
        frefs = forms_in_text(text)
        per_doc[fn] = refs
        per_doc_forms[fn] = frefs
        cited.update(refs)
        cited_forms.update(frefs)
        docs_read += 1

    for p in petition_paths:
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                fp = os.path.join(p, fn)
                if os.path.isfile(fp):
                    _take(fp, fn)
        elif os.path.isfile(p):
            _take(p, os.path.basename(p))

    say("petition documents read: **%d**" % docs_read)
    if per_doc:
        for fn in sorted(per_doc):
            say("  - `%s` — %d exhibit refs, %d form refs"
                % (fn, len(per_doc[fn]), len(per_doc_forms.get(fn, set()))))
    say("")

    if unread:
        say("## 🔴 PETITION FILES NOT READ — %d" % len(unread))
        say("")
        say("References inside these files are INVISIBLE to every count below. A zero here is "
            "an artifact of the reader, not a fact about the filing.")
        say("")
        for fn, why in unread:
            say("* `%s` — %s" % (fn, why))
        say("")

    if docs_read == 0:
        say("## REFUSED: no petition documents read")
        say("")
        say("Zero documents read means zero references found, which means zero defects — ")
        say("but that is an artifact of empty input, not a measurement. Check the paths.")
        return {"report_lines": L, "refused": True, "unread": unread}

    say("exhibit IDs cited in petitions: **%d**" % len(cited))
    say("form IDs cited in petitions: **%d** — %s" % (
        len(cited_forms), ", ".join(sorted(cited_forms)) or "none"))
    say("")

    # --- scan exhibit directories ---
    on_disk = {}
    all_problems = []
    for d in exhibit_dirs:
        say("exhibit directory: `%s`" % d)
        if not os.path.isdir(d):
            say("  (does not exist)")
            continue
        files, problems = scan_exhibit_dir(d, series)
        for eid, paths in files.items():
            on_disk.setdefault(eid, []).extend(paths)
        all_problems.extend(problems)
    total_exhibit_files = sum(len(v) for v in on_disk.values())
    say("exhibit files on disk: **%d** files in **%d** exhibit IDs" % (
        total_exhibit_files, len(on_disk)))
    extra = sorted(declared - {s.upper() for s in series})
    if extra:
        say("series read because the exhibit folders use them (not in krokai's default list): **%s**"
            % ", ".join(extra))
    say("")

    # --- scan form directories ---
    form_on_disk = {}
    if form_dirs:
        for d in form_dirs:
            say("form directory: `%s`" % d)
            if not os.path.isdir(d):
                say("  (does not exist)")
                continue
            files, problems = scan_form_dir(d)
            for fid, paths in files.items():
                form_on_disk.setdefault(fid, []).extend(paths)
            all_problems.extend(problems)
        say("form files on disk: **%d** files in **%d** form IDs" % (
            sum(len(v) for v in form_on_disk.values()), len(form_on_disk)))
        say("")

    # --- exhibits: cited but no file ---
    def _idkey(s):
        return (s[0], int(re.sub(r"\D", "", s[2:]) or "0"), s)

    cited_no_file = cited - set(on_disk)
    # 🔴 K045: «X-13 (= P-07)» in an exhibit list - a file under either id serves both
    alias_ok = {e: sorted(a for a in aliases.get(e, ()) if a in on_disk) for e in cited_no_file}
    alias_ok = {e: v for e, v in alias_ok.items() if v}
    cited_no_file -= set(alias_ok)
    say("## CITED-NO-FILE: referenced in petition, no file on disk — %d" % len(cited_no_file))
    say("")
    if cited_no_file:
        say("The adjudicator follows the reference and finds nothing. This is the class that "
            "costs a filing.")
        say("")
        for eid in sorted(cited_no_file, key=_idkey):
            who = sorted(d for d, ss in per_doc.items() if eid in ss)
            say("* **%s** — cited in: %s%s" % (eid, ", ".join(who),
                                              " · in the exhibit list" if eid in listed else ""))
    else:
        say("*(none)*")
    if alias_ok:
        say("")
        say("Answered by an alias the exhibit list names («X-13 (= P-07)»): %s"
            % ", ".join("%s → %s" % (e, "/".join(v)) for e, v in sorted(alias_ok.items(), key=lambda t: _idkey(t[0]))))
    say("")

    # --- exhibits: file exists but not cited ---
    file_no_cite = {e for e in set(on_disk) - cited if not any(a in cited for a in aliases.get(e, ()))}
    say("## FILE-NO-CITE: file exists, not referenced in any petition document — %d"
        % len(file_no_cite))
    say("")
    if file_no_cite:
        say("Not a defect by itself — may be a supporting document or a forgotten argument. "
            "A human decides.")
        say("")
        for eid in sorted(file_no_cite, key=lambda s: (s[0], int(re.sub(r"\D", "", s[2:]) or "0"), s)):
            paths = on_disk[eid]
            say("* **%s** — %s" % (eid, os.path.basename(paths[0])))
    else:
        say("*(none)*")
    say("")

    # --- the exhibit LIST against the sentences and the disk (K045) ---
    listed_pool = set(listed) | {a for e in listed for a in aliases.get(e, ())}
    argued_pool = set(argued) | {a for e in argued for a in aliases.get(e, ())}
    listed_not_cited, cited_not_listed, file_not_listed = [], [], []
    if listed:
        listed_not_cited = sorted((e for e in listed if not _covered(e, argued_pool)
                                   and not any(_covered(a, argued_pool) for a in aliases.get(e, ()))), key=_idkey)
        cited_not_listed = sorted((e for e in argued if not _covered(e, listed_pool)), key=_idkey)
        file_not_listed = sorted((e for e in on_disk if not _covered(e, listed_pool)), key=_idkey)
        docs_l = collections.Counter(d for v in listed.values() for d in v)
        say("## EXHIBIT LIST — %d ids listed (a table column headed «Exhibit» / «Ex.» / «No.», or lines "
            "«Exhibit B-3 - …»)" % len(listed))
        say("")
        say("in: %s" % ", ".join("`%s` (%d)" % (d, n) for d, n in sorted(docs_l.items())))
        say("A part and its whole count as one exhibit here («H-10a» / «H-10»), and so do two ids the list "
            "joins with «=».")
        say("")
        for title, ids, why in (
                ("LISTED, NEVER CITED IN A SENTENCE", listed_not_cited,
                 "The list promises the exhibit and no sentence of the argument uses it: supporting material, dead "
                 "weight, or an argument that lost its exhibit (a renumbering slip lands here). A human decides."),
                ("CITED IN A SENTENCE, NOT IN THE EXHIBIT LIST", cited_not_listed,
                 "The officer looks the exhibit up in the list and does not find it."),
                ("FILE NOT IN THE EXHIBIT LIST", file_not_listed,
                 "A file in the package that the list never announces.")):
            say("## %s — %d" % (title, len(ids)))
            say("")
            if ids:
                say(why)
                say("")
                say(_runs(ids))
            else:
                say("*(none)*")
            say("")
    else:
        say("## EXHIBIT LIST — none found")
        say("")
        say("No table column headed «Exhibit» / «Ex.» / «No.» and no line «Exhibit B-3 - …» in the documents: the "
            "list checks (listed but never cited, cited but not listed, file not listed) did NOT run.")
        say("")

    # --- duplicates (multiple files, no part suffix) ---
    # 🔴 R77 (#346, kimik3/grokbuild, probe-proven): the part suffix is searched AFTER the
    # exhibit ID, never across the whole name. `PART_RE` on the full basename matched the
    # exhibit's OWN number - `B-03 old.pdf` "has a part suffix" via `-03` - so `all(...)` was
    # true for every set of files that spell their ID with a hyphen, and this class had never
    # once fired. Position is the key, the R51 lesson: the same characters mean a part suffix
    # after the ID and the ID itself before it.
    def _part_after_id(x):
        b = os.path.basename(x)
        # 🔴 R77 (#F-F, grokbuild MINOR, probe-proven): the file was ADMITTED via
        # `id_re.search(fn[:50])` at :234 (ID mid-name), but here `dup_re.match` fails on the
        # same name and the WHOLE basename is scanned - so «B-03 old.pdf»'s own «-03» matched
        # `PART_RE` and duplicates were silently excluded. Mirror the admission logic: locate
        # the ID the same way, search AFTER its end. Whole-name only when no ID is found at
        # all. Position is the invariant (R51: same characters mean a part suffix AFTER the ID
        # and the ID itself BEFORE it).
        # 🔴 K092: the id reader now takes «V-67-1» whole (part 1 of V-67) - its part group IS the part suffix.
        got = name_id(b, active)
        m = got[2] if got else None
        if m is not None and m.groupdict().get("part"):
            return True
        return bool(PART_RE.search(b[m.end():] if m else b))

    duplicates = {k: v for k, v in on_disk.items()
                  if len(v) > 1 and not all(_part_after_id(x) for x in v)}
    say("## DUPLICATE: one ID, multiple files without part suffix (_1, _2) — %d" % len(duplicates))
    say("")
    if duplicates:
        say("Multi-part exhibits with `_1`, `_2` suffixes are legitimate and excluded. "
            "These may be two versions of the same document.")
        say("")
        for k in sorted(duplicates):
            say("* **%s**" % k)
            for f in duplicates[k]:
                try:
                    sz = os.path.getsize(f)
                except OSError:
                    sz = 0
                say("    * `%s` (%d bytes)" % (os.path.basename(f), sz))
    else:
        say("*(none)*")
    say("")

    # --- forms: cited but no file ---
    form_cited_no_file = set()
    form_file_no_cite = set()
    form_matched = set()
    if form_dirs:
        form_cited_no_file = cited_forms - set(form_on_disk)
        form_file_no_cite = set(form_on_disk) - cited_forms
        form_matched = cited_forms & set(form_on_disk)

        say("## FORM-CITED-NO-FILE: form referenced in petition, no file on disk — %d"
            % len(form_cited_no_file))
        say("")
        if form_cited_no_file:
            for fid in sorted(form_cited_no_file):
                who = sorted(d for d, ss in per_doc_forms.items() if fid in ss)
                say("* **%s** — cited in: %s" % (fid, ", ".join(who)))
        else:
            say("*(none)*")
        say("")

        say("## FORM-FILE-NO-CITE: form file exists, not referenced — %d" % len(form_file_no_cite))
        say("")
        if form_file_no_cite:
            for fid in sorted(form_file_no_cite):
                paths = form_on_disk[fid]
                say("* **%s** — %s" % (fid, os.path.basename(paths[0])))
        else:
            say("*(none)*")
        say("")

    # --- action markers in filenames ---
    acts = [p for k, p in all_problems if k == "ACTION-MARKER"]
    if acts:
        say("## ACTION MARKERS in filenames (FIXME/TODO/DRAFT) — %d" % len(acts))
        say("")
        say("A marker in the filename is an unclosed task left by a human.")
        say("")
        for p in acts:
            say("* `%s`" % os.path.basename(p))
        say("")

    # --- look-alike letters (K092) ---
    look_files = [p for k, p in all_problems if k == "LOOKALIKE"]
    if look_files or looks:
        say("## LOOK-ALIKE LETTERS: another script typed for a Latin series letter — %d"
            % (len(look_files) + len(looks)))
        say("")
        say("A Cyrillic or Greek letter that looks Latin (a Russian keyboard types «С», «О», «Р», «Х»). krokai reads "
            "the id as the Latin letter; a search, a sort and other tools do not - retype the letter.")
        say("")
        for p in look_files:
            b = os.path.basename(p)
            got = name_id(b, None)
            ch = got[1] if got else "?"
            say("* file `%s` — «%s» is U+%04X %s, read as **%s**" % (
                b, ch, ord(ch[0]), unicodedata.name(ch[0], "?"), got[0] if got else "?"))
        for (fn, ch, eid), n in sorted(looks.items()):
            say("* petition `%s` — «%s» is U+%04X %s, read as **%s** (%d×)" % (
                fn, ch, ord(ch), unicodedata.name(ch, "?"), eid, n))
        say("")

    # --- names read as codes (K092: they were dropped with no line) ---
    notex = [p for k, p in all_problems if k == "NOT-EXHIBIT"]
    if notex:
        say("## NAMES READ AS A FORM / VISA CODE OR A MEMORANDA SERIES, NOT AN EXHIBIT — %d" % len(notex))
        say("")
        say("Not counted as exhibits: the name starts with a code (G-1450, H-1, J-1 ...) of a series no other file of "
            "this folder uses, or with the memoranda series (%s). If one IS an exhibit, a folder named «Exhibit "
            "<letter>» around it declares the series." % ", ".join(sorted(DOC_SERIES)))
        say("")
        for p in notex:
            say("* `%s`" % os.path.basename(p))
        say("")

    # --- files without recognized ID ---
    noname = [p for k, p in all_problems if k == "NO-ID"]
    if noname:
        say("## FILES WITHOUT RECOGNIZED EXHIBIT ID — %d" % len(noname))
        say("")
        for p in noname:
            b = os.path.basename(p)
            m = _NAME_RE.match(b)
            hint = ""
            if m and _fold(m.group("let")) not in active:
                hint = (" — starts like an id of series %s, which krokai's list lacks and no other file here uses; a "
                        "folder «Exhibit %s» declares it" % (_fold(m.group("let")), _fold(m.group("let"))))
            say("* `%s`%s" % (b, hint))
        say("")

    # --- numbering gaps ---
    say("## Numbering gaps by series")
    say("")
    say("A gap is not a defect — a number may have been retired. This is a map for humans.")
    say("")
    by_s = {}
    for eid in on_disk:
        parts = eid.split("-", 1)
        if len(parts) == 2:
            try:
                n = int(re.sub(r"[^0-9]", "", parts[1]) or "0")
            except ValueError:
                continue
            by_s.setdefault(parts[0], set()).add(n)
    for s in sorted(by_s):
        nums = sorted(by_s[s])
        if not nums:
            continue
        holes = [i for i in range(1, max(nums) + 1) if i not in nums]
        say("* **%s**: %d IDs, max %d, gaps: %s"
            % (s, len(nums), max(nums), ", ".join(map(str, holes)) or "none"))
    say("")

    # --- summary ---
    say("## Summary")
    say("")
    matched = cited & set(on_disk)
    say("| Category | Count |")
    say("|---|---|")
    say("| Exhibits matched | %d |" % len(matched))
    say("| Cited, no file | %d |" % len(cited_no_file))
    say("| File, no citation | %d |" % len(file_no_cite))
    say("| Duplicates | %d |" % len(duplicates))
    if listed:
        say("| Listed, never cited in a sentence | %d |" % len(listed_not_cited))
        say("| Cited in a sentence, not in the exhibit list | %d |" % len(cited_not_listed))
        say("| File, not in the exhibit list | %d |" % len(file_not_listed))
    if form_dirs:
        say("| Forms matched | %d |" % len(form_matched))
        say("| Form cited, no file | %d |" % len(form_cited_no_file))
        say("| Form file, no citation | %d |" % len(form_file_no_cite))
    say("")

    # --- write report ---
    report_text = "\n".join(L) + "\n"
    if out:
        os.makedirs(os.path.dirname(out) if os.path.dirname(out) else ".", exist_ok=True)
        io.open(out, "w", encoding="utf-8", newline="\n").write(report_text)

    return {
        "cited_no_file": cited_no_file,
        "file_no_cite": file_no_cite,
        "duplicates": duplicates,
        "matched": matched,
        "form_cited_no_file": form_cited_no_file,
        "form_file_no_cite": form_file_no_cite,
        "form_matched": form_matched,
        "problems": all_problems,
        "report_lines": L,
        "refused": False,
        "unread": unread,
        "declared": sorted(declared),
        "lookalikes": look_files + [k for k in sorted(looks)],
        "not_exhibit": notex,
        "listed": {e: sorted(v) for e, v in listed.items()},
        "argued": sorted(argued),
        "aliases": {e: sorted(v) for e, v in aliases.items()},
        "alias_ok": alias_ok,
        "listed_not_cited": listed_not_cited,
        "cited_not_listed": cited_not_listed,
        "file_not_listed": file_not_listed,
    }
