# -*- coding: utf-8 -*-
"""PostToolUse hook: catch an unverified quotation of law at the moment it enters a document.

🔴 WHY A HOOK AND NOT A RULE IN THE INSTRUCTIONS FILE
------------------------------------------------------
This is the single most important design finding in the whole toolkit, and it was measured, not
reasoned.

An instruction file said, in bold, "check every quotation as it is entered". The verification
script was run in answers 34 through 50 - and **zero times** in three consecutive rounds that
followed, although those rounds produced new quotations. The library index carried an equally
emphatic "look here before searching the web" and was opened **zero times** in the same rounds.

The distribution tells you why. All of it worked while the *task itself* was about verification.
The moment the task became strategy, all of it went silent.

    **Rules fire by TOPIC, not by rule.**

An instruction is text competing for attention with the current task. When the task *is* the rule,
the rule wins; when the task is something else, it loses. Discipline that is needed as background
had been implemented as foreground.

A hook is executed by the harness, not by the model. Topic cannot influence it.

Measured cost of not having it: **16 turns produced legal quotations and made zero bank entries.**
The worst single turn produced 65 quotations and banked none.

WHAT IT DOES
------------
After every Edit/Write, if the edit touched a document that gets filed AND added a long quoted span
in the language of the law that is not in the quote bank, it returns exit 2 and writes to stderr.
The text goes back to the model.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
* **It does not block.** PostToolUse cannot block usefully here anyway - the file is already
  written - and blocking would be wrong: the quotation has to be written down before it can be
  checked. This is a correction loop, not a gate.
* **It does not run the checker itself.** Six or seven seconds on every edit is a tax on every
  edit, and most edits have nothing to do with quotations. The hook reminds and shows exactly what
  to check.
* **It ignores research folders, scratch and archives.** A guard that fires on drafts becomes noise,
  and noise is how a guard gets ignored - which is the same as not having one.
* **It never repeats itself.** A span it has already raised is remembered, so the same string does
  not resurface on every subsequent edit to the file.

ALWAYS SAFE: any internal error exits 0 and says nothing. A hook that takes down a turn is worse
than a missing hook.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import bootstrap, read_event, find_config      # noqa: E402

bootstrap()

SEEN = os.path.join(tempfile.gettempdir(), "verbatim-quote-guard-seen.json")


def main():
    ev = read_event()
    if (ev.get("tool_name") or "") not in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return 0
    inp = ev.get("tool_input") or {}
    path = str(inp.get("file_path") or "")
    if not path:
        return 0

    cfg = find_config(os.path.dirname(path) or None)
    if cfg is None:
        return 0

    from verbatim.bank import candidates, read_bank, in_bank

    rel = os.path.relpath(os.path.abspath(path), cfg.root).replace("\\", "/").lower()
    if any(rel.startswith(x.lower().rstrip("/") + "/") or rel == x.lower()
           for x in cfg.get("guard_ignore", [])):
        return 0
    watch = [w.lower().rstrip("/") for w in cfg.get("guard_watch", [])]
    bank_rel = (cfg["bank"] or "").replace("\\", "/").lower()
    if not any(rel.startswith(w + "/") or rel == w for w in watch) and rel != bank_rel:
        return 0

    added = str(inp.get("new_string") or inp.get("content") or "")
    if not added and inp.get("edits"):
        added = "\n".join(str(e.get("new_string") or "") for e in inp["edits"])
    if not added:
        return 0

    found = candidates(added, min_len=60)
    if not found:
        return 0

    bank = read_bank(cfg.abs(cfg["bank"]))
    fresh = [q for q in found if not in_bank(q, bank)]
    if not fresh:
        return 0

    try:
        seen = set(json.load(io.open(SEEN, encoding="utf-8")))
    except Exception:
        seen = set()
    keys = [hashlib.md5(q.encode("utf-8")).hexdigest() for q in fresh]
    new = [(k, q) for k, q in zip(keys, fresh) if k not in seen]
    if not new:
        return 0
    try:
        json.dump(sorted(seen | {k for k, _ in new}), io.open(SEEN, "w", encoding="utf-8"))
    except Exception:
        pass

    msg = [
        "🔴 QUOTE GUARD - a long quotation was added to a document that gets filed, and it is NOT",
        "   in the quote bank.  File: %s" % os.path.relpath(path, cfg.root),
        "",
    ]
    for _k, q in new[:3]:
        msg.append("   « %s%s »" % (q[:160], "…" if len(q) > 160 else ""))
    if len(new) > 3:
        msg.append("   …and %d more" % (len(new) - 3))
    msg += [
        "",
        "   Check it NOW, not at the end of the round - and check THREE things, not one:",
        "     (a) is the phrase in the source at all;",
        "     (b) is the ADDRESS beside it correct;",
        "     (c) 🔴 was a CONDITION cut off (If / Where / Unless / provided that / but).",
        "",
        "     python -m verbatim check --only \"%s\"" % os.path.basename(path),
        "",
        "   If the source is not on disk, download it into the library and add its index line",
        "   FIRST - otherwise the verdict will be NOT_FOUND through the library's fault rather",
        "   than the quotation's. Measured: 2 of 8 bank entries failed for exactly that reason.",
        "",
        "   Then bank it: verbatim · address · where on disk · how to re-check ·",
        "   WHAT IT DOES NOT PROVE.",
    ]
    sys.stderr.write("\n".join(msg) + "\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)          # a hook never takes down a turn
