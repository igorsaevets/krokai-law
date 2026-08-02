# -*- coding: utf-8 -*-
"""`krokai <command>` - everything the toolkit does, from one entry point.

Design note: every command that can be wrong about the world prints **what it looked at**, not just
its conclusion. A checker whose output is a single number teaches you to trust the number; a checker
that says "42 source files, 3 of them with no text layer, 2 excluded as your own writing" lets you
notice that the folder you meant is not the folder it read.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

from . import __version__

if hasattr(sys.stdout, "reconfigure"):
    # Without this, output goes out in the console's legacy code page on Windows and any non-ASCII
    # verdict arrives as mojibake - i.e. the warning is unreadable exactly where it is needed.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# ---------------------------------------------------------------------------------- init
def cmd_init(a):
    from .config import TEMPLATE, CONFIG_NAME
    from .bank import BANK_HEADER
    from .library import INDEX_HEADER

    root = os.path.abspath(a.path or ".")
    cfgp = os.path.join(root, CONFIG_NAME)
    if os.path.exists(cfgp) and not a.force:
        print("%s already exists. Nothing was touched. Use --force to overwrite." % cfgp)
        return 1

    made = []
    for rel in ("law", "case", "guides", "research"):
        d = os.path.join(root, rel)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            made.append(rel + "/")

    json.dump(TEMPLATE, io.open(cfgp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    made.append(CONFIG_NAME)

    for rel, header in (("case/QUOTE-BANK.md", BANK_HEADER),
                        ("law/INDEX.md", INDEX_HEADER)):
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, "w", encoding="utf-8", newline="\n").write(header)
            made.append(rel)

    print("created in %s:" % root)
    for m in made:
        print("   %s" % m)
    print("""
Next:
  1. Put PRIMARY SOURCES in law/  - statutes, regulations, decisions, agency manuals AS PUBLISHED.
     🔴 Nothing of your own in there. A quotation copied out of your own memo would otherwise
     verify against your own memo, and a mistake made once would validate itself forever.
  2. Put your drafts in case/ (what gets filed), guides/ and research/.
  3. krokai sidecar      - so grep can see inside your PDFs
  4. krokai check        - the whole-matter pass
  5. krokai install-hooks - so steps 3-4 stop depending on anyone remembering them
""")
    return 0


# --------------------------------------------------------------------------------- check
def cmd_check(a):
    from .config import load
    from .run import scan_matter, print_summary, write_report

    cfg = load(a.dir)
    for kind, p in cfg.missing_paths():
        print("🔴 configured %s folder does not exist: %s" % (kind, p))
    res = scan_matter(cfg, only=a.only, tiers=a.tiers, quiet=a.quiet)
    if res is None:
        return 2
    bad = print_summary(res, cfg["language"])
    out = a.out or os.path.join(cfg.root, "reports",
                                "check-" + __import__("time").strftime("%Y-%m-%d-%H%M"))
    path = write_report(res, cfg, out, cfg["language"])
    print("\nreport -> %s" % path)
    print("took %.0f s" % res["seconds"])
    return 1 if (bad and a.strict) else 0


# --------------------------------------------------------------------------------- quote
def cmd_quote(a):
    """One quotation, one answer. The command you run before pasting something into a document."""
    from .config import load
    from .corpus import Corpus
    from .verify import check
    from .verdicts import label, meaning

    cfg = load(a.dir)
    text = a.text
    if a.file:
        text = io.open(a.file, encoding="utf-8", errors="replace").read()
    if not text:
        print("give a quotation as an argument, or --file")
        return 2
    corpus = Corpus(cfg.source_dirs, skip_dirs=set(cfg["skip_dirs"]),
                    cache_dir=cfg.cache, quiet=a.quiet)
    verdict, where, detail = check(text, corpus)
    lang = cfg["language"]
    print("\n%s" % label(verdict, lang).upper())
    print("  %s" % meaning(verdict, lang))
    if where:
        print("  found in: %s" % os.path.relpath(where, cfg.root))
    if detail:
        print("  %s" % detail)
    if verdict == "NOT_FOUND":
        print("""
