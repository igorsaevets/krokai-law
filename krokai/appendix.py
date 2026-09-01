# -*- coding: utf-8 -*-
"""The legal appendix ("Нормативная база") built from the bank, with fresh verification.

WHAT THIS IS
------------
The one section of the filing that lists the rules the argument rests on. Traditionally hand-
compiled at the end - which means it is hand-compiled from the bank the drafter *remembers*,
not the bank the corpus can still verify. This module builds that section MECHANICALLY from
banked entries whose FRESH verdict is clean, right now, against the current corpus.

WHY FRESH VERIFICATION AT BUILD TIME MATTERS
--------------------------------------------
The bank records what was verified WHEN THE ENTRY WAS BANKED. Between then and the day the
appendix is built:

* a regulation may have been revised (measured in the sister project: 8 CFR 245 replaced
  "alien" with "noncitizen", 32 sentences gone; every affected banked entry would come back
  ``NOT_FOUND`` overnight, correctly quoted and unverifiable);
* a source file may have been re-fetched, re-extracted, moved or removed;
* an entry banked before ``krokai bank add`` existed may never have been machine-verified in
  the first place.

The appendix is what the filing carries. It has to be verified against WHAT IS ON DISK NOW, not
against a memory of last month's disk. So every rebuild re-runs ``check`` on every entry - no
caching, no "was VERIFIED yesterday" shortcut, no exception.

WHAT LANDS WHERE
----------------
An entry whose fresh verdict is in ``verdicts.CLEAN`` goes into the appendix, grouped by kind
(CFR, USC, INA, Public Law, Federal Register, USCIS Policy Manual, other). Every other entry
goes into an ``EXCLUDED`` section that names its fresh verdict and points at the six causes of
a false ``NOT_FOUND``.

🔴 EXCLUSION IS NAMED, NEVER SILENT
------------------------------------
Silent exclusion is how a dropped proviso reaches a filing. If the appendix simply omitted an
entry whose fresh check failed, the drafter would not know an entry they meant to cite is
missing. The excluded section is what turns "the tool decided" into "I decided, and here is
what I looked at". The whole point of the excluded section is to be READ before the appendix
is filed.

🔴 SIDE DEFAULTS TO 'pro' - THE APPENDIX IS FOR US
--------------------------------------------------
An appendix built from ``against us`` entries and pasted into the filing would arm the
adjudicator with the strongest cons. There is no ``--side both`` because there is no legitimate
petition use for it; ``--side con`` exists only for internal review documents that the drafter
labels as such.

DELIBERATELY OUT OF SCOPE
-------------------------
* Package passport (``package_check`` in AOS) - deferred to when multi-round deliveries exist.
* Delivery diff (``pkg_diff``) - same reason.
* PDF generation - the appendix is markdown; a hand tool (or the filing builder) renders it.
"""
from __future__ import annotations

import io
import os
import time

from .verdicts import CLEAN, DANGEROUS, UNCHECKABLE, label as verdict_label
from .verify import check

__all__ = ["build_appendix", "GROUP_ORDER", "group_of_key", "SIDE_LABEL"]


# The reading order of the appendix. Statutes and regulations first, because that is where a
# filing's rules-of-decision live; agency guidance next; Federal Register and precedent-style
# citations after. The "other" bucket collects addresses the packs recognise but this module
# does not group (state code, court reporter, guidance memoranda without a numbered form).
GROUP_ORDER = (
    ("cfr", "Code of Federal Regulations"),
    ("usc", "United States Code"),
    ("ina", "Immigration and Nationality Act"),
    ("publaw", "Public Laws"),
    ("fr", "Federal Register"),
    ("pm", "USCIS Policy Manual"),
    ("pmnum", "USCIS Policy Memoranda"),
    ("other", "Other authorities"),
)

SIDE_LABEL = {"pro": "For us", "con": "Against us"}


def group_of_key(key):
    """Which appendix group a coverage key belongs to. Unknown kinds and empty keys land in
    ``other`` - never dropped, because an entry with an unrecognised address still belongs in
    the appendix under something rather than nowhere.
    """
    if not key:
        return "other"
    kind = key[0] if isinstance(key, tuple) else "other"
    for k, _l in GROUP_ORDER:
        if kind == k:
            return k
    return "other"


def _entry_group(entry, packs):
    """Best group for a banked entry. Uses the coverage extractor's fine keys first (they
    carry the kind we group by), falls back to `other` if none parses.

    The packs argument is present so a future refinement can consult it; the current code
    uses the entry's `addr_keys` (already populated by `coverage.parse_bank_entries`).
    """
    if not entry.get("addr_keys"):
        return "other"
    # Prefer the most specific narrow key: if the entry has both a coarse `(cfr, 8, 214)`
    # and a fine `(cfr, 8, 214, 2, f)`, the fine one wins - same subitem depth the reader
    # sees at the bottom of the section header.
    keys = sorted(entry["addr_keys"], key=lambda k: (-len(k), k))
    return group_of_key(keys[0])


