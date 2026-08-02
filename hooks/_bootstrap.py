# -*- coding: utf-8 -*-
"""Shared start-up for every hook. Imported by path, so it does its own sys.path work.

🔴 FORCE UTF-8 ON STDERR BEFORE ANYTHING ELSE.
Without it, a hook's message goes out in the console's legacy code page on Windows and arrives as
mojibake - which means the warning about an unverified quotation is unreadable at precisely the
moment it matters. Caught on the very first test run of the first hook.
"""
from __future__ import annotations

import os
import sys


def bootstrap():
    """Put the repository root on sys.path and make both streams UTF-8. Returns the root."""
    for stream in (sys.stderr, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    return root


def read_event():
    """The hook payload on stdin, or `{}`. Never raises: a hook that dies on malformed input is
    worse than no hook, because it takes the turn down with it."""
    import json
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
    except Exception:
        return {}
    try:
        return json.loads(raw or "{}")
    except ValueError:
        return {}


def find_config(start=None):
    from lawverbatim.config import load
    try:
        return load(start or os.getcwd(), required=False)
    except SystemExit:
        return None
