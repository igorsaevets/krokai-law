# -*- coding: utf-8 -*-
"""The local law library: download it once, index it, and check the index before the internet.

THE RULE, AND WHY IT IS A RULE
-------------------------------
**Downloaded a source? Save it - to the library folder AND as a line in the index.**

Before this rule existed, sources were fetched into a temp folder and abandoned. Two rounds later
the same statute was fetched again, and the exact wording someone had already reconciled was gone.
Worse, and this is the part that costs real money: a quotation whose source was never saved comes
back NOT FOUND from the checker, and NOT FOUND is indistinguishable from *invented* unless you know
the library has a hole there. Measured: **2 of 8 bank entries flagged NOT FOUND turned out to be
missing downloads, not bad quotations.**

So the index is checked **before** any web search, and the checker classifies a miss three ways -
see ``verify``/``report`` - precisely so that "we never downloaded it" stops masquerading as
"someone made it up".

🔴 A DOWNLOADED FILE IS NOT PROVEN UNTIL BOTH THE PARTY AND THE SUBJECT ARE IN IT
---------------------------------------------------------------------------------
Measured: a search for a case by surname returned **a different case with the same surname** -
different docket, different year, unpublished, on an unrelated area of law. The name matched and the
court matched. Nothing else did. ``prove()`` below is the check that catches it.

🔴 A STUB IS MORE DANGEROUS THAN A MISSING FILE
------------------------------------------------
A 1.8 KB placeholder where a 60 KB chapter should be still looks downloaded. The index counts the
topic as covered, nothing can be verified against it, and every quotation from it fails for reasons
that look like the quotation's fault.

🔴 AND THE COPY YOU HAVE MAY BE SILENTLY INCOMPLETE
----------------------------------------------------
Measured: a scraped copy of one agency chapter carried **four of six** bullet points in a list. Not
a truncated line - the last two simply were not there. A quotation of the missing text came back
flagged, and the quotation was right. **A flag can mean the corpus is wrong.** ``recheck_live`` is
the discipline: before you "fix" a document because of a flag, open the live page.
"""
from __future__ import annotations

import io
import os
import re
import time

__all__ = ["INDEX_HEADER", "index_entries", "add_entry", "prove", "orphans", "RECIPES"]

INDEX_HEADER = """# Law library index

🔴 **Look here before searching the web.** Everything listed is already on disk, in full text.

Found a new source? **Download it into the library folder AND add a line here.** A source that is
not indexed will be downloaded again next round, and its absence turns an honest quotation into a
`NOT_FOUND` that looks like a fabrication.

| Citation | What it is | File | Retrieved | Edition / as of | Notes |
|---|---|---|---|---|---|
"""

ENTRY = "| {citation} | {what} | `{file}` | {when} | {edition} | {notes} |"

# Retrieval recipes that were established by measurement, not by reading documentation. They are
# specific to US federal sources; the point of listing them is that the obvious method fails for
# most of these and the failure is often a 200 with an empty body rather than an error.
RECIPES = [
    ("U.S. Code, any section",
     "https://www.govinfo.gov/link/uscode/{title}/{section}?link-type=html",
     "The government's own copy. No key, no rate limit."),
    ("Federal Register, by volume and page",
     "https://www.govinfo.gov/link/fr/{volume}/{page}?link-type=html",
     "Resolves a bare `NN FR NNNNN` pincite straight to the text."),
    ("Federal Register, full text of a specific rule",
     "https://www.federalregister.gov/api/v1/documents/{number}.json  ->  field `raw_text_url`",
     "🔴 The HTML site is behind an anti-bot layer; the API is not. Document numbers look like "
     "`2024-06657`."),
    ("eCFR, a whole part",
     "https://www.ecfr.gov/api/versioner/v1/full/{date}/title-{n}.xml?part={part}",
     "🔴 Take {date} from `/api/versioner/v1/titles.json` (`latest_issue_date`) or you get a 404. "
     "The browser-facing site refuses automated fetches; this API does not. Strip tags, unescape "
     "entities, collapse whitespace, and it greps verbatim."),
    ("Federal court opinions",
     "https://www.govinfo.gov/content/pkg/USCOURTS-{court}-{docket}/pdf/...-0.pdf",
     "🔴 Use this rather than the free aggregators: one returns 202 for a bot queue, another 403. "
     "govinfo serves the government's copy without authentication."),
    ("A preamble - the reasoning behind a rule",
     "Federal Register, the rule's own document, section-by-section analysis",
     "🔴 Read it BEFORE building an argument on the text of a regulation. The regulation does not "
     "show you which softening the agency already considered and rejected. Measured: a provision "
     "read as a narrow prohibition had a preamble that recorded, verbatim, the rejected objection "
     "asking for exactly the exemption the argument depended on."),
]


