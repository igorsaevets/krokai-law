# -*- coding: utf-8 -*-
"""Pulling the quoted spans out of a document you wrote.

This is the half nobody expects to be hard. It is, and every simplification below was tried first
and produced false alarms - which is the failure that kills a checker, because a tool that cries
wolf stops being read inside a week.
"""
from __future__ import annotations

import bisect
import re
import unicodedata

from .normalize import (normalise, strip_markdown, is_mostly_cyrillic, alnum)

__all__ = ["extract_quotes", "blocks", "not_examined", "DEFAULT_MIN_LEN"]

# Below this length every ordinary phrase in the prose becomes a "quotation", the report fills with
# noise, and a report nobody reads catches nothing.
DEFAULT_MIN_LEN = 45

_NEW_BLOCK = re.compile(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s|\||>)")


def blocks(text):
    """Split into PARAGRAPHS, not lines.

    🔴 Markdown wraps a quotation across lines, and a line-based extractor sees the wreckage:

        > "Family ties to the United States
        > and the closeness of the underlying relationships" - "Length of lawful residence...

    Line two on its own looks exactly like a mangled quotation. The first run of the original tool
    duly reported four of these as ALTERED. Every one of them was verbatim correct in the source.

    So a block is consecutive lines of the same kind, joined. **Table rows stay separate** - joining
    them would let a quotation match across two cells, inventing the opposite error.

    Yields `(kind, text)` where kind is `q` blockquote, `t` table row, `p` prose.
    """
    out, cur = [], []
    kind = None

    def flush():
        if cur:
            out.append((kind, " ".join(cur)))
        del cur[:]

    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            flush()
            kind = None
            continue
        k = "q" if s.startswith(">") else ("t" if s.startswith("|") else "p")
        if k == "t" or kind != k or (k == "p" and _NEW_BLOCK.match(s)):
            flush()
            kind = k
        cur.append(s.lstrip("> ").strip() if k == "q" else s)
    flush()
    return out


# 🔴 K049 (2026-11-28, the re-rank after K045d). Quoted spans were found by a regex per quote style,
# `"([^"]{45,})"` run left to right. A short quoted term before a long quotation broke it: the term
# is under 45 characters, so the scan moved on and RESTARTED AT THE TERM'S CLOSING MARK - the
# drafter's prose up to the long quotation's OPENING mark became a «quotation» (NOT FOUND: a false
# alarm), and the long quotation, its opening mark already spent, was never examined. Nothing said
# so. Measured on a copy of the matter: the filed petition carried 2 long quotations never examined
# and 9 rows of its own prose; the I-140 letter 14 and 92. A language model writes straight quotes,
# so the commonest drafting style was the one read wrong.
#
# So the marks are PAIRED first and the length filter runs after. An opening mark waits on a stack;
# a closing mark takes the nearest one waiting. Curly quotes and guillemets say which they are; a
# straight quote is told by its neighbours - CommonMark's smart-quote test (spec 0.31.2,
# «left-flanking delimiter run»; commonmark.js `scanDelims`: a quote opens when it is left-flanking
# and not right-flanking, and closes when it is right-flanking). The test and not a 1-2 / 3-4
# count: on the same copy 54 paragraphs hold an odd number of straight marks - mostly a quotation
# opened in one paragraph and closed in a later one - and a count shifts every pair after the first
# unpaired mark. A mark that pairs with nothing is listed by `not_examined` (`unpaired`), never
# guessed into a quotation; a quotation inside a quotation is examined as part of the outer one.
def _punct(c):
    return unicodedata.category(c)[0] in "PS"


def _straight_role(s, i):
    """'open', 'close' or None for the straight quote at `s[i]`; the text's edges count as spaces."""
    a = s[i - 1] if i > 0 else " "
    b = s[i + 1] if i + 1 < len(s) else " "
    left = not b.isspace() and (not _punct(b) or a.isspace() or _punct(a))
    right = not a.isspace() and (not _punct(a) or b.isspace() or _punct(b))
    if left and not right:
        return "open"
    return "close" if right else None


