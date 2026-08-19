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

from ._datadir import data_dir

PASS = []
FAIL = []


def _is_source_checkout(root):
    """True when `root` is this project's own working tree rather than `site-packages`.

    Both markers are required. `CHANGELOG.md` alone is too weak - it is a common filename and
    site-packages can contain one from any dependency; `krokai/selftest.py` alone is satisfied by
    the installed package itself. Together they identify a checkout of THIS repository.
    """
    return (os.path.isfile(os.path.join(root, "CHANGELOG.md"))
            and os.path.isfile(os.path.join(root, "krokai", "selftest.py")))


def _hook_module(name):
    """Import a hook in either layout.

    🔴 This suite used a bare `from hooks import bank_queue`, which only resolves when the
    repository root is on sys.path - that is, from a clone. Installed from a wheel the hooks live
    at `krokai.hooks`, the bare import raises ModuleNotFoundError, and the suite died at test 400
    of 421. It was found by running the installed package, not by reading it: from a clone the
    suite passed 421/421 and said nothing.
    """
    try:
        mod = __import__("krokai.hooks." + name, fromlist=[name])
    except ImportError:
        mod = __import__("hooks." + name, fromlist=[name])
    return mod


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

    # --- the CFR omitted-text marker is TEXT, and the quote side used to eat it -----------------
    from krokai.normalize import prepare_quote
    ok("strip_markdown KEEPS the CFR omission marker `* * *`",
       prepare_quote("prescribe. * * * (d) Limitation.") == "prescribe. * * * (d) Limitation.",
       prepare_quote("prescribe. * * * (d) Limitation."))
    # Verbatim, not canonicalised: the corpus keeps whatever spelling it has, so the quote must
    # match itself rather than a tidied version of itself.
    for spelling in ("* * *", "* * * *", "*   *   *"):
        ok("strip_markdown restores the marker VERBATIM: %r" % spelling,
           prepare_quote("before %s after" % spelling) == "before %s after" % spelling,
           prepare_quote("before %s after" % spelling))
    # 🔴 And with PUNCTUATION around it, which is what a quotation actually looks like. The first
    # version of this rule required whitespace on both sides; a reviewer found that
    # `prescribe (* * *) and then` came out as `prescribe (  ) and then` - the marker deleted by
    # the closing bracket. Confirmed by execution before the fix, and locked here in five shapes.
    for wrapped in ("prescribe. * * *.", "prescribe (* * *) and then", 'he wrote "* * *" there',
                    "prescribe. * * *, and then", "line ends with * * *"):
        ok("strip_markdown keeps the marker with punctuation around it: %r" % wrapped[:28],
           "* * *" in prepare_quote(wrapped), prepare_quote(wrapped))
    # 🔴 The negative control that kills the obvious implementation. `\*(\s*\*)+` matches the `* *`
    # standing BETWEEN two bolded words, protects it, and leaves the fragment in the text.
    ok("strip_markdown still strips two ADJACENT bold spans (the `* *` between them is not a marker)",
       prepare_quote("**alpha** **beta** gamma") == "alpha beta gamma",
       prepare_quote("**alpha** **beta** gamma"))
    ok("strip_markdown does not treat an asterisk glued to a word as a marker",
       prepare_quote("x*y and z*w") == "xy and zw", prepare_quote("x*y and z*w"))
    ok("strip_markdown still strips single-asterisk emphasis",
       prepare_quote("the *alien* shall") == "the alien shall")
    # Applied twice by two entry points in the same call chain, so it has to be a no-op the second
    # time or `check()` would quietly differ from `extract_quotes` again, the other way round.
    for s in ("**bold** text", "> quoted", u"«wrapped»", "a * * * b", "see [x](https://e.com) now"):
        ok("prepare_quote is idempotent: %r" % s, prepare_quote(prepare_quote(s)) == prepare_quote(s))


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
    # 🔴 Rewritten 2026-08-03, and the old assertion was wrong in a way worth recording. It said a
    # short markdown file must be EXCLUDED. That is right about a placeholder and wrong about a real
    # short provision - a definition, a savings clause - and the tool cannot tell them apart from
    # the length. Excluding turned a correct quotation of short law into NOT_FOUND, which is this
    # tool's fabrication signal: the checker built to catch invented law reported real law as
    # invented. So the two signals are separated - warn and index, rather than exclude.
    ok("corpus: a short text source is INDEXED, not thrown away",
       any("stub" in p for p in corpus.short_sources)
       and not any("stub" in p for p in corpus.excluded_stub),
       "short=%s excluded=%s" % (len(corpus.short_sources), len(corpus.excluded_stub)))
    ok("corpus: and it is still reported, so a placeholder is noticed",
       len(corpus.short_sources) >= 1)
    ok("corpus: a quotation from a SHORT source verifies", corpus.find("placeholder") is not None)
    ok("corpus: real sources are indexed", len(corpus.paths) == 4)
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
    from krokai.extract import extract_quotes

    v, _w, _d = check("certified by a designated school official to consist of at least eighteen "
                      "clock hours of attendance a week", corpus)
    ok("verdict VERIFIED on an exact, complete quotation", v == "VERIFIED", v)

    # --- the two entry points must agree, whatever the drafter pasted ---------------------------
    # 🔴 The regression lock for the composition drift. `krokai check` reaches this function
    # through `extract_quotes`, which strips markdown; `krokai quote` calls it directly. Five of
    # six realistic inputs disagreed, and not as found-vs-missing: a quotation stopping one clause
    # short of a limiter came back TRUNCATED_CONDITION one way and PUNCTUATION the other, which
    # downgrades the most dangerous verdict this tool has into a cosmetic one.
    #
    # These four shapes are what a model emits and therefore what a person pastes.
    truncated = ("The district director may consider reinstating a student who makes a request "
                 "for reinstatement")
    for label, pasted in [
            ("guillemets", u"«%s»" % truncated),
            ("bold inside the span", truncated.replace("may consider", "**may consider**")),
            ("a provenance tag", "%s [OPENED]" % truncated),
            ("a blockquote marker", "> %s" % truncated)]:
        direct = check(pasted, corpus)[0]                     # the `krokai quote` door
        got = extract_quotes('"%s"' % pasted.replace('"', ""), min_len=20)
        through = check(got[0], corpus)[0] if got else "NO QUOTE"   # the `krokai check` door
        ok("pipeline: both entry points agree when the paste carries %s" % label,
           direct == through == "TRUNCATED_CONDITION", "quote=%s check=%s" % (direct, through))

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


def suite_r50_no_green_without_guard(corpus):
    """🔴🔴 NO GREEN VERDICT WITHOUT THE TRUNCATION QUESTION (2026-08-19).

    The defect, and it was shipped: `truncated_condition` needs an exact hit, so it could only
    ever run on the exact-match branch. PUNCTUATION, TYPESETTING and the shingle path returned
    green without ever asking whether the source continues with a limiter. One character
    decided which:

        the quotation as-is                -> TRUNCATED_CONDITION   loud, correct
        the same + a trailing full stop    -> PUNCTUATION           green
        the same + a line-break hyphen     -> PUNCTUATION           green

    Ending a quotation with a full stop is the normal thing a drafter does, so the laundering
    needed no ill intent. And the detail line printed «our quotation adds `.`» - a precise
    explanation of the WRONG difference, which is worse than silence: it stops the reader
    looking.

    🔴 WHY THIS IS A SEPARATE SUITE. The whole existing suite passed BEFORE the fix and after
    it. Every truncation case it owned was written without trailing punctuation, so it could
    not fail on the bug. A suite that cannot fail on a bug is not covering it - so the lock is
    stated here, in the shape the bug actually had.

    The last two checks are what keep this honest. Turning every near-miss red would pass the
    first three and produce a WORSE tool, because a false alarm in a safety gate teaches the
    reader to click past the gate. NEG-1 and NEG-2 assert that a quotation which is not
    truncated stays green while taking exactly the same branches.
    """
    from krokai.verify import check

    truncated = ("The district director may consider reinstating a student who makes a request "
                 "for reinstatement")
    complete = ("certified by a designated school official to consist of at least eighteen "
                "clock hours of attendance a week")

    v, _w, _d = check(truncated, corpus)
    ok("r50 POS-1 exact truncation is loud", v == "TRUNCATED_CONDITION", v)

    v, _w, _d = check(truncated + ".", corpus)
    ok("r50 POS-2 a trailing full stop does NOT launder a truncation into PUNCTUATION",
       v == "TRUNCATED_CONDITION", v)

    v, _w, _d = check(truncated.replace("reinstating", "reinstat-ing") + ".", corpus)
    ok("r50 POS-3 a line-break hyphen does NOT launder a truncation into TYPESETTING",
       v == "TRUNCATED_CONDITION", v)

    # --- negative controls: the guard must not turn honest near-misses red -------------------
    v, _w, _d = check(complete + ".", corpus)
    ok("r50 NEG-1 a COMPLETE quotation with an added full stop stays green",
       v != "TRUNCATED_CONDITION", v)

    v, _w, _d = check(complete.replace("clock hours", "clock hours,"), corpus)
    ok("r50 NEG-2 a genuine punctuation-only drift is still reported as PUNCTUATION",
       v in ("PUNCTUATION", "VERIFIED"), v)

    # 🔴 NEG-3 was NOT in the first version of this suite, and the first version of the fix
    # failed it. Found by the review panel that reviewed the fix - 7 of 13 channels named the
    # same hole - and reproduced by execution before it was believed. An ellipsis is the
    # drafter DISCLOSING the elision; shouting at it as loudly as at a silent truncation
    # destroys the distinction the verdict exists to draw.
    # 🔴 AMENDED IN R51. "Not a silent truncation" is the whole of what this control asserts, and
    # that is deliberate: it must NOT also assert "and therefore green". The v0.8.2 fix read it
    # that way and returned silence, which is what suite_r51_tail_elision now forbids. The two
    # controls are the two halves of one sentence - a disclosed elision gets a different NAME,
    # not a pass.
    for tail in ("...", "…"):
        v, _w, _d = check(truncated + tail, corpus)
        ok("r50 NEG-3 a DISCLOSED elision (%s) is not reported as a silent truncation" % tail,
           v != "TRUNCATED_CONDITION", v)


