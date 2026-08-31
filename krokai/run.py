# -*- coding: utf-8 -*-
"""The whole-matter pass: every quotation in everything you wrote, against every source you have.

TIERS, AND WHY THE NUMBERS ARE REPORTED SEPARATELY
---------------------------------------------------
Your own writing is not one pile. What gets filed and what sits in a research note fail at
different costs, and mixing them corrupts the number in both directions.

Measured, and this is not a hypothetical: an archived copy of **this tool's own report** had been
filed into a drafts folder. It was therefore re-verifying its own output, and **1 443 of 1 606
misses came from that single file**. The overall figure was meaningless and looked alarming; the
figure for the documents that actually mattered was fine.

So tool output and reviewer answers get their own tier D. They are still checked - a reviewer's
invented quotation is worth catching - but they never pollute the count for tier A.

🔴 A SENTINEL, NOT A NAME PATTERN
-----------------------------------
Tier D was first detected by filename. One hour later this tool's own report went back into tier C,
because it had been archived under a title the pattern did not know. A rule based on names cannot
keep up with names. So the generator **stamps what it writes** and the walker reads the stamp.
"""
from __future__ import annotations

import io
import json
import os
import time

from . import address as addr_mod
from .citations import load_packs
from .corpus import Corpus, walk
from .extract import extract_quotes, citation_window
from .readers import read_any
from .verdicts import ORDER, DANGEROUS, CLEAN, UNCHECKABLE, MEANING, MARK, label, meaning
from .verify import check

__all__ = ["scan_matter", "write_report", "SENTINEL", "SENTINELS"]

SENTINEL = "KROKAI-TOOL-OUTPUT"

# The stamp the tool WRITES is one string; the stamps it RECOGNISES are several, and that asymmetry
# is the whole reason a rename is survivable. A report written before the project was renamed still
# carries the old stamp, and a report that stops being recognised silently rejoins tier C - which is
# incident 3 in FEATURES.md, the largest number in the whole log: 1 443 of 1 606 misses from one
# file. Delete a legacy entry only once you are willing to say that no archived report anywhere
# still carries it, which for a document a lawyer keeps for the life of a matter is a long time.
SENTINELS = (SENTINEL, "LAWVERBATIM-TOOL-OUTPUT")
TARGET_EXT = (".md", ".txt", ".docx")

TIER_D = ("D", "tool output and reviewers' answers")


def corpus_for(cfg, quiet=True):
    """THE one way to build a matter's corpus, with both protections armed.

    🔴 R76 (kimik3, grokbuild, lunapro converged - rated CRITICAL by two of them): sentinel
    exclusion and superseded-edition tracking are constructor PARAMETERS, and only
    `scan_matter` remembered to pass them. `krokai quote` - the documented door for «check
    this before you paste it» - plus `mutate --report` and `review --audit` all built a bare
    Corpus: sidecars inside `law/` were indexed as primary sources and SUPERSEDED_EDITION was
    unreachable, so the same text got different verdicts depending on which command asked.
    The law register comment survives here: without `superseded=`, both editions are indexed
    and a quotation of superseded law comes back VERIFIED - measured 2026-08-05, and it
    silently voided the NOT_FOUND doctrine for every revised provision.
    """
    from .fetch import superseded_paths
    return Corpus(cfg.source_dirs, skip_dirs=set(cfg["skip_dirs"]),
                  cache_dir=cfg.cache, quiet=quiet, sentinel=SENTINELS,
                  superseded=superseded_paths(cfg.root))


def _is_tool_output(path):
    try:
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(400)
        return any(s in head for s in SENTINELS)
    except OSError:
        return False


