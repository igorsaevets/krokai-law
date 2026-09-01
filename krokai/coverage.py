# -*- coding: utf-8 -*-
"""Coverage: the second-order questions the string check cannot answer.

WHAT THIS ANSWERS
-----------------
`krokai check` answers *"are these words in some primary source?"* and, folded with the address
layer, *"in the source whose address you printed?"*. Both are essential, and neither is enough. A
draft can be citation-perfect and still be a defective document, for reasons that show up only
when the draft is compared against the BANK - the ground the matter has decided it stands on.

Three failure shapes were paid for in the sister project before this module existed:

* **MINES.** The draft cites a rule the bank has classified as against us. The classic case,
  measured verbatim: 8 CFR 214.2(f)(8)(i) was in the bank as §Π-13 (against us), and the same
  filing rested on it as its own affirmative support. Nothing about the quotation was wrong; the
  quotation itself was flawless. The defect was that the bank knew the ground was hostile and the
  drafter did not. A string check cannot see that; a coverage check must.

* **UNAPPLIED.** The bank has an entry for us at address X, and the draft never cites X. Sometimes
  this is fine - a shelf takes more books than any one argument uses - and sometimes it is a rule
  everyone forgot. Naming it out loud is what makes the difference visible.

* **PARAPHRASE ONLY.** The draft cites address X, the bank holds a verbatim quotation of X, and the
  draft's rendering of it is a summary. A summary is not a quotation, and an adjudicator following
  the pincite finds words that do not match the source - the same *appearance* as fabrication,
  which is what this toolkit exists to catch. The bank has the exact wording sitting right there;
  the coverage check names the entries that were not used.

And a fourth, added after live forensics of the sister project (round 79 phase 1):

* **UNPARSED ENTRIES.** A bank entry banked by the gatekeeper has an application boundary and a
  verified quotation. A bank entry written by hand years ago may have neither. The count is
  measured, not guessed: entries whose applicability is not written down get cited wider than they
  permit - the same defect the "what this does NOT prove" field exists to catch, one level up.

🔴 WHY THE ADDRESS LAYER HERE IS THINNER THAN `packs`
------------------------------------------------------
The citation packs used by `check` return coarse keys - `("cfr", "8", "214")` - because the
question they answer is *"what file could hold this rule?"*, and the file for the whole part
holds all of its subsections. Coverage asks a different question: *"is THIS specific subparagraph
the one the bank marks hostile?"*. So a coverage key carries the subitems verbatim:
`("cfr", "8", "214", "2", "f", "8", "i")`. The packs' coarse key is untouched; this module
maintains its own extractor for the fine one.

🔴 AND WHY THE PARENT->CHILD RELATION IS ASYMMETRIC
---------------------------------------------------
Measured in the sister project: a marginal note that read "8 CFR 214.2(f)" - the tab label of an
entire subsection - was being counted as a mine against every specific paragraph the bank held
under (f), including several the drafter had never touched. So the relation `related(a, b)` is
True only when the WIDER of the two is narrow enough to be a specific citation rather than a
category: for CFR that means at least three subitem levels past the part (i.e. section plus two
paragraphs), for USC/INA one subitem past the section. Exact-equality matches always fire; only
prefix-relations require the threshold.
"""
from __future__ import annotations

import io
import os
import re

from .normalize import normalise, strip_markdown

__all__ = ["parse_addresses", "parse_bank_entries", "related", "sub_levels",
           "analyse", "render_report", "corpus_bank_inventory", "controls_pass",
           "USC_TO_INA", "MINE", "UNAPPLIED", "PARAPHRASE", "UNPARSED", "AMBIGUOUS",
           "BASE_LEN", "SUB_THRESHOLD"]

