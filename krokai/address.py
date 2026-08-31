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
from .verdicts import CLEAN
from .verify import leading_cut, truncated_condition

__all__ = ["KeyMap", "address_check", "repair_anchor_miss", "fold", "ADDRESS_CLEAN"]

# Verdicts for which a mismatched address is worth upgrading into its own finding. If the text
# already failed on its own, the address note is appended rather than promoted - two complaints
# about one quotation read as two defects.
#
# 🔴 R76: DERIVED from `verdicts.CLEAN`, no longer a third hand-typed list. The old tuple had
# drifted in both directions (spark12cont): it held SCATTERED - so the FOUND_ELSEWHERE promotion
# below would say «found verbatim» about a quotation that is verbatim NOWHERE as one passage -
# and it lacked WRONG_SPEAKER, so a verbatim quotation with a wrong attribution AND a wrong
# address kept its advisory verdict instead of the loud FOUND_ELSEWHERE.
ADDRESS_CLEAN = tuple(CLEAN)


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
            hits, fails = [], 0
            for path, text in zip(self.corpus.paths, self.corpus.texts):
                try:
                    if self.packs.file_matches(key, path, text):
                        hits.append(path)
                except Exception as exc:
                    # 🔴 R77 (#356 / F15, qwen38max + orglm53): a bare `continue` here made a
                    # broken pack rule indistinguishable from a non-matching file - the file
                    # silently left the resolution, the address then read ADDRESS_NOT_IN_CORPUS,
                    # and the advice said "download it" about a source already on disk. Loud,
                    # bounded, never fatal: one broken rule must not kill the whole check.
                    fails += 1
                    if fails <= 3:
                        print("  !! address rule failed on %s for %s: %s"
                              % (os.path.basename(path), "/".join(str(x) for x in key),
                                 type(exc).__name__))
                    continue
            if fails > 3:
                print("  !! ...and %d more rule failures for %s"
                      % (fails - 3, "/".join(str(x) for x in key)))
            self._cache[key] = hits
        return self._cache[key]


