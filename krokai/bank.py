# -*- coding: utf-8 -*-
"""The quote bank and the queue: two files that do opposite jobs.

THE BANK is a decision. *"This quotation matters to the matter, here is its address, here is where
the source sits on disk, here is how to re-check it in a minute, and here is what it does NOT
prove."* A person writes it. Nothing writes to it automatically, ever.

THE QUEUE is a list of undone work. A quotation appeared in an answer, it is not in the bank, so
something must be decided about it. A hook writes it after every turn.

🔴 WHY THEY ARE NOT ONE FILE
-----------------------------
Because automatic entry would turn the bank into a dump. Measured in the source project: a single
turn produced 65 legal quotations. Writing all of them into the bank would bury the four that
mattered under sixty-one that did not, and a bank you cannot read is a bank nobody opens. The queue
poses the question; the bank stores the answer.

🔴 WHY THE BANK NEEDS A "WHAT THIS DOES NOT PROVE" FIELD
---------------------------------------------------------
Paid for twice. A decision was quoted in a filed checklist under the footnote number of a
*different* decision, with the clause that limited it removed - and the case itself had come out
against a party in the same position as the client. Every character of the quotation was correct.
The field is where you write down, at the moment of banking, the thing that will be obvious to the
other side and invisible to you three weeks later.

🔴 WHY THERE IS AN "AGAINST US" SECTION
-----------------------------------------
A bank holding only the convenient quotations is a way of learning the inconvenient ones from the
adjudicator instead of from yourself.
"""
from __future__ import annotations

import io
import os
import re
import time

from .normalize import normalise, strip_markdown, latin_share
from .verdicts import CLEAN, UNCHECKABLE

__all__ = ["read_bank", "in_bank", "bank_quotes", "append_queue", "queue_open_items",
           "candidates", "BANK_HEADER"]

BANK_HEADER = """# Quote bank

Every quotation below has been **opened in the primary source by a person** and copied from it.

> ## Rules for this file
> 1. A quotation enters only **verbatim** and only after someone opened the source. A paraphrase is
>    not a quotation. A row without `On disk` and `How to re-check` is incomplete.
> 2. The field **What this does NOT prove** is mandatory. It is what catches a dropped proviso and
>    a pincite to the wrong page - the two defects a string check can never see.
> 3. The section **against us** is not optional. A bank of only helpful quotations is a way to hear
>    the unhelpful ones from the other side first.
>
> 🔴 Note on this header: it deliberately contains no long English text inside quotation marks.
> This file is itself checked, and prose in quotes would be extracted as a quotation of law and
> reported as NOT FOUND - a false alarm produced by the tool's own template. Measured on the first
> real run.
> 4. Run `krokai check` before anything is filed, and read every flag rather than binning it.

Weight legend: 🟢 primary text, personally verified · 🟡 my inference, or a quotation with a
caveat · 🔴 not personally verified - open the source before this goes anywhere.

---
"""

ENTRY_TEMPLATE = """
### {id} {weight} {claim}

> {quote}

| | |
|---|---|
| **Address** | {address} |
| **On disk** | `{on_disk}` |
| **How to re-check** | {recheck} |
| **Verified** | {who}, {when}{edition} |
| **Used in** | {used_in} |
| **Neighbours** | before — {before} · after — {after} |
| **What this does NOT prove** | {not_proved} |
"""

QUEUE_HEADER = """# Quote queue - not yet banked

Written automatically after each turn. This is a **list of undone work**, not a second bank:
anything that appeared in an answer and is not in the quote bank lands here.

**Closing a line:** open the source → decide whether the matter needs the quotation → if yes, bank
it with its address, its location on disk and a "what this does NOT prove" note → tick the box.
If not, tick the box and write one line saying why.

🔴 A green mark means the checker found the words verbatim. It does **not** mean the quotation is
apt: a dropped proviso and a wrong pincite are caught by eyes, not by string comparison.

🔴🔴 And it does not mean the quotation is *right*: the corpus is a set of downloads and can be
silently incomplete. Measured - a scraped copy of one agency chapter was missing two of its six
bullet points, so a correct quotation of that chapter came back flagged. **A flag can mean the
CORPUS is wrong, not the quotation.**
"""

# Not a rule of law: our own prose, channel telemetry, exhibit labels, code, paths.
NOISE = re.compile(
    r"\bmax_tokens\b|\btool_use\b|\bexit \d|\bHTTP \d|Exhibit\s|Screenshot|"
    r"\.py\b|\.md\b|\.json\b|https?://|%TEMP%|\$\{|\bTODO\b|\bFIXME\b", re.I)

_QUOTE_RE = re.compile(r'[«"“]([^«»"“”\n]{55,700})[»"”]')
_BLOCKQ_RE = re.compile(r"(?m)^>\s?(.{55,})$")


def read_bank(path):
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


_BQ_BLOCK_RE = re.compile(r"(?m)^(?:>.*\n?)+")


def bank_quotes(bank_text):
    """Every blockquote in the bank as one normalised, lower-cased string per block."""
    out = set()
    for m in _BQ_BLOCK_RE.finditer(bank_text or ""):
        q = normalise(strip_markdown(m.group(0))).lower()
        if q:
            out.add(q)
    return out