# ---------------------------------------------------------------------------------- USC -> INA
# Title 8 of the U.S. Code is the codification of the Immigration and Nationality Act. The two
# citation systems name the same provisions, and a document that cites `8 U.S.C. § 1255(k)` and a
# bank entry that cites «section 245(k) of the Act» are talking about the same law - but their
# fine keys are different tuples, and the coverage check will miss the mine unless one is folded
# into the other. Measured in the sister project: an empty MINES section under `USC_TO_INA=None`
# hid a hit the panel later caught by hand.
#
# The mapping is authoritative (USCIS publishes it under the same name it uses on the code) and
# is deliberately restricted to the sections a working immigration practice cites. Adding a row
# does not risk over-firing - the map is one-to-one - and a missing row degrades to "no INA fold"
# for that section, not to a wrong fold. If a section needed here is not in the table, add the
# row; do not paper over it with a heuristic.
USC_TO_INA = {
    "1101": "101", "1102": "102", "1103": "103", "1104": "104",
    "1151": "201", "1152": "202", "1153": "203", "1154": "204", "1155": "205",
    "1157": "207", "1158": "208", "1159": "209",
    "1181": "211", "1182": "212", "1183": "213", "1184": "214", "1185": "215",
    "1186a": "216", "1186b": "216A",
    "1187": "217", "1188": "218", "1189": "219",
    "1201": "221", "1202": "222", "1203": "223",
    "1225": "235", "1226": "236", "1227": "237", "1228": "238",
    "1229": "239", "1229a": "240", "1229b": "240A", "1229c": "240B",
    "1231": "241", "1232": "241A",
    "1252": "242", "1253": "243", "1254a": "244",
    "1255": "245", "1255a": "245A", "1256": "246", "1257": "247",
    "1258": "248", "1259": "249",
    "1281": "251", "1282": "252", "1283": "253", "1284": "254", "1285": "255",
    "1286": "256", "1287": "257", "1288": "258",
    "1301": "261", "1302": "262", "1303": "263", "1304": "264", "1305": "265",
    "1306": "266",
    "1321": "271", "1322": "272", "1323": "273", "1324": "274",
    "1324a": "274A", "1324b": "274B", "1324c": "274C",
    "1325": "275", "1326": "276", "1327": "277", "1328": "278", "1329": "279",
    "1330": "280",
    "1361": "291", "1362": "292", "1363": "293",
    "1401": "301", "1402": "302", "1403": "303", "1404": "304", "1405": "305",
    "1406": "306", "1407": "307", "1408": "308", "1409": "309",
    "1421": "310", "1422": "311", "1423": "312", "1424": "313",
    "1427": "316", "1428": "317", "1429": "318", "1430": "319",
    "1431": "320", "1432": "321", "1433": "322", "1434": "323", "1435": "324",
    "1436": "325", "1437": "326", "1438": "327", "1439": "328", "1440": "329",
    "1441": "330", "1442": "331", "1443": "332", "1444": "333", "1445": "334",
    "1446": "335", "1447": "336", "1448": "337", "1449": "338",
    "1451": "340", "1452": "341", "1453": "342", "1454": "343", "1455": "344",
    "1481": "349", "1482": "350", "1483": "351",
    "1501": "358", "1502": "359", "1503": "360", "1504": "361",
    "1521": "411",
    "1601": "501", "1602": "502",
}

# The reverse. Two names for one home, computed - not restated - so a fix on the source lands on
# the mirror at import.
INA_TO_USC = {v.lower(): k for k, v in USC_TO_INA.items()}


# ---------------------------------------------------------------------------------- regexes
# CFR: 8 CFR 214.2(f)(8)(i). The section number and the parenthetical tail are optional; the
# extractor captures whatever depth the drafter wrote. Alternates for "C.F.R." with dots and
# without, and the section symbol.
_CFR_RX = re.compile(
    r"\b(\d{1,2})\s*C\.?\s?F\.?\s?R\.?\s*(?:§+\s*)?"
    r"(\d{1,4})(?:\.(\d+[A-Za-z]?))?"
    r"((?:\(\s*[^()\s]{1,8}\s*\))*)")

# USC: 8 U.S.C. § 1255(k)(1). Same subitem-optional shape.
_USC_RX = re.compile(
    r"\b(\d{1,2})\s*U\.?\s?S\.?\s?C\.?\s*(?:§+\s*)?"
    r"(\d+[A-Za-z]?)"
    r"((?:\(\s*[^()\s]{1,8}\s*\))*)")

