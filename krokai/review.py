# -*- coding: utf-8 -*-
"""Sending work to outside reviewers, and checking what they send back.

WHAT THIS IS AND IS NOT
-----------------------
It is **not** another multi-model orchestration harness. One already exists, it is separately
published, and duplicating it would create the exact defect this project keeps finding: two files on
one subject, of which the one that is only *read* rots first and silently, because the one that is
*executed* gets corrected by failure and the other has no error signal.

So this module does the three things the orchestration harness cannot do, and delegates the rest:

1. **Before** — build the brief with the citation rules, screen it for anchoring, and run the
   outbound gate.
2. **Delegate** — hand the brief to whatever review harness is installed, or print exactly what to
   do by hand if none is.
3. 🔴 **After — the part that is the whole point.** Take every quotation out of every reviewer's
   answer and check it against your own corpus.

WHY STEP 3 IS THE POINT
-----------------------
A reviewer's answer is *input*, not evidence. Measured, repeatedly:

* A channel produced a quotation, both neighbouring sentences, and an `[OPENED]` provenance tag —
  and had invented all three.
* A quotation carried a genuine `[OPENED]` tag from the most expensive channel available. Opening
  the page by hand showed that **one of its three sentences was not on the page at all** — and it
  had already been republished by then.
* Two channels returned the same pincite and two *different* "verbatim" texts. One was quoting the
  decision; the other was quoting a later decision's paraphrase of it. Filed under the first
  pincite, that would have been another authority's words under this authority's address.

Provenance tags are worth requiring - they measurably make channels honest about uncertainty - but
they are a **courtesy, not a control**. The control is this: run the answers through the same checker
you run your own drafts through, and treat a reviewer's quotation exactly as sceptically.

🔴 The reviewers' answers then live in tier D or in `research/`, never in `law/`. A reviewer's
invented quotation stored as a source would validate itself on the next pass.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys

from .extract import extract_quotes
from .prompts import build_brief, anchor_warnings, RESEARCH_SYSTEM, CANARY_NOTE
from .verdicts import CLEAN, label, meaning

__all__ = ["find_harness", "prepare", "audit_answers"]

# Where a published review harness is usually installed. Probed, never assumed - and its absence is
# reported as "not installed here", never as "does not exist".
HARNESS_CANDIDATES = [
    os.path.join(os.path.expanduser("~"), ".claude", "skills", "model-orchestration",
                 "orchestrate.py"),
    os.path.join(os.path.expanduser("~"), "ai-second-opinion", "orchestrate.py"),
    os.path.join(os.path.expanduser("~"), "tools", "ai-second-opinion", "orchestrate.py"),
]


def find_harness(explicit=None):
    if explicit:
        return explicit if os.path.exists(explicit) else None
    env = os.environ.get("KROKAI_REVIEW_HARNESS")
    if env and os.path.exists(env):
        return env
    for p in HARNESS_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def prepare(question, material="", out_dir=".", marker="REVIEW-COMPLETE",
            tools=True, canary=False, allow_pii=False, printer=print):
    """Build the brief, screen it, gate it. Returns `(brief_path, system_path)` or `None`."""
    from .redact import gate

    os.makedirs(out_dir, exist_ok=True)
    brief = build_brief(question, material, marker=marker, tools=tools,
                        canary=CANARY_NOTE if canary else None)

    warns = anchor_warnings(question)
    if warns:
        printer("🔴 ANCHORING in the question. Fix it before spending anything:\n")
        for why, frag in warns:
            printer("   %s" % why)
            if frag:
                printer("      …%s…" % frag)
        printer("")
        printer("   Agreement between reviewers is NOT confirmation when you wrote the question.")
        printer("   Measured: a question carrying a fragment of its own expected answer got five")
        printer("   channels to return the asker's mistake, and it read as strong consensus.")
        printer("")

    # 🔴 The gate runs on the brief AND the system prompt, before anything is sent. Sending is
    # publishing: what remains reaches the vendor, its logs, and your own transcript on disk.
    rc = gate([("brief", brief), ("system", RESEARCH_SYSTEM)], allow_pii=allow_pii, printer=printer)
    if rc:
        return None

    bp = os.path.join(out_dir, "brief.md")
    sp = os.path.join(out_dir, "system.md")
    io.open(bp, "w", encoding="utf-8", newline="\n").write(brief)
    io.open(sp, "w", encoding="utf-8", newline="\n").write(RESEARCH_SYSTEM)
    printer("brief  -> %s (%d chars)" % (bp, len(brief)))
    printer("system -> %s" % sp)
    printer("")
    printer("🔴 Send this brief BYTE-IDENTICAL to every reviewer. A different brief destroys the")
    printer("   comparison the exercise exists for: when two reviewers disagree you must be able to")
    printer("   say the disagreement is about the law and not about what you asked.")
    return bp, sp


def run_harness(harness, brief_path, system_path, out_dir, extra=(), printer=print):
    """Delegate. Absence is reported as 'not installed here', never as 'does not exist'."""
    if not harness:
        printer("""