def _format_entry_included(entry, verdict, where, detail, cfg_root):
    """The markdown block for one INCLUDED entry.

    Format is stable so downstream tools (a filing builder, a diff of appendices between
    rounds) can parse it back if needed. Fields that were unset in the bank are elided rather
    than rendered as `TO DO`: the appendix is what the filing carries, and a `TO DO` in a
    filing reads as an oversight.
    """
    lines = []
    lines.append("")
    lines.append("### %s%s%s" % (
        entry.get("id") or "§?",
        " " + entry.get("claim") if entry.get("claim") else "",
        "",
    ))
    lines.append("")
    quote = (entry.get("quote") or "").strip()
    if quote:
        # Fold multi-line quotes into one blockquote block; a reader looking at the appendix
        # sees the quotation as one visual unit rather than as several `>` runs.
        lines.append("> %s" % quote)
        lines.append("")
    lines.append("**Address**: %s" % (entry.get("address") or "(no address recorded)"))
    if where:
        try:
            rel = os.path.relpath(where, cfg_root)
        except (TypeError, ValueError):
            rel = where
        lines.append("**On disk**: `%s`" % rel)
    lines.append("**Verified**: %s (fresh, %s)" % (
        verdict_label(verdict).upper(),
        time.strftime("%Y-%m-%d"),
    ))
    if detail:
        lines.append("**Note**: %s" % detail[:400])
    if entry.get("not_proved"):
        lines.append("**What this does NOT prove**: %s" % entry["not_proved"])
    lines.append("")
    return "\n".join(lines)


def _format_entry_excluded(entry, verdict, where, detail, cfg_root):
    """The markdown block for one EXCLUDED entry.

    Loud on purpose. The exclusion section exists to be READ, and reading requires that the
    reader sees WHY - the verdict is called out with its heading, and the six-causes ladder is
    referenced (not restated - the referenced ladder is `krokai quote`'s output for this exact
    quotation, and re-printing it here would be a second home for the same content).
    """
    lines = []
    lines.append("")
    lines.append("### %s%s  🔴 EXCLUDED: %s" % (
        entry.get("id") or "§?",
        " " + entry.get("claim") if entry.get("claim") else "",
        verdict_label(verdict).upper(),
    ))
    lines.append("")
    quote = (entry.get("quote") or "").strip()
    if quote:
        lines.append("> %s" % quote[:600])
        if len(quote) > 600:
            lines.append(">")
            lines.append("> ...quotation truncated for the excluded section (%d chars total)"
                         % len(quote))
        lines.append("")
    lines.append("**Address**: %s" % (entry.get("address") or "(no address recorded)"))
    if where:
        try:
            rel = os.path.relpath(where, cfg_root)
        except (TypeError, ValueError):
            rel = where
        lines.append("**Located in**: `%s`" % rel)
    lines.append("**Fresh verdict**: %s" % verdict_label(verdict).upper())
    if detail:
        lines.append("**Detail**: %s" % detail[:400])
    lines.append("")
    lines.append("🔴 This entry did NOT reach the appendix. Options:")
    lines.append("   1. `krokai quote \"<the quotation>\"` to see the six causes of a false "
                 "NOT_FOUND")
    lines.append("   2. `krokai library --suggest-fetches` may name a download command for the "
                 "missing source")
    lines.append("   3. If the entry is stale, amend it in the bank")
    lines.append("")
    return "\n".join(lines)