def suite_r51_tail_elision(corpus):
    """🔴🔴 THE ELISION AT THE END IS THE ONE NOBODY LOOKED AT (2026-08-19).

    `Corpus.gaps` computes `for k in range(len(parts) - 1)` - the spans BETWEEN fragments. A
    quotation that ENDS with an ellipsis elided the TAIL of the sentence, and a tail is not
    between anything, so no gap was ever computed for it. On top of that, `check` entered the
    ellipsis section only when `len(parts) > 1`, and a quotation that merely ends with an
    ellipsis yields ONE fragment - so it never reached that machinery at all.

    In legal drafting the proviso is at the END: "..., provided that", "..., unless",
    "..., except that", "... subject to". The single elision position the instrument did not
    examine is the position where the limiter almost always is.

    🔴 THIS WAS SELF-INFLICTED AND THE SUITE IS THE APOLOGY. v0.8.2 stopped calling a disclosed
    elision TRUNCATED_CONDITION - correct, the panel was right - but justified it with the claim
    that the case "belongs to the ellipsis machinery below". That machinery could not be reached.
    A sentence about control flow, written in a comment, never executed. The verdict that came
    out instead was PUNCTUATION «our quotation adds `.`» - the R50 confident-wrong-answer defect,
    reintroduced one round after it was named.

    POS-1/2 are the shape the bug had. NEG-1/2/3 are what stops the repair becoming a nuisance:
    measured over 1 118 ellipsis-terminated quotations in a real filing, this turns 26 green
    verdicts loud (2.3%), and reading all 26 by eye every one hides a real carve-out.
    """
    from krokai.verify import check, tail_elision_hides

    truncated = ("The district director may consider reinstating a student who makes a request "
                 "for reinstatement")
    complete = ("certified by a designated school official to consist of at least eighteen "
                "clock hours of attendance a week")

    for tail in ("...", "…"):
        v, _w, _d = check(truncated + tail, corpus)
        ok("r51 POS-1 a trailing ellipsis over a hidden limiter is LOUD, not green (%s)" % tail,
           v == "ELLIPSIS_HIDES", v)

    # 🔴 POS-2 locks the SENTENCE, not just the verdict. The regression this suite exists for did
    # not merely return green - it returned green with «our quotation adds `.`», a confident
    # description of a difference that was not the difference. R50 measured that a wrong
    # explanation is worse than silence, because silence makes a reader look and a confident
    # answer stops them. So assert what the reader is actually told.
    #
    # (An earlier draft of POS-2 asserted that a MID-elision agrees with a tail-elision, and it
    # failed - SPLICED - because the two halves I glued together came from different sentences of
    # the fixture. Kept in the comment rather than deleted: the agreement claim is real, but it is
    # demonstrated on a synthetic statute in r51_trailing_ellipsis.py, where the source can be
    # written to contain both halves in order. A test must not assert geography it does not own.)
    _v, _w, detail = check(truncated + "…", corpus)
    ok("r51 POS-2 the detail line says what was hidden, not what punctuation changed",
       "elision at the END" in detail and "adds `.`" not in detail, detail[:120])

    # --- negative controls -------------------------------------------------------------------
    for tail in ("...", "…"):
        v, _w, _d = check(complete + tail, corpus)
        ok("r51 NEG-1 a disclosed elision hiding nothing material stays green (%s)" % tail,
           v not in ("ELLIPSIS_HIDES", "TRUNCATED_CONDITION"), v)

    # 🔴 NEG-2 is the 27th alarm from the real-material measurement, the only false one. Its last
    # fragment was «(I) In general» - 14 characters, a heading that occurs all over the U.S. Code,
    # so the locator matched a DIFFERENT statute and reported that one's continuation. 25 is not a
    # threshold invented here: it is already this codebase's floor for "this fragment proves
    # something on its own" (see ellipsis_parts). Applying it removed exactly that alarm.
    p, _l, _t = tail_elision_hides("some heading … (I) In general…", "x", corpus)
    ok("r51 NEG-2 a last fragment under 25 chars is too short to locate - no alarm", p is None,
       str(p))

    # NEG-3: no ellipsis at the end at all => this helper must be inert, or it would double up
    # with the R50 guard and report the same thing twice under two names.
    p, _l, _t = tail_elision_hides(truncated, truncated, corpus)
    ok("r51 NEG-3 inert when the quotation does not end in an ellipsis", p is None, str(p))


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

    # --- cite-token guard back-ported from AOS round 29, redesigned per T58 panel ---------------
    #
    # `_STRIP` includes `(` and `)`, so `(b)(16)(i)` reaches word_diff as `b)(16)(i`. That token
    # carries digits and got promoted to OPERATOR by the digit rule — the exact noise the digit
    # rule exists to prevent from swallowing real signal. The guard excludes cite-shaped tokens
    # from OPERATOR promotion — but ONLY when the SAME cite token is on the other side (an
    # alignment artifact, not a real cite change).
    #
    # Codex T58 (round 29) rejected the earlier blanket guard because it demoted real pincite
    # edits like `(b)(16)(i)` → `(b)(16)(ii)` from OPERATOR to ALTERED. This is the design that
    # survives BOTH tests.

    changed, hits, _u = word_diff(
        "the officer shall (b)(16)(i) determine the application without further delay",
        "the officer shall (b)(16)(i) determine the application without further delay")
    ok("word_diff: an identical parenthesised citation does not fire OPERATOR",
       not hits, "%s" % (hits,))

    # 🔴 The Codex T58 test: a citation that ACTUALLY changed must stay OPERATOR. `(b)(16)(i)` vs
    # `(b)(16)(ii)` is a real pincite change — a legal signal — and must not be demoted to
    # ALTERED. The earlier "counter-test" that only asserted the tokens appear in `changed` was
    # a hollow check; the real assertion is `hits` non-empty.
    changed, hits, _u = word_diff(
        "as required by 8 CFR 214.2 (b)(16)(i) of this section",
        "as required by 8 CFR 214.2 (b)(16)(ii) of this section")
    ok("word_diff: a REAL cite change (i vs ii) survives to OPERATOR (Codex T58)",
       bool(hits) and any(any(ch.isdigit() for ch in h) for h in hits),
       "%s :: %s" % (changed, hits))

    # 🔴 Codex/Spark T58 counterexamples: non-citation short labels with digits MUST stay in
    # OPERATOR. Tokens like v2, x64, a1, file1, sec1 are ordinary identifiers whose edits are
    # substantive; an over-broad cite guard silenced them. The tightened regex requires an
    # internal `)(` structure, so these fail it and the digit rule catches them.
    for pair in [("v1", "v2"), ("x64", "x86"), ("a1", "a2"), ("file1", "file2")]:
        q_txt = "release the %s edition of the manual next quarter" % pair[0]
        s_txt = "release the %s edition of the manual next quarter" % pair[1]
        _c, hits2, _u = word_diff(q_txt, s_txt)
        ok("word_diff: label change %s vs %s still fires OPERATOR (T58 counter)"
           % (pair[0], pair[1]),
           bool(hits2), "%s -> hits=%s" % (pair, hits2))


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

    # --- "not downloaded" told apart from "invented" ---------------------------------------------
    from krokai.address import fold
    # 26 CFR is a real citation and there is no tax file in this corpus: nothing to check against.
    v, p, d, ad = fold("a sentence that is nowhere in this corpus at all", "NOT_FOUND", None, "",
                       ["26 CFR 1.61-1"], corpus, km, packs)
    ok("address: a miss whose source is NOT on disk becomes NO_SOURCE_ON_DISK",
       v == "NO_SOURCE_ON_DISK" and ad and ad["status"] == "ADDRESS_NOT_IN_CORPUS",
       "%s / %s" % (v, ad))
    ok("address: and it names what to download, and refuses to read as a pass",
       "26 CFR" in d and "not a pass" in d, d)

    # 🔴🔴 THE CONTROL THAT MATTERS MORE THAN THE FEATURE. If the cited source IS on disk and the
    # words are not in it, that is the fabrication shape - the verdict must NOT soften. Without this
    # assertion the new bucket is an escape hatch: cite something you do not have, get a shrug.
    v2, _p2, d2, _a2 = fold("a sentence that is nowhere in this corpus at all", "NOT_FOUND", None,
                            "", ["8 CFR 214.2"], corpus, km, packs)
    ok("address: a miss whose source IS on disk stays NOT_FOUND",
       v2 == "NOT_FOUND", v2)
    ok("address: and the report says the source was present, which is the stronger accusation",
       "IS on disk" in d2, d2)

    # And with no citation at all there is nothing to resolve, so nothing changes.
    v3, _p3, _d3, a3 = fold("a sentence that is nowhere in this corpus at all", "NOT_FOUND", None,
                            "", [], corpus, km, packs)
    ok("address: with no nearby citation a miss is still just a miss", v3 == "NOT_FOUND", v3)
    ok("address: and no address is invented for it", a3 is None, str(a3))


def suite_redact():
    from krokai.redact import self_test, gate, scan, SECRET_PATTERNS, PII_PATTERNS, FICTIONAL
    out = []
    ok("gate: all detectors have probes and no negative control fires",
       self_test(printer=out.append), " ".join(out))

    rc = gate([("brief", "key = sk-ant-api03-" + "A" * 40)], printer=lambda *_a: None)
    ok("gate: a secret blocks and has no override", rc == 2, str(rc))

    dob = "d.o.b. " + FICTIONAL["DATE_OF_BIRTH"]
    rc = gate([("brief", dob)], allow_pii=False, printer=lambda *_a: None)
    ok("gate: personal data blocks without --allow-pii", rc == 3, str(rc))
    rc = gate([("brief", dob)], allow_pii=True, printer=lambda *_a: None)
    ok("gate: --allow-pii lets personal data through", rc == 0, str(rc))

    rc = gate([("brief", "blocks a labelled date of birth unless you pass --allow-pii")],
              printer=lambda *_a: None)
    ok("gate: does NOT fire on its own documentation (the false positive that kills a gate)",
       rc == 0, str(rc))

    # --- a credential broken across a line, including inside a markdown quote block -------------
    # 🔴 Briefs are markdown and briefs wrap. The first version of the whole-text pass stripped
    # whitespace only, so a `> ` on the continuation line broke the pattern and the key went
    # through - traced by a reviewer, confirmed by probe, and the shape it names is the LIKELY one.
    _k = "sk-" + "ant-api03-" + "B" * 30
    for label, blob in [("plain wrap", _k[:10] + "\n" + _k[10:]),
                        ("wrapped inside a blockquote", _k[:10] + "\n> " + _k[10:]),
                        ("wrapped inside a list item", _k[:10] + "\n- " + _k[10:])]:
        ok("gate: a key wrapped across lines is caught (%s)" % label,
           "ANTHROPIC_KEY" in [k for s, k, _n, _l in scan(blob, "d") if s == "SECRET"], label)
    # The control: folding must not invent a secret out of ordinary prose.
    ok("gate: folding lines does not manufacture a secret from prose",
       not [k for s, k, _n, _l in scan("Authorization:\nBearer of this certificate shall be "
                                       "admitted to the hearing room.\n", "d") if s == "SECRET"])

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

    # --- extractor gains ported from the source project's hooks, 2026-08-10 ---------------------
    #
    # Every one of these is a class of quotation that returned ZERO candidates before the fix.

    # (a) multi-line blockquote paragraph. Each line is short; the norm only exists after the join.
    para = ("Under the memorandum,\n"
            "> Adjustment of status may be granted\n"
            "> in the discretion of the officer,\n"
            "> unless the applicant is inadmissible\n"
            "> under section 212(a) of the Act.\n"
            "so the officer decides.")
    ok("bank: multi-line blockquote is caught as one quotation",
       any("in the discretion of the officer" in q and "212(a) of the Act" in q
           for q in candidates(para)),
       "AOS measurement: 4-line wrapped norm returned 0 candidates before this fix")

    # (b) indented blockquote inside a list.
    indented = ("1. First rule.\n"
                "   > an applicant is eligible only if he establishes admissibility "
                "under section 212 of the Act and has maintained status.\n"
                "2. Second.")
    ok("bank: indented blockquote (nested in a list) is caught",
       any("only if he establishes admissibility" in q for q in candidates(indented)),
       "AOS measurement: 39 of 77 indented blockquotes were in the queue file itself")

    # (c) curly single quotes as delimiters. ASCII "'" is deliberately NOT a delimiter.
    curly = ("A commenter argued that ‘an applicant shall not be admitted unless he "
             "establishes admissibility to the officer under section 212 of the Act’.")
    ok("bank: a curly-single-quoted long span is caught",
       any("shall not be admitted" in q for q in candidates(curly)),
       "AOS measurement: quotations in ‘…’ returned zero candidates before this fix")

    # (d) straight quote with a soft-wrap newline inside it. Same span, unwrapped, was found.
    wrapped = ('Then the memo says "an applicant shall not be admitted to the United States\n'
               'unless he establishes eligibility under section 245(k) of the Act".')
    ok("bank: a straight-quoted span with a soft-wrap newline is caught",
       any("shall not be admitted" in q for q in candidates(wrapped)),
       "AOS execution proof: same quotation, one line → exit 2, wrapped → exit 0")

    # (e) the negative control: possessive `'s` must not be a quotation start.
    possessive = ("The court's decision was that " * 15)
    ok("bank: the ASCII apostrophe in a possessive is not a quotation delimiter",
       not candidates(possessive),
       "regression control: `court's` must not manufacture a quote out of prose")


