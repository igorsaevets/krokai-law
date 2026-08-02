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
    header = "" if os.path.exists(path) else INDEX_HEADER
    row = ENTRY.format(citation=citation, what=what, file=filename,
                       when=when or time.strftime("%Y-%m-%d"),
                       edition=edition or "—", notes=notes or "")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with io.open(path, "a", encoding="utf-8", newline="\n") as fh:
        if header:
            fh.write(header)
        fh.write(row + "\n")
    return row


def prove(text, party=None, subject=None):
    """Is this file actually the document it was downloaded as?

    Both tests must pass. The party alone is not enough - that is precisely how a same-surname
    decoy gets accepted - and the subject alone is not enough either, because every case in an area
    of law discusses the same statute.

    Returns `(ok, reasons)`.
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
    return all(ok for _t, ok in reasons) and bool(reasons), reasons


def orphans(source_dirs, index_path, exts=(".pdf", ".xml", ".htm", ".html", ".txt", ".md")):
    """Files present on disk but absent from the index, and index rows whose file is gone.

    Both directions matter. An unindexed file gets downloaded again; an indexed file that no longer
    exists makes the index a promise the library cannot keep, and a promise nothing re-checks is
    exactly how a stale library survives - the same shape as an allowlist entry nobody revisits.
    """
    from .corpus import walk
    listed = index_entries(index_path)
    on_disk = {}
    for p in walk(source_dirs, exts):
        on_disk[os.path.normcase(os.path.basename(p))] = p
    listed_names = {os.path.normcase(os.path.basename(x)) for x in listed}
    unindexed = sorted(v for k, v in on_disk.items()
                       if k not in listed_names and not k.endswith(".text.md"))
    missing = sorted(x for x in listed if os.path.normcase(os.path.basename(x)) not in on_disk)
    return unindexed, missing