def in_bank(quote, bank_text):
    """Normalised containment, both sides.

    🔴 Both sides. A blockquote captured together with its guillemets normalises to straight
    quotes, the bank has none, and the substring stops matching - so a quotation that was banked
    yesterday raises an alarm today. That exact false positive appeared on the first run of the
    guard hook, and it is the one that teaches people to ignore the guard.
    """
    if not bank_text:
        return False
    n = normalise(strip_markdown(quote)).lower()
    # 🔴 40, not 20. An outside review traced a 25-character stock phrase ("in his discretion
    # grant the…") to a containment hit anywhere in the bank, silently keeping a NEW quotation
    # out of the queue. The extraction pipeline's own floor is 45, so nothing legitimate arrives
    # shorter - and the failure directions are asymmetric: a false "not banked" is one visible
    # queue line, a false "banked" is a quotation nobody ever decides about.
    if len(n) < 40:
        return False
    # 🔴 EQUALITY against the bank's own quotations, not containment in the whole file. Two
    # containment defects were traced by execution on the same day this was rewritten:
    #   * two different quotations sharing an opening formula collapsed into one under a
    #     first-60-characters key, so the second never reached the queue;
    #   * worse, a TRUNCATED variant of a banked quotation is a substring of the full one, so
    #     containment blessed exactly the cut-off-condition shape this toolkit exists to catch -
    #     the full quotation was banked, the truncated copy walked in under its name.
    # So the bank's `> ` blocks are extracted (consecutive lines joined, so a hand-wrapped entry
    # still counts as one quotation) and the candidate must EQUAL one of them. A drafter quoting
    # a legitimate subset gets one visible queue line - the cheap direction.
    return n in bank_quotes(bank_text)


def candidates(text, min_len=55, min_latin_share=0.75):
    """Long quoted spans in a piece of prose that could be quotations of law.

    🔴 The obvious test is wrong, and it shipped. The first version required 40 CONSECUTIVE latin
    letters, which never occurs in English because words are separated by spaces; the check
    silently returned "0 quotations" on a file full of them. The right signal is the latin
    **share**, never a run.
    """
    out, seen = [], []
    for m in list(_BLOCKQ_RE.finditer(text or "")) + list(_QUOTE_RE.finditer(text or "")):
        q = " ".join(m.group(1).split())
        if len(q) < min_len or NOISE.search(q):
            continue
        if latin_share(q) < min_latin_share:
            continue
        # The same span is caught both as a blockquote and as a quoted string. Without dedup the
        # guard showed it twice in a row, which reads as two problems.
        if any(q in s or s in q for s in seen):
            continue
        seen.append(q)
        out.append(q)
    return out


def append_queue(path, rows, dropped=0, cap=0, stamp=None):
    """Append one turn's findings. `rows` is `[(quote, verdict, source_name, detail), ...]`.

    🔴 EVERYTHING fresh goes in, including verdicts that came back clean. "Found verbatim" is not
    "appropriate": the "what this does not prove" analysis exists only in a bank entry, and that is
    what catches an excised condition.
    """
    header = "" if os.path.exists(path) else QUEUE_HEADER
    stamp = stamp or time.strftime("%Y-%m-%d %H:%M")
    out = ["\n## %s - %d quotation(s) not in the bank\n" % (stamp, len(rows))]
    for quote, verdict, src, detail in rows:
        # `?` for the uncheckable one: it is not green, and marking it 🔴🔴 would put "you have
        # not downloaded this yet" above a dropped proviso in the reader's eye.
        mark = ("🟢" if verdict in CLEAN else
                "?" if verdict in UNCHECKABLE else
                "🔴" if verdict in ("NOT_FOUND", "ERROR") else "🔴🔴")
        out.append("- [ ] %s **%s** · source: `%s`" % (mark, verdict, src or "—"))
        if detail:
            out.append("      detail: %s" % detail[:220])
        out.append("      > %s" % quote[:400])
        out.append("")
    if dropped:
        # 🔴 Silent truncation reads as "everything is covered". Say it out loud.
        out.append("- [ ] ⚠️ **%d** further quotation(s) from this turn were NOT checked: "
                   "per-turn cap %d\n" % (dropped, cap))
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(path, "a", encoding="utf-8", newline="\n") as fh:
        if header:
            fh.write(header)
        fh.write("\n".join(out))
    return len(rows)


def queue_open_items(path):
    """`(open, done, [first lines of open items])`. The second half of the hook: something has to
    refuse to close the round while the queue is not empty, or the file is read exactly as often as
    an instruction is obeyed - which is to say, by mood."""
    if not os.path.exists(path):
        return 0, 0, []
    t = io.open(path, encoding="utf-8", errors="replace").read()
    open_items = re.findall(r"(?m)^\s*-\s*\[ \]\s*(.{0,110})", t)
    done = len(re.findall(r"(?m)^\s*-\s*\[[xX]\]", t))
    return len(open_items), done, open_items


def render_entry(**kw):
    """Render a bank entry. Fields left empty are rendered as an explicit TO DO rather than blank,
    because a blank cell reads as "nothing to say here" and an empty "what this does not prove" is
    the single most common way a bad quotation survives."""
    d = {"id": "§?", "weight": "🔴", "claim": "", "quote": "", "address": "",
         "on_disk": "", "recheck": "", "who": "", "when": time.strftime("%Y-%m-%d"),
         "edition": "", "used_in": "", "before": "", "after": "",
         "not_proved": "🔴 TO DO - an entry without this field is not finished"}
    d.update({k: v for k, v in kw.items() if v})
    return ENTRY_TEMPLATE.format(**d)