def suite_upgrade(tmp):
    """The `krokai upgrade` subcommand — layout detection and changelog parsing.

    Added T58 after the panel (Codex + Spark 11 + Spark 12 + agy 36flash) named "zero tests"
    as the ship-blocking risk of the new module. These do not touch the network: they exercise
    the pure functions (`detect_layout`, `_editable_source_dir`, `_top_changelog_from_text`,
    `_has_git_meta`, `_remote_names_krokai`) and one out-of-process CLI smoke.
    """
    from krokai import upgrade
    import subprocess as _sp

    # 1. detect_layout returns a well-formed pair.
    layout, root = upgrade.detect_layout()
    ok("upgrade: detect_layout returns a (layout, root) tuple",
       isinstance(layout, str) and layout in ("pip", "git", "copy") and os.path.isabs(root),
       "layout=%r root=%r" % (layout, root))

    # 2. _editable_source_dir returns None for a non-editable install (the selftest environment).
    #    Ambient state: the running krokai either came from a wheel install (not editable) or
    #    from `python -m krokai selftest` inside the checkout (importlib.metadata may not find
    #    the distribution at all). Both cases return None; a positive True would surface a
    #    genuinely editable install and is fine to assert against.
    src = upgrade._editable_source_dir()
    ok("upgrade: _editable_source_dir returns None or an existing directory",
       src is None or os.path.isdir(src), "src=%r" % (src,))

    # 3. _has_git_meta on a synthetic tree.
    fake_repo = os.path.join(tmp, "fake-git")
    fake_worktree = os.path.join(tmp, "fake-worktree")
    fake_copy = os.path.join(tmp, "fake-copy")
    os.makedirs(os.path.join(fake_repo, ".git"), exist_ok=True)
    os.makedirs(fake_worktree, exist_ok=True)
    io.open(os.path.join(fake_worktree, ".git"), "w", encoding="utf-8").write(
        "gitdir: ../fake-repo/.git/worktrees/fake-worktree\n")
    os.makedirs(fake_copy, exist_ok=True)
    ok("upgrade: _has_git_meta recognises a .git DIRECTORY (regular clone)",
       upgrade._has_git_meta(fake_repo))
    ok("upgrade: _has_git_meta recognises a .git FILE (git worktree / submodule)",
       upgrade._has_git_meta(fake_worktree),
       "Codex T58 named this asymmetry; a worktree has a plain-text .git pointer")
    ok("upgrade: _has_git_meta returns False for a plain folder",
       not upgrade._has_git_meta(fake_copy))

    # 4. _remote_names_krokai — cannot test true-positive without a real remote configured,
    #    but the false-positive case (a plain folder with no git remote) must return False.
    ok("upgrade: _remote_names_krokai returns False for a non-repo folder",
       not upgrade._remote_names_krokai(fake_copy))

    # 5. _top_changelog_from_text parses the Keep-a-Changelog form used by this project.
    sample = ("# Changelog\n\n"
              "## [0.8.0] - 2026-08-10\n\n"
              "First and only body line for 0.8.0.\n\n"
              "## [0.7.7] - 2026-08-07\n\n"
              "Older entry that must NOT bleed into 0.8.0's body.\n")
    v, body = upgrade._top_changelog_from_text(sample)
    ok("upgrade: _top_changelog_from_text extracts the topmost version",
       v == "0.8.0", "got %r" % (v,))
    ok("upgrade: _top_changelog_from_text stops at the next heading",
       "0.8.0's body" not in body and "First and only" in body,
       "body=%r" % (body[:120],))

    # 6. The regex used by _CITE_TOKEN_RE via word_diff also enforces citation shape — cross-
    #    check that `v2` (Codex T58 counterexample) does NOT match the cite regex. This is not
    #    strictly upgrade.py, but it locks the tightened shape in a place a future edit would
    #    have to notice.
    from krokai.verify import _CITE_TOKEN_RE
    for label in ("v2", "x64", "a1", "file1", "test1", "sec1", "covid19"):
        ok("upgrade: _CITE_TOKEN_RE correctly REJECTS non-citation label %r" % label,
           not _CITE_TOKEN_RE.match(label))
    for cite in ("b)(16)(i", "(a)(1)", "(b)(16)(ii)"):
        ok("upgrade: _CITE_TOKEN_RE correctly ACCEPTS citation %r" % cite,
           _CITE_TOKEN_RE.match(cite) is not None)

    # 7. --dry-run smoke test via a real subprocess. Never touches the network for the layout
    #    decision, but WILL try pypi_latest — if the CI machine is offline that field prints
    #    "unreachable" without failing the run, which is precisely the design.
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONPATH=pkg_root, PYTHONIOENCODING="utf-8")
    try:
        r = _sp.run([sys.executable, "-m", "krokai", "upgrade", "--dry-run"],
                    stdout=_sp.PIPE, stderr=_sp.PIPE, env=env, timeout=60)
        out = (r.stdout or b"").decode("utf-8", "replace")
    except Exception as exc:
        r, out = None, "EXC: %s" % exc
    ok("upgrade: `krokai upgrade --dry-run` exits 0",
       r is not None and r.returncode == 0, "rc=%s" % (r.returncode if r else "n/a"))
    ok("upgrade: --dry-run prints the layout and root BEFORE any command",
       "current install" in out and "layout" in out and "root" in out,
       "out[:200]=%r" % out[:200])
    ok("upgrade: --dry-run prints the command that WOULD run",
       "WOULD run" in out, "out[:400]=%r" % out[:400])
    ok("upgrade: --dry-run never claims 'updated successfully'",
       "updated successfully" not in out.lower())


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

    # --- the surname reaches the GATE, not merely the detector -----------------------------------
    # 🔴 This one runs the CLI in a subprocess on purpose. The defect it locks was invisible to
    # every in-process probe for five releases: `name_patterns()` was correct, `scan()` accepted
    # surnames, the documentation named `casefile.json` as the place to configure them - and no
    # caller passed any, because `gate()` had no parameter and `config` had no key. Every existing
    # test called `scan(..., surnames=(...))` directly, so the probe supplied what the product did
    # not, and verified only itself. An outside reviewer found it by tracing call sites.
    #
    # So the assertion is end to end: a real config file, a real brief, the real command, the exit
    # code a user would see. Nothing in this block may import `redact`.
    import subprocess as _sp
    gate_root = os.path.join(tmp, "gate-matter")
    os.makedirs(gate_root, exist_ok=True)
    cfgdata = dict(TEMPLATE)
    cfgdata["surnames"] = ["Kowalczyk"]
    _j.dump(cfgdata, io.open(os.path.join(gate_root, "casefile.json"), "w", encoding="utf-8"))
    brief_path = os.path.join(gate_root, "brief.md")
    io.open(brief_path, "w", encoding="utf-8").write(
        "Counsel for Maria Kowalczyk asks the reviewer to confirm the statute text.\n")
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONPATH=pkg_root, PYTHONIOENCODING="utf-8")

    def _gate(cwd, path):
        r = _sp.run([sys.executable, "-m", "krokai", "gate", path], cwd=cwd, env=env,
                    stdout=_sp.PIPE, stderr=_sp.PIPE, timeout=120)
        return r.returncode, (r.stdout or b"").decode("utf-8", "replace")

    rc, outtxt = _gate(gate_root, brief_path)
    ok("config: a CONFIGURED surname blocks the real `krokai gate`, end to end",
       rc == 3 and "SURNAME" in outtxt, "rc=%s" % rc)

    # The negative control, and it is the more important half: the same brief with no surname
    # configured must NOT block - otherwise the check would pass by blocking everything.
    plain_root = os.path.join(tmp, "gate-plain")
    os.makedirs(plain_root, exist_ok=True)
    _j.dump(TEMPLATE, io.open(os.path.join(plain_root, "casefile.json"), "w", encoding="utf-8"))
    rc2, out2 = _gate(plain_root, brief_path)
    ok("config: with no surname configured the same brief passes", rc2 == 0, "rc=%s" % rc2)
    ok("config: and the gate SAYS no surname was looked for, instead of printing `clean`",
       "no surnames configured" in out2, out2.strip()[-120:])


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
    from krokai.verdicts import UNCHECKABLE
    ok("verdicts: dangerous and clean do not overlap",
       not (set(DANGEROUS) & set(CLEAN)), str(set(DANGEROUS) & set(CLEAN)))
    ok("verdicts: UNCHECKABLE overlaps neither - it is not a pass and not an accusation",
       not (set(UNCHECKABLE) & (set(DANGEROUS) | set(CLEAN))), str(UNCHECKABLE))
    allbuckets = set(DANGEROUS) | set(CLEAN) | set(UNCHECKABLE)
    ok("verdicts: every verdict is classified somewhere",
       set(ORDER) == allbuckets, str(set(ORDER) ^ allbuckets))

    # 🔴 The EXIT CODE is the surface a hook and a CI job read, and it used to see only the
    # dangerous count. `print_summary` returns BOTH numbers now; asserting the arity is what stops
    # a later refactor quietly dropping the second one back to invisible.
    import inspect as _insp
    from krokai import run as _run
    _src = _insp.getsource(_run.print_summary)
    ok("run: print_summary reports the uncheckable count as well as the dangerous one",
       "return ab_bad, ab_unknown" in _src, _src.strip().splitlines()[-1])
    _cli = _insp.getsource(__import__("krokai.cli", fromlist=["cmd_check"]).cmd_check)
    ok("cli: --strict fails on an uncheckable item too, with its own code",
       "bad, unknown = print_summary" in _cli and "return 4" in _cli)


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


