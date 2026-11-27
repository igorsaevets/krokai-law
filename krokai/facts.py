# -*- coding: utf-8 -*-
"""`krokai facts` - a bank of facts SLICED from the exhibits, and the check of every draft sentence that cites one.

THE PROBLEM (K046)
------------------
krokai checks the words a draft QUOTES from the law. The facts a petition ASSERTS about its evidence - a date of
employment, a salary, a name, a count - were checked by nothing. The obvious check, «is every number of the sentence
somewhere in the cited exhibit», is blind to the error that costs most: a value swapped between two entities of the
SAME exhibit (two employers on one résumé, two letters in one bundle) is «somewhere in the exhibit» every time.

So a fact is banked the way a quotation is: `krokai facts add` SLICES the passage out of the exhibit between two
anchors - the words are never typed - and the draft sentence carries the entry's id, `[F-012]`. `check` then holds the
sentence to that slice: every date, amount, number and name of the sentence must stand INSIDE the slice, and the
exhibit the sentence cites must be the entry's.

This module is the token layer (what counts as a fact in a sentence, and when a slice holds it) plus the bank file
and the check; `cli.py` wires `facts add` / `facts list`, `run.py` calls `check_drafts` from `check`.
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import io
import os
import re
import time
from decimal import Decimal, InvalidOperation

from .normalize import normalise, strip_markdown

AMOUNT, DATE, NUMBER, NAME = "amount", "date", "number", "name"

# ----------------------------------------------------------------------------------------------- dates
_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
           "oct": 10, "nov": 11, "dec": 12}
_MON = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
        r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
_DAY = r"(?P<d>[0-3]?\d)(?:st|nd|rd|th)?"
_YR = r"(?P<y>(?:19|20)\d{2})"
# Longest shapes first: each match masks its span, so «January 5, 2020» is one date, never a month-year plus a number.
_DATE_RES = (
    re.compile(r"\b(?P<mon>%s)\.?\s+%s,?\s+%s\b" % (_MON, _DAY, _YR), re.I),            # January 5, 2020
    re.compile(r"\b%s\s+(?:day\s+)?(?:of\s+)?(?P<mon>%s)\.?,?\s+%s\b" % (_DAY, _MON, _YR), re.I),  # 5 January 2020
    re.compile(r"(?<![\d.])%s-(?P<m>[01]?\d)-(?P<d>[0-3]?\d)(?![\d])" % _YR),              # 2020-01-05
    re.compile(r"(?<![\d/.])(?P<m>[01]?\d)[/-](?P<d>[0-3]?\d)[/-](?P<y>(?:19|20)?\d{2})(?![\d/])"),  # 01/05/2020 (US)
    re.compile(r"(?<![\d.])(?P<d>[0-3]?\d)\.(?P<m>[01]?\d)\.(?P<y>(?:19|20)\d{2})(?![\d])"),  # 05.01.2020 (day first)
    re.compile(r"\b(?P<mon>%s)\.?,?\s+%s\b" % (_MON, _YR), re.I),                         # January 2020
    re.compile(r"(?<![\d/.])(?P<m>[01]?\d)/%s(?![\d])" % _YR),                             # 01/2020
)
_YEAR_RE = re.compile(r"(?<![\w.,/])(?:19|20)\d{2}(?![\w/]|[.,]\d)")


def _date_of(m):
    """(y, m, d) with None for a part the shape does not carry; None when the match is not a date."""
    g = m.groupdict()
    mon = g.get("mon")
    if mon is not None:
        if not mon[0].isupper():
            return None                    # «may 2020» - the verb, not the month
        mo = _MONTHS[mon[:3].lower()]
    else:
        mo = int(g["m"])
    y = g["y"]
    y = int(y) if len(y) == 4 else (2000 + int(y) if int(y) < 50 else 1900 + int(y))
    d = int(g["d"]) if g.get("d") else None
    if not 1 <= mo <= 12 or (d is not None and not 1 <= d <= 31):
        return None
    return (y, mo, d)


# --------------------------------------------------------------------------------------------- amounts
_NUM = r"(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
# Case-blind words: «$45 Million» read as 45 dollars before K046's probe found it in a filed exhibit.
_MULT = r"(?:\s*(?P<mult>(?i:million|billion|thousand|mln|bn)\b|[KkMm](?![A-Za-z])))?"
_AMOUNT_RES = (
    re.compile(r"(?:US\s?)?\$\s?%s%s" % (_NUM, _MULT)),
    re.compile(r"\b(?:USD|EUR|GBP|RUB)\s?%s%s" % (_NUM, _MULT)),
    re.compile("[€£₽]\\s?%s%s" % (_NUM, _MULT)),
    re.compile(r"(?<![\w.,])%s%s\s*(?:USD|EUR|GBP|RUB|dollars?|euros?|rubles?|roubles?)\b" % (_NUM, _MULT), re.I),
)
_MULTS = {"thousand": 10 ** 3, "k": 10 ** 3, "million": 10 ** 6, "mln": 10 ** 6, "m": 10 ** 6,
          "billion": 10 ** 9, "bn": 10 ** 9}


def _value(n, mult=None):
    try:
        v = Decimal(n.replace(",", ""))
    except InvalidOperation:
        return None
    if mult:
        v *= _MULTS[mult.lower()]
    return v.normalize()


# --------------------------------------------------------------------------------------------- numbers
_NUMBER_RE = re.compile(r"(?<![\w.,/-])(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w/]|[.,]\d)")
# Every digit run of a SLICE, whatever stands around it: the slice side is forgiving on purpose - a value the slice
# holds in any shape counts as held (a false alarm costs more trust than the rare coincidental hit costs recall).
_ANY_NUM_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")

# ----------------------------------------------------------------------------------------------- names
_NAME_RE = re.compile("(?<![\\w'’-])([A-Z][A-Za-z'’-]*[A-Za-z]|[A-Z]{2,})(?![\\w])")
_WORD_RE = re.compile("[A-Za-z][A-Za-z'’-]*")
# Capitalised words that are not names: function words a sentence opens with, the roles and documents of a petition,
# titles. A word missing here costs a false alarm the drafter sees and the measurement counts (K046 probe).
STOP = frozenset("""
a an the this that these those there here it its he she his her hers him they them their we our us you your i my me
and or but nor so yet for as at by in into of on onto to from with within without upon over under about after before
during since until while when where which who whom whose what why how if then than though although because once
also further furthermore moreover however therefore thus accordingly additionally similarly finally notably
specifically indeed importantly overall here further first second third fourth fifth next last later prior
not no yes all any each every both either neither some such other another many most more much few several only
mr mrs ms dr prof professor sir madam mx jr sr phd ph md mba ms ma ba bs llc inc corp co ltd plc gmbh llp lp pc
petitioner petitioners beneficiary beneficiaries applicant applicants respondent employer employee alien noncitizen
uscis dhs dol doj eoir aao bia ina cfr usc us u.s fed reg stat pub l no nos vol pp p para
exhibit exhibits exh ex tab tabs appendix annex attachment enclosure form forms section sections part chapter volume
letter letters evidence document documents record records report reports statement statements declaration affidavit
policy manual memo memorandum matter decision opinion brief petition petitions application case
national interest waiver niw eb eb-2 eb-1 eb-1a eb-1b o-1 h-1b f-1 j-1 i-140 i-485 i-129 i-765 i-131 i-20 i-94
united states america american federal state department labor homeland security immigration nationality act
citizenship services service court circuit district board appeals office administrative
january february march april may june july august september october november december
monday tuesday wednesday thursday friday saturday sunday
see id cf eg ie et al etc ibid supra infra accord compare note notes footnote
""".split())


def _mask(s, a, b):
    return s[:a] + " " * (b - a) + s[b:]


# A period after one of these is not a stop: «Dr. Elena Varga» keeps «Elena» (K046 smoke test: it was dropped).
_ABBR = frozenset("dr mr mrs ms mx prof st jr sr inc co corp ltd no nos vs v ex exh dept univ assoc inst gen gov "
                  "sen rep hon rev capt col lt sgt mt ft ave blvd rd".split())
_PREV_WORD_RE = re.compile(r"([A-Za-z][A-Za-z.]*)\.\s*$")


def _after_stop(prefix):
    if re.search(r"[:;!?]\s*$", prefix):
        return True
    m = _PREV_WORD_RE.search(prefix)
    if not m:
        return False
    w = m.group(1).lower()
    return not (w in _ABBR or len(w) == 1 or "." in w)


# Spans that carry digits or capitals and are NOT facts about the evidence: the entry marker itself, exhibit ids,
# legal citations, form numbers and visa classes, section signs, URLs, list markers.
_MARKER_RE = re.compile(r"\[\s*F-\d{1,4}(?:\s*[,;]\s*F-\d{1,4})*\s*\]")
_FORM_RE = re.compile(r"\b(?:Forms?\s+)?(?:I|G|N|DS|AR|ETA)\s?-\s?\d{2,5}[A-Z]?\b")
_VISA_RE = re.compile(r"\b(?:EB|H|L|O|E|R|TN|F|J|K|P|B|M|Q)-\d[A-Z]?\b")
_SECTION_RE = re.compile("§+\\s*\\d[\\w.–-]*(?:\\([\\w]+\\))*")
# A provision's subsection chain - «214.2(h)(4)», «203(b)(2)» - outside a citation the packs recognise: K046's probe
# found two such numbers of filed sentences graded as facts.
_SUBSEC_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)*(?:\([A-Za-z0-9]{1,4}\))+")
_CITE_RE = re.compile(r"\d+\s+(?:I&N Dec\.|U\.S\.C\.|C\.F\.R\.|CFR|USC|F\.\s?(?:2d|3d|4th)|F\. Supp\.(?:\s?\dd)?|"
                      r"S\.\s?Ct\.|U\.S\.|Fed\.\s?Reg\.|Stat\.)\s*(?:§+\s*)?[\d.]+(?:\([\w]+\))*")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\w+")
_LIST_RE = re.compile(r"^\s*(?:\(?\d{1,2}[.)]|[-*•])\s+|\(\s*(?:\d{1,2}|[ivx]{1,4}|[a-z])\s*\)")
_EXH_WORD_RE = re.compile(r"\b(?:Exhibits?|Exh\.|Ex\.|Tabs?)\s*", re.I)


# Typeset PDFs extract «ﬁ» / «ﬂ» as one ligature character, so «Certiﬁed» never equalled «Certified» (K046 probe:
# an exhibit's text). K046 folded them here for facts alone; since K099 `normalise` folds them for every caller,
# both sides of a fact included - one table, `normalize._LIGATURES`.
def _cleaned(sentence):
    return normalise(strip_markdown(sentence or ""))


def _masked(text, packs=None):
    """`text` with every non-fact span blanked (same length, so offsets stay the sentence's own)."""
    from .exhibit_check import ANCHORED_ID_RE, DEFAULT_SERIES, _K_RE, _build_id_re
    s = text
    spans = []
    # K092: an id right after the word Exhibit is blanked whatever its letter («Exhibit Y-3»: the 3 is no fact).
    for rx in (_MARKER_RE, _URL_RE, _CITE_RE, _SECTION_RE, _SUBSEC_RE, _FORM_RE, _build_id_re(DEFAULT_SERIES),
               ANCHORED_ID_RE, _K_RE, _VISA_RE, _EXH_WORD_RE, _LIST_RE):
        spans += [(m.start(), m.end()) for m in rx.finditer(s)]
    if packs is not None:
        for cite, pos in packs.find_positions(s):
            j, k = pos, 0
            while j < len(s) and k < len(cite):          # walk the original span: the pack collapses whitespace
                if s[j].isspace() and cite[k] == " ":
                    while j < len(s) and s[j].isspace():
                        j += 1
                    k += 1
                elif s[j] == cite[k]:
                    j, k = j + 1, k + 1
                else:
                    break
            spans.append((pos, j))
    for a, b in spans:
        s = _mask(s, a, b)
    return s


def sentence_tokens(sentence, packs=None):
    """The facts a draft sentence states: dicts {kind, raw, key, at}. `key` is what a slice must hold:
    a date (y, m, d) with None for a missing part, a Decimal for an amount or a number, a lowercase word for a name."""
    text = _cleaned(sentence)
    s = _masked(text, packs)
    out = []
    for rx in _DATE_RES:
        for m in rx.finditer(s):
            key = _date_of(m)
            if key is None:
                continue
            out.append({"kind": DATE, "raw": text[m.start():m.end()], "key": key, "at": m.start()})
            s = _mask(s, m.start(), m.end())
    for rx in _AMOUNT_RES:
        for m in rx.finditer(s):
            v = _value(m.group("n"), m.group("mult"))
            if v is None:
                continue
            out.append({"kind": AMOUNT, "raw": text[m.start():m.end()].strip(), "key": v, "at": m.start()})
            s = _mask(s, m.start(), m.end())
    for m in _YEAR_RE.finditer(s):
        out.append({"kind": DATE, "raw": m.group(0), "key": (int(m.group(0)), None, None), "at": m.start()})
        s = _mask(s, m.start(), m.end())
    for m in _NUMBER_RE.finditer(s):
        v = _value(m.group("n"))
        if v is not None:
            out.append({"kind": NUMBER, "raw": m.group(0), "key": v, "at": m.start()})
            s = _mask(s, m.start(), m.end())
    first = re.search(r"[A-Za-z]", s)
    first = first.start() if first else -1
    for m in _NAME_RE.finditer(s):
        w = re.sub("['’]s$", "", m.group(1))
        lw = w.lower()
        if lw in STOP or len(lw) < 2:
            continue
        if m.start() == first:
            continue                        # the sentence's first word: capitalised by position, not by name
        if _after_stop(s[:m.start()]):
            continue                        # after a colon or a stop inside the unit: same reason
        out.append({"kind": NAME, "raw": w, "key": lw, "at": m.start()})
    out.sort(key=lambda t: t["at"])
    return out


def _rel(path, root):
    """`path` relative to the matter, or absolute when it cannot be: on Windows an exhibit folder on another drive
    («exhibits»: ["D:/case/exhibits"] in a matter on C:) made `os.path.relpath` raise - K046's run on a real copy."""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return os.path.abspath(path)


class SliceIndex(object):
    """What a slice (or several) holds, in the comparable forms `sentence_tokens` produces."""

    def __init__(self, texts):
        self.full, self.ym, self.years, self.values, self.words = set(), set(), set(), set(), set()
        for t in texts:
            t = _cleaned(t)
            s = t
            for rx in _DATE_RES:
                for m in rx.finditer(s):
                    key = _date_of(m)
                    if key is None:
                        continue
                    y, mo, d = key
                    self.years.add(y)
                    self.ym.add((y, mo))
                    if d is not None:
                        self.full.add(key)
            for m in _YEAR_RE.finditer(t):
                self.years.add(int(m.group(0)))
            for rx in _AMOUNT_RES:
                for m in rx.finditer(t):
                    v = _value(m.group("n"), m.group("mult"))
                    if v is not None:
                        self.values.add(v)
            for m in _ANY_NUM_RE.finditer(t):
                v = _value(m.group(0))
                if v is not None:
                    self.values.add(v)
                    if v == v.to_integral_value() and 1900 <= v <= 2099:
                        self.years.add(int(v))
            for m in _WORD_RE.finditer(t):
                w = re.sub("['’]s$", "", m.group(0)).lower()
                self.words.add(w)
                self.words.update(p for p in w.split("-") if p)

    def holds(self, tok):
        k = tok["key"]
        if tok["kind"] == DATE:
            y, mo, d = k
            if d is not None:
                return k in self.full
            if mo is not None:
                return (y, mo) in self.ym
            return y in self.years
        if tok["kind"] in (AMOUNT, NUMBER):
            return k in self.values
        parts = [p for p in k.split("-") if p]
        return k in self.words or (len(parts) > 1 and all(p in self.words for p in parts))


def missing(sentence, slice_texts, packs=None):
    """The tokens of `sentence` that none of `slice_texts` holds."""
    idx = SliceIndex(slice_texts)
    return [t for t in sentence_tokens(sentence, packs) if not idx.holds(t)]


# ================================================================================================== verdicts
# 🔴 WHY NAMES ARE ADVISORY (K046, measured on a copy of a filed petition: 312 sentences citing exactly one exhibit,
# their best slice simulated). Dates, amounts and numbers: 17 of 229 sentences hold one their exhibit lacks, and a value
# swapped in from elsewhere in the same exhibit passed «anywhere in the exhibit» 64 of 64 times while the slice caught
# 64 of 64. Capitalised words: 102 of 229 sentences carried one the whole exhibit lacks (the drafter's own terms), and
# with a natural slice (the exhibit's sentences around the hard facts) 20 of 41 clean sentences had a name outside it.
# A red verdict on names would be wrong about half the time - so names are listed for reading, never in the exit code.
SUPPORTED, NOT_IN_SLICE, WRONG_EXHIBIT = "SUPPORTED", "NOT_IN_SLICE", "WRONG_EXHIBIT"
SLICE_GONE, UNKNOWN_ENTRY, NOTHING = "SLICE_GONE", "UNKNOWN_ENTRY", "NOTHING_TO_HOLD"
RED = (UNKNOWN_ENTRY, SLICE_GONE, WRONG_EXHIBIT, NOT_IN_SLICE)
MARK = {SUPPORTED: "🟢", NOTHING: "⚪", NOT_IN_SLICE: "🔴", WRONG_EXHIBIT: "🔴", SLICE_GONE: "🔴", UNKNOWN_ENTRY: "🔴"}
MEANING = {
    SUPPORTED: "every date, amount and number of the sentence stands in the banked slice",
    NOT_IN_SLICE: "the sentence states a date, amount or number its slice does not hold",
    WRONG_EXHIBIT: "the sentence cites another exhibit than the banked entry's",
    SLICE_GONE: "the banked slice is no longer in its exhibit file - re-slice it",
    UNKNOWN_ENTRY: "the sentence cites a fact id the bank does not hold",
    NOTHING: "the sentence states no date, amount or number - nothing was held to the slice",
}

# ================================================================================================= the bank file
FACT_HEADER = (
    "# FACT BANK - facts sliced from the exhibits\n\n"
    "Every entry is written by `krokai facts add`: the passage is SLICED from the exhibit between two anchors, never "
    "typed. A draft sentence cites an entry as [F-012]; `krokai check` holds the sentence's dates, amounts and numbers "
    "to the slice, lists its names the slice does not hold, and says when the sentence cites another exhibit than "
    "the entry's. This file holds evidence text: keep it in the matter.\n\n"
    "Fact bank revision: - entries: 0\n")
_ENTRY_RE = re.compile(r"(?m)^### (F-\d{1,4})[ \t]*$")
_FIELD_RE = re.compile(r"(?m)^- ([A-Za-z0-9 ]+): (.*)$")
_REV_RE = re.compile(r"(?m)^Fact bank revision: .*$")
_REF_RE = re.compile(r"\[\s*(F-\d{1,4}(?:\s*[,;]\s*F-\d{1,4})*)\s*\]")


def fid(s):
    """«F-12» / «F-012» -> «F-012», the bank's own spelling."""
    return "F-%03d" % int(s.split("-")[1])


def read_bank(path):
    """{id: entry} - entry fields lowercased (`exhibit`, `file`, `sha256`, `page`, `text layer`) + `slice`; None when
    the file does not exist."""
    try:
        with io.open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    out = {}
    heads = list(_ENTRY_RE.finditer(text))
    for i, m in enumerate(heads):
        body = text[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        e = {k.strip().lower(): v.strip() for k, v in _FIELD_RE.findall(body)}
        e["slice"] = " ".join(ln[1:].strip() for ln in body.splitlines() if ln.startswith(">")).strip()
        out[fid(m.group(1))] = e
    return out


def exhibit_id(s):
    """The exhibit id in `s` («K-4», «Exhibit D-19a», «K12») in `exhibit_check`'s canonical form, or None."""
    # K092: any series letter - the user named an exhibit («Y-3» of the I-140 package), and a look-alike letter folds.
    from .exhibit_check import id_of
    return id_of(s)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def _pages_set(spec):
    """«2-3, 5» -> {2, 3, 5}."""
    out = set()
    for part in str(spec or "").split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                out.update(range(int(a), int(b) + 1))
        elif part.isdigit():
            out.add(int(part))
    return out


def run_add(a, printer=print):
    """`krokai facts add` - slice ONE fact from an exhibit. Dry-run unless --apply. The slicing, the anchor
    normalisation and the atomic write are `bank add`'s own (`bank_add._slice`): the same refusals, the same reasons."""
    from .bank_add import LONG_SLICE_WARN, _norm_anchor, _slice, _write_atomic
    from .config import load
    from .corpus import Corpus
    from .exhibit_check import DEFAULT_SERIES, name_id, scan_exhibit_dir
    from .verify import page_of

    cfg = load(a.dir)
    eid = exhibit_id(a.exhibit)
    if not eid:
        printer("🔴 --exhibit «%s» is not an exhibit id krokai reads (a series letter and a number: K-4, D-19a)."
                % a.exhibit)
        return 2
    nfrom, nto = _norm_anchor(a.from_), _norm_anchor(a.to)
    if not nfrom or not nto:
        printer("🔴 --from and --to must both carry words of the exhibit.")
        return 2
    if a.file:
        path = cfg.abs(a.file)
        if not os.path.isfile(path):
            printer("🔴 --file %s does not exist." % a.file)
            return 3
        got = name_id(os.path.basename(path), None)
        if not got or got[0] != eid:
            printer("🟡 the file name does not carry %s as krokai reads exhibit ids - the entry keeps the id you gave."
                    % eid)
    else:
        found = []
        for d in cfg["exhibits"]:
            # K092: the requested id's own series is read even where no other file declares it.
            files, _probs = scan_exhibit_dir(cfg.abs(d), series=list(DEFAULT_SERIES) + [eid.split("-")[0]])
            found += files.get(eid, [])
        if not found:
            printer("🔴 no file carries exhibit %s in its name under %s." % (eid, ", ".join(cfg["exhibits"])))
            printer("   Name the file with --file <path> (an id krokai cannot read from a name, a folder not listed in "
                    "casefile.json «exhibits»).")
            return 3
        groups = collections.OrderedDict()
        for p in found:
            groups.setdefault(_sha(p), []).append(p)
        if len(groups) > 1:
            # K038: 23 cited ids of a filed package had 2+ files that differ - a repaired copy beside the broken one,
            # a summary beside the PDF. Picking one silently is how a fact gets banked from the wrong document.
            printer("🔴 exhibit %s has %d different files - refusing to pick one:" % (eid, len(groups)))
            for h, ps in groups.items():
                printer("     --file \"%s\"   (sha256 %s%s)" % (_rel(ps[0], cfg.root), h[:12],
                                                             ", %d identical copies" % len(ps) if len(ps) > 1 else ""))
            return 3
        path = found[0]
    rel = _rel(path, cfg.root)
    corpus = Corpus([], files=[path], derived_re=None, cache_dir=cfg.cache, quiet=True)
    if path not in corpus.paths:
        why = corpus.stub_why.get(path) or ("unreadable" if corpus.unreadable else "no text")
        printer("🔴 %s has no text a fact can be sliced from (%s)." % (rel, why))
        printer("   A picture or a scan without a text layer: OCR it with a real OCR engine - never a language model.")
        return 3
    text = corpus.text_of(path)
    printer("exhibit : %s -> %s" % (eid, rel))
    span, rc = _slice(text, nfrom, nto, a.to_nth, printer)
    if not span:
        return rc
    i, j = span
    sl = text[i:j]
    printer("slice   : %d characters" % len(sl))
    if len(sl) > LONG_SLICE_WARN:
        printer("   🟡 unusually long - a fact is held to the WHOLE slice, so a long one holds values of other "
                "entities too; slice the sentence the fact stands in.")
    printer("  «%s%s»" % (sl[:300], "…" if len(sl) > 300 else ""))
    pg = page_of(sl, path, corpus)
    pages = {n for a_, b_ in (pg or {}).get("pdf_pages") or () for n in range(a_, b_ + 1)}
    page_label = pg["label"] if pg else "-"
    printer("page    : %s" % page_label)
    layer = "typeset"
    lay = corpus.ocr_layer(path)
    if lay:
        ocr_pages = (set(range(1, (lay.get("pages") or 0) + 1)) if lay.get("class") == "ocr"
                     else _pages_set(lay.get("ocr_pages")))
        if not pages or pages & ocr_pages:
            layer = ("OCR layer - its digits are what an OCR engine read from a scanned image: confirm them "
                     "against the page image")
            printer("   🟡 %s" % layer)
    pic = corpus.picture_pages(path)
    if pic and pages & {n for n, _w in pic.get("flagged") or ()}:
        printer("   🟡 the slice stands on a page whose words are in a PICTURE: the text layer holds only a label "
                "there - the facts in the picture are not in this slice.")
    held = SliceIndex([sl])
    if not (held.ym or held.years or held.values):
        printer("   🟡 the slice holds no date, amount or number - a sentence citing it is held to its names only.")
    else:
        printer("holds   : %d month(s) or year(s) of a date, %d number value(s)"
                % (len(held.ym) or len(held.years), len(held.values)))
    bank_path = cfg.abs(cfg["fact_bank"])
    try:
        with io.open(bank_path, encoding="utf-8") as fh:
            bank_text = fh.read()
    except OSError:
        bank_text = FACT_HEADER
    taken = {fid(m.group(1)) for m in _ENTRY_RE.finditer(bank_text)}
    if a.entry_id:
        new = fid(a.entry_id if a.entry_id.upper().startswith("F-") else "F-" + a.entry_id)
        if new in taken:
            printer("🔴 %s is already in the fact bank - ids are never reused: a reused id silently redirects every "
                    "sentence that cites it." % new)
            return 3
    else:
        new = "F-%03d" % (max([int(x[2:]) for x in taken] or [0]) + 1)
    cmd = 'krokai facts add --exhibit %s --from "%s" --to "%s"' % (eid, nfrom[:60], nto[-60:])
    if a.to_nth:
        cmd += " --to-nth %d" % a.to_nth
    if a.file:
        cmd += ' --file "%s"' % rel
    entry = ("### %s\n- Exhibit: %s\n- File: %s\n- sha256: %s\n- Page: %s\n- Text layer: %s\n- Sliced: %s - `%s`\n\n"
             "> %s\n\n" % (new, eid, rel.replace("\\", "/"), _sha(path), page_label, layer,
                           time.strftime("%Y-%m-%d"), cmd.replace("`", "'"), sl))
    body = bank_text.rstrip("\n") + "\n\n" + entry
    n = len(_ENTRY_RE.findall(body))
    rev = "Fact bank revision: %s - entries: %d" % (time.strftime("%Y-%m-%d"), n)
    body = _REV_RE.sub(rev, body, count=1) if _REV_RE.search(body) else body
    printer("entry   : %s -> %s" % (new, _rel(bank_path, cfg.root)))
    if not a.apply:
        printer("\nDRY RUN - nothing was written. Re-run with --apply to write.")
        return 0
    _write_atomic(bank_path, body)
    back = read_bank(bank_path) or {}
    if back.get(new, {}).get("slice") != sl:
        printer("🔴 post-write re-read FAILED: %s is not in %s as written - inspect the file before writing again."
                % (new, bank_path))
        return 1
    printer("\nwritten : %s (re-read from disk: %s holds the slice as sliced)" % (bank_path, new))
    printer("cite it : end the draft sentence with [%s]; `krokai check` holds the sentence to this slice." % new)
    return 0


# ===================================================================================================== the check
_SENT_END = re.compile("(?<=[.!?])[\"'”’)\\]]*\\s+(?=[\"'“(\\[]*[A-Z0-9\\[])")


def _sentence_at(body, a, b):
    """The sentence of `body` that the marker at [a, b) closes - a marker standing right after a full stop («… 2020.
    [F-3]») belongs to the sentence before it."""
    ps = body.rfind("\n\n", 0, a)
    ps = 0 if ps < 0 else ps + 2
    pe = body.find("\n\n", b)
    pe = len(body) if pe < 0 else pe
    par = body[ps:pe]
    ka, kb = a - ps, b - ps
    cuts = [0]
    for m in _SENT_END.finditer(par):
        w = re.search(r"([A-Za-z][A-Za-z.]*)[.!?]$", par[:m.start()])
        if w and (w.group(1).lower() in _ABBR or len(w.group(1)) == 1 or "." in w.group(1)):
            continue                                    # «Dr.», «U.S.», «Ex.» - not a sentence end
        cuts.append(m.end())
    cuts.append(len(par))
    k = bisect.bisect_right(cuts, ka) - 1
    lo, hi = cuts[k], cuts[min(k + 1, len(cuts) - 1)]
    if k > 0 and not re.search(r"[A-Za-z0-9]", par[lo:ka]):
        lo, hi = cuts[k - 1], kb
    return par[lo:max(hi, kb)].strip()


def _slice_state(cfg, e):
    """(still there, note) - is the entry's slice still in its exhibit file, read as `facts add` read it."""
    from .readers import corpus_text
    rel = e.get("file") or ""
    p = cfg.abs(rel) if rel else None
    if not p or not os.path.isfile(p):
        return False, "its exhibit file is gone: %s" % (rel or "(no File line)")
    try:
        text = corpus_text(p, cfg.cache)
    except Exception as exc:                                       # noqa: BLE001 - reported, never swallowed
        return False, "%s while reading %s" % (type(exc).__name__, rel)
    if not e.get("slice") or e["slice"] not in text:
        return False, "the slice is no longer in %s - the file changed or the entry was edited by hand" % rel
    if e.get("sha256") and _sha(p) != e["sha256"]:
        return True, "the file changed since banking (sha256), the slice is still in it"
    return True, ""


def _fmt(t, idx):
    if t["kind"] == DATE and t["key"][2] is not None and (t["key"][0], t["key"][1]) in idx.ym:
        return "%s (the slice holds the month, not the day)" % t["raw"]
    return t["raw"]


def check_docs(cfg, docs, packs=None):
    """Every [F-nnn] reference in the drafts, graded against the fact bank. `docs` = run.scan_matter's
    (tier, rel, body, mtime) list. Returns {"refs": [...], "bank": rel path, "entries": n}."""
    from .exhibit_check import ids_in_text
    refs = []
    for tier, rel, body, _mt in docs:
        for m in _REF_RE.finditer(body or ""):
            refs.append({"tier": tier, "file": rel, "line": body.count("\n", 0, m.start()) + 1,
                         "ids": [fid(x) for x in re.findall(r"F-\d{1,4}", m.group(1))],
                         "sentence": _sentence_at(body, m.start(), m.end())})
    bank_path = cfg.abs(cfg["fact_bank"])
    if not refs:
        return {"refs": [], "bank": _rel(bank_path, cfg.root), "entries": 0}
    bank = read_bank(bank_path)
    state = {}
    for r in refs:
        entries = [(i, (bank or {}).get(i)) for i in r["ids"]]
        r.update(missing=[], names=[], ocr=[], notes=[], detail="")
        unknown = [i for i, e in entries if not e]
        if unknown:
            r["verdict"] = UNKNOWN_ENTRY
            r["detail"] = "%s not in the fact bank (%s)" % (", ".join(unknown), _rel(bank_path, cfg.root)
                                                           if bank is not None else "no fact bank file yet")
            continue
        for i, e in entries:
            if i not in state:
                state[i] = _slice_state(cfg, e)
        gone = [(i, state[i][1]) for i, _e in entries if not state[i][0]]
        if gone:
            r["verdict"] = SLICE_GONE
            r["detail"] = "; ".join("%s: %s" % g for g in gone)
            continue
        r["notes"] = ["%s: %s" % (i, state[i][1]) for i, _e in entries if state[i][1]]
        idx = SliceIndex([e["slice"] for _i, e in entries])
        toks = sentence_tokens(r["sentence"], packs)
        hard = [t for t in toks if t["kind"] != NAME]
        r["missing"] = [_fmt(t, idx) for t in hard if not idx.holds(t)]
        r["names"] = [t["raw"] for t in toks if t["kind"] == NAME and not idx.holds(t)]
        r["ocr"] = [i for i, e in entries if (e.get("text layer") or "").lower().startswith("ocr")]
        cited = ids_in_text(r["sentence"])
        wrong = [(i, e.get("exhibit")) for i, e in entries if cited and e.get("exhibit") not in cited]
        if wrong:
            r["verdict"] = WRONG_EXHIBIT
            r["detail"] = "; ".join("%s is a slice of %s, the sentence cites %s" % (i, x, ", ".join(sorted(cited)))
                                    for i, x in wrong)
        elif r["missing"]:
            r["verdict"] = NOT_IN_SLICE
        elif not hard:
            r["verdict"] = NOTHING
        else:
            r["verdict"] = SUPPORTED
        if r["missing"]:
            miss = "not in the slice: %s" % ", ".join(r["missing"])
            r["detail"] = "%s; %s" % (r["detail"], miss) if r["detail"] else miss
    return {"refs": refs, "bank": _rel(bank_path, cfg.root), "entries": len(bank or {})}


def red_count(fres, tiers="AB"):
    return sum(1 for r in (fres or {}).get("refs") or () if r["verdict"] in RED and r["tier"] in tiers)


def console_lines(fres):
    """What `check` prints about the fact references (empty when the drafts cite none)."""
    refs = (fres or {}).get("refs") or []
    if not refs:
        return []
    c = collections.Counter(r["verdict"] for r in refs)
    red = sum(c[v] for v in RED)
    out = ["%s FACTS: %d sentence(s) cite the fact bank (%s, %d entries) - %d held by their slice, %d 🔴 %s"
           % ("🔴" if red else "✅", len(refs), fres["bank"], fres["entries"], c[SUPPORTED], red,
              " · ".join("%s %d" % (v, c[v]) for v in RED if c[v]) or "none")]
    if c[NOTHING]:
        out.append("   ⚪ %d state no date, amount or number - nothing was held to their slice." % c[NOTHING])
    nn = sum(1 for r in refs if r["names"])
    if nn:
        out.append("   🟡 %d name a word their slice does not hold - read them: names are listed, never counted "
                   "(REPORT.md)." % nn)
    no = sum(1 for r in refs if r["ocr"] and r["verdict"] == SUPPORTED)
    if no:
        out.append("   🟡 %d held by a slice read from an OCR layer - confirm its digits against the page image." % no)
    if red:
        out.append("   Tiers A+B red facts count in the exit code; REPORT.md «Facts held to their slices» lists "
                   "every reference.")
    return out


def report_md(fres, cap=200):
    refs = (fres or {}).get("refs") or []
    if not refs:
        return []
    md = ["## Facts held to their slices", "",
          "Each sentence carrying `[F-nnn]` is held to the banked slice(s): every date, amount and number of the "
          "sentence must stand in it, and the exhibit the sentence cites must be the entry's. Names are listed when "
          "the slice does not hold them - for reading, never counted (measured: a red on names would be wrong about "
          "half the time). Bank: `%s`." % fres["bank"], ""]
    order = {v: k for k, v in enumerate(RED + (NOTHING, SUPPORTED))}
    for r in sorted(refs, key=lambda r: (order.get(r["verdict"], 99), r["file"], r["line"]))[:cap]:
        extra = []
        if r.get("detail"):
            extra.append(r["detail"])
        if r.get("names"):
            extra.append("🟡 names the slice does not hold: %s" % ", ".join(r["names"]))
        if r.get("ocr"):
            extra.append("🟡 %s rest(s) on an OCR layer" % ", ".join(r["ocr"]))
        extra += r.get("notes") or []
        md.append("* %s **%s** · `%s:%d` · %s%s" % (MARK.get(r["verdict"], ""), r["verdict"], r["file"], r["line"],
                                                    ", ".join(r["ids"]), (" - " + "; ".join(extra)) if extra else ""))
    if len(refs) > cap:
        md.append("* … and %d more (`result.json` `facts`)" % (len(refs) - cap))
    return md + [""]