def scan_matter(cfg, only=None, tiers="ABCD", quiet=False, printer=print):
    """Returns a dict with rows, corpus facts and the tier grid."""
    t0 = time.time()
    packs = load_packs(cfg["citation_packs"])
    if not quiet:
        printer("citation packs: %s" % ", ".join(packs.ids))

    corpus = corpus_for(cfg, quiet=quiet)
    if not corpus.paths:
        printer("\n🔴 The corpus is EMPTY. Every quotation will come back NOT FOUND, which looks "
                "like catastrophe and is really a path problem.")
        printer("   sources configured: %s" % ", ".join(cfg["sources"]))
        for kind, p in cfg.missing_paths():
            printer("   missing %s folder: %s" % (kind, p))
        return None

    # --- collect every quotation from our own writing ----------------------------------------
    uniq = {}
    per_file = []
    for tier, tlabel, root in cfg.draft_tiers:
        for p in walk([root], TARGET_EXT, set(cfg["skip_dirs"])):
            if only and only.lower() not in p.lower():
                continue
            t = TIER_D[0] if _is_tool_output(p) else tier
            if t not in tiers:
                continue
            try:
                body = read_any(p, cfg.cache)
            except Exception as exc:
                printer("  !! unreadable %s (%s)" % (p, type(exc).__name__))
                continue
            qs = extract_quotes(body, cfg["min_quote_length"], cfg["drop_cyrillic_quotes"])
            rel = os.path.relpath(p, cfg.root)
            per_file.append((t, rel, len(qs)))
            for q in qs:
                key = q.strip().lower()
                rec = uniq.setdefault(key, {"quote": q, "sites": []})
                near, far = citation_window(body, q, packs)
                rec["sites"].append({"tier": t, "file": rel, "near": near, "far": far})

    if not quiet:
        printer("\ntargets: %d files, %d distinct quotations of %d+ characters"
                % (len(per_file), len(uniq), cfg["min_quote_length"]))

    # --- check each one ------------------------------------------------------------------------
    keymap = addr_mod.KeyMap(corpus, packs)
    rows = []
    t1 = time.time()
    for i, (_k, rec) in enumerate(sorted(uniq.items()), 1):
        verdict, where, detail = check(rec["quote"], corpus)
        near = sorted({c for s in rec["sites"] for c in s["near"]})
        far = sorted({c for s in rec["sites"] for c in s["far"]})
        near_legal = [c for c in near if packs.is_primary(c)]

        verdict, where, detail, address = addr_mod.fold(
            rec["quote"], verdict, where, detail, near_legal, corpus, keymap, packs)

        kind = ""
        if verdict == "NOT_FOUND":
            far_legal = [c for c in far if packs.is_primary(c)]
            if not far_legal:
                kind = "evidentiary - no legal citation anywhere near it; a corpus of statutes was "\
                       "never going to contain this"
            # 🔴 R76 (orgemini37flash): this used to test `c in corpus.joined` - the citation
            # STRING as the drafter formatted it, searched in the source BODY text. Downloads
            # rarely contain their own Bluebook form («8 U.S.C. § 1255(k)» vs a uslm XML), so
            # the 🔴 branch almost never fired and confirmed fabrications drifted into the 🟡
            # «probably a gap» comfort. The honest question is the keymap's: does any cited
            # key RESOLVE to a file on this disk?
            elif any(keymap.resolve(k) for k in packs.keys(far_legal)):
                kind = "🔴 legal, and the source IS on this disk"
            else:
                kind = "🟡 legal, but the cited authority is not in the corpus at all - probably a "\
                       "gap in the library, not a fabrication"

        rows.append({"verdict": verdict, "detail": detail, "quote": rec["quote"], "kind": kind,
                     "where": os.path.relpath(where, cfg.root) if where else "",
                     "where_abs": where or "",
                     "cites": near or far, "near": near, "sites": rec["sites"],
                     "address": address})
        if not quiet and i % 200 == 0:
            printer("   ...%d/%d (%.0f s)" % (i, len(uniq), time.time() - t1))

    rank = {s: i for i, s in enumerate(ORDER)}
    rows.sort(key=lambda r: (rank.get(r["verdict"], 99), -len(r["sites"])))

    grid = {t: {s: 0 for s in ORDER} for t in "ABCD"}
    for r in rows:
        grid[_tier_of(r)][r["verdict"]] += 1

    return {"rows": rows, "grid": grid, "per_file": per_file, "corpus": corpus,
            "packs": packs, "mixed": mixed_provisions(rows, packs),
            "seconds": round(time.time() - t0, 1),
            "tier_labels": {t: l for t, l, _p in cfg.draft_tiers}}


# Verdicts that read as "this quotation is fine" for the purposes of the pairing below.
# 🔴 R76: DERIVED from `verdicts.CLEAN` - the hand-typed third copy had drifted to include
# SCATTERED, which is DANGEROUS, so a scattered copy of a provision sat on the CLEAN side of
# the mixed-provisions pairing and understated that both copies need attention (qwen38max,
# agy37flash, goog37flash). Three lists of one concept was the defect; now there is one.
_CLEANISH = tuple(CLEAN)


