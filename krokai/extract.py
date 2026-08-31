# -*- coding: utf-8 -*-
"""Pulling the quoted spans out of a document you wrote.

This is the half nobody expects to be hard. It is, and every simplification below was tried first
and produced false alarms - which is the failure that kills a checker, because a tool that cries
wolf stops being read inside a week.
"""
from __future__ import annotations

import re

from .normalize import (normalise, strip_markdown, is_mostly_cyrillic, alnum)

__all__ = ["extract_quotes", "blocks", "DEFAULT_MIN_LEN"]

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


def _quote_patterns(min_len):
    return [re.compile(r'"([^"\n]{%d,})"' % min_len),
            re.compile(r'“([^”\n]{%d,})”' % min_len),
            re.compile(r'«([^»\n]{%d,})»' % min_len)]


_INNER = [re.compile(r'"([^"\n]{20,})"'),
          re.compile(r'«([^»\n]{20,})»'),
          re.compile(r'“([^”\n]{20,})”')]


def _split_blockquote(line):
    """A blockquote line is frequently NOT one quotation. Three shapes measured on a real corpus:

        «A» · «B»                              two separate quotations joined by our own bullet
        "text." Matter of Blas, 15 I&N Dec.    a quotation followed by the citation for it
        > «text» - and our own commentary      a quotation plus a gloss on the same line

    Treating the whole line as one quotation makes all three fail against a real source, and that
    failure is **indistinguishable from fabrication**. If the line contains complete quoted spans,
    those spans ARE the quotations and everything around them is ours.
    """
    inner = []
    for rx in _INNER:
        inner += [m.group(1) for m in rx.finditer(line)]
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
        for rx in _quote_patterns(min_len):
            found += [m.group(1) for m in rx.finditer(blk)]
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
