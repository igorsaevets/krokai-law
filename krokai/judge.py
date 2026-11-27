# -*- coding: utf-8 -*-
"""K061b (2026-11-27): the judge pass - opt-in, and it changes nothing but an order.

`krokai check --judge <channel>` asks ONE outside model, through an HTTP channel of channels.json, to read each
clean quotation of the filed documents against the source passage READING-LIST.md shows, and puts the quotations
it doubts first in part 2 of that list. Nothing else changes.

🔴 WHY A MODEL AT ALL. The reading list orders part 2 by plain facts (a limiter next to the words, words left out,
no citation ...). Facts about the QUOTATION are the same for a faithful sentence and an overstated one built on it:
on K061's 20 known pairs (law text, a supported sentence and a defective one per quotation) they separated none,
while a cheap model given the sentence and the passage flagged all 20 defects - overstatement, a dropped condition,
an exception that covers the sentence's own facts - at about $0.0002-0.0004 and 3-5 s per quotation, effort LOW
(the top effort flagged the same items at 2-2.5x the price; a «find the flaw» framing raised the false alarms to
7-11 of 20). With the passage withheld the same models flagged 0-1 of 20: they read the passage.

🔴 WHY ONLY THE ORDER. The same model also flagged 4-5 of K061's 20 sound sentences, and nobody has measured how
many sentences of real drafting it doubts. Shown beside a row, its label or its reason is advice, and advice gets
followed: Jain et al. (arXiv 2510.26518 v2, 2026) - people checking AI fact verdicts did best when shown only the
evidence, while the AI's label and explanation led to over-reliance (reading.py says more). So the model's answer
moves a quotation up and is then dropped: no label, no reason, no «cleared» anywhere - a quotation it did not doubt
is exactly as unread as before. Every doubt on a sound sentence pushes a real defect one place down; that is the
price of the order, and the reason the pass is off unless asked for.

🔴 WHAT LEAVES THE MACHINE, AND WHAT STOPS IT. One request per draft place of each judged quotation (at most
reading.PLACES): the draft sentence (and the sentence before it when the quotation stands alone), the quotation,
the citation printed beside it and the source passage the list shows - no file name, nothing else of the draft.
This is the first krokai path that sends a draft's own sentences out during a check, so every brief goes through
`redact.gate` with the matter's configured surnames first; a brief the gate stops is not sent and its quotation
keeps its place. There is no override here: a quotation the gate holds is simply read by you alone.

🔴 WHAT IT NEVER DOES. It never changes a verdict, REPORT.md, result.json or the exit code. A missing key, an unset
model, a command-line channel, a model that fails or answers off-format: the list keeps its plain order and `check`
ends exactly as it would have. The cost and the time are printed every run.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor

from . import consult, reading, redact

MARKER = "JUDGE-DONE"
FLOOR = 10                 # characters: the answer is three short lines
PARALLEL = 8               # requests in flight; each is one small brief
TIMEOUT = 120              # seconds per request (K061: median 2-4 s, slowest 24 s)
DOUBT = ("OVERSTATED", "CONDITION_OMITTED", "EXCEPTION_APPLIES", "NOT_THE_HOLDING")
LABELS = DOUBT + ("SUPPORTED", "CANNOT_TELL")
_LABEL = re.compile(r"LABEL:\s*([A-Z_]+)")

# The closed-label instruction K061 scored (20/20 known defects at effort low, both models). Changed since: «a legal
# draft» for «a U.S. immigration legal draft», and the line on left-out words, which the list's passage can show.
SYSTEM = """You check one sentence from a legal draft against the source passage it quotes.
You get the draft SENTENCE (it contains a quotation), the QUOTATION, its CITATION, and the SOURCE PASSAGE: the
quoted words in **bold** with about two sentences of the source on each side; words the quotation leaves out are
shown as _[left out: ...]_. The quotation's words were already verified to appear in the source - do not check
spelling or punctuation. Judge only whether the passage supports the sentence as written. Use only the passage;
if it is not enough to decide, answer CANNOT_TELL.

Labels:
SUPPORTED - the passage supports the sentence as written.
OVERSTATED - the sentence claims more certainty, obligation, entitlement or breadth than the passage gives
  (for example "may" read as "must", "generally" as "always", a necessary condition read as a sufficient one).
CONDITION_OMITTED - the passage attaches a condition or limit that the sentence leaves out.
EXCEPTION_APPLIES - the facts stated in the sentence fall within an exception or contrary rule in the passage.
NOT_THE_HOLDING - the words come from a headnote, syllabus, summary or another speaker, not from the authority
  the sentence attributes them to.
CANNOT_TELL - the passage is not enough to decide.

