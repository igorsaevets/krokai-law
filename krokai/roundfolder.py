"""Which files in a review round folder are reviewers' ANSWERS - one home for both readers of it.

🔴 K004 (2026-11-23, measured in K001 S4). Two readers walk the same folder: `consult.absorb_delegated`
grades the answers a delegated harness produced, and `review.audit_answers` checks their quotations.
Each kept its own list of "files that are not answers"; the two lists differed, and neither knew what
the harness writes for ITSELF. ai-second-opinion writes REPORT.md and HANDOFF.md beside the answers -
and, since its R193, PROGRESS.md, with READING.md kept there by the person reading the round - and every
one of them was graded as a reviewer that FAILED. So a round in which nothing failed exited 1. An alarm
that sounds on every clean round teaches its user to ignore it, and raising that alarm is the job.

A longer list alone would not hold: the harness ships on its own schedule, and the next file it adds
would drift the same way, unseen. So when the harness leaves its own record of the round -
`diagnostics.json`, schema `model-orchestration/diagnostics/1` - THAT record decides: it names, per
channel, the file the channel wrote, and only those files are answers. A file it does not claim is
NAMED, never graded and never silently dropped: an unclaimed file is where the next drift shows.
Without such a record (answers pasted in by hand, another harness) every `.md` / `.txt` file is an
answer except the names below.

The reverse direction is the older defect, and it stays closed: a harness that wrote NOTHING must
never read as a clean round (`consult.absorb_delegated` turns that into a FAILED row).
"""
from __future__ import annotations

import io
import json
import os

# krokai's own files in a round folder.
KROKAI_FILES = frozenset({"brief.md", "system.md", "analytics.md"})
# What the harness writes for itself or for the person reading its round - never a reviewer's voice.
# Read from ai-second-opinion v1.125.0 (`write_handoff`'s skip set) and its R193 working tree
# (PROGRESS.md / READING.md), 2026-11-23. `adjudication.md` is the reader's verdict file (R76).
HARNESS_FILES = frozenset({"report.md", "handoff.md", "progress.md", "reading.md",
                           "prompt.md", "agent.md", "adjudication.md"})
NOT_ANSWERS = KROKAI_FILES | HARNESS_FILES
# The harness's own quote check of an answer (its B-9 sidecar): quotations OF an answer, not one.
NOT_ANSWER_SUFFIXES = (".quote-verify.md",)
ANSWER_EXTENSIONS = (".md", ".txt")

RECORD = "diagnostics.json"
# Only a schema this code was written against is trusted. A newer one is said aloud and the folder is
# judged by name instead - guessing at a changed layout is how a contract drifts in silence.
KNOWN_SCHEMAS = ("model-orchestration/diagnostics/1",)
_SCHEMA_FAMILY = "model-orchestration/"