def suite_pipeline_samples():
    """Every citation shape that declares an address must be REACHABLE through the real pipeline.

    🔴 Ported from a measured incident in a sister project: an address kind was added to the key
    parser, verified by calling the parser directly, and recorded as fixed - while the recogniser
    that feeds the parser never matched that citation style, so the key existed and was never once
    created in a live run. A probe into a function cannot see a hole in the pipeline that feeds
    it. So every address-bearing shape carries a `sample` sentence, and this suite pushes each one
    through find_positions -> keys - the same two steps the scanner uses - and requires the
    declared kind (or its alias target) to come out the other end. A shape without a sample fails
    here by design: that is the coverage assertion, not an inconvenience.
    """
    from krokai.citations import load_packs, available_packs
    packs = load_packs(available_packs())
    for p in packs.packs:
        alias_target = {k: v.get("to_kind") for k, v in (p.aliases or {}).items()
                        if isinstance(v, dict)}
        for sh in p.shapes:
            a = sh.get("address")
            if not a:
                continue
            kind = a["kind"]
            sample = sh.get("sample")
            if not ok("packs: %s shape %r carries a pipeline sample" % (p.id, kind), bool(sample)):
                continue
            found = [t for t, _pos in packs.find_positions(sample)]
            got = {k[0] for k in packs.keys(found)}
            want = {kind, alias_target.get(kind)} - {None}
            ok("packs: %s sample for %r survives find->keys, the scanner's own path"
               % (p.id, kind), bool(found) and bool(got & want),
               "found=%r got=%r want=%r" % (found[:3], sorted(got), sorted(want)))


