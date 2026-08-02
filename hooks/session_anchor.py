# -*- coding: utf-8 -*-
"""SessionStart hook: put the state of the matter in front of the assistant before it acts.

WHY THIS EXISTS
---------------
An audit of a live legal project found there was **no SessionStart hook at all**: nothing met the
assistant at the beginning of a session, so everything that had to happen "on entry" lived in an
instructions file - that is, it was *context*, not a *mechanism*, and context loses to the current
task (see ``quote_guard.py``).

WHAT IT SAYS, AND WHAT IT CAREFULLY DOES NOT
---------------------------------------------
🔴 It emits **facts, not orders**. "The queue has 4 open items" is a fact. "You must clear the
queue" is an instruction arriving from a file the user did not write in this session, and an
assistant that is properly wary of injected instructions is right to discount it. Facts do not
trigger that defence and are more useful anyway: a competent reader knows what an open queue means.

It also states what it did NOT check, because a status line that reports only good news is read as
an all-clear.

ALWAYS SAFE: prints a JSON object on stdout, exits 0, and any internal error yields silence.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import bootstrap, find_config      # noqa: E402

bootstrap()


def main():
    cfg = find_config()
    if cfg is None:
        return 0

    from verbatim.bank import queue_open_items, read_bank
    from verbatim.library import orphans
    from verbatim.corpus import walk
    from verbatim.sidecar import SUFFIX

    lines = ["Facts about this matter, from `verbatim` at session start:"]

    bank = read_bank(cfg.abs(cfg["bank"]))
    entries = bank.count("\n### ")
    todo = bank.count("TO DO")
    lines.append("- Quote bank: %d entr%s%s. It holds only quotations someone has personally "
                 "opened in the source." % (entries, "y" if entries == 1 else "ies",
                                            ", %d unfinished" % todo if todo else ""))

    op, done, items = queue_open_items(cfg.abs(cfg["queue"]))
    if op:
        lines.append("- Quote queue: **%d open item(s)**, %d closed. Each is a quotation that "
                     "appeared in an answer and is not in the bank; a decision is owed on each."
                     % (op, done))
    else:
        lines.append("- Quote queue: empty.")

    try:
        unindexed, missing = orphans(cfg.source_dirs, cfg.abs(cfg["library_index"]))
        if unindexed or missing:
            lines.append("- Library index: %d file(s) on disk but unindexed, %d index row(s) whose "
                         "file is gone. An unindexed source is downloaded again next round, and its "
                         "absence turns an honest quotation into a NOT_FOUND."
                         % (len(unindexed), len(missing)))
    except Exception:
        pass

    try:
        pdfs = list(walk(cfg.source_dirs, (".pdf",), set(cfg["skip_dirs"])))
        without = [p for p in pdfs if not os.path.exists(p[:-4] + SUFFIX)]
        if without:
            lines.append("- **%d of %d PDFs have no text sidecar.** Grep and file search do not "
                         "read PDFs, so a search that finds nothing in those is a false negative, "
                         "not evidence of absence. `python -m verbatim sidecar` fixes it."
                         % (len(without), len(pdfs)))
    except Exception:
        pass

    lines += [
        "- The corpus is a set of downloads and can be silently incomplete. A checker flag can mean "
        "the CORPUS is wrong rather than the quotation - measured on a scraped agency chapter that "
        "held four of its six bullet points.",
        "- `NOT_FOUND` is not `INVENTED`. Rule out, in order: incomplete corpus → broken extraction "
        "→ your own normalisation → and only then the quotation.",
        "- Not checked here: whether any rule is still in force today, and whether any quotation is "
        "apt. This hook reads local files only.",
    ]

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