No review harness found on this machine. That is a statement about this machine, not about the
world - set KROKAI_REVIEW_HARNESS to yours, or do it by hand:

  1. Open each reviewer you use.
  2. Paste system.md as the system prompt, brief.md as the message. BYTE-IDENTICAL to each.
  3. Save each answer as <name>.md in the output folder.
  4. Then run:  krokai review --audit <folder>

Step 4 is the one that matters. Everything before it is transport.""")
        return 1
    cmd = [sys.executable, harness, "--brief", brief_path, "--system", system_path,
           "--out", out_dir] + list(extra)
    printer("running: %s" % " ".join(cmd))
    try:
        return subprocess.call(cmd)
    except Exception as exc:
        printer("could not run the harness: %r" % (exc,))
        return 1


def audit_answers(answers_dir, corpus, packs, min_len=45, printer=print):
    """🔴 The step the orchestration harness cannot do: check the reviewers' quotations.

    Returns `[(file, verdict, quote, detail), ...]`, worst first.
    """
    from .verify import check

    rows = []
    for fn in sorted(os.listdir(answers_dir)):
        if not fn.lower().endswith((".md", ".txt")) or fn in ("brief.md", "system.md"):
            continue
        path = os.path.join(answers_dir, fn)
        body = io.open(path, encoding="utf-8", errors="replace").read()
        for q in extract_quotes(body, min_len):
            verdict, where, detail = check(q, corpus)
            rows.append((fn, verdict, q, detail,
                         os.path.basename(where) if where else ""))

    order = {v: i for i, v in enumerate(
        ["NOT_FOUND", "OPERATOR", "TRUNCATED_CONDITION", "TRUNCATED_OPENING", "SPLICED",
         "ELLIPSIS_HIDES", "ALTERED", "PARTIAL", "SCATTERED", "WRONG_SPEAKER",
         "PUNCTUATION", "TYPESETTING", "ASSEMBLED", "VERIFIED"])}
    rows.sort(key=lambda r: order.get(r[1], 99))

    by_file = {}
    for fn, verdict, _q, _d, _w in rows:
        s = by_file.setdefault(fn, {"total": 0, "clean": 0})
        s["total"] += 1
        s["clean"] += 1 if verdict in CLEAN else 0

    printer("\n%-22s %8s %8s   %s" % ("reviewer", "quotes", "in source", "note"))
    for fn, s in sorted(by_file.items()):
        note = ""
        if s["total"] and s["clean"] == 0:
            note = "🔴 not one quotation is in your corpus - check the corpus before the reviewer"
        elif s["total"] - s["clean"] > s["total"] * 0.3:
            note = "🔴 read every flagged one before repeating anything from this answer"
        printer("%-22s %8d %8d   %s" % (fn, s["total"], s["clean"], note))

    bad = [r for r in rows if r[1] not in CLEAN]
    if bad:
        printer("\n%d quotation(s) from reviewers need a human:\n" % len(bad))
        for fn, verdict, q, detail, where in bad[:40]:
            printer("  [%s] %s" % (label(verdict), fn))
            printer("      %s" % meaning(verdict))
            printer("      > %s%s" % (q[:150], "…" if len(q) > 150 else ""))
            if detail:
                printer("      %s" % detail[:200])
            if where:
                printer("      found in: %s" % where)
            printer("")
        if len(bad) > 40:
            printer("  … and %d more" % (len(bad) - 40))

    printer("🔴 A quotation absent from YOUR corpus is not proof of fabrication - you may simply not")
    printer("   have downloaded that source. It IS proof that you cannot repeat it yet.")
    return rows
