# -*- coding: utf-8 -*-
"""Gap and conflict markers: the drafter flags what it could not ground, and nothing erases a flag silently.

K027 (2026-11-24). A model asked to draft from incomplete evidence fills the hole with fluent prose, and when
two exhibits disagree it silently picks one - every research file the owner collected on AI drafting describes
this, and krokai checked quotations, never the claims around them. The cure is half a rule, half a mechanism:

1. THE RULE (`templates/CLAUDE.md.snippet`): where the evidence runs out the drafter writes `[MISSING: ...]`,
   where two exhibits disagree `[CONFLICT: ...]`. A FIXED vocabulary, because legal text is full of brackets
   (`[sic]`, `[emphasis added]`, `[a]lien`). Measured on a copy of a filed petition (11 files), its version
   chain, a 130-file draft archive and the law corpus (302 files, 25.0 M characters, 17 `[sic]`): not one
   bracket opening with these heads. The only hits were three bare `[КОНФЛИКТ]` tags in the case's Russian
   working notes - a research tier: listed, never gated.
2. THE MECHANISM: `check` lists the open markers per file and remembers them; a marker that vanished since
   the last check is named with the sentence now standing in its place. A later editing pass - human or
   model - that replaces a marker with a smooth sentence is the silent finalization this exists to catch.
   `close` refuses while a filed document (tier A) carries one.

🔴 THE TRAP RUNS BOTH WAYS. Punish markers and the drafter learns to stop writing them: so the count never
reaches `check`'s exit code (a matter mid-drafting is SUPPOSED to carry markers) and only `close` - the
end-of-round gate for what gets filed - refuses. And a gate on open markers alone rewards deleting them,
which is why a vanished marker is loud.

🔴 NO PROSE IN THE STATE. `.krokai/markers.json` (beside `law_registry.json`) keeps the marker notes
themselves - the drafter's own words, needed to say WHICH gap closed - and, for the place, only hashes of
the six words before and after. The sentence printed for a vanished marker is read from the draft as it
stands now, never from the state.

🔴 THE COPY, NOT THE FILE. The measured habit is a version folder per round (Final14 ... Final17, the same
eleven files each). A per-file memory never sees a marker that was written over while the file was COPIED
into the next version - so the six words around every open marker are also looked for in the other filed
and guide drafts, and in any draft when its own file is gone.
"""
from __future__ import annotations

import bisect
import hashlib
import io
import json
import os
import re
import time
from collections import Counter

__all__ = ["MARKER_RE", "STATE", "find_markers", "analyse", "load_state", "save_state",
           "gone_line", "count_line"]

STATE = os.path.join(".krokai", "markers.json")
ANCHOR_WORDS = 6        # words hashed on each side of a marker
MIN_ANCHOR = 3          # fewer than this at the very start / end of a file is no anchor at all
PAIR_SPAN = 3000        # characters allowed between the two anchors when a marker's place is looked for
REPORTED_CAP = 500      # cross-file findings remembered, so each is reported once

_GAP = r"MISSING(?:[ _]EVIDENCE)?|НУЖЕН[ _]ДОКУМЕНТ"
_CONFLICT = r"CONFLICT|КОНФЛИКТ"
# Head: whole word, any case. Then an optional separator (colon, dash, or whitespace), then the drafter's
# note: at most 400 characters, never across a blank line, and it may hold an opening bracket of its own
# (`[MISSING: the date on [Exhibit 12]` still counts - truncated, not missed).
MARKER_RE = re.compile(
    r"\[[ \t]*(?P<head>%s|%s)(?!\w)(?:[ \t]*[:–—-]|\s)?"
    r"(?P<body>(?:(?!\n[ \t]*\n)[^\]]){0,400})\]" % (_GAP, _CONFLICT), re.I)
_WORD = re.compile(r"\w+")
# A sentence ends at . ! ? … before whitespace and a capital / quote / bracket (or the end), at a blank
# line, or at a line break before a list item, heading, table row or quotation line. Display only.
_SENT_END = re.compile(r"[.!?…](?=\s+[A-ZА-ЯЁ\"'“«(\[]|\s*$)|\n[ \t]*\n"
                       r"|\n(?=[ \t]*(?:[-*+#|>]|\d+[.)])[ \t])")
_STRIP = " \t\r\n.,;:!?…"


def _h(words):
    return hashlib.sha1("\x1f".join(words).encode("utf-8")).hexdigest()[:16]


def _key(text):
    return " ".join(text.split()).casefold()


def _tokens(text):
    return [(m.start(), m.end(), m.group().lower()) for m in _WORD.finditer(text)]


