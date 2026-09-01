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
from ._datadir import data_dir, data_file

if hasattr(sys.stdout, "reconfigure"):
    # Without this, output goes out in the console's legacy code page on Windows and any non-ASCII
    # verdict arrives as mojibake - i.e. the warning is unreadable exactly where it is needed.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# ---------------------------------------------------------------------------------- init
CLAUDE_BEGIN = "<!-- krokai:snippet:begin -->"
CLAUDE_END = "<!-- krokai:snippet:end -->"


def _krokai_command():
    """The command that runs THIS copy of the toolkit from ANY working directory.

    🔴 `python -m krokai` only works while the clone is the working directory or on `sys.path` -
    and the client's assistant works in the MATTER folder, which is neither. Running the package
    DIRECTORY (`python <clone>/krokai`) goes through `__main__.py` and works from anywhere, so
    that is the form everything user-facing is rendered with. The path is quoted: real installs
    sit under folders with spaces.
    """
    return 'python "%s"' % os.path.abspath(HERE)


def _render_snippet():
    # data_dir(), not ROOT: `<pkg>/..` is `site-packages` in an installed copy. See _datadir.py.
    tpl_path = os.path.join(data_dir("templates"), "CLAUDE.md.snippet")
    tpl = io.open(tpl_path, encoding="utf-8", errors="replace").read()
    # The leading HTML comment is instructions for the person pasting by hand. Rendered into a
    # client's CLAUDE.md it would be loaded into context on every request while saying nothing to
    # the assistant - so the renderer strips it.
    stripped = tpl.lstrip()
    if stripped.startswith("<!--"):
        end = stripped.find("-->")
        if end >= 0:
            tpl = stripped[end + 3:]
    return tpl.strip().replace("{KROKAI}", _krokai_command())