_CLOSER_OF = {"”": "“", "»": "«"}


def _pairs(blk):
    """`(spans, loose)`: the text of every OUTERMOST quoted span of `blk`, in reading order, and the
    offsets of the quotation marks that pair with nothing. «„…“» (German / Russian) pairs too, so
    its closing mark is not read as an opening one."""
    waiting = {'"': [], "“": [], "«": [], "„": []}
    pairs, loose = [], []
    for i, ch in enumerate(blk):
        if ch == '"':
            role = _straight_role(blk, i)
            if role == "open":
                waiting['"'].append(i)
            elif role == "close" and waiting['"']:
                pairs.append((waiting['"'].pop(), i))
            else:
                loose.append(i)
        elif ch == "“" and waiting["„"]:
            pairs.append((waiting["„"].pop(), i))
        elif ch in waiting:
            waiting[ch].append(i)
        elif ch in _CLOSER_OF:
            st = waiting[_CLOSER_OF[ch]]
            if st:
                pairs.append((st.pop(), i))
            else:
                loose.append(i)
    loose += [i for st in waiting.values() for i in st]
    spans, end = [], -1
    for a, b in sorted(pairs):
        if b > end:                     # not inside the outer span before it
            spans.append(blk[a + 1:b])
            end = b
    return spans, sorted(loose)


def _split_blockquote(line):
    """A blockquote line is frequently NOT one quotation. Three shapes measured on a real corpus:

        «A» · «B»                              two separate quotations joined by our own bullet
        "text." Matter of Blas, 15 I&N Dec.    a quotation followed by the citation for it
        > «text» - and our own commentary      a quotation plus a gloss on the same line

    Treating the whole line as one quotation makes all three fail against a real source, and that
    failure is **indistinguishable from fabrication**. If the line contains complete quoted spans,
    those spans ARE the quotations and everything around them is ours.
    """
    inner = [s for s in _pairs(line)[0] if len(s) >= 20]
    return inner if inner else [line]


# A blockquote containing a markdown HEADING is a callout box, not a quotation of law.
#
# 🔴 Measured on the first real run: this toolkit's own quote-bank template puts its house rules
# inside a `>` block for emphasis, and the whole block was extracted as a quotation and reported
# NOT FOUND - a false alarm manufactured by the tool's own template. Callout blocks are common in
# real memoranda too.
#
# The test is deliberately narrow. `## ` inside quoted statutory text essentially never happens,
# whereas numbered lists inside quoted statutes happen constantly - so a heading marker is the
# signal and a numbered list is NOT. Quoted spans *inside* the callout are still extracted by the
# pattern pass below, so a genuine quotation inside a warning box is not lost.
_CALLOUT_RE = re.compile(r"(?:^|\s)#{1,6}\s")


