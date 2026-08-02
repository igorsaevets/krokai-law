# -*- coding: utf-8 -*-
"""Stop hook: no quotation of law found in an answer is lost between rounds.

THE MEASUREMENT
---------------
Across one working transcript: **16 turns produced long quotations of law and made zero entries in
the quote bank in the same turn.** 142 raw candidates, 108 after removing the assistant's own prose
and channel telemetry. The worst single turn: **65 quotations, none banked.**

Running those 108 through the checker afterwards:

    verified 33 · assembled 20 · NOT FOUND 21 · altered 15 · operator 8 · truncated-condition 2

Twenty-one quotations of law had been used in reasoning and were **not in any source on disk**.
Some were missing downloads. Some were not.

The cause was not forgetfulness. Banking was an *instruction*, and an instruction fires by topic -
see the long note in ``quote_guard.py``. The same profile, same transcript: the checker ran in one
stretch of answers and zero times in the rounds either side of it.

A hook is executed by the harness. It runs whatever the round was about.

WHY A QUEUE AND NOT STRAIGHT INTO THE BANK
-------------------------------------------
The bank is a **decision**: this quotation matters to the matter, here is its address, here is what
it does not prove. A person makes that call. Automatic entry would turn the bank into a dump of a
hundred-odd rows in which the four that matter are invisible - and an unreadable bank is an unopened
bank.

The queue asks the question. The bank stores the answer. ``lawverbatim close`` refuses to call the
round finished while the queue has open items, which is the other half: a file nobody is obliged to
open gets read exactly as often as an instruction gets obeyed.

WHY IT NEVER BLOCKS
-------------------
A Stop hook returning exit 2 prevents the turn from ending and can loop. This one always exits 0.

THIS IS NOT AUTOMATED MONITORING. It contacts nothing and watches no external state; it reads output
that is already on this disk.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _bootstrap import bootstrap, read_event, find_config      # noqa: E402

bootstrap()

MAX_CHECK = 40           # per turn: protects against both a wall of text and a slow hook
LOG_KEEP = 200


def log(cfg, line):
    row = "%s  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), line)
    if "--verbose" in sys.argv:
        print(row)
    if cfg is None:
        return
    p = os.path.join(cfg.root, ".lawverbatim", "bank_queue.log")
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        old = io.open(p, encoding="utf-8").read().splitlines() if os.path.exists(p) else []
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            "\n".join((old + [row])[-LOG_KEEP:]) + "\n")
    except OSError:
        pass


def last_answer(transcript):
    """The text of the LAST answer: the tail of text events with no tool call after them.

    The signal is deliberately the same one the answer archiver uses - after the last tool call the
    assistant is no longer doing, it is writing. Two copies of this logic would diverge within a
    month, so there is one and it is documented in both places.
    """
    events = []
    try:
        fh = io.open(transcript, encoding="utf-8", errors="replace")
    except OSError:
        return ""
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("isSidechain") or rec.get("type") != "assistant":
                continue
            for b in (rec.get("message") or {}).get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    events.append(("t", b.get("text") or ""))
                elif b.get("type") == "tool_use":
                    events.append(("u", ""))
    cut = len(events)
    for i in range(len(events) - 1, -1, -1):
        if events[i][0] == "u":
            break
        cut = i
    return "\n".join(t for k, t in events[cut:] if k == "t")


def main():
    ev = read_event()
    cfg = find_config()
    if cfg is None:
        return 0

    tr = ev.get("transcript_path") or ""
    if "--last" in sys.argv and not tr:
        log(cfg, "no transcript_path and --last given with none: nothing to do")
        return 0
    if not tr or not os.path.exists(tr):
        log(cfg, "no transcript_path - skipped")
        return 0

    text = last_answer(tr)
    if not text.strip():
        log(cfg, "empty answer - skipped")
        return 0

    from lawverbatim.bank import candidates, read_bank, in_bank, append_queue

    cands = candidates(text)
    if not cands:
        log(cfg, "no legal quotations in this answer")
        return 0

    bank = read_bank(cfg.abs(cfg["bank"]))
    fresh = [q for q in cands if not in_bank(q, bank)]
    if not fresh:
        log(cfg, "all %d quotation(s) already banked" % len(cands))
        return 0

    dropped = max(0, len(fresh) - MAX_CHECK)
    fresh = fresh[:MAX_CHECK]

    rows = []
    try:
        from lawverbatim.corpus import Corpus
        from lawverbatim.verify import check
        corpus = Corpus(cfg.source_dirs, skip_dirs=set(cfg["skip_dirs"]),
                        cache_dir=cfg.cache, quiet=True)
        for q in fresh:
            try:
                verdict, where, detail = check(q, corpus)
            except Exception:
                verdict, where, detail = "ERROR", None, ""
            rows.append((q, verdict, os.path.basename(where) if where else "—", detail))
    except Exception as exc:
        log(cfg, "corpus unavailable (%s) - queue written without verdicts" % type(exc).__name__)
        rows = [(q, "NOT CHECKED", "—", "") for q in fresh]

    n = append_queue(cfg.abs(cfg["queue"]), rows, dropped=dropped, cap=MAX_CHECK)
    log(cfg, "queued %d (candidates %d, dropped by cap %d)" % (n, len(cands), dropped))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        try:
            log(None, "EXCEPTION %s: %s" % (type(exc).__name__, exc))
        except Exception:
            pass
        sys.exit(0)
