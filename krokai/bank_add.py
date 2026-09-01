# -*- coding: utf-8 -*-
"""`krokai bank add` - the write gatekeeper. The quotation is SLICED from the source, never typed.

WHY A GATEKEEPER AND NOT AN INSTRUCTION
----------------------------------------
The bank's own header already says "verbatim only, after someone opened the source". The sister
project measured what an instruction is worth: an assistant re-typing six banked quotations *by
eye* lost two markers out of six - a model PRODUCES text, it does not copy it, and every produced
character is a chance to drift. So the gatekeeper takes two ANCHORS - the opening words and the
closing words - finds them in the source file, and writes `text[i:j]`. The text of the quotation
is never in the arguments; there is nowhere to mistype it.

THE GUARANTEES, EACH ONE PAID FOR
----------------------------------
* **The start anchor must be unique in the file.** Silently taking "the first occurrence" answers
  the question about the wrong copy of a phrase that legal text repeats constantly.
* **A repeated end anchor is a refusal, not a guess.** The same closing words often appear both
  BEFORE and AFTER the proviso; silently taking the first occurrence is precisely how a condition
  at the end of a provision is lost. `--to-nth N` makes the choice explicit - and stays visible
  in the command history, which is the audit trail.
* **The verifier runs BEFORE the write.** A slice is in the file by construction, so this is not
  theater: what it catches is the slice that stops one clause short of `except as provided...`
  (TRUNCATED_CONDITION), a slice of a superseded edition, a slice of a recital of somebody
  else's argument. A verdict outside ``verdicts.CLEAN`` refuses the write. There is no override
  flag - a documented escape becomes the default (measured in a sibling registry); if the slice
  really must stop there, the bank is still a hand-editable file and the decision is visible.
* **The edges are printed, plus what the source says NEXT.** A cut-off condition lives immediately
  after the quotation, so the slice's tail and the following characters of the source are shown
  even when every check passes.
* **The address is checked against the file.** A quotation can be genuine while the address beside
  it belongs to a different provision - the text verifier cannot see that (contributed by an
  outside reviewer of the sister project). For law, the file is RESOLVED from the address via the
  citation packs; for `--kind guidance` (agency manuals have no code address) the address must
  carry a year, must NOT parse as a code citation - otherwise a CFR quote could be laundered under
  a "guidance" label - and must demonstrably match the file's name or header.
* **"What this does NOT prove" is mandatory and has a floor.** An entry without an applicability
  boundary is more dangerous than no entry: it will be cited wider than it permits. A too-short
  boundary is the same field left empty while looking filled.
* **The queue is closed BY the write.** Banking a quotation ticks the matching queue line
  automatically; `dismiss` ticks one WITHOUT banking, and demands a reason. Matching is against
  the queue item's quotation text only - and it requires every substantial fragment to be
  contained, with at least one long one, because a stock legal opening shared by two different
  provisions once closed both (found independently by several reviewers).
* **The header keeps a ledger.** `Bank revision: <date> - entries: N` is refreshed on every
  gatekeeper write, and `krokai close` compares it with the body: entries that VANISH between
  writes are a silent deletion, which is the one edit an append-only file must make loud.
* **Reading and normalisation are the shared ones.** The anchors are normalised exactly like the
  corpus (NBSP, typographic dashes, curly quotes), because an anchor pasted from a PDF never
  matches otherwise; the sister project's private copies of these helpers produced both a false
  OPERATOR (from markdown residue) and a false NOT FOUND before they were deleted.

WHY DRY-RUN IS THE DEFAULT
---------------------------
The command prints everything it would write - the slice, its edges, the verdict, the target
section and id, the queue lines it would close - and writes nothing until `--apply`. A write
gatekeeper that writes on the first keystroke just moves the typo one level up.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import time

from .bank import BANK_HEADER, read_bank, render_entry
from .normalize import ELLIPSIS_RE, normalise, prepare_quote, strip_markdown
from .verdicts import CLEAN, SIX_CAUSES, label, meaning

__all__ = ["run_add", "run_dismiss", "revision_ledger", "SIDES", "ID_PREFIX",
           "MIN_NOT_PROVES", "MIN_WHY"]

# The two sides of the bank, and where each entry lands. The section names are structural:
# coverage checks (a planned layer) key on them, and the init template creates both, because a
# bank holding only the convenient quotations is a way of learning the inconvenient ones from
# the adjudicator.
SIDES = {"pro": "## For us", "con": "## Against us"}
ID_PREFIX = {"pro": "P", "con": "C"}

MIN_NOT_PROVES = 25
MIN_WHY = 20
# Advisory only. A whole subsection is sometimes a legitimate quotation; a mis-anchored slice is
# usually enormous. The dry-run default plus the printed edges make the difference visible.
LONG_SLICE_WARN = 1500

_REV_RE = re.compile(r"(?m)^Bank revision: .*? entries: (\d+)")
_ID_LINE_RE = re.compile(r"(?m)^###\s+(§[\w.-]+)")
_H2_RE = re.compile(r"(?m)^## ")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# An identifier token: digits with letters/hyphens glued on ("602-0199", "245a"). The fallback
# link for a guidance address whose name is essentially one token, where "two significant words"
# is unsatisfiable.
_IDENT_RE = re.compile(r"[a-z]*\d[\w-]*", re.I)


def _cell(s):
    """Make a value safe for a markdown table cell: `|` starts a new column mid-sentence."""
    return (s or "").replace("|", "\\|").replace("\n", " ")


def _find_all(hay, needle):
    out, i = [], hay.find(needle)
    while i >= 0:
        out.append(i)
        i = hay.find(needle, i + 1)
    return out


def _norm_anchor(s):
    """An anchor goes through the same preparation as a quotation: markdown stripped, wrapping
    quotes removed, typography folded. Without this, an anchor pasted from a PDF - NBSP,
    guillemets, an em-dash - never matches a corpus that was normalised on the way in."""
    return normalise(prepare_quote(s or ""))


def _norm_match(s):
    """The containment form used for queue matching - same convention as ``bank.in_bank``."""
    return normalise(strip_markdown(s or "")).lower()


def _write_atomic(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    tmp = path + ".krokai-tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(text)
    os.replace(tmp, path)


# ------------------------------------------------------------------------------- source resolve
def _corpus_lookup(corpus):
    """Case/sep-insensitive path -> canonical corpus path. Windows serves the same file under
    mixed case and mixed slashes; a naive `in corpus.paths` test would refuse it."""
    return {os.path.normcase(os.path.abspath(p)): p for p in corpus.paths}


def _resolve_law(address, file_arg, corpus, packs, printer):
    """The corpus file the address points at, or (None, refusal-exit-code)."""
    from .address import KeyMap

    keys = packs.keys([address])
    if not keys:
        printer("🔴 the address «%s» is not recognised by any loaded citation pack." % address)
        printer("   If this is agency guidance (a policy manual, a memorandum), say so:")
        printer("   --kind guidance --file <the source file>. A code citation must parse,")
        printer("   or the address written into the bank would be unverifiable forever.")
        return None, 3
    km = KeyMap(corpus, packs)
    resolved = sorted({p for k in keys for p in km.resolve(k)})
    labels = "; ".join(sorted(packs.label(k) for k in keys))
    if not resolved:
        printer("🔴 %s is not in your sources folder - nothing to slice from." % labels)
        printer("   Download the source first (`krokai library --recipes` lists the retrieval")
        printer("   recipes, `krokai fetch <url>` brings it in with no model in the path).")
        return None, 3
    if file_arg:
        lookup = _corpus_lookup(corpus)
        want = os.path.normcase(os.path.abspath(file_arg))
        path = lookup.get(want)
        if not path:
            printer("🔴 --file %s is not in the corpus (or was excluded from it)." % file_arg)
            printer("   `krokai library` shows what is indexed and what was excluded, and why.")
            return None, 3
        if path not in resolved:
            printer("🔴 --file %s does not match the address %s." % (os.path.basename(path), labels))
            printer("   The files that DO match:")
            for p in resolved[:10]:
                printer("      %s" % p)
            return None, 3
        return path, 0
    if len(resolved) > 1:
        printer("🔴 the address %s matches more than one corpus file - choosing silently would"
                % labels)
        printer("   answer the question about the wrong copy. Repeat with --file <one of these>:")
        for p in resolved[:10]:
            note = "  (SUPERSEDED)" if corpus.is_superseded(p) else ""
            printer("      %s%s" % (p, note))
        return None, 3
    return resolved[0], 0


def _guidance_link(address, path, corpus, printer):
    """The address<->file link for guidance: a year plus matching words, shown as evidence.

    Guidance has no code address, so the strongest available binding is demonstrative: the year
    appears in the file's name or header, and either two significant words of the address do too,
    or - for an address that is essentially one identifier token - that token is in the NAME.
    """
    ym = _YEAR_RE.search(address or "")
    if not ym:
        printer("🔴 a guidance address must carry a YEAR (e.g. «Policy Manual Vol. 7 (2026)»):")
        printer("   guidance is revised without renumbering, and an undated guidance quotation")
        printer("   cannot be re-checked against the edition it was taken from.")
        return None, 3
    year = ym.group(0)
    name = os.path.basename(path).lower()
    try:
        head = corpus.text_of(path)[:600].lower()
    except (KeyError, ValueError):
        head = ""
    words = [w for w in re.findall(r"[0-9a-z]+", (address or "").lower())
             if len(w) >= 4 and not w.isdigit()]
    hits = sorted({w for w in words if w in name or w in head})
    idents = [t.lower() for t in _IDENT_RE.findall(address or "")
              if any(c.isdigit() for c in t) and t != year and len(t) >= 3]
    ident_hits = sorted({t for t in idents if t in name})
    year_ok = year in name or year in head
    if not year_ok or (len(hits) < 2 and not ident_hits):
        printer("🔴 the guidance address does not demonstrably match the file:")
        printer("   year %s in name/header: %s" % (year, "yes" if year_ok else "NO"))
        printer("   address words found in name/header: %s" % (", ".join(hits) or "none"))
        if idents:
            printer("   identifier tokens found in the name: %s" % (", ".join(ident_hits) or "none"))
        printer("   Fix the address, or point --file at the file the address describes.")
        return None, 3
    return {"year": year, "hits": hits or ident_hits}, 0


# ------------------------------------------------------------------------------------ the slice
def _slice(text, nfrom, nto, to_nth, printer):
    """`(start, end)` of the slice, or `(None, exit_code)` after a loud refusal."""
    starts = _find_all(text, nfrom)
    if not starts:
        printer("🔴 the start anchor was not found in the source file.")
        printer("   Anchors are normalised like the source (NBSP, dashes, curly quotes), so this")
        printer("   is a wording difference: open the file and copy the opening words exactly.")
        return None, 3
    if len(starts) > 1:
        printer("🔴 the start anchor occurs %d times in the source file - it must be UNIQUE."
                % len(starts))
        printer("   Make it longer or more specific; a silently chosen occurrence is the wrong")
        printer("   copy of a phrase legal text repeats constantly.")
        return None, 3
    i = starts[0]
    search_from = i + len(nfrom)
    ends = [search_from + k for k in _find_all(text[search_from:], nto)]
    if not ends:
        printer("🔴 the end anchor was not found AFTER the start anchor.")
        printer("   The anchors must not overlap; the end anchor is searched after the start")
        printer("   anchor ends. Check the wording against the file.")
        return None, 3
    if len(ends) > 1 and not to_nth:
        printer("🔴 the end anchor occurs %d times after the start - refusing to guess."
                % len(ends))
        printer("   Taking the first occurrence silently is exactly how a condition at the end")
        printer("   of a provision is lost. Pick one explicitly with --to-nth N:")
        for n, j in enumerate(ends[:8], 1):
            end = j + len(nto)
            printer("      --to-nth %d  -> a %d-character slice ending «…%s»"
                    % (n, end - i, text[max(i, end - 70):end]))
        if len(ends) > 8:
            printer("      ... and %d more" % (len(ends) - 8))
        return None, 3
    n = to_nth or 1
    if not 1 <= n <= len(ends):
        printer("🔴 --to-nth %d, but the end anchor occurs %d time(s) after the start." % (n, len(ends)))
        return None, 3
    return (i, ends[n - 1] + len(nto)), 0


# ---------------------------------------------------------------------------------- bank write
def _existing_ids(bank_text):
    return set(m.group(1) for m in _ID_LINE_RE.finditer(bank_text or ""))


def _next_id(bank_text, side):
    pref = "§%s-" % ID_PREFIX[side]
    nums = [int(m.group(1))
            for m in re.finditer(re.escape(pref) + r"(\d+)\b", bank_text or "")]
    return "%s%d" % (pref, max(nums) + 1 if nums else 1)


def _insert_entry(text, side, entry):
    """Append the entry at the END of its side's section, creating the section if the bank
    predates the two-section header. Section boundary = the next `## ` heading (an entry's own
    heading is `### `, which does not match)."""
    heading = SIDES[side]
    h = re.search(r"(?m)^%s\s*$" % re.escape(heading), text or "")
    if not h:
        base = (text or "").rstrip("\n")
        sep = "\n\n" if base else ""
        return base + sep + heading + "\n" + entry.rstrip("\n") + "\n", "created section «%s»" % heading
    m = _H2_RE.search(text, h.end())
    at = m.start() if m else len(text)
    return (text[:at].rstrip("\n") + "\n" + entry.rstrip("\n") + "\n\n" + text[at:].lstrip("\n"),
            "appended to «%s»" % heading)


def revision_ledger(bank_text):
    """`(ledger_count_or_None, body_count)` - what the header CLAIMS versus what the body HOLDS.

    `krokai close` compares the two: a body smaller than the ledger means entries vanished since
    the last gatekeeper write, which in an append-only file is the deletion shape and must be
    loud. A body larger than the ledger is merely hand-written entries the next `--apply` will
    fold into the count.
    """
    m = _REV_RE.search(bank_text or "")
    return (int(m.group(1)) if m else None), (bank_text or "").count("\n### ")


def _update_revision(text):
    n = text.count("\n### ")
    line = ("Bank revision: %s - entries: %d - refreshed by `krokai bank add`"
            % (time.strftime("%Y-%m-%d"), n))
    if _REV_RE.search(text):
        return _REV_RE.sub(line, text, count=1)
    m = re.search(r"(?m)^---\s*$", text)
    if m:
        return text[:m.start()] + line + "\n\n" + text[m.start():]
    # A hand-rolled bank with no header rule block at all: put the ledger under the first line.
    nl = text.find("\n")
    if nl < 0:
        return text + "\n" + line + "\n"
    return text[:nl + 1] + "\n" + line + "\n" + text[nl + 1:]


# --------------------------------------------------------------------------------------- queue
def _queue_blocks(lines):
    """Open queue items as `(first_line_index, [line_indexes], quote_text)`.

    Only the item's quotation lines (`> …`) participate in matching - the verdict, the source
    name and the detail line are the tool's own prose, and matching on them would let a verdict
    word "close" an unrelated quotation.
    """
    out, cur, quotes = [], None, []
    for idx, ln in enumerate(lines):
        if re.match(r"^\s*-\s*\[.\]", ln) or ln.startswith("## "):
            if cur is not None:
                out.append((cur, " ".join(quotes)))
            cur, quotes = None, []
            if re.match(r"^\s*-\s*\[ \]", ln):
                cur = idx
            continue
        if cur is not None:
            m = re.match(r"^\s*>\s?(.*)$", ln)
            if m:
                quotes.append(m.group(1))
    if cur is not None:
        out.append((cur, " ".join(quotes)))
    return out


def _pieces(quote_text):
    """The item's quotation, split on its ellipses, substantial pieces only. The 400-character
    cap the queue hook applies can cut the final word in half; the trim keeps that artefact from
    defeating a legitimate containment."""
    qn = _norm_match(quote_text)
    if len(qn) >= 395 and " " in qn:
        qn = qn[:qn.rfind(" ")]
    parts = [p.strip(" .,;:-—") for p in ELLIPSIS_RE.split(qn)]
    return [p for p in parts if len(p) >= 40]


def _closable(quote_text, banked_norm):
    """Does the banked quotation close this queue item?

    ALL substantial pieces contained AND at least one long piece. The length floor is measured:
    a stock legal opening shared by two different provisions once closed both queue lines, so a
    short containment alone proves nothing.
    """
    pieces = _pieces(quote_text)
    if not pieces or not any(len(p) >= 60 for p in pieces):
        return False
    return all(p in banked_norm for p in pieces)


def _close_queue(queue_path, banked_norm, bank_id, apply_, printer):
    """Tick every open queue line the banked quotation covers. Returns how many."""
    if not os.path.exists(queue_path):
        return 0
    raw = io.open(queue_path, encoding="utf-8", errors="replace").read()
    lines = raw.split("\n")
    hits = [(idx, q) for idx, q in _queue_blocks(lines) if _closable(q, banked_norm)]
    if not hits:
        return 0
    stamp = time.strftime("%Y-%m-%d")
    for idx, _q in reversed(hits):
        lines[idx] = re.sub(r"\[ \]", "[x]", lines[idx], count=1)
        lines.insert(idx + 1, "      closed: banked as %s (%s)" % (bank_id, stamp))
    for idx, _q in hits:
        printer("   queue: %s «%s»" % ("closed" if apply_ else "would close",
                                       lines[idx].strip()[:90]))
    if apply_:
        _write_atomic(queue_path, "\n".join(lines))
    return len(hits)


# ----------------------------------------------------------------------------------------- add
def run_add(a, printer=print):
    """The whole gatekeeper pass, in the order the guarantees demand. Dry-run unless --apply."""
    from .citations import load_packs
    from .config import load
    from .run import corpus_for
    from .verify import check, neighbours

    cfg = load(a.dir)

    not_proves = (a.not_proves or "").strip()
    if len(not_proves) < MIN_NOT_PROVES:
        printer("🔴 --not-proves is %d characters; the floor is %d." % (len(not_proves), MIN_NOT_PROVES))
        printer("   The applicability boundary is the field that catches a dropped proviso three")
        printer("   weeks later. A one-liner shorter than this is the field left empty while")
        printer("   looking filled - write down what the OTHER side will say about this quotation.")
        return 2

    nfrom, nto = _norm_anchor(a.from_), _norm_anchor(a.to)
    if not nfrom or not nto:
        printer("🔴 --from and --to must both carry words of the source.")
        return 2

    corpus = corpus_for(cfg, quiet=a.quiet)
    packs = load_packs(cfg["citation_packs"])

    # -- which file ----------------------------------------------------------------------------
    if a.kind == "guidance":
        if packs.keys([a.address]):
            printer("🔴 «%s» parses as a code citation - it cannot be banked as guidance."
                    % a.address)
            printer("   A CFR/USC quotation under a guidance label would dodge the address")
            printer("   binding that exists for it. Drop `--kind guidance`.")
            return 3
        if not a.file:
            printer("🔴 guidance has no code address to resolve a file from: give --file <path>.")
            return 3
        lookup = _corpus_lookup(corpus)
        path = lookup.get(os.path.normcase(os.path.abspath(a.file)))
        if not path:
            printer("🔴 --file %s is not in the corpus (or was excluded). `krokai library` shows "
                    "what is indexed." % a.file)
            return 3
        link, rc = _guidance_link(a.address, path, corpus, printer)
        if not link:
            return rc
    else:
        path, rc = _resolve_law(a.address, a.file, corpus, packs, printer)
        if not path:
            return rc

    if corpus.is_superseded(path):
        printer("🔴 %s is marked SUPERSEDED by the law register - a newer edition of the same "
                "provision is on disk." % os.path.basename(path))
        printer("   Bank from the edition in force (or decide, by hand and in writing, that the")
        printer("   matter needs the superseded text - the bank file is yours to edit).")
        return 3

    text = corpus.text_of(path)
    rel = os.path.relpath(path, cfg.root)
    printer("source  : %s%s" % (rel, "" if a.kind != "guidance" else "  (guidance)"))

    # -- the slice ------------------------------------------------------------------------------
    span, rc = _slice(text, nfrom, nto, a.to_nth, printer)
    if not span:
        return rc
    i, j = span
    quote = text[i:j]
    if len(quote) < cfg["min_quote_length"]:
        printer("🔴 the slice is %d characters - under this matter's minimum quotation length "
                "(%d)." % (len(quote), cfg["min_quote_length"]))
        printer("   A span this short matches everywhere and proves nothing; widen the anchors.")
        return 3
    printer("slice   : %d characters (offsets %d-%d)" % (len(quote), i, j))
    if len(quote) > LONG_SLICE_WARN:
        printer("   🟡 unusually long - check both edges below; a mis-anchored slice is usually "
                "enormous.")
    head = quote[:160]
    tail = quote[-160:]
    printer("  starts: «%s%s»" % (head, "…" if len(quote) > 160 else ""))
    if len(quote) > 160:
        printer("  ends  : «…%s»" % tail)
    after_src = text[j:j + 160]
    if after_src:
        printer("  source continues: «%s…»" % after_src)
        if after_src.lstrip().startswith((",", ";", "—", "–", "-")):
            printer("  🔴 the source continues with a CONNECTOR - the slice may stop mid-provision.")
            printer("     A condition sitting immediately after a quotation is a condition you")
            printer("     have dropped. Read the continuation; extend --to if it governs.")

    # -- verify BEFORE the write ----------------------------------------------------------------
    verdict, where, detail = check(quote, corpus)
    lang = cfg["language"]
    printer("verdict : %s - %s" % (label(verdict, lang).upper(), meaning(verdict, lang)))
    if detail:
        printer("          %s" % detail)
    if verdict not in CLEAN:
        printer("\n🔴 REFUSED before writing: the verifier does not clear this slice.")
        if verdict == "NOT_FOUND":
            for k, cause in enumerate(SIX_CAUSES, 1):
                printer("     %d. %s" % (k, cause))
        else:
            printer("   Fix the slice (usually: extend --to past the clause the detail quotes),")
            printer("   or repair the corpus copy - never widen the checker.")
        return 3
    weight = "🟢"
    if verdict != "VERIFIED":
        weight = "🟡"
        printer("   🟡 banked with a caveat: %s - the entry is weighted accordingly." % verdict)

    nb_before = nb_after = ""
    for p, before, after in neighbours(quote, corpus):
        if p == path or not (nb_before or nb_after):
            nb_before, nb_after = before, after
        if p == path:
            break
    # Printed even though the source-continues line above already showed the raw tail: the
    # neighbours are SENTENCES, which is what a person can actually read, and they go into the
    # entry - so what the entry will claim is on the screen before --apply.
    if nb_before:
        print_nb = nb_before[-220:]
        printer("neighbour before: …%s" % print_nb)
    if nb_after:
        printer("neighbour after : %s…" % nb_after[:220])

    # -- entry ----------------------------------------------------------------------------------
    bank_path = cfg.abs(cfg["bank"])
    bank_text = read_bank(bank_path)
    if a.entry_id:
        eid = a.entry_id if a.entry_id.startswith("§") else "§" + a.entry_id
        if eid in _existing_ids(bank_text):
            printer("🔴 %s is already taken in the bank - ids are never reused, because a "
                    "reused id silently redirects every existing reference." % eid)
            return 3
    else:
        eid = _next_id(bank_text, a.side)

    recheck_cmd = 'krokai bank add --side %s --address "%s" --from "%s" --to "%s"' % (
        a.side, a.address, nfrom[:60], nto[-60:])
    if a.to_nth:
        recheck_cmd += " --to-nth %d" % a.to_nth
    edition = " - at banking: %s" % verdict
    if a.kind == "guidance":
        with open(path, "rb") as fh:
            sha = hashlib.sha256(fh.read()).hexdigest()
        edition += " - source sha256 %s" % sha[:16]

    entry = render_entry(
        id=eid, weight=weight, claim=_cell(a.claim or a.address),
        quote=quote,
        address=_cell(a.address),
        on_disk=_cell(rel),
        recheck=_cell("re-run `%s` - the slice, its edges and the verdict must reproduce"
                      % recheck_cmd),
        who="sliced from the source by `krokai bank add` - not typed",
        edition=_cell(edition),
        before=_cell(nb_before or "—"), after=_cell(nb_after or "—"),
        not_proved=_cell(not_proves),
    )
    new_bank, where_put = _insert_entry(bank_text or BANK_HEADER, a.side, entry)
    new_bank = _update_revision(new_bank)
    printer("entry   : %s -> %s" % (eid, where_put))

    # -- queue ----------------------------------------------------------------------------------
    closed = _close_queue(cfg.abs(cfg["queue"]), _norm_match(quote), eid, a.apply, printer)
    if not closed:
        printer("   queue: no open line matches this quotation.")

    if not a.apply:
        printer("\nDRY RUN - nothing was written. Re-run with --apply to write.")
        return 0

    _write_atomic(bank_path, new_bank)
    # Re-read from DISK, never trust the buffer: the write is only real if the file now says so.
    reread = read_bank(bank_path)
    ids = [m.group(1) for m in _ID_LINE_RE.finditer(reread)]
    ledger, body = revision_ledger(reread)
    if ids.count(eid) != 1 or ledger != body:
        printer("🔴 post-write re-read FAILED: id %s appears %d time(s), ledger says %s, body "
                "holds %d. The file is in an unexpected state - inspect it before writing again."
                % (eid, ids.count(eid), ledger, body))
        return 1
    printer("\nwritten : %s (re-read from disk: %s present once, ledger %d = body %d)"
            % (bank_path, eid, ledger, body))
    return 0


# ------------------------------------------------------------------------------------- dismiss
def run_dismiss(a, printer=print):
    """Tick ONE open queue line without banking it, with a reason that meets the floor."""
    from .config import load

    cfg = load(a.dir)
    why = (a.why or "").strip()
    if len(why) < MIN_WHY:
        printer("🔴 --why is %d characters; the floor is %d. «Not needed» teaches nothing to "
                "the person who re-opens the queue in three weeks - say why the matter does "
                "not need this quotation." % (len(why), MIN_WHY))
        return 2
    frag = _norm_match(a.fragment)
    if not frag:
        printer("🔴 give a fragment of the quotation to dismiss (matched against the queue's "
                "quotation lines only).")
        return 2
    queue_path = cfg.abs(cfg["queue"])
    if not os.path.exists(queue_path):
        printer("queue: no queue file at %s - nothing to dismiss." % queue_path)
        return 3
    raw = io.open(queue_path, encoding="utf-8", errors="replace").read()
    lines = raw.split("\n")
    hits = [(idx, q) for idx, q in _queue_blocks(lines) if frag in _norm_match(q)]
    if not hits:
        printer("🔴 no OPEN queue line's quotation contains that fragment. `krokai bank` lists "
                "the open lines.")
        return 3
    if len(hits) > 1:
        printer("🔴 the fragment matches %d open lines - dismissing several under one reason "
                "hides a decision. Narrow it; the matches:" % len(hits))
        for idx, _q in hits[:8]:
            printer("      • %s" % lines[idx].strip()[:100])
        return 3
    idx, _q = hits[0]
    stamp = time.strftime("%Y-%m-%d")
    lines[idx] = re.sub(r"\[ \]", "[x]", lines[idx], count=1)
    lines.insert(idx + 1, "      dismissed: %s (%s)" % (why, stamp))
    printer("%s: %s" % ("dismissed" if a.apply else "would dismiss", lines[idx].strip()[:100]))
    printer("   reason recorded: %s" % why)
    if not a.apply:
        printer("\nDRY RUN - nothing was written. Re-run with --apply to write.")
        return 0
    _write_atomic(queue_path, "\n".join(lines))
    printer("written : %s" % queue_path)
    return 0
