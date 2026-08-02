# -*- coding: utf-8 -*-
"""Citation packs: how this toolkit recognises "the address of a rule".

WHY ADDRESSES ARE A SEPARATE PROBLEM FROM TEXT
----------------------------------------------
A string search answers *"do these words exist somewhere in the law?"*. It cannot answer *"do
these words exist in the provision we said they came from?"* - and those are different questions
with different failure modes.

Measured in the project this was extracted from: a quotation of a signature statute was compared
against a completely unrelated regulation and came back flagged for a changed operative word. The
quotation was perfect. The file holding the real provision was sitting on the same disk. The tool
had simply found *a* match, somewhere, and reported on the wrong document.

Worse in the other direction, and this one reaches a filing: the right words under the wrong
address. A published checklist attributed a Board decision to a footnote belonging to a different
decision entirely. Every character of the quotation was correct, so a substring test says
VERIFIED - and an opposing reader who follows the pincite finds nothing there.

So the address is checked separately, and it needs to know what an address *looks like* in the body
of law you work in. That is what a pack is.

DELIBERATELY LAZY MATCHING
--------------------------
Address matching is soft by construction. A policy manual chapter that reprints a regulation
contains that regulation's number, so it passes as an acceptable home for a quotation of it - same
words, same agency. What gets caught is the opposite and only the provable case: a file in which
the cited provision is **not mentioned at all**. An accusation is made only where it can be
demonstrated.

ADDING YOUR OWN BODY OF LAW
---------------------------
A pack is a JSON file in ``packs/``. Nothing here is immigration-specific except the pack named
``us-immigration``. Copy ``us-federal.json``, add your citation shapes, point ``casefile.json`` at
it. There is no Python to write - field reference in ``FEATURES.md``, section "Citation packs".
"""
from __future__ import annotations

import json
import os
import re

PACKS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "packs")

__all__ = ["Pack", "PackSet", "load_packs", "available_packs"]


def available_packs():
    d = os.path.abspath(PACKS_DIR)
    if not os.path.isdir(d):
        return []
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))


def _fmt(pattern, groups):
    """`"{g1}cfr"` + ("8", "214") -> `"8cfr"`. Deliberately not str.format: real regexes are full
    of braces (`\\d{1,3}`) and str.format would choke on every one of them."""
    out = pattern
    for i, g in enumerate(groups, 1):
        out = out.replace("{g%d}" % i, str(g))
    return out


class Pack(object):
    """One body of law: what a citation to it looks like, and how to tell which file holds it."""

    def __init__(self, data):
        self.id = data["id"]
        self.name = data.get("name", data["id"])
        self.shapes = data.get("shapes", [])
        self.aliases = data.get("aliases", {})
        # A citation shape that promises a PRIMARY SOURCE - used to split a miss into "the source
        # must be on this disk" and "this was never going to be on this disk". See verify.py.
        self.primary_hint = data.get("primary_hint", "")
        self._rx = []
        for sh in self.shapes:
            self._rx.append((sh, re.compile(sh["regex"], 0 if sh.get("case_sensitive") else re.I)))
        self._by_kind = {}
        for sh in self.shapes:
            a = sh.get("address")
            if a:
                self._by_kind.setdefault(a["kind"], a)

    # -- finding citations in prose ------------------------------------------------------------
    def find(self, text):
        """Every citation string in `text`, whitespace-collapsed, order preserved, deduplicated."""
        out, seen = [], set()
        for s, _pos in self.find_positions(text):
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def find_positions(self, text):
        """`(citation_string, start_offset)` for each hit. The offset is what lets a caller tell
        an address standing NEXT TO a quotation from a cross-reference standing INSIDE it."""
        out = []
        for _sh, rx in self._rx:
            for m in rx.finditer(text or ""):
                out.append((" ".join(m.group(0).split()), m.start()))
        return sorted(out, key=lambda t: t[1])

    # -- turning a citation string into a comparable key ---------------------------------------
    def keys(self, cite_strings):
        """`"8 CFR 214.2(f)(6)"` -> `("cfr", "8", "214")`. Structure, not spelling.

        The alias table is why this is not a pure regex exercise. Two citation systems routinely
        name the same provision - an act section number and a code section number - and without the
        mapping they are simply different addresses, so a correct pincite reads as a mismatch. In
        the original project exactly one reviewer out of four contributed that table; nobody else
        noticed it was missing.
        """
        keys = set()
        for s in cite_strings or []:
            for sh, rx in self._rx:
                addr = sh.get("address")
                if not addr:
                    continue
                for m in rx.finditer(s):
                    try:
                        parts = [m.group(g) for g in addr["groups"]]
                    except (IndexError, error_group):
                        continue
                    if any(p is None for p in parts):
                        continue
                    parts = [str(p).strip().lower() for p in parts]
                    keys.add(self._alias(addr["kind"], parts))
        return keys

    def _alias(self, kind, parts):
        al = self.aliases.get(kind)
        if not al:
            return tuple([kind] + parts)
        idx = int(al.get("on", 0))
        table = al.get("map")
        value = parts[idx]
        if table is not None:
            mapped = table.get(value)
            if mapped is None:
                return tuple([kind] + parts)     # known system, unknown member: keep it literal
            value = mapped
        rest = parts[:idx] + parts[idx + 1:]
        return tuple([al["to_kind"]] + list(al.get("to_prefix", [])) + [value] + rest)

    def label(self, key):
        a = self._by_kind.get(key[0])
        if a and a.get("label"):
            try:
                return a["label"] % tuple(key[1:])
            except TypeError:
                pass
        return " ".join(str(x) for x in key)

    # -- deciding whether a corpus file is a plausible home for that address --------------------
    def file_matches(self, key, filename, body):
        """Soft test: could the provision at `key` live in this file?

        `filename` is compared in a *flattened* form - lowercase, with `-`, `_` and spaces
        removed - because real downloads are named `8CFR-part-214-ecfr-2026-07-29.xml`,
        `8cfr_214.xml` and `8 CFR 214.xml` interchangeably, and a naming convention is not a fact
        about the law.
        """
        a = self._by_kind.get(key[0])
        if not a:
            return False
        groups = list(key[1:])
        flat = re.sub(r"[-_ ]", "", os.path.basename(filename).lower())
        head = (body or "")[:8000].lower()
        for rule in a.get("file_match", []):
            if _rule_holds(rule, flat, body or "", head, groups):
                return True
        return False