def index_entries(path):
    """Every `file` cell already listed. Used to find what is on disk but unindexed."""
    if not os.path.exists(path):
        return set()
    out = set()
    for line in io.open(path, encoding="utf-8", errors="replace"):
        m = re.search(r"\|\s*`([^`]+)`\s*\|", line)
        if m:
            out.add(os.path.normcase(m.group(1).strip()))
    return out


def add_entry(path, citation, what, filename, edition="", notes="", when=None):
    """Add one row to the index - INSIDE the table, not after whatever the file ends with.

    🔴 Appending is what the obvious version does, and it is wrong as soon as anyone writes a
    sentence below the table. Measured in the sister project: a 777-line index ended in prose, its
    last table row was line 771, and the script appended row 778 - then printed "row added", which
    was true and useless. Markdown stops rendering a table at the first non-row line, so the entry
    was invisible in every viewer, and an invisible index entry is the same as no index entry: the
    source gets downloaded again and its absence turns an honest quotation into a NOT_FOUND.

    So: find the last line that is a table row and insert after it. If the file exists and has no
    table at all, say so and refuse - a row written into a file with no table is a row nobody will
    ever see, and a silent success is worse than a loud failure.
    """
    row = ENTRY.format(citation=citation, what=what, file=filename,
                       when=when or time.strftime("%Y-%m-%d"),
                       edition=edition or "—", notes=notes or "")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

    if not os.path.exists(path):
        io.open(path, "w", encoding="utf-8", newline="\n").write(INDEX_HEADER + row + "\n")
        return row

    lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
    last = -1
    for i, line in enumerate(lines):
        if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            last = i
    if last < 0:
        raise ValueError(
            "%s exists but contains no table, so a row appended to it would never render. "
            "Add the header from library.INDEX_HEADER, or point library_index somewhere else."
            % path)
    lines.insert(last + 1, row)
    tmp = path + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    os.replace(tmp, path)             # atomic: a half-written index is a lost index
    return row


def prove(text, party=None, subject=None):
    """Is this file actually the document it was downloaded as?

    Both tests must pass. The party alone is not enough - that is precisely how a same-surname
    decoy gets accepted - and the subject alone is not enough either, because every case in an area
    of law discusses the same statute.

    Returns `(ok, reasons)`.

    🔴 NOTHING ASSERTED IS NOT THE SAME AS NOT PROVEN, and the first version returned the same
    `False` for both - with an empty reason list, so the caller was told "unproven" and given no
    way to find out why. That matters far outside case law: a statute, a regulation, an executive
    order and a treaty have no party at all, so for most primary sources there is nothing to assert
    and the honest answer is "you asked me to check nothing". Named by a reviewer who was arguing
    that a party-and-subject test cannot be a general requirement. It cannot; it is an optional
    test that must say when it did not run.
    """
    reasons = []
    low = (text or "").lower()
    if party:
        got = party.lower() in low
        reasons.append(("party %r present" % party, got))
    if subject:
        got = subject.lower() in low
        reasons.append(("subject %r present" % subject, got))
    if len(low.strip()) < 2000:
        reasons.append(("file is suspiciously short (%d chars) - possible stub or login page"
                        % len(low.strip()), False))
    if not (party or subject):
        reasons.append(("no party and no subject were given, so identity was NOT checked - "
                        "correct for a statute or regulation, and not proof of anything", False))
    return all(ok for _t, ok in reasons) and bool(reasons), reasons


def orphans(source_dirs, index_path, exts=None, skip_dirs=()):
    """Files present on disk but absent from the index, and index rows whose file is gone.

    Both directions matter. An unindexed file gets downloaded again; an indexed file that no longer
    exists makes the index a promise the library cannot keep, and a promise nothing re-checks is
    exactly how a stale library survives - the same shape as an allowlist entry nobody revisits.

    R76: the default `exts` is now `corpus.DEFAULT_EXT` - the hand-typed tuple here lacked
    `.docx`/`.doc`, so an indexed-and-verified .docx source could never be reported (kimik3,
    orglm53, orgemini37flash - the exact cross-tuple drift class this file's own docstring
    warns about). `skip_dirs` exists so `krokai close` stops reporting archived material.
    """
    from .corpus import walk, DEFAULT_EXT
    if exts is None:
        exts = DEFAULT_EXT
    listed = index_entries(index_path)
    on_disk = {}
    for p in walk(source_dirs, exts, skip_dirs):
        on_disk[os.path.normcase(os.path.basename(p))] = p
    listed_names = {os.path.normcase(os.path.basename(x)) for x in listed}
    unindexed = sorted(v for k, v in on_disk.items()
                       if k not in listed_names and not k.endswith(".text.md"))
    missing = sorted(x for x in listed if os.path.normcase(os.path.basename(x)) not in on_disk)
    return unindexed, missing