def write_claude_block(root, printer=print):
    """Append or refresh the krokai block in the matter's CLAUDE.md, between markers.

    WHY THIS IS PART OF `init` AND NOT A MANUAL STEP. The block lives in the matter's ROOT
    CLAUDE.md because that is the one instruction surface that is re-read at every session start
    AND after every /compact on the client's machine. The hooks are the mechanism that cannot be
    forgotten; this block is the standing reminder of how the matter works - and before this
    existed, the template shipped in `templates/` and nothing in the install path ever placed it,
    so the piece that survives a compaction was exactly the piece nobody installed.

    Target: the matter's `CLAUDE.md`, or `AGENTS.md` when only that exists. Idempotent by
    markers: outside the markers the TEXT is not modified (the append path trims trailing blank
    space at end-of-file, and the file's own line-ending style is preserved), a re-run refreshes
    only the block, and an existing file is appended to rather than replaced. States this
    function cannot edit safely - an orphaned or duplicated marker, a non-UTF-8 file - are
    refused with instructions, never repaired by guesswork.
    """
    body = (CLAUDE_BEGIN + "\n"
            + "<!-- Everything between these two marker lines is REWRITTEN by `krokai init`. "
              "Put your own notes outside the markers, or they will not survive a refresh. -->\n"
            + _render_snippet() + "\n" + CLAUDE_END)
    target = os.path.join(root, "CLAUDE.md")
    if not os.path.exists(target) and os.path.exists(os.path.join(root, "AGENTS.md")):
        target = os.path.join(root, "AGENTS.md")
    cur, raw = "", b""
    if os.path.exists(target):
        raw = io.open(target, "rb").read()
        # 🔴 STRICT decode, refuse on failure. The first draft read with errors="replace" and
        # wrote the result back - which would have rewritten every non-UTF-8 byte in the USER'S
        # OWN text as U+FFFD, file-wide, while reporting success. A reviewer traced it before a
        # client paid for it. This tool edits its block; it has no licence to transcode the file.
        try:
            cur = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise SystemExit(
                "%s is not UTF-8, and rewriting it would corrupt your own text outside the "
                "krokai block. Nothing was written. Convert the file to UTF-8 (or run with "
                "--no-claude-md and paste templates/CLAUDE.md.snippet by hand)." % target)
        cur = cur.replace("\r\n", "\n")
    if cur.count(CLAUDE_BEGIN) > 1 or cur.count(CLAUDE_END) > 1:
        # A marker string pasted INSIDE the block as an example makes the refresh cut at the
        # wrong boundary - reviewer-traced. Duplicates are a state this function cannot edit
        # safely, so it refuses rather than guessing which marker is real.
        raise SystemExit(
            "%s contains a krokai marker more than once - probably pasted as an example. "
            "Nothing was written. Remove the extra marker line(s), then re-run." % target)
    has_b, has_e = CLAUDE_BEGIN in cur, CLAUDE_END in cur
    if has_b != has_e:
        # 🔴 An orphaned marker means a human edited inside the block. With one marker missing,
        # the refresh path would have swallowed everything between the surviving marker and
        # wherever the partner next appeared - the user's text, deleted, under the word
        # "refreshed". Reviewer-traced. A file in an unexpected state is refused, not repaired.
        raise SystemExit(
            "%s contains one krokai marker but not the other - a hand edit removed %s. Nothing "
            "was written. Restore or delete the remaining marker line, then re-run."
            % (target, CLAUDE_END if has_b else CLAUDE_BEGIN))
    if has_b and has_e:
        pre, _b, rest = cur.partition(CLAUDE_BEGIN)
        _m, _e, post = rest.partition(CLAUDE_END)
        new, action = pre + body + post, "refreshed in"
    elif cur.strip():
        new, action = cur.rstrip() + "\n\n" + body + "\n", "appended to"
    else:
        new, action = body + "\n", "created"
    # Preserve the file's own line endings: a CRLF file silently flipped to LF is a whole-file
    # diff in the client's version control for a three-line change. Ours stay \n internally.
    # And the write is ATOMIC - temp file, then os.replace - because `open(..., "w")` truncates
    # first, and a crash between the truncation and the write would have cost the client their
    # whole CLAUDE.md (reviewer-named; this module's own sibling gateways already wrote that way).
    nl = "\r\n" if b"\r\n" in raw else "\n"
    tmp_path = target + ".krokai-tmp"
    with io.open(tmp_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(new.replace("\n", nl) if nl != "\n" else new)
    os.replace(tmp_path, target)
    return target, action


def cmd_init(a):
    from .config import TEMPLATE, CONFIG_NAME
    from .bank import BANK_HEADER
    from .library import INDEX_HEADER

    root = os.path.abspath(a.path or ".")
    # 🔴 Refuse to initialise a matter inside the toolkit's own checkout (R78 panel, named
    # independently by three reviewers). `init` targets the cwd, and in the clone root the
    # target CLAUDE.md is the repository's @AGENTS.md bridge - the block would be appended
    # after the import, matter folders (law/, case/) would land in the source tree, and the
    # repo pin would keep passing because the bare bridge line is still present. Same two
    # markers as the self-test's `_is_source_checkout`: either alone is too weak.
    if (os.path.isfile(os.path.join(root, "CHANGELOG.md"))
            and os.path.isfile(os.path.join(root, "krokai", "selftest.py"))):
        raise SystemExit(
            "%s looks like the krokai repository itself, not a client matter. Refusing to "
            "initialise a matter inside the toolkit's own tree - run this from the matter "
            "folder instead:  cd <matter> && krokai init ." % root)
    cfgp = os.path.join(root, CONFIG_NAME)
    if os.path.exists(cfgp) and not a.force:
        print("%s already exists. Nothing was touched. Use --force to overwrite." % cfgp)
        print("(the assistant block can still be refreshed on its own: `krokai init . --claude-md-only`)")
        if getattr(a, "claude_md_only", False):
            target, action = write_claude_block(root)
            print("assistant block %s %s" % (action, target))
            return 0
        return 1
    if getattr(a, "claude_md_only", False):
        target, action = write_claude_block(root)
        print("assistant block %s %s" % (action, target))
        return 0

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

    # Site-access map (R79-F3). A per-matter record of which publishers this environment can
    # reach, in the matter root (not law/, which is primary sources only) so a human sees it
    # from the shell. Never overwritten: a matter that ran through walls already has notes here
    # and this init is not authorised to lose them.
    sa_path = os.path.join(root, "SITE-ACCESS.md")
    if not os.path.exists(sa_path):
        try:
            tpl = io.open(data_file("templates/SITE-ACCESS.md"), encoding="utf-8").read()
        except OSError:
            tpl = ""                                       # ship-time contract; degrade gracefully
        if tpl:
            io.open(sa_path, "w", encoding="utf-8", newline="\n").write(tpl)
            made.append("SITE-ACCESS.md")

    if not getattr(a, "no_claude_md", False):
        target, action = write_claude_block(root)
        made.append("%s (assistant block %s)" % (os.path.basename(target), action))

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
    bad, unknown = print_summary(res, cfg["language"])
    out = a.out or os.path.join(cfg.root, "reports",
                                "check-" + __import__("time").strftime("%Y-%m-%d-%H%M"))
    path = write_report(res, cfg, out, cfg["language"])
    print("\nreport -> %s" % path)
    print("took %.0f s" % res["seconds"])
    # 🔴 `--strict` fails on EITHER, and with distinct codes so a hook can tell them apart:
    # 1 = read these, 4 = you cannot check these until you download something. The exit code used
    # to ignore the second entirely, so a quotation citing a source you do not have exited 0 - and
    # the exit code is what a hook and a CI job read. A number a person can see and a machine
    # cannot is half a signal.
    if a.strict and bad:
        return 1
    if a.strict and unknown:
        return 4
    # 🔴 R77 (#340, orglm53/lunapro): the address layer's own doctrine - "NO_NEARBY_CITATION on
    # something you file means do not award a green" - was prose without a mechanism: nothing a
    # script reads ever reflected it. Opt-in, because a matter mid-drafting legitimately has
    # unaddressed quotations and a default-on gate would teach people to pass it by reflex.
    if getattr(a, "strict_address", False):
        from .run import _tier_of
        na = sum(1 for r in res["rows"]
                 if _tier_of(r) in ("A", "B")
                 and (r.get("address") or {}).get("status") in ("NO_NEARBY_CITATION",
                                                                "ADDRESS_NOT_IN_CORPUS"))
        if na:
            print("--strict-address: %d filed-tier quotation(s) have no checkable address" % na)
            return 5
    return 0


# --------------------------------------------------------------------------------- quote
def cmd_quote(a):
    """One quotation, one answer. The command you run before pasting something into a document."""
    from .config import load
    from .run import corpus_for
    from .verify import check, neighbours
    from .verdicts import label, meaning

    cfg = load(a.dir)
    text = a.text
    if a.file:
        text = io.open(a.file, encoding="utf-8", errors="replace").read()
    if not text:
        print("give a quotation as an argument, or --file")
        return 2
    # R76: this door used to build the corpus bare - no sentinel, no superseded set - so it
    # verified sidecars and superseded law green while `krokai check` flagged them (see
    # run.corpus_for, which is now the only constructor the CLI may use).
    corpus = corpus_for(cfg, quiet=a.quiet)
    verdict, where, detail = check(text, corpus)
    lang = cfg["language"]
    print("\n%s" % label(verdict, lang).upper())
    print("  %s" % meaning(verdict, lang))
    if where:
        print("  found in: %s" % os.path.relpath(where, cfg.root))
    if detail:
        print("  %s" % detail)

    # 🔴 Shown for a quotation that PASSED, which is the whole reason it is here. A flagged quotation
    # already sends you to the source; a verified one is the one nobody opens again. The two
    # sentences around it are where a dropped proviso lives, and no string comparison can see one.
    for path, before, after in neighbours(text, corpus):
        if not (before or after):
            continue
        print("\n  in %s, the source reads:" % os.path.relpath(path, cfg.root))
        if before:
            print("    before  …%s" % before[-220:])
        if after:
            print("    after   %s…" % after[:220])
        print("    🔴 Read these two. A condition sitting immediately after a quotation is a "
              "condition\n       you have dropped, and the checker above cannot see it.")

    if verdict == "NOT_FOUND":
        # 🔴 DERIVED from SIX_CAUSES, never retyped (R78 panel, two channels independently):
        # this block was a hand-written FOUR-item ladder for a whole release after the code
        # shipped six - the assistant snippet was synced and the tool's own mouth was not.
        # The one command documented as a new user's first is the worst place for a stale copy.
        import textwrap
        from .verdicts import SIX_CAUSES
        print("\n🔴 NOT FOUND is not the same as INVENTED. Rule these out in order - only what"
              "\n   survives all of them is a defect in the quotation:")
        for i, cause in enumerate(SIX_CAUSES, 1):
            print(textwrap.fill(cause, width=96, initial_indent="     %d. " % i,
                                subsequent_indent="        "))

        # 🔴 R79-F3 (G-E): the FIRST cause is "the source was never downloaded" - and the
        # toolkit has the information to name the exact command. Only fire when a citation is
        # actually next to the quotation AND its address kind has a stable URL (usc, fr,
        # publaw, cfr). Kinds without a stable request-level URL (USCIS PM, FAM) are skipped
        # here so the block does not become noise; those still print through the caveat when
        # `library --suggest-fetches` runs. Silence is correct when nothing new can be added.
        from .citations import load_packs
        from .suggest import suggest_for_key
        try:
            packs = load_packs(cfg["citation_packs"])
            cite_keys = packs.keys(packs.find(text))
        except Exception:                                                # noqa: BLE001
            cite_keys = set()
        printed = 0
        for key in sorted(cite_keys):
            s = suggest_for_key(key)
            if not s or not s.command:
                continue
            if printed == 0:
                print("\n     💡 If cause 1 fits, the ready-to-run command is:")
            print("        %s" % s.command)
            if s.caveat == "requires_date":
                print("        (replace {DATE} first — see SITE-ACCESS.md)")
            printed += 1
            if printed >= 3:                              # a busy quotation stops printing walls
                break
    return 0 if verdict == "VERIFIED" else 1


# ---------------------------------------------------------------------------------- bank
def cmd_bank(a):
    from .config import load
    from .bank import read_bank, queue_open_items, in_bank
    from .bank_add import revision_ledger

    cfg = load(a.dir)
    bank_path = cfg.abs(cfg["bank"])
    bank = read_bank(bank_path)
    entries = bank.count("\n### ")
    print("quote bank: %s" % bank_path)
    print("  %d entr%s, %d bytes" % (entries, "y" if entries == 1 else "ies", len(bank.encode())))
    ledger, _body = revision_ledger(bank)
    if ledger is not None and ledger != entries:
        # The one state worth a line here: the header's count and the body disagree, which for an
        # append-only file is either a silent deletion or hand entries - `krokai close` explains.
        print("  🔴 the revision line says %d - the body disagrees; run `krokai close`" % ledger)
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


def cmd_bank_add(a):
    from .bank_add import run_add
    return run_add(a)


def cmd_bank_dismiss(a):
    from .bank_add import run_dismiss
    return run_dismiss(a)


# ------------------------------------------------------------------------------- coverage
def cmd_coverage(a):
    """Bank ↔ draft coverage: mines, unapplied entries, paraphrases, missing pieces.

    The four findings each answer a question a string check cannot: whether the ground the
    drafter is standing on is ground the bank marks hostile (A), whether a rule the bank
    holds for us is missing from the argument (B), whether the drafter summarised a rule the
    bank has the exact wording of (C), and whether a bank entry itself is missing the fields
    that let it be cited responsibly (D). Runs its own controls first - a zero from a broken
    extractor is a statement about the extractor, not the world.
    """
    from .config import load
    from .bank import read_bank
    from .coverage import (parse_bank_entries, analyse, render_report, controls_pass)

    cfg = load(a.dir)

    # Controls before report. If the extractor is broken, an empty MINES section reads as
    # clean and is not. Exit 2 keeps this failure loud - a hook or CI over `coverage` sees
    # the same code any other bad-input situation would produce.
    if not controls_pass():
        print("🔴 coverage controls failed - the extractor is broken and any report from it")
        print("   would be unreliable. Nothing was analysed. Run `krokai selftest` for detail.")
        return 2

    bank_path = cfg.abs(cfg["bank"])
    entries = parse_bank_entries(read_bank(bank_path))
    if not entries:
        print("🔴 the bank is empty - coverage has nothing to compare against.")
        print("   Bank at least one entry first: `krokai bank add ...`")
        return 3

    drafts = []
    for p in a.drafts:
        if not os.path.isfile(p):
            print("🔴 not a file: %s" % p)
            return 3
        drafts.append((p, io.open(p, encoding="utf-8", errors="replace").read()))
    if not drafts:
        print("give one or more draft files as arguments")
        return 2

    report = analyse(drafts, entries)

    if a.json:
        # A machine-readable form so an outer hook can decide - the same discipline `check`
        # already follows. The rendered text still prints, because a human running this
        # locally reads the terminal, not the JSON.
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        render_report(report, out=sys.stdout)

    # Exit codes: 0 clean, 1 unapplied or missing-pieces only (yellow), 5 mines or
    # paraphrases (red). Distinct codes because a hook must be able to gate on mines
    # without gating on the yellow shape - a fresh matter has unapplied entries by
    # construction.
    if a.strict and (report["mines"] or report["paraphrases"]):
        return 5
    if a.strict and (report["unapplied"] or report["unparsed"]):
        return 1
    return 0


# ------------------------------------------------------------------------------- appendix
def cmd_appendix(a):
    """Build the legal appendix ("Нормативная база") from banked entries.

    Every entry runs a FRESH `check()` against the current corpus at build time. Included
    entries land under their group heading (CFR / USC / INA / ...); everything else lands in
    an EXCLUDED section that names the fresh verdict. Silence is what turns a dropped
    proviso into a filing defect - the excluded section is what the drafter reads before
    filing.
    """
    from .config import load
    from .run import corpus_for
    from .citations import load_packs
    from .appendix import build_appendix

    cfg = load(a.dir)
    corpus = corpus_for(cfg, quiet=True)
    packs = load_packs(cfg["citation_packs"])

    # Default bank list: the matter's own bank. Explicit files win. Both paths accept a
    # list, so `krokai appendix a.md b.md` combines them - useful when a matter carries
    # side-specific files.
    banks = a.banks or [cfg.abs(cfg["bank"])]
    banks = [os.path.abspath(p) for p in banks]

    md, stats = build_appendix(banks, corpus, packs, cfg=cfg, side=a.side)
    if md is None:
        # `build_appendix` already printed the specific error.
        return 3

    if a.out:
        out_path = os.path.abspath(a.out)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        io.open(out_path, "w", encoding="utf-8", newline="\n").write(md)
        print("appendix -> %s (%d chars, %d included, %d excluded)"
              % (out_path, len(md), stats["included"], stats["excluded"]))
    else:
        sys.stdout.write(md)
        print("")
        print("=== summary ===")
        print("included: %d · excluded: %d · side: %s"
              % (stats["included"], stats["excluded"], stats["side"]))

    if a.json:
        print("")
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    # 🔴 Exit codes: 0 clean (nothing excluded), 1 excluded entries present (yellow - the
    # appendix built, some entries did not qualify), 3 no bank at all. A hook needs to gate
    # differently on "some entries dropped" vs "no bank" - a fresh matter has neither by
    # construction and both would otherwise read as 0.
    if a.strict and stats["excluded"]:
        return 1
    return 0


# --------------------------------------------------------------------- fetch-precedent
def cmd_fetch_precedent(a):
    """Download a precedent AND prove it names the party, subject and court you asked for.

    An assistant asked to save `Matter of Smith` may save another Smith from the same
    reporter volume - measured, in a real matter (AOS R79 study §5). The URL, the anchor
    text, the file name and the byte hash all read "fine". Only READING THE DOWNLOADED TEXT
    catches it, and this command requires three tokens to appear in the head of the file
    before it agrees to keep the download.
    """
    from .config import load
    from .citations import load_packs
    from .precedent import fetch_precedent

    cfg = load(a.dir)
    packs = load_packs(cfg["citation_packs"])
    ok, dest, meta_or_reason = fetch_precedent(
        a.url, party=a.party, subject=a.subject, court=a.court,
        root=cfg.root, cfg=cfg, packs=packs, dest_dir=a.into,
        allow_unknown=a.allow_unknown_source, timeout=a.timeout)
    if ok:
        return 0
    # Distinct codes for the three failure stages: 2 = refuse/empty criterion,
    # 3 = download refused (host, HTTP), 4 = extraction failed, 5 = criteria not found.
    # A wrong-file precedent is a different alarm than a network refusal; a hook needs
    # both to be distinguishable.
    stage = (meta_or_reason or {}).get("stage")
    return {"refuse": 2, "fetch": 3, "read": 4, "verify": 5}.get(stage, 1)


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

    # --suggest-fetches implies --bank (a suggestion is FOR a missing entry, and the list of
    # missing entries is what --bank produces). The extra print at the end is the whole point.
    want_suggest = getattr(a, "suggest_fetches", False)
    if getattr(a, "bank", False) or want_suggest:
        # Corpus <-> bank inventory (G-D). The other side of the same "what is not connected"
        # question: index counts what is on disk, bank counts what the matter has actually
        # decided about. A file downloaded and never analysed is a rule the matter has yet to
        # take a position on; an addressed bank entry with no file behind it means the entry
        # cannot be re-checked and its quotation cannot be verified. Both are the silent-hole
        # shape and both must be visible.
        from .bank import read_bank
        from .citations import load_packs
        from .coverage import (parse_bank_entries, corpus_bank_inventory, controls_pass)
        from .run import corpus_for

        if not controls_pass():
            print("\n🔴 coverage controls failed - the inventory would be unreliable.")
            return 2
        entries = parse_bank_entries(read_bank(cfg.abs(cfg["bank"])))
        corpus = corpus_for(cfg, quiet=True)
        packs = load_packs(cfg["citation_packs"])
        inv = corpus_bank_inventory(corpus, entries, packs)
        print("\ncorpus <-> bank inventory:")
        print("  %d corpus file(s), %d matched by a bank entry, %d not"
              % (inv["corpus_file_count"], inv["matched_sources"],
                 len(inv["unparsed_sources"])))
        for p in inv["unparsed_sources"][:20]:
            print("     %s" % os.path.relpath(p, cfg.root))
        if len(inv["unparsed_sources"]) > 20:
            print("     ... and %d more" % (len(inv["unparsed_sources"]) - 20))

        print("  %d bank entr%s whose address has no file in the corpus"
              % (len(inv["missing_for_bank"]),
                 "y" if len(inv["missing_for_bank"]) == 1 else "ies"))
        for m in inv["missing_for_bank"][:20]:
            print("     %s  (%s)" % (m["id"], m["address"]))

        if want_suggest:
            # 🔴 R79-F3 (G-E): for every missing entry, print the ready-to-run download command
            # when the address kind has one, or the browser-only caveat when it does not. The
            # split is honest by construction - a suggest that hands out an invented URL for a
            # 403 site would be the fabrication shape this toolkit exists to catch, one level
            # up. Address strings are re-parsed through the packs (coarse keys - the fetch
            # question is "which file could hold this rule", not "which paragraph").
            from .suggest import suggest_for_key
            print("\nsuggested downloads for the %d missing entr%s:"
                  % (len(inv["missing_for_bank"]),
                     "y" if len(inv["missing_for_bank"]) == 1 else "ies"))
            if not inv["missing_for_bank"]:
                print("  (nothing to suggest - every banked address has a file on disk)")
            for m in inv["missing_for_bank"]:
                addr = m["address"]
                keys = packs.keys([addr]) if addr else set()
                shown = 0
                for key in sorted(keys):
                    s = suggest_for_key(key)
                    if not s:
                        continue
                    if s.command:
                        print("  %s  %s" % (m["id"], addr))
                        print("      %s" % s.command)
                        if s.caveat == "requires_date":
                            print("      note: replace {DATE} first — see SITE-ACCESS.md, "
                                  "or `krokai doctor --probe-sites` prints today's date")
                    else:
                        print("  %s  %s" % (m["id"], addr))
                        print("      🟡 %s" % s.note)
                    shown += 1
                    break                                  # one suggestion per entry is enough
                if not shown and addr:
                    print("  %s  %s" % (m["id"], addr))
                    print("      (no suggester for this address kind - open the publisher's "
                          "site in a browser and save the source)")
    return 0


# --------------------------------------------------------------------------- fetch / intake
def cmd_fetch(a):
    from .config import load
    from .citations import load_packs
    from .fetch import fetch_url
    cfg = load(a.dir)
    packs = load_packs(cfg["citation_packs"])
    meta = fetch_url(a.url, cfg.root, cfg=cfg, packs=packs,
                     allow_unknown=a.allow_unknown_source, timeout=a.timeout)
    return 0 if meta else 1


def cmd_intake(a):
    from .config import load
    from .citations import load_packs
    from .fetch import intake
    cfg = load(a.dir)
    packs = load_packs(cfg["citation_packs"])
    rows = intake(cfg.root, cfg, packs, address=a.address, dest_dir=a.into)
    if not rows:
        return 0
    print("")
    for status, name, note in rows:
        print("  %-14s %-46s %s" % (status, name[:46], note))
    # 🔴 The exit code has to see a revision and a refusal, or a hook wired to this command reads
    # both as success. A number a person can read and a machine cannot is half a signal - the same
    # correction NO_SOURCE_ON_DISK needed.
    if any(s.startswith("🔴") for s, _n, _x in rows):
        return 4
    if any(s in ("NO ADDRESS", "REFUSED") for s, _n, _x in rows):
        return 3
    return 0


# -------------------------------------------------------------------------------- mutate
def cmd_mutate(a):
    from .config import load
    from .run import scan_matter
    from .mutations import run as run_mut

    cfg = load(a.dir)
    if a.report:
        data = json.load(io.open(os.path.join(a.report, "result.json"), encoding="utf-8"))
        base = [(r["quote"], r["where"]) for r in data["rows"] if r["verdict"] == "VERIFIED"]
        from .run import corpus_for
        corpus = corpus_for(cfg)
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
def _configured_surnames():
    """Surnames from `casefile.json`, or none if there is no config here.

    🔴 The gate must work with no configuration at all - it is the command a stranger runs first,
    on a file, before `krokai init` has ever been called. So a missing config is not an error; it
    is zero surnames, and `gate()` says so out loud rather than printing `clean`.
    """
    try:
        from .config import load
        cfg = load(required=False)
        return cfg.surnames if cfg else ()
    except (SystemExit, Exception):                                 # noqa: BLE001
        # `SystemExit` does not derive from `Exception`, and it is this codebase's idiom for a
        # fatal user message - so a malformed casefile.json would otherwise kill `krokai gate`,
        # the one command whose job is to run when things are wrong.
        return ()


def cmd_gate(a):
    from .redact import gate, self_test
    if a.self_test:
        return 0 if self_test() else 1
    parts = []
    for p in a.files:
        parts.append((os.path.basename(p), io.open(p, encoding="utf-8", errors="replace").read()))
    if not parts:
        parts = [("stdin", sys.stdin.read())]
    return gate(parts, allow_pii=a.allow_pii, surnames=_configured_surnames())


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
    # 🔴 R77 (#337, orgemini37flash): the documented second-best home for a key - the keys.env
    # file OUTSIDE the project - was loaded by `krokai keys` (the command that only REPORTS) and
    # by nothing else. So the user proved the key was set, ran `krokai review`, and the round
    # dispatched channels with no key in the environment. Loaded here, names-only printing, and
    # a key already in the environment still wins.
    from .keys import load_key_file
    load_key_file(printer=print)
    out = os.path.abspath(a.out or os.path.join(cfg.root, "reviews", "round"))

    # 🔴 R77 (#339, kimik3/lunapro): the audit's verdicts REACH THE EXIT CODE. `_audit` returned
    # its rows and both call sites discarded them - a reviewer's fabricated quotation printed a
    # red table and exited 0, so a hook or CI over this command could never see the one thing it
    # runs for. 5, distinct from 1 (a channel failed) - transport and trust are different alarms.
    from .verdicts import CLEAN as _CLEAN

    def _audit(folder):
        from .run import corpus_for
        from .citations import load_packs
        corpus = corpus_for(cfg)
        return audit_answers(folder, corpus, load_packs(cfg["citation_packs"]),
                             cfg["min_quote_length"])

    if a.audit:
        audit_rows = _audit(os.path.abspath(a.audit))
        return 5 if any(r[1] not in _CLEAN for r in audit_rows) else 0

    reg = load_registry(a.registry, start=cfg.root)
    harness = find_harness(reg, a.harness)

    # The packs teach the grounding the NAMES of the official bodies this matter cites.
    # `grounding.primary` deliberately holds short generic suffixes (".gov"), and a generic suffix
    # cannot tell the lookalike detector that `uscis` is a name worth impersonating - measured in a
    # sister project: `uscis.com`, the exact agency name in a foreign zone, walked straight past a
    # labels-only detector. Merging here changes no classification of real .gov URLs (the specific
    # domains are already inside the generic suffix); it only arms the lookalike test.
    from .citations import load_packs
    g = reg.setdefault("grounding", {})
    have = {str(x).lower().strip().lstrip(".") for x in (g.get("primary") or [])}
    extra = [d for d in load_packs(cfg["citation_packs"]).official_domains if d not in have]
    if extra:
        g["primary"] = list(g.get("primary") or []) + extra

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
    surnames = _configured_surnames()
    made = prepare(question, material, out_dir=out, marker=a.marker, tools=not a.no_tools,
                   canary=a.canary, allow_pii=a.allow_pii, surnames=surnames)
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
                          allow_pii=a.allow_pii, dry_run=a.dry_run, surnames=surnames)
    if a.dry_run or not rows:
        return 0

    print("\n--- checking the reviewers' quotations against YOUR corpus ---")
    audit_rows = _audit(out)
    if any(r["verdict"] == "FAILED" for r in rows):
        return 1
    return 5 if any(r[1] not in _CLEAN for r in audit_rows) else 0


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
        print("      Closing a line = `krokai bank add` (slices the quotation from the source,")
        print("      verifies it BEFORE writing, and ticks the line here itself), or")
        print("      `krokai bank dismiss \"<fragment>\" --why ...` to decline with a reason.")
        ok = False

    unindexed, missing = orphans(cfg.source_dirs, cfg.abs(cfg["library_index"]),
                                 skip_dirs=set(cfg["skip_dirs"]))
    print("\n[2] library index: %d unindexed file(s), %d dead row(s)  %s"
          % (len(unindexed), len(missing), "OK" if not (unindexed or missing) else "🔴"))
    if unindexed or missing:
        ok = False

    from .sidecar import SUFFIX
    from .corpus import walk
    # R76 (orglm53): skip_dirs was not passed, so `krokai close` reported phantom missing
    # sidecars for archived material and gated the round on folders the corpus itself skips.
    pdfs = list(walk(cfg.source_dirs, (".pdf",), set(cfg["skip_dirs"])))
    without = [p for p in pdfs if not os.path.exists(p[:-4] + SUFFIX)]
    print("\n[3] PDF sidecars: %d of %d PDFs have none  %s"
          % (len(without), len(pdfs), "OK" if not without else "🔴 grep is blind to these"))
    if without:
        ok = False

    from .redact import self_test
    print("\n[4] outbound gate")
    if not self_test(printer=lambda s: print("      " + s)):
        ok = False

    # 🔴 The bank is append-only BY RULE, and a rule enforces nothing: this check does. The
    # header's revision line is refreshed by every `krokai bank add --apply`; a body SMALLER
    # than the ledger means entries vanished between writes - a hand or model deletion, the one
    # edit an append-only file must make loud. A body larger is merely hand-written entries.
    from .bank import read_bank
    from .bank_add import revision_ledger
    ledger, body = revision_ledger(read_bank(cfg.abs(cfg["bank"])))
    if ledger is None:
        print("\n[5] bank ledger: no revision line yet (the bank predates `krokai bank add`)  OK")
    elif body < ledger:
        print("\n[5] bank ledger: the header says %d entries, the body holds %d  🔴 ENTRIES "
              "VANISHED" % (ledger, body))
        print("      An entry was deleted since the last gatekeeper write. Restore it from "
              "version control")
        print("      or a backup; if the deletion was deliberate, correct the revision line by "
              "hand - in writing.")
        ok = False
    elif body > ledger:
        print("\n[5] bank ledger: %d hand-written entr%s since the last gatekeeper write  🟡"
              % (body - ledger, "y" if body - ledger == 1 else "ies"))
        print("      Legitimate - the bank stays hand-editable. The next `krokai bank add "
              "--apply` refreshes the count.")
    else:
        print("\n[5] bank ledger: header and body agree (%d entries)  OK" % body)

    # [6] corpus <-> bank inventory. The other half of "what is not connected": a file with no
    # bank entry is a rule the matter has yet to take a position on, and the read side (bank
    # entry with no file) produces the same NOT_FOUND signal as fabrication. Only fires when
    # both a bank and a corpus exist - a fresh matter has neither. Yellow, not red: neither
    # direction is inherently wrong, and gating close on it would teach people to bank noise
    # to make the count go down.
    try:
        from .coverage import (parse_bank_entries, corpus_bank_inventory, controls_pass)
        from .citations import load_packs
        from .run import corpus_for
        entries = parse_bank_entries(read_bank(cfg.abs(cfg["bank"])))
        if entries and controls_pass(printer=lambda s: None):
            corpus = corpus_for(cfg, quiet=True)
            if corpus.paths:
                packs = load_packs(cfg["citation_packs"])
                inv = corpus_bank_inventory(corpus, entries, packs)
                verdict = ("OK" if not (inv["unparsed_sources"] or inv["missing_for_bank"])
                           else "🟡")
                print("\n[6] corpus <-> bank: %d source(s) with no bank entry, %d bank "
                      "entr%s with no source  %s"
                      % (len(inv["unparsed_sources"]), len(inv["missing_for_bank"]),
                         "y" if len(inv["missing_for_bank"]) == 1 else "ies", verdict))
                for p in inv["unparsed_sources"][:5]:
                    print("      • unparsed: %s" % os.path.relpath(p, cfg.root))
                for m in inv["missing_for_bank"][:5]:
                    print("      • missing:  %s  (%s)" % (m["id"], m["address"]))
                if inv["unparsed_sources"] or inv["missing_for_bank"]:
                    print("      `krokai library --bank` prints the whole inventory. Not "
                          "gated: a")
                    print("      fresh matter has holes both ways by construction.")
    except (SystemExit, Exception):                                   # noqa: BLE001
        # A malformed bank must not kill `close` - this is one check of six and the round-end
        # decisions depend on the other five. `SystemExit` handled the same as any Exception
        # because it is this codebase's fatal-user-message idiom (`_configured_surnames`).
        pass

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

        # The two things that keep working AFTER the client's next /compact - reported as facts,
        # with the exact command when absent, because "minimum manual setup" means the tool names
        # its own missing pieces rather than leaving them to be discovered by failure.
        from .install import _is_ours
        root = os.path.dirname(cfg_path)
        wired = {"project": 0, "user": 0}
        for scope, sp in (("project", os.path.join(root, ".claude", "settings.json")),
                          ("user", os.path.join(os.path.expanduser("~"), ".claude",
                                                "settings.json"))):
            try:
                data = json.load(io.open(sp, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for _ev, gs in (data.get("hooks") or {}).items():
                for g in gs or []:
                    wired[scope] += sum(1 for h in (g.get("hooks") or []) if _is_ours(h, ""))
        total = wired["project"] + wired["user"]
        if total:
            print("   hooks:   %d wired (project %d, user %d) - they fire regardless of what the "
                  "session remembers" % (total, wired["project"], wired["user"]))
        else:
            print("   🔴 hooks: NOT wired - run `krokai install-hooks`. The hooks are the "
                  "mechanism; a written rule fires by topic and a hook fires every time.")
        block_in, block_text, blocks_found = "", "", []
        for fn in ("CLAUDE.md", "AGENTS.md"):
            p = os.path.join(root, fn)
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if CLAUDE_BEGIN in t:
                blocks_found.append(fn)
                if not block_in:
                    block_in, block_text = fn, t
        if len(blocks_found) > 1:
            # The block landed in AGENTS.md before a CLAUDE.md existed, then again in CLAUDE.md -
            # two managed blocks age independently and the assistant obeys whichever it read
            # last. Reviewer-named sequence; the doctor is where it becomes visible.
            print("   🔴 block: TWO managed blocks (%s) - they will drift apart. Keep the one in "
                  "CLAUDE.md and delete the marker block from the other file."
                  % " and ".join(blocks_found))
        if block_in:
            print("   block:   assistant block present in %s - re-read at every session start "
                  "and after every /compact" % block_in)
            # The block bakes in the toolkit's absolute path; a moved clone leaves the client's
            # assistant invoking a path that no longer exists. Raised by an outside review; the
            # doctor is the natural place to notice, because it is the command the client runs
            # when something feels wrong.
            import re as _re
            m = _re.search(r'python "([^"]+)"', block_text)
            if m and not os.path.isdir(m.group(1)):
                print("   🔴 block: the toolkit path inside the block no longer exists (%s) - "
                      "the clone was moved. Run `krokai init . --claude-md-only` to re-render it."
                      % m.group(1))
        else:
            print("   🔴 block: no assistant block in CLAUDE.md - run `krokai init . "
                  "--claude-md-only`. Without it, everything the assistant was told about this "
                  "matter is gone after its next /compact.")

    print()
    ok = self_test(printer=lambda s: print("   " + s))

    # --probe-sites (R79-F3): the ONLY doctor knob that touches the network, opt-in and off by
    # default. One request each to the four known-good publishers, so the same table the
    # SITE-ACCESS.md template lists is measured against reality here. `requests` failures print
    # the exception verbatim - a doctor is meant to be loud about what it saw.
    if getattr(a, "probe_sites", False):
        _probe_sites()

    # 🔴 The status line and the exit code must agree. Measured elsewhere: a doctor printed READY
    # and exited 1, which teaches people to ignore both.
    print("\nSTATUS: %s" % ("READY" if ok and cfg_path else "INCOMPLETE"))
    return 0 if (ok and cfg_path) else 1


def _probe_sites():
    """Live probe of the four publisher URLs the suggest layer prints commands for. Never
    fails the doctor - a probe that flips the exit code teaches you to skip the probe. It
    prints the status line and the reader decides.
    """
    print("\nlive publisher probes (opt-in; hits the network once per row):")
    try:
        import requests
    except ImportError:
        print("   `requests` not installed - skipping. `pip install requests`.")
        return
    ua = ("krokai-law (+https://github.com/igorsaevets/krokai-law) "
          "doctor --probe-sites")
    probes = [
        ("govinfo/uscode",
         "https://www.govinfo.gov/link/uscode/8/1101?link-type=html"),
        ("govinfo/fr",
         "https://www.govinfo.gov/link/fr/91/45324?link-type=html"),
        ("govinfo/plaw",
         "https://www.govinfo.gov/link/plaw/107/public/56?link-type=html"),
        ("ecfr/api",
         "https://www.ecfr.gov/api/versioner/v1/titles.json"),
    ]
    for label, url in probes:
        try:
            r = requests.get(url, timeout=15, allow_redirects=True,
                             headers={"User-Agent": ua})
            note = "%d, %d bytes" % (r.status_code, len(r.content or b""))
            if r.url and r.url != url:
                note += ", -> %s" % r.url[:80]
            print("   %-16s %s   %s" % (label, "OK " if r.status_code == 200 else "!! ", note))
        except Exception as exc:                                          # noqa: BLE001
            print("   %-16s !!    %s: %s" % (label, type(exc).__name__, str(exc)[:120]))

    # Then extract the latest_issue_date for title 8 as a bonus - this is what the CFR
    # suggester's {DATE} needs, and printing it in the doctor is what makes the placeholder
    # actionable without a second manual step.
    try:
        import json as _json
        r = requests.get("https://www.ecfr.gov/api/versioner/v1/titles.json", timeout=15,
                         headers={"User-Agent": ua})
        if r.status_code == 200:
            data = _json.loads(r.content.decode("utf-8", "replace"))
            for row in (data.get("titles") or []):
                if str(row.get("number")) == "8":
                    d = row.get("latest_issue_date") or "?"
                    print("   eCFR title 8   latest_issue_date = %s   (use this for {DATE})" % d)
                    break
    except Exception:                                                     # noqa: BLE001
        pass


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


def cmd_agents(a):
    """Print the toolkit's AGENTS.md - the working discipline for an assistant in a matter.

    WHY A COMMAND AND NOT A FILE COPIED INTO THE MATTER. A pip user never sees the repository, so
    the root AGENTS.md has to travel inside the wheel - but writing a copy into every matter would
    create a second home that rots the moment the package updates, which is the exact
    two-files-on-one-subject failure this project keeps measuring. So the matter gets a one-line
    pointer (in the `init` block) and the content stays in the package, always the installed
    version's own. `data_file` resolves both layouts: the force-included copy inside the wheel,
    or the repository root when running from a clone.
    """
    path = data_file("AGENTS.md")
    if not os.path.isfile(path):
        raise SystemExit("AGENTS.md is missing from this install. Reinstall the package, or run "
                         "from a full clone of the repository.")
    print(io.open(path, encoding="utf-8").read())
    return 0


def cmd_selftest(a):
    from .selftest import main as st
    return st()


def cmd_check_exhibits(a):
    from .exhibit_check import reconcile
    petition = a.petition if isinstance(a.petition, list) else [a.petition]
    exhibits = a.exhibits if isinstance(a.exhibits, list) else [a.exhibits]
    forms = a.forms if a.forms else None
    if forms and not isinstance(forms, list):
        forms = [forms]
    result = reconcile(petition, exhibits, form_dirs=forms, out=a.out)
    for line in result["report_lines"]:
        print(line)
    if result.get("refused"):
        return 2
    if result["cited_no_file"] or result.get("form_cited_no_file"):
        return 1
    if result.get("unread"):
        # 🔴 R77 (#F-E, grokbuild MAJOR, probe-proven): a mixed folder with one readable .md and
        # a broken PDF reported the unread petition loudly AND exited 0 - CI and hooks read the
        # exit code, so a legit broken-input state passed silently. Now: unread petitions flip
        # the exit code (1), joining the round's exit-code theme (#339, #340). No --allow-unread
        # escape flag (R44 registry lesson: a documented escape becomes the default). With F-D
        # this also means a matter holding .doc petitions now exits 1 until they are converted
        # to .docx — deliberate; conversion is one Word Save-As away.
        return 1
    return 0


def cmd_dump_forms(a):
    from .form_dump import dump_forms
    dirs = a.dir if isinstance(a.dir, list) else [a.dir]
    result = dump_forms(dirs, out=a.out, nonempty=a.nonempty)
    for line in result["report_lines"]:
        print(line)
    m = result["manifest"]
    total = len(m["forms"])
    excluded = len(m["excluded"])
    errors = len(m["errors"])
    print("\n%d forms processed, %d excluded, %d errors" % (total, excluded, errors))
    if a.out:
        print("outputs -> %s" % os.path.abspath(a.out))
    return 1 if errors else 0


def cmd_scan_pdfs(a):
    from .repair import scan_broken_pdfs
    found = scan_broken_pdfs(a.directory, skip_dirs=a.skip)
    if not found:
        print("No broken PDFs found.")
        return 0
    print("Found %d broken PDF(s):" % len(found))
    for rel, _full in found:
        print("  %s" % rel)
    return 0


def cmd_fix_pdf(a):
    from .repair import fix_broken_pdf
    dest = a.output
    if not dest:
        base, ext = os.path.splitext(a.source)
        dest = base + "_fixed" + ext
    print("Fixing: %s" % a.source)
    print("Output: %s" % dest)
    pages, chars = fix_broken_pdf(a.source, dest, dpi=a.dpi,
                                  callback=lambda p, t, c: print(
                                      "  Page %d/%d: %d chars" % (p, t, c)))
    print("Done. %d pages, %d characters embedded." % (pages, chars))
    return 0


def cmd_fix_pdfs(a):
    from .repair import fix_batch
    results, errors = fix_batch(a.directory, a.output, skip_dirs=a.skip, dpi=a.dpi, log=print)
    if results:
        print("\nFixed %d file(s)." % len(results))
    if errors:
        print("\n🔴 %d file(s) FAILED to repair - they are still broken:" % len(errors))
        for rel, msg in errors:
            print("   %s  (%s)" % (rel, msg[:120]))
    if not results and not errors:
        print("\nNothing to fix.")
    return 1 if errors else 0


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

    p = sub.add_parser("init", help="create casefile.json, the folder skeleton, and the "
                                    "assistant block in CLAUDE.md")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-claude-md", action="store_true",
                   help="do not touch CLAUDE.md/AGENTS.md")
    p.add_argument("--claude-md-only", action="store_true",
                   help="only append/refresh the assistant block; touch nothing else")
    p.set_defaults(fn=cmd_init)

    p = common(sub.add_parser("check", help="check every quotation in everything you wrote"))
    p.add_argument("--only", help="substring of a path, to check one file")
    p.add_argument("--tiers", default="ABCD")
    p.add_argument("--out", help="report directory")
    p.add_argument("--strict", action="store_true", help="exit non-zero if tiers A+B have findings")
    p.add_argument("--strict-address", action="store_true",
                   help="also exit non-zero (5) when a filed-tier quotation has no checkable "
                        "address beside it - 'found somewhere' is not 'found where you said'")
    p.set_defaults(fn=cmd_check)

    p = common(sub.add_parser("quote", help="check ONE quotation, right now"))
    p.add_argument("text", nargs="?")
    p.add_argument("--file")
    p.set_defaults(fn=cmd_quote)

    # `bank` grew subcommands in 0.12.0. Bare `krokai bank` stays the status view; the parent's
    # own --dir/--quiet still work for it. The children define their own copies with SUPPRESS
    # defaults - argparse otherwise CLOBBERS a parent-parsed value with the child's default,
    # so `krokai bank --dir X add` would silently lose X.
    def bank_common(bp):
        bp.add_argument("--dir", default=argparse.SUPPRESS,
                        help="start looking for casefile.json here (default: cwd)")
        bp.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS)
        return bp

    p = common(sub.add_parser(
        "bank", help="quote-bank and queue: status, the write gatekeeper, dismiss"))
    p.set_defaults(fn=cmd_bank, text=None)
    bsub = p.add_subparsers(dest="bank_cmd")

    q = bank_common(bsub.add_parser("status", help="bank and queue status (the default)"))
    q.add_argument("text", nargs="?", help="ask whether this quotation is already banked")
    q.set_defaults(fn=cmd_bank)

    q = bank_common(bsub.add_parser(
        "add", help="write ONE bank entry - the quotation is SLICED from the source between "
                    "two anchors, never typed. Dry-run unless --apply"))
    q.add_argument("--side", required=True, choices=("pro", "con"),
                   help="which section the entry serves: for us, or against us")
    q.add_argument("--address", required=True,
                   help='the citation this quotation is OF, e.g. "8 CFR 214.2(f)(6)" - for law '
                        'it also picks the source file')
    q.add_argument("--from", dest="from_", required=True, metavar="WORDS",
                   help="the quotation's OPENING words, verbatim; must be unique in the file")
    q.add_argument("--to", dest="to", required=True, metavar="WORDS",
                   help="the quotation's CLOSING words, searched after the opening anchor")
    q.add_argument("--to-nth", dest="to_nth", type=int, default=None, metavar="N",
                   help="when the closing words repeat: which occurrence (1-based). Refused "
                        "rather than guessed - the guess loses the condition at the end")
    q.add_argument("--kind", choices=("law", "guidance"), default="law",
                   help="guidance = agency manuals/memoranda with no code address; needs --file, "
                        "a year in the address, and a demonstrable address-to-file link")
    q.add_argument("--not-proves", dest="not_proves", required=True, metavar="TEXT",
                   help="the applicability boundary - what this quotation does NOT prove")
    q.add_argument("--claim", help="entry title (default: the address)")
    q.add_argument("--file", help="the source file, when the address alone cannot pick one")
    q.add_argument("--id", dest="entry_id", metavar="ID",
                   help="explicit entry id (default: next free in the section)")
    q.add_argument("--apply", action="store_true", help="write; without it: a full dry-run")
    q.set_defaults(fn=cmd_bank_add)

    q = bank_common(bsub.add_parser(
        "dismiss", help="tick ONE open queue line WITHOUT banking it, recording why"))
    q.add_argument("fragment", help="a fragment of the quotation (matched against the queue's "
                                    "quotation lines only)")
    q.add_argument("--why", required=True, help="why the matter does not need this quotation")
    q.add_argument("--apply", action="store_true", help="write; without it: a dry-run")
    q.set_defaults(fn=cmd_bank_dismiss)

    p = common(sub.add_parser(
        "appendix",
        help="build the legal appendix from banked entries with FRESH verification"))
    p.add_argument("banks", nargs="*", metavar="BANK",
                   help="bank file(s); default: the matter's own bank")
    p.add_argument("--side", choices=("pro", "con", "any"), default="pro",
                   help="which side to include (default: pro - the appendix that goes in the "
                        "filing). Use 'con' only for internal review documents you label as "
                        "such; 'any' is deliberately not the default")
    p.add_argument("--out", "-o", help="write the appendix to this file (default: stdout)")
    p.add_argument("--json", action="store_true",
                   help="also print the build stats as JSON (for a hook or CI)")
    p.add_argument("--strict", action="store_true",
                   help="exit non-zero (1) when any entry was excluded by fresh verification")
    p.set_defaults(fn=cmd_appendix)

    p = common(sub.add_parser(
        "fetch-precedent",
        help="download a court decision AND prove it names the party, subject and court"))
    p.add_argument("url", help="URL of the decision (PDF, HTML - anything read_any can read)")
    p.add_argument("--party", required=True, metavar="TEXT",
                   help="the applicant/petitioner name or a distinctive fragment; a bare "
                        "surname collides between cases - prefer 'Smith, 12 I&N Dec. 205'")
    p.add_argument("--subject", required=True, metavar="TEXT",
                   help="the legal issue the opinion decides (e.g. 'adjustment of status')")
    p.add_argument("--court", required=True, metavar="TEXT",
                   help="the deciding body ('BIA', 'AAO', 'Ninth Circuit', 'Supreme Court')")
    p.add_argument("--into", metavar="DIR",
                   help="destination folder for successful writes (default: <matter>/precedents)")
    p.add_argument("--allow-unknown-source", action="store_true",
                   help="the host is not on any list this tool knows; you have looked at it")
    p.add_argument("--timeout", type=int, default=45)
    p.set_defaults(fn=cmd_fetch_precedent)

    p = common(sub.add_parser("sidecar", help="extract PDF text next to each PDF so grep sees it"))
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_sidecar)

    p = common(sub.add_parser("library", help="what is downloaded, what is unindexed"))
    p.add_argument("--recipes", action="store_true", help="print the retrieval recipes")
    p.add_argument("--bank", action="store_true",
                   help="also print the corpus <-> bank inventory: what is downloaded and "
                        "not analysed, and what is banked but has no file")
    p.add_argument("--suggest-fetches", dest="suggest_fetches", action="store_true",
                   help="for every banked entry with no file on disk, print the ready-to-run "
                        "download command. Implies --bank")
    p.set_defaults(fn=cmd_library)

    p = common(sub.add_parser(
        "coverage",
        help="bank <-> draft coverage: mines, unapplied entries, paraphrases, missing pieces"))
    p.add_argument("drafts", nargs="+", metavar="DRAFT",
                   help="the draft file(s) whose citations get checked against the bank")
    p.add_argument("--json", action="store_true",
                   help="print the report as JSON as well (for a hook or CI)")
    p.add_argument("--strict", action="store_true",
                   help="exit non-zero on findings: 5 for mines/paraphrases, 1 for unapplied/"
                        "missing-pieces only")
    p.set_defaults(fn=cmd_coverage)

    p = common(sub.add_parser(
        "fetch", help="download the text of a law into the inbox - no model in the path"))
    p.add_argument("url")
    p.add_argument("--allow-unknown-source", action="store_true",
                   help="the host is not on any list this tool knows; you have looked at it")
    p.add_argument("--timeout", type=int, default=45)
    p.set_defaults(fn=cmd_fetch)

    p = common(sub.add_parser(
        "intake", help="move the inbox into the library, detecting revisions"))
    p.add_argument("--address", help='the citation this file IS, e.g. "8 CFR 245.1"')
    p.add_argument("--into", help="library folder (default: the first source_dir)")
    p.set_defaults(fn=cmd_intake)

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
    p.add_argument("--probe-sites", dest="probe_sites", action="store_true",
                   help="hit the four known-good publisher URLs (govinfo x3 + eCFR API) once "
                        "each and print status codes - the ONLY doctor knob that touches the "
                        "network, opt-in and off by default")
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

    p = sub.add_parser("agents", help="print AGENTS.md - the working discipline for an AI "
                                      "assistant using this toolkit")
    p.set_defaults(fn=cmd_agents)

    p = sub.add_parser("scan-pdfs",
                       help="find PDFs with broken text layers (PScript5 / Type 3)")
    p.add_argument("directory", help="folder to scan recursively")
    p.add_argument("--skip", nargs="*", default=[], metavar="DIR",
                   help="directory basenames to skip")
    p.set_defaults(fn=cmd_scan_pdfs)

    p = sub.add_parser("fix-pdf",
                       help="repair a broken PScript5/Type 3 PDF via OCR overlay")
    p.add_argument("source", help="path to the broken PDF")
    p.add_argument("--output", "-o", help="output path (default: <source>_fixed.pdf)")
    p.add_argument("--dpi", type=int, default=300, help="render DPI (default: 300)")
    p.set_defaults(fn=cmd_fix_pdf)

    p = sub.add_parser("fix-pdfs",
                       help="scan a folder and repair all broken PDFs in batch")
    p.add_argument("directory", help="folder to scan recursively")
    p.add_argument("--output", "-o", required=True, help="output folder for fixed PDFs")
    p.add_argument("--skip", nargs="*", default=[], metavar="DIR",
                   help="directory basenames to skip")
    p.add_argument("--dpi", type=int, default=300, help="render DPI (default: 300)")
    p.set_defaults(fn=cmd_fix_pdfs)

    p = sub.add_parser("check-exhibits",
                       help="cross-check exhibits/forms in petitions against files on disk")
    p.add_argument("--petition", "-p", nargs="+", required=True,
                   help="petition document(s) or folder(s) to read for exhibit references")
    p.add_argument("--exhibits", "-e", nargs="+", required=True,
                   help="exhibit directory(ies) to scan for files")
    p.add_argument("--forms", "-f", nargs="*", default=None,
                   help="form directory(ies) to scan (optional)")
    p.add_argument("--out", help="write the report to this file")
    p.set_defaults(fn=cmd_check_exhibits)

    p = sub.add_parser("dump-forms",
                       help="extract filled AcroForm field values from PDF forms")
    p.add_argument("--dir", "-d", nargs="+", required=True,
                   help="directory(ies) to scan for PDF forms")
    p.add_argument("--out", "-o", help="output directory for per-form dumps and reports")
    p.add_argument("--nonempty", action="store_true",
                   help="only show filled fields, hide blanks")
    p.set_defaults(fn=cmd_dump_forms)

    p = sub.add_parser("selftest", help="behavioural checks; contacts nothing")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("install-hooks", help="wire the hooks into a Claude Code settings.json")
    p.add_argument("--scope", choices=["project", "user"], default="project")
    p.add_argument("--dir")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.set_defaults(fn=lambda a: __import__("krokai.install", fromlist=["main"]).main(a))

    # `upgrade` — one subcommand does the update, whichever install layout this copy is in.
    # See krokai/upgrade.py for the reasoning; the assistant-facing brief lives in
    # INSTALL-FOR-AI.md under "Updating".
    p = sub.add_parser("upgrade", help="update THIS install of krokai to the latest release")
    p.add_argument("--dry-run", action="store_true",
                   help="print what WOULD run and detect the install layout; change nothing")
    p.add_argument("--skip-hooks", action="store_true",
                   help="do not refresh install-hooks in the current matter after the update")
    p.add_argument("--scope", choices=["project", "user"], default="project",
                   help="hook refresh scope; ignored when --skip-hooks is set")
    p.add_argument("--dir", help="matter root; default: walk up from cwd looking for casefile.json")
    p.set_defaults(fn=lambda a: __import__("krokai.upgrade", fromlist=["cmd_upgrade"]).cmd_upgrade(a))

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