def mixed_provisions(rows, packs):
    """The SAME provision quoted both clean and flagged across the matter.

    🔴 Ported from a measured incident in a sister project, 2026-08-02: a round's correction was
    applied to the body of a memorandum and NOT to the exhibit caption three lines below, so one
    file quoted the same regulation both complete and truncated - and the truncated copy sat
    exactly where the adjudicating officer looks first. A per-quotation report shows both rows,
    pages apart, and nothing connects them; a person fixes the first hit and stops. The rule this
    check enforces is *fix every occurrence, not the first*.

    Grouping is by the ADDRESS KEY of the citations printed beside each quotation, because the
    address is the only thing the clean copy and the truncated copy still share. Quotations with no
    nearby citation cannot join a group - which is one more consequence of an address never
    written down.

    Returns `[(label, clean_rows, flagged_rows)]`, largest flagged count first.
    """
    groups = {}
    for r in rows:
        for k in packs.keys(r.get("near") or []):
            g = groups.setdefault(k, ([], []))
            if r["verdict"] in _CLEANISH:
                g[0].append(r)
            elif r["verdict"] in DANGEROUS:
                g[1].append(r)
    out = []
    for k, (clean, flagged) in groups.items():
        if clean and flagged:
            out.append((packs.label(k), clean, flagged))
    out.sort(key=lambda t: -len(t[2]))
    return out


def _tier_of(row):
    ts = {s["tier"][0] for s in row["sites"]}
    for t in "ABCD":
        if t in ts:
            return t
    return "?"


def print_summary(res, lang="en", printer=print):
    grid = res["grid"]
    printer("\n%-25s %7s %7s %7s %7s" % ("verdict", "A filed", "B guides", "C research", "D tool"))
    for s in ORDER:
        n = sum(grid[t][s] for t in "ABCD")
        if not n:
            continue
        # 🔴 R76: MARK was a table only the self-test read - «tested decoration» (F9). It now
        # prefixes every summary row, so a DANGEROUS verdict is visibly marked in the one
        # place every run prints.
        printer("%s %-22s %7d %7d %7d %7d"
                % (MARK.get(s, "  "), label(s, lang),
                   grid["A"][s], grid["B"][s], grid["C"][s], grid["D"][s]))
    ab_bad = sum(grid[t][s] for t in "AB" for s in DANGEROUS)
    printer("\n🔴 needs a human in tiers A+B: %d" % ab_bad)

    # 🔴 Counted and printed SEPARATELY, never folded into either total. Reporting it with the
    # red count buries the real misses - measured at 20 of 37 on a real filing - and reporting it
    # with the green count would call "I could not check this" a pass. It is its own line because
    # it is its own fact, and it comes with the only action that resolves it.
    ab_unknown = sum(grid[t][s] for t in "AB" for s in UNCHECKABLE)
    if ab_unknown:
        printer("? NOT CHECKED in tiers A+B: %d - the address beside them names sources you have "
                "not downloaded. This is neither a pass nor an accusation; get the sources and "
                "run again. `krokai library` lists what is missing." % ab_unknown)

    for lbl, clean, flagged in res.get("mixed") or []:
        printer("🔴 %s is quoted both CLEAN (%d) and FLAGGED (%d) in this matter - the flagged "
                "copies are the same provision. Fix EVERY occurrence, not the first: measured, a "
                "correction landed in a memo body and missed the exhibit caption below it."
                % (lbl, len(clean), len(flagged)))

    astat = {}
    for r in res["rows"]:
        a = r.get("address")
        if a:
            astat[a["status"]] = astat.get(a["status"], 0) + 1
    if astat:
        printer("address binding (found quotations only): "
                + " · ".join("%s %d" % (k, v) for k, v in sorted(astat.items())))
        printer("   NO_NEARBY_CITATION on something you file means DO NOT award a green: there is "
                "no address to check.")
    # 🔴 BOTH numbers, because the EXIT CODE is the surface a hook and a CI job read, and it used
    # to be driven by `ab_bad` alone. A reviewer put it precisely: cite a source you do not have,
    # and a fabricated quotation lands in `NO_SOURCE_ON_DISK`, the headline count reads
    # "needs a human: 0", and `krokai check --strict` exits 0. The separate line was visible to a
    # person and invisible to the machine, which is the half that actually gates anything.
    return ab_bad, ab_unknown


