# -*- coding: utf-8 -*-
"""Behavioural self-test. Contacts nothing, costs nothing, needs no configuration.

WHY IT BUILDS ITS OWN CORPUS
-----------------------------
Because a test that needs your files is a test nobody runs, and because the interesting assertions
are about *specific text*. A synthetic corpus with known contents is the only way to say "this
quotation must produce exactly this verdict" and mean it.

WHY IT MUST NOT TOUCH THE NETWORK
----------------------------------
The suite promises it contacts no vendor. That promise is what lets it run in CI with no
credentials, and what makes it safe to run against a matter under privilege. Live probing lives in
`krokai doctor`, which says out loud what it touched.

🔴 EXPECTATIONS ARE DERIVED, NOT COPIED
----------------------------------------
Where a test asserts something about a list that ships as data - the citation packs, the detector
tables - it computes the expectation from the data rather than restating it. Measured elsewhere:
adding a fourth item to such a list turned four correct tests red, because the tests had the list
hardcoded. A test that duplicates configuration is a second home for it.
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = []
FAIL = []


def ok(name, cond, note=""):
    (PASS if cond else FAIL).append((name, note))
    return bool(cond)


# ------------------------------------------------------------------------------------------------
# A tiny, realistic corpus. The sentences imitate the shapes that actually break things: a proviso
# after a comma, a negation in front of a clause, a preamble reciting a commenter, a line-break
# hyphen, and the same sentence appearing in two documents.
# ------------------------------------------------------------------------------------------------
REG = """
PART 214 - NONIMMIGRANTS

Sec. 214.2 Special requirements for admission.

(f)(6)(i)(D) Study in any other language, liberal arts, fine arts, or other nonvocational training
program, certified by a designated school official to consist of at least eighteen clock hours of
attendance a week if the dominant part of the course of study consists of classroom instruction.

(f)(16) Reinstatement to student status. The district director may consider reinstating a student
who makes a request for reinstatement, but do not include instances where a pattern of repeated
violations has occurred.

An applicant shall not be admitted to the United States unless he establishes to the satisfaction of
the officer that he is not inadmissible under section 212.

The Service does not agree with the commenters that this rule imposes an undue burden, and has
therefore retained the requirement without change.

Applicants engaged in pre- and post-production activity remain eligible under this paragraph.
"""

# The same operative sentence, reprinted in a second document. This is what makes "the first
# occurrence in the corpus" the wrong occurrence, and it is not a contrived case: agencies reprint
# regulations inside their own manuals constantly.
MANUAL = """
Volume 7, Part B, Chapter 8 - Bars to Adjustment

An applicant shall not be admitted to the United States unless he establishes to the satisfaction of
the officer that he is not inadmissible under section 212.

The following situations do not count toward the 180-day limit: any period of unlawful status that
was the result of a technical violation.

The officer must evaluate the record as a whole. Officers should note that the absence of adverse
factors is not by itself sufficient.
"""

PREAMBLE = """
Federal Register Volume 91, Number 12

[[Page 45324]]

Comment: Commenters stated that eliminating any distance education for language programs is too
restrictive and would harm students.

Response: The Department disagrees. The final rule retains the limitation as proposed.

The statutory exemptions created by Congress for certain applicants for adjustment of status
continue to exist and are unaffected by this rule.