error_group = KeyError


def _rule_holds(rule, flat, body, head, groups):
    hay = {"filename_flat": flat, "body": body, "body_head": head}.get(
        rule.get("where", "filename_flat"), flat)

    # A negative guard runs first: if the file's own header names a DIFFERENT subdivision, reject
    # outright. Measured on agency policy manuals, where volume 7 *part A* chapter 8 and volume 7
    # *part B* chapter 8 are different chapters that share a number - and one of them was the whole
    # argument. Three independent reviewers named this on the same day.
    for neg in rule.get("reject_if_head_names", []):
        rx = re.compile(_fmt(neg["scan"], groups), re.I)
        found = set(m.group(1).lower() for m in rx.finditer(head))
        if found and _fmt(neg["expect"], groups).lower() not in found:
            return False

    low = hay.lower()
    for needle in rule.get("all", []):
        if _fmt(needle, groups).lower() not in low:
            return False
    anyv = rule.get("any", [])
    if anyv and not any(_fmt(n, groups).lower() in low for n in anyv):
        return False
    for probe in rule.get("regex_all", []):
        try:
            rx = re.compile(_fmt(probe["pattern"], groups), re.I)
        except re.error:
            return False
        if len(rx.findall(hay)) < int(probe.get("min_count", 1)):
            return False
    return True


class PackSet(object):
    """Several packs behaving as one."""

    def __init__(self, packs):
        self.packs = list(packs)

    @property
    def ids(self):
        return [p.id for p in self.packs]

    def find(self, text):
        out, seen = [], set()
        for p in self.packs:
            for c in p.find(text):
                if c not in seen:
                    seen.add(c)
                    out.append(c)
        return out

    def find_positions(self, text):
        out = []
        for p in self.packs:
            out.extend(p.find_positions(text))
        return sorted(out, key=lambda t: t[1])

    def keys(self, cites):
        ks = set()
        for p in self.packs:
            ks |= p.keys(cites)
        return ks

    def label(self, key):
        for p in self.packs:
            if key[0] in p._by_kind:
                return p.label(key)
        return " ".join(str(x) for x in key)

    def file_matches(self, key, filename, body):
        return any(p.file_matches(key, filename, body) for p in self.packs)

    def is_primary(self, cite):
        """Does this citation promise a document that OUGHT to be in a corpus of primary sources?

        The distinction pays for itself in the report. A missing quotation whose neighbour is a
        statute citation means *the statute is not downloaded, or the quotation is wrong*. A missing
        quotation with no legal citation anywhere near it is a reference letter, a news article, an
        exhibit - it was never going to be in a corpus of statutes. Filing both under one heading is
        how a real fabrication hides in a pile of shrugs. Measured on a real corpus: of 1 606
        misses, 625 were tool output, 479 legal, 502 evidentiary. One number, three meanings.
        """
        for p in self.packs:
            if p.primary_hint and re.search(p.primary_hint, cite, re.I):
                return True
        return False


def load_packs(names):
    d = os.path.abspath(PACKS_DIR)
    out = []
    for n in names or []:
        path = n if (os.path.isabs(n) or n.endswith(".json")) else os.path.join(d, n + ".json")
        if not os.path.exists(path):
            raise SystemExit(
                "citation pack not found: %s\navailable: %s\n"
                "A pack is a JSON file; see FEATURES.md, section 'Citation packs'."
                % (n, ", ".join(available_packs()) or "(none)"))
        with open(path, encoding="utf-8") as fh:
            out.append(Pack(json.load(fh)))
    return PackSet(out)