def suite_ported(tmp):
    """The 2026-08-03 port round: every check here is a defect CONFIRMED BY PROBE that day,
    either in this tree or in the sister project this toolkit was extracted from. Deleting any of
    the round's fixes must turn at least one of these red."""
    from krokai.citations import load_packs
    from krokai.readers import _choose_extraction
    from krokai.bank import in_bank
    from krokai.redact import scan, FICTIONAL
    from krokai.consult import classify_url, agency_labels
    from krokai.run import mixed_provisions

    packs = load_packs(["us-federal", "us-immigration", "us-tax"])

    # --- filename matching: number tokens, not substrings ---------------------------------------
    # Measured cost of the substring in the sister project: a 7 KB EOIR twin shown as the primary
    # source for the most-cited provision of the filing, while the real 205 KB file sat beside it.
    ok("citations: part 245 does not match inside 1245",
       not packs.file_matches(("cfr", "8", "245"), "8CFR-1245.2-EOIR.xml", ""))
    ok("citations: the real part-245 file still matches",
       packs.file_matches(("cfr", "8", "245"), "8CFR-part-245-ecfr-2026-07-01.xml", ""))
    ok("citations: a dotted section name still matches its part",
       packs.file_matches(("cfr", "8", "214"), "8CFR-214.2-f-16.xml", ""))
    ok("citations: part 245 does not claim the part-245a file",
       not packs.file_matches(("cfr", "8", "245"), "8cfr-part-245a-ecfr.xml", ""))
    ok("citations: part 245a still claims its own file",
       packs.file_matches(("cfr", "8", "245a"), "8cfr-part-245a-ecfr.xml", ""))
    ok("citations: usc 255 does not match inside 1255",
       not packs.file_matches(("usc", "8", "255"), "8USC-1255-uscode.xml", ""))
    ok("citations: a fully glued name still matches weakly",
       packs.file_matches(("cfr", "8", "214"), "8cfr_214.xml", ""))
    # The dashed-needle defect was pre-existing and invisible: the captured `602-0199` kept its
    # dash, the flattened filename lost its own, and the name rule had never fired once.
    ok("citations: a dashed memorandum number meets a dashed filename at all",
       packs.file_matches(("pmnum", "602-0199"), "PM-602-0199-AdjustmentOfStatus.md", ""))
    ok("citations: ...and does not match inside a longer digit run",
       not packs.file_matches(("pmnum", "602-0199"), "PM-1602-01991-notes.md", ""))

    # --- a filled PDF form reads as a blank one -------------------------------------------------
    # 🔴 The values of a fillable PDF live in /AcroForm /Fields as /V, not in the page content, so
    # a completed agency form and an empty one produce the same text layer. Measured in the sister
    # project on the actually-filed I-485: 765 fields, 455 filled, none of them extractable.
    # A real form is built here rather than mocked, because the whole defect is about what the
    # library actually returns for a real file.
    from krokai.readers import read_pdf, _form_values, no_text_layer
    try:
        import fitz as _fitz
    except Exception:
        ok("readers: (skipped) PyMuPDF not installed, cannot build a form fixture", True)
    else:
        fpath = os.path.join(tmp, "filled-form.pdf")
        doc = _fitz.open()
        pg = doc.new_page()
        pg.insert_text((72, 90), "Part 8. Item 16. Have you EVER worked without authorization?")
        for nm, val in (("Pt8Line16_YesNo", "No"),
                        ("Pt1Line1a_FamilyName", "Kowalczyk"),
                        ("Pt2Line3_MiddleName", "")):        # the blank one must NOT be invented
            wd = _fitz.Widget()
            wd.field_name = nm
            wd.field_type = _fitz.PDF_WIDGET_TYPE_TEXT
            wd.rect = _fitz.Rect(400, 150, 540, 172)
            wd.field_value = val
            pg.add_widget(wd)
        doc.save(fpath)
        doc.close()

        layer = ""
        try:
            import pypdf as _pypdf
            layer = "\n".join((p.extract_text() or "") for p in _pypdf.PdfReader(fpath).pages)
        except Exception:
            pass
        ok("readers: the control holds - the ANSWER is genuinely absent from the text layer",
           "Kowalczyk" not in layer and "worked without authorization" in layer,
           "len(layer)=%d" % len(layer))

        full = read_pdf(fpath, None)
        ok("readers: read_pdf recovers a FILLED form field value", "Kowalczyk" in full)
        ok("readers: and keeps the item number, which is the only trustworthy pairing",
           "Pt8Line16_YesNo" in full)
        ok("readers: an EMPTY field is not invented into the corpus",
           "Pt2Line3_MiddleName" not in full)

        # 🔴 `/Off` with the slash is an unticked checkbox; `Off` without it is a word somebody
        # typed into a text field, and dropping it deleted a real answer. Reviewer-traced.
        opath = os.path.join(tmp, "off-form.pdf")
        odoc = _fitz.open()
        opg = odoc.new_page()
        for nm, val in (("Mode_Text", "Off"), ("Name_Text", "Kowalczyk")):
            wd = _fitz.Widget()
            wd.field_name = nm
            wd.field_type = _fitz.PDF_WIDGET_TYPE_TEXT
            wd.rect = _fitz.Rect(100, 100, 300, 120)
            wd.field_value = val
            opg.add_widget(wd)
        odoc.save(opath)
        odoc.close()
        ok("readers: a TEXT field whose value is the word 'Off' is kept",
           "Mode_Text" in _form_values(opath), _form_values(opath).replace("\n", " | "))
        ok("readers: a form PDF is not diagnosed as a scan needing OCR",
           no_text_layer(fpath) is False)
        ok("readers: a PDF with no form at all yields no field text",
           _form_values(os.path.join(tmp, "does-not-exist.pdf")) == "")

    # --- the two extension tuples must agree -----------------------------------------------------
    # 🔴 `.docx` sat in EXTRACTED_EXT and not in DEFAULT_EXT for a whole release, so `read_docx` -
    # written, tested, documented at length - was never reached: `walk()` yielded no `.docx`. A
    # decision saved as Word was invisible and every quotation of it read as fabricated. Derived,
    # not copied, so adding a format to one tuple forces the question about the other.
    from krokai.corpus import DEFAULT_EXT, EXTRACTED_EXT
    orphans = [e for e in EXTRACTED_EXT if e not in DEFAULT_EXT]
    ok("corpus: no format is declared EXTRACTED without being walked at all", not orphans,
       str(orphans))

    # --- extraction choice: truncation by characters, splitting by tokens -----------------------
    whole = ("word " * 5000).strip()
    split = ("wo rd " * 5000).strip()
    trunc = ("word " * 50).strip()
    ok("readers: a truncated-but-alive primary loses to a complete alternate",
       _choose_extraction(trunc, whole)[0] is whole)
    ok("readers: a word-splitting primary loses to a clean alternate",
       _choose_extraction(split, whole)[0] is whole)
    ok("readers: a complete primary beats a word-splitting alternate",
       _choose_extraction(whole, split)[0] is whole)
    ok("readers: equal extractions keep the primary", _choose_extraction(whole, whole)[0] is whole)
    ok("readers: a dead primary loses", _choose_extraction("x", whole)[0] is whole)
    # 🔴 The two findings an outside review confirmed by execution on 2026-08-03: the split rule
    # used to fire in the WRONG DIRECTION (a truncated ALTERNATE beat a complete primary, because
    # "more tokens" read as "split words"), and a 45 % loss sat under a lone 2x threshold.
    trunc_alt = ("word " * 2600).strip()
    ok("readers: a complete primary beats a truncated ALTERNATE (direction control)",
       _choose_extraction(whole, trunc_alt)[0] is whole)
    p45 = ("word " * 2750).strip()
    ok("readers: a 45%-loss primary loses to the complete alternate",
       _choose_extraction(p45, whole)[0] is whole)
    # A reviewer's counter-case for the 1.01 hair trigger: two line-break-hyphen artefacts must
    # not hand the round to an alternate that is missing a paragraph.
    near_complete = ("word " * 98).strip() + " regu lation stat ute"          # 102 tokens
    short_alt = ("word " * 100).strip()[:-20]                                 # ~100 tokens, shorter
    ok("readers: two split-word artefacts do not flip the choice to a shorter text",
       _choose_extraction(near_complete, short_alt)[0] is near_complete)

    # --- the bank check compares the WHOLE quotation --------------------------------------------
    shared = "The Secretary may in his discretion and under such regulations as he may prescribe "
    qa = shared + "adjust the status of an alien admitted or paroled."
    qb = shared + "deny the application without prejudice to renewal."
    bank = "### S-1\n\n> " + qa + "\n"
    ok("bank: a banked quotation is recognised", in_bank(qa, bank))
    ok("bank: a DIFFERENT quotation sharing the first 60 characters is not",
       not in_bank(qb, bank))
    cut = qa.rfind(" ", 0, 60)
    wrapped = "### S-2\n\n> " + qa[:cut] + "\n> " + qa[cut + 1:] + "\n"
    ok("bank: a quotation wrapped across blockquote lines is still recognised",
       in_bank(qa, wrapped))
    # 🔴 A TRUNCATED variant of a banked quotation is a substring of the full one - under
    # containment it read as banked, which is exactly the cut-off-condition shape this toolkit
    # exists to catch. Reviewer-traced, equality-fixed.
    ok("bank: a truncated variant of a banked quotation is NOT banked",
       not in_bank(qa[:len(qa) - 18], bank))
    ok("bank: a short boilerplate fragment is NOT banked",
       not in_bank("in his discretion and under such regulations", bank))

    # --- grouped identifiers reach the gate ------------------------------------------------------
    # 🔴 These five fixtures used to be the applicant's REAL numbers, copied here out of the sister
    # project's leak report so that the probe would exercise "the exact shape that got through".
    # They are now built from `redact.FICTIONAL`, which is the only place in this tree allowed to
    # hold an identifier-shaped literal, and `suite_no_real_identifiers` enforces that.
    #
    # Two ways this block leaked, not one: the values sat in the file, AND the failure detail
    # printed the whole probe line to the console. A test that prints its fixture is a publishing
    # channel whenever it goes red - so the detail names the shape and never the line.
    for line, kind, shape in [
            (FICTIONAL["ALIEN_NUMBER"], "ALIEN_NUMBER", "A-nnn-nnn-nnn"),
            (FICTIONAL["ALIEN_NUMBER_HASH"], "ALIEN_NUMBER", "A# nnnnnnnnn"),
            (FICTIONAL["ALIEN_NUMBER_LOWER"], "ALIEN_NUMBER", "a-nnnnnnnnn"),
            (FICTIONAL["USCIS_RECEIPT"], "USCIS_RECEIPT", "MSC-nnn-nnn-nnn-n"),
            (FICTIONAL["USCIS_RECEIPT_IOE"], "USCIS_RECEIPT", "IOE-nnnn-nnn-nnn"),
            (FICTIONAL["USCIS_RECEIPT_FUSED"], "USCIS_RECEIPT", "MSCnnnnnnnnnn")]:
        sentence = "the notice shows %s today" % line
        ok("redact: grouped form is caught: %s (%s)" % (kind, shape),
           kind in [k for _s, k, _n, _l in scan(sentence)], shape)
    ok("redact: a lettered unit number (Apt A-1) is caught",
       "UNIT_NUMBER" in [k for _s, k, _n, _l in scan("at 732 S Spring St Apt A-1 today")])
    ok("redact: a single-capital unit (Suite B) is caught",
       "UNIT_NUMBER" in [k for _s, k, _n, _l in scan("offices at Suite B downtown")])
    ok("redact: all-caps prose is NOT a unit (UNIT OF MEASUREMENT)",
       "UNIT_NUMBER" not in [k for _s, k, _n, _l in scan("THE UNIT OF MEASUREMENT IS THE HOUR")])

    # --- the lookalike detector knows configured NAMES, not only gov/mil labels -----------------
    g = {"primary": [".gov", ".mil"] + packs.official_domains,
         "snapshot": [], "nonauthoritative": []}
    ok("consult: the exact agency name in a foreign zone is flagged",
       classify_url("https://www.uscis.com/i-485", g) == "lookalike")
    ok("consult: a three-letter agency name still counts (irs.com is live and commercial)",
       classify_url("https://irs.com/refund", g) == "lookalike")
    ok("consult: an agency name as a subdomain of a stranger is flagged",
       classify_url("https://uscis.phishing.example/form", g) == "lookalike")
    ok("consult: the real agency stays primary",
       classify_url("https://www.uscis.gov/i-485", g) == "primary")
    ok("consult: names do not fire on unrelated hosts",
       classify_url("https://status.com/page", g) == "other" and
       classify_url("https://www.milano.it/", g) == "other")
    ok("consult: two-letter fragments are never derived as names",
       "us" not in agency_labels(packs.official_domains))
    ok("consult: a www-prefixed entry still teaches its name",
       "uscis" in agency_labels(["www.uscis.gov"]))
    from krokai.consult import gov_lookalike
    ok("consult: an upper-case host does not slip a DIRECT gov_lookalike call",
       gov_lookalike("USCIS.COM", ["uscis.gov"]))
    ok("citations: a dotted no-separator name cannot hand part 245a to part 245",
       not packs.file_matches(("cfr", "8", "245"), "8cfr245a.xml", ""))
    # Tested as an ABSENCE, the same discipline as the cut features: `ice` is an English word, a
    # whole-label match on it would flag a commodities exchange, and the pack left it out on
    # purpose. If it reappears, this fails and the reasoning in the pack file gets re-read.
    ok("packs: ice.gov stays out of official_domains on purpose",
       "ice.gov" not in packs.official_domains)
    ok("packs: the immigration pack teaches uscis.gov",
       "uscis.gov" in packs.official_domains)

    # --- one provision, two texts ----------------------------------------------------------------
    rows = [
        {"verdict": "VERIFIED", "near": ["8 CFR 214.2(f)(16)"], "sites": [], "quote": "full"},
        {"verdict": "TRUNCATED_CONDITION", "near": ["8 CFR 214.2(f)(16)"], "sites": [],
         "quote": "cut"},
        {"verdict": "VERIFIED", "near": ["8 CFR 103.2(b)(8)"], "sites": [], "quote": "clean"},
    ]
    mixed = mixed_provisions(rows, packs)
    ok("run: the same provision quoted clean AND flagged is paired", len(mixed) == 1,
       repr([m[0] for m in mixed]))
    ok("run: a provision quoted only clean is not accused",
       all("103" not in m[0] for m in mixed))

    # --- init writes the assistant block, idempotently -------------------------------------------
    from krokai.cli import write_claude_block, CLAUDE_BEGIN
    root = os.path.join(tmp, "matter")
    os.makedirs(root, exist_ok=True)
    io.open(os.path.join(root, "CLAUDE.md"), "w", encoding="utf-8").write(
        "# My matter\n\nHouse rules stay.\n")
    target, action1 = write_claude_block(root)
    text1 = io.open(target, encoding="utf-8").read()
    ok("cli: the assistant block is appended, not replacing the existing file",
       "House rules stay." in text1 and CLAUDE_BEGIN in text1, action1)
    ok("cli: the block is rendered with a real command, no placeholder left",
       "{KROKAI}" not in text1 and 'python "' in text1)
    _t, action2 = write_claude_block(root)
    text2 = io.open(target, encoding="utf-8").read()
    ok("cli: a second run refreshes in place - exactly one block",
       text2.count(CLAUDE_BEGIN) == 1 and "House rules stay." in text2, action2)
    ok("cli: the rendered block does not carry the template's meta-comment",
       "Paste this into" not in text2)

    # --- write_claude_block refuses the states it cannot edit safely -----------------------------
    # All three vectors were traced by an outside reviewer from the quoted code, before a client
    # paid for any of them: an orphaned marker would have deleted the user's text under the word
    # "refreshed"; a non-UTF-8 file would have been transcoded wholesale to U+FFFD; a CRLF file
    # would have flipped to LF end to end for a three-line change.
    orph = os.path.join(tmp, "orphan-matter")
    os.makedirs(orph, exist_ok=True)
    orphan_text = "# Matter\n\nKeep me.\n\n" + CLAUDE_BEGIN + "\nhand-damaged block, END deleted\n"
    io.open(os.path.join(orph, "CLAUDE.md"), "w", encoding="utf-8").write(orphan_text)
    try:
        write_claude_block(orph)
        ok("cli: an orphaned marker is refused, not repaired", False)
    except SystemExit:
        after = io.open(os.path.join(orph, "CLAUDE.md"), encoding="utf-8").read()
        ok("cli: an orphaned marker is refused, not repaired", after == orphan_text)

    enc = os.path.join(tmp, "cp1251-matter")
    os.makedirs(enc, exist_ok=True)
    raw1251 = ("# Дело\n\nРукописный текст клиента.\n").encode("cp1251")
    open(os.path.join(enc, "CLAUDE.md"), "wb").write(raw1251)
    try:
        write_claude_block(enc)
        ok("cli: a non-UTF-8 CLAUDE.md is refused, never transcoded", False)
    except SystemExit:
        ok("cli: a non-UTF-8 CLAUDE.md is refused, never transcoded",
           open(os.path.join(enc, "CLAUDE.md"), "rb").read() == raw1251)

    crlf = os.path.join(tmp, "crlf-matter")
    os.makedirs(crlf, exist_ok=True)
    open(os.path.join(crlf, "CLAUDE.md"), "wb").write(b"# Matter\r\n\r\nKeep.\r\n")
    write_claude_block(crlf)
    out_bytes = open(os.path.join(crlf, "CLAUDE.md"), "rb").read()
    ok("cli: a CRLF file keeps its line endings after the block is added",
       b"\r\n" in out_bytes and b"Keep." in out_bytes and
       CLAUDE_BEGIN.encode() in out_bytes and b"\n\n" not in out_bytes.replace(b"\r\n", b"\r"),
       "len=%d" % len(out_bytes))
    write_claude_block(crlf)
    out2 = open(os.path.join(crlf, "CLAUDE.md"), "rb").read()
    ok("cli: ...and a refresh on the CRLF file stays a single block",
       out2.count(CLAUDE_BEGIN.encode()) == 1)

    # --- the documented invocation actually runs -------------------------------------------------
    # 🔴 `python <clone>/krokai <cmd>` was in the install document from the first release and had
    # NEVER worked: directory-run gives `__main__.py` no parent package, and the relative import
    # died. Found 2026-08-03 by executing the document end to end in a scratch folder - reading it
    # had proven nothing. This is the regression lock: run the package DIRECTORY from a foreign
    # working directory, exactly as the document tells the client's assistant to.
    import subprocess
    pkg = os.path.dirname(os.path.abspath(
        __import__("krokai.cli", fromlist=["main"]).__file__))
    r = subprocess.run([sys.executable, pkg, "--version"], cwd=root,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    ok("cli: directory-run (`python <clone>/krokai`) works from a foreign cwd",
       r.returncode == 0 and b"krokai" in r.stdout,
       (r.stderr or b"").decode("utf-8", "replace")[:160])


def suite_hooks_stdin(tmp):
    """🔴 THE GUARD WAS DEAD ON ARRIVAL FOR ANY PAYLOAD CONTAINING A NON-ASCII CHARACTER.

    Measured 2026-08-05, one variable at a time, calling the hook exactly as the harness does -
    a subprocess with JSON bytes on stdin:

        UTF-8 bytes, console code page cp1251     -> exit 0, silent
        the same bytes with PYTHONIOENCODING set  -> exit 2, fires
        ASCII path, ASCII matter, curly quotes    -> exit 0, silent

    The trigger is not an exotic path: it is U+201C, which is what a model emits and what every
    scraped source contains. `_bootstrap` forced UTF-8 on stderr and stdout on day one - because
    mojibake going OUT is visible - and never on stdin, where the identical defect is invisible.

    This test runs the real hook in a real subprocess with the environment variable REMOVED, which
    is the only arrangement that can catch it. An in-process call cannot: the test runner's own
    stdin is not the hook's.
    """
    import json
    import shutil
    import subprocess
    root = os.path.join(tmp, "hookmatter")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "drafts"))
    os.makedirs(os.path.join(root, "sources"))
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps(
        {"bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md",
         "guard_watch": ["drafts"], "source_dirs": ["sources"]}))
    io.open(os.path.join(root, "QUOTE-BANK.md"), "w", encoding="utf-8").write(
        "# Quote bank\n\n### 1\n\n> a placeholder entry matching nothing in this suite\n")

    # data_dir(), not `<pkg>/../hooks`: `site-packages/hooks` never exists. See _datadir.py.
    hook = os.path.join(data_dir("hooks"), "quote_guard.py")
    if not os.path.exists(hook):
        ok("hooks: quote_guard.py is present", False, hook)
        return
    quote = ("The Attorney General may in his discretion and under such regulations as he may "
             "prescribe adjust the status of an alien who was inspected and admitted or paroled")

    def call(fname, body):
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        ev = {"tool_name": "Edit", "tool_input": {
            "file_path": os.path.join(root, "drafts", fname), "new_string": body}}
        p = subprocess.run([sys.executable, hook],
                           input=json.dumps(ev, ensure_ascii=False).encode("utf-8"),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        return p.returncode

    ok("hooks: UTF-8 stdin with curly quotes in the quotation FIRES (was silent)",
       call("motion.md", u'As provided: \u201c%s\u201d.' % quote) == 2)
    ok("hooks: a non-ASCII path and guillemets fire too",
       call(u"\u041c\u041e\u0422\u0418\u0412.md", u'\u00ab%s\u00bb' % quote) == 2)
    ok("hooks: CONTROL a pure-ASCII payload still fires",
       call("plain.md", 'As provided: "%s".' % quote) == 2)
    log = os.path.join(root, ".krokai", "quote_guard.log")
    ok("hooks: the guard keeps a log, so silence is observable", os.path.exists(log))
    call("quiet.md", "A short note with no quotation of law in it at all, only prose.")
    body = io.open(log, encoding="utf-8").read()
    ok("hooks: a QUIET turn is logged with its reason too",
       "no quotation candidates" in body, body.strip().splitlines()[-1][:70])
    memo = os.path.join(root, ".krokai", "quote_guard_seen.json")
    ok("hooks: the memo lives in the matter, not in the machine's temp directory",
       os.path.exists(memo))
    entries = json.load(io.open(memo, encoding="utf-8"))
    ok("hooks: the memo records WHEN, so it can expire",
       isinstance(entries, dict) and all(isinstance(v, (int, float)) for v in entries.values()),
       "%d entries" % len(entries))
    _bq = _hook_module("bank_queue")
    import inspect as _i
    ok("hooks: bank_queue screens this toolkit's own output out of its corpus",
       "sentinel=SENTINELS" in _i.getsource(_bq.main))


def suite_sidecar_not_a_source(tmp):
    """🔴 A sidecar this tool writes must never be indexed as primary law.

    Measured 2026-08-05: `krokai sidecar` wrote a `.md` next to every PDF inside a sources folder,
    `Corpus` walked `.md`, and the file was indexed as law. The tool's own warning header - "Page
    breaks, signatures and exact layout exist only there" - came back as a CLEAN verdict citing the
    sidecar. The sister project measured the same shape at scale: 66 of 269 corpus files were its
    own sidecars.

    The stamp is in the CONTENT, never a rule about the name: excluding `.text.md` by extension
    would have thrown out genuinely downloaded decisions that use it.
    """
    from krokai.sidecar import HEADER, SUFFIX, _current
    from krokai.run import SENTINELS
    from krokai.readers import EXTRACTOR_VERSION
    ok("sidecar: the header carries the tool-output sentinel",
       SENTINELS[0] in HEADER, SENTINELS[0])
    ok("sidecar: and the extractor version, so a repair invalidates old files",
       "{extractor}" in HEADER)
    d = os.path.join(tmp, "sidecarfresh")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "a.pdf")
    dst = os.path.join(d, "a" + SUFFIX)
    io.open(src, "w", encoding="utf-8").write("x")
    io.open(dst, "w", encoding="utf-8").write("extractor: %s\nbody" % EXTRACTOR_VERSION)
    ok("sidecar: a current file is recognised as current", _current(dst, src))
    io.open(dst, "w", encoding="utf-8").write("extractor: 0\nbody")
    ok("sidecar: an older extractor forces a rebuild even when mtime says current",
       not _current(dst, src))