# INA in its explicit forms: `INA § 245(k)` and `section 245(k) of the Act`. The bare form
# `section 245(k)` is deliberately NOT accepted here - without the qualifier the same words
# could be a state or regulatory section. The design canon (R79 study §6.4) names both explicit
# forms as the ones that must reduce to an INA key.
_INA_EXPLICIT_RX = re.compile(
    r"\bINA\b\s*(?:§+\s*)?(\d+[A-Za-z]?)((?:\(\s*[^()\s]{1,8}\s*\))*)")
_ACT_SECTION_RX = re.compile(
    r"\bsections?\s+(\d+[A-Za-z]?)((?:\(\s*[^()\s]{1,8}\s*\))*)\s+of\s+the\s+Act\b",
    re.I)

# Public Law and Federal Register - fine keys are the same as the coarse keys, no subitems.
_PL_RX = re.compile(
    r"\bPub\.?\s?L\.?\s*(?:No\.?\s*)?(\d{1,3})[-–](\d{1,4})")
_FR_RX = re.compile(
    r"\b(\d{2,3})\s*(?:F\.?\s?R\.?|Fed\.\s?Reg\.?)\s*(\d{3,6})")

# Parentheticals inside a citation's tail: `(f)(8)(i)` -> `["f", "8", "i"]`. Whitespace
# inside the parens is preserved on capture and stripped here - real filings have
# `(f) (8) (i)` occasionally.
_PAREN_RX = re.compile(r"\(\s*([^()\s]{1,8})\s*\)")


# ---------------------------------------------------------------------------------- keys
# The base length of a fine key by kind. Anything past the base is a subitem, and the count of
# subitems is what decides whether a prefix relation fires.
BASE_LEN = {"cfr": 3, "usc": 3, "ina": 2, "publaw": 3, "fr": 3}

# The subitem-count floor at which a WIDER address is narrow enough to imply matches against
# NARROWER ones. Higher for CFR because a CFR "part" is a whole chapter of regulations and its
# tab-label (`214.2(f)`) legitimately appears next to many different rules; the sister project
# measured false mines from exactly that shape. Lower for USC/INA because a section is a
# single-topic provision by convention. Bare exact-equality matches always fire regardless of
# these floors; the floors only gate PREFIX matches.
SUB_THRESHOLD = {"cfr": 3, "usc": 1, "ina": 1, "publaw": 0, "fr": 0}


def sub_levels(key):
    """Count of subitem elements past the kind's base. `("cfr","8","214","2","f")` -> 2."""
    base = BASE_LEN.get(key[0], len(key))
    return max(0, len(key) - base)


def _is_narrow(key):
    return sub_levels(key) >= SUB_THRESHOLD.get(key[0], 0)