def write_report(res, cfg, out_dir, lang="en"):
    os.makedirs(out_dir, exist_ok=True)
    c = res["corpus"]
    grid = res["grid"]
    md = [
        "<!-- %s : generated by `krokai check`. Not a primary source and not our argument: "
        "quotations from this file must never be counted in tier A or B. -->" % SENTINEL,
        "# Citation check", "",
        "Corpus: **primary sources only** - %d files, %.1f MB. Excluded as our own derived text: "
        "%d. Without a text layer: %d."
        % (len(c.paths), len(c.joined) / 1e6, len(c.excluded_derived), len(c.excluded_stub)), "",
        "🔴 Tier **D** is this tool's own output and outside reviewers' answers. It is checked but "
        "never mixed with what you file: in one measured run a single archived report produced "
        "1 443 of 1 606 misses.", "",
        "| verdict | A filed | B guides | C research | D tool | what it means |",
        "|---|---|---|---|---|---|",
    ]
    for s in ORDER:
        if not sum(grid[t][s] for t in "ABCD"):
            continue
        md.append("| %s | %d | %d | %d | %d | %s |"
                  % (label(s, lang), grid["A"][s], grid["B"][s], grid["C"][s], grid["D"][s],
                     meaning(s, lang)))
    md.append("")

    if c.excluded_derived:
        md += ["## Excluded from the corpus as our own derived text", "",
               "If a primary source is in this list, fix the pattern - do not stay silent.", ""]
        md += ["* `%s`" % os.path.relpath(p, cfg.root) for p in c.excluded_derived] + [""]
    if c.excluded_stub:
        md += ["## Corpus files with no text layer", "",
               "A scan without OCR, or a stub. A quotation from these yields a FALSE miss. "
               "🔴 Run them through a real OCR engine - never a language model.", ""]
        md += ["* `%s`" % os.path.relpath(p, cfg.root) for p in c.excluded_stub] + [""]

    if res.get("mixed"):
        md += ["## 🔴 One provision, two texts", "",
               "The same provision is quoted both clean and flagged somewhere in this matter. "
               "These pairs are invisible in a per-quotation list - the two copies can sit pages "
               "or files apart - and the measured way this happens is a correction applied to one "
               "occurrence and not the others. **Fix every occurrence, not the first.** "
               "(A quotation with several citations beside it joins each group - read the pair "
               "before editing anything; this section prompts a comparison, it does not accuse.)",
               ""]
        for lbl, clean, flagged in res["mixed"]:
            md += ["### %s — clean ×%d, flagged ×%d" % (lbl, len(clean), len(flagged)), ""]
            for r in flagged[:4]:
                files = ", ".join(sorted({s["file"] for s in r["sites"]})[:3])
                md += ["* **%s** in %s" % (r["verdict"], files),
                       "  > %s" % r["quote"][:220].replace("\n", " "), ""]

    for st in ORDER:
        if st in ("VERIFIED", "ASSEMBLED"):
            continue
        sel = [r for r in res["rows"] if r["verdict"] == st]
        if not sel:
            continue
        md += ["", "## %s - %d (A %d · B %d · C %d · D %d)"
               % (label(st, lang), len(sel), grid["A"][st], grid["B"][st], grid["C"][st],
                  grid["D"][st]), "", meaning(st, lang), ""]
        for j, r in enumerate(sel, 1):
            md += ["### %d. [%s] %s" % (j, _tier_of(r),
                                        "; ".join(r["cites"]) if r["cites"] else
                                        "no citation printed beside it"),
                   "", "> %s" % r["quote"].replace("\n", " "), ""]
            if r.get("detail"):
                md += ["**Difference:** %s" % r["detail"], ""]
            if r.get("kind"):
                md += ["**Kind of miss:** %s" % r["kind"], ""]
            a = r.get("address")
            if a and a["status"] != "MATCHED":
                md += ["**Address:** %s%s" % (a["status"],
                                              (" - cited " + "; ".join(a["keys"])) if a.get("keys") else ""),
                       ""]
            md += ["Used in %d file(s):" % len(r["sites"])]
            md += ["* `%s`" % s["file"] for s in r["sites"][:12]]
            if len(r["sites"]) > 12:
                md += ["* … and %d more" % (len(r["sites"]) - 12)]
            if r["where"]:
                md += ["", "Found in: `%s`" % r["where"]]
            md += [""]

    report_md = os.path.join(out_dir, "REPORT.md")
    io.open(report_md, "w", encoding="utf-8", newline="\n").write("\n".join(md))

    payload = {"generated_by": SENTINEL,
               "rows": [{k: v for k, v in r.items() if k not in ("where_abs",)}
                        for r in res["rows"]],
               "grid": grid, "per_file": res["per_file"],
               "corpus_files": len(c.paths),
               "corpus_derived": [os.path.relpath(p, cfg.root) for p in c.excluded_derived],
               "corpus_no_text_layer": [os.path.relpath(p, cfg.root) for p in c.excluded_stub],
               "seconds": res["seconds"]}
    json.dump(payload, io.open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    return report_md