def suite_missing_engine_is_loud(tmp):
    """A format whose engine is absent must RAISE, never return "".

    🔴 THIS IS THE DEFECT THE PACKAGING ROUND ALMOST SHIPPED. Every third-party import here is
    optional on purpose, so `pip install krokai` works on a machine where nothing else may be
    installed. But `read_pdf` caught `Exception`, which swallows `ImportError` next to a corrupt
    file, so a bare install handed back "" - and the checker then reported the document as examined
    with zero quotations found. Measured on the real 0.7.6 wheel in an empty venv before the fix:
    `read_pdf(sample.pdf)` -> `''`, `read_docx` -> `''`, `read_any` -> `''`, no warning anywhere.

    Both external reviewers flagged `dependencies = []` in the same round and both were right; the
    packaging note that called it safe was wrong. Optional must mean degraded LOUDLY.

    An empty text layer stays a legitimate answer - a scanned statute really does read as "" - so
    the test below also pins that the distinction is drawn at the IMPORT, not at the result.
    """
    import builtins
    from krokai.readers import MissingReader
    import krokai.readers as R

    pdf = os.path.join(tmp, "engine-probe.pdf")
    io.open(pdf, "wb").write(b"%PDF-1.4" + b"\n")
    docx = os.path.join(tmp, "engine-probe.docx")
    io.open(docx, "wb").write(b"PK" + bytes([3, 4]))

    real_import = builtins.__import__

    def hide(names):
        def fake(name, *a, **kw):
            if name in names:
                raise ImportError("hidden by the self-test: %s" % name)
            return real_import(name, *a, **kw)
        return fake

    builtins.__import__ = hide({"pypdf", "fitz"})
    try:
        try:
            R.read_pdf(pdf)
            ok("readers: a PDF with no engine installed raises rather than returning ''", False,
               "returned quietly")
        except MissingReader as e:
            msg = str(e)
            ok("readers: a PDF with no engine installed raises rather than returning ''", True)
            ok("readers: the message says nothing was examined, not that nothing was found",
               "nothing was examined" in msg, msg.splitlines()[1] if len(msg.splitlines()) > 1 else msg)
            ok("readers: the message names the exact install command",
               "krokai[pdf]" in msg, msg.splitlines()[-1])
    finally:
        builtins.__import__ = real_import

    builtins.__import__ = hide({"mammoth"})
    try:
        try:
            R.read_docx(docx)
            ok("readers: a .docx with no engine installed raises", False, "returned quietly")
        except MissingReader as e:
            ok("readers: a .docx with no engine installed raises", True)
            ok("readers: the .docx message names the exact install command",
               "krokai[docx]" in str(e), str(e).splitlines()[-1])
    finally:
        builtins.__import__ = real_import

    # 🔴 The control, and it must be GATED on the engines really being there, not assume it.
    #
    # This assertion caught itself. Run from a venv installed with `--no-deps`, pypdf and fitz are
    # genuinely absent, `read_pdf` correctly raised, and the control went red - reporting a defect
    # in the fix when the real fault was its own premise. A control arm whose precondition is never
    # checked measures the environment rather than the code.
    #
    # What it guards is worth the care: with an engine present, an unreadable or image-only PDF must
    # still come back "" and must NOT raise, or every scanned statute in a corpus becomes a crash.
    engines = R.engines_available()
    if engines.get("pypdf") or engines.get("PyMuPDF"):
        try:
            out = R.read_pdf(pdf)
            ok("readers: CONTROL - engine present, unreadable PDF returns '' and does not raise",
               out == "", repr(out)[:60])
        except MissingReader:
            ok("readers: CONTROL - engine present, unreadable PDF returns '' and does not raise",
               False, "raised MissingReader while an engine was importable")
    else:
        print("note: readers CONTROL skipped - no PDF engine in this environment, so its "
              "'engine present' premise does not hold. Run it where krokai[pdf] is installed.")


def suite_readers_signature():
    """🔴 A signature field is not an answer, and its value is not a string.

    The AcroForm reader added in 0.6.0 fixed a real defect - a filled USCIS form reading as blank -
    and opened a new one: every govinfo PDF is digitally signed, `/Sig`'s `/V` is a DICTIONARY
    holding the PKCS#7 certificate chain, and `str()` of it went into the corpus. Measured here:
    4 267 characters of certificate, of which a phrase came back VERIFIED as law. The sister
    project measured 454 KB across 16 % of its search index.
    """
    import inspect
    from krokai import readers as R
    src = inspect.getsource(R._form_values)
    ok("readers: a /Sig field is skipped by type", '"/Sig"' in src and "continue" in src)
    ok("readers: and a non-scalar value is skipped whatever its type says",
       "isinstance(v, (str, int, float))" in src)
    ok("readers: the text-layer test has a PER-PAGE rate, not only a total",
       R.MIN_CHARS_PER_PAGE > 0 and "MIN_CHARS_PER_PAGE" in inspect.getsource(R.no_text_layer),
       "%d chars/page from %d pages up" % (R.MIN_CHARS_PER_PAGE, R.PAGES_BEFORE_RATE_APPLIES))


def suite_fetch(tmp):
    """The download layer: trust, refusal, revisions - and no model anywhere in the path."""
    from krokai import fetch as F
    from krokai.citations import load_packs
    packs = load_packs(["us-immigration", "us-federal"])

    for url, want in [
        ("https://www.ecfr.gov/api/versioner/v1/full/2026-08-01/title-8.xml?part=245", "primary"),
        ("https://uscisdhs-gov.us/policy.pdf", "lookalike"),
        ("https://www.uscis.com/policy-manual", "lookalike"),
        ("https://pastebin.com/raw/aBcDeFgH", "unknown"),
        ("https://files.random-host.ru/8cfr.txt", "unknown"),
        ("https://www.law.cornell.edu/cfr/text/8/245.1", "nonauthoritative"),
        # 🔴🔴 A DATED-EDITION MARKER IS A QUALIFIER, NEVER A CREDENTIAL. The snapshot list holds
        # path and query fragments - `/annual/`, `?date=` - and they were matched as substrings of
        # the WHOLE URL, ahead of every host test, so any host serving such a path was labelled
        # "OFFICIAL BUT DATED" and downloaded with no `--allow-unknown-source`. All three channels
        # of the round-21 review found this independently. It is the second half of the substring
        # bug fixed in 0.4.0: that round replaced the test on the `primary` branch and left the two
        # either side of it - including the one that runs FIRST - matching substrings.
        ("https://untrusted-host.org/annual/8cfr245.pdf", "unknown"),
        ("https://files.random-host.ru/annual/cfr/title-8.xml", "unknown"),
        ("https://evil.example/?ref=govinfo.gov/content/pkg/cfr-2019", "unknown"),
        # ...and the legitimate shapes it exists for must still classify.
        ("https://www.govinfo.gov/content/pkg/CFR-2019-title8/xml/x.xml", "snapshot"),
        ("https://www.ecfr.gov/annual/title-8", "snapshot"),
    ]:
        kind, _h, _w = F.trust_of(url, None, packs)
        ok("fetch: %-52s -> %s" % (url[:52], want), kind == want, kind)

    # 🔴 SILENCE IS NOT A PASS. The sister project printed a green tick whenever its typosquat
    # detector stayed quiet, and wrote a paste-site URL into its law library as a PRIMARY SOURCE.
    out = []
    ok("fetch: an unknown host is refused before any request is made",
       F.fetch_url("https://pastebin.com/raw/nothing", tmp, packs=packs, printer=out.append)
       is None and any("knows nothing" in x for x in out))
    out = []
    ok("fetch: a lookalike is refused EVEN WITH --allow-unknown-source",
       F.fetch_url("https://uscisdhs-gov.us/x.pdf", tmp, packs=packs, allow_unknown=True,
                   printer=out.append) is None and any("REFUSED" in x for x in out))

    # 🔴 The extension is a dispatch key, not decoration. Appending the query after the whole
    # basename turned `title-8.xml?part=245` into `title-8.xml-part-245`, which `read_any` does not
    # recognise - so tags were never stripped and `&#xA7;` never unescaped. Caught by this
    # module's own end-to-end run, which started producing quotations made of markup.
    ok("fetch: a query string does not destroy the extension",
       F._name_from("https://www.ecfr.gov/api/versioner/v1/full/2026-08-01/title-8.xml?part=245",
                    "text/xml").endswith(".xml"),
       F._name_from("https://x/title-8.xml?part=245", "text/xml"))
    ok("fetch: an extensionless URL takes one from the content type",
       F._name_from("https://x/some/path", "application/pdf").endswith(".pdf"))

    d = F.revision_diff(
        "The alien shall be admitted. A second sentence that stays exactly as it was written.",
        "The noncitizen shall be admitted. A second sentence that stays exactly as it was written.")
    ok("fetch: a revision is counted in SENTENCES, not in diff lines",
       len(d["gone"]) == 1 and len(d["added"]) == 1 and d["kept"] == 1, str(d["kept"]))

    ok("fetch: the inbox is not a sources directory by construction",
       F.INBOX.startswith(".krokai"), F.INBOX)


