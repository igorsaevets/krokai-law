# -*- coding: utf-8 -*-
"""Shared start-up for every hook. Imported by path, so it does its own sys.path work.

🔴 FORCE UTF-8 ON STDERR BEFORE ANYTHING ELSE.
Without it, a hook's message goes out in the console's legacy code page on Windows and arrives as
mojibake - which means the warning about an unverified quotation is unreadable at precisely the
moment it matters. Caught on the very first test run of the first hook.

🔴🔴 AND ON STDIN - WHICH IS THE ONE THIS FILE FORGOT, FOR AN INSTRUCTIVE REASON.
The paragraph above was written on day one because mojibake on the way OUT is visible: you run the
hook, you see nonsense, you fix it. The identical defect on the way IN is invisible, and it stayed
in the shipped code until it was measured on 2026-08-05.

The harness writes the event as UTF-8 bytes. `sys.stdin` on Windows decodes in the console code
page (`cp1251` on the machine this was measured on, `cp1252` on a default US install). Those are
single-byte codecs: they never raise, so the JSON still parses and the hook still exits 0. What
changes is every non-ASCII character in it. A left double quotation mark - U+201C, which is what a
model emits and what every scraped source contains - arrives as three mojibake characters, and the
quotation extractor, which looks for that character, finds nothing.

Measured, one variable at a time, same payload:

    UTF-8 bytes, console page cp1251        -> exit 0, SILENT      (what the harness actually sends)
    the same bytes with PYTHONIOENCODING    -> exit 2, fires
    an ASCII path and an ASCII matter, but
      curly quotes in the QUOTATION         -> exit 0, SILENT

So the trigger is not an exotic path. It is a typographic quotation mark, and the guard was dead for
any user whose console is not UTF-8. Two states - "nothing to report" and "dead" - both look like
nothing, which is why `quote_guard` now also keeps a log.

The fix reads the raw bytes and decodes them explicitly rather than reconfiguring the stream:
`reconfigure()` is a no-op once a read has begun and can fail on a redirected handle, while
`stdin.buffer` is what the bytes are actually in.
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
    worse than no hook, because it takes the turn down with it.

    🔴 BYTES, then an explicit UTF-8 decode. See the module docstring: reading `sys.stdin` as text
    hands the console code page a UTF-8 payload, which does not fail - it silently mangles every
    non-ASCII character and the hook then finds nothing to report.
    """
    import json
    raw = ""
    try:
        if sys.stdin.isatty():
            return {}
        buf = getattr(sys.stdin, "buffer", None)
        if buf is not None:
            raw = buf.read().decode("utf-8", "replace")
        else:
            raw = sys.stdin.read()          # a stream with no binary side: nothing better available
    except Exception:
        return {}
    try:
        return json.loads(raw or "{}")
    except ValueError:
        return {}


def find_config(start=None):
    from krokai.config import load
    try:
        return load(start or os.getcwd(), required=False)
    except SystemExit:
        return None