def extract_quotes(text, min_len=DEFAULT_MIN_LEN, drop_cyrillic=True):
    """Quoted spans plus markdown blockquote blocks. Deduplicated, original order preserved.

    `drop_cyrillic` filters out the drafter's own commentary when the working language differs from
    the language of the law. Turn it off if you quote sources in Cyrillic.
    """
    found = []
    for kind, blk in blocks(text):
        found += [s for s in _pairs(blk)[0] if len(s) >= min_len]        # K049: pair, then filter
        if kind == "q" and len(blk) >= min_len and not _CALLOUT_RE.search(blk):
            found.extend(_split_blockquote(blk))

    out, seen = [], set()
    for q in found:
        q = strip_markdown(q).strip()
        if drop_cyrillic and is_mostly_cyrillic(q):
            continue
        if len(q) < min_len:
            continue
        key = normalise(q).lower()
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def citation_window(body, quote, packs, near=140, far=400):
    """The citations standing next to a quotation, in two rings, and the difference matters.

    * **near** (±140 characters of the span, and NOT inside it) is the quotation's *address*. A
      reference inside the quoted text is part of the quoted text - it is what the source cites,
      not where the source lives. Measured: `"...limits stated in 8 C.F.R. § 214.2(f)(6)"` inside a
      quotation from an agency newsletter bound that quotation to part 214, and the resulting
      mismatch was an accusation against an innocent document.

    * **far** (±400) is used only to classify a MISS. A citation in the same paragraph tells you
      whether the corpus ought to have contained the source at all; it does not tell you the
      address.

    Returns `(near_cites, far_cites)`.

    🔴 R76 (F1, execution-proven; kimik3/lunapro/agy37flash converged): the raw `body.find`
    fails for any quotation that `blocks()` re-joined across line breaks or that
    `strip_markdown` cleaned - i.e. most wrapped blockquotes - and the miss was SILENT:
    empty rings, the address layer off, and a NOT_FOUND misclassified «evidentiary». The
    fallback below maps the probe into the raw body through the alphanumeric projection,
    the same walk `_punctuation_detail` uses. First occurrence only, as before.
    """
    probe = quote[:60]
    idx = body.find(probe)
    qlen = len(quote)
    if idx < 0:
        idx, qlen = _alnum_locate(body, quote)
        if idx < 0:
            return [], []
    lo = max(0, idx - far)
    window = body[lo: idx + qlen + far]

    near_c, far_c = [], []
    for text, rel in packs.find_positions(window):
        if text not in far_c:
            far_c.append(text)
        pos = lo + rel
        inside = idx <= pos < idx + qlen
        if not inside and (idx - near <= pos < idx + qlen + near):
            if text not in near_c:
                near_c.append(text)
    return near_c, far_c


def _alnum_locate(body, quote):
    """Locate `quote` in `body` through the alphanumeric projection.

    Returns ``(raw_start, raw_length)`` of the matching span, or ``(-1, 0)``. Letters and
    digits survive every difference `blocks()`/`strip_markdown` introduce (line wraps, `> `
    markers, bold, curly quotes), so this finds what the raw `find` cannot - at the cost of a
    single O(len(body)) walk, paid only on the raw miss.
    """
    aq = alnum(quote)
    if not aq:
        return -1, 0
    positions = []
    chars = []
    for k, ch in enumerate(body):
        if ch.isalnum():
            positions.append(k)
            chars.append(ch.lower())
    i = "".join(chars).find(aq)
    if i < 0:
        return -1, 0
    start = positions[i]
    end = positions[i + len(aq) - 1] + 1
    return start, end - start


# ------------------------------------------------------------------------ what was NOT examined
# 🔴 K023 (2026-11-24; audit 2026-11-23, A1 item 3 and A2 item 1). `extract_quotes` is right to
# skip a quoted phrase under `min_len` (noise, see DEFAULT_MIN_LEN) and, when the matter says so, a
# Cyrillic one (the drafter's own commentary) - but it skipped them SILENTLY, and a paragraph that
# cites a provision without quoting it was never counted at all. So a green `check` meant «what
# was examined is clean» and was read as «everything is clean»: «sustained national or
# international acclaim», quoted beside 8 C.F.R. § 204.5(h)(3), is 43 characters and was never
# looked at. The absence of a warning is read as an all-clear - in the mammography study reviewed
# by Parasuraman & Manzey (2010), readers' detection of the cancers the computer aid left
# unmarked fell from 46 % without the aid to 21 % with it. And a drafter, person or model, who
# drops the quotation marks keeps the report green while citing more and quoting less.
#
# This function only COUNTS what the extractor left out. It never changes what is examined, so
# every verdict stays what it was, and nothing it returns reaches the exit code: it is a reading
# list, not a finding. A short quoted term and a paraphrase are ordinary legal writing, and a gate
# on these numbers would reward deleting citations - the one thing that makes a claim checkable.
# One or more blank lines; \r so that a CRLF text read as bytes still splits into paragraphs.
_PARA_BREAK = re.compile(r"\n(?:[ \t\r\f\v]*\n)+")


