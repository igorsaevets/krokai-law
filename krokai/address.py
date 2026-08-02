# -*- coding: utf-8 -*-
"""Address binding: "found in the corpus" is not the same claim as "found where you said".

WHAT THIS ANSWERS
-----------------
``verify.check()`` answers *"are these words in some primary source?"*. That is a real question and
it catches fabrication. It is also, on its own, the reason a checker can bless a citation that
sends the reader to the wrong page - and an opposing reader who follows a pincite and finds nothing
has been handed a free argument about your care.

So this layer answers the second question: *"were the words found in the document whose address is
printed next to them?"*

FOUR OUTCOMES, AND "COULD NOT TELL" IS ONE OF THEM
--------------------------------------------------
``MATCHED`` · ``MISMATCH`` · ``NO_NEARBY_CITATION`` · ``ADDRESS_NOT_IN_CORPUS``

The last two exist so that *"I could not check"* never quietly renders as *"it checked out"*. That
distinction is the whole ethic of this toolkit: for a document that gets filed,
``NO_NEARBY_CITATION`` means **do not award a green** - not because something is wrong, but because
nothing can be verified about an address that was never written down.

ANCHOR-MISS REPAIR, AND WHY IT NEEDS A FLOOR
--------------------------------------------
When the global search landed in file X but the cited address points at file Y, one possibility is
that the quotation is fine and the *global anchor* simply found another copy first - the same
provision is reprinted in several places. So the text is re-tested inside file Y, and if it is
there, the verdict is repaired to VERIFIED with an explicit note that the previous verdict was an
anchor miss.

🔴 The repair is gated at 60 characters, contributed by one reviewer. A short stock phrase
("not substantially justified") can occur by coincidence inside the file at the cited address, and
without the floor the repair would bless a coincidence.
"""
from __future__ import annotations

import os

from .normalize import normalise, alnum, dehyph

__all__ = ["KeyMap", "address_check", "repair_anchor_miss", "fold", "ADDRESS_CLEAN"]

# Verdicts for which a mismatched address is worth upgrading into its own finding. If the text
# already failed on its own, the address note is appended rather than promoted - two complaints
# about one quotation read as two defects.
ADDRESS_CLEAN = ("VERIFIED", "PUNCTUATION", "TYPESETTING", "ASSEMBLED", "SCATTERED")


class KeyMap(object):
    """address key -> the corpus files that could plausibly hold it.

    Resolution is computed once per key and cached: there are a few dozen distinct addresses and the
    corpus is megabytes, so re-walking it for each of several thousand quotations would cost more
    than the whole check.
    """

    def __init__(self, corpus, packs):
        self.corpus = corpus
        self.packs = packs
        self._cache = {}

    def resolve(self, key):
        if key not in self._cache:
            hits = []
            for path, text in zip(self.corpus.paths, self.corpus.texts):
                try:
                    if self.packs.file_matches(key, path, text):
                        hits.append(path)
                except Exception:
                    continue
            self._cache[key] = hits
        return self._cache[key]


def address_check(near_cites, found_path, keymap, packs):
    """Compare the address printed beside a quotation with the file the text was found in."""
    keys = packs.keys(near_cites)
    if not keys:
        return {"status": "NO_NEARBY_CITATION", "keys": []}
    mapped = {k: keymap.resolve(k) for k in keys}
    known = {k: v for k, v in mapped.items() if v}
    if not known:
        return {"status": "ADDRESS_NOT_IN_CORPUS",
                "keys": sorted(packs.label(k) for k in keys)}
    for k, paths in known.items():
        if found_path in paths:
            return {"status": "MATCHED", "matched": packs.label(k),
                    "keys": sorted(packs.label(x) for x in keys)}
    better = sorted({p for v in known.values() for p in v})
    return {"status": "MISMATCH",
            "keys": sorted(packs.label(k) for k in known),
            "expected_files": better}


def repair_anchor_miss(quote, addr, corpus, min_len=60):
    """Is the quotation actually present in one of the files the address points at?

    Returns the path if so. This is the measured case where a statute's declaration clause was
    compared against an unrelated regulation and flagged for a changed operative word, while the
    file holding the real provision sat on the same disk.
    """
    n = normalise(quote)
    if len(n) < min_len:
        return None
    for path in (addr.get("expected_files") or [])[:10]:
        try:
            t = corpus.text_of(path)
        except (KeyError, ValueError):
            continue
        if n in t or alnum(n) in alnum(t) or dehyph(n) in dehyph(t):
            return path
    return None


def fold(quote, verdict, path, detail, near_cites, corpus, keymap, packs):
    """Fold the address layer into a text verdict. Returns `(verdict, path, detail, address)`.

    🔴 The address is taken from the NEAR ring only (see ``extract.citation_window``). The wide ring
    stays available to the miss classifier, because a neighbour in the same paragraph tells you
    whether the source ought to be downloaded - but it is not this quotation's address, and treating
    it as one produced accusations against innocent documents in the first build of this layer.
    """
    if not path:
        return verdict, path, detail, None
    if not near_cites:
        return verdict, path, detail, {"status": "NO_NEARBY_CITATION", "keys": []}

    addr = address_check(near_cites, path, keymap, packs)
    if addr["status"] != "MISMATCH":
        return verdict, path, detail, addr

    repaired = repair_anchor_miss(quote, addr, corpus)
    if repaired:
        if verdict != "VERIFIED":
            detail = ("correct at the cited address «%s»; the global anchor pointed at «%s» - the "
                      "previous verdict %s was an anchor miss"
                      % (os.path.basename(repaired), os.path.basename(path), verdict))
        return ("VERIFIED", repaired, detail,
                {"status": "MATCHED", "matched": "after binding", "keys": addr["keys"]})

    if verdict in ADDRESS_CLEAN:
        detail = ("found verbatim in «%s», but the address printed beside it (%s) points at %s - "
                  "and the string is NOT there%s"
                  % (os.path.basename(path), "; ".join(addr["keys"]),
                     "; ".join(os.path.basename(b) for b in addr["expected_files"][:3]),
                     ("" if not detail else ". Previously: " + detail)))
        return "FOUND_ELSEWHERE", path, detail, addr

    detail = (detail + " · " if detail else "") + (
        "address mismatch: cited %s, found in «%s»"
        % ("; ".join(addr["keys"]), os.path.basename(path)))
    return verdict, path, detail, addr