def _excluded_match(keys, corpus, packs):
    """Files the corpus EXCLUDED whose filename matches one of the cited keys, with the reason.

    Filename rules only (`body=""`): the excluded file's content is exactly what could not be
    trusted, so it does not get a vote. Returns `[(path, why), ...]`, worst reason first.
    """
    pools = (("a failed download - the file itself says it is an error page or a bot wall",
              getattr(corpus, "excluded_placeholder", ())),
             ("a scan with no usable text layer (or a stub)",
              getattr(corpus, "excluded_stub", ())),
             ("an empty file", getattr(corpus, "excluded_empty", ())))
    out = []
    for why, paths in pools:
        for p in paths:
            for k in keys:
                try:
                    if packs.file_matches(k, p, ""):
                        out.append((p, why))
                        break
                except Exception:
                    continue
    return out


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

    Returns ``(path, tier)`` where tier is ``"exact"``, ``"dehyph"`` or ``"alnum"`` - the
    strongest containment that held - or ``(None, None)``. This is the measured case where a
    statute's declaration clause was compared against an unrelated regulation and flagged for a
    changed operative word, while the file holding the real provision sat on the same disk.

    🔴 R76: the tier is returned because the three containments are NOT one fact. «Exact
    substring of the cited file» supports VERIFIED; an alphanumeric-only containment supports
    at most PUNCTUATION - and the old single-boolean form let ``fold`` print VERIFIED over an
    alnum coincidence (probe CRIT2, named independently by 12 of 17 panel channels).
    """
    n = normalise(quote)
    if len(n) < min_len:
        return None, None
    for path in (addr.get("expected_files") or [])[:10]:
        try:
            t = corpus.text_of(path)
        except (KeyError, ValueError):
            continue
        if n in t:
            return path, "exact"
        if dehyph(n) in dehyph(t):
            return path, "dehyph"
        if alnum(n) in alnum(t):
            return path, "alnum"
    return None, None


def fold(quote, verdict, path, detail, near_cites, corpus, keymap, packs):
    """Fold the address layer into a text verdict. Returns `(verdict, path, detail, address)`.

    🔴 The address is taken from the NEAR ring only (see ``extract.citation_window``). The wide ring
    stays available to the miss classifier, because a neighbour in the same paragraph tells you
    whether the source ought to be downloaded - but it is not this quotation's address, and treating
    it as one produced accusations against innocent documents in the first build of this layer.
    """
    if not path:
        # 🔴 THE MISS THAT IS NOT A MISS. Until 2026-08-03 the address layer was skipped entirely
        # whenever the text was not located - so a quotation of a source the user simply does not
        # have was graded exactly like one the authority never wrote. `NOT_FOUND`'s own meaning
        # string admitted the ambiguity ("either the source is not downloaded, or invented") and
        # the tool had what it needed to resolve it sitting right there: the citation printed
        # beside the quotation.
        #
        # Measured in the sister project on a real filing: 20 of 37 flagged items were quotations
        # of agency press releases and FAQ pages, whose sources are not in a corpus of law by
        # construction. Two thirds of the list was unactionable, and the genuine misses were
        # hiding in it.
        #
        # 🔴 The guard against this becoming an escape hatch is the `ADDRESS_NOT_IN_CORPUS` test,
        # not a softer word. If the cited authority IS on disk and the words are not in it, that is
        # the fabrication shape and the verdict stays `NOT_FOUND` - said louder, not quieter.
        if verdict == "NOT_FOUND" and near_cites:
            a = address_check(near_cites, None, keymap, packs)
            if a["status"] == "ADDRESS_NOT_IN_CORPUS":
                # 🔴 R77 (#354, orgrok420): "not in the corpus" has two causes and the advice
                # differs. The keymap walks INDEXED files only, so a source that IS on disk but
                # was excluded - a bot wall saved as the chapter, a scan with no text layer, an
                # empty download - read as "not downloaded", and the advice said to download a
                # file the user already has. The exclusion lists know the truth; say it.
                excl = _excluded_match(packs.keys(near_cites), keymap.corpus, packs)
                if excl:
                    p, why = excl[0]
                    return ("NO_SOURCE_ON_DISK", None,
                            "not checked: %s resolves to «%s», which IS on disk but was "
                            "EXCLUDED from the corpus as %s. Re-fetch or repair that file - "
                            "downloading it again from the same URL will likely fail the same "
                            "way. This is not a pass" % ("; ".join(a["keys"]),
                                                         os.path.basename(p), why), a)
                return ("NO_SOURCE_ON_DISK", None,
                        "not checked: %s is not in your sources folder. Download it and run again "
                        "- this is not a pass" % "; ".join(a["keys"]), a)
            if a["status"] in ("MISMATCH", "MATCHED"):
                names = a.get("keys") or []
                detail = ("the cited source IS on disk (%s) and these words are not in it%s"
                          % ("; ".join(names), (" - " + detail) if detail else ""))
                return verdict, path, detail, a
        return verdict, path, detail, None
    if not near_cites:
        return verdict, path, detail, {"status": "NO_NEARBY_CITATION", "keys": []}

    addr = address_check(near_cites, path, keymap, packs)
    if addr["status"] != "MISMATCH":
        return verdict, path, detail, addr

    # 🔴 R76 — THE REPAIR MAY NO LONGER BLESS BLINDLY. The old form returned VERIFIED for ANY
    # incoming verdict the moment the text was (even loosely) contained in the cited file. A
    # quotation that stops before its proviso is a SUBSTRING of the full provision, and the same
    # provision is reprinted across files with the same proviso - so the repair was discarding
    # TRUNCATED_CONDITION on the strength of the very containment that truncation guarantees.
    # Probe CRIT2: check=TRUNCATED_CONDITION -> fold=VERIFIED at the cited file. Named
    # independently by 12 of 17 panel channels; kimik3 and ordeepseek added that the repaired
    # path also bypassed the superseded-edition wrapper, which runs inside `check()` on the
    # PRE-fold path only. Now: the completeness questions are re-asked AT the cited file, the
    # edition question is re-asked at the repaired path, a DANGEROUS verdict upgrades only on
    # EXACT containment, and the containment tier caps the verdict it can produce.
    repaired, tier = repair_anchor_miss(quote, addr, corpus)
    if repaired:
        n = normalise(quote)
        matched = {"status": "MATCHED", "matched": "after binding", "keys": addr["keys"]}
        if tier == "exact":
            tp, _lim, ttail = truncated_condition(n, corpus, restrict_to={repaired})
            if tp:
                return ("TRUNCATED_CONDITION", repaired,
                        "at the cited address the source continues: «%s…»" % ttail, matched)
            lp, bad, cut = leading_cut(n, corpus, restrict_to={repaired})
            if lp:
                return ("TRUNCATED_OPENING", repaired,
                        "at the cited address, immediately before it: «…%s» (governing "
                        "words: %s)" % (cut, bad), matched)
        if getattr(corpus, "is_superseded", None) and corpus.is_superseded(repaired):
            return ("SUPERSEDED_EDITION", repaired,
                    "the cited address resolves to «%s», which the law register marks as "
                    "SUPERSEDED - see the revision report" % os.path.basename(repaired), matched)
        if tier != "exact" and verdict not in ADDRESS_CLEAN:
            detail = (detail + " · " if detail else "") + (
                "the words also appear (%s containment only) in the cited «%s» - a loose match "
                "may not clear a %s verdict; read the cited file yourself"
                % (tier, os.path.basename(repaired), verdict))
            return verdict, path, detail, addr
        candidate = {"exact": "VERIFIED", "dehyph": "TYPESETTING", "alnum": "PUNCTUATION"}[tier]
        if verdict != candidate:
            detail = ("%s at the cited address «%s» (%s containment); the global anchor pointed "
                      "at «%s» - the previous verdict %s was an anchor miss"
                      % ("correct" if candidate == "VERIFIED" else "present",
                         os.path.basename(repaired), tier, os.path.basename(path), verdict))
        return candidate, repaired, detail, matched

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