Answer with exactly three lines:
LABEL: <one label>
REASON: <one sentence>
JUDGE-DONE
"""


def candidates(entries):
    """The quotations the pass may read: part 2 of the list (clean), with a passage and a place in the draft."""
    return [e for e in entries if not e["flagged"] and e["passage"] and e["places"]]


def briefs(e, lang="en"):
    """One brief per draft place (at most reading.PLACES). The passage is the list's own, without its file line."""
    r = e["row"]
    lines = reading._source_lines(e, lang)
    shown = lines[-1][2:] if lines[-1].startswith("> ") else lines[-1]
    cite = "; ".join(r.get("cites") or ()) or "none printed beside the quotation"
    out = []
    for _rel, cl in e["places"][:reading.PLACES]:
        sentence = (cl["lead"] + "\n" + cl["shown"]) if cl.get("lead") else cl["shown"]
        out.append("SENTENCE:\n%s\n\nQUOTATION:\n\"%s\"\n\nCITATION: %s\n\nSOURCE PASSAGE:\n%s\n"
                   % (sentence.strip(), reading._flat(r["quote"]), cite, shown.strip()))
    return out


def label_of(text):
    """The answer's label, or None when it is not one of LABELS (an off-format answer reads as no answer)."""
    m = _LABEL.search(text or "")
    return m.group(1) if m and m.group(1) in LABELS else None


def preflight(reg, name):
    """(channel, None) when the channel can be asked, else (None, why) - checked BEFORE anything is built or sent."""
    ch = (reg.get("channels") or {}).get(name)
    if not isinstance(ch, dict):
        return None, "no channel named «%s» in %s" % (name, reg.get("_loaded_from") or "channels.json")
    if ch.get("kind") != "http":
        return None, ("«%s» is a %s channel; the judge sends one short request per quotation and needs an HTTP "
                      "channel (an API key)" % (name, ch.get("kind") or "non-HTTP"))
    key, var = consult.resolve_key(ch)
    if not consult.resolve_base(ch):
        return None, "%s is not set for «%s»" % (ch.get("base_url_env") or "base_url", name)
    if not key:
        names = [v for v in (ch.get("key_env"), ch.get("key_env_fallback")) if v]
        return None, "no key: set %s" % (" or ".join(names) or "a key variable for «%s»" % name)
    if not ch.get("model") or ch.get("model") == "set-me":
        return None, "set `model` for «%s» in %s" % (name, reg.get("_loaded_from") or "channels.json")
    return ch, None


def ask(entries, name, ch, surnames=(), lang="en", printer=print):
    """Send the briefs, gate first. Returns the counts and the ids of the entries the model doubted - never what it
    said: the label decides one boolean and is dropped here."""
    work, held = [], 0
    for e in candidates(entries):
        for text in briefs(e, lang):
            sink = []
            if redact.gate([("judge brief", text)], allow_pii=False, printer=sink.append, surnames=surnames):
                held += 1
                continue
            work.append((id(e), text))
    info = {"channel": name, "model": ch.get("model"), "quotations": len(candidates(entries)), "briefs": len(work)
            + held, "held": held, "sent": len(work), "failed": 0, "doubted": set(), "usd": 0.0, "usd_known": True,
            "tokens_in": 0, "tokens_out": 0, "seconds": 0.0}
    if not work:
        return info
    printer("judge: %d brief(s) to «%s» (%s)%s ..." % (len(work), name, ch.get("model"),
                                                      ", %d held by the gate" % held if held else ""))

    def one(item):
        _eid, text = item
        return consult.call_http(name, ch, SYSTEM, text, MARKER, FLOOR, TIMEOUT, printer=lambda *a, **k: None,
                                 extra=ch.get("judge_body"))

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=min(PARALLEL, len(work))) as pool:
        answers = list(pool.map(one, work))
    info["seconds"] = round(time.time() - t0, 1)
    for (eid, _text), r in zip(work, answers):
        usage = (r.get("telemetry") or {}).get("usage") or {}
        info["tokens_in"] += int(usage.get("prompt_tokens") or 0)
        info["tokens_out"] += int(usage.get("completion_tokens") or 0)
        if isinstance(usage.get("cost"), (int, float)) and not isinstance(usage.get("cost"), bool):
            info["usd"] += float(usage["cost"])
        elif r.get("text"):
            info["usd_known"] = False
        lab = None if r.get("failures") else label_of(r.get("text"))
        if lab is None:
            info["failed"] += 1
        elif lab in DOUBT:
            info["doubted"].add(eid)
    return info


def reorder(entries, doubted):
    """Part 1 as it was; part 2 = the doubted quotations, then the others - each group keeps its plain order."""
    p1 = [e for e in entries if e["flagged"]]
    p2 = [e for e in entries if not e["flagged"]]
    return p1 + [e for e in p2 if id(e) in doubted] + [e for e in p2 if id(e) not in doubted]


def summary(info):
    """The console line. Counts only - which quotations were doubted is told by the list's order alone."""
    usd = ("$%.4f" % info["usd"]) if info["usd_known"] else "cost not reported by this channel"
    return ("judge: «%s» (%s) read %d brief(s) for %d quotation(s) - %d held by the gate, %d failed; %d quotation(s) "
            "put first in part 2 of the reading list; %s, %d+%d tokens, %.0f s"
            % (info["channel"], info["model"], info["sent"] - info["failed"], info["quotations"], info["held"],
               info["failed"], len(info["doubted"]), usd, info["tokens_in"], info["tokens_out"], info["seconds"]))
