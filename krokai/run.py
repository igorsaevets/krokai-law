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
from . import facts as facts_mod
from .citations import load_packs
from .corpus import Corpus, walk
from .extract import extract_quotes, citation_window, not_examined, _alnum_projection, _occurrences, _PARA_BREAK
from .readers import read_any, OCR_CHECK, ocr_pages_cell, ocr_label, PICTURE_ADVICE, picture_pages_cell
from .verdicts import ORDER, DANGEROUS, CLEAN, UNCHECKABLE, MEANING, MARK, label, meaning
from .verify import check, copies_check, page_of, split_join, zone_of

__all__ = ["scan_matter", "write_report", "print_not_examined", "print_markers", "draft_docs",
           "print_editions", "editions", "ocr_counts", "copy_counts", "copy_line",
           "SENTINEL", "SENTINELS", "SENTINEL_HEAD"]

SENTINEL = "KROKAI-TOOL-OUTPUT"

# 🔴 R77 (#F-C, grokbuild + agy37flash MAJOR, probe-proven): the sentinel window is a PACKAGE-WIDE
# constant, not a per-file literal. Three call sites - `run._is_tool_output`, `sidecar._current`
# and `exhibit_check._is_tool_output` - all read a fixed head window. Two of them said 400 while a
# third said 2000; a header offset was probed at 431 and the two 400-readers were blind to it.
# Named `SENTINEL_HEAD` and exported, with a suite pin that greps `\.read\(\d+\)` in krokai/*.py
# and hooks/*.py and asserts no literal below 2000 remains. The pin is what stops a fourth 400
# from appearing when someone forgets to import.
SENTINEL_HEAD = 2000

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
    # 🔴 Deliberate near-twin of `exhibit_check._is_tool_output`: same window (SENTINEL_HEAD),
    # different admission gate. This one classifies ANY draft file; the exhibit-check version
    # gates to .md/.txt so a sidecar beside its PDF is skipped without opening binaries. Unify
    # the WINDOW only, never the functions - a fork ageing in silence is the R76 lesson (F5).
    try:
        with io.open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(SENTINEL_HEAD)
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
    unexamined = []
    docs = []                                   # K027: every draft as read, for the marker pass
    fbank = os.path.normcase(os.path.abspath(cfg.abs(cfg["fact_bank"])))
    for tier, tlabel, root in cfg.draft_tiers:
        for p in walk([root], TARGET_EXT, set(cfg["skip_dirs"])):
            if only and only.lower() not in p.lower():
                continue
            if os.path.normcase(os.path.abspath(p)) == fbank:
                continue                        # K046: the fact bank holds evidence slices, not our writing
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
            docs.append((t, rel, body, _mtime(p)))
            # K023: what the extractor left out of THIS file - counted beside the verdicts, never
            # folded into them (see extract.not_examined for the incident and the exit-code rule).
            ne = not_examined(body, qs, packs, cfg["min_quote_length"],
                              cfg["drop_cyrillic_quotes"])
            unexamined.append({"tier": t, "file": rel, "examined": len(qs),
                               "short": ne["short"], "cyrillic": ne["cyrillic"],
                               "cited": ne["cited"]})
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
        ocr_cited = []
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
                # K024: a cited source whose text is an OCR layer puts cause 3 (an OCR misread)
                # ahead of fabrication - one wrong digit there hides a correct quotation.
                ocr_cited = sorted({os.path.relpath(p, cfg.root)
                                    for k in packs.keys(far_legal)
                                    for p in (keymap.resolve(k) or ()) if corpus.ocr_layer(p)})
                if ocr_cited:
                    kind += (" - but its text is an OCR layer (%s): rule out cause 3, an OCR "
                             "misread, first - %s" % ("; ".join(ocr_cited), OCR_CHECK))
            else:
                kind = "🟡 legal, but the cited authority is not in the corpus at all - probably a "\
                       "gap in the library, not a fabrication"

        # K025: the same question asked of every other copy of that document (advisory)
        copies = [{"file": os.path.relpath(c["path"], cfg.root), "share": c["share"],
                   "verdict": c["verdict"], "state": c["state"], "reading": c["reading"],
                   "reading_from": os.path.relpath(c["reading_from"], cfg.root)
                   if c["reading_from"] else ""}
                  for c in copies_check(rec["quote"], verdict, where, corpus)]
        rows.append({"verdict": verdict, "detail": detail, "quote": rec["quote"], "kind": kind,
                     "where": os.path.relpath(where, cfg.root) if where else "",
                     "where_abs": where or "",
                     "cites": near or far, "near": near, "sites": rec["sites"],
                     "address": address,
                     # K024: the source text this verdict was read from is an OCR layer
                     "ocr_layer": corpus.ocr_layer(where), "ocr_cited": ocr_cited,
                     # K018: the PDF page(s) the words stand on, or why no page can be named
                     "page": page_of(rec["quote"], where, corpus),
                     # K018c: the zone of a decision the words stand in (headnote / opinion / separate)
                     "zone": zone_of(rec["quote"], where, corpus),
                     "copies": copies})
        if not quiet and i % 200 == 0:
            printer("   ...%d/%d (%.0f s)" % (i, len(uniq), time.time() - t1))

    def fold_one(text, v, w, d, pieces):                         # K097: the address layer, joined
        near = sorted({c for row in pieces for c in row["near"] if packs.is_primary(c)})
        v, w, d, _a = addr_mod.fold(text, v, w, d, near, corpus, keymap, packs)
        return v, w, d
    splits = split_pass(rows, docs, corpus, fold_one, cfg.root)
    fres = facts_mod.check_docs(cfg, docs, packs)                 # K046: [F-nnn] sentences vs the fact bank

    rank = {s: i for i, s in enumerate(ORDER)}
    rows.sort(key=lambda r: (rank.get(r["verdict"], 99), -len(r["sites"])))

    # K027: open gap / conflict markers and the ones that vanished since the last check. The state is
    # READ here and only `cmd_check` writes it back - `mutate` also calls this function and must not.
    from .markers import analyse, load_state
    prev, perr = load_state(cfg.root)
    marks = analyse(docs, prev, tiers, only)
    marks["state_error"] = perr
    marks["prev"] = prev
    eds = editions(cfg, packs, unexamined)                        # K028

    grid = {t: {s: 0 for s in ORDER} for t in "ABCD"}
    for r in rows:
        grid[_tier_of(r)][r["verdict"]] += 1

    return {"rows": rows, "grid": grid, "per_file": per_file, "corpus": corpus, "splits": splits, "facts": fres,
            "docs": docs,                                         # K047: the drafts as read, for the reading list
            "not_examined": unexamined, "min_len": cfg["min_quote_length"], "markers": marks,
            "editions": eds,
            "drop_cyrillic": bool(cfg["drop_cyrillic_quotes"]),
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


# 🔴 K097 (2026-11-26): a quotation the drafter split in two is graded as the one quotation the reader
# reads. The incident, the measurement and why the join is strict: `verify.split_join`. Two more
# rules live here, each against a laundering:
#   * NEXT TO EACH OTHER: the other piece stands within SPLIT_NEAR characters of the drafter's own
#     text and no blank line separates them (the measured splits sat 4 and 45 characters apart; the
#     third pairing of the same two pieces, 1 870 characters away across paragraphs, is not one);
#   * AT EVERY PLACE: a quotation used twice - once beside its continuation, once alone - keeps its
#     alarm, because at the second place the condition is hidden; the detail names both places.
# The joined text goes through `check` and the address layer again, so a pair that still stops before
# a limiter, or starts after a negation, stays loud - about its OUTER edge, the one the reader sees.
SPLIT_NEAR = 300
SPLIT_MAX = 4                    # pieces in one chain («A» «B» «C» of one sentence)
_SPLIT_FROM = ("TRUNCATED_CONDITION", "TRUNCATED_OPENING")


def _draft_places(rows, docs):
    """{file: (body, [(start, end, row)])} - every occurrence of every quotation in every draft,
    wrap-proof (`extract._occurrences`); an occurrence inside a longer quotation's belongs to it."""
    places = {}
    for _t, rel, body, _m in docs:
        mine = [r for r in rows if any(s["file"] == rel for s in r["sites"])]
        if not mine:
            continue
        proj = _alnum_projection(body)
        occ = [(a, b, r) for r in mine for (a, b) in _occurrences(proj, r["quote"])]
        occ = [o for o in occ if not any(p[0] <= o[0] and o[1] <= p[1] and p[1] - p[0] > o[1] - o[0]
                                         for p in occ)]
        places[rel] = (body, sorted(occ, key=lambda o: o[0]))
    return places


def _chain(row, at, body, occ, corpus, fold_one):
    """Grow one place's chain of pieces while the joined quotation still points at its neighbour."""
    chain, text = [at], row["quote"]
    v, w, d = row["verdict"], row.get("where_abs") or None, row["detail"]
    while v in _SPLIT_FROM and len(chain) < SPLIT_MAX:
        tail_side = v == "TRUNCATED_CONDITION"
        edge = chain[-1] if tail_side else chain[0]
        best = None
        for o in occ:
            if any(o[2] is c[2] for c in chain):
                continue
            lo, hi = (edge[1], o[0]) if o[0] >= edge[1] else (o[1], edge[0])
            if hi < lo or hi - lo > SPLIT_NEAR or _PARA_BREAK.search(body[lo:hi]):
                continue
            j = (split_join(text, o[2]["quote"], corpus) if tail_side
                 else split_join(o[2]["quote"], text, corpus))
            if j and (best is None or hi - lo < best[0]):
                best = (hi - lo, o, j)
        if not best:
            break
        chain = chain + [best[1]] if tail_side else [best[1]] + chain
        text = best[2]
        v, w, d = check(text, corpus)
        v, w, d = fold_one(text, v, w, d, [c[2] for c in chain])
    return chain, v, w, d


def split_pass(rows, docs, corpus, fold_one, root):
    """K097: re-grade every truncation whose missing words the draft quotes right beside it. Returns
    the joins for REPORT.md and the console; changes the rows in place (verdict, where, detail, and
    `split` with what the piece was alone)."""
    if not any(r["verdict"] in _SPLIT_FROM for r in rows):
        return []
    rank = {s: i for i, s in enumerate(ORDER)}
    places = _draft_places(rows, docs)
    joins = []
    for r in rows:
        if r["verdict"] not in _SPLIT_FROM:
            continue
        done = [(rel, _chain(r, o, body, occ, corpus, fold_one))
                for rel, (body, occ) in sorted(places.items()) for o in occ if o[2] is r]
        joined = [(rel, c) for rel, c in done if len(c[0]) > 1]
        if not joined:
            continue
        others = []
        for _rel, c in joined:
            others += [p[2]["quote"] for p in c[0] if p[2] is not r and p[2]["quote"] not in others]
        with_ = "; ".join("«%s»" % (q if len(q) <= 90 else q[:87] + "…") for q in others[:3])
        files = sorted({rel for rel, _c in joined})
        alone = {"verdict": r["verdict"], "detail": r["detail"]}
        if len(joined) < len(done):
            r["detail"] = (r["detail"] + "; " if r["detail"] else "") + (
                "split quotation at %d of %d place(s): there (%s) the draft quotes the missing words "
                "right beside it - %s - but at the other place(s) this piece stands alone, so the "
                "alarm stays" % (len(joined), len(done), ", ".join("`%s`" % f for f in files), with_))
            r["split"] = {"places": len(joined), "of": len(done), "read_with": others, "files": files,
                          "verdict": r["verdict"]}
            joins.append({"pieces": [r["quote"]] + others, "files": files, "alone": alone["verdict"],
                          "verdict": r["verdict"], "places": len(joined), "of": len(done)})
            continue
        rel, (chain, v, w, d) = min(joined, key=lambda x: rank.get(x[1][1], 99))
        r["verdict"], r["where_abs"] = v, w or ""
        r["where"] = os.path.relpath(w, root) if w else ""
        r["detail"] = ("split quotation - read together with %s, quoted right beside it (%s): one "
                       "passage of the source cut in two, graded as one%s. Alone, this piece is %s: %s"
                       % (with_, ", ".join("`%s`" % f for f in files), " - " + d if d else "",
                          label(alone["verdict"]), alone["detail"][:200]))
        r["ocr_layer"] = corpus.ocr_layer(w) if w else False
        r["split"] = {"places": len(joined), "of": len(done), "read_with": others, "files": files,
                      "alone": alone, "verdict": v}
        joins.append({"pieces": [r["quote"]] + others, "files": files, "alone": alone["verdict"],
                      "verdict": v, "places": len(joined), "of": len(done)})
    return joins


def _splits_md(res, cap=40):
    """K097: REPORT.md's list of quotations graded together with the piece quoted beside them."""
    groups = {}
    for j in res.get("splits") or []:
        g = groups.setdefault(tuple(sorted(j["pieces"][:SPLIT_MAX])), {"alone": [], "j": j})
        g["alone"].append("%s → %s%s" % (label(j["alone"]), label(j["verdict"]),
                                         "" if j["places"] == j["of"] else
                                         " (alone at %d of %d places)" % (j["of"] - j["places"], j["of"])))
    if not groups:
        return []
    md = ["## Split quotations read together", "",
          "A quotation cut in pieces that stand right beside each other in the draft, with nothing but "
          "the source's own punctuation between them in the source. Alone, each piece stops before - "
          "or starts after - words the other piece quotes; together they are graded as one quotation, "
          "so a pair that still drops a condition at its outer edge stays flagged. A piece that also "
          "stands alone somewhere keeps its alarm.", ""]
    for pieces, g in list(groups.items())[:cap]:
        md.append("* %s - %s; `%s`" % (" + ".join("«%s»" % (q if len(q) <= 80 else q[:77] + "…")
                                                  for q in g["j"]["pieces"]), "; ".join(g["alone"]),
                                       "`, `".join(g["j"]["files"][:3])))
    if len(groups) > cap:
        md.append("* … and %d more (`result.json`: rows with `split`)" % (len(groups) - cap))
    return md + [""]


def _tier_of(row):
    ts = {s["tier"][0] for s in row["sites"]}
    for t in "ABCD":
        if t in ts:
            return t
    return "?"


def _pl(n, one, many):
    return "%d %s" % (n, one if n == 1 else many)


def _ne_counts(rec):
    """(short phrases, of them beside a citation, Cyrillic phrases, citing paragraphs)."""
    return (len(rec["short"]), sum(1 for s in rec["short"] if s["cites"]),
            len(rec["cyrillic"]), len(rec["cited"]))


def _ne_line(rec, min_len):
    s, sb, c, p = _ne_counts(rec)
    parts = []
    if s:
        parts.append("%s under %d characters (%d beside a citation of law)"
                     % (_pl(s, "quoted phrase", "quoted phrases"), min_len, sb))
    if c:
        parts.append("%s (drop_cyrillic_quotes is on)"
                     % _pl(c, "Cyrillic quoted phrase", "Cyrillic quoted phrases"))
    if p:
        parts.append("%s citing the law with no quotation beside the citation"
                     % _pl(p, "paragraph", "paragraphs"))
    return "%s examined · %s" % (_pl(rec["examined"], "quotation", "quotations"),
                                 ("NOT examined: " + " · ".join(parts)) if parts
                                 else "nothing skipped")


def print_not_examined(res, printer=print, limit=20):
    """Per file: how many quotations were examined and what was NOT (K023).

    Printed BEFORE the verdict table, so the verdicts and the «needs a human» count stay the last
    lines on screen. Tiers A and B file by file - what gets filed is where a silent gap costs -
    and tiers C and D as one line; REPORT.md carries every file. Returns nothing: these counts
    never reach the exit code (extract.not_examined says why)."""
    recs = res.get("not_examined") or []
    if not recs:
        return
    n = res.get("min_len") or 0
    ab = sorted((r for r in recs if r["tier"] in ("A", "B")),
                key=lambda r: (r["tier"], -(len(r["short"]) + len(r["cyrillic"])
                                            + len(r["cited"])), r["file"]))
    cd = [r for r in recs if r["tier"] not in ("A", "B")]
    printer("\nNOT examined - a clean verdict below says nothing about these "
            "(per file; the phrases and paragraphs are listed in REPORT.md):")
    for r in ab[:limit]:
        printer("  %s %s: %s" % (r["tier"], r["file"], _ne_line(r, n)))
    if len(ab) > limit:
        printer("  ... and %s in tiers A+B" % _pl(len(ab) - limit, "more file", "more files"))
    if cd:
        tot = [sum(_ne_counts(r)[i] for r in cd) for i in range(4)]
        printer("  tiers C+D, %s: %s examined · NOT examined: %s, %s, %s"
                % (_pl(len(cd), "file", "files"),
                   _pl(sum(r["examined"] for r in cd), "quotation", "quotations"),
                   _pl(tot[0], "short phrase", "short phrases"),
                   _pl(tot[2], "Cyrillic phrase", "Cyrillic phrases"),
                   _pl(tot[3], "paragraph citing the law without a quotation",
                       "paragraphs citing the law without a quotation")))


def _mtime(p):
    try:
        return os.path.getmtime(p)
    except OSError:
        return None


def draft_docs(cfg):
    """(tier, relative path, text, mtime) for every draft `check` reads, tool output as tier D.
    `close` reads the drafts through this to judge markers without running the whole check."""
    out = []
    for tier, _l, root in cfg.draft_tiers:
        for p in walk([root], TARGET_EXT, set(cfg["skip_dirs"])):
            try:
                body = read_any(p, cfg.cache)
            except Exception:                                      # noqa: BLE001
                continue
            out.append((TIER_D[0] if _is_tool_output(p) else tier, os.path.relpath(p, cfg.root),
                        body, _mtime(p)))
    return out


def print_markers(res, printer=print, limit=20):
    """K027: open gap / conflict markers per file, then every marker that vanished since the last check
    with the sentence now in its place. Returns nothing: markers never reach `check`'s exit code - a
    draft mid-work is SUPPOSED to carry them, and punishing them teaches the drafter to stop writing
    them (krokai/markers.py). `close` is the gate."""
    from .markers import count_line, gone_line
    mk = res.get("markers") or {}
    op, gone = mk.get("open") or [], mk.get("gone") or []
    if op:
        ab = [o for o in op if o["tier"] in ("A", "B")]
        rest = [o for o in op if o["tier"] not in ("A", "B")]
        printer("\nMarkers - gaps and conflicts the drafter flagged; a person closes each one, and "
                "`close` refuses while a filed (tier A) document carries one:")
        for o in ab[:limit]:
            printer("  %s %s: %s" % (o["tier"], o["file"], count_line(o)))
        if len(ab) > limit:
            printer("  ... and %s in tiers A+B" % _pl(len(ab) - limit, "more file", "more files"))
        if rest:
            printer("  tier C, %s: %s" % (_pl(len(rest), "file", "files"),
                                          _pl(sum(o["gap"] + o["conflict"] for o in rest),
                                              "open marker", "open markers")))
    if gone:
        printer("🔴 Markers GONE since the last check - read each: closed with evidence, or written "
                "over?")
        for g in gone:
            printer("  " + gone_line(g))


def _markers_md(res):
    from .markers import gone_line
    mk = res.get("markers") or {}
    op, gone = mk.get("open") or [], mk.get("gone") or []
    if not (op or gone):
        return []
    md = ["## Markers - gaps and conflicts flagged in the drafts", "",
          "`[MISSING: ...]` is the drafter saying the evidence runs out here; `[CONFLICT: ...]`, that "
          "two exhibits disagree. An open marker is not a defect of the draft - it is the honest "
          "alternative to fluent prose over a gap. A person closes each one; `krokai close` refuses "
          "while a filed (tier A) document carries one. These counts never change the exit code of "
          "`check`.", ""]
    if op:
        md += ["| tier | file | gaps | conflicts | open since |", "|---|---|---|---|---|"]
        for o in sorted(op, key=lambda o: (o["tier"], o["file"])):
            md.append("| %s | `%s` | %d | %d | %s |"
                      % (o["tier"], o["file"], o["gap"], o["conflict"], o["since"]))
        md.append("")
        for o in sorted(op, key=lambda o: (o["tier"], o["file"])):
            if o["tier"] in ("A", "B"):
                md += ["### %s · `%s`" % (o["tier"], o["file"]), ""]
                md += ["* %s" % t for t in o["markers"][:40]]
                if len(o["markers"]) > 40:
                    md.append("* ... and %d more" % (len(o["markers"]) - 40))
                md.append("")
    if gone:
        md += ["### 🔴 Gone since the last check", "",
               "Each line is a marker that is no longer there, with what stands in its place now. "
               "Read each: was the gap closed with evidence, or written over?", ""]
        md += ["* %s" % gone_line(g) for g in gone] + [""]
    return md


def editions(cfg, packs, recs):
    """K028: every provision the law register knows in more than one edition, the older editions
    whose index row carries no SUPERSEDED mark, and the draft paragraphs (tiers A+B) that cite one of
    those provisions WITHOUT a quotation. A quotation of an old edition is graded SUPERSEDED_EDITION;
    a paraphrase passes every string check, so these paragraphs are where one would hide - a reading
    list, never in the exit code (K023's rule for everything `check` did not examine)."""
    from .fetch import register_chains
    from .library import mark_superseded
    idx = cfg.abs(cfg["library_index"])
    rel = lambda p: os.path.relpath(p, cfg.root) if os.path.isabs(p) else p   # noqa: E731
    provs, unmarked = [], []
    for kid, addr, cur, chain, e in register_chains(cfg.root):
        eds = e.get("editions") or {}
        provs.append({"kid": kid, "address": addr, "current": rel(cur),
                      "current_date": e.get("edition_date") or "",
                      "older": [{"file": rel(p), "date": (eds.get(p) or {}).get("edition_date") or ""}
                                for p in chain]})
        n, _norow = mark_superseded(idx, [os.path.basename(p) for p in chain],
                                    os.path.basename(cur), dry_run=True)
        if n:
            unmarked.append({"address": addr, "rows": n})
    para = []
    kids = {p["kid"]: p["address"] for p in provs}
    for r in recs if kids else ():
        if r["tier"] not in ("A", "B"):
            continue
        for x in r["cited"]:
            hit = set()
            for c in x["cites"]:
                hit |= {"|".join(k) for k in packs.keys(packs.find(c))} & set(kids)
            if hit:
                para.append({"tier": r["tier"], "file": r["file"], "excerpt": x["excerpt"],
                             "provisions": sorted(kids[k] for k in hit)})
    return {"provisions": provs, "unmarked": unmarked, "paraphrases": para}


def _ed(d):
    return " (%s)" % d if d else ""


def print_editions(res, printer=print, limit=20):
    ed = res.get("editions") or {}
    provs = ed.get("provisions") or []
    if not provs:
        return
    printer("\nEditions - %s with an OLDER edition still on disk (law register); the older one is "
            "not the law now:" % _pl(len(provs), "provision", "provisions"))
    for p in provs[:limit]:
        printer("  %s · current `%s`%s · older %s" % (
            p["address"], p["current"], _ed(p["current_date"]),
            ", ".join("`%s`%s" % (o["file"], _ed(o["date"])) for o in p["older"][:4])))
    for u in ed.get("unmarked") or []:
        printer("  ⚠️ %s: %s with no SUPERSEDED mark in the index - `krokai intake` writes it"
                % (u["address"], _pl(u["rows"], "older edition row", "older edition rows")))
    para = ed.get("paraphrases") or []
    if para:
        printer("  %s cite a revised provision WITHOUT a quotation - a paraphrase passes every string "
                "check; compare each with the current edition:"
                % _pl(len(para), "paragraph", "paragraphs"))
        for x in para[:limit]:
            printer("     %s %s: «%s» (%s)" % (x["tier"], x["file"], x["excerpt"][:110],
                                             ", ".join(x["provisions"])))
        if len(para) > limit:
            printer("     ... and %d more (REPORT.md)" % (len(para) - limit))


def _editions_md(res):
    ed = res.get("editions") or {}
    provs = ed.get("provisions") or []
    if not provs:
        return []
    md = ["## Editions - revised provisions with an older edition on disk", "",
          "The older edition stays on disk on purpose: a quotation of it was correct when it was "
          "taken, and its verdict is SUPERSEDED_EDITION. A paraphrase of it passes every string check, "
          "so every paragraph below that cites a revised provision without a quotation needs a "
          "reading against the CURRENT edition. These lines never change the exit code.", "",
          "| provision | current edition | older editions |", "|---|---|---|"]
    for p in provs:
        md.append("| %s | `%s`%s | %s |" % (p["address"], p["current"], _ed(p["current_date"]),
                                            ", ".join("`%s`%s" % (o["file"], _ed(o["date"]))
                                                      for o in p["older"])))
    md.append("")
    for u in ed.get("unmarked") or []:
        md.append("* ⚠️ %s: %d older edition row(s) carry no SUPERSEDED mark in the index - "
                  "`krokai intake` writes it." % (u["address"], u["rows"]))
    para = ed.get("paraphrases") or []
    if para:
        md += ["", "### Paragraphs citing a revised provision without a quotation", ""]
        md += ["* %s `%s`: «%s» (%s)" % (x["tier"], x["file"], x["excerpt"], ", ".join(x["provisions"]))
               for x in para[:200]]
    return md + [""]


def _not_examined_md(res):
    recs = res.get("not_examined") or []
    if not recs:
        return []
    n = res.get("min_len") or 0
    md = ["## Not examined - what the verdicts in this report do not cover", "",
          "The verdicts are about the quotations of %d+ characters the extractor examined. A quoted "
          "phrase of two or more words under that length%s, and a paragraph that cites the law "
          "and carries no examined quotation (a heading, a line ending with a colon or a bare "
          "citation right before a quotation, and a bare citation line right after one, count "
          "as carrying it), were NOT examined: a clean "
          "verdict says nothing about them. These counts are "
          "a reading list, not a finding - they never change the exit code. A quoted single word "
          "is not counted." % (n, ", a Cyrillic phrase (drop_cyrillic_quotes is on)"
                               if res.get("drop_cyrillic") else ""), "",
          "| tier | file | examined | short phrases (beside a citation) | Cyrillic phrases | "
          "paragraphs citing the law, no quotation |", "|---|---|---|---|---|---|"]
    recs = sorted(recs, key=lambda r: (r["tier"], r["file"]))
    for r in recs:
        s, sb, c, p = _ne_counts(r)
        md.append("| %s | `%s` | %d | %d (%d) | %d | %d |"
                  % (r["tier"], r["file"], r["examined"], s, sb, c, p))
    md.append("")

    def capped(items, cap):
        return items[:cap] + (["* ... and %d more" % (len(items) - cap)]
                              if len(items) > cap else [])

    for r in recs:
        if r["tier"] not in ("A", "B") or not (r["short"] or r["cyrillic"] or r["cited"]):
            continue
        md += ["### %s · `%s`" % (r["tier"], r["file"]), ""]
        bes = [x for x in r["short"] if x["cites"]]
        oth = [x for x in r["short"] if not x["cites"]]
        if bes:
            md += ["Short quoted phrases BESIDE a citation of law - check each by hand: "
                   "`krokai quote \"<phrase>\"`, then confirm the file it names is the provision "
                   "you cite:", ""]
            md += capped(['* "%s" - %s' % (x["text"], "; ".join(x["cites"])) for x in bes], 25)
            md.append("")
        if oth:
            md += ["Other short quoted phrases:", ""]
            md += capped(['* "%s"' % x["text"] for x in oth], 15) + [""]
        if r["cyrillic"]:
            md += ["Cyrillic quoted phrases (skipped because drop_cyrillic_quotes is on):", ""]
            md += capped(["* «%s»" % x for x in r["cyrillic"]], 10) + [""]
        if r["cited"]:
            md += ["Paragraphs citing the law with no examined quotation beside the citation - "
                   "what they say about the law rests on the reader, not on this check:", ""]
            md += capped(["* %s - %s" % ("; ".join(x["cites"]), x["excerpt"])
                          for x in r["cited"]], 25)
            md.append("")
    return md


def ocr_counts(res):
    """K024: tier A+B rows read from an OCR text layer - clean, flagged, and NOT_FOUND whose cited
    source is one. One function, so the console line and REPORT.md cannot disagree."""
    out = {"clean": 0, "flagged": 0, "not_found": 0, "rows": [], "files": 0}
    files = set()
    for r in res["rows"]:
        if _tier_of(r) not in ("A", "B"):
            continue
        if r.get("ocr_layer"):
            files.add(r["where"])
            out["rows"].append(r)
            out["clean" if r["verdict"] in CLEAN else "flagged"] += 1
        elif r.get("ocr_cited"):
            out["rows"].append(r)
            out["not_found"] += 1
    out["files"] = len(files)
    return out


def _ocr_md(res, root, cap=60):
    o = ocr_counts(res)
    c = res["corpus"]
    ocr_files = c.ocr_files() if hasattr(c, "ocr_files") else []
    if not (o["rows"] or ocr_files):
        return []
    md = ["## Read from an OCR text layer - tiers A+B: %d clean, %d flagged, %d NOT FOUND"
          % (o["clean"], o["flagged"], o["not_found"]), "",
          "These verdicts were read from text an OCR engine produced from a scanned page, not from "
          "typeset text. A misread digit or name in that layer makes a wrong quotation verify and a "
          "right one fail. For each: %s. A flagged one may be the OCR's misread, not the drafter's "
          "- do not change the quotation to match the layer. (Advisory: the verdicts and the exit "
          "code are unchanged.)" % OCR_CHECK, ""]
    for r in o["rows"][:cap]:
        f = r["where"] or "; ".join(r.get("ocr_cited") or [])
        lay = r.get("ocr_layer")
        md += ["* **[%s] %s** · %s · `%s`%s" % (_tier_of(r), r["verdict"],
                                                "; ".join(r["cites"]) if r["cites"] else "no citation",
                                                f, " (%s)" % ocr_pages_cell(lay) if lay else ""),
               "  > %s" % r["quote"][:200].replace("\n", " "), ""]
    if len(o["rows"]) > cap:
        md += ["* … and %d more - `result.json` rows carry `ocr_layer` / `ocr_cited`"
               % (len(o["rows"]) - cap), ""]
    if ocr_files:
        md += ["Sources in the corpus whose text is an OCR layer - %d:" % len(ocr_files), ""]
        md += ["* `%s` (%s)" % (os.path.relpath(p, root), ocr_pages_cell(f))
               for p, f in ocr_files[:cap]]
        if len(ocr_files) > cap:
            md += ["* … and %d more (`krokai library`)" % (len(ocr_files) - cap)]
        md += [""]
    return md


def copy_counts(res):
    """K025: tier A+B rows whose source has another copy on the disk - those that read differently
    there (``disagree``) and those every copy confirms (``confirmed``). One function, so the console
    line and REPORT.md cannot disagree."""
    out = {"disagree": 0, "confirmed": 0, "rows": [], "files": 0}
    files = set()
    for r in res["rows"]:
        cs = r.get("copies") or []
        if _tier_of(r) not in ("A", "B") or not cs:
            continue
        if any(c["state"] == "disagree" for c in cs):
            out["disagree"] += 1
            out["rows"].append(r)
            files.add(r["where"])
        elif any(c["state"] == "agree" for c in cs):
            out["confirmed"] += 1
    out["files"] = len(files)
    return out


def copy_line(c, where):
    """K025: one copy's answer in words - the same sentence on the console, in REPORT.md and in
    `quote`, so the three cannot drift."""
    if c["state"] == "agree":
        return "`%s` reads it the same way (%s)" % (c["file"], c["verdict"])
    if c["state"] == "absent":
        return "`%s` does not hold this passage (%s)" % (c["file"], c["verdict"])
    pairs = "; ".join("quoted «%s», `%s` reads «%s»" % (q or "-", c["reading_from"], s or "-")
                      for q, s in (c.get("reading") or [])[:4])
    return ("`%s` gives %s where `%s` gives the verdict above%s"
            % (c["file"], c["verdict"], where, (" - " + pairs) if pairs else ""))


def _copies_md(res, cap=60):
    o = copy_counts(res)
    if not (o["disagree"] or o["confirmed"]):
        return []
    md = ["## Copies disagree - tiers A+B: %d quotation(s)" % o["disagree"], "",
          "The same document is on this disk more than once, and one of the copies is an OCR text "
          "layer (a second OCR run of one scan, the text extracted beside its PDF). These quotations "
          "read one way in one copy and another way in the other: one of the two copies is an OCR "
          "misread, and only the page image can say which. A clean verdict here rests on the copy "
          "that happened to be read. (Advisory: the verdicts and the exit code are unchanged.)", ""]
    for r in o["rows"][:cap]:
        md += ["* **[%s] %s** · %s · `%s`" % (_tier_of(r), r["verdict"],
                                              "; ".join(r["cites"]) if r["cites"] else "no citation",
                                              r["where"]),
               "  > %s" % r["quote"][:200].replace("\n", " ")]
        md += ["  * %s" % copy_line(c, r["where"]) for c in r["copies"]]
        md += [""]
    if len(o["rows"]) > cap:
        md += ["* … and %d more - `result.json` rows carry `copies`" % (len(o["rows"]) - cap), ""]
    if o["confirmed"]:
        md += ["Read the same way in every copy of their source: %d quotation(s) - a second reading "
               "of the same page agrees (it is not an independent source: a typo on the page is in "
               "both)." % o["confirmed"], ""]
    return md


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

    # K024: advisory, never in the returned counts (the exit code): which verdicts were read from
    # an OCR layer - a clean one may rest on a misread digit, a flagged one may BE the misread.
    o = ocr_counts(res)
    if o["clean"]:
        printer("🟡 OCR TEXT LAYER, tiers A+B: %d clean quotation(s) matched what an OCR engine read "
                "(%d file(s)) - %s. REPORT.md lists them." % (o["clean"], o["files"], OCR_CHECK))
    if o["flagged"]:
        printer("🟡 OCR TEXT LAYER, tiers A+B: %d flagged quotation(s) were compared with an OCR "
                "layer - the difference may be the OCR's misread, not the drafter's: compare with "
                "the page image before changing the quotation." % o["flagged"])
    if o["not_found"]:
        printer("🟡 OCR TEXT LAYER, tiers A+B: %d NOT FOUND cite a source whose text is an OCR layer "
                "- rule out cause 3 (an OCR misread) before fabrication." % o["not_found"])
    # K096: advisory as well - a NOT FOUND may quote a picture's words that were never in the text.
    nf = sum(1 for r in res["rows"] if r["verdict"] == "NOT_FOUND")
    pics = res["corpus"].picture_files() if hasattr(res["corpus"], "picture_files") else []
    if nf and pics:
        printer("🟡 PICTURE PAGES: %d indexed file(s) have pages whose words are in a picture, not in "
                "the text - %d NOT FOUND may quote one of them (REPORT.md lists the pages)."
                % (len(pics), nf))
    # K097: a quotation cut in two pieces that stand beside each other is graded as one.
    sp = res.get("splits") or []
    if sp:
        printer("ℹ SPLIT QUOTATIONS: %d quotation(s) are pieces of one source passage quoted right beside "
                "each other - graded together (%d at every place they are used); REPORT.md «Split "
                "quotations read together» lists them." % (len(sp), sum(1 for j in sp if j["places"] == j["of"])))
    # K046: sentences that cite the fact bank - a red one in tiers A+B counts in the exit code below.
    for ln in facts_mod.console_lines(res.get("facts")):
        printer(ln)
    ab_bad += facts_mod.red_count(res.get("facts"))
    # K025: advisory too - a quotation that reads differently in another copy of its source.
    cc = copy_counts(res)
    if cc["disagree"]:
        printer("🟡 COPIES DISAGREE, tiers A+B: %d quotation(s) read differently in another copy of "
                "the same document (%d file(s)) - one of the copies is an OCR misread: compare both "
                "with the page image. REPORT.md shows both readings." % (cc["disagree"], cc["files"]))
    if cc["confirmed"]:
        printer("✅ SECOND COPY, tiers A+B: %d quotation(s) read the same way in every copy of their "
                "source." % cc["confirmed"])

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
    md += _not_examined_md(res)
    md += _markers_md(res)
    md += _editions_md(res)
    md += _ocr_md(res, cfg.root)                                  # K024
    md += _copies_md(res)                                         # K025
    md += _splits_md(res)                                         # K097
    md += facts_mod.report_md(res.get("facts"))                   # K046

    if c.excluded_derived:
        md += ["## Excluded from the corpus as our own derived text", "",
               "If a primary source is in this list, fix the pattern - do not stay silent.", ""]
        md += ["* `%s`" % os.path.relpath(p, cfg.root) for p in c.excluded_derived] + [""]
    if c.excluded_stub:
        md += ["## Corpus files with no text layer", "",
               "A scan without OCR, or a stub. A quotation from these yields a FALSE miss. "
               "🔴 Run them through a real OCR engine - never a language model.", ""]
        why = getattr(c, "stub_why", {})                              # K093: the reason, per file
        md += ["* `%s`%s" % (os.path.relpath(p, cfg.root), " - %s" % why[p] if why.get(p) else "")
               for p in c.excluded_stub] + [""]
    pics = c.picture_files() if hasattr(c, "picture_files") else []        # K096
    if pics:
        md += ["## Indexed files with picture pages", "",
               "These files ARE searched - but on the pages named here %s." % PICTURE_ADVICE, ""]
        md += ["* `%s` - %s; page %d: %s" % (os.path.relpath(p, cfg.root), picture_pages_cell(f),
                                               f["flagged"][0][0], f["flagged"][0][1]) for p, f in pics[:60]]
        if len(pics) > 60:
            md += ["* … and %d more (`krokai library`; `result.json` `picture_pages`)" % (len(pics) - 60)]
        md += [""]

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
        if st == "NOT_FOUND" and pics:                                # K096: cause 3, live here
            md += ["🟡 %d indexed file(s) have PICTURE PAGES (listed under «Indexed files with picture "
                   "pages»): a quotation of a picture's words reads NOT FOUND here - look at those pages "
                   "before calling a quotation invented." % len(pics), ""]
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
                md += ["", "Found in: `%s`%s%s" % (r["where"], " - %s" % r["page"]["label"]
                                                   if r.get("page") else "",
                                                   " · %s" % r["zone"]["label"] if r.get("zone") else "")]
                if r.get("ocr_layer"):
                    md += ["", "🟡 %s. The difference may be the OCR's misread, not the drafter's."
                           % ocr_label(r["ocr_layer"])]
                for cp in r.get("copies") or []:
                    if cp["state"] == "disagree":
                        md += ["", "🟡 COPIES DISAGREE: %s." % copy_line(cp, r["where"])]
            md += [""]

    report_md = os.path.join(out_dir, "REPORT.md")
    io.open(report_md, "w", encoding="utf-8", newline="\n").write("\n".join(md))

    payload = {"generated_by": SENTINEL,
               "rows": [{k: v for k, v in r.items() if k not in ("where_abs",)}
                        for r in res["rows"]],
               "grid": grid, "per_file": res["per_file"],
               "not_examined": res.get("not_examined") or [],
               "markers": {k: (res.get("markers") or {}).get(k) or [] for k in ("open", "gone")},
               "editions": res.get("editions") or {},
               "corpus_files": len(c.paths),
               "corpus_derived": [os.path.relpath(p, cfg.root) for p in c.excluded_derived],
               "corpus_no_text_layer": [os.path.relpath(p, cfg.root) for p in c.excluded_stub],
               "ocr_layers": [dict(f, file=os.path.relpath(p, cfg.root))
                              for p, f in (c.ocr_files() if hasattr(c, "ocr_files") else [])],
               # K096: pages whose words are in a picture or drawn as shapes, not in the text
               "picture_pages": [{"file": os.path.relpath(p, cfg.root), "pages": [n for n, _w in f["flagged"]],
                                  "of": f["pages"], "why": {str(n): w for n, w in f["flagged"]}}
                                 for p, f in pics],
               "copies": {k: v for k, v in copy_counts(res).items() if k != "rows"},
               # K046: every [F-nnn] reference of the drafts, graded against the fact bank
               "facts": (res.get("facts") or {}).get("refs") or [],
               "seconds": res["seconds"]}
    json.dump(payload, io.open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    # K047: every quotation of the filed tier beside its source passage - flagged first, then the rest by the
    # facts noted (reading.py says why there is no verdict label beside a clean one). Written on EVERY run,
    # a clean one included: the clean quotations are the ones nobody opens again.
    from . import reading as reading_mod
    entries = reading_mod.build(res)
    rpath, rcounts = reading_mod.write(entries, out_dir, lang, SENTINEL)
    res["reading"] = dict(rcounts, file=rpath)
    res["reading_entries"] = entries            # K061b: `check --judge` reorders these; in memory only, never saved
    return report_md