An officer may not deny an application on- line without first issuing a notice of intent to deny.
"""


def build_corpus(tmp):
    law = os.path.join(tmp, "law")
    os.makedirs(law, exist_ok=True)
    io.open(os.path.join(law, "8CFR-part-214.txt"), "w", encoding="utf-8").write(REG)
    io.open(os.path.join(law, "7-USCIS-PM-B-chapter-8.md"), "w", encoding="utf-8").write(MANUAL)
    io.open(os.path.join(law, "91FR45324-preamble.txt"), "w", encoding="utf-8").write(PREAMBLE)
    # A file that is OUR OWN analysis sitting in the sources folder. It must be excluded, or a
    # quotation copied out of it would verify against it.
    io.open(os.path.join(law, "OUR-ANALYSIS-of-part-214.md"), "w", encoding="utf-8").write(
        "We think the rule says something entirely invented for this test, verbatim and unique.")
    # A stub: present, tiny, useless. Must be reported, not silently indexed.
    io.open(os.path.join(law, "chapter-11-stub.md"), "w", encoding="utf-8").write("# placeholder\n")
    from krokai.corpus import Corpus
    return Corpus([law], quiet=True), law


# ------------------------------------------------------------------------------------------------
def suite_normalise():
    from krokai.normalize import normalise, dehyph, alnum, latin_share, strip_markdown

    ok("normalise: line wrap collapses",
       normalise("on March\n9, 2020") == "on March 9, 2020")
    ok("normalise: line-break hyphen heals",
       normalise("on-\nline course") == "on-line course")
    ok("normalise: hyphen+space on ONE line is left alone (pre- and post-production)",
       "pre- and post-production" in normalise("Applicants in pre- and post-production remain"),
       "the blanket rule welded this into pre-and")
    ok("normalise: smart quotes fold", normalise("“word”") == '"word"')
    ok("normalise: letters are never touched",
       normalise("shall not") == "shall not")
    ok("dehyph heals hyphen+space (PDF justification)",
       dehyph("pre- sented") == "presented")
    ok("alnum drops punctuation only", alnum("A, b. 12!") == "ab12")
    ok("latin_share is a SHARE not a run",
       latin_share("the quick brown fox") == 1.0 and latin_share("это текст") == 0.0,
       "the 40-consecutive-letters test never matched English")
    ok("strip_markdown removes bold inside a quotation",
       strip_markdown("the **full** course") == "the full course")
    ok("strip_markdown removes an asymmetric closing guillemet",
       strip_markdown("some text»") == "some text")
    ok("strip_markdown removes a provenance tag",
       "[OPENED]" not in strip_markdown("the rule says X [OPENED]"))
    ok("strip_markdown removes [sic] so either convention verifies",
       "[sic]" not in strip_markdown("the dates o[f] receipt [sic]"))


def suite_extract():
    from krokai.extract import extract_quotes, blocks

    doc = ('Intro paragraph.\n\n'
           '> «Family ties to the United States\n'
           '> and the closeness of the underlying relationships»\n\n'
           'She wrote "a quoted span that is definitely long enough to count as a quotation".\n')
    qs = extract_quotes(doc)
    ok("extract: a wrapped blockquote is ONE quotation, not two broken halves",
       any("Family ties to the United States and the closeness" in q for q in qs),
       "line-based extraction reported four of these as ALTERED on a real corpus")
    ok("extract: a plain quoted span is found",
       any(q.startswith("a quoted span") for q in qs))

    two = '> «First quoted passage here, long enough» · «Second quoted passage, also long enough»\n'
    qs2 = extract_quotes(two, min_len=20)
    ok("extract: two quotations on one blockquote line are split",
       len([q for q in qs2 if "quoted passage" in q]) >= 2)

    kinds = [k for k, _t in blocks("| a | b |\n| c | d |\n")]
    ok("extract: table rows are NOT joined (would invent a cross-cell match)",
       kinds.count("t") == 2)

    callout = ("> ## Rules for this file\n"
               "> 1. A quotation enters only verbatim and only after someone opened the source.\n"
               "> 2. Every row needs an address and a location on disk.\n")
    ok("extract: a blockquote CALLOUT is not treated as a quotation of law",
       not extract_quotes(callout),
       "the toolkit's own template produced this false alarm on the first real run")
    inside = ('> ## Warning\n'
              '> The rule says "an applicant shall not be admitted unless he establishes '
              'eligibility to the satisfaction of the officer".\n')
    ok("extract: but a real quotation INSIDE a callout is still found",
       any("shall not be admitted" in q for q in extract_quotes(inside)),
       str(extract_quotes(inside)))


def suite_corpus(corpus, law):
    ok("corpus: our own analysis inside a sources folder is EXCLUDED",
       any("OUR-ANALYSIS" in p for p in corpus.excluded_derived),
       "a quotation copied out of it would otherwise verify against it")
    ok("corpus: a stub is reported, not indexed",
       any("stub" in p for p in corpus.excluded_stub))
    ok("corpus: real sources are indexed", len(corpus.paths) == 3)
    ok("corpus: a match cannot straddle two documents",
       corpus.find("classroom instruction. Volume 7") is None)

    # 🔴 THE CONTEXT WINDOWS ARE CLAMPED TO THE FILE, AT BOTH ENDS - asserted here, at the level the
    # clamp lives, and not through a caller. `window()`'s own docstring records that an earlier
    # version clamped only the low end, so a window near the end of a document quoted the NEXT
    # document as its continuation. There was no test. Two negative controls removed the clamps and
    # the suite stayed green: every caller cuts the window at a sentence boundary, and that discards
    # the overrun before any assertion downstream can see it.
    #
    # This is the third measured instance in this project of a guard that is correct and uncovering,
    # and the shape repeats: the assertion was made where the damage is READ instead of where it is
    # PRODUCED.
    mid = corpus.paths[1]                      # the middle document, so both edges have a neighbour
    body = corpus.text_of(mid)
    k = corpus.paths.index(mid)
    start, end = corpus.starts[k], corpus.ends[k]
    for label, got in [
            ("before, asked for far more than the file holds", corpus.before(mid, start + 5, 4000)),
            ("after, asked past the end of the file",
             corpus.after(mid, end - len(body) + len(body) - 5, 5, 4000)),
            ("window, both ends past the file", corpus.window(mid, start + 5, 10, 4000, 4000))]:
        ok("corpus: %s stays inside it" % label,
           got in body and "\x00" not in got, repr(got[:60]) + " … " + repr(got[-60:]))
    ok("corpus: the clamp is actually reached, so the test above can fail",
       len(corpus.window(mid, start + 5, 10, 4000, 4000)) < 8010, "window was never truncated")


def suite_verify(corpus):
    from krokai.verify import check

    v, _w, _d = check("certified by a designated school official to consist of at least eighteen "
                      "clock hours of attendance a week", corpus)
    ok("verdict VERIFIED on an exact, complete quotation", v == "VERIFIED", v)

    v, _w, d = check("The district director may consider reinstating a student who makes a request "
                     "for reinstatement", corpus)
    ok("verdict TRUNCATED_CONDITION when the source continues with a limiter",
       v == "TRUNCATED_CONDITION", "%s :: %s" % (v, d))

    v, _w, _d = check("certified by a designated school official to consist of at least eighteen "
                      "clock hours of attendance a week if the dominant part of the course of "
                      "study consists of laboratory work", corpus)
    ok("verdict ALTERED when only the tail differs", v in ("ALTERED", "OPERATOR", "PARTIAL"), v)

    v, _w, d = check("certified by a designated school official to consist of at least eighteen "
                     "clock hours of attendance a week if the dominant part of the course of study "
                     "does not consist of classroom instruction", corpus)
    ok("verdict OPERATOR when a negation is inserted", v == "OPERATOR", "%s :: %s" % (v, d))

    v, _w, _d = check("A wholly invented sentence about immigration law that appears in no source "
                      "anywhere on this disk at all", corpus)
    ok("verdict NOT_FOUND on an invented sentence", v == "NOT_FOUND", v)

    v, _w, d = check("The statutory exemptions created by Congress ... continue to exist",
                     corpus)
    ok("verdict ELLIPSIS_HIDES when the elision removes a narrowing phrase",
       v == "ELLIPSIS_HIDES", "%s :: %s" % (v, d))

    v, _w, _d = check("Study in any other language, liberal arts, fine arts, or other nonvocational "
                      "training program ... at least eighteen clock hours", corpus)
    ok("verdict ASSEMBLED when an ellipsis hides nothing material",
       v in ("ASSEMBLED", "VERIFIED"), v)

    v, _w, d = check("The district director may consider reinstating a student ... The final rule "
                     "retains the limitation as proposed", corpus)
    ok("verdict SPLICED when fragments come from different documents",
       v in ("SPLICED", "ELLIPSIS_HIDES", "ALTERED"), "%s :: %s" % (v, d))

    v, _w, _d = check("An officer may not deny an application online without first issuing a "
                      "notice of intent to deny", corpus)
    ok("verdict TYPESETTING when the SOURCE is line-broken and our quotation is right",
       v in ("TYPESETTING", "VERIFIED"), v)

    v, _w, _d = check("certified by a designated school official to consist of at least eighteen "
                      "clock hours of attendance a week;", corpus)
    ok("verdict PUNCTUATION when only punctuation drifts",
       v in ("PUNCTUATION", "VERIFIED", "TRUNCATED_CONDITION"), v)

    v, _w, d = check("eliminating any distance education for language programs is too restrictive "
                     "and would harm students", corpus)
    ok("verdict WRONG_SPEAKER when the source is reciting a commenter",
       v == "WRONG_SPEAKER", "%s :: %s" % (v, d))

    # 🔴 NEIGHBOURS. Deliberately tested on a quotation that PASSES, because that is the whole
    # argument for the feature: a flagged quotation already sends the reader to the source, and a
    # verified one is the one nobody opens again. `truncated_condition` cannot help here - it is a
    # detector, it fires only mid-sentence and only on a listed limiter, and it is narrow on purpose.
    from krokai.verify import neighbours
    q = ("certified by a designated school official to consist of at least eighteen "
         "clock hours of attendance a week")
    nb = neighbours(q, corpus)
    ok("neighbours: a located quotation yields its surroundings", bool(nb), str(nb)[:120])
    ok("neighbours: at least one side is real text, not an empty cell",
       any(b or af for _p, b, af in nb), str(nb)[:200])
    ok("neighbours: an invented sentence has no neighbours rather than wrong ones",
       neighbours("A wholly invented sentence that appears in no source on this disk", corpus) == [])
    # The window must not run past the end of the file into the next document: that would present
    # one authority's sentence as the continuation of another's - the defect this whole module
    # exists to catch, produced by the tool itself.
    #
    # 🔴 THE OBVIOUS VERSION OF THIS TEST WAS UNCOVERING, and a negative control is what found it.
    # It asserted that no neighbour contains the `\x00` document separator. It cannot: the neighbour
    # is cut at a sentence boundary, and the last sentence before the separator has no `\x00` in it,
    # so the overrun stays invisible while the assertion reads as protection. Removing the clamp in
    # `corpus.after` left the suite fully green. The property that actually holds is stronger and
    # simpler - every neighbour must be text of the SAME FILE the quotation was found in.
    ok("neighbours: every neighbour is text of the file the quotation was found in",
       all((not b or b in corpus.text_of(p)) and (not af or af in corpus.text_of(p))
           for p, b, af in nb), str(nb)[:200])

    # 🔴 AND IT MUST BE ASKED AT A DOCUMENT BOUNDARY, or the clamp is never exercised. Two negative
    # controls removed the clamps in `corpus.before`/`after` and the suite stayed green, because the
    # only quotation being tested sat in the middle of a file where no window could reach an edge.
    # A test that cannot reach the condition it names is the same defect this project measured
    # before: correct, and uncovering. The last sentence of the middle document is the case - the
    # corpus holds three files, so it has a neighbour on the far side of the separator to steal.
    last = ("Applicants engaged in pre- and post-production activity remain eligible under this "
            "paragraph.")
    nbl = neighbours(last, corpus)
    ok("neighbours: a quotation at the END of a document has no 'after' at all",
       bool(nbl) and all(not af for _p, _b, af in nbl), str(nbl)[:200])
    ok("neighbours: ...and nothing from the next document leaks into it",
       all((not af or af in corpus.text_of(p)) and "\x00" not in af for p, _b, af in nbl),
       str(nbl)[:200])
    first = ("Study in any other language, liberal arts, fine arts, or other nonvocational "
             "training program")
    nbf = neighbours(first, corpus)
    ok("neighbours: at the HEAD of a document nothing from the previous one leaks in",
       all((not b or b in corpus.text_of(p)) and "\x00" not in b for p, b, _a in nbf),
       str(nbf)[:200])


def suite_word_diff():
    from krokai.verify import word_diff
    changed, hits, unaligned = word_diff(
        "the officer shall approve the application in every case",
        "the officer shall not approve the application in every case")
    ok("word_diff sees an inserted negation (85 % similarity would not)",
       "not" in hits and not unaligned, str(hits))

    changed, hits, _u = word_diff(
        "for the 2020-21 academic year the limit applies",
        "for the 2021-22 academic year the limit applies")
    ok("word_diff flags a changed number as never-typography",
       any(any(c.isdigit() for c in h) for h in hits), str(hits))

    changed, hits, _u = word_diff("the officer may approve the request today",
                                  "the officer may approve the request today")
    ok("word_diff is silent on identical text", not changed and not hits)


def suite_citations():
    from krokai.citations import load_packs, available_packs

    # Derived, not copied: adding a pack must not turn this red.
    names = available_packs()
    ok("packs: at least the base pack ships", "us-federal" in names, str(names))
    packs = load_packs(names)

    cites = packs.find("See 8 CFR 214.2(f)(6)(i)(D) and INA § 245(k), plus 91 FR 45324 and "
                       "Matter of Blas, 15 I&N Dec. 626, and 26 U.S.C. § 162.")
    ok("citations: CFR recognised", any("214" in c and "CFR" in c.upper() for c in cites), str(cites))
    ok("citations: Federal Register recognised", any("45324" in c for c in cites))
    ok("citations: a single-party case style is recognised",
       any("Matter of Blas" in c for c in cites))

    keys = packs.keys(["INA § 245(k)"])
    ok("citations: INA maps onto the U.S. Code (the alias table)",
       ("usc", "8", "1255") in keys, str(keys))
    keys = packs.keys(["I.R.C. § 162"])
    ok("citations: IRC maps onto title 26 with no explicit map entry",
       ("usc", "26", "162") in keys, str(keys))
    keys = packs.keys(["8 CFR 214.2(f)(6)"])
    ok("citations: CFR key is title+part, not the subsection",
       ("cfr", "8", "214") in keys, str(keys))

    ok("citations: a statute cite is primary", packs.is_primary("8 CFR 214.2"))
    ok("citations: an arbitrary phrase is not primary", not packs.is_primary("the annual report"))


def suite_address(corpus, law):
    from krokai.citations import load_packs
    from krokai.address import KeyMap, address_check

    packs = load_packs(["us-federal", "us-immigration"])
    km = KeyMap(corpus, packs)

    reg = [p for p in corpus.paths if "214" in os.path.basename(p)][0]
    man = [p for p in corpus.paths if "PM" in os.path.basename(p)][0]

    a = address_check(["8 CFR 214.2"], reg, km, packs)
    ok("address: MATCHED when the quotation is in the cited part", a["status"] == "MATCHED", str(a))

    a = address_check(["8 CFR 214.2"], man, km, packs)
    ok("address: MISMATCH when found in a different document",
       a["status"] in ("MISMATCH", "ADDRESS_NOT_IN_CORPUS"), str(a))

    a = address_check([], reg, km, packs)
    ok("address: NO_NEARBY_CITATION is its own outcome, not a pass",
       a["status"] == "NO_NEARBY_CITATION", str(a))

    # 🔴 The part letter must be load-bearing: volume 7 part A chapter 8 is not part B chapter 8.
    a = address_check(["7 USCIS-PM A.8"], man, km, packs)
    ok("address: the PM part letter is respected (A.8 is not B.8)",
       a["status"] != "MATCHED", str(a))


def suite_redact():
    from krokai.redact import self_test, gate, scan, SECRET_PATTERNS, PII_PATTERNS
    out = []
    ok("gate: all detectors have probes and no negative control fires",
       self_test(printer=out.append), " ".join(out))

    rc = gate([("brief", "key = sk-ant-api03-" + "A" * 40)], printer=lambda *_a: None)
    ok("gate: a secret blocks and has no override", rc == 2, str(rc))

    rc = gate([("brief", "d.o.b. April 12, 1988")], allow_pii=False, printer=lambda *_a: None)
    ok("gate: personal data blocks without --allow-pii", rc == 3, str(rc))
    rc = gate([("brief", "d.o.b. April 12, 1988")], allow_pii=True, printer=lambda *_a: None)
    ok("gate: --allow-pii lets personal data through", rc == 0, str(rc))

    rc = gate([("brief", "blocks a labelled date of birth unless you pass --allow-pii")],
              printer=lambda *_a: None)
    ok("gate: does NOT fire on its own documentation (the false positive that kills a gate)",
       rc == 0, str(rc))

    findings = scan("sk-ant-api03-" + "A" * 40)
    ok("gate: reports kind and line, never the value",
       findings and all("A" * 20 not in str(f) for f in findings), str(findings))


def suite_mutations(corpus):
    from krokai.mutations import run
    reg = [p for p in corpus.paths if "214" in os.path.basename(p)][0]
    man = [p for p in corpus.paths if "PM" in os.path.basename(p)][0]
    # Two base quotations chosen so that between them EVERY mutation is applicable: a modal without
    # a following negation, an existing negation, a digit, enough words for a tail rewrite, and a
    # comma-plus-limiter to cut before. One quotation exercises about one mutation, and a
    # regression bank that only ever runs one mutation is not a regression bank.
    base = [("The district director may consider reinstating a student who makes a request for "
             "reinstatement, but do not include instances where a pattern of repeated violations "
             "has occurred", reg),
            ("An applicant shall not be admitted to the United States unless he establishes to the "
             "satisfaction of the officer that he is not inadmissible under section 212", man)]
    stats, rows = run(base, corpus, limit=5, printer=lambda *_a: None)
    applied = sum(s["applicable"] for s in stats.values())
    ok("mutations: every mutation class is exercised by the sample", applied >= 6, str(applied))
    caught = sum(s["caught"] for s in stats.values())
    ok("mutations: it catches most of what it makes", caught >= applied * 0.5,
       "%d/%d" % (caught, applied))
    ok("mutations: cut-condition is credited only for the right REASON",
       all(r["caught"] is False or r["verdict"].startswith("TRUNCATED")
           for r in rows if r["mutation"] == "cut-condition"),
       str([r for r in rows if r["mutation"] == "cut-condition"]))


def suite_prompts():
    from krokai.prompts import build_brief, anchor_warnings, QUOTE_RULES

    b = build_brief("What does the rule say?", marker="DONE-1")
    ok("brief: carries the fabrication rule", "worse than a refusal" in b.lower())
    ok("brief: carries the provenance vocabulary", "[SNIPPET]" in b)
    ok("brief: ends with the completion marker", b.rstrip().endswith("DONE-1"))

    # 🔴 THE GRADER MUST NOT BE STRICTER THAN THE INSTRUCTIONS. `DATED_EDITION_CITED` has downgraded
    # rounds for as long as the analytics have existed, while nothing in the brief ever asked a
    # reviewer to check whether a codification was the text in force. A score against an unstated
    # rule measures what the reviewer happened to guess, not what it did.
    ok("brief: asks for the EFFECTIVE date, which the analytics already grade on",
       "effective date" in b.lower() and "annual edition" in b.lower())
    ok("brief: forbids joining two sources into a claim in neither",
       "unsupported synthesis" in b.lower())
    ok("brief: requires the source layer to be collected before any conclusion",
       "two layers" in b.lower())
    # Coverage of the pairing above, asserted rather than assumed: every quality code that can
    # downgrade a round must correspond to something the brief actually asked for.
    from krokai.consult import QUALITY_MEANING, INSTRUMENT_ONLY
    graded = set(QUALITY_MEANING) - set(INSTRUMENT_ONLY)
    asked = {"DATED_EDITION_CITED": "effective date", "COMMENTARY_CITED": "[OPENED]",
             "NO_URLS_CITED": "url", "SEARCH_NOT_USED": "search",
             "GOV_LOOKALIKE_CITED": "url"}
    ok("brief: every grading code has something in the brief it grades against",
       all(k in asked and asked[k].lower() in b.lower() for k in graded),
       str(sorted(graded - set(asked))))

    w = anchor_warnings("Is there a simple statement rule in section E.8?")
    ok("brief: anchoring in the question is detected",
       any("yes/no" in why for why, _f in w), str(w))

    w2 = anchor_warnings("Quote the entire section in full, all of the paragraphs in full.")
    ok("brief: an unanchored question with the in-full instruction is clean", not w2, str(w2))

    # 🔴 The "quote it IN FULL" requirement is scoped, and these four cases are why. It fired on a
    # software-architecture brief, which hands the reviewer no statutory text at all - a false
    # positive in a safety check, which this toolkit treats as worse than a miss because it teaches
    # the reader to dismiss the whole class by reflex.
    ok("brief: the in-full rule stays silent when no legal text is handed over",
       not anchor_warnings("Which architecture is right, and what does the loser cost?"))
    ok("brief: the in-full rule fires when a citation IS handed over",
       any("IN FULL" in why for why, _f in
           anchor_warnings("Does 8 CFR 274a.12(c)(9) permit work before the notice?")))
    ok("brief: the in-full rule fires on an embedded quotation of a provision",
       any("IN FULL" in why for why, _f in anchor_warnings(
           'The rule says "the officer may provide a simple statement of the reasons" - check it.')))
    ok("brief: every required-phrase entry declares when it applies",
       all(len(e) == 3 for e in __import__("krokai.prompts", fromlist=["x"]).REQUIRED_PHRASES))


def suite_bank(tmp):
    from krokai.bank import candidates, in_bank, append_queue, queue_open_items

    text = ('We rely on «an applicant shall not be admitted to the United States unless he '
            'establishes eligibility» and on our own Russian gloss «это наш комментарий '
            'на русском языке, он не является нормой права вообще».')
    c = candidates(text)
    ok("bank: an English quotation of law is a candidate",
       any("shall not be admitted" in q for q in c), str(c))
    ok("bank: our own Russian commentary is not", not any("комментарий" in q for q in c))

    bank_text = "> an applicant shall not be admitted to the United States unless he establishes"
    ok("bank: a banked quotation is recognised through guillemets and bold",
       in_bank("«**an applicant shall not be admitted** to the United States unless he "
               "establishes»", bank_text),
       "this exact false positive fired on the first run of the guard hook")

    q = os.path.join(tmp, "QUEUE.md")
    append_queue(q, [("some quotation", "NOT_FOUND", "—", "")], dropped=7, cap=40)
    op, done, _items = queue_open_items(q)
    ok("bank: the queue records open items", op == 2 and done == 0, "%d/%d" % (op, done))
    body = io.open(q, encoding="utf-8").read()
    ok("bank: a per-turn cap is stated out loud, never silent", "7" in body and "cap" in body.lower())


def suite_config(tmp):
    from krokai.config import Config, find_config, TEMPLATE
    import json as _j
    root = os.path.join(tmp, "matter")
    os.makedirs(os.path.join(root, "sub", "deeper"), exist_ok=True)
    _j.dump(TEMPLATE, io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8"))
    found = find_config(os.path.join(root, "sub", "deeper"))
    ok("config: found by walking up, like git finds .git",
       found and os.path.dirname(found) == root, str(found))
    cfg = Config(TEMPLATE, os.path.join(root, "casefile.json"))
    ok("config: relative paths resolve against the config file, not the cwd",
       cfg.abs("law") == os.path.normpath(os.path.join(root, "law")))
    ok("config: missing folders are reported rather than created",
       len(cfg.missing_paths()) >= 1)


def suite_install(tmp):
    from krokai.install import build_block, merge

    hooks_dir = os.path.join(tmp, "hooks")
    block = build_block(hooks_dir, "python")

    existing = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                               "command": "python",
                                               "args": ["/somewhere/else/save_answer.py"]}]}]}}
    new, added, _r = merge(existing, block, hooks_dir)
    stop = new["hooks"]["Stop"]
    theirs = [g for g in stop if any("save_answer" in str(h.get("args"))
                                     for h in g.get("hooks", []))]
    ok("install: someone else's hook survives the merge", len(theirs) == 1, str(stop))
    ok("install: ours is added", len(stop) == 2, str(len(stop)))

    twice, _a, _r = merge(new, block, hooks_dir)
    ok("install: running twice does not duplicate (idempotent)",
       len(twice["hooks"]["Stop"]) == 2, str(len(twice["hooks"]["Stop"])))

    removed, _a, rem = merge(twice, block, hooks_dir, remove=True)
    ok("install: uninstall removes ours and only ours",
       len(removed["hooks"]["Stop"]) == 1 and rem, str(removed["hooks"]["Stop"]))


def suite_verdicts():
    from krokai.verdicts import ORDER, LABEL, MEANING, DANGEROUS, CLEAN
    for lang in LABEL:
        missing = [v for v in ORDER if v not in LABEL[lang]]
        ok("verdicts: every verdict has a %s label" % lang, not missing, str(missing))
        missing = [v for v in ORDER if v not in MEANING[lang]]
        ok("verdicts: every verdict has a %s explanation" % lang, not missing, str(missing))
    ok("verdicts: dangerous and clean do not overlap",
       not (set(DANGEROUS) & set(CLEAN)), str(set(DANGEROUS) & set(CLEAN)))
    ok("verdicts: every verdict is classified somewhere",
       set(ORDER) == set(DANGEROUS) | set(CLEAN), str(set(ORDER) ^ (set(DANGEROUS) | set(CLEAN))))


def suite_consult(tmp):
    """The review layer. Nothing here contacts a vendor; that is asserted, not assumed."""
    import io as _io
    import json as _json
    import re as _re
    from krokai import consult as C

    # 🔴 A partial copy is a SUPPORTED install method - INSTALL.md option 4 exists for a work laptop
    # where nothing may be installed - and `channels.json` sits beside the package rather than inside
    # it. Copy only `krokai/` and the registry loader raised, so the suite died with a bare path list
    # and no verdict, in front of an installer whose instruction is "if any check fails, stop and
    # report it". A missing registry is a real defect for a full install and merely a limitation for
    # a package-only one, so it is reported as a named failure that says which of the two it is -
    # never a crash, and never a silent skip.
    # 🔴 `SystemExit` is listed FIRST and deliberately. It is this codebase's convention for a fatal
    # user-facing message (`config.py`, `citations.py`, `consult.py` all use it, and the hook
    # bootstrap already catches it), and it does NOT derive from `Exception` - so the obvious
    # `except Exception` caught nothing and the suite still died without printing a verdict.
    try:
        reg = C.load_registry()
    except (SystemExit, Exception) as exc:
        ok("consult: the channel registry ships beside the package and is findable", False,
           "%s - `krokai review` cannot run; the citation checker is unaffected"
           % (type(exc).__name__,))
        return
    chans = dict(C.channel_items(reg))
    ok("consult: the shipped registry loads", bool(chans))
    # 🔴 The registry's own convention is that an `_`-prefixed key is documentation. The first
    # version put a prose note inside `channels`, and every loop over it crashed on a string.
    # One iterator now decides what a channel is; this asserts the tests use it too.
    ok("consult: documentation keys are not mistaken for channels",
       all(isinstance(c, dict) and not n.startswith("_") for n, c in chans.items()))

    # Expectations are DERIVED from the file, never copied into the test. A registry with a fourth
    # channel must not turn three correct tests red.
    documented_kinds = set((reg.get("_kinds") or {}).keys())
    used_kinds = {c.get("kind") for _n, c in C.channel_items(reg)}
    ok("consult: every channel kind in use is documented in _kinds",
       used_kinds <= documented_kinds, str(used_kinds - documented_kinds))
    for name, ch in chans.items():
        ok("consult: %s declares a cost class" % name, bool(ch.get("cost")))
    metered_on = [n for n, c in chans.items() if c.get("cost") == "metered" and c.get("enabled")]
    ok("consult: no metered channel ships switched ON", not metered_on, str(metered_on))
    # A key belongs in the environment. A registry that ships one is a registry that gets committed.
    blob = _json.dumps(reg)
    from krokai.redact import scan as _scan
    ok("consult: the shipped registry contains no secret-shaped value",
       not [f for f in _scan(blob, "channels.json") if f[0] == "SECRET"])

    # Every code the transports can emit must have a meaning. Otherwise a real failure prints as
    # a bare token and the reader has to read the source to find out what happened.
    src = _io.open(C.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    emitted = set(_re.findall(r'\(\s*"([A-Z][A-Z_]{3,})"\s*,', src))
    known = set(C.FAILURE_MEANING) | set(C.QUALITY_MEANING)
    ok("consult: every emitted code has a plain-English meaning",
       emitted <= known, str(sorted(emitted - known)))

    # --- keys ------------------------------------------------------------------------------
    from krokai import keys as K
    from krokai.redact import scan as _kscan

    api = [(n, c) for n, c in C.channel_items(reg) if c.get("kind") == "http"]
    ok("keys: API channels ship", bool(api))
    for n, c in api:
        ok("keys: %s names a key variable" % n, bool(c.get("key_env")))
        ok("keys: %s declares its API shape" % n, (c.get("api") or "chat") in ("chat", "messages"))
    ok("keys: no API channel ships enabled", not [n for n, c in api if c.get("enabled")])

    # 🔴 The recipe must not itself look like a leaked key. Measured: `setx NAME "18-word-chars"`
    # matched the labelled-secret detector, so the instructions for handling a key SAFELY were
    # blocked as a key. Third false positive in this project's own safety checks, and by its own
    # doctrine that outranks a miss.
    for line in K.console_recipe("KROKAI_TEST_KEY"):
        hits = [f for f in _kscan(line, "recipe") if f[0] == "SECRET"]
        ok("keys: the console recipe is not itself secret-shaped", not hits, line[:60])

    os.environ["KROKAI_SELFTEST_KEY"] = "abcdefghijklmnopqrstuvwxyz0123456789"
    st = K.status(["KROKAI_SELFTEST_KEY", "KROKAI_DEFINITELY_UNSET"])
    ok("keys: status reports set-ness and LENGTH only",
       st[0] == ("KROKAI_SELFTEST_KEY", True, 36) and st[1][1] is False, str(st))
    ok("keys: the folder note tells an assistant to stop, and says rotate",
       "stop here" in K.FOLDER_NOTE.lower() and "rotate" in K.FOLDER_NOTE.lower())
    del os.environ["KROKAI_SELFTEST_KEY"]

    kf = os.path.join(tmp, "keys.env")
    _io.open(kf, "w", encoding="utf-8").write(
        "# comment\nKROKAI_FROMFILE=zzz9\nKROKAI_ALREADY=fromfile\n")
    os.environ["KROKAI_ALREADY"] = "fromenv"
    got = K.load_key_file(kf)
    ok("keys: the key file loads by NAME, and returns names not values",
       got == ["KROKAI_FROMFILE"], str(got))
    # The console is the stronger channel; a stale line in a file must not silently override it.
    ok("keys: an existing environment value wins over the file",
       os.environ["KROKAI_ALREADY"] == "fromenv")
    for v in ("KROKAI_FROMFILE", "KROKAI_ALREADY"):
        os.environ.pop(v, None)

    g = reg["grounding"]
    ok("consult: a .gov page is primary",
       C.classify_url("https://www.ecfr.gov/current/title-8/section-274a.12", g) == "primary")
    # 🔴 The measurement behind this test: a channel graded clean while grounded on an annual CFR
    # edition. It is a dated snapshot, not the text in force, and it sits on a .gov domain - so the
    # obvious "is this an official source" check passes it.
    ok("consult: an annual edition is a snapshot, not current law",
       C.classify_url("https://www.govinfo.gov/content/pkg/CFR-2019-title8-vol1/x.htm",
                      g) == "snapshot")
    ok("consult: a firm blog is not authority",
       C.classify_url("https://www.jdsupra.com/legalnews/whatever-12345/", g) == "nonauthoritative")

    # 🔴🔴 THE SUBSTRING TEST THAT GRADED HOSTILE DOMAINS AS OFFICIAL LAW.
    #
    # The old line was `host.endswith(s) or s in host`, and the second half of it returned `primary`
    # - the strongest endorsement this tool can give a URL, the bucket that means "this is the law
    # itself" - for every host below. Found by execution, not by reading; nothing in the suite could
    # have caught it, because there was no test that a NON-official domain is not official.
    #
    # Each of these is a real shape. `.gov.ru` / `.gov.cn` / `.gov.cm` are ordinary foreign
    # second-level government domains, `mil.kg` likewise, and `milano.it` is a city. The hyphenated
    # pair are typosquats of the kind a paid channel was measured grounding an answer on.
    for host, why in [("https://www.milano.it/turismo", "`mil` inside an Italian city"),
                      ("https://uscis.gov.ru/policy-manual", "`gov` label under .ru"),
                      ("https://law.gov.cn/rules", "`gov` label under .cn"),
                      ("https://www.mil.kg/news", "`mil` label under .kg"),
                      ("https://ecfr.i0.gov.cm/current/title-8", "`gov` label under .cm"),
                      ("https://uscisdhs-gov.us/policy-manual", "typosquat, hyphen part"),
                      ("https://uscis-gov.co/policy-manual", "typosquat, hyphen part")]:
        ok("consult: %s is NOT official law (%s)" % (host.split("/")[2], why),
           C.classify_url(host, g) != "primary", C.classify_url(host, g))

    # And the other direction, which is the half that makes the fix safe rather than merely strict.
    for host in ["https://www.uscis.gov/policy-manual", "https://uscis.gov",
                 "https://uscis.gov./trailing-root-dot", "https://UsCiS.GoV/mixed-case",
                 "https://uscis.gov:8443/explicit-port", "https://www.gov.uk/guidance/x",
                 "https://legislation.gov.uk/ukpga/2020/1",
                 "https://eur-lex.europa.eu/legal-content/EN/TXT/",
                 "https://www.courtlistener.com/opinion/1/"]:
        ok("consult: %s is still official" % host.split("/")[2][:34],
           C.classify_url(host, g) == "primary", C.classify_url(host, g))

    # 🔴 PARSER BYPASSES. OWASP's Web Security Testing Guide lists `@`, `#` and percent-encoding as
    # the standard ways to make a host filter read the wrong name, and a reviewer of this very change
    # named them. A userinfo spoof puts the real domain to the LEFT of an `@`, where a naive split
    # reads it as the host; the host here is `evil.example`.
    for u, want, why in [
            ("https://www.uscis.gov@evil.example/pm", "other", "userinfo before @"),
            ("https://evil.example/#https://www.uscis.gov/pm", "other", "real name in the fragment"),
            ("https://evil.example/?u=https://www.uscis.gov/pm", "other", "real name in the query"),
            # Not `other`: this one wears `gov` as a whole label and ends somewhere else, which is
            # the impersonation shape exactly. The stronger answer is the right one.
            ("https://www.uscis.gov.evil.example/pm", "lookalike", "official name as a subdomain"),
            ("https://user:pw@www.uscis.gov/pm", "primary", "credentials on a REAL host")]:
        ok("consult: %s does not decide the classification" % why,
           C.classify_url(u, g) == want, "%s -> %s" % (u[:44], C.classify_url(u, g)))
    ok("consult: host parsing is delegated, not hand-rolled against a bypass list",
       "urlsplit" in src)

    # COVERAGE, not just correctness. This toolkit has already shipped a guard that compared
    # accurately and matched nothing in the sentence carrying the defect, so a planted wrong value
    # passed a clean run. Assert that the bucket exists, is reachable, and reaches the verdict.
    look = C.grounding_of({"text": "See https://uscisdhs-gov.us/pm and https://uscis.gov.ru/x"}, g)
    ok("consult: the lookalike bucket is populated, not merely defined",
       len(look.get("lookalike") or []) == 2, str(look))
    v, q, _gr = C.triage({"channel": "t", "failures": [], "quality": [],
                          "text": "Authority: https://uscisdhs-gov.us/policy-manual"}, g)
    ok("consult: citing a government lookalike grades DIRTY", v == "DIRTY", v)
    ok("consult: ...and names the code", "GOV_LOOKALIKE_CITED" in [c for c, _ in q], str(q))

    # 🔴 THE INSTRUMENT IS NOT THE ANSWER. `NO_TELEMETRY` is a constant property of a channel, and
    # while it graded, every answer absorbed from an external harness was DIRTY forever - for a
    # reason the console printer then deliberately skipped. A verdict that never varies carries no
    # information, and an unexplained one teaches the reader to ignore the column.
    tele = {"channel": "t", "text": "Authority: https://www.ecfr.gov/current/title-8",
            "failures": [], "quality": [("NO_TELEMETRY", "")]}
    v, q, _gr = C.triage(tele, g)
    ok("consult: a good answer from a channel with no telemetry grades OK", v == "OK", v)
    ok("consult: ...and the instrument code is still reported, not dropped",
       "NO_TELEMETRY" in [c for c, _ in q], str(q))
    v, _q, _gr = C.triage({**tele, "text": "Authority: https://www.jdsupra.com/x"}, g)
    ok("consult: a real sourcing fault still grades DIRTY alongside it", v == "DIRTY", v)
    ok("consult: the printer no longer skips the code that produces the verdict",
       'if code == "NO_TELEMETRY":\n                continue' not in src)

    clean = {"channel": "t", "text": "See https://www.ecfr.gov/current/title-8 for the text.",
             "failures": [], "quality": []}
    v, _q, _gr = C.triage(clean, g)
    ok("consult: a clean answer on a primary source grades OK", v == "OK", v)
    v, _q, _gr = C.triage({**clean, "failures": [("TIMED_OUT", "")]}, g)
    ok("consult: any failure code grades FAILED", v == "FAILED", v)
    v, q, _gr = C.triage({"channel": "t", "text": "no links here at all", "failures": [],
                          "quality": []}, g)
    ok("consult: an answer citing nothing is DIRTY, not OK", v == "DIRTY", v)
    ok("consult: ...and says why", "NO_URLS_CITED" in [c for c, _ in q], str(q))

    # 🔴 NEGATIVE CONTROLS for the refusal detector. Each of these is a sentence a good review
    # legitimately contains. The system this was extracted from graded the honest outcome its own
    # brief asks for as FAILED, because its detector matched ordinary English about the law.
    for line in ["my search found no confirmation that this rule exists",
                 "the regulation does not set a deadline",
                 "the firm's version is truncated and drops the condition",
                 "I cannot find this sentence anywhere in the published text",
                 "the agency declined to adopt the proposed comment"]:
        ok("consult: refusal detector stays silent on %r" % line[:38],
           not C._REFUSAL_RE.search(line))
    ok("consult: refusal detector still catches a real policy refusal",
       bool(C._REFUSAL_RE.search("I can't help with that request.")))

    r = C._finish({"text": "x" * 2000, "failures": [], "quality": []}, "END-MARKER", 800)
    ok("consult: a missing end marker is a FAILURE, because partial reads as complete",
       "NO_END_MARKER" in [c for c, _ in r["failures"]])

    # 🔴 NOTHING ACCUMULATES ACROSS ROUNDS. A persistent dispatch ledger was built and cut on
    # 2026-08-02. This asserts it stays cut: a file that quietly grows a history of what was sent
    # to whom is a second record of the client's material, and its absence is a property worth
    # testing rather than a thing to remember.
    # 🔴 THREE FEATURES WERE BUILT AND THEN CUT ON INSTRUCTION (2026-08-02): a persistent dispatch
    # ledger, the brief hash printed before sending, and the per-vendor retention column. Testing
    # that something is ABSENT is the only way it stays absent - otherwise it comes back next month
    # looking like an improvement, because each one reads as obviously useful in isolation.
    for gone, why in [("append_ledger", "cross-round dispatch ledger"),
                      ("brief_sha", "brief hash printed before sending")]:
        ok("consult: %s stays removed" % why, not hasattr(C, gone) and gone not in src)
    ok("consult: the retention column stays removed",
       "retains" not in src and "UNKNOWN_RETENTION" not in src)
    ok("consult: no channel in the shipped registry declares retention",
       not [n for n, c in C.channel_items(reg) if "retains" in c])

    rows = [{"channel": "t", "verdict": "DIRTY", "seconds": 1, "bytes": 10,
             "ground": {"total": 1, "primary": [], "snapshot": ["u"], "nonauthoritative": []},
             "failures": [], "quality": [("DATED_EDITION_CITED", "1: u")]}]
    ap = C.write_analytics(os.path.join(tmp, "an.md"), rows, 1.0)
    txt = _io.open(ap, encoding="utf-8").read()
    ok("consult: analytics explains the code rather than printing a bare token",
       C.QUALITY_MEANING["DATED_EDITION_CITED"][:40] in txt)
    # 🔴 The caveat is load-bearing, not decoration. Two independent reviewers attacked this same
    # mechanism: a URL printed in an answer comes from the same process that produces a fabricated
    # quotation, so presenting the count as retrieval evidence manufactures corroboration out of
    # the model's own assertion.
    ok("consult: analytics says printing a URL is not opening it",
       "printing is not opening" in txt.lower())
    # An annual edition is the codification - official law, just not the text in force. Tabulating
    # it opposite `primary` printed three government sources as `primary 0`.
    ok("consult: a dated official edition still counts as official",
       "| 1 | 1 |" in txt, txt.split("|---")[-1][:200])
    ok("consult: analytics refuses to claim the answers are right",
       "NOTHING HERE SAYS" in txt.upper())

    # 🔴 `other` must not be the silent bucket. A live typosquat carrying no official-looking label
    # - `ussciss.us` resolved when checked - is invisible to a label-based detector by construction,
    # and closing that with a similarity threshold was rejected by four independent reviewers. So
    # the hole is PRINTED rather than closed: naming what was not covered is the rule here, because
    # a gap nobody mentions reads as coverage.
    rows2 = [{"channel": "t", "verdict": "OK", "seconds": 1, "bytes": 10, "failures": [],
              "quality": [], "ground": {"total": 2, "primary": [], "snapshot": [],
                                        "lookalike": [], "nonauthoritative": [],
                                        "other": ["https://ussciss.us/pm", "https://ussciss.us/x"]}}]
    t2 = _io.open(C.write_analytics(os.path.join(tmp, "an2.md"), rows2, 1.0), encoding="utf-8").read()
    ok("consult: an unrecognised host is named in the report, not swallowed by `other`",
       "ussciss.us" in t2, t2[-400:])
    ok("consult: ...once, as a host, not once per URL", t2.count("`ussciss.us`") == 1)
    ok("consult: ...and the report says why no verdict is attached to it",
       "cannot be detected mechanically" in t2)


def suite_docs(root):
    """The prose is checked against the code, because prose has no error signal.

    🔴 This suite exists because of a measured failure, not as tidiness. Adding the house-number
    detector took the personal-data table from 11 entries to 12, and three shipped documents went on
    saying 11 - in a file whose entire promise is that its numbers were measured rather than
    estimated. Nothing failed, because nothing was looking. Same shape as the `LICENSE` that read
    `Copyright (c) 2026 the operator Saevets` for a repository's whole life while the build reported
    clean: a claim nobody executes is a claim with no error signal.

    So the numbers a document states about the code are now *read back out of the document* and
    compared with the code. The self-test's own count is deliberately NOT written down anywhere,
    for the opposite reason - it changes on nearly every commit, so guarding it would only teach
    someone to delete the guard.
    """
    from krokai.redact import SECRET_PATTERNS, PII_PATTERNS

    docs = [f for f in ("README.md", "README.ru.md", "FEATURES.md", "INSTALL.md",
                        "INSTALL-FOR-AI.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md")
            if os.path.exists(os.path.join(root, f))]
    if not docs:
        # Stated out loud rather than skipped silently: a check that quietly does not run reads
        # exactly like a check that ran and found nothing.
        print("note: documentation checks did not run - no shipped .md next to the package "
              "(a package-only copy). Run the suite from a source checkout to include them.")
        return

    text = {f: io.open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            for f in docs}

    # 🔴 The first version of this check MATCHED NOTHING IN THE SENTENCE IT WAS WRITTEN FOR, and
    # passed. Its regex demanded the word "detectors" between the number and the class, and the
    # README says "10 detectors for credentials ..., 12 for personal identifiers" - the second
    # count carries no such word. A deliberately falsified count of 99 went straight through while
    # the suite printed a clean run, which is this project's own recurring defect committed inside
    # the guard written to prevent it. Two things fixed it, and the second matters more than the
    # first: the word is optional now, AND every document must be shown to carry BOTH counts, so a
    # sentence the regex cannot see fails loudly instead of being silently uncovered.
    CLASS = {"credentials": "secret", "personal identifiers": "pii",
             "учётных данных": "secret", "персональных данных": "pii"}
    want = {"secret": len(SECRET_PATTERNS), "pii": len(PII_PATTERNS)}

    claims = []          # (file, class, claimed)
    for f, t in text.items():
        for m in re.finditer(r"(\d+)\s+(?:detectors?\s+|детекторов\s+)?(?:for\s+)?"
                             r"(credentials|personal identifiers|учётных данных|персональных данных)",
                             t):
            claims.append((f, CLASS[m.group(2)], int(m.group(1))))

    bad = ["%s says %d for %s, the table has %d" % (f, c, k, want[k])
           for f, k, c in claims if c != want[k]]
    ok("docs: every stated detector count matches the tables", not bad, "; ".join(bad))

    # Coverage, not just correctness: a document that states one count and not the other has a
    # sentence this check cannot see, and an unseen sentence is where the stale number lives.
    for f in ("README.md", "README.ru.md", "FEATURES.md"):
        if f not in text:
            continue
        got = {k for g, k, _ in claims if g == f}
        ok("docs: %s states both detector counts where the check can read them" % f,
           got == {"secret", "pii"}, "found %s" % (sorted(got) or "none"))

    # -- the version the tool prints against the version it documents -----------------------------
    # 🔴 `krokai --version` said 0.1.0 while CHANGELOG.md documented 0.2.0. One fact, two homes, and
    # the home that gets EXECUTED was the stale one - which is the direction people assume cannot
    # happen. Nothing forced them to agree, so they stopped agreeing.
    if "CHANGELOG.md" in text:
        from krokai import __version__
        heads = re.findall(r"^## \[([0-9][^\]]*)\]", text["CHANGELOG.md"], re.M)
        ok("docs: the newest changelog entry is a version number", bool(heads), "none found")
        if heads:
            ok("docs: --version matches the newest changelog entry", __version__ == heads[0],
               "__version__=%s, changelog=%s" % (__version__, heads[0]))

    # -- an install command nobody can run --------------------------------------------------------
    # 🔴 FOURTH TIME IN THIS PROJECT that a safety check fired on the documentation OF that check:
    # the changelog entry describing the placeholder defect contains the placeholder. A false
    # positive here is worse than a miss - it teaches whoever hits it to delete the check - so the
    # exemption is a DECLARATION the document makes about itself, in the manner of the parent
    # project's `PUBLISH-AUDIT: PATTERN-SOURCE`, never a filename this code recognises. An
    # allowlist keyed on a name is what let a mangled `LICENSE` ship for a repository's whole life.
    #
    # And the declaration is refused outright for the three files a reader copies commands out of.
    # A document may say "I discuss placeholders"; the install instructions may not.
    DECLARE = "KROKAI-SELFTEST: DISCUSSES-PLACEHOLDERS"
    NEVER = ("README.md", "README.ru.md", "INSTALL.md", "INSTALL-FOR-AI.md")
    abuse = [f for f in NEVER if DECLARE in text.get(f, "")]
    ok("docs: the placeholder exemption is refused to the files people copy commands from",
       not abuse, ", ".join(abuse))
    holes = ["%s:%s" % (f, ph) for f, t in text.items() if DECLARE not in t or f in NEVER
             for ph in ("<owner>", "<your-", "TODO", "FIXME") if ph in t]
    ok("docs: no placeholder survives in a shipped document", not holes, ", ".join(holes))

    # -- a link on the front page that 404s is the dead-button failure again -----------------------
    if "README.md" in text:
        rel = set(re.findall(r"\]\((?!https?:|\.\./)([^)#\s]+)", text["README.md"]))
        missing = sorted(r for r in rel if not os.path.exists(os.path.join(root, r)))
        ok("docs: every relative link in README.md resolves to a file", not missing,
           ", ".join(missing))

    # -- the translation drifts, and it drifts in the direction that flatters ----------------------
    # 🔴 Measured: README.ru.md was two whole sections behind README.md - the second-opinion
    # architecture and, worse, the PRIOR ART table. A Russian reader was therefore shown a tool with
    # no precedent and no invitation to name one, which is not a translation gap but a different
    # claim. Comparing prose across languages is hopeless; comparing the set of outside projects and
    # people each version links to is not, and that set is exactly what went missing.
    if "README.md" in text and "README.ru.md" in text:
        def outward(t):
            skip = ("github.com/igorsaevets/krokai-law", "keepachangelog", "semver.org")
            return {u.rstrip("/.,)") for u in re.findall(r"https?://[^\s)\]]+", t)
                    if not any(s in u for s in skip)}
        en, ru = outward(text["README.md"]), outward(text["README.ru.md"])
        ok("docs: the Russian README credits the same outside projects as the English one",
           not (en - ru), "missing from README.ru.md: " + ", ".join(sorted(en - ru)))
        ok("docs: ...and cites nothing the English one does not",
           not (ru - en), "only in README.ru.md: " + ", ".join(sorted(ru - en)))


def suite_rename(root):
    """A rename is survivable only if the old stamp is still recognised.

    The tier-D stamp is written into every report this tool produces and read back months later.
    Renaming the product changed the string; a report carrying the old one would silently rejoin
    tier C, which is incident 3 - the largest number in the incident log, 1 443 of 1 606 misses
    from a single file. So the tool writes one stamp and recognises several.
    """
    from krokai.run import SENTINEL, SENTINELS
    ok("rename: the stamp written carries the current product name", SENTINEL.startswith("KROKAI"),
       SENTINEL)
    ok("rename: the stamp of the previous name is still recognised",
       "LAWVERBATIM-TOOL-OUTPUT" in SENTINELS, str(SENTINELS))
    ok("rename: what is written is the first thing recognised", SENTINELS[0] == SENTINEL,
       str(SENTINELS))


# ------------------------------------------------------------------------------------------------
def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    tmp = tempfile.mkdtemp(prefix="krokai-selftest-")
    try:
        corpus, law = build_corpus(tmp)
        suite_normalise()
        suite_extract()
        suite_corpus(corpus, law)
        suite_verify(corpus)
        suite_word_diff()
        suite_citations()
        suite_address(corpus, law)
        suite_redact()
        suite_mutations(corpus)
        suite_prompts()
        suite_bank(tmp)
        suite_config(tmp)
        suite_install(tmp)
        suite_verdicts()
        suite_consult(tmp)
        suite_rename(root)
        suite_docs(root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(PASS) + len(FAIL)
    for name, note in FAIL:
        print("FAIL  %s%s" % (name, ("  ::  " + note) if note else ""))
    print("\nself-test: %d/%d passed  (no vendor was contacted, nothing was written outside %s)"
          % (len(PASS), total, tempfile.gettempdir()))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