def find_markers(text, toks=None):
    """Every marker in `text`: kind (gap / conflict), its text, offsets, and the anchors around it."""
    toks = _tokens(text) if toks is None else toks
    starts = [t[0] for t in toks]
    out = []
    for m in MARKER_RE.finditer(text):
        head = m.group("head").upper()
        i = bisect.bisect_left(starts, m.start())
        j = bisect.bisect_left(starts, m.end())
        bw = [t[2] for t in toks[max(0, i - ANCHOR_WORDS):i]]
        aw = [t[2] for t in toks[j:j + ANCHOR_WORDS]]
        out.append({"kind": "gap" if head.startswith(("MISSING", "НУЖЕН")) else "conflict",
                    "text": " ".join(m.group(0).split()), "start": m.start(), "end": m.end(),
                    "before": {"h": _h(bw), "n": len(bw)} if len(bw) >= MIN_ANCHOR else None,
                    "after": {"h": _h(aw), "n": len(aw)} if len(aw) >= MIN_ANCHOR else None})
    return out


class _Doc(object):
    """One draft as it stands now, with its markers and a lazy index of its word windows."""

    def __init__(self, tier, rel, text, mtime=None):
        self.tier, self.rel, self.text, self.mtime = tier, rel.replace(os.sep, "/"), text, mtime
        self.toks = _tokens(text)
        self.markers = find_markers(text, self.toks)
        self.keys = Counter(_key(m["text"]) for m in self.markers)
        self._win = {}

    def at(self, anchor, side):
        """Where `anchor` stands now: the END offsets of a before-anchor, the START offsets of an
        after-anchor."""
        if not anchor:
            return []
        n = anchor["n"]
        if n not in self._win:
            words = [t[2] for t in self.toks]
            idx = {}
            for i in range(len(words) - n + 1):
                idx.setdefault(_h(words[i:i + n]), []).append(i)
            self._win[n] = idx
        hits = self._win[n].get(anchor["h"], [])
        return [self.toks[i + n - 1][1] for i in hits] if side == "before" else \
               [self.toks[i][0] for i in hits]


def _place(doc, mk):
    """(lo, hi) between the anchors of marker `mk` in `doc`; one side None when only that side was found
    (and found once); None when the place cannot be found."""
    bs, as_ = doc.at(mk.get("before"), "before"), doc.at(mk.get("after"), "after")
    best = None
    for b in bs:
        for a in as_:
            if 0 <= a - b <= PAIR_SPAN and (best is None or a - b < best[1] - best[0]):
                best = (b, a)
    if best:
        return best
    if len(bs) == 1:
        return bs[0], None
    if len(as_) == 1:
        return None, as_[0]
    return None


def _clip(s, cap=400):
    s = " ".join(s.split())
    return s if len(s) <= cap else s[:cap - 1] + "…"


def _sentence(text, lo, hi):
    st = 0
    for m in _SENT_END.finditer(text, 0, lo):
        st = m.end()
    m = _SENT_END.search(text, max(lo, hi - 1))
    return _clip(text[st:m.end() if m else len(text)])


def _describe(doc, mk, both_only=False):
    """What stands where marker `mk` stood, in `doc` as it is now."""
    rec = {"tier": doc.tier, "file": doc.rel, "marker": mk["text"], "kind": mk.get("kind", ""),
           "seen": mk.get("seen", "")}
    pl = _place(doc, mk)
    if pl is None or (both_only and None in pl):
        rec.update(how="lost", now="")
        return rec
    b, a = pl
    if b is None or a is None:
        p = b if b is not None else a
        rec.update(how="near", now=_sentence(doc.text, p, p))
        return rec
    region = doc.text[b:a]
    other = MARKER_RE.search(region)
    if other:
        rec.update(how="reworded", now=" ".join(other.group(0).split()))
    elif not region.strip(_STRIP):
        rec.update(how="deleted", now=_sentence(doc.text, b, b))
    else:
        lo = b + len(region) - len(region.lstrip(_STRIP))
        hi = b + len(region.rstrip(" \t\r\n"))
        rec.update(how="replaced", now=_sentence(doc.text, lo, hi))
    return rec


