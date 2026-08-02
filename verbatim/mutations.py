# -*- coding: utf-8 -*-
"""The mutation bank: measuring how often the checker says "clean" about something that is not.

WHY THIS EXISTS, IN ONE QUOTED SENTENCE
----------------------------------------
From a reviewing model, about the project this toolkit came from:

    *"right now you learn about your gaps from incidents in filings - the most expensive testing
    method that exists."*

That is the whole argument. Every defect class this system has ever paid for is turned here into a
**mutation** applied to quotations the checker already calls clean. A mutant the checker still calls
clean is a hole - found for free, in seconds, instead of by an adjudicator.

It is a regression harness, not a benchmark. The number that matters is not "how good is it" but
"did my last change break something that used to work". Run it after every edit to ``verify.py``.

THE CATALOGUE MIRRORS THE INCIDENT LOG - ONE MUTATION PER PAID-FOR INCIDENT
---------------------------------------------------------------------------
    insert-operator     "shall" -> "shall not"          the 85 %-similarity hole
    drop-negation       a negation removed              the same hole, other direction
    digit               a date or threshold altered     an OCR-shaped corruption
    tail                the last words rewritten        a model that fetched the right page
    cut-condition       cut right before ", but ..."    10 found among already-VERIFIED quotations
    synonym             one word paraphrased            "produces text, not a quotation"
    splice              two quotations welded with ...  an ellipsis joining two authorities
    wrong-address       right words, wrong citation     a decision under another's footnote

🔴 A MUTATION IS "CAUGHT" ONLY IF THE REASON IS RIGHT
------------------------------------------------------
``cut-condition`` counts as caught **only** when the verdict is the truncation verdict itself. Any
other dangerous verdict there is an accident - the tool got the right answer for the wrong reason,
which will not survive the next refactor - and a clean verdict is a hole.
"""
from __future__ import annotations

import re

from .normalize import normalise
from .verify import check
from .verdicts import DANGEROUS

__all__ = ["MUTATIONS", "run"]

_MODAL = re.compile(r"\b(shall|may|must|will|does|do|is|are)\b(?!\s+not)", re.I)
_LIMITER_IN = re.compile(r",\s*(but|except|unless|provided|however)\b", re.I)
_SYNONYMS = [(" apply ", " request "), (" prior to ", " before "), (" alien ", " applicant "),
             (" pursuant to ", " according to "), (" upon ", " on "), (" shall ", " will "),
             (" must ", " has to "), (" may not ", " cannot ")]


def m_insert_operator(q):
    m = _MODAL.search(q)
    return None if not m else q[:m.end()] + " not" + q[m.end():]


def m_drop_negation(q):
    return q.replace(" not ", " ", 1) if " not " in q else None


def m_digit(q):
    for i, ch in enumerate(q):
        if ch.isdigit():
            return q[:i] + str((int(ch) + 5) % 10) + q[i + 1:]
    return None


def m_tail(q):
    w = q.split()
    return None if len(w) < 16 else " ".join(w[:-6]) + " in accordance with applicable law"


def m_cut_condition(q):
    m = _LIMITER_IN.search(q, 45)
    return None if (not m or m.start() < 45) else q[:m.start()].rstrip(" ,;")


def m_synonym(q):
    for a, b in _SYNONYMS:
        if a in q:
            return q.replace(a, b, 1)
    return None


MUTATIONS = [
    ("insert-operator", m_insert_operator, None),
    ("drop-negation", m_drop_negation, None),
    ("digit", m_digit, None),
    ("tail", m_tail, None),
    # The reason must be right, not just the alarm.
    ("cut-condition", m_cut_condition, ("TRUNCATED_CONDITION", "TRUNCATED_OPENING")),
    ("synonym", m_synonym, None),
]

SPLICE_CAUGHT = ("SPLICED", "ELLIPSIS_HIDES", "ALTERED", "FOUND_ELSEWHERE")


def run(verified_quotes, corpus, limit=60, printer=print):
    """`verified_quotes` is `[(quote, source_path), ...]` the checker already called clean.

    Returns `(stats, rows)`.
    """
    base = []
    for q, where in verified_quotes:
        if not where or not (60 <= len(q) <= 420) or len(q.split()) < 12:
            continue
        if "..." in q or "…" in q:
            continue                       # a mutant of an ellipsis quotation tests two things
        base.append((q, where))
    base = base[:limit]
    printer("mutation bank: %d base quotations" % len(base))

    stats = {name: {"applicable": 0, "caught": 0, "missed": 0, "examples": []}
             for name, _fn, _ok in MUTATIONS}
    stats["splice"] = {"applicable": 0, "caught": 0, "missed": 0, "examples": []}
    rows = []

    for i, (q, where) in enumerate(base):
        for name, fn, must_be in MUTATIONS:
            mq = fn(q)
            if not mq or normalise(mq).lower() == normalise(q).lower():
                continue
            verdict, _p, detail = check(mq, corpus)
            s = stats[name]
            s["applicable"] += 1
            ok = (verdict in must_be) if must_be else (verdict in DANGEROUS)
            if ok:
                s["caught"] += 1
            else:
                s["missed"] += 1
                if len(s["examples"]) < 3:
                    s["examples"].append({"got": verdict, "mutant": mq[:160], "base": q[:120]})
            rows.append({"mutation": name, "verdict": verdict, "caught": bool(ok),
                         "detail": (detail or "")[:160]})

        # Splice: this quotation welded to one from a DIFFERENT file. Same-file would be a
        # legitimate ellipsis quotation, which is exactly what must NOT be flagged.
        for q2, w2 in base[i + 1: i + 6]:
            if w2 != where:
                mq = q + " ... " + q2
                verdict, _p, _d = check(mq, corpus)
                s = stats["splice"]
                s["applicable"] += 1
                ok = verdict in SPLICE_CAUGHT
                s["caught" if ok else "missed"] += 1
                if not ok and len(s["examples"]) < 3:
                    s["examples"].append({"got": verdict, "mutant": mq[:160]})
                rows.append({"mutation": "splice", "verdict": verdict, "caught": bool(ok)})
                break

    total = sum(s["applicable"] for s in stats.values())
    missed = sum(s["missed"] for s in stats.values())
    printer("\n%-18s %6s %8s %6s %10s" % ("mutation", "made", "caught", "holes", "catch rate"))
    for name, s in stats.items():
        rate = (100.0 * s["caught"] / s["applicable"]) if s["applicable"] else 0.0
        printer("%-18s %6d %8d %6d %9.0f%%"
                % (name, s["applicable"], s["caught"], s["missed"], rate))
    printer("\nFALSE-CLEAN RATE: %d of %d mutants (%.1f%%) were called harmless"
            % (missed, total, 100.0 * missed / max(total, 1)))
    if missed:
        printer("Each one is a hole found for free. Read the examples before shipping a change.")
    return stats, rows