🔴 NOT FOUND is not the same as INVENTED. Rule them out in this order, and only the last one is a
   defect in the quotation:
     1. THE CORPUS IS INCOMPLETE. It is a set of downloads and can be silently missing text.
        Measured: a scraped agency chapter held four of its six bullet points. Open the live page.
     2. THE EXTRACTION IS BROKEN. Check with a second PDF engine - one splits words ("resu lt")
        while the PDF has them whole.
     3. YOUR OWN NORMALISATION. Strip the blockquote marker, the bold, the line wrap, and re-search.
     4. Only now: the quotation is altered.""")
    return 0 if verdict == "VERIFIED" else 1


# ---------------------------------------------------------------------------------- bank
def cmd_bank(a):
    from .config import load
    from .bank import read_bank, queue_open_items, in_bank

    cfg = load(a.dir)
    bank_path = cfg.abs(cfg["bank"])
    bank = read_bank(bank_path)
    entries = bank.count("\n### ")
    print("quote bank: %s" % bank_path)
    print("  %d entr%s, %d bytes" % (entries, "y" if entries == 1 else "ies", len(bank.encode())))
    todo = bank.count("TO DO")
    if todo:
        print("  🔴 %d entr%s still say TO DO - most often the 'what this does NOT prove' field, "
              "which is the one that catches a dropped proviso" % (todo, "y" if todo == 1 else "ies"))
    op, done, items = queue_open_items(cfg.abs(cfg["queue"]))
    print("queue: %d open, %d closed" % (op, done))
    for it in items[:20]:
        print("   • %s" % it)
    if a.text:
        print("\nin bank: %s" % ("yes" if in_bank(a.text, bank) else "NO"))
    return 0


# ------------------------------------------------------------------------------- sidecar
def cmd_sidecar(a):
    from .config import load
    from .sidecar import build
    cfg = load(a.dir)
    build(cfg.source_dirs, force=a.force, dry_run=a.dry_run, cache_dir=cfg.cache)
    return 0


# ------------------------------------------------------------------------------- library
def cmd_library(a):
    from .config import load
    from .library import orphans, RECIPES
    cfg = load(a.dir)
    idx = cfg.abs(cfg["library_index"])
    if a.recipes:
        print("Retrieval recipes that were established by measurement:\n")
        for what, how, note in RECIPES:
            print("  %s\n     %s\n     %s\n" % (what, how, note))
        return 0
    unindexed, missing = orphans(cfg.source_dirs, idx)
    print("library index: %s" % idx)
    print("  %d file(s) on disk but NOT in the index" % len(unindexed))
    for p in unindexed[:40]:
        print("     %s" % os.path.relpath(p, cfg.root))
    if len(unindexed) > 40:
        print("     ... and %d more" % (len(unindexed) - 40))
    print("  %d index row(s) whose file is gone" % len(missing))
    for p in missing[:20]:
        print("     %s" % p)
    if unindexed or missing:
        print("\nAn unindexed source gets downloaded again next round, and its absence turns an "
              "honest quotation into a NOT_FOUND that reads like a fabrication.")
    return 0


# -------------------------------------------------------------------------------- mutate
def cmd_mutate(a):
    from .config import load
    from .corpus import Corpus
    from .run import scan_matter
    from .mutations import run as run_mut

    cfg = load(a.dir)
    if a.report:
        data = json.load(io.open(os.path.join(a.report, "result.json"), encoding="utf-8"))
        base = [(r["quote"], r["where"]) for r in data["rows"] if r["verdict"] == "VERIFIED"]
        corpus = Corpus(cfg.source_dirs, skip_dirs=set(cfg["skip_dirs"]),
                        cache_dir=cfg.cache, quiet=True)
    else:
        res = scan_matter(cfg, quiet=True)
        if res is None:
            return 2
        base = [(r["quote"], r["where"]) for r in res["rows"] if r["verdict"] == "VERIFIED"]
        corpus = res["corpus"]
    stats, _rows = run_mut(base, corpus, limit=a.limit)
    holes = sum(s["missed"] for s in stats.values())
    return 1 if (holes and a.strict) else 0


# ---------------------------------------------------------------------------------- gate
def cmd_gate(a):
    from .redact import gate, self_test
    if a.self_test:
        return 0 if self_test() else 1
    parts = []
    for p in a.files:
        parts.append((os.path.basename(p), io.open(p, encoding="utf-8", errors="replace").read()))
    if not parts:
        parts = [("stdin", sys.stdin.read())]
    return gate(parts, allow_pii=a.allow_pii)


# --------------------------------------------------------------------------------- brief
def cmd_brief(a):
    from .prompts import build_brief, anchor_warnings, RESEARCH_SYSTEM, CANARY_NOTE
    question = a.question
    if a.file:
        question = io.open(a.file, encoding="utf-8", errors="replace").read()
    material = io.open(a.material, encoding="utf-8", errors="replace").read() if a.material else ""
    text = build_brief(question, material, marker=a.marker, tools=not a.no_tools,
                       canary=CANARY_NOTE if a.canary else None)

    warns = anchor_warnings(question)
    if warns:
        print("🔴 ANCHORING in the question - fix before sending:\n")
        for why, frag in warns:
            print("   %s" % why)
            if frag:
                print("      …%s…" % frag)
        print("\nWhy this matters: consensus among reviewers is NOT confirmation when you wrote the "
              "question. Measured - a question with a fragment of the expected answer inside it got "
              "five channels to return the asker's own mistake, which read as strong agreement.\n")
    if a.system:
        io.open(a.system, "w", encoding="utf-8", newline="\n").write(RESEARCH_SYSTEM)
        print("system prompt -> %s" % a.system)
    if a.out:
        io.open(a.out, "w", encoding="utf-8", newline="\n").write(text)
        print("brief -> %s (%d chars)" % (a.out, len(text)))
    else:
        print(text)
    return 1 if (warns and a.strict) else 0


# -------------------------------------------------------------------------------- review
def cmd_review(a):
    """Ask several outside models the same question, then check every quotation they send back.

    ONE command, not two. An earlier draft had `review` for the brief and `consult` for the
    dispatch, which is two names for one job - the same two-homes-for-one-subject defect this
    toolkit exists to measure. The dispatch lives in `consult.py`; the verb the user types is
    `review`, because that is what they are doing.
    """
    from .config import load
    from .consult import load_registry, find_harness, run_round, selected, plan
    from .review import prepare, audit_answers

    cfg = load(a.dir)
    out = os.path.abspath(a.out or os.path.join(cfg.root, "reviews", "round"))

    def _audit(folder):
        from .corpus import Corpus
        from .citations import load_packs
        corpus = Corpus(cfg.source_dirs, skip_dirs=set(cfg["skip_dirs"]),
                        cache_dir=cfg.cache, quiet=True)
        return audit_answers(folder, corpus, load_packs(cfg["citation_packs"]),
                             cfg["min_quote_length"])

    if a.audit:
        _audit(os.path.abspath(a.audit))
        return 0

    reg = load_registry(a.registry, start=cfg.root)
    harness = find_harness(reg, a.harness)

    if a.channels:
        # What COULD run here, including what is switched off, so "why is my channel not running"
        # has an answer that does not require reading JSON.
        plan(reg, selected(reg, with_disabled=True), harness=harness)
        return 0

    question = a.question
    if a.file:
        question = io.open(a.file, encoding="utf-8", errors="replace").read()
    if not question:
        print("give a question, or --file, or --audit <folder>, or --channels")
        return 2
    material = io.open(a.material, encoding="utf-8", errors="replace").read() if a.material else ""

    # The gate runs here, on the brief AND the system prompt, before the registry is even consulted.
    made = prepare(question, material, out_dir=out, marker=a.marker, tools=not a.no_tools,
                   canary=a.canary, allow_pii=a.allow_pii)
    if not made:
        return 3
    bp, sp = made
    if a.prepare_only:
        print("\n--prepare-only: nothing was sent.")
        return 0

    brief = io.open(bp, encoding="utf-8").read()
    system = io.open(sp, encoding="utf-8").read()
    rows, out = run_round(reg, system, brief, out, marker=a.marker,
                          only=tuple(a.only or ()), skip=tuple(a.skip or ()),
                          harness=harness, use_harness=not a.no_harness,
                          harness_args=tuple(a.harness_args or ()),
                          allow_pii=a.allow_pii, dry_run=a.dry_run)
    if a.dry_run or not rows:
        return 0

    print("\n--- checking the reviewers' quotations against YOUR corpus ---")
    _audit(out)
    return 1 if any(r["verdict"] == "FAILED" for r in rows) else 0


# ---------------------------------------------------------------------------------- keys
def cmd_keys(a):
    """Where an API key should live, whether it is there, and how to put it there safely.

    🔴 This command exists so that "is my key set?" has an answer that is not "open the file".
    Opening the file is how a key reaches a transcript - and a transcript is written to disk,
    replayed into later context, and archived.
    """
    from .keys import key_dir, key_file, load_key_file, status, console_recipe, FOLDER_NOTE
    from .consult import load_registry, channel_items

    reg = load_registry(getattr(a, "registry", None))
    wanted = []
    for name, ch in sorted(channel_items(reg)):
        for var in (ch.get("key_env"), ch.get("key_env_fallback")):
            if var and not any(v == var for v, _ in wanted):
                wanted.append((var, name))

    if a.setup:
        d = key_dir()
        os.makedirs(d, exist_ok=True)
        note = os.path.join(d, "READ-THIS-NOT-THE-KEYS.md")
        io.open(note, "w", encoding="utf-8", newline="\n").write(FOLDER_NOTE)
        kf = key_file()
        if os.path.exists(kf):
            # 🔴 Never overwrite. A "template" written over a populated key file destroys the
            # credentials and looks like a successful setup.
            print("kept your existing %s untouched" % kf)
        else:
            lines = ["# One key per line: NAME=value. No quotes, no spaces around `=`.",
                     "# A key already set in your environment WINS over a line here.",
                     "# Never commit this file. Never paste it into a chat window.", ""]
            lines += ["# %s" % v for v, _c in wanted]
            io.open(kf, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
            print("created %s - empty, with the variable NAMES as comments and no values" % kf)
        print("wrote   %s" % note)
        print("")
        print("🔴 That folder is OUTSIDE your matter on purpose, so an assistant working in the")
        print("   matter does not meet it by accident. It is the SECOND-strongest place for a key.")
        print("   The strongest is not a file at all - see below.")
        print("")

    loaded = load_key_file()
    exists = os.path.exists(key_file())
    print("key file : %s%s" % (key_file(), "" if exists else "   (none - that is fine)"))
    if loaded:
        print("           supplied %d variable(s) not already in your environment" % len(loaded))
    print("")
    print("%-28s %-12s %-6s %s" % ("variable", "channel", "set?", "length"))
    missing = []
    for var, ch_name in wanted:
        _n, is_set, ln = status([var])[0]
        # 🔴 The LENGTH, never a prefix, never a masked form. A "mask" that kept the first 60
        # characters of a 48-character key printed the whole key. That is why this column is an
        # integer and why there is no --show flag anywhere in this program.
        print("%-28s %-12s %-6s %s" % (var, ch_name, "yes" if is_set else "no",
                                       ln if is_set else "-"))
        if not is_set:
            missing.append(var)

    if missing and a.how:
        print("")
        print("=" * 76)
        print("SETTING A KEY WITHOUT ANY ASSISTANT EVER SEEING IT")
        print("=" * 76)
        print("Type these yourself in a terminal. Do NOT ask an assistant to run them for you:")
        print("the value would then be in the conversation, which is the thing being avoided.")
        for var in missing[:4]:
            print("")
            print("  %s" % var)
            for line in console_recipe(var):
                print(("  " + line) if line else "")
        if len(missing) > 4:
            print("")
            print("  ... and %d more; the pattern is the same." % (len(missing) - 4))
        print("")
        print("Easier and slightly weaker: put them in the key file above (`krokai keys --setup`).")
    elif missing:
        print("")
        print("%d not set. `krokai keys --how` prints the exact command for your system."
              % len(missing))
    else:
        print("")
        print("All set. Nothing above showed a key, and nothing in this toolkit ever will.")
    return 0


# --------------------------------------------------------------------------------- close
def cmd_close(a):
    """Mechanical end-of-round checks. Changes nothing; prints. The decision stays human."""
    from .config import load
    from .bank import queue_open_items
    from .library import orphans

    cfg = load(a.dir)
    ok = True

    op, done, items = queue_open_items(cfg.abs(cfg["queue"]))
    print("[1] quote queue: %d open, %d closed  %s" % (op, done, "OK" if not op else "🔴 CLEAR IT"))
    for it in items[:15]:
        print("      • %s" % it)
    if op:
        print("      Closing a line = bank it (address · file on disk · what it does NOT prove),")
        print("      or tick it and write one line saying why the matter does not need it.")
        ok = False

    unindexed, missing = orphans(cfg.source_dirs, cfg.abs(cfg["library_index"]))
    print("\n[2] library index: %d unindexed file(s), %d dead row(s)  %s"
          % (len(unindexed), len(missing), "OK" if not (unindexed or missing) else "🔴"))
    if unindexed or missing:
        ok = False

    from .sidecar import SUFFIX
    from .corpus import walk
    pdfs = list(walk(cfg.source_dirs, (".pdf",)))
    without = [p for p in pdfs if not os.path.exists(p[:-4] + SUFFIX)]
    print("\n[3] PDF sidecars: %d of %d PDFs have none  %s"
          % (len(without), len(pdfs), "OK" if not without else "🔴 grep is blind to these"))
    if without:
        ok = False

    from .redact import self_test
    print("\n[4] outbound gate")
    if not self_test(printer=lambda s: print("      " + s)):
        ok = False

    print("\n%s" % ("ALL CLEAR" if ok else "🔴 there are things to decide - see above"))
    return 0 if ok else 1


# -------------------------------------------------------------------------------- doctor
def cmd_doctor(a):
    from .readers import engines_available
    from .citations import available_packs
    from .config import find_config
    from .redact import self_test, SECRET_PATTERNS, PII_PATTERNS

    print("krokai %s" % __version__)
    print("python  %s" % sys.version.split()[0])
    print("packs   %s" % ", ".join(available_packs()))
    print("gate    %d secret + %d personal detectors" % (len(SECRET_PATTERNS), len(PII_PATTERNS)))

    eng = engines_available()
    print("\noptional libraries - each one absent means a whole file type reads as empty:")
    for name, present in sorted(eng.items()):
        print("   %-10s %s" % (name, "installed" if present else
                               "MISSING  (pip install %s)" % name.lower()))
    if not eng.get("pypdf") and not eng.get("PyMuPDF"):
        print("   🔴 With no PDF engine at all, every PDF in your library is invisible and every "
              "quotation from one comes back NOT FOUND. Install at least one.")
    if eng.get("pypdf") and not eng.get("PyMuPDF"):
        print("   🟡 Only one PDF engine. The cross-check that catches a word-splitting extraction "
              "needs two; measured, a single engine inflated one opinion by 51 % in broken tokens.")

    cfg_path = find_config(a.dir)
    print("\nconfig  %s" % (cfg_path or "NOT FOUND - run `krokai init`"))
    if cfg_path:
        from .config import load
        cfg = load(a.dir)
        for kind, p in cfg.missing_paths():
            print("   🔴 configured %s folder missing: %s" % (kind, p))
        print("   sources: %s" % ", ".join(cfg["sources"]))
        print("   packs:   %s" % ", ".join(cfg["citation_packs"]))

    print()
    ok = self_test(printer=lambda s: print("   " + s))
    # 🔴 The status line and the exit code must agree. Measured elsewhere: a doctor printed READY
    # and exited 1, which teaches people to ignore both.
    print("\nSTATUS: %s" % ("READY" if ok and cfg_path else "INCOMPLETE"))
    return 0 if (ok and cfg_path) else 1


def cmd_packs(a):
    from .citations import available_packs, load_packs
    for name in available_packs():
        p = load_packs([name]).packs[0]
        print("%-18s %s" % (name, p.name))
        for sh in p.shapes:
            addr = sh.get("address")
            print("     %-10s %s" % (addr["kind"] if addr else "(no key)",
                                     (sh.get("_what") or "")[:90]))
    return 0


def cmd_selftest(a):
    from .selftest import main as st
    return st()


# ----------------------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(
        prog="krokai",
        description="Check that every quotation of law in your documents is really in the source.")
    ap.add_argument("--version", action="version", version="krokai " + __version__)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--dir", help="start looking for casefile.json here (default: cwd)")
        p.add_argument("--quiet", action="store_true")
        return p

    p = sub.add_parser("init", help="create casefile.json and the folder skeleton")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = common(sub.add_parser("check", help="check every quotation in everything you wrote"))
    p.add_argument("--only", help="substring of a path, to check one file")
    p.add_argument("--tiers", default="ABCD")
    p.add_argument("--out", help="report directory")
    p.add_argument("--strict", action="store_true", help="exit non-zero if tiers A+B have findings")
    p.set_defaults(fn=cmd_check)

    p = common(sub.add_parser("quote", help="check ONE quotation, right now"))
    p.add_argument("text", nargs="?")
    p.add_argument("--file")
    p.set_defaults(fn=cmd_quote)

    p = common(sub.add_parser("bank", help="quote-bank and queue status"))
    p.add_argument("text", nargs="?", help="ask whether this quotation is already banked")
    p.set_defaults(fn=cmd_bank)

    p = common(sub.add_parser("sidecar", help="extract PDF text next to each PDF so grep sees it"))
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_sidecar)

    p = common(sub.add_parser("library", help="what is downloaded, what is unindexed"))
    p.add_argument("--recipes", action="store_true", help="print the retrieval recipes")
    p.set_defaults(fn=cmd_library)

    p = common(sub.add_parser("mutate", help="regression bank: how often does it say clean wrongly"))
    p.add_argument("--report", help="reuse a previous report directory instead of re-scanning")
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("--strict", action="store_true")
    p.set_defaults(fn=cmd_mutate)

    p = sub.add_parser("gate", help="outbound check for secrets and personal data")
    p.add_argument("files", nargs="*")
    p.add_argument("--allow-pii", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.set_defaults(fn=cmd_gate)

    p = sub.add_parser("brief", help="build a review brief carrying the citation rules")
    p.add_argument("question", nargs="?", default="")
    p.add_argument("--file", help="read the question from a file")
    p.add_argument("--material", help="embed source material")
    p.add_argument("--marker", default="REVIEW-COMPLETE")
    p.add_argument("--no-tools", action="store_true", help="the reviewer has no web access")
    p.add_argument("--canary", action="store_true")
    p.add_argument("--system", help="also write the research system prompt here")
    p.add_argument("--out")
    p.add_argument("--strict", action="store_true")
    p.set_defaults(fn=cmd_brief)

    p = common(sub.add_parser(
        "review", help="prepare a brief for outside reviewers and AUDIT their quotations"))
    p.add_argument("question", nargs="?", default="")
    p.add_argument("--file")
    p.add_argument("--material")
    p.add_argument("--out")
    p.add_argument("--marker", default="REVIEW-COMPLETE")
    p.add_argument("--no-tools", action="store_true")
    p.add_argument("--canary", action="store_true")
    p.add_argument("--allow-pii", action="store_true")
    p.add_argument("--prepare-only", action="store_true", help="build and gate, send nothing")
    p.add_argument("--dry-run", action="store_true",
                   help="resolve and print the whole plan, spend nothing. A complete preflight.")
    p.add_argument("--channels", action="store_true",
                   help="list every channel, including the ones switched off, and why")
    p.add_argument("--registry", help="a channels.json other than the one next to your casefile")
    p.add_argument("--only", nargs="*", help="run only these channels")
    p.add_argument("--skip", nargs="*", help="run everything except these")
    p.add_argument("--no-harness", action="store_true",
                   help="ignore an installed harness and use the built-in transports")
    p.add_argument("--harness", help="path to a review harness (or set KROKAI_REVIEW_HARNESS)")
    p.add_argument("--harness-args", nargs="*")
    p.add_argument("--audit", help="skip everything and audit a folder of answers you already have")
    p.set_defaults(fn=cmd_review)

    p = common(sub.add_parser("close", help="mechanical end-of-round checks"))
    p.set_defaults(fn=cmd_close)

    p = common(sub.add_parser("doctor", help="what is installed, what is configured, what is missing"))
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("keys", help="where API keys go, whether they are set, and how to set one")
    p.add_argument("--setup", action="store_true",
                   help="create the key folder outside your matter, with its warning file")
    p.add_argument("--how", action="store_true",
                   help="print the exact console command for each key that is missing")
    p.add_argument("--registry", help="a channels.json other than the shipped one")
    p.set_defaults(fn=cmd_keys)

    p = sub.add_parser("packs", help="list the citation packs that ship")
    p.set_defaults(fn=cmd_packs)

    p = sub.add_parser("selftest", help="behavioural checks; contacts nothing")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("install-hooks", help="wire the hooks into a Claude Code settings.json")
    p.add_argument("--scope", choices=["project", "user"], default="project")
    p.add_argument("--dir")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.set_defaults(fn=lambda a: __import__("krokai.install", fromlist=["main"]).main(a))

    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        ap.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
