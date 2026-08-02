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
from .verdicts import ORDER, DANGEROUS, MEANING, label, meaning
from .verify import check

__all__ = ["scan_matter", "write_report", "SENTINEL"]

SENTINEL = "LAWVERBATIM-TOOL-OUTPUT"
TARGET_EXT = (".md", ".txt", ".docx")

TIER_D = ("D", "tool output and reviewers' answers")


def _is_tool_output(path):
    try:
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            return SENTINEL in fh.read(400)
    except OSError:
        return False


def scan_matter(cfg, only=None, tiers="ABCD", quiet=False, printer=print):
    """Returns a dict with rows, corpus facts and the tier grid."""
    t0 = time.time()
    packs = load_packs(cfg["citation_packs"])
    if not quiet:
        printer("citation packs: %s" % ", ".join(packs.ids))

    corpus = Corpus(cfg.source_dirs, skip_dirs=set(cfg["skip_dirs"]),
                    cache_dir=cfg.cache, quiet=quiet, sentinel=SENTINEL)
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
            elif any(c in corpus.joined for c in far_legal):
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
            "packs": packs, "seconds": round(time.time() - t0, 1),
            "tier_labels": {t: l for t, l, _p in cfg.draft_tiers}}


def _tier_of(row):
    ts = {s["tier"][0] for s in row["sites"]}
    for t in "ABCD":
        if t in ts:
            return t
    return "?"


def print_summary(res, lang="en", printer=print):
    grid = res["grid"]
    printer("\n%-22s %7s %7s %7s %7s" % ("verdict", "A filed", "B guides", "C research", "D tool"))
    for s in ORDER:
        n = sum(grid[t][s] for t in "ABCD")
        if not n:
            continue
        printer("%-22s %7d %7d %7d %7d"
                % (label(s, lang), grid["A"][s], grid["B"][s], grid["C"][s], grid["D"][s]))
    ab_bad = sum(grid[t][s] for t in "AB" for s in DANGEROUS)
    printer("\n🔴 needs a human in tiers A+B: %d" % ab_bad)

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
    return ab_bad


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
