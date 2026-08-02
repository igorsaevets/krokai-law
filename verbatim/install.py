# -*- coding: utf-8 -*-
"""Wiring the hooks into Claude Code's settings.json, without destroying what is already there.

WHY THIS IS A PROGRAM AND NOT A PARAGRAPH OF INSTRUCTIONS
----------------------------------------------------------
Because "add this block to your settings.json" is how people end up with a broken settings.json,
and because the hooks are the part that makes the rest work without anybody remembering anything.
A toolkit whose central mechanism requires a manual JSON edit will be installed with the mechanism
missing.

THREE RULES THIS FILE OBEYS
---------------------------
1. **Merge, never replace.** Other hooks in that file belong to the user and may be load-bearing -
   a secret scanner, an answer archiver. Clobbering them to install a citation checker would be an
   unusually poor trade. Existing entries are read, ours are added, everything else is left alone.

2. **Idempotent.** Running it twice must not produce two copies. Ours are recognised by the marker
   in the command path, not by position.

3. **Back up first, print the diff, and support `--dry-run`.** Editing another program's
   configuration is not a step to take silently.

🔴 A NOTE THAT SAVES A CONFUSED HALF-HOUR
-------------------------------------------
`settings.json` is read when a session **starts**. A freshly installed hook does nothing in the
session that installed it. Measured the hard way; it is printed at the end of every run.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys
import time

MARKER = "verbatim"

EVENTS = [
    ("PostToolUse", "Edit|Write|NotebookEdit|MultiEdit", "quote_guard.py", 20,
     "catches a long quotation entering a filed document that is not in the quote bank"),
    ("Stop", None, "bank_queue.py", 90,
     "queues every quotation of law from the answer that is not yet banked"),
    ("SessionStart", None, "session_anchor.py", 15,
     "states the queue, index and sidecar status at the start of a session"),
]


def _settings_path(scope, project_dir):
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    return os.path.join(os.path.abspath(project_dir or "."), ".claude", "settings.json")


def _hook_entry(python, script, timeout):
    return {"type": "command", "command": python, "args": [script], "timeout": timeout}


def _is_ours(entry, hooks_dir):
    cmd = " ".join([str(entry.get("command") or "")] + [str(x) for x in entry.get("args") or []])
    return MARKER in cmd.replace("\\", "/").lower() or os.path.basename(
        str((entry.get("args") or [""])[0])) in {e[2] for e in EVENTS}


def build_block(hooks_dir, python):
    out = {}
    for event, matcher, script, timeout, _why in EVENTS:
        entry = _hook_entry(python, os.path.join(hooks_dir, script), timeout)
        group = {"hooks": [entry]}
        if matcher:
            group["matcher"] = matcher
        out.setdefault(event, []).append(group)
    return out


def merge(existing, block, hooks_dir, remove=False):
    """Return `(new_settings, added, removed)`."""
    settings = json.loads(json.dumps(existing or {}))
    hooks = settings.setdefault("hooks", {})
    added, removed = [], []

    for event, groups in block.items():
        current = hooks.setdefault(event, [])
        # Drop any of ours that are already present - that is what makes this idempotent, and what
        # makes --uninstall exact.
        cleaned = []
        for g in current:
            keep = [h for h in (g.get("hooks") or []) if not _is_ours(h, hooks_dir)]
            if len(keep) != len(g.get("hooks") or []):
                removed.append(event)
            if keep:
                g = dict(g)
                g["hooks"] = keep
                cleaned.append(g)
            elif not g.get("hooks"):
                cleaned.append(g)
        hooks[event] = cleaned
        if not remove:
            for g in groups:
                hooks[event].append(g)
                added.append(event)
        if not hooks[event]:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    return settings, added, removed


def main(a):
    hooks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
    if not os.path.isdir(hooks_dir):
        print("hooks folder not found next to the package: %s" % hooks_dir)
        return 2

    python = sys.executable or "python"
    path = _settings_path(a.scope, getattr(a, "dir", None))
    existing = {}
    if os.path.exists(path):
        try:
            existing = json.load(io.open(path, encoding="utf-8"))
        except ValueError as exc:
            print("🔴 %s is not valid JSON (%s)." % (path, exc))
            print("   Refusing to touch it - a rewrite here would lose whatever is in it.")
            return 2

    block = build_block(hooks_dir, python)
    new, added, removed = merge(existing, block, hooks_dir, remove=a.uninstall)

    print("settings file : %s" % path)
    print("python        : %s" % python)
    print("hooks folder  : %s" % hooks_dir)
    print()
    for event, matcher, script, timeout, why in EVENTS:
        verb = "REMOVE" if a.uninstall else "add"
        print("  %-6s %-13s %-22s %s" % (verb, event, script, why))
    other = sum(len(g.get("hooks") or []) for ev, gs in (existing.get("hooks") or {}).items()
                for g in gs if not any(_is_ours(h, hooks_dir) for h in (g.get("hooks") or [])))
    if other:
        print("\n  %d hook(s) belonging to something else are present and are left untouched."
              % other)

    if a.dry_run:
        print("\n--dry-run: nothing was written. The file would become:\n")
        print(json.dumps(new, ensure_ascii=False, indent=2)[:4000])
        return 0

    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        backup = path + ".backup-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, backup)
        print("\nbackup        : %s" % backup)
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(new, ensure_ascii=False, indent=2) + "\n")

    print("written.")
    if a.uninstall:
        print("removed %d hook registration(s)." % len(removed))
    else:
        print("registered %d hook(s)." % len(added))
    print("""
🔴 settings.json is read when a SESSION STARTS. These hooks do nothing in the session that
   installed them. Start a new session, then confirm with:

       python -m verbatim doctor
""")
    return 0