def suite_placeholder():
    """🔴 A failed download must not become law, and a short provision must stay indexed.

    0.6.0 stopped excluding short text sources because a real 71-character savings clause was being
    thrown out and a correct quotation of it came back NOT_FOUND. A reviewer named the other side
    the same week: a scraped `404 Not Found` body is also short, and indexing it made a phrase from
    it VERIFY. Both are true, so the test is on the CONTENT - length was only ever a proxy.
    """
    from krokai.corpus import looks_like_placeholder as lp
    for s in ["404 Not Found - The requested page could not be found.",
              "Just a moment... Checking your browser before accessing the site.",
              "403 Forbidden",
              "Access Denied",
              "Please enable JavaScript to view this page.",
              "500 Internal Server Error"]:
        ok("placeholder: recognised - %s" % s[:44], lp(s))
    for s in ["Nothing in this section shall be construed to limit the authority of the Secretary.",
              "The applicant was denied access to the record and now argues that access denied "
              "in these circumstances violates due process, citing the following authorities.",
              "An alien who has been granted a waiver under section 212(e) of the Act.",
              "The petition shall be considered abandoned if not found to be timely."]:
        ok("placeholder: CONTROL not fired on real prose - %s" % s[:40], not lp(s))

    # 🔴🔴 THE FIX FOR THE OPPOSITE BUG DELETED REAL LAW, AND NO TEST HERE SAW IT.
    # 0.7.1 moved this call out of the length branch so a 900-character bot wall would be caught -
    # correct - and left tier 1 firing at EVERY length. A scraped `.gov` page keeping its noscript
    # footer is the ordinary case, so ~10 000 characters of statute plus one line reading "Please
    # enable JavaScript" excluded the whole document, and every correct quotation of it would come
    # back NOT_FOUND, which is this tool's accusation that the drafter invented it. The suite above
    # passed throughout, because every control in it is SHORT. Found by an outside reviewer asking
    # what else now reaches a call site that had just been widened.
    LAW = ("The Attorney General may in his discretion and under such regulations as he may "
           "prescribe adjust the status of an alien who was inspected and admitted or paroled "
           "into the United States to that of an alien lawfully admitted for permanent "
           "residence. ") * 40
    ok("placeholder: a LONG law carrying one boilerplate line is NOT a placeholder",
       not lp(LAW + "\nPlease enable JavaScript to use this site.\n"),
       "%d chars" % len(LAW))
    ok("placeholder: a long ERROR page with two distinct markers still is",
       lp("404 Not Found. " + "Navigation home about contact search help. " * 120
          + " The requested URL /x was not found on this server."))
    ok("placeholder: a bot wall well over the old 200-char gate still is",
       lp("Just a moment. Checking your browser before accessing the site. "
          "Please enable JavaScript and cookies to continue. " * 9))
    # The gap between the two tiers: over _AMBIGUOUS_MAX, and tier 1 said only "permission to
    # access" while the page says "permission to view". Named by one channel of three.
    ok("placeholder: 'permission to view' is server language too",
       lp("Error: Access Denied. You do not have permission to view this page. "
          "Please contact support for assistance with this request."))


def suite_revision_and_window():
    """The two round-21 findings that are about what a measurement CANNOT see.

    Both were named by all three review channels, and both are cases where the tool answered
    confidently and the confident answer was the wrong shape of answer.
    """
    from krokai import fetch as F
    from krokai import redact as RD

    # 🔴 THE 25-CHARACTER FLOOR HID THE CHANGES MOST WORTH SEEING. An operative sentence is short
    # BECAUSE it is operative: a repeal, a fee, a deadline, an effective date. The floor existed
    # only to drop fragments left by splitting on the stop inside `U.S.C.`, so a fragment is now
    # identified by what it is - no internal space - rather than by being short.
    ok("revision: a short repeal is a sentence", F._sentences("Section 4 is repealed.") != [],
       repr(F._sentences("Section 4 is repealed.")))
    ok("revision: a fee change is a sentence", F._sentences("The fee is $1,440.") != [])
    ok("revision: CONTROL an abbreviation fragment is still dropped", F._sentences("U.S.C.") == [])

    # 🔴 A SET LOSES ORDER, AND ORDER IS OPERATIVE. Relocating a conditioning sentence into another
    # subsection left both differences empty, so this reported 100 % unchanged - and the bank check
    # agreed, because the words really are still somewhere in the file.
    A = ("Alpha beta gamma delta epsilon zeta eta theta. "
         "Iota kappa lambda mu nu xi omicron pi rho sigma tau.")
    B = ("Iota kappa lambda mu nu xi omicron pi rho sigma tau. "
         "Alpha beta gamma delta epsilon zeta eta theta.")
    d = F.revision_diff(A, B)
    ok("revision: pure reordering is reported, not called unchanged",
       d.get("moved", 0) > 0 and not d["gone"] and not d["added"],
       "gone=%d added=%d moved=%d" % (len(d["gone"]), len(d["added"]), d.get("moved", 0)))
    ok("revision: CONTROL an identical document has moved 0",
       F.revision_diff(A, A).get("moved", 0) == 0)
    d3 = F.revision_diff(A, A.replace("Alpha", "Omega"))
    ok("revision: CONTROL a real one-word edit is still caught",
       len(d3["gone"]) == 1 and len(d3["added"]) == 1)

    # 🔴 A CONSTANT THAT CANNOT BE VARIED FROM OUTSIDE CANNOT BE MEASURED FROM OUTSIDE. The wrap
    # width was a local, so the attempt to measure what widening it costs set a module attribute
    # nothing read and reported an identical 0 findings at every width - indistinguishable from a
    # safe change. This asserts the knob stays connected, which is the part that silently rots.
    ok("redact: the wrap window is reachable from outside the function",
       isinstance(getattr(RD, "WRAP_WINDOW", None), int) and RD.WRAP_WINDOW >= 4,
       str(getattr(RD, "WRAP_WINDOW", None)))
    tok = "ghp_" + "B" * 36
    for cols, must in ((20, True), (10, True), (8, True)):
        wrapped = "\n".join(tok[i:i + cols] for i in range(0, len(tok), cols))
        ok("redact: a token wrapped at %d columns is found" % cols,
           bool([f for f in RD.scan(wrapped) if f and f[0] == "SECRET"]) == must)
    ok("redact: CONTROL ordinary prose over the window is not a secret",
       not [f for f in RD.scan("The Secretary shall\nprescribe such regulations\nas may be "
                               "necessary\nto carry out this section\nin a timely manner.")
            if f and f[0] == "SECRET"])


def suite_library_index(tmp):
    """🔴 A row appended below the table renders nowhere.

    The sister project measured it: a 777-line index ending in prose, last table row at 771, and
    the script wrote row 778 and printed "row added" - true, and useless. Markdown stops rendering
    a table at the first non-row line.
    """
    from krokai.library import add_entry, INDEX_HEADER
    p = os.path.join(tmp, "libidx.md")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        INDEX_HEADER + "| 8 CFR 214.2 | reg | `a.xml` | 2026-01-01 | - |  |\n"
        "\nClosing prose a human wrote under the table.\n")
    add_entry(p, "8 CFR 245.1", "reg", "b.xml")
    lines = io.open(p, encoding="utf-8").read().splitlines()
    rowi = [i for i, l in enumerate(lines) if "b.xml" in l][0]
    prosei = [i for i, l in enumerate(lines) if l.startswith("Closing prose")][0]
    ok("library: a new row lands INSIDE the table, above the prose", rowi < prosei,
       "row %d, prose %d" % (rowi, prosei))
    p2 = os.path.join(tmp, "libidx-notable.md")
    io.open(p2, "w", encoding="utf-8", newline="\n").write("prose only, no table\n")
    try:
        add_entry(p2, "8 CFR 245.1", "reg", "c.xml")
        ok("library: a file with no table is refused loudly", False, "it appended silently")
    except ValueError as exc:
        ok("library: a file with no table is refused loudly", "no table" in str(exc))