def _alnum_projection(text):
    """Raw offsets and lowercased characters of every letter and digit in `text` - built once per
    document, then searched for every quotation (the per-call walk `_alnum_locate` pays each time).
    One character in, one character out, so an offset in the projection is an offset in `text`."""
    pos, chars = [], []
    for k, ch in enumerate(text):
        if ch.isalnum():
            pos.append(k)
            chars.append(ch.lower()[:1])
    return pos, "".join(chars)


def _occurrences(proj, quote):
    """Every raw `(start, end)` of `quote` in the projected text. Letters and digits survive what
    `blocks()` and `strip_markdown` change (line wraps, `> ` markers, emphasis, curly quotes), so
    this finds a wrapped blockquote that a raw `find` misses - and finds every occurrence, not the
    first, because `extract_quotes` deduplicates a quotation used twice in one file."""
    pos, joined = proj
    aq = "".join(ch.lower()[:1] for ch in quote if ch.isalnum())
    out, i = [], joined.find(aq) if aq else -1
    while i >= 0:
        out.append((pos[i], pos[i + len(aq) - 1] + 1))
        i = joined.find(aq, i + len(aq))
    return out


def not_examined(text, examined, packs=None, min_len=DEFAULT_MIN_LEN, drop_cyrillic=True,
                 near=140):
    """What `extract_quotes(text, min_len, drop_cyrillic)` did NOT examine, in four buckets.

    * ``short`` - quoted phrases of two or more words under `min_len` characters, each as
      ``{"text", "cites"}``: `cites` are the primary citations within `near` characters of the
      phrase. A short phrase beside a citation of law is the one worth checking by hand.
    * ``cyrillic`` - quoted phrases skipped because `drop_cyrillic` is on and they are mostly
      Cyrillic. The extractor applies that test before the length test, and so does this.
    * ``cited`` - paragraphs holding a primary citation and carrying no examined quotation, each
      as ``{"excerpt", "cites"}``: the draft cites the law there and the check had nothing to
      compare. A lead-in (a heading, a line ending with a colon, a bare citation) right before a
      quotation and a bare citation line right after one carry it (see below); `near` is the
      address ring of `citation_window`.
    * ``unpaired`` - paragraphs holding a quotation mark that pairs with nothing in the paragraph
      (K049), each as ``{"excerpt", "marks"}``: the excerpt starts 80 characters before the first
      such mark. Measured: a quotation opened in one paragraph and closed in a later one - neither
      part was examined. A typo, an inch mark or a glued word («term"shall"») lands here too.

    A quoted single word is in no bucket: a defined term or a scare quote, and a one-word match
    proves nothing. `examined` is what `extract_quotes` returned for the same text with the same
    settings; `packs=None` skips the citation work (``cites`` and ``cited`` come back empty).
    """
    text = text or ""
    seen = {normalise(q).lower() for q in examined}
    short, cyrillic, unpaired = [], [], []
    for kind, blk in blocks(text):
        spans, loose = _pairs(blk)                  # K049: the extractor's own pairing
        if kind == "q" and not _CALLOUT_RE.search(blk):
            whole = _split_blockquote(blk)
            spans += whole
            if whole == [blk] and len(blk) >= min_len:
                loose = []                          # the whole blockquote was examined
        if loose:
            k = loose[0]
            ex = " ".join(blk[max(0, k - 80):k + 120].split())
            if not (drop_cyrillic and is_mostly_cyrillic(ex)):
                unpaired.append({"excerpt": ex, "marks": len(loose)})
        for s in spans:
            s = strip_markdown(s).strip()
            if len(s.split()) < 2:
                continue
            key = normalise(s).lower()
            if key in seen:
                continue
            if drop_cyrillic and is_mostly_cyrillic(s):
                seen.add(key)
                cyrillic.append(s)
            elif len(s) < min_len:
                seen.add(key)
                short.append(s)

    if packs is None:
        return {"short": [{"text": s, "cites": []} for s in short], "cyrillic": cyrillic,
                "cited": [], "unpaired": unpaired}

    cites = [(c, p) for c, p in packs.find_positions(text) if packs.is_primary(c)]
    proj = _alnum_projection(text)

    def beside(lo, hi):
        return [c for c, p in cites if lo - near <= p < hi + near and not lo <= p < hi]

    short_out = []
    for s in short:
        # The quoted occurrence first: a short phrase often recurs unquoted in the prose, and the
        # citation that matters is the one beside the quotation marks.
        hit = None
        for op, cl in (('"', '"'), ("“", "”"), ("«", "»")):
            k = text.find(op + s + cl)
            if k >= 0:
                hit = (k + 1, k + 1 + len(s))
                break
        if hit is None:
            occ = _occurrences(proj, s)
            hit = occ[0] if occ else None
        near_c = []
        if hit:
            for c in beside(*hit):
                if c not in near_c:
                    near_c.append(c)
        short_out.append({"text": s, "cites": near_c})

    # A paragraph CARRIES a quotation when an examined quotation overlaps it. Two neighbours count
    # as carrying one too, or the commonest layout of a brief reads as a paraphrase: a LEAD-IN - a
    # heading, a line ending with a colon, or a bare citation - whose citation stands within `near`
    # characters before a quotation that opens the next paragraph («Under 8 C.F.R. § 204.5(h)(3)
    # the petitioner must show:» + a blockquote), and a BARE CITATION LINE right after a paragraph
    # that ends with one. A plain ring would be simpler and is wrong both ways, measured on the
    # K023 fixture: it counted a paraphrase as covered because the quotation ABOVE it was within
    # 140 characters, and another because the quotation BELOW it was - hence the shape test.
    occ = sorted(span for q in examined for span in _occurrences(proj, q))
    pos = proj[0]
    starts = [0] + [m.end() for m in _PARA_BREAK.finditer(text)]
    bounds = [(starts[i], starts[i + 1] if i + 1 < len(starts) else len(text))
              for i in range(len(starts))]

    def edge(lo, hi, last):
        j = bisect.bisect_left(pos, hi) - 1 if last else bisect.bisect_left(pos, lo)
        return pos[j] if 0 <= j < len(pos) and lo <= pos[j] < hi else None

    def opener(i):                      # the examined quotation this paragraph OPENS with
        first = edge(bounds[i][0], bounds[i][1], False)
        return next((a for a, _b in occ if a == first), None) if first is not None else None

    def closes(i):                      # does this paragraph END with an examined quotation?
        last = edge(bounds[i][0], bounds[i][1], True)
        return last is not None and any(b - 1 == last for _a, b in occ)

    def carries(i):
        lo, hi = bounds[i]
        return any(a < hi and b > lo for a, b in occ)

    by_para = {}
    for c, p in cites:
        by_para.setdefault(bisect.bisect_right(starts, p) - 1, []).append((c, p))
    cited = []
    for i in sorted(by_para):
        if carries(i):
            continue
        lo, hi = bounds[i]
        para = text[lo:hi].strip()
        nxt = opener(i + 1) if i + 1 < len(bounds) else None
        cite_letters = sum(1 for c, _p in by_para[i] for ch in c if ch.isalpha())
        bare_line = sum(1 for ch in para if ch.isalpha()) - cite_letters < 25
        lead_in = nxt is not None and (para.rstrip("*_ ").endswith(":") or para.startswith("#")
                                       or bare_line)
        left = []
        for c, p in by_para[i]:
            if lead_in and nxt - near <= p:
                continue                                    # a lead-in: the address of the next
            if bare_line and i > 0 and closes(i - 1):
                continue                                    # the citation of the line above
            if c not in left:
                left.append(c)
        if left:
            cited.append({"excerpt": " ".join(text[lo:hi].split())[:200], "cites": left})
    return {"short": short_out, "cyrillic": cyrillic, "cited": cited, "unpaired": unpaired}