def analyse(docs, prev=None, scanned_tiers="ABCD", only=None, today=None):
    """`docs` = [(tier, relative path, text[, mtime])] for every draft this run read; `prev` = the state of the last
    `check` ({} when none). Returns {"open", "gone", "state"}; the caller decides whether to keep the state
    (`check` does, `close` never)."""
    today = today or time.strftime("%Y-%m-%d")
    D = [_Doc(*e) for e in docs if e[0] != "D"]
    by = {d.rel: d for d in D}
    ab = [d for d in D if d.tier in ("A", "B")]
    pfiles = (prev or {}).get("files") or {}
    reported = [x for x in ((prev or {}).get("reported") or []) if isinstance(x, str)]
    rep = set(reported)
    files, open_, gone, carry = {}, [], [], {}

    for rel, rec in sorted(pfiles.items()):
        if rel in by:
            continue
        if only or rec.get("tier") not in scanned_tiers:
            files[rel] = rec                                    # outside this run: kept as it was
            continue
        lost = 0                                                # the file is gone: where did its markers go?
        for p in rec.get("markers") or []:
            k = _key(p["text"])
            home = next((d for d in ab if d.keys.get(k)), None)
            if home is not None:                                # moved, still open: keep its date
                carry.setdefault((home.rel, k), []).append(p.get("seen") or today)
                continue
            hit = None
            for g in ab:
                d = _describe(g, p, both_only=True)
                if d["how"] != "lost":
                    hit = d
                    break
            if hit:
                hit["was_in"] = rel
                gone.append(hit)
            else:
                lost += 1
        if lost:
            gone.append({"tier": rec.get("tier", ""), "file": rel, "how": "file gone", "kind": "",
                         "marker": "%d open marker%s" % (lost, "" if lost == 1 else "s"), "now": "",
                         "seen": ""})

    for d in D:
        prevm = (pfiles.get(d.rel) or {}).get("markers") or []
        if d.tier in ("A", "B") and prevm:
            left = Counter(d.keys)
            for p in prevm:
                k = _key(p["text"])
                if left[k] > 0:
                    left[k] -= 1
                else:
                    gone.append(_describe(d, p))
        seen = {}
        for p in prevm:
            seen.setdefault(_key(p["text"]), []).append(p.get("seen") or today)
        for (home, k), dates in carry.items():
            if home == d.rel:
                seen.setdefault(k, []).extend(dates)
        recs = []
        for m in d.markers:
            lst = seen.get(_key(m["text"]))
            recs.append({"kind": m["kind"], "text": m["text"], "before": m["before"],
                         "after": m["after"], "seen": lst.pop(0) if lst else today})
        if recs:
            open_.append({"tier": d.tier, "file": d.rel,
                          "gap": sum(1 for m in recs if m["kind"] == "gap"),
                          "conflict": sum(1 for m in recs if m["kind"] == "conflict"),
                          "markers": [m["text"] for m in recs],
                          "since": min(m["seen"] for m in recs)})
            if d.tier in ("A", "B"):
                files[d.rel] = {"tier": d.tier, "markers": recs}

    for f in D:                                                 # written over in a copy
        for m in f.markers:
            k = _key(m["text"])
            for g in ab:
                if g is f or g.keys.get(k):
                    continue
                if f.mtime is not None and g.mtime is not None and g.mtime < f.mtime:
                    continue                    # g is the OLDER copy: the marker was added in f, not written over
                d = _describe(g, m, both_only=True)
                if d["how"] in ("lost", "reworded"):
                    continue
                tag = _h([f.rel, g.rel, k])
                if tag in rep:
                    continue
                rep.add(tag)
                reported.append(tag)
                d["open_in"] = f.rel
                gone.append(d)

    state = {"_doc": "krokai (K027): the gap and conflict markers each filed and guide draft carried at the "
                     "last `krokai check`. Holds the marker notes themselves (the drafter's words - keep this "
                     "file inside the matter) and, for each place, hashes of the six words around it: no "
                     "surrounding prose. Delete it and the next check starts a fresh record.",
             "version": 1, "files": files, "reported": reported[-REPORTED_CAP:]}
    return {"open": open_, "gone": gone, "state": state}


def load_state(root):
    """(state, problem): ({}, None) when there is no record yet; ({}, "<why>") when it cannot be read."""
    p = os.path.join(root, STATE)
    if not os.path.exists(p):
        return {}, None
    try:
        with io.open(p, encoding="utf-8") as fh:
            st = json.load(fh)
        return (st, None) if isinstance(st, dict) else ({}, "not a JSON object")
    except (OSError, ValueError) as exc:
        return {}, type(exc).__name__


def save_state(root, state):
    """Atomic: a truncated record would forget every marker it held (the `_write_registry` lesson)."""
    p = os.path.join(root, STATE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True))
    os.replace(tmp, p)
    return p


def _pl(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def count_line(o):
    parts = []
    if o["gap"]:
        parts.append(_pl(o["gap"], "gap", "gaps"))
    if o["conflict"]:
        parts.append(_pl(o["conflict"], "conflict", "conflicts"))
    return "%s open (%s)" % (o["gap"] + o["conflict"], " · ".join(parts))


def gone_line(g):
    """One line per vanished marker - the place and what stands there now."""
    head = "%s %s: " % (g["tier"], g["file"])
    if g["how"] == "file gone":
        return head + "file gone - it carried %s" % g["marker"]
    where = (" (still open in %s)" % g["open_in"]) if g.get("open_in") else \
            (" (was in %s)" % g["was_in"]) if g.get("was_in") else ""
    tail = {"replaced": "now: «%s»",
            "deleted": "deleted, nothing in its place; the sentence now: «%s»",
            "reworded": "reworded, still open: %s",
            "near": "its exact place is unclear; near it now: «%s»",
            "lost": "its place cannot be found - the words around it changed too%s"}[g["how"]]
    return head + g["marker"] + where + " → " + (tail % g["now"])