def build_appendix(bank_files, corpus, packs, cfg=None, side="pro", printer=print):
    """Build a markdown legal appendix from one or more bank files.

    Every entry runs a FRESH ``check()`` at build time. Included entries are grouped by kind;
    excluded entries are listed in their own section with the fresh verdict.

    Returns ``(markdown_text, stats_dict)`` - the stats hold counts by verdict and by group,
    plus the timestamp of the build. Callers (the CLI, a hook, a report) use the stats for
    the summary line; the markdown is what gets written to disk.
    """
    from .coverage import parse_bank_entries

    # Read the bank files. A missing file is loud - the caller passed a path, so refusing to
    # find it means telling the caller which one, not silently building from the others.
    all_entries = []
    files_read = []
    for bp in bank_files:
        if not os.path.isfile(bp):
            printer("🔴 not a file: %s" % bp)
            return None, {"error": "bank file missing", "path": bp}
        text = io.open(bp, encoding="utf-8", errors="replace").read()
        parsed = parse_bank_entries(text)
        all_entries.extend(parsed)
        files_read.append((bp, len(parsed)))

    if not all_entries:
        printer("🔴 the bank(s) hold no entries - nothing to build.")
        return None, {"error": "no entries", "files": files_read}

    # Filter by side. Default 'pro' is the appendix that goes in the filing; 'con' is for a
    # standalone review document that names its own audience.
    if side not in ("pro", "con", "any"):
        printer("🔴 unknown side: %r (want pro|con|any)" % side)
        return None, {"error": "bad side", "side": side}
    if side == "any":
        entries = all_entries
    else:
        entries = [e for e in all_entries if e.get("side") == side]

    if not entries:
        printer("🔴 no bank entries on side=%s. Nothing to build." % side)
        return None, {"error": "no side entries", "side": side,
                      "total": len(all_entries)}

    cfg_root = getattr(cfg, "root", "") if cfg is not None else ""

    # Fresh verification. Every entry, one call, no cache.
    included = []
    excluded = []
    by_verdict = {}
    for e in entries:
        q = (e.get("quote") or "").strip()
        if not q:
            # An entry with no quotation cannot be verified - and cannot go into an appendix
            # either. Loud in the excluded section: an addressless quotationless entry is a
            # rot indicator, not a valid row.
            v, where, detail = "NOT_FOUND", None, "the bank entry has no quotation body"
        else:
            v, where, detail = check(q, corpus)
        by_verdict[v] = by_verdict.get(v, 0) + 1
        if v in CLEAN:
            included.append((e, v, where, detail))
        else:
            excluded.append((e, v, where, detail))

    # Group INCLUDED entries by kind. Every group present in the data appears; empty groups
    # stay hidden - a section header with "no entries" is noise.
    by_group = {}
    for e, v, where, detail in included:
        g = _entry_group(e, packs)
        by_group.setdefault(g, []).append((e, v, where, detail))

    # ------------- build the markdown ---------------------------------------------------
    when = time.strftime("%Y-%m-%d %H:%M")
    out = []
    out.append("# Legal appendix")
    out.append("")
    out.append("Built %s from %s bank entr%s (side=%s). Every quotation was re-verified "
               "against the corpus at build time." % (
                   when,
                   len(entries),
                   "y" if len(entries) == 1 else "ies",
                   side,
               ))
    out.append("")
    src_names = ", ".join("`%s`" % os.path.basename(p) for p, _ in files_read)
    out.append("**Source bank(s)**: %s" % src_names)
    out.append("**Included**: %d · **Excluded**: %d · **Corpus files**: %d"
               % (len(included), len(excluded), len(corpus.paths)))
    out.append("")
    out.append("🔴 EVERY REBUILD RE-RUNS `check` ON EVERY ENTRY. If a rule was revised, a "
               "source was re-fetched, or a file moved since the last build, this appendix "
               "reflects it - the previous build does not.")
    out.append("")
    out.append("---")
    out.append("")

    if not included:
        out.append("## No entries reached the appendix")
        out.append("")
        out.append("🔴 Every %s entry was excluded by fresh verification. See the excluded "
                   "section below for the fresh verdicts and the six causes of a false "
                   "NOT_FOUND." % SIDE_LABEL.get(side, side))
        out.append("")
    else:
        # In `GROUP_ORDER` order, then whatever groups are left over (defensive: a future
        # kind added to `coverage` before this module gets its row still surfaces).
        seen_groups = set()
        for group_key, group_label in GROUP_ORDER:
            rows = by_group.get(group_key)
            if not rows:
                continue
            seen_groups.add(group_key)
            out.append("## %s" % group_label)
            out.append("")
            for e, v, where, detail in rows:
                out.append(_format_entry_included(e, v, where, detail, cfg_root))
        for group_key in sorted(by_group.keys()):
            if group_key in seen_groups:
                continue
            rows = by_group[group_key]
            out.append("## Other (%s)" % group_key)
            out.append("")
            for e, v, where, detail in rows:
                out.append(_format_entry_included(e, v, where, detail, cfg_root))

    if excluded:
        out.append("")
        out.append("---")
        out.append("")
        out.append("## 🔴 Excluded from build (%d)" % len(excluded))
        out.append("")
        out.append("These entries did NOT reach the appendix because fresh verification "
                   "against the current corpus did not return a clean verdict. Read them - a "
                   "silently-dropped bank entry is how a filing loses ground it meant to "
                   "stand on.")
        out.append("")
        for e, v, where, detail in excluded:
            out.append(_format_entry_excluded(e, v, where, detail, cfg_root))

    stats = {
        "included": len(included),
        "excluded": len(excluded),
        "by_verdict": by_verdict,
        "by_group": {k: len(v) for k, v in by_group.items()},
        "side": side,
        "files_read": [{"path": p, "entries": n} for p, n in files_read],
        "total_entries_on_side": len(entries),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    return "\n".join(out) + "\n", stats