def harness_record(folder, since=None):
    """The harness's own record of THIS round, as `(record, note)`.

    `record` is None when there is none to trust; `note` then says why, when it is worth saying.
    """
    path = os.path.join(folder, RECORD)
    if not os.path.isfile(path):
        return None, ""
    try:
        rec = json.load(io.open(path, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, "%s could not be read (%s) - files are judged by name" % (RECORD, type(exc).__name__)
    schema = rec.get("schema") if isinstance(rec, dict) else None
    if not str(schema or "").startswith(_SCHEMA_FAMILY):
        return None, ""                      # somebody else's diagnostics.json: not ours to read
    try:
        if since and os.path.getmtime(path) < since:
            return None, ("%s is a previous round's record (older than this dispatch) - files are "
                          "judged by name" % RECORD)
    except OSError:
        pass
    if schema not in KNOWN_SCHEMAS:
        return None, ("the harness wrote its record in schema %r, which this krokai does not know - "
                      "files are judged by name; update krokai if this repeats" % schema)
    return rec, ""


def classify(folder, since=None):
    """Sort a round folder into what is graded and what is not, and why.

    Returns a dict:
      answers    [(file, channel)] to grade, in name order
      stale      files older than `since` - a previous round's, never this round's voices
      unclaimed  answer-shaped files the harness's record does not claim: named, not graded
      never_read files of channels the harness marks `never_read` (its operator's rule): not graded
      no_answer  channels the harness ran that left no answer file
      absent     answer files the record claims that are not in the folder
      crashed    the harness's own error text when its record says it crashed, else ""
      note       why the record was not used, or ""
      by_record  True when the harness's record decided
    """
    rec, note = harness_record(folder, since)
    out = {"answers": [], "stale": [], "unclaimed": [], "never_read": [], "no_answer": [],
           "absent": [], "crashed": "", "note": note, "by_record": False}
    if rec is not None and rec.get("crashed"):
        # A crash record has no channel table. Whatever was written before the crash is judged by name.
        out["crashed"] = ("%s: %s" % (rec.get("error_type") or "error", rec.get("error") or "")).strip()
        rec = None
    claimed, attempts, never = {}, set(), set()
    if rec is not None:
        out["by_record"] = True
        for name, r in sorted((rec.get("channels") or {}).items()):
            if not isinstance(r, dict):
                continue
            af = os.path.basename(str(r.get("answer_file") or "").strip())
            # A channel that ran twice keeps its other attempt and a copy of the winner beside the
            # answer (the harness's R154); they are the same voice, and grading them would count it twice.
            more = [str(x) for x in (r.get("attempt_files") or [])]
            if r.get("answer_copy"):
                more.append(str(r["answer_copy"]))
            if r.get("never_read") is True:
                never.update(x.lower() for x in [af] + more if x)
                out["never_read"].append(name)
                continue
            if af:
                claimed[af.lower()] = name
            elif r.get("seconds") is not None:
                out["no_answer"].append(name)
            attempts.update(x.lower() for x in more)
    seen = set()
    for fn in sorted(os.listdir(folder)):
        low = fn.lower()
        if not low.endswith(ANSWER_EXTENSIONS) or low in NOT_ANSWERS or low.endswith(NOT_ANSWER_SUFFIXES):
            continue
        path = os.path.join(folder, fn)
        if not os.path.isfile(path) or low in attempts or low in never:
            continue
        try:
            if since and os.path.getmtime(path) < since:
                out["stale"].append(fn)
                continue
        except OSError:
            continue
        if rec is None:
            out["answers"].append((fn, os.path.splitext(fn)[0].lower()))
        elif low in claimed:
            out["answers"].append((fn, claimed[low]))
            seen.add(low)
        else:
            out["unclaimed"].append(fn)
    out["absent"] = sorted(af for af in claimed if af not in seen
                           and not os.path.isfile(os.path.join(folder, af)))
    return out


def report(c, printer=print):
    """Say what was NOT graded and why. A silently ignored file in an answers folder is how the
    opposite defect starts (R77 #341), so every skip that is not a known name is printed."""
    if c.get("note"):
        printer("  note: %s" % c["note"])
    if c.get("crashed"):
        printer("  🔴 the review harness reports that it CRASHED: %s" % c["crashed"][:300])
    if c.get("stale"):
        printer("  skipped %d file(s) already in the folder BEFORE this dispatch (a previous "
                "round's answers): %s" % (len(c["stale"]), ", ".join(c["stale"])))
    if c.get("never_read"):
        printer("  not graded: the harness marks these channels never_read (its operator's rule): %s"
                % ", ".join(c["never_read"]))
    if c.get("no_answer"):
        printer("  the harness ran %d channel(s) that left no answer: %s - its REPORT.md says why"
                % (len(c["no_answer"]), ", ".join(c["no_answer"])))
    if c.get("absent"):
        printer("  the harness's record names answer file(s) that are not in the folder: %s"
                % ", ".join(c["absent"]))
    if c.get("unclaimed"):
        printer("  🔴 NOT GRADED - the harness's record of this round does not claim %d file(s): %s"
                % (len(c["unclaimed"]), ", ".join(c["unclaimed"])))
        printer("     A harness that started writing a new file of its own looks exactly like this. If one")
        printer("     of them IS an answer, audit it with `krokai review --audit <a folder holding only it>`.")