def related(a, b):
    """Do these two fine keys point at the same passage?

    Exact match always fires. Prefix match fires only when the WIDER of the two is narrow
    enough to be a specific citation rather than a tab label (`SUB_THRESHOLD`). Different
    kinds never match here; a USC-to-INA fold has to be resolved BEFORE calling this - the
    extractor emits both forms for every title-8 hit, and it is the caller's job to pass all
    of them.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    if a[0] != b[0]:
        return False
    wider, narrower = (a, b) if len(a) <= len(b) else (b, a)
    if narrower[:len(wider)] != wider:
        return False
    return _is_narrow(wider)


def _parens_from_tail(tail):
    """Extract subitem tokens from a raw parenthetical tail like `(f)(8)(i)`."""
    return [m.group(1).lower() for m in _PAREN_RX.finditer(tail or "")]


def _cfr_keys(title, part, section, tail):
    parts = [title.lower(), part.lower()]
    if section:
        parts.append(section.lower())
    parts.extend(_parens_from_tail(tail))
    return {tuple(["cfr"] + parts)}


def _usc_keys(title, section, tail):
    """USC key plus its INA twin when the mapping exists.

    The two-form emission is what lets `("usc","8","1255","k")` and `("ina","245","k")` count
    as the same passage in `related()` (which is otherwise strict about the kind).
    """
    subs = _parens_from_tail(tail)
    section_l = section.lower()
    out = {tuple(["usc", title.lower(), section_l] + subs)}
    if title == "8":
        ina = USC_TO_INA.get(section_l)
        if ina:
            out.add(tuple(["ina", ina.lower()] + subs))
    return out


def _ina_keys(section, tail):
    subs = _parens_from_tail(tail)
    section_l = section.lower()
    out = {tuple(["ina", section_l] + subs)}
    usc = INA_TO_USC.get(section_l)
    if usc:
        # Emit an "8 USC" companion so a draft that cites USC and a bank that cites INA fold.
        out.add(tuple(["usc", "8", usc.lower()] + subs))
    return out


def _label(key):
    """A human-readable string for a fine key. Used in the report so the same subitem depth the
    key carries is what the reader sees; a coarse-key label would say "part 214" for a mine
    that is actually about `(f)(8)(i)`."""
    if key[0] == "cfr" and len(key) >= 3:
        base = "%s CFR %s" % (key[1], key[2])
        if len(key) >= 4:
            base += "." + key[3]
        subs = "".join("(%s)" % s for s in key[4:])
        return base + subs
    if key[0] == "usc" and len(key) >= 3:
        base = "%s U.S.C. § %s" % (key[1], key[2])
        subs = "".join("(%s)" % s for s in key[3:])
        return base + subs
    if key[0] == "ina" and len(key) >= 2:
        base = "INA § %s" % key[1]
        subs = "".join("(%s)" % s for s in key[2:])
        return base + subs
    if key[0] == "publaw" and len(key) >= 3:
        return "Pub. L. No. %s-%s" % (key[1], key[2])
    if key[0] == "fr" and len(key) >= 3:
        return "%s FR %s" % (key[1], key[2])
    return " ".join(str(x) for x in key)


def parse_addresses(text):
    """Every citation in `text` as `[(key, label, position)]`. Duplicates are kept because a
    caller often wants the position (a mine printed next to the paragraph that raised it), but
    the analysis dedupes on the key.

    🔴 The USC-to-INA fold happens HERE, not in the caller. A draft that cites `8 U.S.C. §
    1255(k)` yields the USC key AND the INA key, so a bank entry addressed as «section 245(k)
    of the Act» will match without the caller reasoning about aliases.
    """
    out = []
    if not text:
        return out
    for m in _CFR_RX.finditer(text):
        for k in _cfr_keys(m.group(1), m.group(2), m.group(3) or "", m.group(4) or ""):
            out.append((k, _label(k), m.start()))
    for m in _USC_RX.finditer(text):
        for k in _usc_keys(m.group(1), m.group(2), m.group(3) or ""):
            out.append((k, _label(k), m.start()))
    for m in _INA_EXPLICIT_RX.finditer(text):
        for k in _ina_keys(m.group(1), m.group(2) or ""):
            out.append((k, _label(k), m.start()))
    for m in _ACT_SECTION_RX.finditer(text):
        for k in _ina_keys(m.group(1), m.group(2) or ""):
            out.append((k, _label(k), m.start()))
    for m in _PL_RX.finditer(text):
        k = ("publaw", m.group(1).lower(), m.group(2).lower())
        out.append((k, _label(k), m.start()))
    for m in _FR_RX.finditer(text):
        k = ("fr", m.group(1).lower(), m.group(2).lower())
        out.append((k, _label(k), m.start()))
    return out


# ---------------------------------------------------------------------------------- bank parser
_ENTRY_HEAD_RX = re.compile(r"(?m)^###\s+(\S+)\s*(?:\S+\s*)?(.*)$")
_H2_RX = re.compile(r"(?m)^##\s+(.+?)\s*$")
_BLOCKQUOTE_RX = re.compile(r"(?m)^>\s?(.*)$")
_TABLE_ROW_RX = re.compile(r"(?m)^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$")


def _side_from_heading(heading):
    """Map a `## For us` / `## Against us` heading to `pro`/`con`. Returns None for anything
    else - which is what makes the parser tolerant of hand-rolled banks with extra sections
    like `## Rules` or `## Notes`."""
    h = (heading or "").strip().lower()
    if h == "for us":
        return "pro"
    if h == "against us":
        return "con"
    return None


def parse_bank_entries(bank_text):
    """Every `### §…` block in the bank, one dict per entry.

    Fields:
      side       'pro' | 'con' | None (None = outside a For-us/Against-us section)
      id         '§P-1' (the token after ###)
      claim      the rest of the ### line
      quote      the blockquote body, whitespace-joined
      address    the value of `| **Address** | ... |` (as written)
      addr_keys  set of fine keys parsed from the address, plus their INA/USC twins
      not_proved text of `| **What this does NOT prove** | ... |`
      used_in    text of `| **Used in** | ... |` (empty if absent or a `TO DO`)
      free_text  the entry's non-table, non-quote prose (heuristic for "applied?")

    A missing field arrives as an empty string, never as None - so a caller can safely check
    `.strip()` without a truthy dance.
    """
    if not bank_text:
        return []
    # Split into (section_heading, section_body) chunks. `re.split` keeps the delimiter groups
    # when the pattern captures, so a walk of the parts recovers who each entry sits under.
    parts = re.split(r"(?m)^(##\s+.+?)\s*$", bank_text)
    # parts is [preamble, h2_1, body_1, h2_2, body_2, ...] - the preamble is the file header.
    sections = []
    if parts:
        sections.append((None, parts[0]))
        for i in range(1, len(parts) - 1, 2):
            heading = re.sub(r"^##\s+", "", parts[i]).strip()
            body = parts[i + 1] if i + 1 < len(parts) else ""
            sections.append((heading, body))

    out = []
    for heading, body in sections:
        side = _side_from_heading(heading)
        # Split the body into entries at `### ` boundaries. A body that has no entries yields
        # nothing here, which is correct.
        entries = re.split(r"(?m)^###\s+", body)
        for chunk in entries[1:]:                     # entries[0] is the pre-first-entry prose
            first_nl = chunk.find("\n")
            if first_nl < 0:
                head_line, rest = chunk, ""
            else:
                head_line, rest = chunk[:first_nl], chunk[first_nl + 1:]
            head_parts = head_line.split(None, 1)
            entry_id = head_parts[0].strip()
            claim = head_parts[1].strip() if len(head_parts) > 1 else ""

            quote_lines = [m.group(1) for m in _BLOCKQUOTE_RX.finditer(rest)]
            quote = " ".join(quote_lines).strip()

            fields = {}
            for m in _TABLE_ROW_RX.finditer(rest):
                key = m.group(1).strip().lower()
                fields[key] = m.group(2).strip()

            address = fields.get("address", "")
            not_proved = fields.get("what this does not prove", "")
            used_in = fields.get("used in", "")
            # Strip the "TO DO" placeholder value from either optional field - a placeholder
            # is not content. `render_entry` in bank.py emits the string that starts with
            # "TO DO" for a field left blank at creation.
            if "TO DO" in used_in.upper():
                used_in = ""
            if "TO DO" in not_proved.upper():
                not_proved = ""

            addr_keys = set()
            for k, _lbl, _pos in parse_addresses(address):
                addr_keys.add(k)

            # Free text: the entry body with quote lines and table rows removed. Used as a
            # loose "was this entry applied to the matter" signal in question D.
            body_lines = []
            for line in rest.splitlines():
                if line.startswith(">"):
                    continue
                if line.startswith("|"):
                    continue
                body_lines.append(line)
            free_text = " ".join(ln.strip() for ln in body_lines if ln.strip())

            out.append({"side": side, "id": entry_id, "claim": claim,
                        "quote": quote, "address": address, "addr_keys": addr_keys,
                        "not_proved": not_proved, "used_in": used_in,
                        "free_text": free_text})
    return out


# ---------------------------------------------------------------------------------- analysis
MINE = "MINE"
UNAPPLIED = "UNAPPLIED"
PARAPHRASE = "PARAPHRASE"
UNPARSED = "UNPARSED"
AMBIGUOUS = "AMBIGUOUS"


def _draft_addr_set(drafts):
    """Union of every fine key extracted from every draft. Duplicates removed; positions
    dropped because the follow-up matching is set-membership."""
    keys = set()
    for _name, text in drafts:
        for k, _lbl, _pos in parse_addresses(text):
            keys.add(k)
    return keys


def _entry_addr_related_any(entry, key_set):
    """True if any of the entry's addresses is `related()` to any key in `key_set`."""
    for ek in entry["addr_keys"]:
        for dk in key_set:
            if related(ek, dk):
                return True
    return False


def _quote_present_in_drafts(quote, drafts):
    """Normalised containment across the concatenated drafts.

    The same normalisation the bank uses for its own containment check (`bank.in_bank`), so
    "the quote is in the draft" here means the same thing there. A short quote is still
    checked: this fold is about paraphrase, not fabrication, so a coincidental match on 30
    characters of English is a false alarm not a false clean.
    """
    if not quote:
        return False
    n = normalise(strip_markdown(quote)).lower()
    if len(n) < 40:
        return False
    for _name, text in drafts:
        if n in normalise(strip_markdown(text)).lower():
            return True
    return False


def analyse(drafts, bank_entries):
    """The four findings, ready to render.

    `drafts` is `[(name, text)]`. `bank_entries` is what `parse_bank_entries` returns.
    """
    draft_keys = _draft_addr_set(drafts)

    mines = []
    for e in bank_entries:
        if e["side"] != "con":
            continue
        if not e["addr_keys"]:
            continue
        if _entry_addr_related_any(e, draft_keys):
            # Which draft key(s) triggered it - printing them helps the reader locate the
            # paragraph in the draft rather than hunting for the address.
            triggers = sorted({_label(dk) for ek in e["addr_keys"] for dk in draft_keys
                               if related(ek, dk)})
            mines.append({"id": e["id"], "address": e["address"], "claim": e["claim"],
                          "triggers": triggers})

    unapplied = []
    for e in bank_entries:
        if e["side"] != "pro":
            continue
        if not e["addr_keys"]:
            continue
        if not _entry_addr_related_any(e, draft_keys):
            unapplied.append({"id": e["id"], "address": e["address"], "claim": e["claim"]})

    paraphrases = []
    for e in bank_entries:
        if e["side"] != "pro":
            continue
        if not e["addr_keys"]:
            continue
        # Only entries WHOSE ADDRESS is cited in the draft (an unapplied entry cannot be
        # paraphrased - it is not there at all) and WHOSE QUOTE is NOT verbatim in the draft.
        if not _entry_addr_related_any(e, draft_keys):
            continue
        if _quote_present_in_drafts(e["quote"], drafts):
            continue
        paraphrases.append({"id": e["id"], "address": e["address"], "claim": e["claim"],
                            "quote_preview": (e["quote"] or "")[:120]})

    unparsed = []
    ambiguous = []
    for e in bank_entries:
        # Question D presence checks. An entry banked through the gatekeeper cannot be
        # missing not_proves - the gatekeeper refuses that write - but a hand-written entry
        # can be, and this is where the count becomes visible.
        missing = []
        if not e["not_proved"]:
            missing.append("what this does NOT prove")
        if not e["used_in"] and not e["free_text"]:
            missing.append("used in / application to the matter")
        if missing:
            unparsed.append({"id": e["id"], "address": e["address"], "claim": e["claim"],
                             "missing": missing})
        if not e["addr_keys"] and e["address"]:
            # Addressed but the parser could not turn it into a fine key - report so a human
            # decides. Guidance addresses (Policy Manual chapters) legitimately fall here.
            ambiguous.append({"id": e["id"], "address": e["address"], "claim": e["claim"]})

    return {"mines": mines, "unapplied": unapplied, "paraphrases": paraphrases,
            "unparsed": unparsed, "ambiguous": ambiguous,
            "draft_key_count": len(draft_keys),
            "bank_entry_count": len(bank_entries)}


# ---------------------------------------------------------------------------------- render
def render_report(report, out=None):
    """Print a coverage report. `out` is any file-like with a `.write`; default: return the
    text (used by the CLI to also print it, and by the JSON path to skip rendering)."""
    buf = io.StringIO()

    def w(line=""):
        buf.write(line + "\n")

    w("coverage: %d bank entr%s, %d distinct citation(s) in draft(s)"
      % (report["bank_entry_count"], "y" if report["bank_entry_count"] == 1 else "ies",
         report["draft_key_count"]))

    w("")
    w("[A] MINES - the draft cites a rule the bank marks AGAINST us (%d)"
      % len(report["mines"]))
    for m in report["mines"]:
        w("      %s  %s" % (m["id"], m["address"]))
        if m["claim"]:
            w("           claim: %s" % m["claim"][:100])
        if m["triggers"]:
            w("           cited in draft as: %s" % "; ".join(m["triggers"][:4]))
    if report["mines"]:
        w("      🔴 A mine is the drafter arguing on ground the other side owns. Open the "
          "entry; either")
        w("         answer the con OR remove the argument. A string check cannot see this.")

    w("")
    w("[B] UNAPPLIED - bank entries FOR us the draft never cites (%d)"
      % len(report["unapplied"]))
    for u in report["unapplied"][:40]:
        w("      %s  %s" % (u["id"], u["address"]))
        if u["claim"]:
            w("           claim: %s" % u["claim"][:100])
    if len(report["unapplied"]) > 40:
        w("      ... and %d more" % (len(report["unapplied"]) - 40))
    if report["unapplied"]:
        w("      🟡 Sometimes correct - a shelf takes more books than any one argument uses. "
          "But")
        w("         if a rule matters and is not cited, this is where you notice.")

    w("")
    w("[C] PARAPHRASE ONLY - address cited but the bank's verbatim quotation is not in the "
      "draft (%d)" % len(report["paraphrases"]))
    for p in report["paraphrases"]:
        w("      %s  %s" % (p["id"], p["address"]))
        if p["claim"]:
            w("           claim: %s" % p["claim"][:100])
        w("           bank has: «%s%s»" % (p["quote_preview"],
                                            "..." if len(p["quote_preview"]) >= 120 else ""))
    if report["paraphrases"]:
        w("      🔴 A summary is not a quotation, and an adjudicator following the pincite "
          "finds")
        w("         words that do not match the source - the fabrication-shape this toolkit "
          "exists to catch.")

    w("")
    w("[D] BANK ENTRIES MISSING PIECES (%d)" % len(report["unparsed"]))
    for u in report["unparsed"]:
        w("      %s  %s" % (u["id"], u["address"]))
        w("           missing: %s" % "; ".join(u["missing"]))
    if report["unparsed"]:
        w("      🔴 A row without an applicability boundary is more dangerous than no row: "
          "it will")
        w("         be cited wider than it permits. Fill in the fields; the gatekeeper "
          "refuses to write")
        w("         one without them.")

    if report["ambiguous"]:
        w("")
        w("(bank entries with an address the coverage parser did not recognise - %d)"
          % len(report["ambiguous"]))
        for a in report["ambiguous"]:
            w("      %s  %s" % (a["id"], a["address"]))
        w("      Common for USCIS Policy Manual chapters and case reporter cites - they")
        w("      cannot be checked for mines or paraphrase but the entries themselves are OK.")

    text = buf.getvalue()
    if out is not None:
        out.write(text)
    return text


# ---------------------------------------------------------------------------------- G-D inventory
def corpus_bank_inventory(corpus, bank_entries, packs):
    """The corpus-to-bank cross reference: what is downloaded and never analysed, what is
    banked and never downloaded.

    Both directions matter. Files with no bank entry get downloaded again next round and their
    absence turns an honest quotation into a NOT_FOUND (this tool's fabrication signal); bank
    entries whose file is missing produce the same signal on the read side, and both are the
    silent-hole shape.

    🔴 The MATCHING uses `packs.file_matches`, not this module's fine-key extractor. The
    reason is a filename form the fine parser was never going to see: `8CFR-part-214.xml`,
    `8usc-1255.xml`, `PM-602-0199-…md`. Those are the shapes the citation packs already handle
    (they were tuned for exactly this) - and the inventory question is coarser than the mine
    question by construction: "is there ANY file that could hold this address" does not care
    about `(f)(8)(i)` any more than a shelf label cares which sentence you are looking for.
    Coverage's own fine-key extractor is untouched; it is still what [A]/[B]/[C] use.
    """
    from .address import KeyMap

    bank_coarse_keys = set()
    entry_coarse_keys = []          # per-entry so we can reverse-map for the missing report
    for e in bank_entries:
        ks = packs.keys([e["address"]]) if e["address"] else set()
        entry_coarse_keys.append(ks)
        bank_coarse_keys.update(ks)

    km = KeyMap(corpus, packs)

    # Bank entries whose coarse key resolves to no file the corpus indexed. An entry with an
    # unparseable address (no packs key) is NOT counted as missing - that is the AMBIGUOUS
    # bucket, reported by `analyse`. This function reports only what is provably absent.
    missing_for_bank = []
    for e, ks in zip(bank_entries, entry_coarse_keys):
        if not ks:
            continue
        if any(km.resolve(k) for k in ks):
            continue
        missing_for_bank.append({"id": e["id"], "address": e["address"]})

    # Files that match at least one bank coarse key. The packs' own filename form covers the
    # dash/underscore/dot variants (`8cfr_214.xml`, `8CFR-part-214.xml`, `8 CFR 214.xml`), so
    # a file whose basename encodes an address the bank cites is picked up here.
    matched_sources = 0
    unparsed_sources = []
    for p in corpus.paths:
        matched = False
        for k in bank_coarse_keys:
            try:
                if packs.file_matches(k, p, ""):
                    matched = True
                    break
            except Exception:                                        # noqa: BLE001
                # A broken pack rule is loud in the address layer already; here it is one
                # file, and the whole inventory must not fail on one file.
                continue
        if matched:
            matched_sources += 1
        else:
            unparsed_sources.append(p)

    return {"unparsed_sources": unparsed_sources,
            "matched_sources": matched_sources,
            "files_with_no_recognised_key": [],       # left present for old callers
            "missing_for_bank": missing_for_bank,
            "bank_key_count": len(bank_coarse_keys),
            "corpus_file_count": len(corpus.paths)}


# ---------------------------------------------------------------------------------- controls
def controls_pass(printer=print):
    """Positive-plus-negative controls the extractor MUST clear before any report is trusted.

    Rationale, one line: a zero from a broken shape is a statement about the shape, not the
    world. Every G-D report from the sister project's `law_gap.py` runs these two probes
    first, and a failure aborts with exit 2 rather than a clean-looking empty output.
    """
    passed = True

    # Positive: a known CFR citation must parse into a fine key with the right subitems.
    got = parse_addresses("see 8 CFR 214.2(f)(8)(i)(D) for the rule")
    cfr_hits = [k for k, _l, _p in got if k[0] == "cfr"]
    want = ("cfr", "8", "214", "2", "f", "8", "i", "d")
    if not any(k == want for k in cfr_hits):
        printer("coverage control POS: 8 CFR 214.2(f)(8)(i)(D) did not parse as %r "
                "(got %r)" % (want, cfr_hits[:3]))
        passed = False

    # Positive: USC folds to INA when title 8.
    got = parse_addresses("under 8 U.S.C. § 1255(k) the count")
    want_ina = ("ina", "245", "k")
    if not any(k == want_ina for k, _l, _p in got):
        printer("coverage control POS: 8 U.S.C. § 1255(k) did not fold to %r"
                % (want_ina,))
        passed = False

    # Positive: "section 245(k) of the Act" folds back.
    got = parse_addresses("under section 245(k) of the Act, the count")
    if not any(k == want_ina for k, _l, _p in got):
        printer("coverage control POS: section 245(k) of the Act did not fold to %r"
                % (want_ina,))
        passed = False

    # Negative: a tab-label parent must NOT match a specific child via `related`.
    parent = ("cfr", "8", "214", "2", "f")
    child = ("cfr", "8", "214", "2", "f", "8", "i")
    if related(parent, child):
        printer("coverage control NEG: 214.2(f) matched 214.2(f)(8)(i) as related - the "
                "AOS-measured mine-inflation bug is back")
        passed = False

    # Positive: exact match always fires.
    if not related(child, child):
        printer("coverage control POS: exact-match check failed - `related(x,x)` is False")
        passed = False

    # Positive: a narrow parent DOES match its child.
    narrow_parent = ("cfr", "8", "214", "2", "f", "8")
    if not related(narrow_parent, child):
        printer("coverage control POS: `related(214.2(f)(8), 214.2(f)(8)(i))` is False - "
                "the narrow-parent path is broken")
        passed = False

    # Negative: different kinds must not accidentally match (the USC/INA fold is the ONLY
    # cross-kind allowance and it happens at extraction time, not in `related`).
    if related(("cfr", "8", "214", "2"), ("usc", "8", "214", "2")):
        printer("coverage control NEG: CFR and USC folded across kinds - the extractor's "
                "job leaked into `related`")
        passed = False

    return passed