def suite_review_r21(tmp):
    """Six defects an outside reviewer found in 0.7.1, each reproduced before it was fixed.

    The headline one invalidated the release's own marquee claim: after `intake` detected a
    revision, BOTH editions stayed in the sources directory and both were indexed, so a quotation of
    superseded law came back VERIFIED. The module docstring asserted the opposite - that a
    superseded quotation "will not be found in this year's edition, which this tool reports as
    NOT_FOUND". Measured: it was found, in the wrong edition, silently. **The revision machinery
    created the condition it exists to detect and then suppressed its own alarm.**
    """
    import json
    import shutil
    from krokai import fetch as F
    from krokai.corpus import Corpus, looks_like_placeholder
    from krokai.citations import load_packs
    from krokai.config import load as load_cfg
    from krokai.verify import check
    from krokai.verdicts import CLEAN, DANGEROUS, ORDER, MARK, MEANING
    from krokai.run import SENTINELS

    root = os.path.join(tmp, "r21matter")
    shutil.rmtree(root, ignore_errors=True)
    law = os.path.join(root, "law")
    os.makedirs(law)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "source_dirs": ["law"], "citation_packs": ["us-immigration", "us-federal"]}))
    cfg = load_cfg(root)
    packs = load_packs(cfg["citation_packs"])

    OLD = ("Sec. 245.23 Adjustment of aliens in T nonimmigrant classification. An alien who has "
           "been granted T-1 nonimmigrant status may apply for adjustment of status to that of a "
           "lawful permanent resident. The applicant must establish continuous physical presence.")
    NEW = OLD.replace("aliens", "noncitizens").replace("An alien", "A noncitizen")

    inbox = os.path.join(root, F.INBOX)
    os.makedirs(inbox)

    def drop(name, body, sha):
        io.open(os.path.join(inbox, name), "w", encoding="utf-8", newline="\n").write(body)
        io.open(os.path.join(inbox, name + ".meta.json"), "w", encoding="utf-8").write(json.dumps(
            {"url": "https://www.ecfr.gov/x", "sha256": sha, "trust": "primary",
             "trust_label": "OFFICIAL", "model_in_path": False}))

    drop("8CFR-245.txt", OLD, "a" * 64)
    F.intake(root, cfg, packs, address="8 CFR 245.23", printer=lambda *a: None)
    drop("8CFR-245.txt", NEW, "b" * 64)
    rows = F.intake(root, cfg, packs, address="8 CFR 245.23", printer=lambda *a: None)
    ok("r21: a second edition is detected as a revision",
       any(s.startswith("\U0001f534") for s, _n, _x in rows), str(rows[:1]))

    corp = Corpus([law], sentinel=SENTINELS, quiet=True, superseded=F.superseded_paths(root))
    v, w, _d = check("An alien who has been granted T-1 nonimmigrant status may apply", corp)
    ok("r21: a quotation of SUPERSEDED law is NOT clean", v not in CLEAN, v)
    ok("r21: and it is named for what it is, not accused of fabrication",
       v == "SUPERSEDED_EDITION", v)
    ok("r21: the superseded edition is still ON DISK and still indexed",
       any(os.path.basename(p) == "8CFR-245.txt" for p in corp.paths),
       "a quotation of it was correct when it was taken")
    v2, _w2, _d2 = check("A noncitizen who has been granted T-1 nonimmigrant status may apply",
                         corp)
    ok("r21: CONTROL the CURRENT edition still verifies", v2 in CLEAN, v2)
    for tbl, name in ((ORDER, "ORDER"), (DANGEROUS, "DANGEROUS"), (MARK, "MARK"),
                      (MEANING["en"], "MEANING/en"), (MEANING["ru"], "MEANING/ru")):
        ok("r21: SUPERSEDED_EDITION is in %s" % name, "SUPERSEDED_EDITION" in tbl)

    # 🔴 The placeholder test used to sit inside the `< MIN_TEXT_LAYER` branch, so the tier-1
    # strings documented as firing "wherever they appear" could not fire anywhere except in a file
    # under 200 characters - while a real bot wall is tens of kilobytes. The comment and the call
    # site contradicted each other, and the dangerous direction was the live one.
    big = os.path.join(tmp, "r21big")
    shutil.rmtree(big, ignore_errors=True)
    os.makedirs(big)
    wall = ("Just a moment... Checking your browser before accessing the site. This process is "
            "automatic. Your browser will redirect to your requested content shortly. ") * 6
    io.open(os.path.join(big, "8CFR-214.html"), "w", encoding="utf-8").write(wall)
    bc = Corpus([big], quiet=True)
    ok("r21: a %d-character bot wall is excluded, not indexed" % len(wall),
       not bc.paths and len(bc.excluded_placeholder) == 1,
       "indexed=%d excluded=%d" % (len(bc.paths), len(bc.excluded_placeholder)))
    ok("r21: CONTROL a long real document is untouched by the placeholder test",
       not looks_like_placeholder("The petitioner argues that access denied to the record is "
                                  "itself a violation of due process under the Fifth Amendment."))

    # 🔴 An extraction failure is not a change in the law.
    drop("8CFR-245.txt", "   ", "c" * 64)
    rows = F.intake(root, cfg, packs, address="8 CFR 245.23", printer=lambda *a: None)
    ok("r21: an unreadable new edition is REFUSED, not reported as a change in the law",
       any(s == "UNREADABLE" for s, _n, _x in rows), str(rows[:1]))

    # 🔴 The trust label is re-derived, never read out of the writable file beside the download.
    io.open(os.path.join(inbox, "evil.txt"), "w", encoding="utf-8").write(
        "Text pretending to be law, long enough to be indexed without tripping any floor at all.")
    io.open(os.path.join(inbox, "evil.txt.meta.json"), "w", encoding="utf-8").write(json.dumps(
        {"url": "https://pastebin.com/raw/x", "sha256": "d" * 64, "trust": "primary",
         "trust_label": "OFFICIAL", "model_in_path": False}))
    F.intake(root, cfg, packs, address="8 CFR 245.1", printer=lambda *a: None)
    idx = io.open(cfg.abs(cfg["library_index"]), encoding="utf-8").read()
    ok("r21: a hand-written OFFICIAL claim does not survive intake",
       not any("evil" in l and "OFFICIAL" in l for l in idx.splitlines()),
       [l.strip()[:60] for l in idx.splitlines() if "evil" in l][:1])

    # 🔴 An ellipsis is citation style, not an alteration.
    io.open(os.path.join(root, "QUOTE-BANK.md"), "w", encoding="utf-8").write(
        "# Quote bank\n\n### 1\n\n> A noncitizen who has been granted T-1 nonimmigrant status "
        "... lawful permanent resident.\n\n### 2\n\n> An alien who has been granted T-1 "
        "nonimmigrant status may apply for adjustment.\n")
    impact = "\n".join(F._bank_impact(cfg, NEW, packs))
    ok("r21: an ellipsis quotation whose fragments survive is not reported lost",
       "**1 no longer appear" in impact, impact.splitlines()[0][:70])
    ok("r21: CONTROL the quotation whose words really changed IS reported",
       "An alien who has been granted" in impact)

    # 🔴 The one handler whose purpose is to record a death recorded it nowhere.
    import inspect as _i
    _bq = _hook_module("bank_queue")
    tail = _i.getsource(_bq)
    tail = tail[tail.rindex('if __name__'):]
    code = [l for l in tail.splitlines() if not l.strip().startswith("#")]
    ok("r21: bank_queue's death handler no longer logs to None",
       not any("log(None," in l for l in code))
    ok("r21: it writes to the matter and falls back to stderr",
       any("log(find_config()" in l for l in code) and any("stderr.write" in l for l in code))


def suite_no_real_identifiers(root):
    """No identifier-shaped literal exists in this tree except the documented fictional ones.

    🔴 This is the negative control for incident 65, and it is the one the previous 292 assertions
    could not have been. The write-up of the grouped-identifier defect quoted the applicant's real
    A-number and receipt number, and the SAME numbers were the positive fixtures for
    `ALIEN_NUMBER` - so the detector fired on them, the suite went green, and the green run is what
    kept the values in the file. **A passing test was evidence for the leak.**

    Three design choices, each of them a rule this project already paid for:

    1. **The allow-list is a set of VALUES, never a set of filenames.** `redact.py` legitimately
       contains identifier shapes; exempting `redact.py` would have exempted the two real numbers
       sitting in its comment. The same mistake, made with a filename, kept a wrong copyright line
       in `LICENSE` for this repository's entire life while the build reported clean.
    2. **Coverage is asserted, not assumed.** A scanner that silently scans nothing is a green
       light with no eyes - measured three times in this project. So the suite fails unless it
       actually opened the four files that have historically carried a value.
    3. **The scanner is proved to work by planting one.** A control string is scanned in the same
       call, and the suite fails if the scan does not flag it.

    The value is never printed - not in a pass, not in a failure. A failure names kind, file, line
    and a SHA-256 prefix, which is enough to find it with `grep -n` and not enough to publish it.
    """
    import hashlib
    from krokai.redact import PII_PATTERNS, FICTIONAL, ALLOWED_NON_FICTIONAL, SECRET_PATTERNS

    # The classes that identify a PERSON by number. Addresses are deliberately out: the street and
    # the city are geography by this project's own redaction rule, and they appear in prose on
    # nearly every page, so including them would make this check cry wolf - the failure mode
    # `normalize.py` names as the one that kills a tool.
    WATCHED = ("EMAIL", "US_PHONE", "SSN", "ALIEN_NUMBER", "USCIS_RECEIPT", "SEVIS_ID",
               "PASSPORT_NUMBER", "DATE_OF_BIRTH", "PAYMENT_CARD", "BANK_ACCOUNT")
    pats = [(k, rx) for k, rx in PII_PATTERNS if k in WATCHED] + list(SECRET_PATTERNS)
    allowed = set(FICTIONAL.values()) | set(ALLOWED_NON_FICTIONAL)

    def offenders(text):
        out = []
        for lineno, line in enumerate(text.splitlines(), 1):
            for kind, rx in pats:
                for m in rx.finditer(line):
                    val = m.group(0)
                    if val in allowed or any(val in a for a in allowed):
                        continue
                    out.append((kind, lineno, hashlib.sha256(val.encode("utf-8")).hexdigest()[:10]))
        return out

    # (3) the planted control, scanned by the same code path as the tree.
    # 🔴 Assembled from fragments, and the reason is that the first version was NOT: this scanner's
    # very first run flagged its own probe line. A detector whose test data trips the detector
    # cannot be run over its own source, which is how a check quietly acquires a file exemption -
    # the exemption this suite exists to avoid. Concatenation keeps the runtime match and leaves no
    # literal on disk, the same move the secret probes make in `redact.py`.
    planted = offenders("the notice shows A-123" + "-456-789 and receipt EAC" + "1234567890 today")
    ok("publish: the tree scanner flags a planted identifier",
       {k for k, _l, _d in planted} == {"ALIEN_NUMBER", "USCIS_RECEIPT"},
       str(sorted({k for k, _l, _d in planted})))
    ok("publish: the tree scanner does not flag a documented fictional value",
       not offenders("the notice shows %s and receipt %s today"
                     % (FICTIONAL["ALIEN_NUMBER"], FICTIONAL["USCIS_RECEIPT"])))

    scanned, findings = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".pytest_cache", ".venv", "runs")]
        for fn in sorted(filenames):
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root).replace("\\", "/")
            try:
                with io.open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, OSError, ValueError):
                continue                      # binary or unreadable: not a place a literal hides
            scanned.append(rel)
            for kind, lineno, dig in offenders(text):
                findings.append("%s %s:%d sha=%s" % (kind, rel, lineno, dig))

    # (2) coverage, asserted rather than hoped for
    MUST_SEE = ("krokai/redact.py", "krokai/selftest.py", "CHANGELOG.md", "FEATURES.md")
    missing = [m for m in MUST_SEE if m not in scanned]
    ok("publish: the tree scan actually opened the files that have carried a value",
       not missing and len(scanned) >= 30, "missing=%s scanned=%d" % (missing, len(scanned)))

    ok("publish: no undocumented identifier or secret literal anywhere in the tree",
       not findings, "; ".join(findings[:6]))


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
        suite_r50_no_green_without_guard(corpus)
        suite_r51_tail_elision(corpus)
        suite_word_diff()
        suite_citations()
        suite_address(corpus, law)
        suite_redact()
        suite_mutations(corpus)
        suite_prompts()
        suite_bank(tmp)
        suite_upgrade(tmp)
        suite_config(tmp)
        suite_install(tmp)
        suite_verdicts()
        suite_consult(tmp)
        suite_pipeline_samples()
        suite_ported(tmp)
        suite_hooks_stdin(tmp)
        suite_sidecar_not_a_source(tmp)
        suite_readers_signature()
        suite_missing_engine_is_loud(tmp)
        suite_fetch(tmp)
        suite_placeholder()
        suite_revision_and_window()
        suite_library_index(tmp)
        suite_review_r21(tmp)

        # 🔴 THESE THREE SCAN THE SOURCE TREE, NOT THE PRODUCT, so they mean something only from a
        # checkout. `root` is `<pkg>/..`, which is `site-packages` in an installed copy - and there
        # the identifier scanner walked pip's own vendored code and reported six LABELLED_SECRET
        # findings in `pip/_internal/network/auth.py`. A leak detector that confidently accuses a
        # third-party dependency is worse than one that does not run, because somebody would have
        # believed it. Found by running the wheel; from a clone this suite passed 421/421 and said
        # nothing.
        #
        # The skip is announced, not silent. A test that quietly vanishes reads as a test that
        # passed, which is the exact failure shape this project exists to catch.
        if _is_source_checkout(root):
            suite_no_real_identifiers(root)
            suite_rename(root)
            suite_docs(root)
        else:
            print("note: 3 repository-hygiene suites skipped - this is an installed copy, not a\n"
                  "      source checkout, so there is no tree of ours to scan (looked in: %s).\n"
                  "      To run them: git clone the repo and `python -m krokai selftest` there."
                  % root)
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
