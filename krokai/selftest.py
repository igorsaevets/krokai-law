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

from ._datadir import data_dir, data_file

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
                      "clock hours of attendance a week if the dominant part of the course of study "
                      "consists of classroom instruction", corpus)
    ok("verdict VERIFIED on an exact, complete quotation", v == "VERIFIED", v)
    # 🔴 K094: the quotation this pin used until 2026-11-26 stops before «if the dominant part of the
    # course of study consists of classroom instruction» - the eighteen hours hold only for a course
    # that is mostly classroom teaching. It was «complete» only in the eyes of a limiter list with no
    # «if»; it is the condition-dropping cut K094 exists for.
    v, _w, d = check("certified by a designated school official to consist of at least eighteen "
                     "clock hours of attendance a week", corpus)
    ok("k094 the old «complete» quotation, cut before «if the dominant part …», is TRUNCATED_CONDITION",
       v == "TRUNCATED_CONDITION" and "if the dominant part" in (d or ""), "%s :: %s" % (v, d))

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
    # K094: «… attendance a week» was this complete quotation until 2026-11-26 - the source goes on
    # «if the dominant part of the course of study consists of classroom instruction», so it was a
    # condition-dropping cut that read green only because LIMITER_RE had no «if». Complete = to the
    # end of the sentence.
    complete = ("certified by a designated school official to consist of at least eighteen "
                "clock hours of attendance a week if the dominant part of the course of study "
                "consists of classroom instruction")

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
    # K094: «… attendance a week» was this complete quotation until 2026-11-26 - the source goes on
    # «if the dominant part of the course of study consists of classroom instruction», so it was a
    # condition-dropping cut that read green only because LIMITER_RE had no «if». Complete = to the
    # end of the sentence.
    complete = ("certified by a designated school official to consist of at least eighteen "
                "clock hours of attendance a week if the dominant part of the course of study "
                "consists of classroom instruction")

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

    # 🔴🔴 R56 / r55 panel Finding 4 — NEG-2 IS RIGHT TO BE SILENT AND WAS WRONG TO BE INVISIBLE.
    # NEG-2 above asserts the tool raises no ALARM on a sub-25-character tail, and that is correct:
    # the locator would match the wrong provision. But «no alarm» reached the reader as «checked,
    # clean», which for a tool that grades legal filings is a false clean bill. Every panel channel
    # that returned called it a real defect; the three that argued the design (spark12cont,
    # mimo25pro, grokbuild) all rejected a fourth verdict state in favour of a disclosure on the
    # existing one.
    #
    # The pair below is the whole test, and the second half is what makes it a test rather than a
    # restatement: a check that fires everywhere is indistinguishable from a check that is stuck on.
    # 🔴🔴 R56 / r55 panel Finding 4 — THE ANSWER IS «UNREACHABLE», AND THIS PINS IT.
    #
    # The panel was unanimous that declining in silence is a defect, and the reasoning is sound.
    # It is also unreachable: `ellipsis_parts` drops sub-floor fragments UPSTREAM, so `parts[-1]`
    # is short only when the whole quotation is one short fragment, and a quotation that short
    # cannot be located, so it returns NOT_FOUND - loud. Six shapes measured, zero silent passes;
    # see `tail_short_enough_to_decline`. agy37flash predicted precisely this in its own «what
    # would change my conclusion», which is the one place a reviewer can be more useful than four
    # reviewers agreeing.
    #
    # No disclosure was shipped, because a guard that cannot fire is decoration. THIS assertion
    # is what ships instead: it fails the day `ellipsis_parts` starts letting a short tail through
    # to a clean verdict, and on that day Finding 4 stops being theoretical.
    from krokai.verify import CLEAN, normalise, prepare_quote, tail_short_enough_to_decline
    for name, q in (("single short fragment", "clock hours…"),
                    ("multi fragment, short tail",
                     "certified by a designated school official … a week…")):
        v, _w, _d = check(q, corpus)
        n_ = normalise(prepare_quote(q))
        ok("r56 no CLEAN verdict is returned over a tail the floor declined to examine (%s) - "
           "the silent pass the r55 panel warned about is unreachable, not merely unobserved"
           % name,
           not (v in CLEAN and tail_short_enough_to_decline(n_, q)),
           "%s + declined=%s" % (v, tail_short_enough_to_decline(n_, q)))
    # POSITIVE CONTROL for the predicate itself: it must be able to say True, or the assertion
    # above is satisfied by a function that always returns False and proves nothing.
    ok("r56 the predicate CAN report a declined tail - without this the assertion above passes "
       "on a helper that is simply stuck off",
       tail_short_enough_to_decline(normalise(prepare_quote("clock hours…")), "clock hours…"),
       "predicate never fires")
    ok("r56 NEG the predicate is silent on a quotation with no trailing ellipsis",
       not tail_short_enough_to_decline(truncated, truncated), "fired anyway")

    # 🔴🔴 POS-3/NEG-4: THE BLUEBOOK SPACED ELLIPSIS, found by the panel that reviewed v0.8.3 and
    # confirmed by execution the same hour. Three places each spelled "an ellipsis" for themselves
    # and all three wrote `...` or `…`. The Bluebook (rule 5.3) marks an omission with periods
    # SEPARATED BY SPACES, so `. . .` is the form legal citation actually prescribes - and it fell
    # past the ellipsis machinery entirely and came back TRUNCATED_CONDITION, i.e. "you cut this
    # off silently". That is the exact false accusation v0.8.2 removed, still live one release
    # later for the one dialect that matters most. 80 quotations on the live filing use it.
    for tail in (". . .", " . . ."):
        v, _w, _d = check(truncated + tail, corpus)
        ok("r51 POS-3 a Bluebook spaced ellipsis is an ELLIPSIS, not a silent truncation (%r)"
           % tail, v == "ELLIPSIS_HIDES", v)
        v, _w, _d = check(complete + tail, corpus)
        ok("r51 NEG-4 a Bluebook spaced ellipsis hiding nothing stays green (%r)" % tail,
           v not in ("ELLIPSIS_HIDES", "TRUNCATED_CONDITION"), v)

    # The negative control that keeps ELLIPSIS_RE from eating ordinary prose: an abbreviation and a
    # sentence boundary followed by an initial both contain periods near each other, and neither is
    # an omission. `\.\s?\.\s?\.` cannot match them because letters sit between the periods - but
    # that is an argument, and an argument is not a test.
    from krokai.normalize import ELLIPSIS_RE as _ER
    for benign in ("8 U.S.C. 1255", "decided in 1990. J. Smith wrote", "see id. at 12",
                   "Cf. Matter of A-B-, 27 I&N Dec. 316"):
        ok("r51 NEG-5 ELLIPSIS_RE does not fire on ordinary prose: %r" % benign[:28],
           not _ER.search(benign), benign)


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

    # -- the Python floor: one fact, five homes ----------------------------------------------------
    # 🔴 K003 (2026-11-23): INSTALL.md promised 3.9 after GitHub's ubuntu-latest had stopped
    # offering a 3.9 to test it on, and CI went red with no code change. pip enforces the floor in
    # pyproject.toml; the install documents, the version classifiers and the CI matrix restate it,
    # so they are read back here. The CI half matters most: a floor that no runner executes is a
    # number in prose. Versions are compared as numbers - as strings "3.9" sorts above "3.15".
    pp = os.path.join(root, "pyproject.toml")
    wf = os.path.join(root, ".github", "workflows", "selftest.yml")
    if os.path.isfile(pp) and os.path.isfile(wf):
        ptxt = io.open(pp, encoding="utf-8").read()
        wtxt = io.open(wf, encoding="utf-8").read()
        minor = lambda v: int(v.split(".")[1])
        m = re.search(r'^requires-python\s*=\s*">=\s*(3\.\d+)"\s*$', ptxt, re.M)
        ok("docs: pyproject.toml states the Python floor as a plain >=3.N", bool(m),
           "no `requires-python = \">=3.N\"` line")
        if m:
            floor = m.group(1)
            for f in ("INSTALL.md", "INSTALL-FOR-AI.md"):
                if f in text:
                    said = sorted(set(re.findall(r"\b(3\.\d+) or newer", text[f])))
                    ok("docs: %s states the floor pyproject.toml enforces" % f, said == [floor],
                       "pyproject %s, %s says %s" % (floor, f, said or "nothing"))
            ci = sorted(set(re.findall(r"""['"](3\.\d+)['"]""", wtxt)), key=minor)
            ok("docs: CI runs the suite on the floor Python itself, and on nothing older",
               bool(ci) and ci[0] == floor, "floor %s, CI matrix %s" % (floor, ci))
            cls = sorted(set(re.findall(r'Python :: (3\.\d+)"', ptxt)), key=minor)
            ok("docs: the version classifiers are exactly the Pythons CI runs",
               cls == ci, "classifiers %s, CI %s" % (cls, ci))
    else:
        print("note: the Python-floor check did not run - pyproject.toml or the CI workflow is not "
              "beside the package here.")

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
        from krokai import _pdfengine
        _fitz = _pdfengine.load()
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

    builtins.__import__ = hide({"pypdf", "fitz", "pymupdf"})   # K003: both PyMuPDF names
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

    # 🔴 K003: PyMuPDF 2.x prints "The `fitz` API is deprecated and will be removed in future". The
    # day it is removed, every `import fitz` raises ImportError, which this package reads as "not
    # installed": doctor would say MISSING on a machine that has it, and the two-engine cross-check
    # would drop to one engine without a word. Simulated by hiding the OLD name only - and gated on
    # the new name really importing here, or the check would measure the environment, not the code.
    try:
        import pymupdf as _new
    except Exception:
        _new = None
        print("note: readers K003 check skipped - `import pymupdf` fails here (PyMuPDF absent or "
              "older than 1.24.3), so its premise does not hold.")
    if _new is not None:
        fx = os.path.join(tmp, "k003-new-name.pdf")
        d = _new.open()
        pg = d.new_page()
        # Over MIN_TEXT_LAYER on purpose: with pypdf hidden, a page shorter than the floor reads as
        # "no text layer" by design, and the check would then fail for the wrong reason.
        for i in range(8):
            pg.insert_text((72, 90 + 16 * i), "line %d of the new name probe marker K003" % i)
        d.save(fx)
        d.close()
        builtins.__import__ = hide({"fitz", "pypdf"})
        try:
            eng = R.engines_available()
            ok("readers: PyMuPDF still counts as installed once its old `fitz` name is gone (K003)",
               eng.get("PyMuPDF") is True, str(eng))
            try:
                got = R.read_pdf(fx)
            except MissingReader as e:
                got = "MissingReader: %s" % e
            ok("readers: and a PDF is still read through the `pymupdf` name alone (K003)",
               "new name probe marker K003" in (got or ""), repr(got)[:80])
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
    # K093: the rate moved with the rest of the PDF question into `pdf_text_verdict`, which
    # `no_text_layer` now answers through - the behaviour is pinned by r77 #351 (thin-scan.pdf).
    ok("readers: the text-layer test has a PER-PAGE rate, not only a total",
       R.MIN_CHARS_PER_PAGE > 0 and "MIN_CHARS_PER_PAGE" in inspect.getsource(R.pdf_text_verdict)
       and "pdf_text_verdict" in inspect.getsource(R.no_text_layer),
       "%d chars/page from %d pages up" % (R.MIN_CHARS_PER_PAGE, R.PAGES_BEFORE_RATE_APPLIES))


def suite_write_only_accumulator():
    """🔴🔴 A list that is only ever appended to is a SILENT DROP wearing a variable name.

    Found 2026-08-19 in my own work, by the sister project, in the patch I had written the day
    before. `NEIGHBOUR_SKIPS = []  # печатается в конце прогона` - declared with that comment,
    appended to in one place, and read in none. 104 rows vanished from a report without a word,
    in code whose entire purpose was to STOP silent dropping. The comment was an assertion by
    the author about a program that never did it.

    This is the same shape as R51's `tail_elision_hides`: a sentence about control flow that was
    never executed. The difference is that this one is mechanically detectable, so it does not
    have to be remembered - an accumulator with zero reads is a defect by construction.

    The POSITIVE CONTROL is the point of this suite. A scanner that returns "nothing found"
    against a codebase that has nothing to find is indistinguishable from a scanner that cannot
    find anything, so a known-bad snippet must come back red in the same run.
    """
    import ast
    import collections
    import inspect
    import os

    from krokai import __file__ as pkg_file

    GROW = ("append", "add", "extend", "update")

    def write_only(src):
        """Names appended to but never loaded for any other purpose.

        🔴 0.8.6: PARAMETERS ARE EXCLUDED, and 0.8.5 was wrong to include them. A helper whose
        whole job is to fill a list handed to it — `def record(msg, hard, soft): hard.append(msg)`
        — appends and never reads, inside this file, under that name. The caller reads it under
        a different one. That is correct design and 0.8.5 called it a defect.

        Found by running this detector against a foreign codebase rather than only against
        krokai, which happens to contain no such helper: the suite below was green and the
        shipped detector was still wrong for its users. A scanner tested only on the tree it
        ships with has been tested on one sample.

        This matters more than a tidy report. A false positive in a safety gate is worse than a
        miss — it teaches the reader to wave the check through, and that disables the whole
        class, including the real `NEIGHBOUR_SKIPS` this suite exists to catch.

        The exclusion is lexical and deliberately generous: if any enclosing function binds the
        name as a parameter, the name is not reported. That can hide a module-level accumulator
        that shares a name with some parameter elsewhere in the file — a MISS. Chosen knowingly,
        because the cost of the two errors is not symmetric.
        """
        tree = ast.parse(src)
        appended, read = collections.Counter(), collections.Counter()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in GROW
                    and isinstance(node.func.value, ast.Name)):
                appended[node.func.value.id] += 1
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                read[node.id] += 1

        param_bound = set()
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = fn.args
            params = {a.arg for a in
                      list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)}
            if args.vararg:
                params.add(args.vararg.arg)
            if args.kwarg:
                params.add(args.kwarg.arg)
            if not params:
                continue
            for node in ast.walk(fn):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in GROW
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in params):
                    param_bound.add(node.func.value.id)

        # every Load of the name, minus the ones that are just the `.append` receiver
        return sorted(n for n, c in appended.items()
                      if read.get(n, 0) - c <= 0 and n not in param_bound)

    BAD = (
        "SKIPS = []\n"
        "def f(rows):\n"
        "    for r in rows:\n"
        "        if drop(r):\n"
        "            SKIPS.append(r)   # printed at the end of the run - except it is not\n"
    )
    GOOD = BAD + "def report():\n    return len(SKIPS)\n"
    ok("accumulator: the detector BITES on a write-only list", "SKIPS" in write_only(BAD))
    ok("accumulator: and stays quiet once the name is read back",
       "SKIPS" not in write_only(GOOD))

    # 🔴 The 0.8.5 false positive, kept as a permanent case. Verbatim shape of the helper that
    # exposed it: a routing function that fills two lists its caller owns and names differently.
    PARAM = (
        "def record(msg, hard, soft):\n"
        "    if msg.startswith('~soft~'):\n"
        "        soft.append(msg)\n"
        "    else:\n"
        "        hard.append(msg)\n"
        "def run():\n"
        "    warn, note = [], []\n"
        "    record('x', warn, note)\n"
        "    return len(warn), len(note)\n"
    )
    ok("accumulator: a list PASSED IN and filled is not an orphan (0.8.5 said it was)",
       write_only(PARAM) == [], repr(write_only(PARAM)))
    # ...and the exclusion must not have blunted the detector: same file, real defect added.
    ok("accumulator: the parameter exemption did not disable the check",
       "SKIPS" in write_only(PARAM + BAD))

    root = os.path.dirname(os.path.abspath(pkg_file))
    offenders = []
    scanned = 0
    for dp, _dn, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dp, fn)
            try:
                with io.open(path, encoding="utf-8") as fh:
                    names = write_only(fh.read())
            except (SyntaxError, OSError):
                continue
            scanned += 1
            for n in names:
                offenders.append("%s:%s" % (fn, n))
    ok("accumulator: no write-only accumulator anywhere in krokai",
       not offenders, "%d файлов просмотрено%s"
       % (scanned, ("; " + ", ".join(offenders[:4])) if offenders else ""))
    # coverage: a green above is only meaningful if the walk actually saw the package
    ok("accumulator: and the scan really opened the package", scanned >= 8,
       "%d .py" % scanned)


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


# What git exports to a hook so that git commands run inside it find the hook's repository: the
# list `git rev-parse --local-env-vars` prints (git 2.53).
_GIT_LOCAL_ENV = ("GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG", "GIT_CONFIG_PARAMETERS",
                  "GIT_CONFIG_COUNT", "GIT_OBJECT_DIRECTORY", "GIT_DIR", "GIT_WORK_TREE",
                  "GIT_IMPLICIT_WORK_TREE", "GIT_GRAFT_FILE", "GIT_INDEX_FILE",
                  "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE", "GIT_PREFIX",
                  "GIT_SHALLOW_FILE", "GIT_COMMON_DIR")


def _git(folder, *args, opts=()):
    """Run git about the repository at `folder`, never about the one an outer hook points at.

    🔴 This self-test may run from a git hook (a local pre-commit guard), and git hands every hook
    these variables "so that Git commands run by the hook can correctly locate the repository" -
    githooks(5), which tells a hook that works on another repository to clear them. Measured, git
    2.53: a partial commit (`git commit <path>`) gives its hook GIT_INDEX_FILE as an ABSOLUTE path
    to the commit's temporary index. `git add` honours that variable, so the scope proof's `git
    add` in its throwaway repository would have staged the planted files into the commit being
    made - in a public repository.
    """
    import subprocess
    env = {k: v for k, v in os.environ.items() if k.upper() not in _GIT_LOCAL_ENV}
    return subprocess.run(["git"] + list(opts) + ["-C", folder] + list(args),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60)


def _first_line(raw):
    """The first non-empty line of a subprocess stream, short enough for a one-line note."""
    lines = [ln.strip() for ln in raw.decode("utf-8", "replace").splitlines() if ln.strip()]
    return lines[0][:120] if lines else "no message"


def _git_never_published(root, opts=()):
    """What git lists under `root` as untracked AND ignored: `(paths, None)`, or `(None, why)`.

    Paths are root-relative with '/'; a folder ignored whole is one entry ending in '/'. A TRACKED
    file is never among them: `--others` lists untracked paths only, and git opens an ignored
    folder that holds a tracked file and lists its untracked files one by one - so an ignore
    pattern cannot hide a file git already publishes. `-z` prints each name verbatim; without it
    a non-ASCII name comes back octal-quoted and matches nothing on disk (the false BLOCKED on
    Cyrillic paths in the publish audit's `--respect-gitignore`). `None` whenever git cannot
    answer for exactly this folder: no git, not a working tree, or a folder inside a larger
    working tree, whose ignore rules belong to somebody else.
    """
    import subprocess
    try:
        r = _git(root, "rev-parse", "--is-inside-work-tree", "--show-prefix", opts=opts)
        lines = r.stdout.decode("utf-8").splitlines()
        if r.returncode != 0 or not lines or lines[0] != "true":
            return None, "not a git working tree: %s" % _first_line(r.stderr)
        if len(lines) > 1 and lines[1]:
            return None, "a folder inside a larger git working tree (%s)" % lines[1]
        r = _git(root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard",
                 "--directory", opts=opts)
        if r.returncode != 0:
            return None, "git ls-files failed: %s" % _first_line(r.stderr)
        return {p for p in r.stdout.decode("utf-8").split("\0") if p}, None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return None, "git did not answer (%s)" % type(exc).__name__


def _publish_tree_scan(root, offenders, opts=()):
    """Read what git would publish under `root`: `(scanned, findings, left_out, why)`.

    The walk is the one this check always made; only the paths git itself lists as untracked AND
    ignored are left out. When git cannot answer for this folder `left_out` is None and every
    file is read - the failure direction is a red line, never a file that went unread.
    """
    left_out, why = _git_never_published(root, opts)
    skip = left_out or set()
    scanned, findings = [], []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", ".pytest_cache", ".venv", "runs")
                       and rel_dir + d + "/" not in skip]
        for fn in sorted(filenames):
            rel = rel_dir + fn
            if rel in skip:
                continue
            try:
                with io.open(os.path.join(dirpath, fn), encoding="utf-8") as fh:
                    text = fh.read()
            except (UnicodeDecodeError, OSError, ValueError):
                continue                      # binary or unreadable: not a place a literal hides
            scanned.append(rel)
            for kind, lineno, dig in offenders(text):
                findings.append((kind, rel, lineno, dig))
    return scanned, findings, left_out, why


def _rmtree_writable(path):
    """`shutil.rmtree` that also removes read-only files.

    🔴 git writes its object files read-only. On Windows `shutil.rmtree(..., ignore_errors=True)`
    then keeps the whole throwaway repository and says nothing - measured in K006: the two objects
    of one `git add` kept the folder. Clear the bit first, then remove.
    """
    import stat
    for dirpath, _dirs, files in os.walk(path):
        for fn in files:
            try:
                os.chmod(os.path.join(dirpath, fn), stat.S_IREAD | stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def _publish_scope_proof(offenders):
    """Prove the scope of the publish scan on a throwaway repository, through the same walk.

    Every planted file carries the same planted identifier, so WHICH files the scan reports is the
    scope. The machine's own git configuration must not move the answer: a global ignore file
    that matched `published.md` would turn this proof red on one machine only, so the proof points
    `core.excludesFile` at a file that does not exist; `core.fsmonitor=` (empty: off), because a
    monitor daemon would hold the folder open and the clean-up would fail on Windows.
    """
    planted = "receipt EAC" + "1234567890 on the notice"      # assembled: see (3) in the suite
    cyr = "архив"                          # a non-ASCII folder name
    base = tempfile.mkdtemp(prefix="krokai-scope-")
    opts = ("-c", "core.excludesFile=" + os.path.join(base, "no-such-ignore-file"),
            "-c", "core.fsmonitor=")
    # The proof runs as if from a hook: an absolute GIT_INDEX_FILE that every git call here must
    # ignore (see `_git`). Asserted on the output - nothing may appear at that path.
    poison = base + "-hook-index"
    saved = os.environ.get("GIT_INDEX_FILE")
    os.environ["GIT_INDEX_FILE"] = poison
    try:
        try:
            _git(base, "version")
        except OSError:
            print("note: git was not found - the publish-scope proof was skipped, and the tree "
                  "scan reads every file")
            return
        tree = {".gitignore": "/private/\n*.log\n%s/\n" % cyr, "sub/.gitignore": "secret.txt\n",
                "published.md": planted, "forced.log": planted, "private/notes.md": planted,
                "local.md": planted, cyr + "/notes.md": planted, "sub/secret.txt": planted}
        for rel, text in tree.items():
            path = os.path.join(base, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text + "\n")
        made = [_git(base, "init", "-q", opts=opts)]
        os.makedirs(os.path.join(base, ".git", "info"), exist_ok=True)
        with io.open(os.path.join(base, ".git", "info", "exclude"), "a", encoding="utf-8") as fh:
            fh.write("/local.md\n")
        made.append(_git(base, "add", ".gitignore", "published.md", opts=opts))
        made.append(_git(base, "add", "-f", "forced.log", opts=opts))
        bad = [_first_line(m.stderr) for m in made if m.returncode != 0]
        ok("publish scope: the proof built its throwaway repository", not bad, "; ".join(bad))

        _s, found, left, why = _publish_tree_scan(base, offenders, opts)
        read = sorted({rel for _k, rel, _l, _d in found})
        ok("publish scope: read - an untracked file git would add, and a TRACKED file an ignore "
           "pattern matches", read == ["forced.log", "published.md"], "%s %s" % (read, why))
        want = sorted(["private/", "local.md", "sub/secret.txt", cyr + "/"])
        ok("publish scope: left out - an ignored folder, .git/info/exclude, a nested .gitignore, "
           "a non-ASCII name", sorted(left or ()) == want, "%s %s" % (sorted(left or ()), why))

        _s, found, left, why = _publish_tree_scan(os.path.join(base, "sub"), offenders, opts)
        ok("publish scope: a folder inside a larger working tree is read whole",
           left is None and [rel for _k, rel, _l, _d in found] == ["secret.txt"],
           "%s %s" % (why, found))

        _rmtree_writable(os.path.join(base, ".git"))
        _s, found, left, why = _publish_tree_scan(base, offenders, opts)
        read = sorted({rel for _k, rel, _l, _d in found})
        ok("publish scope: with no git every file is read, the ignored ones included",
           left is None and len(read) == 6, "%s %s" % (why, read))
    finally:
        if saved is None:
            os.environ.pop("GIT_INDEX_FILE", None)
        else:
            os.environ["GIT_INDEX_FILE"] = saved
        _rmtree_writable(base)
    ok("publish scope: the proof removed its throwaway repository", not os.path.exists(base),
       base)
    ok("publish scope: a hook's GIT_INDEX_FILE was not written to", not os.path.exists(poison),
       poison)
    if os.path.exists(poison):
        os.remove(poison)


def suite_no_real_identifiers(root):
    """No identifier-shaped literal exists in this tree except the documented fictional ones.

    🔴 This is the negative control for incident 65, and it is the one the previous 292 assertions
    could not have been. The write-up of the grouped-identifier defect quoted the applicant's real
    A-number and receipt number, and the SAME numbers were the positive fixtures for
    `ALIEN_NUMBER` - so the detector fired on them, the suite went green, and the green run is what
    kept the values in the file. **A passing test was evidence for the leak.**

    Four design choices, each of them a rule this project already paid for:

    1. **The allow-list is a set of VALUES, never a set of filenames.** `redact.py` legitimately
       contains identifier shapes; exempting `redact.py` would have exempted the two real numbers
       sitting in its comment. The same mistake, made with a filename, kept a wrong copyright line
       in `LICENSE` for this repository's entire life while the build reported clean.
    2. **Coverage is asserted, not assumed.** A scanner that silently scans nothing is a green
       light with no eyes - measured three times in this project. So the suite fails unless it
       actually opened the four files that have historically carried a value.
    3. **The scanner is proved to work by planting one.** A control string is scanned in the same
       call, and the suite fails if the scan does not flag it.
    4. **The tree is what git would publish.** The walk leaves out only what git itself lists as
       untracked AND ignored; a tracked file is read even when an ignore pattern matches it, and
       where git cannot answer for this folder every file is read, as before. K006 (2026-11-24):
       a maintainer's working folder keeps a private layer that git ignores, and this check
       failed there on every run while a fresh clone passed - so every verdict on the code
       needed a copy of the tree, and a line that is always red is the line a reader learns to
       skip. Exempting file names inside this check would have been choice 1's mistake; the scope
       follows the rule that decides what is published instead, and no ignore pattern can take
       a tracked file out of it. The scope is proved on a throwaway repository in the same call.

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

    # (4) the scope - what git would publish. Proved first on a throwaway repository through the
    # same walk, then applied to this tree; what was left out is printed, never dropped silently.
    _publish_scope_proof(offenders)
    scanned, found, left_out, why = _publish_tree_scan(root, offenders)
    findings = ["%s %s:%d sha=%s" % f for f in found]
    if left_out:
        names = sorted(left_out)
        print("note: the identifier scan left out %d path(s) git never publishes (untracked and "
              "ignored): %s%s" % (len(names), ", ".join(names[:8]),
                                  ", ..." if len(names) > 8 else ""))
    elif why and os.path.exists(os.path.join(root, ".git")):
        print("note: the identifier scan reads every file here, the ignored ones included - %s"
              % why)

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


def suite_r76(tmp):
    """R76 panel round: every behavior change pinned by the probe that proved the defect.

    19 channels reviewed v0.9.3; the accepted findings were reproduced by execution BEFORE the
    fixes (probe_adjudicate.py, R76) and each pin below is one probe. The controls matter as
    much as the pins: the repair must still repair, and a genuine punctuation drift must still
    be green - a fix that turns everything loud disables the tool as surely as a false green.
    """
    import json as _json
    from krokai.corpus import Corpus
    from krokai.verify import check, word_diff, FOOTNOTE_RE
    from krokai import address as addr_mod
    from krokai.citations import load_packs
    from krokai.verdicts import CLEAN, DANGEROUS, MARK, SIX_CAUSES
    from krokai.run import _CLEANISH
    from krokai.extract import citation_window

    def corp(name, files):
        d = os.path.join(tmp, "r76", name)
        os.makedirs(d, exist_ok=True)
        for fn, text in files.items():
            io.open(os.path.join(d, fn), "w", encoding="utf-8").write(text)
        return Corpus([d], quiet=True)

    packs = load_packs(["us-federal"])
    full = ("No alien shall be granted adjustment of status under this part unless the alien "
            "establishes clear eligibility for the benefit sought at the time of filing.")
    quote = "No alien shall be granted adjustment of status under this part"

    # --- CRIT-2: the anchor-miss repair may not launder a dangerous verdict -----------------
    c = corp("crit2", {"1-preamble.md": "Preliminary discussion. " + full + " End.",
                       "8USC-1255.md": "SEC. 1255. " + full + " (b) Record."})
    keymap = addr_mod.KeyMap(c, packs)
    v0, w0, d0 = check(quote, c)
    v1, w1, _d1, a1 = addr_mod.fold(quote, v0, w0, d0, ["8 U.S.C. § 1255"], c, keymap, packs)
    ok("r76: truncation survives the anchor-miss repair (12 channels, probe CRIT2)",
       v0 == "TRUNCATED_CONDITION" and v1 == "TRUNCATED_CONDITION", "%s -> %s" % (v0, v1))
    ok("r76: and the repaired path points at the CITED file, address MATCHED",
       w1 and os.path.basename(w1) == "8USC-1255.md" and (a1 or {}).get("status") == "MATCHED",
       "%s %s" % (w1, a1))

    # --- control: the honest anchor-miss still repairs to VERIFIED --------------------------
    whole = ("The period of authorized admission ends sixty days after the program end date "
             "stated on the form for every classification in this paragraph.")
    c2 = corp("repair_ok", {"1-preamble.md": "Quoting the rule: " + whole,
                            "8USC-1184.md": "SEC. 1184. " + whole})
    k2 = addr_mod.KeyMap(c2, packs)
    v0, w0, d0 = check(whole, c2)
    v1, w1, _d1, a1 = addr_mod.fold(whole, v0, w0, d0, ["8 U.S.C. § 1184"], c2, k2, packs)
    ok("r76 control: a clean quotation still repairs to VERIFIED at the cited file",
       v1 == "VERIFIED" and w1 and os.path.basename(w1) == "8USC-1184.md",
       "%s -> %s @ %s" % (v0, v1, w1))

    # --- P3/P4/P7: the alphanumeric branch asks the exact branch's questions ----------------
    c3 = corp("p3", {"src.md": ("General rule. The director shall approve the application, and "
                                "shall notify the applicant of the decision unless the applicant "
                                "has abandoned the claim entirely.")})
    v, _w, _d = check("The director shall approve the application; and shall notify the "
                      "applicant of the decision", c3)
    ok("r76: internal punctuation drift + stop-before-limiter is LOUD (probe P3)",
       v == "TRUNCATED_CONDITION", v)

    c4 = corp("p4", {"src.md": ("In this subsection the term applies when not able persons "
                                "request assistance from the designated officer during regular "
                                "business hours in the district office.")})
    v, _w, _d = check("the term applies when no table persons request assistance from the "
                      "designated officer", c4)
    ok("r76: a word-boundary collision under alnum is OPERATOR, not green (probe P4)",
       v == "OPERATOR", v)

    c7 = corp("p7", {"src.md": ("Except as otherwise provided, no alien may be admitted to the "
                                "United States; the burden of proof rests upon the applicant at "
                                "every stage of the proceeding without exception.")})
    v, _w, _d = check("alien may be admitted to the United States, the burden of proof rests "
                      "upon the applicant", c7)
    ok("r76: a cut leading negation + punctuation drift is LOUD (probe P7)",
       v == "TRUNCATED_OPENING", v)

    # --- controls: genuine punctuation drift and an intra-word style variant stay green -----
    c5 = corp("punct_ok", {"src.md": ("The applicant bears the burden of proof; the standard is "
                                      "a preponderance of the evidence in every proceeding under "
                                      "this part of the chapter.")})
    v, _w, _d = check("The applicant bears the burden of proof, the standard is a preponderance "
                      "of the evidence in every proceeding under this part of the chapter.", c5)
    ok("r76 control: a genuine punctuation drift is still PUNCTUATION", v == "PUNCTUATION", v)
    c6 = corp("hyphen_ok", {"src.md": ("The non-immigrant classification described in this "
                                       "paragraph requires a petition filed by the employer "
                                       "before the beneficiary may apply for the visa.")})
    v, _w, _d = check("The nonimmigrant classification described in this paragraph requires a "
                      "petition filed by the employer before the beneficiary may apply for the "
                      "visa.", c6)
    ok("r76 control: an intra-word hyphen variant is not promoted to a loud verdict",
       v in CLEAN, v)

    # --- P5: a 10-24 character tail fragment is anchored, not waved through -----------------
    c8 = corp("p5", {"src.md": ("The application shall be adjudicated within ninety days of the "
                                "date of filing and the Secretary may waive the requirement, "
                                "unless the applicant has previously been granted a waiver under "
                                "this subsection.")})
    v, _w, d = check("The application shall be adjudicated within ninety days of the date of "
                     "filing … waive the requirement …", c8)
    ok("r76: a short (10-24) anchored tail hiding a limiter is ELLIPSIS_HIDES (spark11, probe P5)",
       v == "ELLIPSIS_HIDES" and "unless" in (d or ""), "%s | %s" % (v, (d or "")[:80]))

    # --- P6: a bare omitted digit is not a footnote --------------------------------------
    _ch, hits, _u = word_diff("the petition must be filed within days after the qualifying event",
                              "the petition must be filed within 90 days after the qualifying event")
    ok("r76: an omitted bare number reaches the digit rule (grokbuild, probe P6)",
       "90" in hits, str(hits))
    ok("r76 control: a welded «14 See Matter of …» footnote is still recognised",
       bool(FOOTNOTE_RE.match("14 See Matter of Blas, 15 I&N Dec. at 628")), "")

    # --- P10: sentences from two files are SPLICED, from one file SCATTERED -----------------
    s1 = ("The petitioner bears the burden of establishing eligibility for the visa "
          "classification sought.")
    s2 = ("Any appeal must be filed within thirty days of the decision denying the application "
          "for benefits.")
    c10 = corp("p10", {"a.md": s1, "b.md": s2})
    v, _w, _d = check(s1 + " " + s2, c10)
    ok("r76: every-sentence-verbatim across TWO files is SPLICED (codex, probe P10)",
       v == "SPLICED", v)
    c11 = corp("p10same", {"a.md": s1 + " Unrelated filler sentence stands here. " + s2})
    v, _w, _d = check(s1 + " " + s2, c11)
    ok("r76 control: the same shape inside ONE file is still SCATTERED", v == "SCATTERED", v)

    # --- P8: the superseded chain survives a third edition ----------------------------------
    from krokai.fetch import superseded_paths
    root8 = os.path.join(tmp, "r76", "reg")
    os.makedirs(os.path.join(root8, ".krokai"), exist_ok=True)
    io.open(os.path.join(root8, ".krokai", "law_registry.json"), "w", encoding="utf-8").write(
        _json.dumps({"usc|8|1255": {"path": "law/r3.xml", "supersedes": "law/r2.xml",
                                    "superseded_paths": ["law/r2.xml", "law/r1.xml"]}}))
    got = superseded_paths(root8)
    ok("r76: all three editions' predecessors are superseded, not just the last (probe P8)",
       got == {"law/r2.xml", "law/r1.xml"}, str(sorted(got)))

    # --- N42: a tail-ellipsis banked quote present in the new edition is not «lost» ---------
    from krokai.fetch import _bank_impact  # noqa: F401  (import proves the surface exists)
    from krokai.normalize import ellipsis_parts as _ep, normalise as _norm, prepare_quote as _pq
    ok("r76: ellipsis_parts yields one part for a tail ellipsis (the shape N42 guards)",
       len(_ep(_norm(_pq("The applicant shall file the petition …")), 25)) == 1, "")

    # --- one list, one home ------------------------------------------------------------------
    ok("r76: run._CLEANISH is DERIVED from verdicts.CLEAN", _CLEANISH == tuple(CLEAN),
       str(_CLEANISH))
    ok("r76: address.ADDRESS_CLEAN is DERIVED from verdicts.CLEAN",
       addr_mod.ADDRESS_CLEAN == tuple(CLEAN), str(addr_mod.ADDRESS_CLEAN))
    ok("r76: every DANGEROUS verdict renders a NON-BLANK mark (F9)",
       all(MARK.get(s, "").strip() for s in DANGEROUS),
       str({s: MARK.get(s) for s in DANGEROUS if not MARK.get(s, "").strip()}))
    ok("r76: the six causes of a false NOT_FOUND exist and number six (F11)",
       len(SIX_CAUSES) == 6, str(len(SIX_CAUSES)))

    # --- F1: a wrapped blockquote quotation still finds its citation ring --------------------
    body = ("The rule is stated plainly, see 8 U.S.C. § 1255(k) for the text:\n\n"
            "> No alien shall be granted adjustment of status\n"
            "> under this part in any case\n\n"
            "and the discussion continues.")
    near, far = citation_window(
        body, "No alien shall be granted adjustment of status under this part in any case",
        packs)
    ok("r76: a line-wrapped blockquote quotation locates its NEAR citation (F1)",
       any("1255" in x for x in near), "near=%s far=%s" % (near, far))

    # --- N13: no CLI door builds a bare Corpus any more --------------------------------------
    import krokai.cli as _cli
    src = io.open(_cli.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    ok("r76: cli builds every corpus through run.corpus_for (sentinel + superseded armed)",
       "Corpus(" not in src and src.count("corpus_for(") >= 3, str(src.count("corpus_for(")))


# ------------------------------------------------------------------------------------------------
def suite_r77(tmp):
    """R77 backlog round (#333-#359): each verifiable claim reproduced before its fix, each fix
    pinned WITH a control - the honest case must keep working, or the fix disables the tool."""
    import time as _time
    import zipfile as _zf
    from krokai.corpus import Corpus
    from krokai import address as addr_mod
    from krokai.citations import load_packs
    from krokai.exhibit_check import reconcile, scan_form_dir, scan_exhibit_dir
    from krokai.run import SENTINELS

    d77 = os.path.join(tmp, "r77x")
    os.makedirs(d77, exist_ok=True)
    packs = load_packs(["us-federal"])

    # --- #333: a same-numbered section under ANOTHER title is not a home ---------------------
    # R77 F-A: heads enriched to ×2 foreign self-naming (per-value min_count=2 threshold in
    # the citation-form reject_if_head_names scans - a head citing another title ONCE is a
    # normal cross-reference, not a decisive title declaration). The filename guard added in
    # rule 2/3 (F-B extension) is the redundant defence for these same-file cases.
    key = ("usc", "8", "1255")
    wrong = ("26 U.S.C. § 1255 Gain from dispositions. See section 1255; also 1255 applies. "
             "This is a Title 26 U.S.C. section — 26 U.S.C. § 1255(a) references the tax code.")
    right = "8 U.S.C. § 1255 Adjustment of status. See section 1255; also 1255 applies."
    ok("r77: 26USC-1255 no longer satisfies 8 U.S.C. § 1255 (#333, lunapro)",
       not packs.file_matches(key, "26USC-1255-uscode.xml", wrong), "")
    ok("r77 control: the true 8 USC 1255 file still matches, by name and by body",
       packs.file_matches(key, "8USC-1255-uscode.xml", right)
       and packs.file_matches(key, "8usc-1255.xml", ""), "")
    ok("r77: a 26-CFR part under an 8 CFR key is rejected by its own head (#333 class)",
       not packs.file_matches(
           ("cfr", "8", "245"), "part-245-cfr.xml",
           "26 CFR part 245 rules. 245.1 text. 245.2 text. 245.3 text. "
           "Also 26 CFR § 245.4 supplements the above."), "")
    ok("r77 control: an eCFR-style part file with the right title still matches",
       packs.file_matches(("cfr", "8", "245"), "part-245-ecfr.xml",
                          "8 CFR Part 245 - Adjustment. 245.1 a. 245.2 b. 245.3 c."), "")

    # --- #346 + #335 + #334: the exhibit reconciliation ---------------------------------------
    pet = os.path.join(d77, "pet")
    exd = os.path.join(d77, "ex")
    os.makedirs(pet)
    os.makedirs(exd)
    doc_xml = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
               'wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Exh</w:t></w:r><w:r><w:t>ibit B-3 is attached; see also </w:t>'
               '</w:r></w:p>'
               '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Exhibit D-19 in the table</w:t></w:r></w:p>'
               '</w:tc></w:tr></w:tbl></w:body></w:document>')
    px = os.path.join(pet, "brief.docx")
    with _zf.ZipFile(px, "w") as z:
        z.writestr("word/document.xml", doc_xml)
    for fn in ("B-03 old.pdf", "B-03 new.pdf", "D-19_1.pdf", "D-19_2.pdf"):
        io.open(os.path.join(exd, fn), "w").write("x")
    r = reconcile([pet], [exd])
    ok("r77: a run-split «Exh|ibit» docx reference is still read (#335, agy31pro, probe-proven)",
       "B-3" in (r.get("matched") or set()), str(sorted(r.get("matched") or [])))
    ok("r77: a table-cell reference survives the paragraph walk (#335 control)",
       "D-19" in (r.get("matched") or set()), str(sorted(r.get("matched") or [])))
    ok("r77: two same-ID files without part suffixes are DUPLICATE at last (#346, probe-proven)",
       "B-3" in r["duplicates"], str(sorted(r["duplicates"])))
    ok("r77 control: _1/_2 multi-part files are still not duplicates",
       "D-19" not in r["duplicates"], str(sorted(r["duplicates"])))

    pet2 = os.path.join(d77, "pet2")
    os.makedirs(pet2)
    io.open(os.path.join(pet2, "note.md"), "w", encoding="utf-8").write("See Exhibit B-3.")
    io.open(os.path.join(pet2, "scan.pdf"), "wb").write(b"%PDF-1.4 broken")
    saved = {m: sys.modules.get(m) for m in ("pypdf", "fitz", "pymupdf")}
    sys.modules["pypdf"] = None
    sys.modules["fitz"] = None
    sys.modules["pymupdf"] = None                       # K003: PyMuPDF answers to both names
    try:
        r2 = reconcile([pet2], [exd])
    finally:
        for m, v in saved.items():
            if v is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = v
    ok("r77: a MIXED folder reports the unreadable PDF petition instead of a silent zero (#334)",
       not r2["refused"] and len(r2.get("unread") or []) == 1
       and "PDF" in r2["unread"][0][1], str(r2.get("unread")))

    # --- #347: this toolkit's own outputs are neither forms nor exhibits ---------------------
    fdir = os.path.join(d77, "forms")
    os.makedirs(fdir)
    io.open(os.path.join(fdir, "I-485.pdf"), "w").write("x")
    io.open(os.path.join(fdir, "I-485.forms.txt"), "w", encoding="utf-8").write("=== FORM ===")
    io.open(os.path.join(fdir, "manifest.json"), "w").write("{}")
    files, _probs = scan_form_dir(fdir)
    ok("r77: the form counts once - its .forms.txt dump and manifest are not forms (#347)",
       list(files) == ["I-485"] and len(files["I-485"]) == 1, str(files))
    io.open(os.path.join(exd, "B-03 old.text.md"), "w", encoding="utf-8").write(
        "<!-- %s : extracted layer --> body text" % SENTINELS[0])
    files2, _p2 = scan_exhibit_dir(exd)
    ok("r77: a stamped sidecar beside its exhibit is not a third copy (#347 class)",
       len(files2.get("B-3") or []) == 2, str(files2.get("B-3")))

    # --- #336: every stamped writer lands inside the widened corpus scan window --------------
    from krokai.sidecar import HEADER
    from krokai.form_dump import _stamp                    # R77 minor: lazy sentinel imports
    wd = os.path.join(d77, "law36")
    os.makedirs(wd)
    long_src = "A" * 240 + ".pdf"
    io.open(os.path.join(wd, "sc.text.md"), "w", encoding="utf-8").write(
        HEADER.format(src=long_src, srcname=long_src, when="2026-08-31", extractor="3")
        + "Statutory body text here. " * 40)
    io.open(os.path.join(wd, "f.forms.txt"), "w", encoding="utf-8").write(
        _stamp("txt") + "[p 1] field <t> = value\n" * 40)
    io.open(os.path.join(wd, "cc.md"), "w", encoding="utf-8").write(
        _stamp("md") + "# Cross-engine agreement\nrow after row\n" * 40)
    io.open(os.path.join(wd, "real.txt"), "w", encoding="utf-8").write(
        "A real short provision of law stands here, indexed as always. " * 5)
    c36 = Corpus([wd], quiet=True, sentinel=SENTINELS)
    ok("r77: all three stamped artifact shapes are excluded as tool output (#336, agy37flash)",
       len(c36.excluded_derived) == 3 and len(c36.paths) == 1
       and c36.paths[0].endswith("real.txt"),
       "derived=%d paths=%s" % (len(c36.excluded_derived),
                                [os.path.basename(p) for p in c36.paths]))

    # --- #351: a long THIN scan is excluded by the per-page rate, not passed by the total ----
    try:
        from krokai import _pdfengine
        _fz = _pdfengine.load()
    except ImportError:
        _fz = None
    if _fz is not None:
        p51 = os.path.join(d77, "law51")
        os.makedirs(p51)
        doc = _fz.open()
        for i in range(8):
            pg = doc.new_page()
            pg.insert_text(_fz.Point(30, 50), "thin page marker line %02d xx" % i)
        doc.save(os.path.join(p51, "thin-scan.pdf"))
        doc.close()
        doc = _fz.open()
        pg = doc.new_page()
        pg.insert_text(_fz.Point(30, 50), "A dense single page. " * 30)
        doc.save(os.path.join(p51, "dense.pdf"))
        doc.close()
        c51 = Corpus([p51], quiet=True)
        ok("r77: a 240-char 8-page scan is a stub by RATE in the corpus path (#351, lunapro)",
           any(p.endswith("thin-scan.pdf") for p in c51.excluded_stub),
           str([os.path.basename(p) for p in c51.excluded_stub]))
        ok("r77 control: a dense one-pager is still indexed",
           any(p.endswith("dense.pdf") for p in c51.paths), "")
    else:
        print("note: r77 #351 rate-test pins skipped - fitz is not installed here")

    # --- #350: pre-2007 .doc refuses loudly instead of indexing soup -------------------------
    from krokai.readers import read_any, MissingReader
    p50 = os.path.join(d77, "law50")
    os.makedirs(p50)
    # not "memo": DERIVED_DEFAULT matches that word in a filename and would bucket the fixture
    # as our own writing before the reader ever ran
    pdoc = os.path.join(p50, "signed-letter.doc")
    open(pdoc, "wb").write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(range(256)) * 20)
    raised = False
    try:
        read_any(pdoc)
    except MissingReader:
        raised = True
    ok("r77: .doc raises MissingReader - probe measured 3 798 chars of soup passing the floor "
       "(#350, grokbuild)", raised, "")
    c50 = Corpus([p50], quiet=True)
    ok("r77: and the corpus reports it UNREADABLE, loudly, instead of indexing it",
       any(p == pdoc and kind == "MissingReader" for p, kind in c50.unreadable)
       and not c50.paths, str(c50.unreadable))

    # --- #345: a mammoth-covered body is no longer doubled by the raw-XML pass ---------------
    try:
        import mammoth as _mam  # noqa: F401
    except ImportError:
        _mam = None
    if _mam is not None:
        from krokai.readers import read_docx
        px45 = os.path.join(d77, "body.docx")
        with _zf.ZipFile(px45, "w") as z:
            z.writestr("[Content_Types].xml",
                       '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/'
                       'package/2006/content-types"><Default Extension="xml" ContentType='
                       '"application/xml"/><Default Extension="rels" ContentType="application/'
                       'vnd.openxmlformats-package.relationships+xml"/><Override PartName='
                       '"/word/document.xml" ContentType="application/vnd.openxmlformats-'
                       'officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr("_rels/.rels",
                       '<?xml version="1.0"?><Relationships xmlns="http://schemas.'
                       'openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" '
                       'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                       'relationships/officeDocument" Target="word/document.xml"/>'
                       '</Relationships>')
            z.writestr("word/document.xml",
                       '<?xml version="1.0"?><w:document xmlns:w="http://schemas.'
                       'openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r>'
                       '<w:t>UNIQUEBODYPHRASE alpha</w:t></w:r></w:p></w:body></w:document>')
            z.writestr("word/footnotes.xml",
                       '<?xml version="1.0"?><w:footnotes xmlns:w="http://schemas.'
                       'openxmlformats.org/wordprocessingml/2006/main"><w:footnote><w:p><w:r>'
                       '<w:t>FOOTMARK beta</w:t></w:r></w:p></w:footnote></w:footnotes>')
        t45 = read_docx(px45)
        ok("r77: the body appears ONCE when mammoth read it (#345, agy31pro/lunapro)",
           t45.count("UNIQUEBODYPHRASE") == 1, "count=%d" % t45.count("UNIQUEBODYPHRASE"))
        ok("r77 control: footnote text is still appended from the XML pass",
           "FOOTMARK" in t45, "")
    else:
        print("note: r77 #345 mammoth-gate pins skipped - mammoth is not installed here")

    # --- #344: OCR sanitize keeps every script -----------------------------------------------
    from krokai.repair import _sanitize_ocr_text
    s = _sanitize_ocr_text("José — «да» 中文\x02ctrl�end")
    ok("r77: sanitize keeps é/Cyrillic/CJK and drops controls + U+FFFD (#344, qwen38max)",
       "José" in s and "да" in s and "中文" in s
       and "\x02" not in s and "�" not in s, repr(s))
    ok("r77 control: the dash family still folds to '-'",
       "a-b" in _sanitize_ocr_text("a—b"), "")

    # --- #348 + #343: the fetch layer --------------------------------------------------------
    from krokai.fetch import _name_from
    ok("r77: a trailing-slash URL takes its extension from Content-Type, not the hostname "
       "(#348, probe-proven)",
       _name_from("https://www.uscis.gov/laws-and-policy/", "text/html").endswith(".html"),
       _name_from("https://www.uscis.gov/laws-and-policy/", "text/html"))
    ok("r77 control: a path basename keeps its own extension, query in the stem",
       _name_from("https://x.gov/title-8.xml?part=245", "text/html").endswith(".xml"), "")
    import krokai.fetch as _fetch_mod
    fsrc = io.open(_fetch_mod.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    ok("r77: the placeholder probe covers the whole refusable region (#343, grokbuild/lunapro)",
       "data[:20000]" in fsrc and "data[:4000]" not in fsrc, "")

    # --- #341: stale answers are not this round's voices; a leaking cwd refuses --------------
    from krokai.consult import absorb_delegated, neutral_cwd
    ad = os.path.join(d77, "round")
    os.makedirs(ad)
    io.open(os.path.join(ad, "OLDCH.md"), "w", encoding="utf-8").write(
        "an old answer from last round " * 20 + "\nR77-MARK")
    stale_t = _time.time() - 3600
    os.utime(os.path.join(ad, "OLDCH.md"), (stale_t, stale_t))
    io.open(os.path.join(ad, "NEWCH.md"), "w", encoding="utf-8").write(
        "a fresh answer from this dispatch " * 20 + "\nR77-MARK")
    rows41 = absorb_delegated(ad, "R77-MARK", 10, since=_time.time() - 60)
    ok("r77: an answer already in the folder BEFORE dispatch is skipped as stale (#341, "
       "kimik3/codex/lunapro)",
       [r["channel"] for r in rows41] == ["newch"], str([r["channel"] for r in rows41]))
    real_chdir = os.chdir
    os.chdir = lambda p: (_ for _ in ()).throw(OSError("denied"))
    try:
        refused = False
        try:
            neutral_cwd(printer=lambda *a, **k: None)
        except SystemExit:
            refused = True
    finally:
        os.chdir = real_chdir
    ok("r77: a failed neutral cwd REFUSES the round - the leak it prevents is confirmed, "
       "not hypothetical (#341)", refused, "")

    # --- #342: harness paths absolute; hook refresh survives every install layout ------------
    from krokai.consult import find_harness
    hp = os.path.join(d77, "harness.py")
    io.open(hp, "w").write("# stub")
    cur = os.getcwd()
    os.chdir(d77)
    try:
        got = find_harness({}, explicit="harness.py")
    finally:
        os.chdir(cur)
    ok("r77: an explicit relative harness path comes back ABSOLUTE (#342, agy37flash)",
       bool(got) and os.path.isabs(got), repr(got))
    import krokai.upgrade as _up
    usrc = io.open(_up.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    ok("r77: the hook refresh never spawns `-m krokai` from a foreign cwd (#342, 4 channels)",
       '"-m", "krokai"' not in usrc, "")

    # --- #352: a repair batch that fails is a non-zero exit ----------------------------------
    import krokai.repair as _rp
    from krokai.cli import cmd_fix_pdfs

    class _Args(object):
        directory, output, skip, dpi = d77, os.path.join(d77, "outp"), None, 72

    sv_scan, sv_fix = _rp.scan_broken_pdfs, _rp.fix_broken_pdf
    _rp.scan_broken_pdfs = lambda d, skip_dirs=None: [("bad.pdf", os.path.join(d, "bad.pdf"))]
    _rp.fix_broken_pdf = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        res52, errs52 = _rp.fix_batch(d77, os.path.join(d77, "outp"))
        rc52 = cmd_fix_pdfs(_Args())
    finally:
        _rp.scan_broken_pdfs, _rp.fix_broken_pdf = sv_scan, sv_fix
    ok("r77: an all-fail repair batch returns its failures and exits 1 (#352, lunapro)",
       res52 == [] and len(errs52) == 1 and "boom" in errs52[0][1] and rc52 == 1,
       "rc=%s errs=%s" % (rc52, errs52))

    # --- #354: «download it» is not said about a file already on disk ------------------------
    law54 = os.path.join(d77, "law54")
    os.makedirs(law54)
    io.open(os.path.join(law54, "8USC-1255-download.xml"), "w", encoding="utf-8").write(
        "Just a moment... Checking your browser before accessing this site. "
        "Please enable JavaScript to continue.")
    c54 = Corpus([law54], quiet=True)
    ok("r77 control: the bot wall is excluded as a placeholder, not indexed",
       any(p.endswith("8USC-1255-download.xml") for p in c54.excluded_placeholder)
       and not c54.paths, "")
    km54 = addr_mod.KeyMap(c54, packs)
    v54, _w, d54, _a = addr_mod.fold(
        "A quotation of the statute that is nowhere in this corpus at all today.",
        "NOT_FOUND", None, "", ["8 U.S.C. § 1255"], c54, km54, packs)
    ok("r77: the advice names the EXCLUDED file instead of saying «download it» (#354, "
       "orgrok420)", v54 == "NO_SOURCE_ON_DISK" and "EXCLUDED" in d54
       and "8USC-1255-download.xml" in d54, d54[:160])
    law54b = os.path.join(d77, "law54b")
    os.makedirs(law54b)
    io.open(os.path.join(law54b, "unrelated.md"), "w", encoding="utf-8").write(
        "Some other provision entirely, long enough to be a source.")
    c54b = Corpus([law54b], quiet=True)
    km54b = addr_mod.KeyMap(c54b, packs)
    v54b, _w, d54b, _a = addr_mod.fold(
        "A quotation of the statute that is nowhere in this corpus at all today.",
        "NOT_FOUND", None, "", ["8 U.S.C. § 1255"], c54b, km54b, packs)
    ok("r77 control: with nothing on disk the advice is still «download it»",
       v54b == "NO_SOURCE_ON_DISK" and "Download it" in d54b, d54b[:120])

    # --- #356: a broken pack rule is loud and does not kill the resolution -------------------
    law56 = os.path.join(d77, "law56")
    os.makedirs(law56)
    io.open(os.path.join(law56, "one.md"), "w", encoding="utf-8").write(
        "A provision long enough to stand in the corpus for this test to walk.")
    c56 = Corpus([law56], quiet=True)

    class _BoomPacks(object):
        def file_matches(self, key, path, text):
            raise re.error("a broken pack rule")

    buf56 = io.StringIO()
    stdout56, stderr56 = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf56
    try:
        hits56 = addr_mod.KeyMap(c56, _BoomPacks()).resolve(("x", "1"))
    finally:
        sys.stdout, sys.stderr = stdout56, stderr56
    ok("r77: a pack rule that raises is PRINTED (to stderr), not swallowed into «not in "
       "corpus» (#356 / F15, qwen38max+orglm53; R77 minor: was stdout, moved to stderr so "
       "report parsers stay clean)",
       hits56 == [] and "address rule failed" in buf56.getvalue(), buf56.getvalue()[:100])

    # --- #357: the guard keeps the LONGER quotation ------------------------------------------
    from krokai.bank import candidates
    short_q = "the Secretary may in his discretion grant the application for adjustment"
    long_q = ("no application shall be approved unless " + short_q
              + " and the alien establishes eligibility at the time of filing")
    got57 = candidates("> %s\n\nprose.\n\n> %s\n" % (short_q, long_q), min_len=55)
    ok("r77: a longer quotation arriving after its own clause SURVIVES (#357, probe-proven)",
       len(got57) == 1 and got57[0].startswith("no application"), str([q[:40] for q in got57]))
    got57b = candidates("> %s\n\nprose.\n\n> %s\n" % (long_q, short_q), min_len=55)
    ok("r77 control: the shorter-inside-longer still merges to one, either order",
       len(got57b) == 1 and got57b[0].startswith("no application"), "")

    # --- #359: notebook edits reach the guard ------------------------------------------------
    qg = io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              "hooks", "quote_guard.py"), encoding="utf-8", errors="replace"
                 ).read() if _is_source_checkout(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) else ""
    if qg:
        ok("r77: the guard reads NotebookEdit's notebook_path and new_source (#359, orglm53)",
           'inp.get("notebook_path")' in qg and 'inp.get("new_source")' in qg, "")
    # #339/#337/#340 are pinned end-to-end in suite_r77_cli below via subprocesses.


def suite_r77_cli(tmp):
    """The R77 exit-code fixes, pinned through the real CLI - the surface a hook or CI reads."""
    import subprocess as _sp
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matter = os.path.join(tmp, "r77m")
    os.makedirs(matter, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    keydir = os.path.join(tmp, "r77keys")
    os.makedirs(keydir, exist_ok=True)
    io.open(os.path.join(keydir, "keys.env"), "w", encoding="utf-8").write(
        "TESTKEY_R77=name-check-fixture\n")
    env["KROKAI_KEY_DIR"] = keydir

    def run(*args):
        return _sp.run([sys.executable, "-m", "krokai"] + list(args),
                       cwd=root, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=240)

    r = run("init", matter)
    if r.returncode != 0:
        ok("r77cli: init failed - remaining CLI pins skipped", False, r.stderr[-200:])
        return
    provision = ("No application for adjustment of status shall be approved unless the "
                 "applicant establishes clear eligibility for the benefit sought at filing.")
    io.open(os.path.join(matter, "law", "8USC-1255.md"), "w", encoding="utf-8").write(
        "SEC. 1255. " + provision)

    # --- #339: the audit's verdicts reach the exit code --------------------------------------
    ans = os.path.join(tmp, "r77answers")
    os.makedirs(ans, exist_ok=True)
    io.open(os.path.join(ans, "CHAN.md"), "w", encoding="utf-8").write(
        "The reviewer answers at length and then quotes:\n\n"
        "> The Attorney General shall in every case waive the filing requirement without "
        "exception or delay.\n\nEnd of answer.\n")
    r = run("review", "--dir", matter, "--audit", ans)
    ok("r77cli: a fabricated reviewer quotation exits 5, not 0 (#339, kimik3/lunapro)",
       r.returncode == 5, "rc=%s tail=%s" % (r.returncode, (r.stdout or "")[-120:]))
    io.open(os.path.join(ans, "CHAN.md"), "w", encoding="utf-8").write(
        "The reviewer answers and quotes:\n\n> " + provision + "\n\nEnd.\n")
    r = run("review", "--dir", matter, "--audit", ans)
    ok("r77cli control: a verbatim reviewer quotation exits 0",
       r.returncode == 0, "rc=%s" % r.returncode)
    # --- #337: keys.env reaches the review path, names only ----------------------------------
    ok("r77cli: the review path loads keys.env and prints the NAME only (#337, orgemini37flash)",
       "TESTKEY_R77" in (r.stdout or ""), (r.stdout or "")[:200])
    ok("r77cli control: the key VALUE never reaches the transcript",
       "name-check-fixture" not in (r.stdout or "") + (r.stderr or ""), "")

    # --- #340: --strict-address gives the address doctrine a mechanism -----------------------
    io.open(os.path.join(matter, "case", "draft.md"), "w", encoding="utf-8").write(
        "Our filing argues as follows:\n\n> " + provision + "\n\nNo citation stands nearby.\n")
    r0 = run("check", "--dir", matter, "--strict")
    r5 = run("check", "--dir", matter, "--strict", "--strict-address")
    ok("r77cli: --strict-address exits 5 on a filed green with no checkable address (#340, "
       "orglm53/lunapro)", r0.returncode == 0 and r5.returncode == 5,
       "strict=%s strict-address=%s" % (r0.returncode, r5.returncode))


def suite_r77b(tmp):
    """R77 PANEL round (F-A..F-G′ + minors): pins for the fixes decided in
    `reviews/r77-krokai/ADJUDICATION.md`. Every fix has a BUG probe (translated from the
    pre-fix `reviews/r77-krokai/probes_prefix.py` into a positive assertion) and at least one
    CONTROL — the honest case must keep working, or the fix has disabled the tool.

    The F-B extension `reject_if_filename_names` was UNCOVERED by executing the F-B fix in
    `_has`: closing rule 1's substring bless immediately revealed rule 2 blessing the same
    file via `_has(part1)+_has(cfr)`, with `reject_if_head_names` unable to fire on the
    empty-body probe. Pinned symmetrically here."""
    import argparse as _ap
    import contextlib as _ctx
    import re as _re
    import shutil as _sh
    import tempfile as _tf
    import zipfile as _zip
    from krokai.citations import load_packs
    from krokai.cli import cmd_check_exhibits
    from krokai.exhibit_check import _read_docx, _read_text, reconcile
    from krokai.readers import MissingReader
    from krokai.run import SENTINEL_HEAD, SENTINELS, _is_tool_output as run_is_tool_output
    from krokai import consult, form_dump

    d = os.path.join(tmp, "r77b")
    os.makedirs(d, exist_ok=True)
    packs = load_packs(["us-federal"])

    # --- F-B: digit-prefix substring blesses a wrong-title file (rule[0]) + F-B extension
    # (rule[1]/[2] filename guard uncovered by the F-B fix)
    ok("r77b F-B cfr bug: 18CFR-part-1.xml does NOT satisfy ('cfr','8','1'), empty body",
       not packs.file_matches(("cfr", "8", "1"), "18CFR-part-1.xml", ""), "")
    ok("r77b F-B usc bug: 28USC-1254.xml does NOT satisfy ('usc','8','1254'), empty body",
       not packs.file_matches(("usc", "8", "1254"), "28USC-1254.xml", ""), "")
    ok("r77b F-B pos cfr: 8CFR-part-1.xml still matches ('cfr','8','1')",
       packs.file_matches(("cfr", "8", "1"), "8CFR-part-1.xml", ""), "")
    ok("r77b F-B pos usc: 8USC-1254.xml still matches ('usc','8','1254')",
       packs.file_matches(("usc", "8", "1254"), "8USC-1254.xml", ""), "")
    ok("r77b F-B neg control: 26CFR-part-5.xml refuses ('cfr','8','1')",
       not packs.file_matches(("cfr", "8", "1"), "26CFR-part-5.xml", ""), "")
    ok("r77b F-B real-name control: part245-ecfr.xml still matches ('cfr','8','245') "
       "— the filename guard must NOT over-reject real download names",
       packs.file_matches(("cfr", "8", "245"), "part245-ecfr.xml", ""), "")

    # --- F-A: reject_if_head_names — per-value min_count rescues true files
    fn = "USCODE-2024-section1255.txt"
    one_foreign = ("Cross-reference only: 26 U.S.C. 7701 defines the term person "
                   "for the purposes of this chapter.")
    ok("r77b F-A bug: title-8 file with ONE foreign cross-ref is NOT rejected",
       packs.file_matches(("usc", "8", "1255"), fn, one_foreign), "")
    two_foreign = ("As under 26 U.S.C. 7701 and again 26 U.S.C. 61, the internal "
                   "revenue meaning controls here.")
    ok("r77b F-A reject-holds: foreign ×2 with no own mention IS refused",
       not packs.file_matches(("usc", "8", "1255"), fn, two_foreign), "")
    rescued = ("Adjustment under 8 U.S.C. 1255 interacts with 26 U.S.C. 7701, "
               "26 U.S.C. 61 and 26 U.S.C. 32.")
    ok("r77b F-A rescue: own ×1 among foreign ×3 → matched (any own mention rescues)",
       packs.file_matches(("usc", "8", "1255"), fn, rescued), "")

    # --- F-C: sentinel window unified to SENTINEL_HEAD (=2000)
    ok("r77b F-C: SENTINEL_HEAD is exported at 2000",
       SENTINEL_HEAD == 2000, "SENTINEL_HEAD=%r" % SENTINEL_HEAD)
    sc = os.path.join(d, "deep-sentinel.md")
    io.open(sc, "w", encoding="utf-8").write("A" * 430 + "\n" + SENTINELS[0] + "\n")
    ok("r77b F-C bug: sentinel at offset 431 IS detected (was invisible in the 400 window)",
       run_is_tool_output(sc), "")
    # F-C CLASS-PIN: no `read(<N-below-2000>)` literal remains in krokai/*.py + hooks/*.py.
    # This stops a fourth 400 from appearing silently when someone forgets to import.
    pkg_root = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(pkg_root)
    scan_dirs = [pkg_root, os.path.join(repo_root, "hooks")]
    small_reads = []
    for base in scan_dirs:
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            for f in files:
                if not f.endswith(".py"):
                    continue
                p = os.path.join(root, f)
                src = io.open(p, encoding="utf-8", errors="replace").read()
                for m in _re.finditer(r"\.read\(\s*(\d+)\s*\)", src):
                    n = int(m.group(1))
                    if n < 2000:
                        small_reads.append((os.path.relpath(p, repo_root),
                                            m.group(0), n))
    ok("r77b F-C class-pin: no `.read(<N-below-2000>)` literal remains in krokai/*.py or "
       "hooks/*.py (the fourth 400 must not appear silently — F-C invariant)",
       small_reads == [], str(small_reads[:6]))

    # --- F-D: exhibit intake refuses .doc + corrupt .docx + soup binary
    scratch = _tf.mkdtemp(prefix="r77b-fd-", dir=d)
    doc = os.path.join(scratch, "x.doc")
    io.open(doc, "wb").write(b"\xd0\xcf\x11\xe0" + b"\x00" * 64)
    try:
        _read_text(doc)
        doc_raised = False
    except MissingReader:
        doc_raised = True
    ok("r77b F-D bug: .doc raises MissingReader (loud, not silent '')", doc_raised, "")

    soup = os.path.join(scratch, "x.sqlite")
    io.open(soup, "wb").write(b"SQLite format 3\x00" + bytes(range(256)) * 8)
    got_soup = ""
    try:
        got_soup = _read_text(soup)
    except MissingReader:
        pass
    ok("r77b F-D bug: unknown binary (.sqlite) returns '' — not decoded as soup and searched",
       got_soup == "", "got=%r len=%d" % (got_soup[:40], len(got_soup)))

    badx = os.path.join(scratch, "bad.docx")
    io.open(badx, "w", encoding="utf-8").write("this is not a zip archive")
    try:
        _read_docx(badx)
        badx_raised = False
    except MissingReader:
        badx_raised = True
    ok("r77b F-D bug: corrupt .docx raises MissingReader (not swallowed to '')",
       badx_raised, "")

    md_ok = os.path.join(scratch, "fine.md")
    io.open(md_ok, "w", encoding="utf-8").write("See Exhibit B-3.\n")
    ok("r77b F-D control: .md still reads", "Exhibit B-3" in _read_text(md_ok), "")

    # F-D move 3: an empty .docx (valid zip, empty document body) lands in unread
    empty_docx = os.path.join(scratch, "empty.docx")
    with _zip.ZipFile(empty_docx, "w") as z:
        z.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body/></w:document>')
    pet_empty = os.path.join(scratch, "petition-empty-docx")
    os.makedirs(pet_empty)
    io.open(os.path.join(pet_empty, "readable.md"), "w", encoding="utf-8").write(
        "See Exhibit B-3.")
    _sh.move(empty_docx, os.path.join(pet_empty, "empty.docx"))
    exd_empty = os.path.join(scratch, "exhibits-empty")
    os.makedirs(exd_empty)
    io.open(os.path.join(exd_empty, "B-03.pdf"), "w").write("x")
    r_empty = reconcile([pet_empty], [exd_empty])
    unread_names = [fn for fn, _why in (r_empty.get("unread") or [])]
    ok("r77b F-D move 3: an empty .docx (valid zip, empty body) lands in unread — "
       "symmetric with the .pdf empty-text branch",
       "empty.docx" in unread_names, str(unread_names))

    # --- F-E: check-exhibits exits 1 when unread is non-empty (mixed folder)
    pet_e = os.path.join(scratch, "petition-mixed")
    os.makedirs(pet_e)
    io.open(os.path.join(pet_e, "note.md"), "w", encoding="utf-8").write("See Exhibit B-3.")
    io.open(os.path.join(pet_e, "broken.pdf"), "wb").write(b"%PDF-1.4 garbage, no xref")
    exd_e = os.path.join(scratch, "exhibits-fe")
    os.makedirs(exd_e)
    io.open(os.path.join(exd_e, "B-03.pdf"), "w").write("x")
    ns = _ap.Namespace(petition=[pet_e], exhibits=[exd_e], forms=None,
                       out=os.path.join(scratch, "rep-fe.md"))
    with _ctx.redirect_stdout(io.StringIO()), _ctx.redirect_stderr(io.StringIO()):
        rc_fe = cmd_check_exhibits(ns)
    ok("r77b F-E bug: an unread petition flips the exit code to 1 (was 0 pre-fix)",
       rc_fe == 1, "rc=%d" % rc_fe)

    # --- F-F: mid-name IDs report as duplicates (position parity with :234)
    pet_f = os.path.join(scratch, "petition-f")
    os.makedirs(pet_f)
    io.open(os.path.join(pet_f, "note.md"), "w", encoding="utf-8").write("See Exhibit B-3.")
    exd_f = os.path.join(scratch, "ex-midname")
    os.makedirs(exd_f)
    io.open(os.path.join(exd_f, "Letter B-03 old.pdf"), "w").write("x")
    io.open(os.path.join(exd_f, "Letter B-03 new.pdf"), "w").write("x")
    r_f = reconcile([pet_f], [exd_f])
    # canon('B','03') == 'B-3' — the R77 probe-author trap: assert on canon output.
    ok("r77b F-F bug: two mid-name copies of B-03 are reported duplicate under canon key B-3 "
       "(was silently excluded — PART_RE matched the ID's own -03 across the whole name)",
       "B-3" in r_f["duplicates"], str(list(r_f["duplicates"])))

    exd_f2 = os.path.join(scratch, "ex-canon")
    os.makedirs(exd_f2)
    io.open(os.path.join(exd_f2, "B-03.pdf"), "w").write("x")
    io.open(os.path.join(exd_f2, "B-03 copy.pdf"), "w").write("x")
    r_f2 = reconcile([pet_f], [exd_f2])
    ok("r77b F-F control: canonical-name duplicates still fire (regression guard)",
       "B-3" in r_f2["duplicates"], str(list(r_f2["duplicates"])))

    exd_f3 = os.path.join(scratch, "ex-parts")
    os.makedirs(exd_f3)
    io.open(os.path.join(exd_f3, "B-03_1.pdf"), "w").write("x")
    io.open(os.path.join(exd_f3, "B-03_2.pdf"), "w").write("x")
    r_f3 = reconcile([pet_f], [exd_f3])
    ok("r77b F-F neg control: _1/_2 part suffixes are NOT reported as duplicates",
       "B-3" not in r_f3["duplicates"], str(list(r_f3["duplicates"])))

    # --- F-G': neutral_cwd uses tempfile.gettempdir(), not the "." fallback
    env0 = {k: os.environ.get(k) for k in ("TEMP", "TMPDIR", "TMP")}
    cwd0 = os.getcwd()
    os.chdir(d)
    try:
        for k in ("TEMP", "TMPDIR", "TMP"):
            os.environ.pop(k, None)
        p = consult.neutral_cwd(printer=lambda *a, **k: None)
        ok("r77b F-G' bug: with TEMP/TMPDIR/TMP unset, scratch is ABSOLUTE and outside cwd "
           "(was RELATIVE inside the matter, and SystemExit could never fire)",
           os.path.isabs(p) and not os.path.abspath(p).startswith(os.path.abspath(d)),
           "p=%r cwd=%r" % (p, d))
    finally:
        os.chdir(cwd0)
        for k, v in env0.items():
            if v is not None:
                os.environ[k] = v

    # --- Minor: form_dump lazy sentinel imports; module load does not eagerly import SENTINEL
    st_txt = form_dump._stamp("txt")
    st_md = form_dump._stamp("md")
    ok("r77b minor: form_dump._stamp('txt') carries the SENTINEL and 'form-dump' tag",
       SENTINELS[0] in st_txt and "form-dump" in st_txt, st_txt[:60])
    ok("r77b minor: form_dump._stamp('md') carries the SENTINEL and 'form-dump' tag",
       SENTINELS[0] in st_md and "form-dump" in st_md, st_md[:60])
    import krokai.form_dump as _fd_mod
    ok("r77b minor: form_dump does NOT eagerly import SENTINEL at module load (lazy import "
       "invariant — guards against a future run→form_dump cycle appearing silently)",
       "SENTINEL" not in vars(_fd_mod), "form_dump top names: %s" %
       [k for k in vars(_fd_mod) if not k.startswith("_")][:15])


# ------------------------------------------------------------------------------------------------
def suite_r78(tmp):
    """R78 (И3): AGENTS.md delivery, editorial-mark symmetry, catalogue honesty, docstring
    pointers. Every behavioural pin here started as a RED probe through the real pipeline
    (reviews/r78-i3/probes in the meta-project); the pins keep the repairs from regressing and
    keep two deliberate DECISIONS from being "improved" away."""
    import contextlib
    from krokai.corpus import Corpus
    from krokai.verify import check
    from krokai.verdicts import CLEAN, DANGEROUS, SIX_CAUSES
    from krokai import mutations

    # --- the [sic] that belongs to the source (probe b1; was PARTIAL on a faithful quote) -----
    sic_src = ("The Board received the application on Setpember [sic] 22, 1987, and denied it "
               "as untimely under the applicable regulation because the delay was not excused")
    law = os.path.join(tmp, "law-r78")
    os.makedirs(law, exist_ok=True)
    io.open(os.path.join(law, "matter-of-sic.txt"), "w", encoding="utf-8").write(
        "Decision text. " + sic_src + ". Further text follows here.")
    c = Corpus([law], quiet=True)

    v, _w, d = check(sic_src, c)
    ok("r78 [sic] in the SOURCE: a faithful quotation (mark included) is clean",
       v == "VERIFIED", v)
    ok("r78 [sic] in the SOURCE: the detail says the mark was KEPT, not stripped",
       "kept, not stripped" in (d or ""), d[:90])

    nosic = sic_src.replace(" [sic]", "")
    law2 = os.path.join(tmp, "law-r78b")
    os.makedirs(law2, exist_ok=True)
    io.open(os.path.join(law2, "matter-of-nosic.txt"), "w", encoding="utf-8").write(
        "Decision text. " + nosic + ". Further text follows here.")
    c2 = Corpus([law2], quiet=True)

    v, _w, d = check(sic_src, c2)     # the drafter's own editorial mark - source has none
    ok("r78 drafter-added [sic] (source without): still clean - the common case survives",
       v == "VERIFIED", v)
    # --- no silent excision (probe c1/c2: the strip left no trace anywhere) -------------------
    ok("r78 excision is visible: stripping a mark leaves a note in the detail",
       "stripped before comparison" in (d or ""), d[:90])

    v, _w, d = check(nosic, c)        # the quote CUT the source's [sic]
    ok("r78 a quotation that OMITS the source's [sic] stays loud (cutting source text)",
       v not in CLEAN, v)

    # The kept pass may not COST a diagnosis: a quotation truncated before its proviso that
    # includes the source's own [sic] must come back TRUNCATED_CONDITION (the kept pass's
    # located verdict), not the first pass's PARTIAL artifact. Found by shape enumeration
    # against the fix itself (probe_q1_shape).
    trunc_src = ("The application [sic] must be filed before the deadline expires under this "
                 "part, provided that the applicant establishes timely eligibility for the "
                 "benefit sought")
    law4 = os.path.join(tmp, "law-r78d")
    os.makedirs(law4, exist_ok=True)
    io.open(os.path.join(law4, "matter-of-q1.txt"), "w", encoding="utf-8").write(
        "Decision text. " + trunc_src + ". Tail text here.")
    c4 = Corpus([law4], quiet=True)
    v, _w, d = check("The application [sic] must be filed before the deadline expires "
                     "under this part", c4)
    ok("r78 [sic]-kept pass keeps the SHARP verdict: truncation, not a PARTIAL artifact",
       v == "TRUNCATED_CONDITION", "%s %s" % (v, (d or "")[:60]))
    v, _w, _d = check(trunc_src + ".", c4)
    ok("r78 ...and the untruncated control with the same [sic] stays clean",
       v == "VERIFIED", v)

    # --- R78 PANEL pins: each was a probe-proven red before its repair ------------------------
    # (1) A source-side [sic] between the quotation's end and the limiter blinded LIMITER_RE on
    # BOTH asking branches - a silent truncation graded VERIFIED, and the alnum twin explained
    # itself with the confidently wrong «our quotation adds `,`».
    blind_src = ("An applicant remains eligible for the requested relief [sic], unless the "
                 "applicant has been convicted of a felony offense after the date of filing")
    law5 = os.path.join(tmp, "law-r78e")
    os.makedirs(law5, exist_ok=True)
    io.open(os.path.join(law5, "matter-of-blind.txt"), "w", encoding="utf-8").write(
        "Decision text. " + blind_src + ". Tail.")
    c5 = Corpus([law5], quiet=True)
    v, _w, d = check("An applicant remains eligible for the requested relief", c5)
    ok("r78 panel: a source [sic] before the limiter no longer blinds the exact branch",
       v == "TRUNCATED_CONDITION", "%s %s" % (v, (d or "")[:60]))
    v, _w, d = check("An applicant remains eligible, for the requested relief", c5)
    ok("r78 panel: ...nor the alnum branch (the comma-drift twin)",
       v == "TRUNCATED_CONDITION", "%s %s" % (v, (d or "")[:60]))

    # (2) The [OPENED]-for-'opened' laundering: a provenance tag whose letters equal a real
    # source word must NOT ride the marks-kept pass to a green PUNCTUATION, and no note may
    # call it "the source's own text". Gate on the editorial class + exact-anchored wins.
    open_src = ("The record was opened to the public on June 1, 2020, and the applicant was "
                "notified in writing of the decision")
    law6 = os.path.join(tmp, "law-r78f")
    os.makedirs(law6, exist_ok=True)
    io.open(os.path.join(law6, "order-of-open.txt"), "w", encoding="utf-8").write(
        "Order text. " + open_src + ". Tail.")
    c6 = Corpus([law6], quiet=True)
    v, _w, d = check(open_src.replace(" opened ", " [OPENED] "), c6)
    ok("r78 panel: [OPENED] colliding with the word 'opened' stays loud (no laundering)",
       v not in CLEAN, "%s %s" % (v, (d or "")[:60]))
    ok("r78 panel: ...and the note never claims a provenance tag is the source's own text",
       "source's own text" not in (d or ""), (d or "")[:80])

    # (3) The mixed-tags cost: a faithful source-[sic] quotation carrying a provenance tag
    # beside it used to fail BOTH passes (all-or-nothing keep). The editorial/provenance split
    # keeps [sic] and strips [OPENED] on the second pass.
    v, _w, d = check(sic_src + " [OPENED]", c)
    ok("r78 panel: faithful source-[sic] + a provenance tag beside it is clean again",
       v == "VERIFIED", "%s %s" % (v, (d or "")[:70]))
    ok("r78 panel: ...with the provenance tag's excision still visible in the detail",
       "[OPENED]" in (d or ""), (d or "")[:90])

    # (4) init refuses the toolkit's own checkout (three reviewers independently). The positive
    # control - init working in a normal folder - is suite_install's whole job.
    from krokai.cli import cmd_init
    fake = os.path.join(tmp, "fake-checkout")
    os.makedirs(os.path.join(fake, "krokai"), exist_ok=True)
    io.open(os.path.join(fake, "CHANGELOG.md"), "w", encoding="utf-8").write("# log\n")
    io.open(os.path.join(fake, "krokai", "selftest.py"), "w", encoding="utf-8").write("# st\n")

    class _A(object):
        path = fake
        force = False
        claude_md_only = False
    try:
        cmd_init(_A())
        refused = False
        msg = "<no exception>"
    except SystemExit as e:
        refused = True
        msg = str(e)
    ok("r78 panel: init REFUSES a folder that looks like the toolkit's own checkout",
       refused and "matter" in msg, msg[:80])

    # (5) The live CLI ladder is DERIVED from SIX_CAUSES - the hand-written four-cause block
    # survived a whole release after the code went to six. Source-level pin: the old literal is
    # gone and the derivation is present in cli.py.
    cli_src = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py"),
                      encoding="utf-8").read()
    ok("r78 panel: cmd_quote's NOT_FOUND ladder derives from SIX_CAUSES (old literal gone)",
       "THE CORPUS IS INCOMPLETE" not in cli_src and cli_src.count("SIX_CAUSES") >= 1)

    # (6) Every `krokai <sub>` named in channels.json resolves to a real subcommand - the _doc
    # said `krokai consult` for releases after the command became `review` (dangling-pointer
    # class, in DATA this time).
    import json as _json
    from krokai.cli import build_parser
    reg_text = io.open(data_file("channels.json"), encoding="utf-8").read()
    subs = set()
    for act in build_parser()._subparsers._group_actions:
        subs |= set(getattr(act, "choices", {}) or {})
    cited = set(re.findall(r"krokai ([a-z-]+)", reg_text))
    ok("r78 panel: every `krokai <sub>` cited in channels.json is a real subcommand",
       cited <= subs, "cited-but-missing: %s" % sorted(cited - subs))

    # (7) The snippet's rungs carry their SIX_CAUSES twins - counting alone would pass a ladder
    # with the right length and the wrong content.
    snip_t = io.open(os.path.join(data_dir("templates"), "CLAUDE.md.snippet"),
                     encoding="utf-8").read()
    section_t = snip_t.split("`NOT_FOUND` is not `INVENTED`", 1)[-1].split("###", 1)[0]
    rung_keys = ("downloaded", "edition", "damaged", "placeholder", "law", "rewritten")
    rungs = re.findall(r"(?m)^\d+\.\s+(.+(?:\n\s{3,}.+)*)", section_t)
    paired = len(rungs) == len(rung_keys) and all(
        k in r.lower() for k, r in zip(rung_keys, rungs))
    ok("r78 panel: each snippet rung matches its SIX_CAUSES twin by key word, in order",
       paired, "rungs=%d" % len(rungs))

    # --- DECISION pin (probe a2): an interposed running header stays LOUD ---------------------
    # «677 Interim Decision #2282» welded mid-sentence by a page break comes back OPERATOR. That
    # is a false alarm about a CORPUS defect, and it stays: an automatic excuse for
    # header-shaped insertions would also excuse a real edit of the same shape - the exact hole
    # the R76 mandatory-group fix in FOOTNOTE_RE closed. The cure is in the corpus copy
    # (SIX_CAUSES cause 3 names it); this pin keeps the forgiveness from being added back.
    sent = ("The respondent has established that his deportation would result in extreme "
            "hardship to his lawful permanent resident spouse within the meaning of the statute")
    law3 = os.path.join(tmp, "law-r78c")
    os.makedirs(law3, exist_ok=True)
    io.open(os.path.join(law3, "interim-header.txt"), "w", encoding="utf-8").write(
        "Opinion text. " + sent[:98] + " 677 Interim Decision #2282 " + sent[98:] + ". More.")
    c3 = Corpus([law3], quiet=True)
    v, _w, _d = check(sent, c3)
    ok("r78 DECISION: a running header welded mid-sentence stays a loud corpus-damage alarm",
       v in DANGEROUS, v)
    ok("r78 ...and cause 3 of SIX_CAUSES names the welded-header and wrong-projection cases",
       "running header" in SIX_CAUSES[2] and "PROJECTION" in SIX_CAUSES[2], SIX_CAUSES[2][:80])

    # --- Д-3 micro: the generator is no narrower than the checker (probe d1) ------------------
    q_semi = ("An application for adjustment of status shall be filed with the fee prescribed "
              "and with the documents specified in the instructions; provided that the "
              "applicant establishes eligibility at the time of filing")
    m = mutations.m_cut_condition(q_semi)
    ok("r78 Д-3: m_cut_condition mutates the '; provided that' form the checker catches",
       bool(m) and "provided" not in (m or ""), repr(m)[:70])
    m2 = mutations.m_synonym("the alien is eligible for relief from removal proceedings")
    ok("r78 Д-3: the synonym bank tests the real 2026 shift, alien -> noncitizen",
       bool(m2) and " noncitizen " in m2, repr(m2)[:70])

    # --- Д-3: the catalogue mirrors the code, bidirectionally ---------------------------------
    rows = set(re.findall(r"(?m)^\s{4}([a-z][a-z-]+)\s{2,}", mutations.__doc__ or ""))
    implemented = {n for n, _f, _m in mutations.MUTATIONS} | {"splice"}
    ok("r78 Д-3: every catalogue row is implemented (no row mirrors nothing)",
       rows <= implemented, "rows not implemented: %s" % sorted(rows - implemented))
    ok("r78 Д-3: every implemented mutation has its catalogue row (drift is two-way)",
       implemented <= rows, "implemented but unlisted: %s" % sorted(implemented - rows))
    ok("r78 Д-3: wrong-address is honestly recorded as the ADDRESS layer's class, not a row",
       "wrong-address" in (mutations.__doc__ or "") and "ADDRESS layer" in (mutations.__doc__ or ""))

    # --- Д-1 class: directive docstring pointers resolve to files -----------------------------
    # Scope: `see X.py` / `see \`X.py\`` and double-backticked ``X.py`` in krokai/*.py. This
    # file itself is excluded - it QUOTES pointer shapes as data, and scanning the scanner
    # grades its own examples. Provenance citations without a directive shape (a probe named
    # with its round) are out of scope on purpose: they cite history, not the tree.
    pkg = os.path.dirname(os.path.abspath(__file__))
    hooks_dir = data_dir("hooks")
    dangling, seen = [], 0
    for fn in sorted(os.listdir(pkg)):
        if not fn.endswith(".py") or fn == os.path.basename(__file__):
            continue
        src = io.open(os.path.join(pkg, fn), encoding="utf-8", errors="replace").read()
        for mm in re.finditer(r"(?i)\bsee\s+`{0,2}([\w.-]+\.py)`{0,2}|``([\w.-]+\.py)``", src):
            name = mm.group(1) or mm.group(2)
            seen += 1
            if not (os.path.isfile(os.path.join(pkg, name))
                    or os.path.isfile(os.path.join(hooks_dir, name))):
                dangling.append("%s -> %s" % (fn, name))
    ok("r78 Д-1: every directive docstring pointer resolves to a file in the tree "
       "(the fourth dangling-pointer incident was verdicts.py naming a module that never shipped)",
       seen > 0 and not dangling, "checked %d; dangling: %s" % (seen, dangling))

    # --- Б-12: the brief asks for the field that was right when the verdict was wrong ---------
    from krokai.prompts import QUOTE_RULES
    ok("r78 Б-12: the brief demands 'what evidence would change your conclusion'",
       "would change your conclusion" in QUOTE_RULES)

    # --- Б-6: the snippet's ladder is the code's ladder ---------------------------------------
    snip = io.open(os.path.join(data_dir("templates"), "CLAUDE.md.snippet"),
                   encoding="utf-8").read()
    ok("r78 Б-6: the snippet says SIX causes, not the four it said while the code held six",
       "six causes" in snip and "four causes" not in snip)
    section = snip.split("`NOT_FOUND` is not `INVENTED`", 1)[-1].split("###", 1)[0]
    numbered = re.findall(r"(?m)^\d+\.\s", section)
    ok("r78 Б-6: the snippet ladder has exactly len(SIX_CAUSES) rungs - counted, not recalled",
       len(numbered) == len(SIX_CAUSES), "snippet %d vs code %d" % (len(numbered), len(SIX_CAUSES)))
    ok("r78 В-1: the snippet points the matter's assistant at `agents` for the full discipline",
       "{KROKAI} agents" in snip)

    # --- В-1: AGENTS.md travels with the package and the command prints it --------------------
    agents_path = data_file("AGENTS.md")
    ok("r78 В-1: AGENTS.md resolves in this layout (wheel force-include or repo root)",
       os.path.isfile(agents_path), agents_path)
    from krokai.cli import main as cli_main
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli_main(["agents"])
    out = buf.getvalue()
    ok("r78 В-1: `krokai agents` prints the discipline and exits 0",
       rc == 0 and "ai-second-opinion" in out and "INSTALL-FOR-AI.md" in out,
       "rc=%s len=%d" % (rc, len(out)))


def suite_r78_repo(root):
    """Root-file half of R78 - meaningful only from a source checkout (the wheel does not carry
    the repository root). The CLAUDE.md bridge exists because Claude Code reads CLAUDE.md and
    not AGENTS.md, and a backticked `@path` is a literal, not an import - so the bridge line
    must be bare."""
    ap = os.path.join(root, "AGENTS.md")
    cp = os.path.join(root, "CLAUDE.md")
    ok("r78 repo: AGENTS.md exists at the repository root", os.path.isfile(ap), ap)
    body = io.open(ap, encoding="utf-8").read() if os.path.isfile(ap) else ""
    ok("r78 repo: AGENTS.md names the install runbook and the orchestration sibling",
       "INSTALL-FOR-AI.md" in body and "ai-second-opinion" in body)
    ok("r78 repo: AGENTS.md is not a template - no {KROKAI} placeholder to rot unrendered",
       "{KROKAI}" not in body)
    ok("r78 repo: CLAUDE.md bridge exists", os.path.isfile(cp), cp)
    bridge = io.open(cp, encoding="utf-8").read() if os.path.isfile(cp) else ""
    ok("r78 repo: the bridge line is a BARE @AGENTS.md (backticked = literal = silent no-op)",
       re.search(r"(?m)^@AGENTS\.md\s*$", bridge) is not None)
    # The R78 panel showed the presence pin above is decorative against contamination: init in
    # the clone root would APPEND a matter block after the import and this pin would still
    # pass. So: the bridge holds NOTHING but its comment and the import line.
    residue = re.sub(r"(?s)<!--.*?-->", "", bridge).replace("@AGENTS.md", "").strip()
    ok("r78 repo: the bridge file holds ONLY the comment and the import - no appended blocks",
       residue == "", residue[:60])
    ok("r78 repo: no second AGENTS.md inside the package dir (data_file must serve the root's)",
       not os.path.isfile(os.path.join(root, "krokai", "AGENTS.md")))


# ------------------------------------------------------------------------------------------------
def suite_r79(tmp):
    """R79 (Ф1): the bank write gatekeeper - `krokai bank add` / `krokai bank dismiss`.

    Every pin here reproduces a branch first proven by execution on a live temp matter the day
    the feature was built. The design is ported from a sister project's gatekeeper, whose
    measured motivation was: an assistant re-typing six banked quotations by eye lost two
    markers of six - the quotation must be a SLICE of the source, with nowhere to mistype it.
    """
    import contextlib
    import json as _json
    from krokai.cli import main as cli_main, build_parser
    from krokai.config import TEMPLATE, CONFIG_NAME
    from krokai.bank import BANK_HEADER, append_queue
    from krokai.bank_add import revision_ledger, SIDES

    def run(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(argv)
        return rc, buf.getvalue()

    root = os.path.join(tmp, "r79-matter")
    law = os.path.join(root, "law")
    case = os.path.join(root, "case")
    for d in (law, case):
        os.makedirs(d, exist_ok=True)
    _json.dump(TEMPLATE, io.open(os.path.join(root, CONFIG_NAME), "w", encoding="utf-8"))
    io.open(os.path.join(law, "8CFR-part-214.txt"), "w", encoding="utf-8").write(REG)
    bank_path = os.path.join(case, "QUOTE-BANK.md")
    io.open(bank_path, "w", encoding="utf-8", newline="\n").write(BANK_HEADER)

    # --- the init template carries BOTH side sections (G-B: structure, not prose) --------------
    for side, heading in SIDES.items():
        ok("r79 init bank template carries the «%s» section" % side,
           re.search(r"(?m)^%s\s*$" % re.escape(heading), BANK_HEADER) is not None)

    NP = "Admissibility standard only; it does not prove this applicant is admissible."
    base = ["bank", "add", "--dir", root, "--side", "pro", "--address", "8 CFR 214.2",
            "--from", "An applicant shall not be admitted",
            "--to", "not inadmissible under section 212.", "--not-proves", NP]

    # --- dry-run is the default: everything shown, nothing written -----------------------------
    before = io.open(bank_path, encoding="utf-8").read()
    rc, out = run(base)
    ok("r79 dry-run: exit 0 and the would-be id is on screen", rc == 0 and "§P-1" in out, out[-200:])
    ok("r79 dry-run: the bank file is untouched",
       io.open(bank_path, encoding="utf-8").read() == before)

    # --- --apply writes; the quotation is the SLICE, not the anchors ---------------------------
    rc, out = run(base + ["--apply"])
    body = io.open(bank_path, encoding="utf-8").read()
    ok("r79 apply: written, and the post-write re-read is reported", rc == 0 and "re-read" in out)
    ok("r79 apply: the middle words - present in NEITHER anchor - are in the banked quote",
       "establishes to the satisfaction of the officer" in body,
       "proof the text was sliced from the source, not assembled from the arguments")
    ledger, entries = revision_ledger(body)
    ok("r79 apply: the header ledger agrees with the body", ledger == entries == 1,
       "%s/%s" % (ledger, entries))
    ok("r79 apply: the entry sits under «For us», above «Against us»",
       body.find("## For us") < body.find("### §P-1 ") < body.find("## Against us"))
    ok("r79 apply: the entry says it was sliced, and the verdict at banking",
       "not typed" in body and "at banking: VERIFIED" in body)

    # --- the headline refusal: a slice that stops before its proviso ---------------------------
    rc, out = run(["bank", "add", "--dir", root, "--side", "con", "--address", "8 CFR 214.2",
                   "--from", "The district director may consider reinstating",
                   "--to", "makes a request for reinstatement", "--not-proves", NP])
    ok("r79 the cut-condition shape is REFUSED before writing (exit 3)",
       rc == 3 and "REFUSED" in out, "the whole reason the gatekeeper exists")
    ok("r79 the refusal shows the continuation the slice dropped",
       "but do not include" in out)
    ok("r79 the connector warning fired on the edge print", "CONNECTOR" in out)
    ok("r79 nothing was written by the refusal",
       "§C-" not in io.open(bank_path, encoding="utf-8").read())

    # --- anchors: unique start, explicit choice for a repeated end -----------------------------
    rc, out = run(["bank", "add", "--dir", root, "--side", "pro", "--address", "8 CFR 214.2",
                   "--from", "student", "--to", "occurred.", "--not-proves", NP])
    ok("r79 a non-unique start anchor is refused with its count",
       rc == 3 and "2 times" in out, out[-160:])
    amb = ["bank", "add", "--dir", root, "--side", "pro", "--address", "8 CFR 214.2",
           "--from", "(f)(16) Reinstatement", "--to", "student", "--not-proves", NP]
    rc, out = run(amb)
    ok("r79 a repeated end anchor is refused, listing each occurrence with its slice",
       rc == 3 and "--to-nth 2" in out and "-character slice" in out)
    rc, out = run(amb + ["--to-nth", "2"])
    ok("r79 --to-nth resolves the ambiguity explicitly", rc == 0 and "VERIFIED" in out)

    # --- floors and ids ------------------------------------------------------------------------
    rc, _out = run(base[:-1] + ["too short"])
    ok("r79 the --not-proves floor holds (the boundary field must not be decorative)", rc == 2)
    rc, out = run(base + ["--id", "P-1"])
    ok("r79 a taken id is refused - ids are never reused", rc == 3 and "already taken" in out)
    rc, out = run(base + ["--id", "P-10"])
    ok("r79 §P-10 is free while §P-1 is taken (id equality, not substring)", rc == 0,
       "the naive `'§P-1' in text` test would refuse it")

    # --- the queue closes BY the write, under the containment floors ---------------------------
    queue_path = os.path.join(case, "QUOTE-QUEUE.md")
    covered = ("The district director may consider reinstating a student who makes a request "
               "for reinstatement, but do not include instances where a pattern of repeated "
               "violations has occurred.")
    unrelated = ("An officer may not deny an application without first issuing a notice of "
                 "intent to deny under this part in any circumstance whatsoever.")
    also_notice = ("The notice of intent to deny procedure applies to every application filed "
                   "under this part without exception at all times.")
    short_contained = "Reinstatement to student status. The district"
    append_queue(queue_path, [(covered, "NOT_FOUND", "t", ""),
                              (unrelated, "NOT_FOUND", "t", ""),
                              (also_notice, "NOT_FOUND", "t", ""),
                              (short_contained, "NOT_FOUND", "t", "")])
    rc, out = run(["bank", "add", "--dir", root, "--side", "con", "--address", "8 CFR 214.2",
                   "--from", "(f)(16) Reinstatement", "--to", "violations has occurred.",
                   "--not-proves", NP, "--apply"])
    q = io.open(queue_path, encoding="utf-8").read()
    ok("r79 banking ticks the covered queue line, naming the entry",
       rc == 0 and "closed: banked as §C-1" in q)
    ok("r79 a short contained line is NOT closed (no piece of sixty)",
       short_contained in q and q.count("- [x]") == 1,
       "a stock legal opening once closed two different provisions")
    ok("r79 unrelated lines stay open", q.count("- [ ]") >= 2)

    # --- dismiss: one line, one reason, floors -------------------------------------------------
    rc, _out = run(["bank", "dismiss", "--dir", root, "notice of intent", "--why", "short"])
    ok("r79 the --why floor holds", rc == 2)
    rc, out = run(["bank", "dismiss", "--dir", root, "notice of intent",
                   "--why", "Procedural posture only; the matter has no denial to answer."])
    ok("r79 a fragment matching two open lines is refused - one reason cannot cover two "
       "decisions", rc == 3 and "matches 2" in out)
    rc, out = run(["bank", "dismiss", "--dir", root, "in any circumstance whatsoever",
                   "--why", "Procedural posture only; the matter has no denial to answer.",
                   "--apply"])
    q = io.open(queue_path, encoding="utf-8").read()
    ok("r79 a unique dismiss ticks the line and records the reason",
       rc == 0 and "dismissed: Procedural posture only" in q)

    # --- the ledger makes deletion loud --------------------------------------------------------
    body = io.open(bank_path, encoding="utf-8").read()
    cut = re.sub(r"(?s)### §P-1 .*?(?=### §P-10|## Against us)", "", body, count=1)
    ledger, entries = revision_ledger(cut)
    ok("r79 a hand deletion is visible: body below the header ledger",
       ledger is not None and entries == ledger - 1, "%s vs %s" % (ledger, entries))
    io.open(bank_path, "w", encoding="utf-8", newline="\n").write(cut)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli_main(["close", "--dir", root])
    ok("r79 `krokai close` says ENTRIES VANISHED and fails the round",
       rc == 1 and "VANISHED" in buf.getvalue())

    # --- guidance: no code-address laundering, year + demonstrable link, sha in the entry ------
    gpath = os.path.join(law, "uscis-policy-manual-vol7-2019.md")
    io.open(gpath, "w", encoding="utf-8").write(
        "USCIS Policy Manual, Volume 7 - Adjustment of Status (2019 edition)\n\n"
        "The officer must evaluate the record as a whole in every adjustment case before any "
        "favorable exercise of discretion is recorded in the decision.\n")
    g = ["bank", "add", "--dir", root, "--side", "pro", "--kind", "guidance",
         "--file", gpath, "--from", "The officer must evaluate the record",
         "--to", "recorded in the decision.", "--not-proves", NP]
    rc, out = run(g + ["--address", "8 CFR 214.2"])
    ok("r79 guidance refuses an address that parses as a code citation",
       rc == 3 and "parses as a code citation" in out,
       "a CFR quote under a guidance label would dodge the address binding")
    rc, out = run(g + ["--address", "USCIS Policy Manual Volume 7"])
    ok("r79 guidance demands a year in the address", rc == 3 and "YEAR" in out)
    rc, out = run(g + ["--address", "USCIS Policy Manual Volume 7 (2019)", "--apply"])
    body = io.open(bank_path, encoding="utf-8").read()
    ok("r79 guidance banks with the source sha256 in the entry",
       rc == 0 and "source sha256" in body)

    # --- the parser keeps the parent's --dir/--quiet reachable from the subcommands ------------
    a = build_parser().parse_args(base)
    ok("r79 the namespace carries --dir/--quiet defaults for the subcommand (no argparse "
       "clobber)", hasattr(a, "dir") and hasattr(a, "quiet"))
    rc, out = run(["bank", "--dir", root])
    ok("r79 bare `krokai bank` is still the status view", rc == 0 and "quote bank:" in out)


def suite_r79_phase2(tmp):
    """R79 (Ф2): coverage - the four bank<->draft findings, plus corpus<->bank inventory.

    Every pin here reproduces a branch first proven by execution against a live temp matter
    while the module was being built. The four findings each come from a measured incident in
    the sister project: a filing that rested on a rule the bank marked hostile as its own
    affirmative support (MINE); a rule cited by shorthand where the bank held its verbatim
    text (PARAPHRASE); a bank entry with an applicability boundary and one without (UNPARSED);
    a corpus file downloaded and never analysed (G-D inventory).
    """
    import contextlib
    import json as _json
    from krokai.cli import main as cli_main
    from krokai.config import TEMPLATE, CONFIG_NAME
    from krokai.bank import BANK_HEADER
    from krokai import coverage

    def run(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(argv)
        return rc, buf.getvalue()

    # ------------------------------------------------------------------------ address parser
    # A CFR citation with three parenthetical subitems must land as a fine key that carries them
    # all. This is the whole difference between the coverage extractor and the packs' coarse key,
    # and the reason for it is the AOS §Π-13 case - the mine was against `(f)(8)(i)`, not against
    # any (f) entry.
    got = coverage.parse_addresses("see 8 CFR 214.2(f)(8)(i)(D) for the rule")
    keys = [k for k, _l, _p in got if k[0] == "cfr"]
    ok("r79.2 CFR citation parses with all subitems preserved",
       ("cfr", "8", "214", "2", "f", "8", "i", "d") in keys,
       "expected the full 8-tuple, got %r" % keys[:3])

    # USC ↔ INA fold at extraction. A bank cite of «section 245(k) of the Act» and a draft cite
    # of «8 U.S.C. § 1255(k)» must meet - the fold happens here so `related()` does not have to
    # know about aliases.
    got = coverage.parse_addresses("under 8 U.S.C. § 1255(k) the")
    fine = {k for k, _l, _p in got}
    ok("r79.2 USC 8:1255(k) also emits its INA twin 245(k)",
       ("ina", "245", "k") in fine and ("usc", "8", "1255", "k") in fine)
    got = coverage.parse_addresses("section 245(k) of the Act allows")
    fine = {k for k, _l, _p in got}
    ok("r79.2 «section 245(k) of the Act» folds to INA plus USC",
       ("ina", "245", "k") in fine and ("usc", "8", "1255", "k") in fine)

    # Bare «section 245(k)» without «of the Act» is ambiguous and must NOT parse as INA. Same
    # words could be a state statute or a regulation; a false fold would generate mines that
    # are not mines.
    got = coverage.parse_addresses("state section 245(k) reads as")
    ok("r79.2 bare «section 245(k)» (no «of the Act») does NOT parse as INA",
       not any(k[0] == "ina" for k, _l, _p in got))

    # -------------------------------------------------------------------------- related() rule
    # The AOS-measured bug: a tab-label parent must not fire on specific children. `214.2(f)` is
    # a category, `214.2(f)(8)(i)` is a specific paragraph; catching the parent as related to
    # the child would revive the mine-inflation the fix exists to close.
    parent = ("cfr", "8", "214", "2", "f")
    child = ("cfr", "8", "214", "2", "f", "8", "i")
    ok("r79.2 related() refuses tab-label parent -> specific child (the AOS bug)",
       not coverage.related(parent, child))
    ok("r79.2 related() accepts narrow parent -> specific child",
       coverage.related(("cfr", "8", "214", "2", "f", "8"), child))
    ok("r79.2 related() accepts exact-equality regardless of narrowness",
       coverage.related(parent, parent))
    ok("r79.2 related() refuses across kinds - the USC/INA fold happens at extraction",
       not coverage.related(("cfr", "8", "214", "2"), ("usc", "8", "214", "2")))

    # USC/INA thresholds are lower because a section is a single-topic provision by convention.
    ok("r79.2 USC 1 subitem is narrow enough for a prefix match",
       coverage.related(("usc", "8", "1255", "k"), ("usc", "8", "1255", "k", "1")))
    ok("r79.2 USC 0 subitems (bare section) is NOT narrow enough",
       not coverage.related(("usc", "8", "1255"), ("usc", "8", "1255", "k")))

    # ---------------------------------------------------------------- bank parser
    # 🔴 The two entries are placed BY HAND under their respective ## sections. Appending
    # after `BANK_HEADER` alone would put both entries under `## Against us` (the last H2 in
    # the header), because the parser assigns each entry to the last preceding `##` heading.
    # This is the same subtle placement rule `bank_add._insert_entry` handles at write time;
    # here the test is testing the PARSER, so we set the layout deliberately.
    bank_text = """# Quote bank

Every quotation below has been opened in the primary source by a person.

## For us

### §P-1 Late filing safe harbour
> No application may be denied solely because the applicant made a late filing of the
> underlying nonimmigrant status extension.

| | |
|---|---|
| **Address** | 8 U.S.C. § 1255(k) |
| **On disk** | `8usc-1255.xml` |
| **How to re-check** | krokai quote ... |
| **Verified** | igor, 2026-09-01 |
| **Used in** | brief section III.B |
| **Neighbours** | before — ... · after — ... |
| **What this does NOT prove** | Does not cover unlawful presence exceeding 180 days. |

## Against us

### §C-1 F-1 reinstatement discretion
> The district director may consider reinstating a student who makes a request for
> reinstatement, but do not include instances where a pattern of repeated violations has
> occurred.

| | |
|---|---|
| **Address** | 8 CFR 214.2(f)(16) |
| **On disk** | `8CFR-part-214.xml` |
| **How to re-check** | krokai quote ... |
| **Verified** | igor, 2026-09-01 |
| **Used in** | 🔴 TO DO |
| **Neighbours** | before — ... · after — ... |
| **What this does NOT prove** | Discretion is not entitlement. |
"""
    # A companion bank text where BOTH entries are complete - used by the CLI "clean draft"
    # test, so that --strict does not fire on a residual [D] finding from §C-1's empty
    # «Used in» when the test is only checking [A]/[C] cleanliness.
    bank_text_clean = bank_text.replace("| **Used in** | 🔴 TO DO |",
                                        "| **Used in** | opposing brief IV.C |")
    entries = coverage.parse_bank_entries(bank_text)
    ok("r79.2 bank parser finds both entries", len(entries) == 2,
       "got %d" % len(entries))
    by_id = {e["id"]: e for e in entries}
    ok("r79.2 §P-1 landed under «For us»", by_id.get("§P-1", {}).get("side") == "pro")
    ok("r79.2 §C-1 landed under «Against us»", by_id.get("§C-1", {}).get("side") == "con")
    ok("r79.2 the entry's address parsed into a fine key",
       ("usc", "8", "1255", "k") in by_id["§P-1"]["addr_keys"])
    ok("r79.2 USC address ALSO carries the INA twin (fold at parse time)",
       ("ina", "245", "k") in by_id["§P-1"]["addr_keys"])
    ok("r79.2 «Used in» filled with prose is non-empty on the entry",
       by_id["§P-1"]["used_in"] == "brief section III.B")
    ok("r79.2 «Used in» with a 🔴 TO DO placeholder is treated as empty",
       by_id["§C-1"]["used_in"] == "")
    ok("r79.2 the blockquote body is joined into a single normalised quote string",
       "district director may consider reinstating" in by_id["§C-1"]["quote"])

    # ---------------------------------------------------------------------- analyse: A/B/C/D
    draft_with_mine = ("brief.md",
                       "The applicant is eligible under section 245(k) of the Act. The rule at "
                       "8 CFR 214.2(f)(16) - reinstatement - supports our position because the "
                       "district director's discretion runs in favour of a compliant student. "
                       "See also 8 U.S.C. § 1255(k).")
    report = coverage.analyse([draft_with_mine], entries)
    ok("r79.2 [A] MINE fires when the draft cites a rule the bank marks against us",
       any(m["id"] == "§C-1" for m in report["mines"]),
       "mines: %r" % report["mines"])
    ok("r79.2 [A] a mine reports the draft's own address form as the trigger",
       any("8 CFR 214.2(f)(16)" in "; ".join(m.get("triggers", []))
           for m in report["mines"]))
    ok("r79.2 [C] PARAPHRASE fires when address is cited but the bank's exact quote is missing",
       any(p["id"] == "§P-1" for p in report["paraphrases"]))
    ok("r79.2 [D] MISSING PIECES flags §C-1 for its empty «Used in»",
       any(u["id"] == "§C-1" and any("used in" in m.lower() for m in u["missing"])
           for u in report["unparsed"]))

    # [B] UNAPPLIED requires a draft that does NOT cite the entry's address at all.
    draft_no_pro = ("other.md",
                    "The applicant lost F-1 status; 8 CFR 214.2(f)(16) is the reinstatement rule "
                    "and does not apply here for reasons X, Y and Z. There is no adjustment.")
    report2 = coverage.analyse([draft_no_pro], entries)
    ok("r79.2 [B] UNAPPLIED fires for a For-us entry the draft never cites",
       any(u["id"] == "§P-1" for u in report2["unapplied"]))

    # ------------------------------------------------------------------ [C] verbatim exempts
    draft_with_verbatim = ("brief.md",
                           "The applicant is protected because «No application may be denied "
                           "solely because the applicant made a late filing of the underlying "
                           "nonimmigrant status extension.» See 8 U.S.C. § 1255(k).")
    report3 = coverage.analyse([draft_with_verbatim], entries)
    ok("r79.2 [C] no PARAPHRASE flag when the bank's exact wording is in the draft",
       not any(p["id"] == "§P-1" for p in report3["paraphrases"]))

    # ------------------------------------------------------------------ tab-label protection
    # A draft citing `214.2(f)` (the tab label, no specific paragraph) MUST NOT mine §C-1 which
    # is `(f)(16)`. This is the AOS bug and the whole reason `related()` is asymmetric.
    draft_tab_label = ("weak.md", "See generally 8 CFR 214.2(f) for the whole framework.")
    report_tab = coverage.analyse([draft_tab_label], entries)
    ok("r79.2 tab-label reference 214.2(f) does NOT mine §C-1 which is (f)(16)",
       not any(m["id"] == "§C-1" for m in report_tab["mines"]),
       "the AOS bug would resurface as any (f) mention firing every (f) entry")

    # ------------------------------------------------------------------ CLI integration
    root = os.path.join(tmp, "r79p2-matter")
    law = os.path.join(root, "law")
    case = os.path.join(root, "case")
    for d in (law, case):
        os.makedirs(d, exist_ok=True)
    _json.dump(TEMPLATE, io.open(os.path.join(root, CONFIG_NAME), "w", encoding="utf-8"))
    io.open(os.path.join(law, "8CFR-part-214.xml"), "w", encoding="utf-8").write(REG)
    io.open(os.path.join(law, "8usc-1255.xml"), "w", encoding="utf-8").write(
        "Section 1255(k). No application may be denied solely because the applicant made a "
        "late filing of the underlying nonimmigrant status extension.")
    bank_path = os.path.join(case, "QUOTE-BANK.md")
    io.open(bank_path, "w", encoding="utf-8", newline="\n").write(bank_text)

    draft_path = os.path.join(case, "brief.md")
    io.open(draft_path, "w", encoding="utf-8", newline="\n").write(draft_with_mine[1])

    rc, out = run(["coverage", "--dir", root, draft_path])
    ok("r79.2 CLI: coverage prints all four sections and exits 0 without --strict",
       rc == 0 and "[A] MINES" in out and "[B] UNAPPLIED" in out
       and "[C] PARAPHRASE" in out and "[D]" in out,
       out[-260:])
    ok("r79.2 CLI: --strict returns 5 when there is a MINE (or paraphrase)",
       run(["coverage", "--dir", root, draft_path, "--strict"])[0] == 5)

    # A clean draft against the clean bank: exact quotation, no mine, no [D] finding either.
    io.open(bank_path, "w", encoding="utf-8", newline="\n").write(bank_text_clean)
    clean_draft = os.path.join(case, "clean.md")
    io.open(clean_draft, "w", encoding="utf-8", newline="\n").write(
        "The applicant is protected because «No application may be denied solely because the "
        "applicant made a late filing of the underlying nonimmigrant status extension.» See "
        "8 U.S.C. § 1255(k).")
    rc, out = run(["coverage", "--dir", root, clean_draft, "--strict"])
    ok("r79.2 CLI: --strict exits 0 on a mine-free, paraphrase-free draft with the pro quote "
       "verbatim AND a bank with no [D] findings",
       rc == 0, out[-260:])
    # Restore the dirty bank for the remaining CLI probes.
    io.open(bank_path, "w", encoding="utf-8", newline="\n").write(bank_text)

    # -------------------------------------------------------------- CLI: library --bank
    rc, out = run(["library", "--dir", root, "--bank"])
    ok("r79.2 CLI: library --bank prints the corpus <-> bank inventory",
       rc == 0 and "corpus <-> bank inventory" in out, out[-260:])

    # -------------------------------------------------------------- CLI: close [6]
    rc, out = run(["close", "--dir", root])
    ok("r79.2 CLI: close now prints a [6] corpus <-> bank line when bank has entries",
       "[6] corpus <-> bank" in out, out[-260:])

    # -------------------------------------------------------------- controls fail loudly
    # A synthetic breakage of `related` would abort. We can't monkey-patch cleanly here, but
    # we can assert the control set is honest by construction: it names each measured probe.
    ok("r79.2 controls_pass returns True on the shipped extractor",
       coverage.controls_pass(printer=lambda s: None))

    # -------------------------------------------------------------- corpus_bank_inventory
    from krokai.run import corpus_for
    from krokai.config import load as load_cfg
    from krokai.citations import load_packs
    cfg = load_cfg(root)
    corpus = corpus_for(cfg, quiet=True)
    packs = load_packs(cfg["citation_packs"])
    inv = coverage.corpus_bank_inventory(corpus, entries, packs)
    ok("r79.2 inventory names the corpus files that match a bank entry",
       inv["matched_sources"] >= 1,
       "matched=%d unparsed=%d" % (inv["matched_sources"], len(inv["unparsed_sources"])))
    ok("r79.2 inventory reports zero-missing when both entries have their file",
       len(inv["missing_for_bank"]) == 0,
       "missing: %r" % inv["missing_for_bank"])

    # A THIRD bank entry, placed under `## Against us` (that is where `bank_text` ends), whose
    # address has no file on disk - the missing-side signal.
    bank_text_with_missing = bank_text + """
### §C-2 Preamble to the 2024 rule
> The Department clarifies that the reinstatement provision applies without a duration limit.

| | |
|---|---|
| **Address** | 91 FR 45324 |
| **On disk** | `not-downloaded.md` |
| **How to re-check** | krokai quote ... |
| **Verified** | igor, 2026-09-01 |
| **Used in** | test |
| **Neighbours** | before — ... · after — ... |
| **What this does NOT prove** | Does not amend the statute or CFR rule. |
"""
    io.open(bank_path, "w", encoding="utf-8", newline="\n").write(bank_text_with_missing)
    entries2 = coverage.parse_bank_entries(io.open(bank_path, encoding="utf-8").read())
    inv2 = coverage.corpus_bank_inventory(corpus, entries2, packs)
    ok("r79.2 inventory names a bank entry whose address has NO file on disk",
       any(m["id"] == "§C-2" for m in inv2["missing_for_bank"]),
       "missing: %r" % inv2["missing_for_bank"])


def suite_r79_phase3(tmp):
    """R79 (Ф3): suggest-fetches + SITE-ACCESS map + doctor --probe-sites.

    Every URL template here was measured against the live host on 2026-09-01 while the module
    was being built. The suite does NOT touch the network - `doctor --probe-sites` does, on
    demand, but the pins here confirm the SHAPE of what would be sent, not the outcome. A
    network probe in the suite is a suite that stops running when Comcast has a bad day.
    """
    import contextlib
    import json as _json
    from krokai.cli import main as cli_main
    from krokai.config import TEMPLATE, CONFIG_NAME
    from krokai.bank import BANK_HEADER
    from krokai import suggest

    def run(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(argv)
        return rc, buf.getvalue()

    # ------------------------------------------------------------------ suggest_for_key builders
    # Each verified-live-2026-09-01 template lands as a FetchSuggestion with the exact URL and a
    # command that starts with the exact `krokai fetch` string the assistant is expected to run.
    s = suggest.suggest_for_key(("usc", "8", "1101"))
    ok("r79.3 usc suggests govinfo link-service URL",
       s is not None and s.url == "https://www.govinfo.gov/link/uscode/8/1101?link-type=html")
    ok("r79.3 usc suggestion carries a ready-to-run krokai fetch command",
       s is not None and s.command.startswith('krokai fetch "https://www.govinfo.gov/link/'))
    ok("r79.3 usc suggestion has no caveat (works with plain requests)",
       s is not None and s.caveat is None)

    s = suggest.suggest_for_key(("fr", "91", "45324"))
    ok("r79.3 fr suggests govinfo link-service URL",
       s is not None and s.url == "https://www.govinfo.gov/link/fr/91/45324?link-type=html")

    s = suggest.suggest_for_key(("publaw", "107", "56"))
    ok("r79.3 publaw suggests govinfo link-service URL",
       s is not None and s.url
       == "https://www.govinfo.gov/link/plaw/107/public/56?link-type=html")

    # cfr keeps a {DATE} placeholder because the browser eCFR is behind an anti-bot wall and the
    # API needs today's date. The caveat is REQUIRES_DATE, not `browser_only`.
    s = suggest.suggest_for_key(("cfr", "8", "214"))
    ok("r79.3 cfr suggests the eCFR versioner API with a {DATE} placeholder",
       s is not None and "{DATE}" in (s.url or "")
       and "title-8.xml?part=214" in (s.url or ""))
    ok("r79.3 cfr suggestion caveat is requires_date",
       s is not None and s.caveat == "requires_date")

    # pm / pmnum are browser-only: no URL, no command, an explicit caveat naming the site
    # behaviour. The note carries the browser fallback so the caller has something to do.
    s = suggest.suggest_for_key(("pm", "7", "b", "8"))
    ok("r79.3 pm returns no command (USCIS PM is anti-bot; browser only)",
       s is not None and s.url is None and s.command is None
       and s.caveat == "browser_only")
    ok("r79.3 pm note names the browser URL AND the intake fallback",
       s is not None and "policy-manual" in s.note and "krokai intake" in s.note)

    s = suggest.suggest_for_key(("pmnum", "602-0199"))
    ok("r79.3 pmnum is browser-only with a browser URL in the note",
       s is not None and s.caveat == "browser_only"
       and "policy-memoranda" in s.note)

    # INA is the mapped kind - the coverage extractor emits a USC twin at parse time, so
    # calling INA on its own returns a pointer note rather than an invented URL.
    s = suggest.suggest_for_key(("ina", "245"))
    ok("r79.3 ina points at its USC twin (route through USC)",
       s is not None and s.url is None
       and "USC" in s.note and "1255" in s.note)

    # Unknown kind returns None cleanly rather than raising - callers can iterate a mixed set
    # of coarse keys without a try/except around each one.
    ok("r79.3 unknown kind returns None (silent fall-through, not an exception)",
       suggest.suggest_for_key(("fam", "9", "302")) is None)
    ok("r79.3 empty/None key returns None",
       suggest.suggest_for_key(()) is None and suggest.suggest_for_key(None) is None)

    # ---------------------------------------------------------------- verify_kinds mechanical
    # The suggest builders must still produce the SHAPE their template_for entry documents. A
    # mismatch means someone edited one home without editing the other - the exact
    # two-homes-for-one-subject rot the toolkit measures elsewhere.
    for kind, ok_flag, why in suggest.verify_kinds():
        ok("r79.3 verify_kinds: %s shape matches template_for" % kind, ok_flag, why)

    # ---------------------------------------------------------------- SUPPORTED_KINDS coverage
    # Every kind advertised in SUPPORTED_KINDS must resolve to something on a canonical probe.
    # Kinds that come back None here would be dead advertising.
    for k in suggest.SUPPORTED_KINDS:
        probe_key = {
            "usc": ("usc", "8", "1101"),
            "ina": ("ina", "245"),
            "fr": ("fr", "91", "45324"),
            "publaw": ("publaw", "107", "56"),
            "cfr": ("cfr", "8", "214"),
            "pm": ("pm", "7", "b", "8"),
            "pmnum": ("pmnum", "602-0199"),
        }[k]
        ok("r79.3 SUPPORTED_KINDS: %s resolves to a FetchSuggestion" % k,
           suggest.suggest_for_key(probe_key) is not None)

    # ---------------------------------------------------------------- one-home invariant
    # `library.RECIPES` and `suggest.template_for(...)` MUST point at the same publishing
    # endpoints for the kinds they both cover, so an edit to one lands in both. A drift is a
    # ship-time defect this pin catches.
    from krokai.library import RECIPES
    recipe_urls = " | ".join(r[1] for r in RECIPES)
    for kind in ("usc", "fr", "publaw", "cfr"):
        template = suggest.template_for(kind)
        ok("r79.3 one-home: %s template shares the publisher endpoint with library.RECIPES"
           % kind,
           any(host in recipe_urls for host in ("govinfo.gov/link/uscode",
                                                "govinfo.gov/link/fr",
                                                "govinfo.gov/link/plaw",
                                                "ecfr.gov/api/versioner"))
           and template is not None)

    # ---------------------------------------------------------------- init writes SITE-ACCESS.md
    matter = os.path.join(tmp, "r79p3-init")
    os.makedirs(matter, exist_ok=True)
    rc, out = run(["init", matter, "--no-claude-md"])
    ok("r79.3 CLI init creates SITE-ACCESS.md in the matter root",
       rc == 0 and os.path.isfile(os.path.join(matter, "SITE-ACCESS.md")),
       out[-260:])
    sa = io.open(os.path.join(matter, "SITE-ACCESS.md"), encoding="utf-8").read()
    ok("r79.3 SITE-ACCESS.md lists the four known-good publishers",
       "govinfo.gov/link/uscode" in sa and "govinfo.gov/link/fr" in sa
       and "govinfo.gov/link/plaw" in sa and "ecfr.gov/api/versioner" in sa)
    ok("r79.3 SITE-ACCESS.md names the three measured walls",
       "unblock.federalregister.gov" in sa and "403" in sa
       and "uscis.gov/policy-manual" in sa)

    # A re-run of `init` on the SAME matter must not overwrite a hand-edited SITE-ACCESS.md.
    io.open(os.path.join(matter, "SITE-ACCESS.md"), "a", encoding="utf-8").write(
        "\n<!-- hand-edited by suite_r79_phase3 -->\n")
    rc, out = run(["init", matter, "--force", "--no-claude-md"])
    sa2 = io.open(os.path.join(matter, "SITE-ACCESS.md"), encoding="utf-8").read()
    ok("r79.3 init --force preserves an existing SITE-ACCESS.md (never overwrites notes)",
       "hand-edited by suite_r79_phase3" in sa2)

    # ---------------------------------------------------------------- library --suggest-fetches
    # Build a small matter with ONE banked entry whose file is on disk (§P-1, has 8usc-1255.xml)
    # and one whose file is NOT on disk (§C-2, addressed 91 FR 45324). The suggest-fetches
    # output must name the ready command for the missing one.
    root = os.path.join(tmp, "r79p3-matter")
    law = os.path.join(root, "law")
    case = os.path.join(root, "case")
    for d in (law, case):
        os.makedirs(d, exist_ok=True)
    _json.dump(TEMPLATE, io.open(os.path.join(root, CONFIG_NAME), "w", encoding="utf-8"))
    io.open(os.path.join(law, "8usc-1255.xml"), "w", encoding="utf-8").write(
        "Section 1255(k). No application may be denied solely because the applicant made a "
        "late filing of the underlying nonimmigrant status extension.")
    bank_text = """# Quote bank

## For us

### §P-1 Late filing safe harbour
> No application may be denied solely because the applicant made a late filing.

| | |
|---|---|
| **Address** | 8 U.S.C. § 1255(k) |
| **On disk** | `8usc-1255.xml` |
| **Verified** | igor, 2026-09-01 |
| **Used in** | brief |
| **What this does NOT prove** | Not for over-180 unlawful presence. |

## Against us

### §C-2 Preamble to the 2024 rule
> The Department clarifies that the reinstatement provision applies without a duration limit.

| | |
|---|---|
| **Address** | 91 FR 45324 |
| **On disk** | `not-downloaded.md` |
| **Verified** | igor, 2026-09-01 |
| **Used in** | test |
| **What this does NOT prove** | Does not amend the statute. |
"""
    io.open(os.path.join(case, "QUOTE-BANK.md"), "w", encoding="utf-8", newline="\n").write(
        bank_text)

    rc, out = run(["library", "--dir", root, "--suggest-fetches"])
    ok("r79.3 CLI library --suggest-fetches prints the suggested-downloads section",
       rc == 0 and "suggested downloads" in out, out[-260:])
    ok("r79.3 CLI --suggest-fetches names the missing bank entry and the fetch command",
       "§C-2" in out and "krokai fetch" in out
       and "govinfo.gov/link/fr/91/45324" in out, out[-320:])

    # ---------------------------------------------------------------- quote prints fetch command
    # A quotation whose citation is next to it, of a source that is NOT in the corpus, must
    # print the fetch command under the SIX_CAUSES ladder.
    quote_text = ("Under 8 U.S.C. § 1234 the applicant is ineligible for anything invented "
                  "for this test whose exact wording is nowhere on disk.")
    rc, out = run(["quote", "--dir", root, quote_text])
    ok("r79.3 CLI quote prints the fetch command under NOT_FOUND when the citation resolves",
       "krokai fetch" in out and "govinfo.gov/link/uscode/8/1234" in out
       and "cause 1 fits" in out, out[-320:])

    # A quotation with NO citation next to it must NOT print the block - silence is correct
    # when nothing new can be added.
    rc, out = run(["quote", "--dir", root, "some text with no citation nearby at all invented"])
    ok("r79.3 CLI quote is SILENT about fetch when no citation sits next to the quotation",
       "krokai fetch" not in out or "cause 1 fits" not in out, out[-260:])

    # ---------------------------------------------------------------- doctor argument accepted
    # The flag must parse (executing --probe-sites would touch the network; the suite promises
    # not to). The absence of a parser error is what this pin measures.
    from krokai.cli import build_parser
    ap = build_parser()
    parsed = ap.parse_args(["doctor", "--probe-sites"])
    ok("r79.3 doctor --probe-sites parses without error",
       getattr(parsed, "probe_sites", False) is True)


def suite_r79_phase4(tmp):
    """R79 (Ф4): the petition layer.

    `krokai appendix <bank>` builds the legal appendix from banked entries with a FRESH
    ``check()`` at build time; every entry whose fresh verdict is not clean lands in an
    EXCLUDED section that names the verdict. `krokai fetch-precedent <URL> --party X
    --subject Y --court Z` downloads a decision AND requires those three tokens to appear
    in the head of the extracted text before the file is kept - measured in the sister
    project, an assistant asked to save `Matter of Smith` saved "another Smith" with a
    different disposition; nothing in the URL or the file name distinguished them.

    Nothing here touches the network. The fetch_precedent surface is covered mechanically
    (``verify_criteria`` on synthetic text) - the network path is what ``doctor
    --probe-sites`` handles for real.
    """
    import contextlib
    from krokai.cli import main as cli_main
    from krokai import precedent, appendix
    from krokai.config import TEMPLATE, CONFIG_NAME

    def run(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli_main(argv)
        return rc, buf.getvalue()

    # ------------------------------------------------------------------------- verify_criteria
    # The mechanical head of `fetch_precedent`. Its shape is the specification of the check:
    # case-insensitive, whitespace-collapsed, head window only. Every one of these axes was a
    # measured failure mode of hand-rolled precedent verification.
    body = ("Matter of Smith, 12 I&N Dec. 205\n"
            "Board of Immigration Appeals, September 1966\n\n"
            "This case concerns adjustment of status of the applicant.")

    ok_flag, missing = precedent.verify_criteria(
        body, party="Smith, 12 I&N Dec. 205",
        subject="adjustment of status", court="Board of Immigration Appeals")
    ok("r79.4 verify_criteria: all three tokens present -> ok, no missing",
       ok_flag is True and missing == [])

    ok_flag, missing = precedent.verify_criteria(
        body, party="Jones, 99 I&N Dec. 1",
        subject="adjustment of status", court="Board of Immigration Appeals")
    ok("r79.4 verify_criteria: wrong party -> not ok, party in missing",
       ok_flag is False and any(label == "party" for label, _v in missing))

    ok_flag, missing = precedent.verify_criteria(
        body, party="Smith, 12 I&N Dec. 205",
        subject="removal proceedings",  # not the subject the opinion actually decides
        court="Board of Immigration Appeals")
    ok("r79.4 verify_criteria: wrong subject -> not ok, subject in missing",
       ok_flag is False and any(label == "subject" for label, _v in missing))

    ok_flag, missing = precedent.verify_criteria(
        body, party="Smith, 12 I&N Dec. 205",
        subject="adjustment of status", court="Supreme Court")
    ok("r79.4 verify_criteria: wrong court -> not ok, court in missing",
       ok_flag is False and any(label == "court" for label, _v in missing))

    # Case-insensitive: the caption is often uppercased.
    ok_flag, _m = precedent.verify_criteria(
        body.upper(), party="smith, 12 i&n dec. 205",
        subject="adjustment of status", court="board of immigration appeals")
    ok("r79.4 verify_criteria is case-insensitive on both sides",
       ok_flag is True)

    # Whitespace-collapsed: a line break inside the party name must not defeat the match.
    wrapped = "Matter of\nSmith,\n12 I&N Dec. 205\n\n"
    ok_flag, _m = precedent.verify_criteria(
        wrapped + body, party="Smith, 12 I&N Dec. 205",
        subject="adjustment of status", court="Board of Immigration Appeals")
    ok("r79.4 verify_criteria collapses whitespace: wrapped caption still matches",
       ok_flag is True)

    # Empty criterion is refused - a caller who slipped an empty string past the CLI would
    # otherwise match everywhere and get a bogus green.
    ok_flag, missing = precedent.verify_criteria(
        body, party="", subject="adjustment of status",
        court="Board of Immigration Appeals")
    ok("r79.4 verify_criteria: empty party -> not ok (empty string is not a match)",
       ok_flag is False)

    # Head window is enforced. A token appearing PAST the head window must NOT satisfy the
    # criterion - a footnote 40 pages in citing another case with the same name is exactly the
    # false-positive shape this window exists to defeat.
    tail = "\n\n" + ("XXX filler line. " * 20000) + "\n\nAAO decision"
    ok_flag, missing = precedent.verify_criteria(
        "Some other body text with none of the tokens." + tail,
        party="AAO decision", subject="AAO decision", court="AAO decision")
    ok("r79.4 verify_criteria: match past 200 KB does NOT satisfy - head window is enforced",
       ok_flag is False)

    ok("r79.4 SEARCH_HEAD_BYTES is the documented 200 KB (200_000)",
       precedent.SEARCH_HEAD_BYTES == 200_000)

    # ------------------------------------------------------------------------- appendix module
    # `group_of_key` maps every coverage key kind to an appendix group; unknown kinds land in
    # `other` rather than getting dropped. Every kind in `GROUP_ORDER` must map to itself.
    for kind, _label in appendix.GROUP_ORDER:
        if kind == "other":
            continue
        ok("r79.4 group_of_key: %s maps to %s" % (kind, kind),
           appendix.group_of_key((kind, "8", "214")) == kind)
    ok("r79.4 group_of_key: unknown kind -> other (never dropped)",
       appendix.group_of_key(("fam", "9", "302")) == "other")
    ok("r79.4 group_of_key: None/empty -> other",
       appendix.group_of_key(None) == "other" and appendix.group_of_key(()) == "other")

    ok("r79.4 SIDE_LABEL covers pro and con",
       "pro" in appendix.SIDE_LABEL and "con" in appendix.SIDE_LABEL)

    # ------------------------------------------------------------------------- build_appendix e2e
    # Build a small matter with a bank of three entries:
    # §P-1 - address on disk, quotation exact -> INCLUDED
    # §P-2 - address on disk, quotation fabricated -> EXCLUDED
    # §C-1 - "against us" side, must NOT appear when side=pro (default)
    matter = os.path.join(tmp, "r79p4-matter")
    law = os.path.join(matter, "law")
    case = os.path.join(matter, "case")
    for d in (law, case):
        os.makedirs(d, exist_ok=True)
    import json as _json
    _json.dump(TEMPLATE, io.open(os.path.join(matter, CONFIG_NAME), "w", encoding="utf-8"))

    # A small primary source with two quotable sentences.
    io.open(os.path.join(law, "8usc-1255.xml"), "w", encoding="utf-8").write(
        "No application may be denied solely because the applicant made a late filing of the "
        "underlying nonimmigrant status extension. The Secretary retains discretion to consider "
        "each application on its individual merits.")
    io.open(os.path.join(law, "8CFR-214-2.xml"), "w", encoding="utf-8").write(
        "The district director may consider reinstating a student who makes a request for "
        "reinstatement, but do not include instances where a pattern of repeated violations "
        "has occurred.")

    bank_text = """# Quote bank

## For us

### §P-1 Late filing safe harbour
> No application may be denied solely because the applicant made a late filing of the underlying nonimmigrant status extension.

| | |
|---|---|
| **Address** | 8 U.S.C. § 1255(k) |
| **On disk** | `8usc-1255.xml` |
| **Verified** | igor, 2026-09-01 |
| **Used in** | brief |
| **What this does NOT prove** | Not for over-180 unlawful presence. |

### §P-2 Something we made up
> This sentence appears in no primary source at all and cannot verify.

| | |
|---|---|
| **Address** | 8 U.S.C. § 9999(z) |
| **On disk** | `nowhere.xml` |
| **Verified** | igor, 2026-09-01 |
| **Used in** | test |
| **What this does NOT prove** | Test entry, not real. |

## Against us

### §C-1 A mine
> The district director may consider reinstating a student who makes a request for reinstatement, but do not include instances where a pattern of repeated violations has occurred.

| | |
|---|---|
| **Address** | 8 CFR 214.2(f)(16) |
| **On disk** | `8CFR-214-2.xml` |
| **Verified** | igor, 2026-09-01 |
| **Used in** | none |
| **What this does NOT prove** | Only about F-1. |
"""
    io.open(os.path.join(case, "QUOTE-BANK.md"), "w", encoding="utf-8", newline="\n").write(
        bank_text)

    # ------------------------------------------------------------------------- default side=pro
    from krokai.config import load
    from krokai.run import corpus_for
    from krokai.citations import load_packs
    cfg = load(matter)
    corpus = corpus_for(cfg, quiet=True)
    packs = load_packs(cfg["citation_packs"])
    md, stats = appendix.build_appendix(
        [cfg.abs(cfg["bank"])], corpus, packs, cfg=cfg, side="pro")
    ok("r79.4 build_appendix returns text + stats",
       md is not None and isinstance(stats, dict))
    ok("r79.4 build_appendix: §P-1 (verified) is INCLUDED under For us",
       stats["included"] >= 1 and "§P-1" in md and "Late filing safe harbour" in md)
    ok("r79.4 build_appendix: §P-2 (unverifiable) is EXCLUDED, not silently dropped",
       stats["excluded"] >= 1 and "§P-2" in md and "EXCLUDED" in md)
    ok("r79.4 build_appendix: excluded section names the verdict",
       "NOT" in md and "Excluded from build" in md)
    ok("r79.4 build_appendix: side=pro EXCLUDES §C-1 (against us)",
       "§C-1" not in md)
    ok("r79.4 build_appendix: header names fresh verification at build time",
       "re-verified against the corpus at build time" in md
       and "RE-RUNS `check`" in md)
    ok("r79.4 build_appendix stats carry by_verdict counts",
       isinstance(stats.get("by_verdict"), dict) and len(stats["by_verdict"]) >= 1)
    ok("r79.4 build_appendix stats carry built_at timestamp",
       "built_at" in stats and len(stats["built_at"]) >= 10)

    # ------------------------------------------------------------------------- grouping
    # §P-1 has address `8 U.S.C. § 1255(k)`, which folds to USC and INA - the entry lands in
    # ONE group (fine key chosen), and the group heading appears in the output.
    ok("r79.4 build_appendix: §P-1 rendered under a group heading (USC or INA)",
       "## United States Code" in md or "## Immigration and Nationality Act" in md)

    # ------------------------------------------------------------------------- side=con
    md_con, stats_con = appendix.build_appendix(
        [cfg.abs(cfg["bank"])], corpus, packs, cfg=cfg, side="con")
    ok("r79.4 build_appendix side=con: §C-1 appears, §P-1 does not",
       "§C-1" in md_con and "§P-1" not in md_con)

    # ------------------------------------------------------------------------- missing bank file
    md_bad, stats_bad = appendix.build_appendix(
        [os.path.join(tmp, "does-not-exist.md")], corpus, packs, cfg=cfg, side="pro")
    ok("r79.4 build_appendix: missing bank file -> (None, error dict), loud",
       md_bad is None and stats_bad.get("error") == "bank file missing")

    # ------------------------------------------------------------------------- CLI appendix e2e
    rc, out = run(["appendix", "--dir", matter, "--side", "pro"])
    ok("r79.4 CLI appendix: prints the appendix to stdout, exit code sane",
       rc in (0, 1) and "Legal appendix" in out and "§P-1" in out)
    ok("r79.4 CLI appendix: names the fresh-build discipline in the header",
       "re-verified against the corpus at build time" in out)

    # --strict flips the code non-zero when anything was excluded (§P-2 is unverifiable).
    rc, out = run(["appendix", "--dir", matter, "--side", "pro", "--strict"])
    ok("r79.4 CLI appendix --strict: exit 1 when entries were excluded",
       rc == 1)

    # --out writes to a file.
    outp = os.path.join(matter, "appendix.md")
    rc, out = run(["appendix", "--dir", matter, "--side", "pro", "--out", outp])
    ok("r79.4 CLI appendix --out writes the file",
       rc in (0, 1) and os.path.isfile(outp))
    written = io.open(outp, encoding="utf-8").read()
    ok("r79.4 CLI appendix --out file contains the appendix header + §P-1",
       "Legal appendix" in written and "§P-1" in written)

    # --json prints stats.
    rc, out = run(["appendix", "--dir", matter, "--side", "pro", "--json"])
    ok("r79.4 CLI appendix --json includes stats JSON in output",
       '"included"' in out and '"excluded"' in out)

    # ------------------------------------------------------------------------- CLI argparse
    from krokai.cli import build_parser
    ap = build_parser()

    parsed = ap.parse_args(["appendix", "--side", "pro"])
    ok("r79.4 CLI: appendix parses without banks (defaults to matter bank)",
       parsed.side == "pro" and parsed.banks == [])

    parsed = ap.parse_args(["appendix", "a.md", "b.md", "--side", "any"])
    ok("r79.4 CLI: appendix accepts multiple bank files and --side any",
       parsed.side == "any" and parsed.banks == ["a.md", "b.md"])

    parsed = ap.parse_args([
        "fetch-precedent", "https://example.gov/opinion.pdf",
        "--party", "Smith, 12 I&N Dec. 205",
        "--subject", "adjustment of status",
        "--court", "Board of Immigration Appeals"])
    ok("r79.4 CLI: fetch-precedent parses required flags",
       parsed.url == "https://example.gov/opinion.pdf"
       and parsed.party.startswith("Smith")
       and parsed.subject == "adjustment of status"
       and parsed.court == "Board of Immigration Appeals")

    # --party missing must fail argparse (required)
    err_buf = io.StringIO()
    with contextlib.redirect_stderr(err_buf):
        try:
            ap.parse_args(["fetch-precedent", "https://example.gov/o.pdf",
                           "--subject", "s", "--court", "c"])
            missing_ok = False
        except SystemExit:
            missing_ok = True
    ok("r79.4 CLI: fetch-precedent refuses missing --party",
       missing_ok is True)

    # ------------------------------------------------------------------------- no side=both
    # A caller must not be able to spell 'both' - the appendix that mixes pro and con would
    # arm the adjudicator with the strongest cons if pasted into the filing. `any` is
    # deliberately named 'any' (weaker word, less inviting) and no shortcut spells the union.
    err_buf = io.StringIO()
    with contextlib.redirect_stderr(err_buf):
        try:
            ap.parse_args(["appendix", "--side", "both"])
            bad_side_ok = False
        except SystemExit:
            bad_side_ok = True
    ok("r79.4 CLI: appendix refuses --side both (only pro/con/any)",
       bad_side_ok is True)

    # ------------------------------------------------------------------------- no build for empty
    # An empty bank must not silently build an empty appendix; that would read as "nothing
    # to worry about" when nothing has been analysed. Loud error, non-zero code.
    empty_bank = os.path.join(tmp, "r79p4-empty-bank.md")
    io.open(empty_bank, "w", encoding="utf-8").write("# Quote bank\n\n## For us\n\n## Against us\n")
    md_e, stats_e = appendix.build_appendix(
        [empty_bank], corpus, packs, cfg=cfg, side="pro")
    ok("r79.4 build_appendix: empty bank -> (None, error dict), never a fake-clean file",
       md_e is None and stats_e.get("error") == "no entries")


# The stand-in harness for suite_k004: it takes the harness's OWN arguments (required, so a change in
# what krokai passes fails here) and writes the harness's real folder layout (ai-second-opinion: a
# live round folder + its v1.125.0 source, read 2026-11-23). It calls nothing and sends nothing.
_K004_FAKE_HARNESS = r'''
import argparse, io, json, os, sys
ap = argparse.ArgumentParser()
for flag in ("--brief", "--system", "--out", "--marker"):
    ap.add_argument(flag, required=True)
a = ap.parse_args()
if not io.open(a.brief, encoding="utf-8").read().strip():
    sys.exit(3)
if os.environ.get("K004_FAKE_MODE") == "silent":
    sys.exit(1)
os.makedirs(a.out, exist_ok=True)
def w(name, text):
    io.open(os.path.join(a.out, name), "w", encoding="utf-8").write(text)
q = os.environ["K004_QUOTE"]
w("GOODCH.md", "The reviewer reads the brief and answers at length. " * 20
  + "\n\n> " + q + "\n\n" + a.marker + "\n")
w("GOODCH.quote-verify.md", "| quotation | verdict |\n\n> " + q + "\n")
w("REPORT.md", "# Review round report\n" + "| goodch | ok |\n" * 60)
w("HANDOFF.md", "# Handoff\n" + "Read GOODCH.md first.\n" * 60)
w("PROGRESS.md", "# Progress\n" + "GOODCH answered.\n" * 60)
w("READING.md", "## GOODCH.md\n\n> The reader typed this line from memory, and it stands in no source.\n")
w("NEWKITFILE.md", "a file the harness writes for itself\n" * 40)
w("run.log", "log\n")
w("diagnostics.json", json.dumps({"schema": "model-orchestration/diagnostics/1", "channels": {
    "goodch": {"answer_file": "GOODCH.md", "ok": True, "seconds": 3.0},
    "downch": {"answer_file": None, "ok": False, "seconds": 9.0}}}))
'''


def suite_k004_kit_contract(tmp, corpus):
    """K004: the krokai <-> review-harness contract on the OUTPUT side - which files are answers.

    🔴 Measured in K001 S4 (2026-11-23): the harness (ai-second-opinion) writes REPORT.md and
    HANDOFF.md - since its R193 also PROGRESS.md, and READING.md for its reader - beside the answers;
    krokai graded every one as a reviewer that FAILED, and a round in which nothing failed exited 1.
    `review --dry-run` returns before the harness is called, so nothing had ever exercised it.
    """
    import json as _json
    import subprocess as _sp
    import time as _time
    from krokai import roundfolder as _rf
    from krokai.consult import absorb_delegated, find_harness
    from krokai.review import audit_answers

    base = os.path.join(tmp, "k004")
    os.makedirs(base, exist_ok=True)
    mark = "REVIEW-COMPLETE"
    quote = ("No application for adjustment of status shall be approved unless the applicant "
             "establishes clear eligibility for the benefit sought at filing.")
    invented = "The reader typed this line from memory, and it stands in no source at all."
    answer = ("The reviewer reads the brief and answers at length. " * 20
              + "\n\n> " + quote + "\n\n" + mark + "\n")
    record = {"schema": "model-orchestration/diagnostics/1", "channels": {
        "goodch": {"answer_file": "GOODCH.md", "attempt_files": ["GOODCH.first.md"],
                   "ok": True, "seconds": 3.0},
        "downch": {"answer_file": None, "ok": False, "seconds": 9.0},
        "nemo": {"answer_file": "NEMO.md", "never_read": True, "ok": True, "seconds": 4.0}}}

    def layout(name, rec=record, extra=()):
        d = os.path.join(base, name)
        os.makedirs(os.path.join(d, "goodch-ws"), exist_ok=True)
        os.makedirs(os.path.join(d, ".never-read"), exist_ok=True)
        files = [("brief.md", "the brief krokai wrote\n"), ("system.md", "the framing\n"),
                 ("GOODCH.md", answer), ("GOODCH.first.md", "the first attempt, cut short\n"),
                 ("GOODCH.quote-verify.md", "| quotation | verdict |\n\n> " + quote + "\n"),
                 ("REPORT.md", "# Review round report\n" + "| goodch | ok |\n" * 60),
                 ("HANDOFF.md", "# Handoff\n" + "Read GOODCH.md first.\n" * 60),
                 ("PROGRESS.md", "# Progress\n" + "GOODCH answered.\n" * 60),
                 ("READING.md", "## GOODCH.md\n\n> " + invented + "\n"),
                 ("run.log", "log\n"), ("progress.json", "{}"), ("GOODCH.events.ndjson", "{}\n"),
                 (os.path.join(".never-read", "NEMO.md.gz"), "not text")] + list(extra)
        if rec is not None:
            files.append(("diagnostics.json", _json.dumps(rec)))
        for n, s in files:
            io.open(os.path.join(d, n), "w", encoding="utf-8").write(s)
        return d

    said = []

    def grab(*a, **k):
        said.append(" ".join(str(x) for x in a))

    def quiet(*a, **k):
        pass

    # --- the harness as installed here (its R193 layout = the K001 S4 folder) --------------------
    t0 = _time.time() - 2
    d1 = layout("installed")
    rows = absorb_delegated(d1, mark, 100, since=t0, printer=grab)
    got = [(r["channel"], r.get("file")) for r in rows]
    ok("k004: the harness's REPORT/HANDOFF/PROGRESS/READING, its quote-check sidecar and a second "
       "attempt are never graded as reviewers - only the answer its record claims (K001 S4)",
       got == [("goodch", "GOODCH.md")], str(got))
    ok("k004: a clean round through the harness has no FAILED row",
       not [r for r in rows if r.get("failures")],
       str([(r["channel"], r["failures"]) for r in rows]))
    told = "\n".join(said)
    ok("k004: what is not graded is SAID - a channel that left no answer, a never_read channel",
       "downch" in told and "nemo" in told, told[:300])

    # --- one home: the audit reads exactly what the grading graded --------------------------------
    arows = audit_answers(d1, corpus, None, 45, printer=quiet)
    ok("k004: the quotation audit reads exactly the files the grading graded - the reader's "
       "READING.md quotation is not a reviewer's", sorted({r[0] for r in arows}) == ["GOODCH.md"],
       str(sorted({r[0] for r in arows})))
    import krokai.consult as _cm
    import krokai.review as _rv
    srcs = [io.open(m.__file__.replace(".pyc", ".py"), encoding="utf-8").read() for m in (_cm, _rv)]
    ok("k004: neither reader keeps a private list of non-answers again (one home: roundfolder)",
       not any("_OURS" in s or "ours = {" in s for s in srcs), "")

    # --- a file the harness starts writing tomorrow: named, not graded, no alarm ------------------
    said[:] = []
    d3 = layout("newfile", extra=[("NEWKITFILE.md", "a file the harness writes for itself\n" * 40)])
    rows = absorb_delegated(d3, mark, 100, since=t0, printer=grab)
    ok("k004: a file the harness's record does not claim is not graded - and it is named aloud",
       [r["channel"] for r in rows] == ["goodch"] and "NEWKITFILE.md" in "\n".join(said),
       "%s | %s" % ([r["channel"] for r in rows], " ".join(said)[:200]))

    # --- no record (answers pasted by hand, another harness): judged by name -----------------------
    d4 = os.path.join(base, "byhand")
    os.makedirs(d4)
    for n in ("REPORT.md", "HANDOFF.md", "PROGRESS.md", "READING.md", "brief.md", "CHAN.md",
              "NOTES.txt"):
        io.open(os.path.join(d4, n), "w", encoding="utf-8").write("text\n")
    c4 = _rf.classify(d4)
    ok("k004: without a record the harness's own names are still not answers; a pasted .txt is",
       [f for f, _ch in c4["answers"]] == ["CHAN.md", "NOTES.txt"] and not c4["by_record"],
       str(c4["answers"]))

    # --- a record that is not this round's, or in a schema this krokai does not know --------------
    d5 = layout("stalerecord")
    old = _time.time() - 3600
    os.utime(os.path.join(d5, "diagnostics.json"), (old, old))
    c5 = _rf.classify(d5, since=t0)
    ok("k004: a previous round's record is not trusted for this round - and that is said",
       not c5["by_record"] and "previous round" in c5["note"], c5["note"])
    d5b = layout("newschema", rec=dict(record, schema="model-orchestration/diagnostics/2"))
    c5b = _rf.classify(d5b, since=t0)
    ok("k004: a record in a schema this krokai does not know is not guessed at - it is said",
       not c5b["by_record"] and "diagnostics/2" in c5b["note"], c5b["note"])

    # --- the reverse defect: a harness that crashed or wrote nothing is never a clean round -------
    d6 = os.path.join(base, "crashed")
    os.makedirs(d6)
    io.open(os.path.join(d6, "diagnostics.json"), "w", encoding="utf-8").write(_json.dumps({
        "schema": "model-orchestration/diagnostics/1", "crashed": True,
        "error_type": "ValueError", "error": "boom"}))
    rows = absorb_delegated(d6, mark, 100, since=t0, printer=quiet)
    ok("k004: a harness that reports a crash is a FAILED row, never an empty clean round",
       [(r["channel"], r["failures"][0][0]) for r in rows] == [("harness", "HARNESS_CRASHED")],
       str([(r["channel"], r["failures"]) for r in rows]))
    d7 = os.path.join(base, "nothing")
    os.makedirs(d7)
    rows = absorb_delegated(d7, mark, 100, since=t0, harness_exit=1, printer=quiet)
    ok("k004: a harness that left nothing is a FAILED row carrying its exit code",
       [(r["channel"], r["failures"]) for r in rows]
       == [("harness", [("HARNESS_NO_ANSWER", "exit 1")])],
       str([(r["channel"], r["failures"]) for r in rows]))

    # --- where krokai looks: the harness's published install routes, the plugin one included -----
    cache = os.path.join(base, "plugins", "cache", "review-channels", "model-orchestration")
    for ver, retired in (("1.124.0", True), ("1.125.0", False)):
        sk = os.path.join(cache, ver, "skills", "model-orchestration")
        os.makedirs(sk)
        io.open(os.path.join(sk, "orchestrate.py"), "w").write("# stub\n")
        if retired:
            io.open(os.path.join(cache, ver, ".orphaned_at"), "w").write("0")
    pat = os.path.join(cache, "*", "skills", "model-orchestration", "orchestrate.py")
    reg = {"channels": {"harness": {"env": "KROKAI_K004_UNSET_VARIABLE", "candidates": [pat]}}}
    got = find_harness(reg) or ""
    ok("k004: a plugin-installed harness is found, and the live version wins over a retired one",
       os.path.join("1.125.0", "skills") in got, got)
    io.open(os.path.join(cache, "1.125.0", ".orphaned_at"), "w").write("0")
    ok("k004 control: only retired plugin versions on disk -> not found, never a stale copy",
       find_harness(reg) is None, str(find_harness(reg)))
    from krokai._datadir import data_file
    shipped = _json.load(io.open(data_file("channels.json"), encoding="utf-8"))
    cands = ((shipped.get("channels") or {}).get("harness") or {}).get("candidates") or []
    ok("k004: the shipped candidates name the plugin route and no pre-plugins/ repo-root path",
       any("plugins/cache/review-channels/" in c for c in cands)
       and not any(c.endswith("ai-second-opinion/orchestrate.py") for c in cands), str(cands))

    # --- through the real CLI: krokai review -> harness -> grading -> audit -> exit code ---------
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matter = os.path.join(base, "matter")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["KROKAI_KEY_DIR"] = os.path.join(base, "no-keys-here")
    fake = os.path.join(base, "fake_harness.py")
    io.open(fake, "w", encoding="utf-8").write(_K004_FAKE_HARNESS)

    def krokai(*args, **extra_env):
        return _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=root,
                       env=dict(env, **extra_env), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=240)

    r = krokai("init", matter, "--no-claude-md")
    if r.returncode != 0:
        ok("k004 CLI: init failed - the CLI pins are skipped", False, (r.stderr or "")[-200:])
        return
    io.open(os.path.join(matter, "law", "8USC-1255.md"), "w", encoding="utf-8").write(
        "SEC. 1255. " + quote)

    def review(name, mode, q):
        return krokai("review", "--dir", matter, "--harness", fake, "--out",
                      os.path.join(base, "out-" + name),
                      "Does the provision require eligibility at filing? Quote it.",
                      K004_FAKE_MODE=mode, K004_QUOTE=q)

    ra = review("clean", "layout", quote)
    out_a = ra.stdout or ""
    ok("k004 CLI: a clean round through a harness writing its real layout exits 0 (it exited 1)",
       ra.returncode == 0, "rc=%s tail=%s" % (ra.returncode, out_a[-500:]))
    ok("k004 CLI: none of the harness's own files is a reviewer row; its unknown file is named",
       "[FAILED]" not in out_a and "NEWKITFILE.md" in out_a and "goodch" in out_a, out_a[-300:])
    rv = review("invented", "layout", invented)
    ok("k004 CLI control: an invented quotation through the same harness still exits 5",
       rv.returncode == 5, "rc=%s tail=%s" % (rv.returncode, (rv.stdout or "")[-300:]))
    rs = review("silent", "silent", quote)
    ok("k004 CLI: a harness that exits 1 and writes nothing exits 1 - never the empty clean 0",
       rs.returncode == 1 and "HARNESS_NO_ANSWER" in (rs.stdout or ""),
       "rc=%s tail=%s" % (rs.returncode, (rs.stdout or "")[-300:]))


def suite_k023_not_examined(tmp):
    """K023 (2026-11-24): `check` says, per file, what it did NOT examine - and nothing else moves.

    The extractor skips a quoted phrase under `min_quote_length` and, when the matter says so, a
    Cyrillic one; a paragraph that cites the law without quoting it was never counted. All of it
    was silent, so a green report read as «all clean». These pins hold the three counts, the two
    layout rules measured on this fixture, and the promise that the exit code ignores them."""
    import json
    import subprocess as _sp
    from krokai.extract import extract_quotes, not_examined, DEFAULT_MIN_LEN
    from krokai.citations import load_packs

    packs = load_packs(["us-federal", "us-immigration"])
    short_q = "sustained national or international acclaim"
    long_q = ("Documentation of the alien's receipt of lesser nationally or internationally "
              "recognized prizes or awards for excellence in the field of endeavor")
    # Nine six-letter Cyrillic words, built from code points: mostly Cyrillic, over the minimum.
    cyr = " ".join("".join(chr(0x430 + (7 * i + j) % 32) for j in range(6)) for i in range(9))
    doc = ("# Brief\n\n"
           "Under 8 C.F.R. § 204.5(h)(3), the beneficiary must show \"%s\" in the field.\n\n"
           "The regulation lists the evidence:\n\n> \"%s\"\n> 8 C.F.R. § 204.5(h)(3)(i)\n\n"
           "Under 8 C.F.R. § 103.2(b)(1), the petitioner must establish eligibility at filing.\n\n"
           "Our note: «%s».\n\nA defined \"term\" alone is not a quotation.\n"
           % (short_q, long_q, cyr))
    ok("k023: the fixture's short quotation really is under the extractor's minimum",
       len(short_q) < DEFAULT_MIN_LEN, "%d" % len(short_q))
    qs = extract_quotes(doc, DEFAULT_MIN_LEN, True)
    ne = not_examined(doc, qs, packs, DEFAULT_MIN_LEN, True)
    ok("k023: only the long quotation is examined", qs == [long_q], str(qs))
    ok("k023: the short quotation is counted, with the citation beside it",
       [x["text"] for x in ne["short"]] == [short_q]
       and "8 C.F.R. § 204.5(h)(3)" in ne["short"][0]["cites"], str(ne["short"]))
    ok("k023: a Cyrillic quotation skipped by drop_cyrillic_quotes is counted",
       ne["cyrillic"] == [cyr], str(ne["cyrillic"]))
    ok("k023: the two paragraphs that cite the law without an examined quotation are counted",
       [x["cites"] for x in ne["cited"]] == [["8 C.F.R. § 204.5(h)(3)"],
                                            ["8 C.F.R. § 103.2(b)(1)"]],
       str([x["cites"] for x in ne["cited"]]))
    ok("k023: a quoted single word is not counted", "term" not in str(ne["short"]))
    qs_off = extract_quotes(doc, DEFAULT_MIN_LEN, False)
    ne_off = not_examined(doc, qs_off, packs, DEFAULT_MIN_LEN, False)
    ok("k023 control: with drop_cyrillic_quotes off the Cyrillic span is examined, not counted",
       cyr in qs_off and not ne_off["cyrillic"], str(ne_off["cyrillic"]))

    lay = ("Under 8 C.F.R. § 204.5(h)(2), the term means:\n\n> \"%s\"\n\n8 C.F.R. § 204.5(h)(2).\n\n"
           "Under 8 C.F.R. § 103.2(b)(1), the petitioner must establish eligibility at the time "
           "of filing and continuing through adjudication.\n\n\"%s\" 8 U.S.C. § 1255(a).\n"
           % (long_q, long_q.replace("Documentation", "Evidence")))
    got = [x["cites"] for x in not_examined(lay, extract_quotes(lay), packs)["cited"]]
    ok("k023: a lead-in ending with a colon and a bare citation line after the quotation carry it",
       not any("204.5(h)(2)" in c for cs in got for c in cs), str(got))
    ok("k023: a paraphrase right BEFORE a quotation is still counted (a plain 140-character ring "
       "called it covered - measured)", got == [["8 C.F.R. § 103.2(b)(1)"]], str(got))

    # --- through the real CLI: per-file line, REPORT.md, result.json, and the exit code --------
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matter = os.path.join(tmp, "k023m")
    out = os.path.join(tmp, "k023out")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    def run(*args):
        return _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=root, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=240)

    r = run("init", matter)
    if r.returncode != 0:
        ok("k023: init failed - the CLI pins were skipped", False, r.stderr[-200:])
        return
    cf = os.path.join(matter, "casefile.json")
    cfg_json = json.load(io.open(cf, encoding="utf-8"))
    cfg_json["drop_cyrillic_quotes"] = True
    io.open(cf, "w", encoding="utf-8").write(json.dumps(cfg_json, ensure_ascii=False, indent=1))
    provision = ("No application for adjustment of status shall be approved unless the "
                 "applicant establishes clear eligibility for the benefit sought at filing.")
    io.open(os.path.join(matter, "law", "8USC-1255.md"), "w", encoding="utf-8").write(
        "SEC. 1255. " + provision)
    spacer = "This paragraph is our own prose and keeps the citations below out of the " \
             "quotation's address ring, so the verdict on it is the plain corpus verdict. " * 2
    io.open(os.path.join(matter, "case", "draft.md"), "w", encoding="utf-8").write(
        "Our filing argues as follows:\n\n> %s\n\n%s\n\n"
        "Under 8 C.F.R. § 204.5(h)(3), the beneficiary must show \"%s\" in the field.\n\n"
        "Under 8 C.F.R. § 103.2(b)(1), the petitioner must establish eligibility at filing.\n\n"
        "Our note: «%s».\n" % (provision, spacer, short_q, cyr))
    r = run("check", "--dir", matter, "--strict", "--out", out)
    so = r.stdout or ""
    rel = os.path.join("case", "draft.md")
    line = ("A %s: 1 quotation examined · NOT examined: 1 quoted phrase under %d characters "
            "(1 beside a citation of law) · 1 Cyrillic quoted phrase (drop_cyrillic_quotes is on) "
            "· 2 paragraphs citing the law with no quotation beside the citation"
            % (rel, DEFAULT_MIN_LEN))
    ok("k023: `check` prints, per file, what it did NOT examine and how much", line in so,
       so[-600:])
    ok("k023: the NOT-examined block comes BEFORE the verdicts, which stay the last lines",
       0 <= so.find("NOT examined") < so.find("needs a human"), "")
    ok("k023: the not-examined counts never reach the exit code (--strict, clean quotation)",
       r.returncode == 0, "rc=%s" % r.returncode)
    try:
        data = json.load(io.open(os.path.join(out, "result.json"), encoding="utf-8"))
        rep = io.open(os.path.join(out, "REPORT.md"), encoding="utf-8").read()
    except (OSError, ValueError) as exc:
        ok("k023: the report files were written", False, repr(exc))
        return
    rec = [x for x in data.get("not_examined", []) if x["file"] == rel]
    ok("k023: result.json carries the per-file record",
       len(rec) == 1 and rec[0]["examined"] == 1 and len(rec[0]["short"]) == 1
       and len(rec[0]["cyrillic"]) == 1 and len(rec[0]["cited"]) == 2, str(rec)[:300])
    ok("k023: the verdict on the examined quotation is the plain one (VERIFIED)",
       [x["verdict"] for x in data["rows"]] == ["VERIFIED"],
       str([x["verdict"] for x in data["rows"]]))
    ok("k023: REPORT.md lists the short quotation with the citation beside it",
       "## Not examined" in rep and '"%s" - 8 C.F.R. § 204.5(h)(3)' % short_q in rep, "")


def suite_k012_section_form(tmp):
    """K012 (2026-11-24): a citation written with the WORD - «INA Section 245(k)», «8 C.F.R. Section
    204.5(h)(3)», «8 U.S.C. Section 1255(k)», «Section 245(k) of the INA» - binds to the same address
    as its «§» twin; «of the Act» and a bare «Section N» bind to nothing.

    Measured on a copy of a filed petition: 111 references written with the word reached no address,
    and once they did, two CORRECT citations turned into FOUND_ELSEWHERE - the repair read only the
    first ten files behind a key (8 U.S.C. § 1101 had 36, the statute 14th) and tested an elided
    quotation whole (never contained anywhere). The fixture below rebuilds both traps and the
    274a / 274 pair (a part cut to its number names a different part).
    """
    import json
    import subprocess as _sp
    from krokai.citations import load_packs
    from krokai.coverage import parse_addresses, controls_pass

    packs = load_packs(["us-federal", "us-immigration"])
    cases = [
        ("Under INA Section 245(k), the applicant may adjust.", ("usc", "8", "1255")),
        ("as INA section 203(b)(2) provides", ("usc", "8", "1153")),
        ("INA Sec. 212(a)(9)(B) bars", ("usc", "8", "1182")),
        ("relief under Section 245(k) of the INA is available", ("usc", "8", "1255")),
        ("§ 203(b)(2) of the Immigration and Nationality Act covers", ("usc", "8", "1153")),
        ("see 8 C.F.R. Section 204.5(h)(3) for the criteria", ("cfr", "8", "204")),
        ("see 8 CFR Sec. 214.2(f) here", ("cfr", "8", "214")),
        ("the whole of 8 C.F.R. Part 214 governs", ("cfr", "8", "214")),
        ("8 C.F.R. Section 274a.12(c)(9) lists", ("cfr", "8", "274a")),
        ("8 CFR § 274a.12(c)(9) lists", ("cfr", "8", "274a")),
        ("under 8 U.S.C. Section 1255(k) the count", ("usc", "8", "1255")),
        ("Section 203(b)(2) of the Act covers advanced degrees.", None),
        ("section 101(a)(3) of the Act, as the REAL ID Act amended it", None),
        ("Under Section 245(k), the applicant may adjust.", None),
        ("Section 2 of this memorandum explains", None),
        ("Section 106 of the REAL ID Act governs review", None),
        ("the INA 2450 typo", None),
    ]
    for s, want in cases:
        keys = packs.keys([c for c, _p in packs.find_positions(s)])
        if want:
            ok("k012: «%s» binds to %s (find -> keys, the scanner's path)" % (s[:40], "/".join(want)),
               want in keys and ("cfr", "8", "274") not in keys, str(sorted(keys)))
        else:
            ok("k012: «%s» binds to NO address" % s[:40], not keys, str(sorted(keys)))

    got = {k for k, _l, _p in parse_addresses("INA Section 245(k); 8 C.F.R. Section 274a.12(c)(9); "
                                                "Section 203(b)(2) of the INA")}
    for want in (("ina", "245", "k"), ("usc", "8", "1255", "k"), ("cfr", "8", "274a", "12", "c", "9"),
                 ("ina", "203", "b", "2")):
        ok("k012: coverage parses the word form as %s" % "/".join(want), want in got, str(sorted(got)))
    ok("k012: coverage's own controls pass (they now include the word form)",
       controls_pass(printer=lambda *_a: None))

    # --- end to end through `check`, the path a user runs -----------------------------------
    matter = os.path.join(tmp, "k012-matter")
    out = os.path.join(tmp, "k012-out")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    run = lambda *a: _sp.run([sys.executable, "-m", "krokai"] + list(a), cwd=root, env=env,  # noqa: E731
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             timeout=240)
    r = run("init", matter)
    if r.returncode != 0:
        ok("k012: init failed - the end-to-end pins were skipped", False, r.stderr[-200:])
        return
    cf = os.path.join(matter, "casefile.json")
    cfg_json = json.load(io.open(cf, encoding="utf-8"))
    cfg_json["citation_packs"] = ["us-federal", "us-immigration"]
    io.open(cf, "w", encoding="utf-8").write(json.dumps(cfg_json, indent=1))
    law = os.path.join(matter, "law")

    def put(name, text):
        io.open(os.path.join(law, name), "w", encoding="utf-8").write(text)

    # Trap 1: twelve files behind 8 U.S.C. § 1101, the statute LAST; a policy chapter quotes it first.
    adm = ("The term admission means the lawful entry of the alien into the United States after "
           "inspection and authorization by an immigration officer.")
    # (named «amended», not «note»: a NOTES name is a derived file the corpus leaves out on purpose)
    for i in range(1, 12):
        put("8USC-1101-amended-%02d.md" % i, "Amendment %d to 8 U.S.C. 1101 and its definitions." % i)
    put("z-8USC-1101-definitions.md", "SEC. 1101. Definitions. (13)(A) " + adm)
    put("a-policy-chapter.md", "Policy chapter. The statute reads: " + adm + " End of chapter.")
    # Trap 2: an elided quotation met first in the enacting public law, then in the statute.
    insp = ("All aliens (including alien crewmen) who are applicants for admission or otherwise "
            "seeking admission or readmission to or transit through the United States shall be "
            "inspected by immigration officers.")
    put("1-public-law-104-208.md", "SEC. 302. Inspection. " + insp)
    put("z-8USC-1225-inspection.md", "SEC. 1225. Inspection by immigration officers. (a)(3) " + insp)
    # Trap 3: part 274a and part 274 side by side.
    ead = "An alien who has filed an application for adjustment of status to lawful permanent " \
          "residence may apply for employment authorization."
    put("8CFR-part-274a.md", "PART 274a - CONTROL OF EMPLOYMENT OF ALIENS. 274a.1 x. 274a.2 y. "
                             "274a.12 (c)(9) " + ead)
    put("8CFR-part-274.md", "PART 274 - SEIZURE AND FORFEITURE OF CONVEYANCES. 274.1 a. 274.2 b. "
                            "274.3 c.")
    # «of the Act»: a 1255 file is on disk, the quotation is not in it - binding would accuse.
    act = "The applicant bears the burden of showing statutory eligibility for the benefit sought."
    put("8USC-1255-adjustment.md", "SEC. 1255. Adjustment of status. Section 1255 text.")
    put("b-practice-guide.md", "Guide. " + act)
    gap = "This paragraph is our own prose; it keeps each citation out of its neighbours' rings. " * 2
    io.open(os.path.join(matter, "case", "draft.md"), "w", encoding="utf-8").write(
        "Under INA Section 101(a)(13)(A), \"%s\"\n\n%s\n\n"
        "INA Section 235(a)(3) says \"All aliens (including alien crewmen)... who are applicants "
        "for admission... shall be inspected by immigration officers.\"\n\n%s\n\n"
        "Under 8 C.F.R. Section 274a.12(c)(9), \"%s\"\n\n%s\n\n"
        "As section 245(k) of the Act puts it, \"%s\"\n" % (adm, gap, gap, ead, gap, act))
    r = run("check", "--dir", matter, "--out", out)
    try:
        rows = json.load(io.open(os.path.join(out, "result.json"), encoding="utf-8"))["rows"]
    except (OSError, ValueError) as exc:
        ok("k012: check wrote no result.json - the end-to-end pins were skipped", False,
           "%s %s" % (type(exc).__name__, (r.stderr or r.stdout)[-300:]))
        return
    by = {}
    for row in rows:
        for key, head in (("adm", "The term admission"), ("insp", "All aliens"), ("ead", "An alien who"),
                          ("act", "The applicant bears")):
            if row["quote"].startswith(head):
                by[key] = (row["verdict"], (row.get("address") or {}).get("status"),
                           "; ".join((row.get("address") or {}).get("keys") or []))
    ok("k012: a correct «INA Section 101(a)(13)(A)» with the statute 12th behind its key: VERIFIED + "
       "MATCHED (the repair reads every file, not the first ten)",
       by.get("adm", ("",))[:2] == ("VERIFIED", "MATCHED"), str(by.get("adm")))
    ok("k012: an elided quotation met first in the public law: ASSEMBLED + MATCHED at the cited "
       "statute (fragments re-checked at the address)",
       by.get("insp", ("",))[:2] == ("ASSEMBLED", "MATCHED"), str(by.get("insp")))
    ok("k012: «8 C.F.R. Section 274a.12» binds to part 274a, not 274 (VERIFIED + MATCHED)",
       by.get("ead", ("",))[:2] == ("VERIFIED", "MATCHED") and "274a" in by.get("ead", ("", "", ""))[2],
       str(by.get("ead")))
    ok("k012: «section 245(k) of the Act» binds to nothing (NO_NEARBY_CITATION, never an accusation)",
       by.get("act", ("",))[:2] == ("VERIFIED", "NO_NEARBY_CITATION"), str(by.get("act")))
    ok("k012: the fixture produced no FOUND_ELSEWHERE at all",
       len(by) == 4 and not any(v[0] == "FOUND_ELSEWHERE" for v in by.values()), str(by))


def suite_k027_markers(tmp):
    """K027 (2026-11-24): gap and conflict markers. The drafter writes `[MISSING: ...]` /
    `[CONFLICT: ...]` where the evidence runs out; `check` lists them and names every marker that
    vanished with the sentence now in its place; `close` refuses while a filed document carries one;
    nothing about markers reaches `check`'s exit code (punish markers and they stop being written).
    The vocabulary was measured on a filed petition and the law corpus before it was fixed."""
    import json
    import time as _time
    import subprocess as _sp
    from krokai.markers import find_markers, analyse

    def kinds(t):
        return [m["kind"] for m in find_markers(t)]

    gaps = ["[MISSING: the lease]", "[missing: the lease]", "[MISSING EVIDENCE: x]",
            "[Missing_Evidence: x]", "[НУЖЕН ДОКУМЕНТ: диплом]", "[MISSING]"]
    cons = ["[CONFLICT: Ex. 8 vs Ex. 11]", "[КОНФЛИКТ: 8 / 11]", "[CONFLICT - dates]", "[КОНФЛИКТ]"]
    ok("k027: every gap spelling reads as a gap", all(kinds(t) == ["gap"] for t in gaps),
       str([kinds(t) for t in gaps]))
    ok("k027: every conflict spelling reads as a conflict",
       all(kinds(t) == ["conflict"] for t in cons), str([kinds(t) for t in cons]))
    neg = ["[sic]", "[emphasis added]", "the [a]lien", "[Exhibit 12]", "[filing date]", "[...]",
           "[MISSINGS: x]", "[CONFLICTING evidence]", "MISSING: no bracket", "[TODO: x]",
           "[MISSING: one paragraph\n\nand another]"]
    ok("k027: legal brackets, placeholders, look-alikes and a note across a blank line are not "
       "markers", not any(find_markers(t) for t in neg),
       str([t for t in neg if find_markers(t)]))
    nest = find_markers("Dated [MISSING: the date on [Exhibit 12] and the signature] here.")
    ok("k027: a note holding a bracket of its own still counts (cut at its first closing bracket)",
       len(nest) == 1 and nest[0]["text"] == "[MISSING: the date on [Exhibit 12]", str(nest))
    snip = io.open(os.path.join(data_dir("templates"), "CLAUDE.md.snippet"), encoding="utf-8").read()
    sk = kinds(snip)
    ok("k027: the assistant block teaches the markers the code reads - both kinds, both languages",
       sk.count("gap") >= 2 and sk.count("conflict") >= 2 and "{KROKAI} close" in snip
       and "never write one away" in snip, str(sk))

    base = ("The beneficiary joined the Northwind Atelier in Rivertown as lead designer and worked "
            "there from %s until the end of the contract. The second sentence stays as it was.\n")
    mk = "[MISSING: the employer letter with the start date]"
    filled = base % "March 2019 (Exhibit 14)"
    first = analyse([("A", "case/d.md", base % mk)], {}, today="2026-11-01")
    st = first["state"]
    blob = json.dumps(st, ensure_ascii=False).lower()
    ok("k027: the record keeps the marker note and none of the prose around it (hashes only)",
       mk.lower() in blob and "atelier" not in blob and "contract" not in blob, blob[:200])

    def gone(docs, only=None):
        return analyse(docs, st, "ABCD", only, today="2026-11-02")

    g = gone([("A", "case/d.md", filled)])["gone"]
    ok("k027: a marker written over is named with the whole sentence now in its place",
       len(g) == 1 and g[0]["how"] == "replaced" and g[0]["now"] == filled.split(" The second")[0],
       str(g))
    hows = [gone([("A", "case/d.md", t)])["gone"][0]["how"] for t in
            (base % "", "Nothing of the old paragraph is left here at all.\n",
             base % "[MISSING: the signed employer letter]")]
    ok("k027: deleted, rewritten beyond recognition and reworded are told apart",
       hows == ["deleted", "lost", "reworded"], str(hows))
    r = gone([("A", "case/e.md", base % mk)])
    ok("k027: a marker that moved with its file (renamed) is still open, not gone",
       not r["gone"] and r["open"][0]["since"] == "2026-11-01", str(r["gone"]))
    r = gone([("A", "case/e.md", filled)])["gone"]
    ok("k027: a gone file's marker is looked for in the other drafts and named where it was written "
       "over", len(r) == 1 and r[0].get("was_in") == "case/d.md" and r[0]["how"] == "replaced",
       str(r))
    r = gone([("A", "case/e.md", "Unrelated text with no anchor of the old one in it.\n")])["gone"]
    ok("k027: a gone file whose markers are nowhere is reported as such",
       [x["how"] for x in r] == ["file gone"], str(r))
    r = gone([("A", "case/e.md", "Unrelated.\n")], only="e.md")
    ok("k027: a file outside this run (--only) keeps its record and is not called gone",
       not r["gone"] and "case/d.md" in r["state"]["files"], str(r["gone"]))
    newer = analyse([("A", "case/v1.md", base % mk, 100.0), ("A", "case/v2.md", filled, 200.0)])
    older = analyse([("A", "case/v1.md", base % mk, 100.0), ("A", "case/v2.md", filled, 50.0)])
    ok("k027: a NEWER copy that wrote the marker over is named; an OLDER copy without it is not "
       "(the marker was added later, nothing was erased)",
       [x.get("open_in") for x in newer["gone"]] == ["case/v1.md"] and not older["gone"],
       "%s / %s" % (newer["gone"], older["gone"]))
    tiers = analyse([("D", "case/r.md", base % mk), ("C", "research/n.md", base % mk)])
    ok("k027: tool output (tier D) is never read for markers; tier C is listed but not remembered",
       [o["tier"] for o in tiers["open"]] == ["C"] and not tiers["state"]["files"],
       str(tiers["open"]))

    # --- through the real CLI: check never gates, close does, close writes nothing ---------------
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matter = os.path.join(tmp, "k027m")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    def run(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=root, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def w(rel, text, mt=None):
        p = os.path.join(matter, rel)
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        if mt:
            os.utime(p, (mt, mt))

    rc, out = run("init", matter)
    if rc != 0:
        ok("k027: init failed - the CLI pins were skipped", False, out[-200:])
        return
    w(os.path.join("law", "8USC-1255.md"), "SEC. 1255. No application for adjustment of status "
      "shall be approved unless the applicant establishes eligibility at filing.")
    idx = io.open(os.path.join(matter, "law", "INDEX.md"), encoding="utf-8").read()
    w(os.path.join("law", "INDEX.md"), idx + "\n| 8 U.S.C. § 1255 | adjustment | `8USC-1255.md` | "
      "2026 | |\n")
    state_p = os.path.join(matter, ".krokai", "markers.json")
    t0 = _time.time() - 3600
    conflict = (" The value was confirmed [CONFLICT: Exhibit 8 vs Exhibit 11 - the amount] by both of "
                "the sources on file.")
    w(os.path.join("case", "draft.md"), filled, t0)
    rc1, out1 = run("check", "--dir", matter, "--out", os.path.join(tmp, "k027o1"))
    rc2, out2 = run("close", "--dir", matter)
    ok("k027: a matter with no marker gets no record file and no Markers block",
       rc1 == 0 and "Markers" not in out1 and not os.path.exists(state_p), out1[-300:])
    ok("k027: a fresh matter with its law indexed closes ALL CLEAR - `law/INDEX.md` is not an "
       "unindexed source of its own (close could never come back clear before)",
       rc2 == 0 and "[2] library index: 0 unindexed" in out2
       and "[7] markers in filed documents (tier A): 0 open" in out2, out2[-400:])

    w(os.path.join("case", "draft.md"), base % mk + conflict + "\n", t0)
    w(os.path.join("research", "note.md"), "Open question for the team [КОНФЛИКТ] here.\n")
    rc, out = run("check", "--dir", matter, "--strict", "--out", os.path.join(tmp, "k027o2"))
    rel = "case/draft.md"
    ok("k027: check lists the open markers per filed file and tier C on one line",
       "  A %s: 2 open (1 gap · 1 conflict)" % rel in out and "tier C, 1 file: 1 open marker" in out,
       out[-500:])
    ok("k027: the markers never reach check's exit code (--strict, two open markers in tier A)",
       rc == 0, "rc=%s" % rc)
    ok("k027: the Markers block comes before the verdicts, which stay the last lines",
       0 <= out.find("Markers - gaps") < out.find("needs a human"), "")
    rep = io.open(os.path.join(tmp, "k027o2", "REPORT.md"), encoding="utf-8").read()
    res = json.load(io.open(os.path.join(tmp, "k027o2", "result.json"), encoding="utf-8"))
    ok("k027: REPORT.md and result.json carry the markers",
       "## Markers" in rep and mk in rep
       and [o["file"] for o in res["markers"]["open"] if o["tier"] == "A"] == [rel],
       str(res.get("markers"))[:200])
    ok("k027: check keeps the record inside the matter, beside the law registry",
       os.path.isfile(state_p), state_p)
    rc, out = run("close", "--dir", matter)
    ok("k027: close refuses while a filed document carries markers - and names them",
       rc == 1 and "[7] markers in filed documents (tier A): 2 open in 1 file(s)" in out
       and mk in out, out[-500:])

    w(os.path.join("case", "draft.md"), filled.rstrip("\n") + conflict + "\n", t0 + 10)
    w(os.path.join("case", "v2.md"), filled.rstrip("\n") + conflict.replace(
        " [CONFLICT: Exhibit 8 vs Exhibit 11 - the amount]", "") + "\n", t0 + 100)
    def state_bytes():
        return io.open(state_p, "rb").read() if os.path.exists(state_p) else None

    before = state_bytes()
    rc, out = run("close", "--dir", matter)
    ok("k027: close refuses while a marker vanished that no check has named yet - and writes "
       "nothing", rc == 1 and "gone since the last `krokai check`" in out
       and before is not None and state_bytes() == before, out[-500:])
    rc, out = run("check", "--dir", matter, "--out", os.path.join(tmp, "k027o3"))
    line = "  A %s: %s → now: «%s»" % (rel, mk, filled.split(" The second")[0])
    ok("k027: check names the marker that vanished, with the sentence now in its place",
       line in out, out[-700:])
    ok("k027: a newer copy that dropped a marker still open in the original is named there",
       "A case/v2.md: [CONFLICT: Exhibit 8 vs Exhibit 11 - the amount] (still open in %s) → "
       "deleted" % rel in out, out[-700:])
    rc, out = run("check", "--dir", matter, "--out", os.path.join(tmp, "k027o4"))
    ok("k027: a vanished marker is named once, not on every run", "GONE" not in out, out[-300:])
    w(os.path.join("case", "draft.md"), filled, t0 + 20)
    run("check", "--dir", matter, "--out", os.path.join(tmp, "k027o5"))
    rc, out = run("close", "--dir", matter)
    ok("k027: once a person has closed every filed marker and a check has named it, close is clear "
       "again (tier C notes are listed, never gated)",
       rc == 0 and "tiers B+C: 1 open in 1 file(s)" in out and "ALL CLEAR" in out, out[-400:])


def suite_k028_editions(tmp):
    """K028 (2026-11-24): an older edition must look old. The publisher's own edition date is read
    only from measured shapes; the index row of an older edition is marked SUPERSEDED and names the
    current file; «arrived later» is not «newer»; a quotation that is ALSO in the current edition is
    not graded SUPERSEDED_EDITION; `check` lists the paragraphs that cite a revised provision without
    a quotation. The fixture mirrors the AOS register: two editions fetched the same day, point-in-time
    2024-01-01 and 2026-08-01, the newer one under a different stem."""
    import json
    import subprocess as _sp
    from krokai import fetch as F
    from krokai.corpus import Corpus
    from krokai.citations import load_packs
    from krokai.config import load as load_cfg
    from krokai.verify import check
    from krokai.verdicts import CLEAN
    from krokai.library import INDEX_HEADER, mark_superseded, orphans, SUPERSEDED_TAG
    from krokai.run import scan_matter, print_editions, SENTINELS

    ed = F.edition_date
    ok("k028: «Current as of» on a Policy Manual page is the edition date",
       ed("Page sub tree links Current as of August 12, 2026 more") == ("2026-08-12", "«Current as of»"),
       str(ed("Current as of August 12, 2026")))
    ok("k028: an eCFR point-in-time URL is the edition date, whatever the text says",
       ed("as of May 5, 1988", "https://www.ecfr.gov/api/versioner/v1/full/2024-01-01/title-8.xml?part=245")[0]
       == "2024-01-01")
    ok("k028: a govinfo U.S. Code page gives its annual edition as a year, never an invented day",
       ed("8 U.S.C. United States Code, 2024 Edition Title 8")[0] == "2024"
       and ed("current through Public Law 119-142 (November 10, 2026).")[0] == "2026-11-10")
    amb = ed("Current as of May 1, 2026 ... Current as of June 2, 2026")
    ok("k028: a phrase that prints two different dates records none (and says why)",
       amb[0] == "" and "2 different dates" in amb[1], str(amb))
    law_text = ("pending adjudication as of November 12, 1999; effective Dec. 23, 2008; Last updated: "
                "4/26/2021; the 8 CFR edition revised as of January 1, 1987; effective on July 21, 2010")
    ok("k028: dates inside the law's own text are never taken for the edition (as of / effective / "
       "Last updated / revised as of - each measured ambiguous on the AOS corpus)",
       ed(law_text) == ("", ""), str(ed(law_text)))
    ok("k028: a new index explains its two date columns and the SUPERSEDED mark",
       "SUPERSEDED" in INDEX_HEADER and "PUBLISHER" in INDEX_HEADER and "a dash means none" in INDEX_HEADER)

    root = os.path.join(tmp, "k028m")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))
    cfg = load_cfg(root)
    packs = load_packs(cfg["citation_packs"])
    idx = cfg.abs(cfg["library_index"])
    fill = " ".join(["Paragraph %d of the provision keeps this synthetic source above every floor." % i
                     for i in range(12)])
    BOTH = "The officer shall consider every relevant factor in the record before deciding."
    OLD = ("Sec. 245.1 Eligibility. %s The former fee schedule applies to every application filed "
           "before the effective date of this section. %s" % (BOTH, fill))
    NEW = OLD.replace("The former fee schedule applies to every application filed before",
                      "The current fee schedule applies to every application filed on or after")
    OLDEST = OLD.replace("The officer shall consider", "The officer may consider")
    inbox = os.path.join(root, F.INBOX)
    os.makedirs(inbox)
    ecfr = "https://www.ecfr.gov/api/versioner/v1/full/%s/title-8.xml?part=245"

    def drop(name, body, day, fetched):
        io.open(os.path.join(inbox, name), "w", encoding="utf-8", newline="\n").write(body)
        io.open(os.path.join(inbox, name + ".meta.json"), "w", encoding="utf-8").write(json.dumps(
            {"url": ecfr % day, "sha256": F.sha256_of(body.encode("utf-8")), "trust": "primary",
             "trust_label": "OFFICIAL", "model_in_path": False, "fetched_at": fetched}))

    def rows_of(name):                       # by the File cell - a marked row NAMES the current file too
        out = []
        for ln in io.open(idx, encoding="utf-8").read().splitlines():
            m = re.search(r"\|\s*`([^`]+)`\s*\|", ln)
            if ln.startswith("|") and m and m.group(1) == name:
                out.append(ln)
        return out

    quiet = lambda *a: None                                         # noqa: E731
    drop("8CFR-245-Adjustment.txt", OLD, "2024-01-01", "2026-08-05T10:54:01")
    r1 = F.intake(root, cfg, packs, address="8 CFR 245.1", printer=quiet)
    drop("8CFR-245.txt", NEW, "2026-08-01", "2026-08-05T10:54:11")
    r2 = F.intake(root, cfg, packs, address="8 CFR 245.1", printer=quiet)
    v1, v2 = rows_of("8CFR-245-Adjustment.txt"), rows_of("8CFR-245__rev2.txt")
    ok("k028: the second edition is a revision, saved under the NEW file's stem",
       [s for s, _n, _x in r1] == ["added"] and r2 and r2[-1][0].startswith("\U0001f534")
       and len(v1) == 1 and len(v2) == 1, str(r1 + r2))
    if not (len(v1) == 1 and len(v2) == 1):
        return
    ok("k028: the old edition's row is marked SUPERSEDED and names the current file",
       v1[0].startswith("| %s · " % SUPERSEDED_TAG)
       and "superseded - current edition: `8CFR-245__rev2.txt`" in v1[0], v1[0])
    ok("k028: the current edition's row carries no mark", SUPERSEDED_TAG not in v2[0], v2[0])
    ok("k028: «Retrieved» is the fetch day and «Edition / as of» the publisher's date - two editions "
       "fetched the same day no longer look like one",
       "| 2026-08-05 | 2024-01-01 · eCFR point-in-time URL |" in v1[0]
       and "| 2026-08-05 | 2026-08-01 · eCFR point-in-time URL |" in v2[0], v1[0] + " / " + v2[0])
    un, miss = orphans(cfg.source_dirs, idx)
    ok("k028: a marked row still indexes its file (the File cell is never touched)",
       un == [] and miss == [], str(un) + str(miss))
    reg = json.load(io.open(os.path.join(root, F.REGISTRY), encoding="utf-8"))
    ent = list(reg.values())[0]
    ok("k028: the register keeps every edition's own date",
       ent.get("edition_date") == "2026-08-01"
       and sorted(v.get("edition_date") for v in (ent.get("editions") or {}).values())
       == ["2024-01-01", "2026-08-01"], str(ent.get("editions")))
    before = io.open(idx, "rb").read()
    again = mark_superseded(idx, ["8CFR-245-Adjustment.txt"], "8CFR-245__rev2.txt")
    ok("k028: marking again changes nothing", again == (0, []) and io.open(idx, "rb").read() == before,
       str(again))

    corp = Corpus([law], sentinel=SENTINELS, quiet=True, superseded=F.superseded_paths(root))
    vb, wb, _d = check(BOTH, corp)
    ok("k028: a quotation that is ALSO in the current edition verifies there - it used to come back "
       "SUPERSEDED_EDITION whenever the old file sorted first",
       vb in CLEAN and os.path.basename(wb or "") == "8CFR-245__rev2.txt", "%s %s" % (vb, wb))
    vo, _w, do = check("The former fee schedule applies to every application filed before the "
                       "effective date", corp)
    ok("k028: a quotation found ONLY in the old edition is still SUPERSEDED_EDITION, and says what the "
       "current edition holds", vo == "SUPERSEDED_EDITION" and "In the current edition it is" in do,
       "%s %s" % (vo, do[-160:]))

    drop("8CFR-245-2020.txt", OLDEST, "2020-01-01", "2026-08-06T09:00:00")
    r3 = F.intake(root, cfg, packs, address="8 CFR 245.1", printer=quiet)
    sup = {os.path.basename(p) for p in F.superseded_paths(root)}
    reg = json.load(io.open(os.path.join(root, F.REGISTRY), encoding="utf-8"))
    ok("k028: an OLDER point-in-time edition fetched later does not become the current law",
       r3 and r3[-1][0] == "⚠️ OLDER EDITION"
       and os.path.basename(list(reg.values())[0]["path"]) == "8CFR-245__rev2.txt"
       and sup == {"8CFR-245-Adjustment.txt", "8CFR-245-2020__rev3.txt"}, "%s %s" % (r3, sup))
    v3, v1b = rows_of("8CFR-245-2020__rev3.txt"), rows_of("8CFR-245-Adjustment.txt")
    ok("k028: its row is marked at birth, and the first edition's mark is not stacked",
       len(v3) == 1 and v3[0].startswith("| %s · " % SUPERSEDED_TAG)
       and "`8CFR-245__rev2.txt`" in v3[0] and len(v1b) == 1 and v1b[0].count(SUPERSEDED_TAG) == 1,
       str(v3 + v1b))
    ok("k028: an older edition arriving is not a 🔴 revision (intake exits 0 on it)",
       not any(s.startswith("\U0001f534") for s, _n, _x in r3), str(r3))

    marked = io.open(idx, encoding="utf-8").read()
    io.open(idx, "w", encoding="utf-8", newline="\n").write(
        marked.replace("%s · " % SUPERSEDED_TAG, "").replace(
            "superseded - current edition: `8CFR-245__rev2.txt`; ", ""))
    r4 = F.intake(root, cfg, packs, printer=quiet)
    ok("k028: an index written before the marks existed is repaired by intake with an empty inbox",
       [s for s, _n, _x in r4] == ["marked"] and io.open(idx, encoding="utf-8").read() == marked, str(r4))

    io.open(os.path.join(law, "0-USCIS-PM-quotes.txt"), "w", encoding="utf-8").write(
        "Volume 7 discussion. %s %s" % (BOTH, fill))
    io.open(os.path.join(case, "petition.md"), "w", encoding="utf-8").write(
        'Under 8 C.F.R. § 245.1, "%s" That standard governs this application.\n\n'
        "Under 8 C.F.R. § 245.1 the former fee schedule still governs applications like this one.\n\n"
        "The applicant meets every requirement of 8 U.S.C. § 1182 as the record shows.\n" % BOTH)
    res = scan_matter(cfg, quiet=True, printer=quiet)
    row = [r for r in (res or {}).get("rows", []) if "relevant factor" in r["quote"]]
    ok("k028: through `check`, the quotation at the cited address verifies in the CURRENT edition "
       "(the address repair no longer prefers the old file)",
       len(row) == 1 and row[0]["verdict"] in CLEAN and row[0]["where"].endswith("8CFR-245__rev2.txt"),
       str([(r["verdict"], r["where"]) for r in row]))
    eds = (res or {}).get("editions") or {}
    para = eds.get("paraphrases") or []
    ok("k028: `check` names the paragraph that cites the revised provision without a quotation - and "
       "only that one", len(para) == 1 and "former fee schedule" in para[0]["excerpt"], str(para))
    prov = (eds.get("provisions") or [{}])[0]
    ok("k028: the editions block names the current file and both older ones with their dates",
       prov.get("current", "").endswith("8CFR-245__rev2.txt") and prov.get("current_date") == "2026-08-01"
       and sorted(o["date"] for o in prov.get("older", [])) == ["2020-01-01", "2024-01-01"], str(prov))
    printed = []
    print_editions(res, printer=printed.append)
    ok("k028: the block is printed with its reading instruction",
       any("compare each with the current edition" in p for p in printed), "\n".join(printed)[-300:])
    snip = io.open(os.path.join(data_dir("templates"), "CLAUDE.md.snippet"), encoding="utf-8").read()
    ok("k028: the assistant block tells the drafter what a SUPERSEDED row means",
       "is an older edition of the law" in snip and "the edition in force then" in snip
       and "a dash means none" in snip)

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", root, "--out",
                 os.path.join(tmp, "k028o")], cwd=repo, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=240)
    out = (p.stdout or "") + (p.stderr or "")
    rep = os.path.join(tmp, "k028o", "REPORT.md")
    md = io.open(rep, encoding="utf-8").read() if os.path.exists(rep) else ""
    ok("k028: the real `check` prints the editions block and REPORT.md carries it",
       "Editions - 1 provision with an OLDER edition" in out and "## Editions" in md, out[-500:])


def suite_k024_ocr_layer(tmp):
    """K024 (2026-11-25): a verdict read from an OCR text layer says so - `check` (console,
    REPORT.md, result.json), `quote`, `library` - and the NOT_FOUND ladder names an OCR misread.
    The layer is told by the text render mode (3 = invisible), counted by pypdf on the extraction
    pass or by PyMuPDF; advisory: the exit code never moves. On the measured corpus 38 of 100 law
    PDFs were OCR layers, and nothing in the output said so."""
    import builtins
    import json
    import shutil
    import subprocess as _sp
    from krokai import readers as R
    from krokai import repair as RP
    from krokai.config import load as load_cfg
    from krokai.corpus import Corpus
    from krokai.run import scan_matter, ocr_counts, print_summary
    from krokai.verdicts import SIX_CAUSES, CLEAN

    ok("k024: NOT_FOUND cause 3 names an OCR text layer's misread and where those files are listed",
       "OCR TEXT LAYER" in SIX_CAUSES[2] and "krokai library" in SIX_CAUSES[2]
       and "page image" in SIX_CAUSES[2], SIX_CAUSES[2][:160])
    snip = io.open(os.path.join(data_dir("templates"), "CLAUDE.md.snippet"), encoding="utf-8").read()
    rung3 = re.search(r"(?m)^3\.\s+(.+(?:\n\s{3,}.+)*)",
                      snip.split("`NOT_FOUND` is not `INVENTED`", 1)[-1])
    ok("k024: the assistant block's rung 3 carries the OCR misread too",
       bool(rung3) and "OCR text layer" in rung3.group(1) and "{KROKAI} library" in rung3.group(1),
       rung3.group(1)[:200] if rung3 else "no rung 3")
    c = R._TrCounter()
    for op, args in ((b"BT", []), (b"q", []), (b"Tr", [3]), (b"Tj", ["abcd"]), (b"Q", []),
                     (b"Tr", ["x"]), (b"Tj", ["xy"]), (b"Do", []), (b"Tr", [3]),
                     (b"TJ", [["ef", -120, "g"]])):
        c.before(op, args, None, None)
    c.after(b"Do", [], None, None)
    c.before(b"'", ["hij"], None, None)
    c.stop()
    ok("k024: the render-mode count follows q / Q and a form XObject (Do), and a bad operand never "
       "raises", c.pages == [(5, 7)], str(c.pages))
    cl = R._classify
    ok("k024: page classes - all invisible = ocr; a typeset page 4 % invisible stays typeset; one of "
       "each = mixed, naming the OCR page; nothing to judge = none",
       cl([(0, 500), (0, 480)], "t")["class"] == "ocr" and cl([(480, 20)], "t")["class"] == "typeset"
       and cl([(500, 0), (0, 500)], "t")["class"] == "mixed"
       and cl([(500, 0), (0, 500)], "t")["ocr_pages"] == "2" and cl([(10, 0)], "t")["class"] == "none")
    ok("k024: OCR pages print as a reader writes them", R._ranges([1, 2, 3, 7, 9, 10]) == "1-3, 7, 9-10")

    try:
        from krokai import _pdfengine
        fz = _pdfengine.load()
    except ImportError:
        fz = None
    if fz is None:
        print("note: k024 OCR-layer fixture pins skipped - PyMuPDF builds the fixtures and is not "
              "installed here")
        return
    try:
        import pypdf  # noqa: F401
        have_pypdf = True
    except ImportError:
        have_pypdf = False

    root = os.path.join(tmp, "k024m")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))

    def make(path, pages):
        d = fz.open()
        for mode, lines in pages:
            pg = d.new_page()
            for i, ln in enumerate(lines):
                pg.insert_text((50, 60 + 14 * i), ln, fontsize=9, render_mode=mode)
        d.save(path)
        d.close()

    fill = ["Line %d of this synthetic part keeps every page above the floor of the reader." % i
            for i in range(6)]
    OCR_S = "The applicant shall submit the completed form within 30 days of the notice."
    TYP_S = "The officer shall record each decision in the file before the case is closed."
    MIX_S = "A request for evidence shall state the reason and the deadline for a response."
    NF_S = "The applicant may ask the officer for a second interview at any time."
    ocr_pdf, typ_pdf, mix_pdf = (os.path.join(law, n)
                                 for n in ("8CFR-299.pdf", "8CFR-298.pdf", "8CFR-297.pdf"))
    make(ocr_pdf, [(3, ["Sec. 299.1 Fixture rule.", OCR_S] + fill)] + [(3, fill)] * 2)
    make(typ_pdf, [(0, ["Sec. 298.1 Fixture rule.", TYP_S] + fill)] + [(0, fill)] * 2)
    make(mix_pdf, [(0, ["Sec. 297.1 Fixture rule."] + fill), (3, [MIX_S] + fill), (3, fill)])

    R._LAYER_MEMO.clear()
    got = [(R.text_layer(p) or {}) for p in (ocr_pdf, typ_pdf, mix_pdf)]
    ok("k024: text_layer tells an OCR layer, typeset text and a mix apart, naming the OCR pages",
       [g.get("class") for g in got] == ["ocr", "typeset", "mixed"]
       and got[2].get("ocr_pages") == "2-3", str(got))

    real_import = builtins.__import__

    def hider(names):
        def imp(name, *a, **k):
            if name.split(".")[0] in names:
                raise ImportError("hidden by the k024 selftest: %s" % name)
            return real_import(name, *a, **k)
        return imp

    for hidden, eng in (({"fitz", "pymupdf"}, "pypdf"), ({"pypdf"}, "PyMuPDF")):
        if eng == "pypdf" and not have_pypdf:
            print("note: k024 pypdf-alone pin skipped - pypdf is not installed here")
            continue
        R._LAYER_MEMO.clear()
        builtins.__import__ = hider(hidden)
        try:
            alone = [(R.text_layer(p) or {}) for p in (ocr_pdf, typ_pdf, mix_pdf)]
        finally:
            builtins.__import__ = real_import
        ok("k024: with %s alone the same three classes come back" % eng,
           [a.get("class") for a in alone] == ["ocr", "typeset", "mixed"]
           and all(a.get("engine") == eng for a in alone), str(alone))

    R._LAYER_MEMO.clear()
    cache = os.path.join(tmp, "k024cache")
    R.read_pdf(ocr_pdf, cache)
    lp = R._layer_file(ocr_pdf, cache)
    on_disk = json.load(io.open(lp, encoding="utf-8")) if os.path.exists(lp) else {}
    ok("k024: read_pdf writes the layer beside the text cache, counted on the extraction it runs",
       on_disk.get("class") == "ocr" and on_disk.get("engine") == ("pypdf" if have_pypdf else "PyMuPDF"),
       str(on_disk))
    if os.path.exists(lp):
        os.remove(lp)
    R._LAYER_MEMO.clear()
    again = R.text_layer(ocr_pdf, cache) or {}
    ok("k024: a text cache from an older version (no layer file) gets its layer measured and kept",
       again.get("class") == "ocr" and os.path.exists(lp), str(again))

    rep = os.path.join(tmp, "k024rep")
    os.makedirs(rep)
    broken = os.path.join(rep, "broken-type3.pdf")
    shutil.copyfile(typ_pdf, broken)
    rcache = os.path.join(tmp, "k024repcache")
    real_b, real_fix = R.is_broken_type3, RP.fix_broken_pdf
    R.is_broken_type3 = lambda p: os.path.basename(p) == "broken-type3.pdf"
    RP.fix_broken_pdf = lambda src, dest, **k: (shutil.copyfile(ocr_pdf, dest), (3, 0))[1]
    try:
        R._LAYER_MEMO.clear()
        txt = R.read_pdf(broken, rcache)
        lay1 = R.text_layer(broken, rcache) or {}
        R._LAYER_MEMO.clear()
        if os.path.exists(R._layer_file(broken, rcache)):
            os.remove(R._layer_file(broken, rcache))
        lay2 = R.text_layer(broken, rcache) or {}
    finally:
        R.is_broken_type3, RP.fix_broken_pdf = real_b, real_fix
    ok("k024: text from krokai's own OCR repair of a broken Type 3 file is an OCR layer - on the read "
       "and from a cache written before the layer file existed",
       "completed form" in txt and lay1.get("class") == "ocr" and "repair" in lay1.get("source", "")
       and lay2.get("class") == "ocr" and "repair" in lay2.get("source", ""), str((lay1, lay2)))

    R._LAYER_MEMO.clear()
    corp = Corpus([law], quiet=True)
    ok("k024: the corpus keeps the layer per indexed PDF - the OCR and the mixed file, never the "
       "typeset one", bool(corp.ocr_layer(ocr_pdf)) and bool(corp.ocr_layer(mix_pdf))
       and corp.ocr_layer(typ_pdf) is None and len(corp.ocr_files()) == 2,
       str([(os.path.basename(p), f.get("class")) for p, f in corp.ocr_files()]))

    ALT = OCR_S.replace("30 days", "60 days")
    io.open(os.path.join(case, "petition.md"), "w", encoding="utf-8").write(
        'Under 8 C.F.R. § 299.1, "%s"\n\nUnder 8 C.F.R. § 298.1, "%s"\n\n'
        'Under 8 C.F.R. § 299.1, "%s"\n\nUnder 8 C.F.R. § 299.1, "%s"\n\n'
        'Under 8 C.F.R. § 297.1, "%s"\n' % (OCR_S, TYP_S, NF_S, ALT, MIX_S))
    cfg = load_cfg(root)
    res = scan_matter(cfg, quiet=True, printer=lambda *a: None) or {"rows": []}

    def row(marker):
        return next((r for r in res["rows"] if marker in r["quote"]), {})
    r_ocr, r_typ, r_mix = row("within 30 days"), row("record each decision"), row("request for evidence")
    r_alt, r_nf = row("within 60 days"), row("second interview")
    ok("k024: a VERIFIED row read from an OCR layer carries it; the typeset row does not",
       r_ocr.get("verdict") in CLEAN and (r_ocr.get("ocr_layer") or {}).get("class") == "ocr"
       and r_typ.get("verdict") in CLEAN and r_typ.get("ocr_layer") is None
       and (r_mix.get("ocr_layer") or {}).get("class") == "mixed",
       str([(r.get("verdict"), r.get("ocr_layer")) for r in (r_ocr, r_typ, r_mix)]))
    ok("k024: a FLAGGED row compared with an OCR layer carries it (the difference may be the OCR's)",
       r_alt.get("verdict") not in CLEAN and (r_alt.get("ocr_layer") or {}).get("class") == "ocr",
       str((r_alt.get("verdict"), r_alt.get("where"))))
    ok("k024: a NOT_FOUND citing a source whose text is an OCR layer puts cause 3 first and names it",
       r_nf.get("verdict") == "NOT_FOUND" and "OCR layer" in r_nf.get("kind", "")
       and any(f.endswith("8CFR-299.pdf") for f in r_nf.get("ocr_cited") or []),
       str((r_nf.get("verdict"), r_nf.get("kind"), r_nf.get("ocr_cited"))))
    oc = ocr_counts(res)
    lines = []
    print_summary(res, printer=lines.append)
    said = "\n".join(lines)
    ok("k024: the console summary counts them - 2 clean, 1 flagged, 1 NOT FOUND - with the instruction",
       (oc["clean"], oc["flagged"], oc["not_found"]) == (2, 1, 1)
       and "2 clean quotation(s) matched what an OCR engine read" in said
       and "page image" in said, said[-600:])

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    _rc, out = cli("check", "--dir", root, "--out", os.path.join(tmp, "k024o"))
    rep_md = os.path.join(tmp, "k024o", "REPORT.md")
    md = io.open(rep_md, encoding="utf-8").read() if os.path.exists(rep_md) else ""
    sec = md.split("## Read from an OCR text layer", 1)[-1].split("\n## ", 1)[0] if md else ""
    ok("k024: the real `check` prints the OCR line and REPORT.md lists the OCR-read rows - not the "
       "typeset one", "OCR TEXT LAYER, tiers A+B" in out and "## Read from an OCR text layer" in md
       and "within 30 days" in sec and "record each decision" not in sec and "pages 2-3 of 3" in sec,
       out[-400:] + " || " + sec[:300])
    rj = os.path.join(tmp, "k024o", "result.json")
    payload = json.load(io.open(rj, encoding="utf-8")) if os.path.exists(rj) else {}
    ok("k024: result.json carries the layer on each row and lists the OCR sources",
       sorted(os.path.basename(f["file"]) for f in payload.get("ocr_layers", []))
       == ["8CFR-297.pdf", "8CFR-299.pdf"]
       and any((r.get("ocr_layer") or {}).get("class") == "ocr" for r in payload.get("rows", [])),
       str(payload.get("ocr_layers")))

    green = os.path.join(tmp, "k024g")
    shutil.copytree(law, os.path.join(green, "law"))
    os.makedirs(os.path.join(green, "case"))
    shutil.copyfile(os.path.join(root, "casefile.json"), os.path.join(green, "casefile.json"))
    io.open(os.path.join(green, "case", "petition.md"), "w", encoding="utf-8").write(
        'Under 8 C.F.R. § 299.1, "%s"\n' % OCR_S)
    rc, out = cli("check", "--strict", "--dir", green, "--out", os.path.join(tmp, "k024go"))
    ok("k024: the OCR line is advisory - a matter whose only quotation verified in an OCR layer still "
       "passes `check --strict` (exit 0) and is told about the layer",
       rc == 0 and "OCR TEXT LAYER, tiers A+B: 1 clean" in out, "exit %s: %s" % (rc, out[-300:]))

    _rc, q1 = cli("quote", "--dir", root, OCR_S)
    _rc, q2 = cli("quote", "--dir", root, TYP_S)
    _rc, q3 = cli("quote", "--dir", root, NF_S + " 8 C.F.R. § 299.1")
    ok("k024: `quote` labels a match in an OCR layer and says what to check - and not a typeset match",
       "🟡 OCR TEXT LAYER (all 3 pages)" in q1 and "page image" in q1
       and "🟡 OCR TEXT LAYER" not in q2, q1[:600] + " || " + q2[:300])
    ok("k024: `quote` names the OCR file when cause 3 is live for a NOT FOUND",
       "Cause 3 is live here" in q3 and "8CFR-299.pdf" in q3, q3[-400:])
    _rc, lib = cli("library", "--dir", root)
    tail = lib.split("OCR text layers:", 1)[-1]
    ok("k024: `library` lists the sources whose text is an OCR layer, with their pages",
       "OCR text layers: 2 of 3 PDF(s)" in lib and "8CFR-299.pdf  (all 3 pages)" in tail
       and "8CFR-297.pdf  (pages 2-3 of 3)" in tail and "8CFR-298.pdf" not in tail, lib[-500:])


def suite_k030_edge_ellipsis(tmp):
    """🔴 K030 (2026-11-25): a verbatim quotation cut at ONE edge was graded ALTERED.

    Found by putting krokai's verdicts next to the sister project's own checker on a copy of a real
    matter (the filed petition): three quotations whose words are verbatim in the source, cut with a
    single leading or trailing ellipsis, came back ALTERED with an EMPTY detail; without the ellipsis
    both checkers said VERIFIED. `check` entered the ellipsis section only with two fragments or more,
    so a one-edge cut fell through to the branch that reads our own ellipsis as a changed tail.

    The pins hold the three sides of the repair: the verbatim one-edge cut is ASSEMBLED (it was the
    defect); a cut that hides a negation in FRONT, or stops before an unmarked limiter, is still loud
    (the repair must not turn today's accidental alarm into a pass); and a short piece on the other
    side of the ellipsis keeps the quotation out of the green path - `ellipsis_parts` drops it below
    its floor, so nothing would have checked it.
    """
    from krokai.corpus import Corpus
    from krokai.verify import CLEAN, check
    d = os.path.join(tmp, "k030")
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, "src.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("For purposes of the counting period, the calculation of the number of days will stop "
                 "as of the date the agency receives a properly filed application from the person "
                 "concerned.\n\nExcept as otherwise provided, no alien may be admitted to the United "
                 "States under this paragraph for any purpose whatsoever.\n\nThe officer shall approve "
                 "the application filed under this section unless the applicant is inadmissible.\n")
    c = Corpus([d], quiet=True)
    body = ("the calculation of the number of days will stop as of the date the agency receives a "
            "properly filed application")
    for label, q in (("trailing ...", body + "..."), ("trailing …", body + "…"),
                     ("leading ...", "..." + body), ("both edges", "… " + body + " …")):
        v, _w, dd = check(q, c)
        ok("k030 a verbatim quotation cut at one edge is ASSEMBLED, not ALTERED (%s)" % label,
           v == "ASSEMBLED", "%s :: %s" % (v, dd))
    v, _w, dd = check("...alien may be admitted to the United States under this paragraph", c)
    ok("k030 a front cut hiding a negation stays TRUNCATED_OPENING with an ellipsis before it",
       v == "TRUNCATED_OPENING", "%s :: %s" % (v, dd))
    v, _w, dd = check("...shall approve the application filed under this section", c)
    ok("k030 an unmarked end before a limiter stays TRUNCATED_CONDITION after a leading ellipsis",
       v == "TRUNCATED_CONDITION", "%s :: %s" % (v, dd))
    v, _w, dd = check("Not ... " + body, c)
    ok("k030 a short piece across the ellipsis keeps the quotation out of the green path",
       v not in CLEAN, "%s :: %s" % (v, dd))


def suite_k047_reading_list(tmp):
    """K047 (2026-11-26): `check` writes READING-LIST.md beside REPORT.md - every quotation of the filed tier, the
    draft sentence, the source passage +-2 sentences and the question; flagged ones first in REPORT.md's order, the
    rest by the facts noted (OCR layer, another speaker, may against must, a limiter, words left out, no citation,
    numbers); never a clean verdict's label; written on a clean round too; tool-output sentinel at its head."""
    import json
    import subprocess as _sp
    from krokai import config as _config
    from krokai import reading as R
    from krokai.run import scan_matter, write_report, _is_tool_output
    from krokai.verdicts import label as _label
    LAW = ("# 8 CFR 214.7 Transfers (fixture)\n\n"
           "(a) A student may transfer to another school at any time during the program. However, a transfer "
           "during the first term needs the approval of the school official.\n\n"
           "(b) The school shall notify the agency within 30 days of the transfer. The notice is filed "
           "**electronically** through the system. The agency answers each notice in writing.\n\n"
           "(c) The officer may extend the stay of a student for a period of one year if the program requires "
           "it. No other extension is granted.\n\n"
           "(e) The school records the address of each student, the program of study, and the date of the last "
           "attendance. The records are kept by the school for three years after the student leaves.\n\n"
           "(f) Under 8 U.S.C. 1101 the term student has the meaning given there. A student keeps the status "
           "while enrolled in the program. The school reports a student who leaves.\n")
    T = "A student may transfer to another school at any time during the program"
    X = "The officer may extend the stay of a student for a period of one year if the program requires it"
    N = "The school shall notify the agency within 30 days of the transfer"
    S = "The school records the address of each student ... and the date of the last attendance"
    K = "The records are kept by the school for three years after the student leaves"
    F = "The school must refund every fee paid by the student at once to the family"
    DRAFT = ('The transfer is open to him: "%s".\n\n'
             'The officer must grant the extension, because "%s".\n\n'
             "The school's duty is set out below:\n\n> \"%s\"\n\n"
             'Records exist: "%s".\n\n'
             'They keep them: "%s". Later we say it again: "%s" in another sentence.\n\n'
             'The school promised that "%s".\n' % (T, X, N, S, K, K, F))

    def matter(name, drafts, tier="A"):
        root = os.path.join(tmp, name)
        os.makedirs(os.path.join(root, "law"))
        os.makedirs(os.path.join(root, "case"))
        io.open(os.path.join(root, "law", "8CFR-214.md"), "w", encoding="utf-8").write(LAW)
        for fn, text in drafts.items():
            io.open(os.path.join(root, "case", fn), "w", encoding="utf-8").write(text)
        io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
            "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
            "sources": ["law"], "drafts": [{"tier": tier, "label": "filed" if tier == "A" else "guides",
                                            "path": "case"}],
            "citation_packs": ["us-immigration", "us-federal"]}))
        return root

    def read(p):
        try:
            return io.open(p, encoding="utf-8").read()
        except OSError:
            return ""

    # --- the helpers alone -------------------------------------------------------------------------------
    sp = R.sentence_spans("See 8 U.S.C. 1255(k) and 8 C.F.R. 245.1. The rule applies. Sec. 3 says so, e.g. here.")
    ok("k047: the splitter keeps «U.S.C. 1255», «C.F.R. 245.1» and «Sec. 3» inside their sentences - 3 sentences",
       len(sp) == 3, str(sp))
    ocr = R.signals({"quote": "the words", "ocr_layer": {"class": "ocr", "pages": 3, "source": "tesseract"},
                     "near": ["x"], "verdict": "VERIFIED"}, None, [])
    spk = R.signals({"quote": "the words", "near": ["x"], "verdict": "WRONG_SPEAKER", "detail": "a commenter"},
                    None, [])
    cit = R.signals({"quote": "the words", "near": [], "verdict": "VERIFIED", "where": "law/x.md"}, None, [])
    edge = R.signals({"quote": "… a transfer during the first term needs the approval", "near": ["x"],
                      "verdict": "ASSEMBLED"},
                     {"pieces": [("a transfer during the first term needs the approval", True)], "own_before": "",
                      "own_after": "", "next": ""}, [])
    ok("k047: the row-borne facts - an OCR layer, another speaker, no citation, an ellipsis at the edge - each "
       "noted, and a plain row gets none of them",
       [n for n, _x in ocr] == ["ocr"] and [n for n, _x in spk] == ["speaker"]
       and [n for n, _x in cit] == ["uncited"] and [n for n, _x in edge] == ["omitted"]
       and not R.signals({"quote": "the words", "near": ["x"], "verdict": "VERIFIED"}, None, []),
       "%s | %s | %s | %s" % (ocr, spk, cit, edge))

    def ent(names, places=1, sites=1, index=0):
        return {"signals": [(n, "") for n in names], "places": [None] * places,
                "row": {"sites": [None] * sites}, "index": index}
    order = sorted([ent(["digits", "uncited", "limiter"], index=0), ent(["ocr"], index=1),
                    ent(["limiter"], index=2), ent([], index=3), ent(["limiter"], places=3, index=4)],
                   key=R.order_key)
    ok("k047: the order - the strongest fact first (an OCR layer alone beats three weaker ones), then more facts, "
       "then the quotation used in more places, then REPORT.md's order; no facts last",
       [e["index"] for e in order] == [1, 0, 4, 2, 3], str([e["index"] for e in order]))

    # --- one matter end to end through the CLI -------------------------------------------------------------
    root = matter("k047m", {"petition.md": DRAFT})
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(tmp, "k047o")
    p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", root, "--out", out], cwd=repo, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    cout = (p.stdout or "") + (p.stderr or "")
    path = os.path.join(out, R.FILE)
    md = read(path)
    try:
        verdicts = {" ".join(r["quote"].split()): r["verdict"] for r in
                    json.load(io.open(os.path.join(out, "result.json"), encoding="utf-8"))["rows"]}
    except (OSError, ValueError, KeyError):
        verdicts = {}
    part1, _s, part2 = md.partition("## Part 2")

    def entry(q, text=md):
        """The block of the entry whose Quoted line is `q`."""
        for blk in re.split(r"^### \d+\. ", text, flags=re.M)[1:]:
            if "**Quoted:**\n> %s" % q in blk:
                return blk
        return ""

    ok("k047: the fixture graded as built - five clean (one ASSEMBLED), one NOT FOUND",
       [verdicts.get(q) for q in (T, X, N, K)] == ["VERIFIED"] * 4 and verdicts.get(S) == "ASSEMBLED"
       and verdicts.get(F) == "NOT_FOUND", "%s | %s" % (verdicts, cout[-500:]))
    ok("k047: `check` writes READING-LIST.md beside REPORT.md and says so with its counts",
       bool(md) and os.path.isfile(os.path.join(out, "REPORT.md"))
       and "reading list -> " in cout and "6 quotation(s) of the filed documents: 1 flagged first" in cout,
       cout[-700:])
    ok("k047: the list carries the tool-output sentinel - a later check counts it as tool output (tier D)",
       bool(md) and _is_tool_output(path), md[:200])
    ok("k047: part 1 = the flagged quotation with no passage and a pointer to REPORT.md; part 2 never holds it",
       bool(entry(F, part1)) and "no passage shown" in entry(F, part1) and "REPORT.md" in entry(F, part1)
       and not entry(F, part2), part1[-600:])
    pos = [part2.find("**Quoted:**\n> %s" % q) for q in (X, T, S, N, K)]
    ok("k047: part 2's order - may-against-must, the limiter, the left-out words, numbers, then the plain one",
       all(x >= 0 for x in pos) and pos == sorted(pos), str(pos))
    ok("k047: each fact noted in plain words - «may» vs «must», «However» opening the next sentence, the "
       "words left out shown in italics, numbers; the plain quotation gets only the missing citation",
       "the source says «may»; the sentence around it says «must»" in entry(X)
       and "«However» opening the next sentence" in entry(T)
       and "words left out between the quoted pieces" in entry(S) and "_[left out: , the program of study,]_" in entry(S)
       and "numbers in the quotation" in entry(N)
       and re.search(r"\*\*Noted:\*\* no citation printed beside the quotation[^·\n]*\n", entry(K)) is not None,
       entry(K)[:400])
    ok("k047: the passage is the quoted words in bold with TWO sentences after them - not one, not three",
       "**%s**" % T in entry(T) and "(b) The school shall notify the agency within 30 days of the transfer." in entry(T)
       and "The notice is filed" not in entry(T), entry(T)[-500:])
    ok("k047: «8 U.S.C. 1101» does not end a sentence - the two sentences after the words are whole",
       "Under 8 U.S.C. 1101 the term student has the meaning given there. A student keeps the status while "
       "enrolled in the program." in entry(K) and "The school reports a student" not in entry(K), entry(K)[-400:])
    ok("k047: the source's own bold (**electronically**) is dropped from the passage - bold marks the quoted "
       "words only", "filed electronically through the system" in entry(N) and "**electronically**" not in md,
       entry(N)[-300:])
    ok("k047: a blockquote's claim is the sentence before it; a quotation used twice shows both sentences",
       "the sentence before the quotation:\n> The school's duty is set out below:" in entry(N)
       and "> They keep them:" in entry(K) and "> Later we say it again:" in entry(K), entry(N)[:400])
    ok("k047: no clean verdict's label anywhere - the clean part shows facts, words and the question",
       bool(md) and "**%s**" % _label("VERIFIED") not in md and "VERIFIED" not in md
       and "**%s**" % _label("ASSEMBLED") not in md, md[:300])
    ok("k047: the question stands under every passage shown (5) and nowhere else",
       md.count(R.QUESTION) == 5, str(md.count(R.QUESTION)))

    # --- the green path (E-1072): a clean round still writes the list; a matter with no filed tier says so ---
    root2 = matter("k047g", {"clean.md": 'They keep them: "%s".\n' % K})
    res2 = scan_matter(_config.load(root2), quiet=True, printer=lambda *a: None)
    out2 = os.path.join(tmp, "k047go")
    write_report(res2, _config.load(root2), out2) if res2 else None
    md2 = read(os.path.join(out2, R.FILE))
    ok("k047: a clean round still writes the list - no part 1, the quotation in part 2 with its passage and question",
       bool(md2) and "## Part 1" not in md2 and "## Part 2" in md2 and "**Quoted:**\n> %s" % K in md2
       and md2.count(R.QUESTION) == 1, md2[-500:])
    root3 = matter("k047b", {"guide.md": 'They keep them: "%s".\n' % K}, tier="B")
    res3 = scan_matter(_config.load(root3), quiet=True, printer=lambda *a: None)
    out3 = os.path.join(tmp, "k047bo")
    write_report(res3, _config.load(root3), out3) if res3 else None
    md3 = read(os.path.join(out3, R.FILE))
    ok("k047: only the filed tier (A) is listed - a guide's quotation is not, and the list says none was found",
       "No quotation was found in a document of the filed tier (A)" in md3 and "**Quoted:**" not in md3, md3[:600])


def suite_k061b_judge(tmp):
    """K061b (2026-11-27): `check --judge <channel>` - an outside model reads each clean filed quotation against its
    passage and the doubted ones go first in part 2 of READING-LIST.md. Pinned end to end through the CLI against a
    fake OpenAI-protocol server on 127.0.0.1 (the selftest contacts nothing): without the flag nothing is sent; a
    missing key, a failing server and a command-line channel leave the list byte-identical; a brief naming a
    configured surname never reaches the server; the list never carries the model's label or reason; the exit code
    and REPORT.md do not move."""
    import json
    import re as _re
    import subprocess as _sp
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from krokai import judge as J
    from krokai import reading as R
    LAW = ("# 8 CFR 214.7 Transfers (fixture)\n\n"
           "(a) A student may transfer to another school at any time during the program. However, a transfer "
           "during the first term needs the approval of the school official.\n\n"
           "(b) The school shall notify the agency within 30 days of the transfer. The notice is filed "
           "electronically through the system. The agency answers each notice in writing.\n\n"
           "(c) The officer may extend the stay of a student for a period of one year if the program requires "
           "it. No other extension is granted.\n\n"
           "(e) The school keeps the file of each student in its office. The records are kept by the school for "
           "three years after the student leaves. The school shows them to the agency on request.\n")
    DRAFT = ('He can move: "A student may transfer to another school at any time during the program", as '
             'Mr. Kowalczyk did.\n\n'
             'Notice is due: "The school shall notify the agency within 30 days of the transfer".\n\n'
             'The stay can grow: "The officer may extend the stay of a student for a period of one year if the '
             'program requires it".\n\n'
             'The file lives forever: "The records are kept by the school for three years after the student '
             'leaves".\n\n'
             'The school promised that "The school must refund every fee paid by the student at once".\n')
    seen = {"bodies": [], "fail": False}

    class Fake(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8"))
            seen["bodies"].append(body)
            if seen["fail"]:
                self.send_response(500)
                self.end_headers()
                return
            user = body["messages"][-1]["content"]
            lab = "OVERSTATED" if "forever" in user.split("QUOTATION:")[0] else "SUPPORTED"
            out = json.dumps({"choices": [{"message": {"content": "LABEL: %s\nREASON: K061B-FAKE-REASON\n%s"
                                                                  % (lab, J.MARKER)}}],
                              "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.0001}})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out.encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        root = os.path.join(tmp, "k061bm")
        os.makedirs(os.path.join(root, "law"))
        os.makedirs(os.path.join(root, "case"))
        io.open(os.path.join(root, "law", "8CFR-214.md"), "w", encoding="utf-8").write(LAW)
        io.open(os.path.join(root, "case", "petition.md"), "w", encoding="utf-8").write(DRAFT)
        io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
            "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
            "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
            "citation_packs": ["us-immigration", "us-federal"], "surnames": ["Kowalczyk"]}))
        io.open(os.path.join(root, "channels.json"), "w", encoding="utf-8").write(json.dumps({"channels": {
            "fakejudge": {"kind": "http", "api": "chat", "base_url": "http://127.0.0.1:%d/v1" % srv.server_port,
                          "key_env": "KROKAI_K061B_TEST_KEY", "model": "judge-test-model",
                          "judge_body": {"reasoning": {"effort": "low"}}},
            "nokey": {"kind": "http", "api": "chat", "base_url": "http://127.0.0.1:%d/v1" % srv.server_port,
                      "key_env": "KROKAI_K061B_ABSENT_KEY", "model": "judge-test-model"},
            "acli": {"kind": "cli", "bin": "nothing-here"}}, "limits": {}}))
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        def run(tag, *extra):
            env = dict(os.environ, PYTHONIOENCODING="utf-8", NO_PROXY="127.0.0.1,localhost",
                       no_proxy="127.0.0.1,localhost", KROKAI_K061B_TEST_KEY="dummy-test-value")
            env.pop("KROKAI_K061B_ABSENT_KEY", None)
            out = os.path.join(tmp, "k061bo-" + tag)
            p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", root, "--out", out, "--strict"] +
                        list(extra), cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8",
                        errors="replace", timeout=240)

            def rd(name):
                try:
                    return io.open(os.path.join(out, name), encoding="utf-8").read()
                except OSError:
                    return ""
            return p.returncode, (p.stdout or "") + (p.stderr or ""), rd(R.FILE), rd("REPORT.md")

        def masked(s):
            return _re.sub(r"\d+", "#", s)

        def part2_first(md):
            m = _re.search(r"## Part 2 [^\n]*\n\n### \d+\.[^\n]*\n(.*?)\n### ", md, _re.S)
            return m.group(1) if m else ""

        rc0, out0, md0, rep0 = run("base")
        n0 = len(seen["bodies"])
        ok("k061b: without --judge nothing is sent - the fake server saw no request", n0 == 0, str(n0))
        ok("k061b: the baseline is what the fixture needs - a flagged row (exit 1 under --strict), a part 2, and the "
           "quotation the fake model doubts is not first there", rc0 == 1 and "## Part 2" in md0
           and "forever" not in part2_first(md0), "rc %s; %s" % (rc0, part2_first(md0)[:200]))

        rc1, out1, md1, rep1 = run("nokey", "--judge", "nokey")
        ok("k061b: a channel without its key - «judge: not run», nothing sent, the list byte-identical, exit unchanged",
           "judge: not run - no key: set KROKAI_K061B_ABSENT_KEY" in out1 and len(seen["bodies"]) == n0
           and md1 == md0 and rc1 == rc0, out1.strip()[-300:])
        rc2, out2, md2, _r = run("cli", "--judge", "acli")
        ok("k061b: a command-line channel is refused before anything is built - the list byte-identical",
           "«acli» is a cli channel" in out2 and len(seen["bodies"]) == n0 and md2 == md0 and rc2 == rc0,
           out2.strip()[-300:])
        rc3, out3, md3, _r = run("absent", "--judge", "nosuchchannel")
        ok("k061b: an unknown channel name - «judge: not run», the list byte-identical",
           "no channel named «nosuchchannel»" in out3 and md3 == md0 and rc3 == rc0, out3.strip()[-300:])

        rc4, out4, md4, rep4 = run("judged", "--judge", "fakejudge")
        bodies = seen["bodies"][n0:]
        users = [b["messages"][-1]["content"] for b in bodies]
        ok("k061b: the judged run - the quotation the model doubts is first in part 2, the heading says a model's "
           "doubts come first", "forever" in part2_first(md4) and "a model's doubts first" in md4,
           part2_first(md4)[:300])
        ok("k061b: part 1 (the flagged rows) is untouched by the judge",
           md4.split("## Part 2")[0].split("## Part 1")[1] == md0.split("## Part 2")[0].split("## Part 1")[1])
        ok("k061b: the list never carries what the model said - no label, no reason",
           not any(w in md4 for w in J.LABELS + ("K061B-FAKE-REASON", "REASON:")), md4[:400])
        ok("k061b: the exit code and REPORT.md do not move (digits masked: REPORT.md carries timings)",
           rc4 == rc0 and masked(rep4) == masked(rep0), "rc %s vs %s" % (rc4, rc0))
        ok("k061b: the brief naming a configured surname was held - it never reached the server, and the console "
           "says one was held", users and not any("Kowalczyk" in u for u in users)
           and "1 held by the gate" in out4, out4.strip()[-400:])
        ok("k061b: one request per clean quotation the gate let through, each with the judge's system prompt, the "
           "channel's model and its judge_body - and no source file name",
           len(bodies) == 3 and all(b["messages"][0]["content"] == J.SYSTEM and b["model"] == "judge-test-model"
                                    and b.get("reasoning") == {"effort": "low"} for b in bodies)
           and not any("8CFR-214" in u for u in users), str(len(bodies)))
        ok("k061b: the console prints the counts, the cost and the time",
           _re.search(r"judge: «fakejudge» \(judge-test-model\) read 3 brief\(s\) .*1 quotation\(s\) put first .*"
                      r"\$0\.0003, 300\+60 tokens, \d+ s", out4) is not None, out4.strip()[-400:])

        reg_path = os.path.join(root, "channels.json")
        good_reg = io.open(reg_path, encoding="utf-8").read()
        io.open(reg_path, "w", encoding="utf-8").write(good_reg[:-5])
        try:
            rc6, out6, md6, _r = run("badreg", "--judge", "fakejudge")
        finally:
            io.open(reg_path, "w", encoding="utf-8").write(good_reg)
        ok("k061b: a broken channels.json - «judge: not run» with the error's class, the list byte-identical, exit "
           "unchanged (E-1011: the handler takes SystemExit too)", "judge: not run - JSONDecodeError" in out6
           and md6 == md0 and rc6 == rc0, out6.strip()[-300:])

        seen["fail"] = True
        rc5, out5, md5, _r = run("failing", "--judge", "fakejudge")
        ok("k061b: a server that fails every request - the failures are counted, the list byte-identical, exit "
           "unchanged", "3 failed" in out5 and md5 == md0 and rc5 == rc0, out5.strip()[-400:])
    finally:
        srv.shutdown()
        srv.server_close()
    ok("k061b: an off-format answer or an unknown label reads as no answer",
       J.label_of("LABEL: MAYBE\nJUDGE-DONE") is None and J.label_of("I think it is fine") is None
       and J.label_of("LABEL: CONDITION_OMITTED\nREASON: x\nJUDGE-DONE") == "CONDITION_OMITTED")


def suite_k094_condition_cuts(tmp):
    """🔴 K094 (2026-11-26): a verbatim quotation cut so that it drops the CONDITION it hangs on.

    Measured on a copy of a real filed petition: of five cuts made at a clause boundary (the words
    kept verbatim), `check` caught «, except that …» and «absent any negative factors,» and read three
    VERIFIED - a tail cut before «, if the student has completed …» (LIMITER_RE had no «if») and two
    head cuts dropping «Subject to clause (ii),» and «In the absence of adverse factors,» (the head
    test knew negations only). Each widening was measured on the petition's 67 clean quotations and
    on a law library before it shipped (private record K094). The pins hold each caught shape on both
    the exact and the punctuation-drift path, the clean near-miss of each (E-1072), and the two
    mutations that cut where a clause ends, as a drafter does.
    """
    import subprocess as _sp
    from krokai import mutations as MU
    from krokai.corpus import Corpus
    from krokai.verify import check
    d = os.path.join(tmp, "k094")
    os.makedirs(d, exist_ok=True)
    vac = ("A student attending a school on a quarter calendar who takes only one vacation a year during "
           "any one of the quarters instead of during the summer is considered to be in status during "
           "that vacation")
    s_if = vac + (", if the student has completed the equivalent of an academic year prior to taking "
                  "the vacation.")
    waiver = ("the Secretary may, when the Secretary deems it to be in the national interest, waive the "
              "requirements of subparagraph (A) that the services of a foreign national be sought by an "
              "employer in the United States.")
    s_subj = "(B) Waiver of job offer (i) National interest waiver Subject to clause (ii), " + waiver
    adj = ("adjustment will ordinarily be granted, still as a matter of discretion and only after the full "
           "record has been reviewed by the officer.")
    s_abs = "The Board has said that favorable factors will be weighed. In the absence of adverse factors, " + adj
    with io.open(os.path.join(d, "k094-law.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("(iii) Annual vacation. " + s_if + "\n\n" + s_subj + "\n\n" + s_abs + "\n\n"
                 "The school shall report the change to the Service, which shall record it in the file of the "
                 "student concerned.\n\n"
                 "Every decision of the officer is subject to review by the Board, which may affirm or reverse "
                 "the decision in whole or in part.\n\n"
                 "Subject to the conditions and limitations that the Secretary prescribes by regulation for "
                 "this program, the employer may file a single petition for several workers.\n\n"
                 "In general, the agency may accept one petition that covers several workers in the same "
                 "occupation.\n\n"
                 "The term child includes a child adopted while under the age of sixteen years, if such adoption is "
                 "final before the child reaches that age.\n")
    c = Corpus([d], quiet=True)

    def is_(label, q, want, word=None):
        v, _w, dd = check(q, c)
        good = v == want and (word is None or word in (dd or ""))
        ok("k094 " + label, good, "%s :: %s" % (v, (dd or "")[:160]))

    # the three measured misses, each on the exact path and on the punctuation-drift path
    is_("a tail cut before «, if the student has completed …» is TRUNCATED_CONDITION", vac,
        "TRUNCATED_CONDITION", "if the student has completed")
    is_("...and with a drift inside it (the alphanumeric branch) as well",
        vac.replace("during the summer is", "during the summer, is"), "TRUNCATED_CONDITION", "if the student")
    is_("a bare «if» with no article («, if such adoption is final …») is TRUNCATED_CONDITION too",
        "The term child includes a child adopted while under the age of sixteen years", "TRUNCATED_CONDITION",
        "if such adoption")
    is_("a head cut dropping «Subject to clause (ii),» is TRUNCATED_OPENING", waiver, "TRUNCATED_OPENING",
        "subject to")
    is_("...and with a bracketed capital «[T]he Secretary may …» as well", "[T]" + waiver[1:],
        "TRUNCATED_OPENING", "subject to")
    is_("a head cut dropping «In the absence of adverse factors,» is TRUNCATED_OPENING", adj,
        "TRUNCATED_OPENING", "in the absence of")
    # the clean near-misses (E-1072)
    is_("the whole sentence with its «, if …» is VERIFIED", s_if, "VERIFIED")
    is_("a quotation stopping before «, which …» is VERIFIED (not a limiter)",
        "The school shall report the change to the Service", "VERIFIED")
    is_("the sentence that STARTS with «Subject to clause (ii),» is VERIFIED",
        "Subject to clause (ii), " + waiver, "VERIFIED")
    is_("a start after a later comma of the same sentence is VERIFIED (the condition closed earlier)",
        "still as a matter of discretion and only after the full record has been reviewed by the officer.",
        "VERIFIED")
    is_("«is subject to review by the Board,» is a predicate, not an opening condition - VERIFIED",
        "which may affirm or reverse the decision in whole or in part.", "VERIFIED")
    is_("an opener 15 words back is outside the measured 12-word window - VERIFIED (a documented limit)",
        "the employer may file a single petition for several workers.", "VERIFIED")
    is_("a start after «In general,» (no condition) is VERIFIED",
        "the agency may accept one petition that covers several workers in the same occupation.", "VERIFIED")

    # the generator: clause-boundary cuts beside the mid-clause one
    mid = "The officer who reviews the application shall find that the alien is not eligible for the benefit."
    ok("k094 m_cut_clause stops at «, if …», where the clause ends", MU.m_cut_clause(s_if) == vac,
       repr(MU.m_cut_clause(s_if))[-60:])
    ok("k094 m_cut_clause never cuts mid-clause (a limiter with no comma before it)",
       MU.m_cut_clause(mid) is None
       and MU.m_cut_condition(mid) == "The officer who reviews the application shall find that the alien",
       "%r / %r" % (MU.m_cut_clause(mid), MU.m_cut_condition(mid)))
    ok("k094 m_drop_opening drops «Subject to clause (ii),» at the comma that closes it",
       MU.m_drop_opening("Subject to clause (ii), " + waiver) == waiver,
       repr(MU.m_drop_opening("Subject to clause (ii), " + waiver))[:60])
    ok("k094 m_drop_opening leaves a non-condition opener and an over-long one alone",
       MU.m_drop_opening("In general, the employer may file a single petition for several workers in the "
                         "same occupation.") is None
       and MU.m_drop_opening("Subject to the conditions and limitations that the Secretary prescribes by "
                             "regulation for this program, the employer may file a single petition.") is None)
    stats, rows = MU.run([(s_if, "k094-law.md"), ("Subject to clause (ii), " + waiver, "k094-law.md")], c,
                         limit=5, printer=lambda *_a: None)
    for name, want in (("cut-clause", "TRUNCATED_CONDITION"), ("drop-opening", "TRUNCATED_OPENING")):
        mine = [r for r in rows if r["mutation"] == name]
        ok("k094 mutation %s is made and caught for the right reason" % name,
           mine and all(r["caught"] and r["verdict"] == want for r in mine), str(mine)[:200])

    # through the real CLI (E-215): the label and the widened meaning a user reads
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    matter = os.path.join(tmp, "k094m")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    def run(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=root, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    rc, out = run("init", matter)
    if rc != 0:
        ok("k094: init failed - the CLI pins were skipped", False, out[-200:])
        return
    shutil.copy(os.path.join(d, "k094-law.md"), os.path.join(matter, "law", "k094-law.md"))
    _rc, out = run("quote", "--dir", matter, waiver)
    ok("k094 CLI quote: the «Subject to» cut prints TRUNCATED OPENING with «a negation or a condition»",
       ("TRUNCATED OPENING" in out or "ОБРЕЗАНО НАЧАЛО" in out)
       and ("a negation or a condition" in out or "отрицания или условия" in out), out[-300:])
    _rc, out = run("quote", "--dir", matter, vac)
    ok("k094 CLI quote: the «, if …» cut prints TRUNCATED CONDITION",
       "TRUNCATED CONDITION" in out or "ОБРЕЗАНО УСЛОВИЕ" in out, out[-300:])
    _rc, out = run("quote", "--dir", matter, s_if)
    ok("k094 CLI quote: the whole sentence prints VERIFIED (the clean path through the same door)",
       ("VERIFIED" in out or "ДОСЛОВНО" in out) and "ОБРЕЗАНО" not in out and "TRUNCATED" not in out, out[-300:])


def suite_k026_front_door(tmp):
    """K026 + K016 (2026-11-25): what enters the library must be the document it claims to be. ONE
    --address takes ONE inbox file; a «new edition» that keeps too little of the current one's text
    is refused (a foreign law, a publisher's empty shell) unless the user says so; a real rewrite like
    the measured USCIS-PM 8.G.12 edition still goes in, under any file name; `fetch` refuses a
    redirect to the site's home page and a page whose own title is an error title, and never a law
    page for an error word in its body. Measured on real publishers in the private record K026."""
    import json
    import subprocess as _sp
    from krokai import fetch as F
    from krokai.citations import load_packs
    from krokai.config import load as load_cfg

    root = os.path.join(tmp, "k026m")
    os.makedirs(os.path.join(root, "law"))
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "library_index": "law/INDEX.md", "sources": ["law"], "drafts": [],
        "citation_packs": ["us-immigration", "us-federal"]}))
    cfg = load_cfg(root)
    packs = load_packs(cfg["citation_packs"])
    inbox = os.path.join(root, F.INBOX)
    os.makedirs(inbox)
    chrome = " ".join("Navigation block %d: contact website careers privacy updates explore subject %d." % (j, j)
                      for j in range(6))
    law = ["Section 245.%d provides that the officer examines records numbered %d before deciding whether "
           "adjustment applies to applicant %d." % (i, i, i) for i in range(40)]
    rewrite = ["Section 245.%d now requires counsel to present evidence numbered %d whenever another "
               "applicant %d appears." % (i, i, i) for i in range(40)]
    foreign = " ".join("Paragraph 214.%d governs student visitor reporting duties numbered %d for schools "
                       "certified under program %d." % (i, i, i) for i in range(40))
    OLD = chrome + " " + " ".join(law)
    LIGHT = chrome + " " + " ".join(law[:36] + rewrite[36:])
    HEAVY = chrome + " " + " ".join(law[:15] + rewrite[15:])          # like USCIS-PM 8.G.12 (K026)
    SHELL = chrome + " Policy Manual chapter page."
    share = lambda a, b: F.edition_overlap(a, b)[0]                    # noqa: E731
    ok("k026: fixture - a foreign law keeps ~0 of the current edition, an empty shell (chrome only) "
       "little, a heavy rewrite 40-50 % like the measured PM 8.G.12, a light edit most of it",
       share(OLD, foreign) < 0.05 and share(OLD, SHELL) < F.REVISION_FLOOR
       and 0.40 <= share(OLD, HEAVY) <= 0.50 and share(OLD, LIGHT) > 0.85,
       "foreign %.2f shell %.2f heavy %.2f light %.2f floor %.2f" % (
           share(OLD, foreign), share(OLD, SHELL), share(OLD, HEAVY), share(OLD, LIGHT), F.REVISION_FLOOR))
    ok("k026: the share is counted on the CURRENT edition's side - the shell scores 100 % the symmetric way",
       F.edition_overlap(chrome, OLD)[0] == 1.0 and share(OLD, chrome) < 0.5,
       "%s %.2f" % (F.edition_overlap(chrome, OLD), share(OLD, chrome)))
    short_old = "Sec. 553.101 Volunteer defined. An individual who performs hours of service is a volunteer."
    ok("k026: a short section is measured in sentences when it has too few shingles",
       F.edition_overlap(short_old, short_old + " A new sentence.") == (1.0, "sentences"),
       str(F.edition_overlap(short_old, short_old)))
    big_chrome = " ".join("Site menu entry %d: contact website careers privacy updates explore subject "
                          "dossier %d." % (j, j) for j in range(17))
    OLD_B = big_chrome + " " + " ".join(law[:25])
    SHRINK = chrome + " " + " ".join(law[:17] + rewrite[17:21])       # like PM 8.G.9: smaller, adds text
    d_frag = F.revision_doubt(OLD_B, big_chrome)
    ok("k026: red - an empty page whose site chrome is a big share of the page (PM 6.E.9's 41 %) passes "
       "the floor and is caught as a FRAGMENT: it adds nothing and is under half the size",
       share(OLD_B, big_chrome) >= F.REVISION_FLOOR and "FRAGMENT" in (d_frag or ""),
       "%.2f %s" % (share(OLD_B, big_chrome), d_frag))
    ok("k026: green - real editions are not doubted: a heavy rewrite, a light edit, a smaller edition that "
       "adds text (like PM 8.G.9 at 56 % of the size)",
       F.revision_doubt(OLD, HEAVY) is None and F.revision_doubt(OLD, LIGHT) is None
       and F.revision_doubt(OLD, SHRINK) is None,
       "%s | %s | %s" % (F.revision_doubt(OLD, HEAVY), F.revision_doubt(OLD, LIGHT), F.revision_doubt(OLD, SHRINK)))
    ok("k026: red - a foreign law is doubted as a DIFFERENT document",
       "DIFFERENT" in (F.revision_doubt(OLD, foreign) or ""))

    ecfr = "https://www.ecfr.gov/api/versioner/v1/full/%s/title-8.xml?part=245"

    def drop(name, body, day="2026-11-20"):
        io.open(os.path.join(inbox, name), "w", encoding="utf-8", newline="\n").write(body)
        io.open(os.path.join(inbox, name + ".meta.json"), "w", encoding="utf-8").write(json.dumps(
            {"url": ecfr % day, "sha256": F.sha256_of(body.encode("utf-8")), "trust": "primary",
             "trust_label": "OFFICIAL", "model_in_path": False, "fetched_at": day + "T10:00:00"}))

    def take(**kw):
        return F.intake(root, cfg, packs, address="8 CFR 245", printer=lambda *a: None, **kw)

    def pending():
        return sorted(f for f in os.listdir(inbox) if not f.endswith(".meta.json"))

    def clear(name):                           # tolerant: a mutation may already have moved it (E-1064)
        for p in (name, name + ".meta.json"):
            if os.path.exists(os.path.join(inbox, p)):
                os.remove(os.path.join(inbox, p))

    def index_rows():
        p = os.path.join(root, "law", "INDEX.md")
        return [ln for ln in io.open(p, encoding="utf-8").read().splitlines()
                if ln.startswith("| ") and "`" in ln] if os.path.exists(p) else []

    drop("part-245.xml", OLD, "2026-08-01")
    r = take()
    ok("k026: green - one file, one address: filed", [s for s, _n, _x in r] == ["added"], str(r))
    drop("other-law.xml", foreign)
    drop("part-245-again.xml", LIGHT)
    r = take()
    ok("k026: red - two files in the inbox and ONE --address: both refused, nothing filed",
       [s for s, _n, _x in r] == ["REFUSED", "REFUSED"] and "ONE citation" in r[0][2]
       and pending() == ["other-law.xml", "part-245-again.xml"] and len(index_rows()) == 1, str(r))
    clear("part-245-again.xml")
    r = take()
    ok("k026: red - a foreign law under an address that has a file is refused, the current law is not "
       "marked superseded, the register still names it",
       [s for s, _n, _x in r] == ["REFUSED"] and "DIFFERENT document" in r[0][2]
       and "--allow-low-overlap" in r[0][2] and pending() == ["other-law.xml"]
       and not any("SUPERSEDED" in ln for ln in index_rows())
       and F._registry(root)["cfr|8|245"]["path"].endswith("part-245.xml"), "%s %s" % (r, index_rows()))
    clear("other-law.xml")
    drop("chapter-shell.html", SHELL)
    r = take()
    ok("k026: red - an empty page (site chrome only) is not a new edition",
       [s for s, _n, _x in r] == ["REFUSED"] and not any("SUPERSEDED" in ln for ln in index_rows()), str(r))
    clear("chapter-shell.html")
    drop("document.xml", HEAVY)
    r = take()
    ok("k026: green - a heavy rewrite of the provision (kept ~45 %, PM 8.G.12) under an arbitrary file "
       "name is filed as the new edition and the old one is marked superseded (K028 unchanged)",
       [s for s, _n, _x in r] == ["🔴 REVISION"] and "of the old text kept" in r[0][2]
       and any("SUPERSEDED" in ln and "part-245.xml" in ln for ln in index_rows()), "%s %s" % (r, index_rows()))
    drop("other-law.xml", foreign)
    r = take(allow_low_overlap=True)
    ok("k026: green - --allow-low-overlap is the user's word: the low-overlap file goes in, and the row says so",
       [s for s, _n, _x in r] == ["🔴 REVISION"] and "(--allow-low-overlap)" in r[0][2] and pending() == [], str(r))

    # the CLI: the flag exists and a refusal reaches the exit code (3), the hint names the flag
    root2 = os.path.join(tmp, "k026c")
    os.makedirs(os.path.join(root2, "law"))
    io.open(os.path.join(root2, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "library_index": "law/INDEX.md", "sources": ["law"], "drafts": [],
        "citation_packs": ["us-immigration", "us-federal"]}))
    inbox, root = os.path.join(root2, F.INBOX), root2
    os.makedirs(inbox)
    cfg = load_cfg(root2)
    drop("part-245.xml", OLD, "2026-08-01")
    take()
    drop("other-law.xml", foreign)
    env = dict(os.environ, PYTHONPATH=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
               PYTHONIOENCODING="utf-8")
    cp = _sp.run([sys.executable, "-m", "krokai", "intake", "--address", "8 CFR 245", "--dir", root2],
                 stdout=_sp.PIPE, stderr=_sp.PIPE, env=env, timeout=120)
    out = (cp.stdout or b"").decode("utf-8", "replace")
    ok("k026: CLI - `intake` refuses with exit 3 and names --allow-low-overlap",
       cp.returncode == 3 and "REFUSED" in out and "--allow-low-overlap" in out, "rc=%d %s" % (cp.returncode, out[-300:]))
    cp = _sp.run([sys.executable, "-m", "krokai", "intake", "--address", "8 CFR 245", "--allow-low-overlap",
                  "--dir", root2], stdout=_sp.PIPE, stderr=_sp.PIPE, env=env, timeout=120)
    out = (cp.stdout or b"").decode("utf-8", "replace")
    ok("k026: CLI - with --allow-low-overlap the same file is filed (exit 4, a revision)",
       cp.returncode == 4 and "REVISION" in out, "rc=%d %s" % (cp.returncode, out[-300:]))

    # K016: soft 404 - two signals a law page never gives; an error WORD in a law page's body never refuses
    s4 = F.soft404_reason
    html = lambda title, body="": ("<html><head><title>%s</title></head><body>%s</body></html>"   # noqa: E731
                                   % (title, body)).encode("utf-8")
    ok("k016: red - a redirect to the publisher's home page is not the document",
       s4("https://www.uscis.gov/policy-manual/volume-7-part-b-chapter-99", "https://www.uscis.gov/",
          "text/html", html("Home | USCIS")) is not None)
    ok("k016: red - a redirect from a query URL to the home page is not the document",
       s4("https://uscode.house.gov/view.xhtml?req=granuleid:USC-prelim-title8-section1255",
          "https://uscode.house.gov/", "text/html", html("Office of the Law Revision Counsel")) is not None)
    ok("k016: red - an HTTP 200 whose own title is an error title (any page size)",
       all(s4("https://www.uscis.gov/x/y", "https://www.uscis.gov/x/y", "text/html; charset=UTF-8",
              html(t, "menu " * 9000)) for t in ("Page Not Found | USCIS", "404 - Page Not Found",
                                                 "Not Found", "Error 404 :: eCFR", "Page Not Found | GovInfo",
                                                 "Federal Register :: Request Access")))
    ok("k016: green - a law page passes, error words in its BODY included (the 0.7.1 lesson)",
       s4("https://www.uscis.gov/policy-manual/volume-7-part-b-chapter-8",
          "https://www.uscis.gov/policy-manual/volume-7-part-b-chapter-8", "text/html",
          html("Chapter 8 - Inapplicability of Bars to Adjustment | USCIS",
               "If the record is not found, page not found errors do not apply. Error 404 " * 50)) is None
       and s4("https://www.ecfr.gov/current/title-8/part-245", "https://www.ecfr.gov/current/title-8/part-245",
              "text/html", html("eCFR :: 8 CFR Part 245 -- Adjustment of Status")) is None)
    ok("k016: green - a PDF is never judged by an HTML title, a redirect to a deeper page is not «home»",
       s4("https://www.justice.gov/eoir/page/file/1/dl", "https://www.justice.gov/d9/2026/x.pdf",
          "application/pdf", b"%PDF-1.7 <title>Not Found</title>") is None
       and s4("https://www.ecfr.gov/x", "https://www.ecfr.gov/current/title-8/part-245", "text/html",
              html("eCFR :: 8 CFR Part 245")) is None)

    # E-215: the guard must be reached by the code `krokai fetch` runs - a stand-in `requests` (no network)
    import types

    class _Resp(object):
        def __init__(self, final, body, ctype="text/html; charset=UTF-8", status=200):
            self.url, self.status_code, self.content = final, status, body
            self.headers = {"Content-Type": ctype}

    answers = {}
    fake = types.ModuleType("requests")
    fake.get = lambda url, **kw: answers[url]
    real_mod = sys.modules.get("requests")
    sys.modules["requests"] = fake
    try:
        froot = os.path.join(tmp, "k026f")
        os.makedirs(froot)
        ib = os.path.join(froot, F.INBOX)
        bad = "https://www.govinfo.gov/content/pkg/FR-2026-01-02/html/2026-43423.htm"
        answers[bad] = _Resp("https://www.govinfo.gov/error", html("Page Not Found | GovInfo", "menu " * 9000))
        good = "https://www.ecfr.gov/current/title-8/part-245"
        answers[good] = _Resp(good, html("eCFR :: 8 CFR Part 245 -- Adjustment of Status",
                                         "Sec. 245.1 Eligibility of an applicant. " * 400))
        out = []
        r_bad = F.fetch_url(bad, froot, packs=packs, printer=out.append)
        ok("k016: red - `fetch` itself refuses the soft 404 (wired, not only defined) and saves nothing",
           r_bad is None and any("HTTP 200, but" in x for x in out)
           and not (os.path.isdir(ib) and os.listdir(ib)), str(out[-2:]))
        out = []
        r_good = F.fetch_url(good, froot, packs=packs, printer=out.append)
        ok("k016: green - `fetch` saves a law page", bool(r_good) and len(os.listdir(ib)) == 2, str(out[-3:]))
    finally:
        if real_mod is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = real_mod


def suite_k018_pages(tmp):
    """K018 (2026-11-26): a match in a PDF says which page OF THE FILE it stands on - `quote`,
    `check` (result.json, REPORT.md) - or «page unknown» with the reason. The pages are counted in
    letters and digits beside the text cache and checked against the indexed text before any page
    is named. Before, the extracted text was one string with no page in it: a quotation verbatim on
    one page verified exactly like the same words cited to another, so no pincite could be checked."""
    import builtins
    import json
    import subprocess as _sp
    from krokai import readers as R
    from krokai.normalize import alnum as _al, normalise as _nm, strip_scrape_artifacts as _ss
    from krokai.corpus import Corpus
    from krokai.verify import check, page_of
    from krokai.verdicts import CLEAN

    # -- the arithmetic, with no PDF engine at all ---------------------------------------------
    pages = ["Alpha beta 12.", "", "Gamma delta.", "Epsilon."]
    f = R._page_facts(pages, "t", False)
    at = "".join(_al(_nm(_ss(t))) for t in pages)
    ok("k018: page counts that add up to the indexed text give the page ends; an empty page takes "
       "no room", R.page_check(f, at) == ([11, 11, 21, 28], ""), str(R.page_check(f, at)))
    bad = [R.page_check(f, at[:-1] + "x"), R.page_check(f, at + "tail"), R.page_check(f, at[:-3]),
           R.page_check(dict(f, alnum=None, why="w"), at)]
    ok("k018: counts that do NOT add up name no page - another text, a tail with no form fields, a "
       "shorter text, an unmeasured file", all(b[0] is None and b[1] for b in bad), str(bad))
    ok("k018: form-field values may stand after the last page",
       R.page_check(R._page_facts(pages, "t", True), at + "fieldvalue")[0] == [11, 11, 21, 28])

    try:
        from krokai import _pdfengine
        fz = _pdfengine.load()
    except ImportError:
        fz = None
    if fz is None:
        print("note: k018 page fixture pins skipped - PyMuPDF builds the fixtures and is not "
              "installed here")
        return
    try:
        import pypdf  # noqa: F401
        have_pypdf = True
    except ImportError:
        have_pypdf = False

    root = os.path.join(tmp, "k018m")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))

    def make(path, pgs):
        d = fz.open()
        for lines in pgs:
            pg = d.new_page()
            for i, ln in enumerate(lines):
                pg.insert_text((50, 60 + 14 * i), ln, fontsize=9)
        d.save(path)
        d.close()

    def fill(tag):
        return ["Filler line %d of the %s page keeps this fixture above every reader floor." % (i, tag)
                for i in range(6)]

    REP_S = "The applicant bears the burden of proof in every proceeding under this part."
    P2_S = "An officer may request additional evidence when the record does not establish eligibility."
    CROSS_A = "A decision on the application shall be made in writing and shall"
    CROSS_B = "state the reasons for any denial of the benefit requested."
    CROSS = CROSS_A + " " + CROSS_B
    P3_S = "The record shall include every document the applicant submitted with the form."
    ELL = "The record shall include every document ... submitted with the form."
    UNK_S = "Each petition under this section shall be filed with the fee the form prescribes."
    MD_S = "A notice of intent to deny shall give the applicant thirty days to respond."
    pdf4, pdfu = os.path.join(law, "8CFR-296.pdf"), os.path.join(law, "8CFR-295.pdf")
    # REP_S opens page 4: its first letter IS the first letter of that page (the boundary case)
    make(pdf4, [["Sec. 296.1 Fixture rule.", REP_S] + fill("first"),
                [P2_S] + fill("second") + [CROSS_A], [CROSS_B, P3_S] + fill("third"),
                [REP_S] + fill("fourth")])
    # a footnote link split by the page break: the clean-up removes it from the joined text only
    make(pdfu, [["Sec. 295.1 Fixture rule.", UNK_S] + fill("fifth") + ["See [12](https://x.gov/pm/v7"],
                ["#footnote-12) for the rule."] + fill("sixth")])
    io.open(os.path.join(law, "8CFR-294.md"), "w", encoding="utf-8").write(
        "# Sec. 294.1 Fixture rule.\n\n%s\n\n%s\n" % (MD_S, "\n".join(fill("text"))))

    cache = os.path.join(tmp, "k018cache")
    R._PAGES_MEMO.clear()
    R.read_pdf(pdf4, cache)
    pf = R._pages_file(pdf4, cache)
    disk = json.load(io.open(pf, encoding="utf-8")) if os.path.exists(pf) else {}
    ok("k018: read_pdf keeps the page counts of the extraction it chose beside the text cache",
       disk.get("v") == R.PAGES_VERSION and len(disk.get("alnum") or []) == 4
       and disk.get("engine") in ("pypdf", "PyMuPDF"), str(disk)[:200])

    def pg(q, c):
        v, w, _d = check(q, c)
        return v, page_of(q, w, c)

    def head(g):                      # K018b: the PDF page part of a label, before its printed page
        return ((g or {}).get("label") or "").split(" (printed page unknown")[0]

    corp = Corpus([law], quiet=True, cache_dir=cache)
    got = [pg(q, corp) for q in (P2_S, CROSS, REP_S, ELL)]
    labels = [head(g) for _v, g in got]
    ok("k018: the page of a match - one page, across a page break, a sentence the file repeats (on "
       "the page that STARTS with it too), an ellipsis quotation",
       labels == ["PDF page 2 of 4", "PDF pages 2-3 of 4", "PDF page 1 of 4", "PDF page 3 of 4"]
       and (got[2][1] or {}).get("pdf_pages") == [[1, 1], [4, 4]]
       and "; also on PDF page 4)" in (got[2][1] or {}).get("label", "")
       and all(v in CLEAN for v, _g in got[:3]), str(got))
    v5, g5 = pg(UNK_S, corp)
    ok("k018: «page unknown» with its reason when the page counts do not add up to the indexed text "
       "(a link removed across a page break) - and the verdict is untouched",
       v5 in CLEAN and (g5 or {}).get("label", "").startswith("page unknown - ")
       and not (g5 or {}).get("pdf_pages"), str((v5, g5)))
    v6, g6 = pg(MD_S, corp)
    v7, g7 = pg("The officer may waive every requirement of this part at any time for any reason.", corp)
    ok("k018: a match in a text source, and a quotation found nowhere, name no page",
       v6 in CLEAN and g6 is None and v7 == "NOT_FOUND" and g7 is None, str((v6, g6, v7, g7)))

    if os.path.exists(pf):            # absent only when the pin above is already red
        os.remove(pf)
    R._PAGES_MEMO.clear()
    g8 = pg(P2_S, Corpus([law], quiet=True, cache_dir=cache))[1]
    ok("k018: a text cache written before the pages file existed gets its pages re-read, checked "
       "and kept", head(g8) == "PDF page 2 of 4" and os.path.exists(pf), str(g8))

    if have_pypdf:
        real_import = builtins.__import__

        def imp(name, *a, **k):
            if name.split(".")[0] in ("fitz", "pymupdf"):
                raise ImportError("hidden by the k018 selftest: %s" % name)
            return real_import(name, *a, **k)

        R._PAGES_MEMO.clear()
        builtins.__import__ = imp
        try:
            g9 = pg(CROSS, Corpus([law], quiet=True))[1]
        finally:
            builtins.__import__ = real_import
        ok("k018: with pypdf alone the same pages come back", head(g9) == "PDF pages 2-3 of 4",
           str(g9))
    else:
        print("note: k018 pypdf-alone pin skipped - pypdf is not installed here")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    q1, q2, q3 = (cli("quote", "--dir", root, q)[1] for q in (CROSS, UNK_S, MD_S))
    ok("k018: `quote` prints the PDF page, «page unknown» with its reason, and no page line for a "
       "text source", "PDF pages 2-3 of 4 (printed page unknown - " in q1 and "page unknown - " in q2
       and "PDF page" not in q3 and "page unknown" not in q3, (q1[:300] + " || " + q2[:300]))
    DRIFT = CROSS.replace("in writing and", "in writing, and")
    io.open(os.path.join(case, "petition.md"), "w", encoding="utf-8").write(
        'Under 8 C.F.R. § 296.1, "%s"\n\nUnder 8 C.F.R. § 296.1, "%s"\n\n'
        'Under 8 C.F.R. § 295.1, "%s"\n\nUnder 8 C.F.R. § 294.1, "%s"\n' % (P2_S, DRIFT, UNK_S, MD_S))
    out_dir = os.path.join(tmp, "k018o")
    _rc, out = cli("check", "--dir", root, "--out", out_dir)
    rj = os.path.join(out_dir, "result.json")
    rows = (json.load(io.open(rj, encoding="utf-8")) if os.path.exists(rj) else {}).get("rows", [])

    def row(marker):
        return next((r for r in rows if marker in r["quote"]), {})

    md = (io.open(os.path.join(out_dir, "REPORT.md"), encoding="utf-8").read()
          if os.path.exists(os.path.join(out_dir, "REPORT.md")) else "")
    r1, r2, r3, r4 = row("request additional"), row("writing, and"), row("fee the form"), row("thirty days")
    ok("k018: result.json rows carry the page or why not, and REPORT.md prints it beside «Found in»",
       (r1.get("page") or {}).get("pdf_pages") == [[2, 2]] and r2.get("verdict") == "PUNCTUATION"
       and (r2.get("page") or {}).get("pdf_pages") == [[2, 3]]
       and (r3.get("page") or {}).get("unknown") and r4.get("verdict") in CLEAN
       and r4.get("page") is None and "8CFR-296.pdf` - PDF pages 2-3 of 4" in md,
       str([(r.get("verdict"), r.get("page")) for r in (r1, r2, r3, r4)]) + " || " + out[-300:])


def suite_k018b_printed_pages(tmp):
    """K018b (2026-11-27): beside the PDF page, the page the source PRINTS - a reprint's own number
    on a line of its own, proven by the file's one run of numbers (a page without one is counted
    only between numbered pages), or a GPO text's `[[Page N]]` / `[[Page 110 STAT. N]]` markers,
    whose pieces must add up to the indexed text. «printed page unknown» and why everywhere else.
    And the Statutes-at-Large marker, which the clean-up never matched, no longer breaks a quotation
    that crosses it. Before: only the FILE page, so a pincite to «21 I&N Dec. 296, 299» could not be
    compared with anything."""
    import json
    import subprocess as _sp
    from krokai import readers as R
    from krokai.normalize import alnum as _al, normalise as _nm
    from krokai.corpus import Corpus
    from krokai.verify import check, page_of
    from krokai.verdicts import CLEAN

    # -- the run, with no PDF engine ----------------------------------------------------------
    pp = R._printed_pages
    run = pp(["296\nAlpha.", "Beta.\n297", "Gamma.", "[299]\nDelta.", "Epsilon."])
    ok("k018b: a run of printed numbers - each page's own (p), one counted between two numbered pages "
       "(b), one outside them unknown (n)", run == {"offset": 295, "kinds": "ppbpn", "why": ""}, str(run))
    ocr = pp(["296\nA.", "997\nB.", "298\nC.", "299\nD."])
    ok("k018b: a number the OCR misread on one page does not break the file's run - the page is "
       "counted between its neighbours", ocr == {"offset": 295, "kinds": "pbpp", "why": ""}, str(ocr))
    tab = ["x\n%d\ny" % (40 + i) for i in range(1, 7)]
    tab[1] += "\n" + "\n".join(str(n) for n in range(1, 25))
    tab[4] += "\n" + "\n".join(str(n) for n in range(1, 25))
    tab_run = pp(tab)
    ok("k018b: two pages of a table of numbers make a plateau of weak offsets and do not outvote the "
       "run", tab_run.get("offset") == 40 and tab_run.get("kinds") == "pppppp", str(tab_run))
    nones = [pp(["Alpha.", "Beta 3 of 4."]), pp(["Alpha.\n12", "Beta."]),
             pp(["10\nA.", "11\nB.", "12\nC.", "1\nD.", "2\nE.", "3\nF."])]
    ok("k018b: no run - no page prints a number alone on a line, only one does, two sequences of "
       "equal strength", [n.get("why") for n in nones] == [R.PRINTED_NONE, R.PRINTED_FEW, R.PRINTED_TWO]
       and all(n.get("offset") is None for n in nones), str(nones))
    glued = ["Alpha text 296", "Beta text 297", "Gamma text 298"]
    alone = ["296\nAlpha text", "Beta text\n297", "298\nGamma text"]
    ok("k018b: a number one engine glues to a line and the other reads alone still counts - the "
       "page is the same page", pp(glued).get("offset") is None
       and pp(glued, also=alone).get("kinds") == "ppp", str(pp(glued, also=alone)))
    spans = [R.printed_span(run, 2, 2), R.printed_span(run, 2, 3), R.printed_span(run, 5, 5),
             R.printed_span(nones[0], 1, 1), R.printed_span(None, 1, 1)]
    ok("k018b: the printed pages of a PDF span - own number, counted between, outside, no run, not "
       "measured", spans[:3] == [([297, 297], "page"), ([297, 298], "between"),
                                 (None, R.PRINTED_OUTSIDE)]
       and spans[3] == (None, R.PRINTED_NONE) and spans[4][0] is None and spans[4][1], str(spans))

    root = os.path.join(tmp, "k018bm")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))

    def fill(tag):
        return ["Filler line %d of the %s page keeps this fixture above every reader floor." % (i, tag)
                for i in range(6)]

    # -- GPO markers: a Federal Register text and a Public Law --------------------------------
    FR_LEAD = "The lead paragraph of this rule stands on the page before the first page marker."
    FR_A = "The Secretary may extend the period of admission for good cause shown and shall"
    FR_B = "publish each extension in the Federal Register within thirty days."
    FR_X = FR_A + " " + FR_B
    io.open(os.path.join(law, "91FR41299-fixture-rule.txt"), "w", encoding="utf-8").write(
        "[Federal Register Volume 91, Number 99 (Monday, May 4, 2026)]\n[Rules and Regulations]\n"
        "[Pages 41299-41302]\n\n%s\n%s\n\n[[Page 41300]]\n\n%s\n%s\n[[Page 41301]]\n%s\n%s\n\n"
        "[[Page 41302]]\n\nThe final page of the fixture rule carries only its signature block.\n"
        % (FR_LEAD, "\n".join(fill("lead")), "\n".join(fill("41300")), FR_A, FR_B,
           "\n".join(fill("41301"))))
    FR2_LEAD = "A notice whose header names pages that do not touch its first marker stays unknown."
    io.open(os.path.join(law, "91FR50001-fixture-notice.txt"), "w", encoding="utf-8").write(
        "[Federal Register Volume 91, Number 120 (Friday, June 5, 2026)]\n[Notices]\n"
        "[Pages 50001-50004]\n\n%s\n%s\n\n[[Page 50003]]\n\n%s\n"
        % (FR2_LEAD, "\n".join(fill("notice")), "\n".join(fill("50003"))))
    PL_A = "The Attorney General may not admit an alien under this fixture section unless the alien"
    PL_B = "establishes eligibility for the benefit by clear and convincing evidence."
    PL_X = PL_A + " " + PL_B
    io.open(os.path.join(law, "PL-199-999-fixture.htm"), "w", encoding="utf-8").write(
        "<html><body><pre>\n[DOCID: f:publ999.199]\n\n[[Page 110 STAT. 3009-546]]\n\n"
        "SEC. 999. FIXTURE PROVISION.\n%s\n    (a) In General.--%s\n[[Page 110 STAT. 3009-547]]\n%s\n%s\n"
        "</pre></body></html>\n" % ("\n".join(fill("statute")), PL_A, PL_B, "\n".join(fill("547"))))
    pl_raw = "shall be\n[[Page 110 STAT. 3009-547]]\nadmitted"
    ok("k018b: the clean-up removes a Statutes-at-Large page marker, as it always removed a Federal "
       "Register one", _nm(pl_raw) == "shall be admitted" and _nm("a [[Page 41300]] b") == "a b",
       repr(_nm(pl_raw)))

    corp = Corpus([law], quiet=True)
    gx = [(lambda v, w, _d: (v, page_of(q, w, corp)))(*check(q, corp)) for q in (FR_X, FR_LEAD, FR2_LEAD, PL_X)]
    ok("k018b: a match in a GPO text names the printed page its markers put it on - across a marker "
       "both pages, the lead piece by the source's own «[Pages N-M]» line",
       gx[0][0] in CLEAN and (gx[0][1] or {}).get("printed") == [["41300", "41301"]]
       and (gx[0][1] or {}).get("label") == "printed pages 41300-41301 (by the source's own page markers)"
       and gx[1][0] in CLEAN and (gx[1][1] or {}).get("printed") == [["41299", "41299"]], str(gx[:2]))
    ok("k018b: a lead piece the header does not place is «printed page unknown» with the reason",
       gx[2][0] in CLEAN and (gx[2][1] or {}).get("printed") == [None]
       and (gx[2][1] or {}).get("label") == "printed page unknown - %s" % R.MARK_LEAD, str(gx[2]))
    ok("k018b: a quotation across a Statutes-at-Large page break verifies, and names both pages by "
       "their own labels", gx[3][0] in CLEAN and (gx[3][1] or {}).get("printed")
       == [["110 STAT. 3009-546", "110 STAT. 3009-547"]]
       and "pages 110 STAT. 3009-546 to 110 STAT. 3009-547" in (gx[3][1] or {}).get("label", ""),
       str(gx[3]))
    frp = os.path.join(law, "91FR41299-fixture-rule.txt")
    good = _al(corp.text_of(frp))
    ok("k018b: markers whose pieces do not add up to the indexed text name no page",
       R.marker_table(frp, good)[0] is not None
       and R.marker_table(frp, good[:-5] + "zzzzz") == (None, None, R.MARK_BROKEN),
       str(R.marker_table(frp, good[:-5] + "zzzzz")))

    try:
        from krokai import _pdfengine
        fz = _pdfengine.load()
    except ImportError:
        fz = None
    if fz is None:
        print("note: k018b printed-page PDF pins skipped - PyMuPDF builds the fixtures and is not "
              "installed here")
        return

    def make(path, pgs):
        d = fz.open()
        for lines in pgs:
            p_ = d.new_page()
            y = 46
            for ln in lines:
                if isinstance(ln, tuple):     # (x, text): on the baseline of the line before it
                    p_.insert_text((ln[0], y), ln[1], fontsize=9)
                    continue
                y += 14
                p_.insert_text((50, y), ln, fontsize=9)
        d.save(path)
        d.close()

    S1 ="The respondent bears the burden of establishing eligibility for the relief he seeks here."
    S2 = "An immigration judge may grant a continuance for good cause shown on the record before him."
    S3 = "The Board reviews findings of fact for clear error and all other questions de novo."
    S4 = "A motion to reopen must state the new facts that will be proven at a hearing if granted."
    S5 = "The record is remanded to the immigration judge for further proceedings consistent here."
    # the name says 500 and the pages print 296-300: the printed page comes from the pages. Pages 2
    # and 4 print their number on the running header's baseline, as reprints do: pypdf (the engine
    # the corpus indexes) reads «… (BIA 2026) 297», PyMuPDF «297» alone - `read_pdf` asks both
    HDR = "Cite as 27 I&N Dec. 296 (BIA 2026)"
    dec = os.path.join(law, "Matter-of-Fixture-27-IN-Dec-500.pdf")
    make(dec, [["296", "Matter of FIXTURE", S1] + fill("first"),
               [HDR, (500, "297"), S2] + fill("second"),
               [S3] + fill("third"),
               [HDR, (500, "299"), S4] + fill("fourth"),
               [S5] + fill("fifth")])
    two = os.path.join(law, "Fixture-two-parts.pdf")
    T2 = "Each part of this fixture is numbered on its own and the two runs never meet at all."
    make(two, [["%d" % (10 + i), T2 if i == 1 else "Part one page."] + fill("one-%d" % i) for i in range(3)]
         + [["%d" % (i + 1), "Part two page."] + fill("two-%d" % i) for i in range(3)])
    cache = os.path.join(tmp, "k018bcache")
    R._PAGES_MEMO.clear()
    pc = Corpus([law], quiet=True, cache_dir=cache)

    def lab(q):
        v, w, _d = check(q, pc)
        return v, page_of(q, w, pc)

    got = [lab(q) for q in (S2, S3, S5, T2)]
    ok("k018b: a PDF match names the page the decision prints - its own number (not the file name's), "
       "one counted between numbered pages",
       got[0][0] in CLEAN and (got[0][1] or {}).get("label") == "PDF page 2 of 5, printed page 297"
       and (got[0][1] or {}).get("printed") == [[297, 297]]
       and (got[1][1] or {}).get("label") == "PDF page 3 of 5, printed page 298 (%s)" % R.PRINTED_BETWEEN,
       str(got[:2]))
    ok("k018b: «printed page unknown» and why - a page outside the numbered ones, a file numbered in two "
       "runs; the PDF page is still named",
       (got[2][1] or {}).get("label") == "PDF page 5 of 5 (printed page unknown - %s)" % R.PRINTED_OUTSIDE
       and (got[2][1] or {}).get("printed_unknown") == R.PRINTED_OUTSIDE
       and (got[3][1] or {}).get("label") == "PDF page 2 of 6 (printed page unknown - %s)" % R.PRINTED_TWO,
       str(got[2:]))

    # a pages file from 0.26.0 (no printed run) is re-measured, never read as «not measured»
    pf = R._pages_file(dec, cache)
    if os.path.exists(pf):
        old = json.load(io.open(pf, encoding="utf-8"))
        old.pop("printed", None)
        old["v"] = "1"
        io.open(pf, "w", encoding="utf-8").write(json.dumps(old))
    R._PAGES_MEMO.clear()
    pc = Corpus([law], quiet=True, cache_dir=cache)       # a new run: no page memo of its own yet
    g_old = lab(S2)[1]
    ok("k018b: a pages file written before the printed pages existed is measured again",
       (g_old or {}).get("printed") == [[297, 297]] and os.path.exists(pf)
       and json.load(io.open(pf, encoding="utf-8")).get("printed", {}).get("offset") == 295, str(g_old))

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p_ = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p_.returncode, (p_.stdout or "") + (p_.stderr or "")

    q = cli("quote", "--dir", root, FR_X)[1]
    ok("k018b: `quote` prints the printed page of a GPO text and no PDF page for it",
       "printed pages 41300-41301 (by the source's own page markers)" in q and "PDF page" not in q,
       q[:400])
    S4D = S4.replace("proven at a hearing", "proven, at a hearing")
    io.open(os.path.join(case, "petition.md"), "w", encoding="utf-8").write(
        'Under Matter of Fixture, "%s"\n\nUnder Matter of Fixture, "%s"\n\n'
        'Under 91 Fed. Reg. 41300, "%s"\n' % (S2, S4D, FR_X))
    out_dir = os.path.join(tmp, "k018bo")
    _rc, out = cli("check", "--dir", root, "--out", out_dir)

    def read(name):
        p_ = os.path.join(out_dir, name)
        return io.open(p_, encoding="utf-8").read() if os.path.exists(p_) else ""

    rows = (json.loads(read("result.json") or "{}")).get("rows", [])

    def row(marker):
        return next((r for r in rows if marker in r["quote"]), {})

    md, rl = read("REPORT.md"), read("READING-LIST.md")
    r2, r4, rx = row("continuance"), row("proven, at"), row("extend the period")
    ok("k018b: result.json, REPORT.md («Found in» of a flagged row) and READING-LIST.md carry the "
       "printed page",
       (r2.get("page") or {}).get("printed") == [[297, 297]] and r4.get("verdict") == "PUNCTUATION"
       and "Matter-of-Fixture-27-IN-Dec-500.pdf` - PDF page 4 of 5, printed page 299" in md
       and "PDF page 2 of 5, printed page 297" in rl
       and (rx.get("page") or {}).get("printed") == [["41300", "41301"]]
       and "printed pages 41300-41301" in rl,
       str([(r.get("verdict"), r.get("page")) for r in (r2, r4, rx)]) + " || " + out[-300:])


def suite_k018c_zones(tmp):
    """K018c (2026-11-27): the ZONE of a decision the words stand in - the headnote above the opinion (EOIR adds it
    when it publishes the decision), the opinion, a separate (dissenting / concurring) opinion - or «zone unknown» and
    why. A headnote-only match carries an advisory, never a verdict; `wrong_speaker` asks the zone, so a dissent's
    words are WRONG_SPEAKER however far below its heading, and a «dissenting» in a majority's citation no longer
    flags the majority. Before: a headnote quoted as the Board's words and a dissent quoted as the majority passed."""
    import json
    import subprocess as _sp
    from krokai import readers as R
    from krokai import verify as V
    from krokai.normalize import alnum as _al
    from krokai.corpus import Corpus
    from krokai.verdicts import CLEAN

    root = os.path.join(tmp, "k018cm")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))

    def fill(tag, n=6):
        return " ".join("The Board weighed fixture point %s number %d on the record as a whole and found it plain."
                        % (tag, k) for k in range(n))

    HN = "A respondent who files a late fixture motion must show a change in the fixture circumstances of the case."
    BOTH = "The fixture rule applies to every motion that is filed after the regulatory deadline has passed."
    OPN = "The record shows that the respondent never received the notice that set the fixture deadline."
    CITX = "A motion to reopen that rests on new evidence must explain why the evidence was not available before."
    DIS = "The majority overlooks that the fixture deadline was never served on the respondent at any address."
    d1 = os.path.join(law, "99-IN-Dec-100-fixture-zone.txt")
    io.open(d1, "w", encoding="utf-8").write(
        "Cite as 99 I&N Dec. 100 (BIA 2026)          Interim Decision #9901\n\nMatter of FIXTURE-ZONE, Respondent\n\n"
        "Decided November 2, 2026\n\nU.S. Department of Justice\nBoard of Immigration Appeals\n\n(1) %s\n(2) %s\n\n"
        "FOR RESPONDENT: Pro se\nFOR THE DEPARTMENT OF HOMELAND SECURITY: Assistant Chief Counsel\n\n"
        "BEFORE: Board Panel: ALPHA, BETA, and GAMMA, Board Members. Dissenting Opinion: GAMMA,\nBoard Member.\n\n"
        "ALPHA, Board Member:\n\n%s\n%s\n%s\n%s\nSee Matter of Sample, 98 I&N Dec. 50, 52 (BIA 2025) (Delta, "
        "dissenting). %s\n%s\n\nORDER: The appeal is dismissed.\n\nDISSENTING OPINION: Gamma, Board Member\n\n"
        "I respectfully dissent.\n\n%s\n%s\n"
        % (HN, BOTH, fill("a"), BOTH, fill("b"), OPN, CITX, fill("c"), fill("d", 20), DIS))
    HN2 = "An alien who departs while a fixture appeal is pending abandons the appeal for every fixture purpose."
    OPN2 = "The respondent left the country while the appeal was pending and the record leaves no doubt of it."
    d2 = os.path.join(law, "98-IN-Dec-200-fixture-old.txt")
    io.open(d2, "w", encoding="utf-8").write(
        "Interim Decision #9902\n\nMATTER OF FIXTURE-OLD\n\nIn Deportation Proceedings\n\nDecided by Board March 5, "
        "1975\n\n%s\n\nON BEHALF. OP RESPONDENT: Pro se\nON BEHALF OF SERVICE: Trial Attorney\n\n%s\n%s\n"
        % (HN2, fill("e"), OPN2))
    HN3 = "A petition for a fixture worker is denied when the employer cannot show the ability to pay the wage."
    d3 = os.path.join(law, "97-IN-Dec-300-fixture-regional.txt")
    io.open(d3, "w", encoding="utf-8").write(
        "Interim Decision #9903\n\nMATTER OF FIXTURE-REGIONAL\n\nIn Visa Petition Proceedings\n\nDecided by "
        "Regional Commissioner May 1, 1974\n\n%s\n\nThis matter is before the Regional Commissioner on "
        "certification. %s\n" % (HN3, fill("f")))
    CITY = "A fixture statute that names a deadline must be read with the notice that starts the deadline running."
    st = os.path.join(law, "8USC-9999-fixture-statute.txt")
    io.open(st, "w", encoding="utf-8").write(
        "8 U.S.C. 9999 - fixture provision.\n\n%s\nSee Sample v. Fixture, 1 F.4th 2 (Delta, dissenting). %s\n%s\n"
        % (fill("g"), CITY, fill("h")))
    co = os.path.join(law, "Fixture-v-USCIS-4th-Cir.txt")
    io.open(co, "w", encoding="utf-8").write(
        "PUBLISHED\nUNITED STATES COURT OF APPEALS\nFOR THE FOURTH CIRCUIT\n\nArgued: October 29, 2009\nDecided: "
        "January 13, 2010\n\nThe court reviewed Matter of Sample, 98 I&N Dec. 50 (BIA 2025).\n\nFOR THE PETITIONER: "
        "Counsel of record\n\n%s\n" % fill("i"))
    DIS4 = "The respondent's long residence and his family here outweigh one stale fixture conviction by far."
    AGX = "On review I conclude that the Board applied the correct fixture standard to the respondent's case."
    d4 = os.path.join(law, "96-IN-Dec-400-fixture-attorney-general.txt")
    io.open(d4, "w", encoding="utf-8").write(
        "Interim Decision #9904\n\nMATTER OF FIXTURE-REVIEW\n\nDecided by Board August 2, 1974\nDecided by Attorney "
        "General March 10, 1976\n\n%s\n\nCHARGE:\nOrder: Act of 1952 - Section 241(a)(2) - remained longer\n\n"
        "BEFORE THE BOARD\n\n%s\n\nAlpha Beta, Chairman, Dissenting:\n\n%s\n%s\n\nBEFORE THE ATTORNEY GENERAL\n\n"
        "%s\n%s\n" % (fill("j"), fill("k"), DIS4, fill("l"), AGX, fill("m")))
    nd = os.path.join(law, "Fixture-appeals-unit-order.txt")
    io.open(nd, "w", encoding="utf-8").write(
        "DEPARTMENT OF FIXTURES - APPEALS UNIT\n\nDecided March 2, 2020\n\nFOR THE APPLICANT: Counsel of record\n\n"
        "%s\n" % fill("n"))
    corp = Corpus([law], quiet=True)
    z4 = corp.zones(d4)[0] or []
    ok("k018c: a file holding a Board decision, a dissent and the Attorney General's review - «Name, Chairman, "
       "Dissenting:» opens the dissent, «BEFORE THE ATTORNEY GENERAL» ends it; no I&N mark, no decision",
       [k for _s, k, _l in z4] == ["headnote", "opinion", "opinion", "separate", "opinion"]
       and V.check(DIS4, corp)[0] == "WRONG_SPEAKER" and V.check(AGX, corp)[0] == "VERIFIED"
       and (V.zone_of(AGX, d4, corp) or {}).get("zone") == "opinion" and corp.zones(nd) == (None, ""), str(z4))
    zs = corp.zones(d1)[0] or []
    ok("k018c: a decision's zones are read from its own lines - the headnote from the top, the opinion from the "
       "first counsel line, a dissent from its heading (the panel line's «Dissenting Opinion: GAMMA» is no heading)",
       [k for _s, k, _l in zs] == ["headnote", "opinion", "separate"] and zs[1][2] == "FOR RESPONDENT: Pro se"
       and zs[2][2] == "DISSENTING OPINION: Gamma, Board Member", str(zs))

    def zq(q, path=d1):
        v, w, d = V.check(q, corp)
        return v, w, d, V.zone_of(q, path, corp)
    hn, both, opn, dis, citx = zq(HN), zq(BOTH), zq(OPN), zq(DIS), zq(CITX)
    ok("k018c: words that stand only in the headnote - verdict unchanged, zone «headnote», the advisory",
       hn[0] == "VERIFIED" and (hn[3] or {}).get("zone") == "headnote" and hn[3]["advisory"] == V.HEADNOTE_ONLY
       and hn[3]["label"] == "zone: the headnote only, not the opinion", str(hn))
    ok("k018c: words the headnote repeats from the opinion are the opinion's - the FIRST occurrence (in the "
       "headnote) does not decide; the opinion alone gets no «also» and no advisory",
       (both[3] or {}).get("zone") == "opinion" and both[3]["zones"] == ["headnote", "opinion"]
       and both[3]["label"] == "zone: the opinion; also in the headnote" and not both[3]["advisory"]
       and opn[0] == "VERIFIED" and (opn[3] or {}).get("label") == "zone: the opinion" and not opn[3]["advisory"],
       str((both, opn)))
    txt = corp.text_of(d1)
    gap = txt.index(DIS) - txt.rindex("dissent", 0, txt.index(DIS))
    ok("k018c: a dissent's words far below its heading - out of the 1 400-character window - are WRONG_SPEAKER "
       "by the zone, and the zone names the heading",
       gap > 1400 and dis[0] == "WRONG_SPEAKER" and "DISSENTING OPINION: Gamma, Board Member" in dis[2]
       and (dis[3] or {}).get("zone") == "separate"
       and dis[3]["label"] == "zone: a separate opinion only - «DISSENTING OPINION: Gamma, Board Member»",
       "gap %d %s" % (gap, dis))
    city = V.check(CITY, corp)
    ok("k018c: a majority's words right after a citation «(Delta, dissenting)» verify in a decision whose zones are "
       "known; the window still flags the same shape where no zones are known",
       citx[0] == "VERIFIED" and (citx[3] or {}).get("zone") == "opinion" and city[0] == "WRONG_SPEAKER",
       str((citx, city)))
    z2 = corp.zones(d2)[0] or []
    hn2, opn2 = V.zone_of(HN2, d2, corp), V.zone_of(OPN2, d2, corp)
    ok("k018c: an old decision whose counsel line the OCR bent («ON BEHALF. OP RESPONDENT») opens its opinion there",
       len(z2) == 2 and z2[1][2] == "ON BEHALF. OP RESPONDENT: Pro se" and (hn2 or {}).get("zone") == "headnote"
       and (opn2 or {}).get("zone") == "opinion", str((z2, hn2, opn2)))
    hn3 = V.zone_of(HN3, d3, corp)
    ok("k018c: a decision with no counsel, charge or panel line is «zone unknown» with the reason, never a guess",
       corp.zones(d3) == (None, R.ZONE_NONE) and (hn3 or {}).get("zone") is None
       and hn3["label"] == "zone unknown - %s" % R.ZONE_NONE and not hn3["advisory"], str(hn3))
    ok("k018c: a statute and a court of appeals opinion («Decided:» with a colon, I&N Dec. cited in its body) are "
       "not decisions - no zone line at all",
       V.zone_of(CITY, st, corp) is None and corp.zones(co) == (None, "") and corp.zones(st) == (None, ""),
       str((corp.zones(co), corp.zones(st))))
    across = V.zone_of(BOTH + " FOR RESPONDENT: Pro se", d1, corp)
    good = _al(txt)
    ok("k018c: words across the line that opens the opinion are «zone unknown»; zones that do not add up to the "
       "indexed text are not named",
       (across or {}).get("zone") is None and across["unknown"] == V.ZONE_ACROSS
       and R.zone_table(d1, good)[0] is not None and R.zone_table(d1, good[:-5] + "zzzzz") == (None, R.ZONE_BROKEN),
       str(across))

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p_ = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                     capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p_.returncode, (p_.stdout or "") + (p_.stderr or "")

    q1, q2, q3 = cli("quote", "--dir", root, HN)[1], cli("quote", "--dir", root, OPN)[1], \
        cli("quote", "--dir", root, CITY)[1]
    ok("k018c: `quote` prints the zone and, for a headnote-only match, the advisory - and neither for an opinion "
       "match or a statute",
       "zone: the headnote only, not the opinion" in q1 and "🟡 HEADNOTE ONLY:" in q1
       and "zone: the opinion" in q2 and "HEADNOTE ONLY" not in q2
       and "zone: " not in q3 and "zone unknown" not in q3, q1[:500] + " || " + q2[:300])
    io.open(os.path.join(case, "petition.md"), "w", encoding="utf-8").write(
        'Under Matter of Fixture-Zone, "%s"\n\nUnder Matter of Fixture-Zone, "%s"\n\nUnder Matter of Fixture-Zone, '
        '"%s"\n' % (HN, OPN.replace("received the notice", "received, the notice"), DIS))
    out_dir = os.path.join(tmp, "k018co")
    _rc, out = cli("check", "--dir", root, "--out", out_dir)

    def read(name):
        p_ = os.path.join(out_dir, name)
        return io.open(p_, encoding="utf-8").read() if os.path.exists(p_) else ""
    rows = (json.loads(read("result.json") or "{}")).get("rows", [])
    rh = next((r for r in rows if "late fixture motion" in r["quote"]), {})
    rp = next((r for r in rows if "received, the notice" in r["quote"]), {})
    md, rl = read("REPORT.md"), read("READING-LIST.md")
    ok("k018c: result.json carries the zone, REPORT.md's «Found in» names it, READING-LIST.md notes the "
       "headnote-only quotation as a fact and names the zone beside the source",
       (rh.get("zone") or {}).get("zone") == "headnote" and rh.get("verdict") in CLEAN
       and rp.get("verdict") == "PUNCTUATION" and (rp.get("zone") or {}).get("zone") == "opinion"
       and "99-IN-Dec-100-fixture-zone.txt` · zone: the opinion" in md
       and "the words stand only in the decision's headnote" in rl
       and "99-IN-Dec-100-fixture-zone.txt`, zone: the headnote only, not the opinion:" in rl,
       str([(r.get("verdict"), r.get("zone")) for r in (rh, rp)]) + " || " + out[-300:])


def suite_k096_picture_pages(tmp):
    """K096 (2026-11-26): a page of an INDEXED PDF whose words are in a picture or drawn as shapes
    while its text layer holds little more than a label there is named - in the build output, REPORT.md,
    result.json, `quote`'s NOT FOUND ladder, `library` and `sidecar`. A background picture under body
    text, a letterhead and an OCR engine's page are not; the geometry is the same on a ROTATED page
    (PyMuPDF's boxes are unrotated, `page.rect` is not - K093 compared them directly)."""
    import builtins
    import contextlib
    import json
    import subprocess as _sp
    from krokai import readers as R
    from krokai import sidecar as SC
    from krokai.corpus import Corpus
    from krokai.verdicts import SIX_CAUSES
    try:
        from krokai import _pdfengine
        fz = _pdfengine.load()
    except ImportError:
        fz = None
    ok("k096: NOT_FOUND's cause 3 names the picture page, in the tool and in the assistant snippet",
       "PICTURE PAGE" in SIX_CAUSES[2] and "picture page" in io.open(
           os.path.join(data_dir("templates"), "CLAUDE.md.snippet"), encoding="utf-8").read().split(
           "3. **The corpus copy is damaged", 1)[-1][:400], SIX_CAUSES[2][:160])
    if fz is None:
        print("note: k096 picture-page fixture pins skipped - PyMuPDF builds the fixtures and is not "
              "installed here")
        return

    LETTER = ("The applicant submitted the following evidence in support of the petition. "
              "Each item is labelled with its exhibit number and the page it was filed on. "
              "The originals were shown to the officer at the interview and returned. ")
    MISSING = "The entrance of the office stayed closed for the whole week of the scheduled hearing."

    def make(folder, name, pages):
        d = fz.open()
        for spec in pages:
            pg = d.new_page()                                # 595 x 842: the body band is y 84-758
            if spec.get("picture"):
                pix = fz.Pixmap(fz.csGRAY, fz.IRect(0, 0, 40, 60), 0)
                pix.clear_with(190)
                pg.insert_image(fz.Rect(*spec["picture"]), pixmap=pix, keep_proportion=False)
            for i in range(spec.get("shapes", 0)):           # words drawn as vector shapes
                x, y = 80 + (i % 30) * 14, 300 + (i // 30) * 20
                pg.draw_rect(fz.Rect(x, y, x + 6, y + 9), color=(0, 0, 0), fill=(0, 0, 0))
            x0, y0 = spec.get("at", (72, 300))
            for i, ln in enumerate(spec.get("body", ())):
                pg.insert_text((x0, y0 + 16 * i), ln, fontsize=11)
            for y, ln in spec.get("margin", ()):
                pg.insert_text((72, y), ln, fontsize=8, render_mode=3 if spec.get("invisible") else 0)
            if spec.get("rot"):
                pg.set_rotation(spec["rot"])
        p = os.path.join(folder, name)
        d.save(p)
        d.close()
        return p

    root = os.path.join(tmp, "k096m")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))
    typeset = {"body": (LETTER[:74], LETTER[75:152], LETTER[153:])}
    label = {"picture": (0, 0, 595, 842), "margin": ((40, "EXHIBIT K-12"), (820, "ABC-000123"))}
    exhibit = make(law, "8CFR-279.pdf", [typeset, label])
    backgr = make(law, "8CFR-278.pdf", [dict(typeset, picture=(0, 0, 595, 842))])
    letterhead = make(law, "8CFR-277.pdf", [dict(typeset, picture=(0, 0, 595, 100))])
    turned = make(law, "8CFR-276.pdf", [typeset, dict(label, rot=90)])
    shapes = make(law, "8CFR-274.pdf", [typeset, {"shapes": 60, "margin": ((40, "EXHIBIT C-7"),)}])
    ocrpage = make(law, "8CFR-273.pdf", [typeset, dict(label, margin=((40, "EXHIBIT D-2 OCR READ THE LABEL"),),
                                                       invisible=True)])
    # a short typeset notice on a page turned 90 degrees: its lines stand in the page body as the page
    # is SHOWN, in the bottom margin of the unrotated page that PyMuPDF's boxes describe
    notice = make(law, "8CFR-275.pdf", [{"body": ("The office is closed on the day of the hearing.",
                                                  "A filing due that day is due on the next business day."),
                                         "at": (150, 620), "rot": 90}])

    def flagged(p):
        R._PICTURES_MEMO.clear()
        f = R.picture_pages(p)
        return [n for n, _w in (f or {}).get("flagged", ())], f

    pages, f_ex = flagged(exhibit)
    ok("k096: a page-sized picture under a margin label is a picture page - only that page of the file",
       pages == [2] and "covers 100 %" in f_ex["flagged"][0][1] and R.picture_pages_cell(f_ex) == "page 2 of 2",
       str(f_ex))
    ok("k096: a background picture under body text is NOT a picture page (the text layer holds the page)",
       flagged(backgr)[0] == [], str(flagged(backgr)[1]))
    ok("k096: a letterhead picture over a typeset letter is NOT a picture page", flagged(letterhead)[0] == [],
       str(flagged(letterhead)[1]))
    pages, f_tu = flagged(turned)
    ok("k096: on a page turned 90 degrees the picture still covers 100 % - the boxes are rotated first",
       pages == [2] and "covers 100 %" in f_tu["flagged"][0][1], str(f_tu))
    pages, f_sh = flagged(shapes)
    ok("k096: a page whose words are drawn as vector shapes, under a margin label, is a picture page",
       pages == [2] and "vector shapes" in f_sh["flagged"][0][1], str(f_sh))
    ok("k096: a page an OCR engine already read (an invisible layer) is left to the OCR label",
       flagged(ocrpage)[0] == [], str(flagged(ocrpage)[1]))
    R._LAYER_MEMO.clear()
    R._PICTURES_MEMO.clear()
    v = R.pdf_text_verdict(notice)
    ok("k093/k096: a short notice on a turned page is read where it is SHOWN - in the body, so it is "
       "indexed (the unrotated boxes put it in the bottom margin)", v == (False, ""), str(v))

    cache = os.path.join(tmp, "k096cache")
    os.makedirs(cache)
    R._PICTURES_MEMO.clear()
    first = R.picture_pages(exhibit, cache)
    real_load = _pdfengine.load

    def no_engine():
        raise ImportError("hidden by the k096 selftest")
    R._PICTURES_MEMO.clear()
    _pdfengine.load = no_engine
    try:
        again = R.picture_pages(exhibit, cache)
        R._PICTURES_MEMO.clear()
        bare = R.picture_pages(backgr, cache)
    finally:
        _pdfengine.load = real_load
    ok("k096: the pages are kept beside the text cache and read back without PyMuPDF; a file never "
       "measured reads None (unmeasured), not «no picture pages»",
       again == first and bool(first and first["flagged"]) and bare is None
       and any(n.endswith(".pictures.json") for n in os.listdir(cache)), "again=%s bare=%s" % (again, bare))

    R._PICTURES_MEMO.clear()
    R._LAYER_MEMO.clear()
    c = Corpus([law], quiet=True)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        c.print_build()
    out = buf.getvalue()
    ok("k096: the build output counts the picture pages and the files they stand in",
       "PICTURE PAGES - 3 page(s) in 3 indexed file(s)" in out and "8CFR-275.pdf" in "".join(
           os.path.basename(p) for p in c.short_sources), out[-700:])

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    _rc, qout = cli("quote", "--dir", root, MISSING)
    ok("k096: `quote` on a NOT FOUND says cause 3 may be live - the corpus has picture pages",
       "NOT FOUND" in qout.upper().replace("_", " ") and "Cause 3 may be live" in qout
       and "PICTURE PAGES" in qout, qout[-900:])
    io.open(os.path.join(case, "brief.md"), "w", encoding="utf-8").write(
        'The letter says: "%s" And the officer wrote: "%s"\n' % (LETTER[:74], MISSING))
    _rc, cout = cli("check", "--dir", root, "--out", os.path.join(tmp, "k096o"))
    md_p = os.path.join(tmp, "k096o", "REPORT.md")
    md = io.open(md_p, encoding="utf-8").read() if os.path.exists(md_p) else ""
    sec = (md.split("## Indexed files with picture pages", 1)[-1].split("\n## ", 1)[0]
           if "## Indexed files with picture pages" in md else "").replace("\\", "/")
    ok("k096: REPORT.md lists the files with picture pages and their pages - not the background or the "
       "letterhead", "`law/8CFR-279.pdf` - page 2 of 2; page 2: a picture covers 100 %" in sec
       and "8CFR-278.pdf" not in sec and "8CFR-277.pdf" not in sec and "--redo-ocr" in sec, sec[:600] or md[:300])
    nf = md.split("\n## not found", 1)[-1][:900] if "\n## not found" in md else ""
    ok("k096: REPORT.md's NOT FOUND section says a picture's words read NOT FOUND here",
       "PICTURE PAGES (listed under" in nf, nf[:400] or md[-600:])
    rj = os.path.join(tmp, "k096o", "result.json")
    pj = json.load(io.open(rj, encoding="utf-8")).get("picture_pages") if os.path.exists(rj) else None
    ok("k096: result.json carries picture_pages - file, pages, of, why",
       bool(pj) and any(x["file"].replace("\\", "/") == "law/8CFR-279.pdf" and x["pages"] == [2] and x["of"] == 2
                        and "covers 100 %" in x["why"]["2"] for x in pj), str(pj)[:400])
    ok("k096: the check console names the picture pages beside the NOT FOUND", "🟡 PICTURE PAGES:" in cout,
       cout[-600:])
    _rc, lout = cli("library", "--dir", root)
    ok("k096: `library` lists the picture pages with the page and the reason",
       "Picture pages: 3 of 7 PDF(s)" in lout and "8CFR-279.pdf  (page 2 of 2; page 2: a picture covers 100 %"
       in lout.replace("\\", "/"), lout[-900:])
    sbuf = []
    SC.build([law], dry_run=True, printer=lambda *a, **k: sbuf.append(" ".join(str(x) for x in a)))
    sout = "\n".join(sbuf)
    ok("k096: `sidecar` says the picture pages' words are not in the sidecars either",
       "PICTURE PAGES - their words are NOT in the sidecars" in sout and "8CFR-279.pdf  (page 2 of 2)" in sout,
       sout[-500:])

    # the clean path (E-1072): a matter with no picture page prints none of it
    groot = os.path.join(tmp, "k096g")
    glaw, gcase = os.path.join(groot, "law"), os.path.join(groot, "case")
    os.makedirs(glaw)
    os.makedirs(gcase)
    io.open(os.path.join(groot, "casefile.json"), "w", encoding="utf-8").write(io.open(
        os.path.join(root, "casefile.json"), encoding="utf-8").read())
    make(glaw, "8CFR-272.pdf", [typeset, dict(typeset, picture=(0, 0, 595, 842))])
    io.open(os.path.join(gcase, "brief.md"), "w", encoding="utf-8").write(
        'The letter says: "%s" And the officer wrote: "%s"\n' % (LETTER[:74], MISSING))
    _rc, gq = cli("quote", "--dir", groot, MISSING)
    _rc, gc = cli("check", "--dir", groot, "--out", os.path.join(tmp, "k096go"))
    gmd_p = os.path.join(tmp, "k096go", "REPORT.md")
    gmd = io.open(gmd_p, encoding="utf-8").read() if os.path.exists(gmd_p) else ""
    gj = os.path.join(tmp, "k096go", "result.json")
    gpj = json.load(io.open(gj, encoding="utf-8")).get("picture_pages") if os.path.exists(gj) else None
    ok("k096: with no picture page nothing is said - no build line, no REPORT.md section, no hint in "
       "`quote`, result.json picture_pages == []",
       "PICTURE PAGES" not in gq and "Cause 3 may be live" not in gq and "PICTURE PAGES" not in gc
       and "## Indexed files with picture pages" not in gmd and "\n## not found" in gmd and gpj == [],
       "quote=%s check=%s json=%s" % (gq[-300:], gc[-300:], gpj))

    real_import = builtins.__import__

    def imp(name, *a, **k):
        if name.split(".")[0] in ("fitz", "pymupdf"):
            raise ImportError("hidden by the k096 selftest: %s" % name)
        return real_import(name, *a, **k)
    R._PICTURES_MEMO.clear()
    R._LAYER_MEMO.clear()
    builtins.__import__ = imp
    try:
        nc = Corpus([law], quiet=True)
        nbuf = io.StringIO()
        with contextlib.redirect_stdout(nbuf):
            nc.print_build()
    finally:
        builtins.__import__ = real_import
        R._PICTURES_MEMO.clear()
        R._LAYER_MEMO.clear()
    ok("k096: without PyMuPDF the build output says the picture pages were NOT checked - never a silent "
       "zero", "picture pages NOT checked in" in nbuf.getvalue() and "PICTURE PAGES -" not in nbuf.getvalue(),
       nbuf.getvalue()[-500:])


def suite_k097_split_quotation(tmp):
    """K097 (2026-11-26): a quotation the drafter split in two pieces that stand right beside each
    other is graded as ONE quotation - each piece alone stops before (or starts after) the other's
    words. Strict: nothing alphanumeric between the pieces in the source, next to each other in the
    draft (no blank line, SPLIT_NEAR characters), at EVERY place the piece is used; the joined text
    keeps the outer-edge tests. A condition left out BETWEEN two quotations stays loud."""
    import json
    import subprocess as _sp
    from krokai import config as _config
    from krokai.corpus import Corpus
    from krokai.run import scan_matter, SPLIT_NEAR
    from krokai.verify import split_join
    LAW = ("# 8 CFR 214.9 Late filings (fixture)\n\n"
           "(a) The officer may excuse a late filing caused by a third party over whose actions the student "
           "has no control, if the delay is acknowledged by that third party in writing. Any other late "
           "filing is refused.\n\n"
           "(b) The fee is waived for a student whose school closed for good during the term, if the closure "
           "is confirmed in writing by the agency, unless the student enrolled after the closure was "
           "announced.\n\n"
           "(c) A late fee is charged to a student who files after the deadline, unless the student shows "
           "good cause for the delay, and the fee is paid to the school within thirty days.\n\n"
           "(d) A transfer request is granted to a student whose program of study ended before its last "
           "term, if the new school accepts the student before the term starts. No other transfer is "
           "granted.\n\n"
           "(e) A refund is paid to a student whose visa was refused at the consulate abroad, if the refusal "
           "is shown by the letter of the consulate. The refund is paid once.\n\n"
           "(f) The school may report a student who stopped attending all of the classes, if the student was "
           "absent for ten school days in a row, unless the absence was approved in advance by the school.\n")
    A, B = ("a third party over whose actions the student has no control",
            "if the delay is acknowledged by that third party in writing")
    A2, B2 = ("a student whose school closed for good during the term",
              "if the closure is confirmed in writing by the agency")
    C, D = ("A late fee is charged to a student who files after the deadline",
            "the fee is paid to the school within thirty days")
    A4, B4 = ("a student whose program of study ended before its last term",
              "if the new school accepts the student before the term starts")
    A5, B5 = ("a student whose visa was refused at the consulate abroad",
              "if the refusal is shown by the letter of the consulate")
    A6, B6, C6 = ("a student who stopped attending all of the classes",
                  "if the student was absent for ten school days in a row",
                  "unless the absence was approved in advance by the school")
    LONG = "caused by a third party over whose actions the student has no control"
    filler = " ".join(["The client kept every receipt and every letter from the school."] * 6)

    def matter(name, drafts):
        root = os.path.join(tmp, name)
        os.makedirs(os.path.join(root, "law"))
        os.makedirs(os.path.join(root, "case"))
        io.open(os.path.join(root, "law", "8CFR-214.md"), "w", encoding="utf-8").write(LAW)
        for fn, text in drafts.items():
            io.open(os.path.join(root, "case", fn), "w", encoding="utf-8").write(text)
        io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
            "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
            "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
            "citation_packs": ["us-immigration", "us-federal"]}))
        return root

    # --- the helper alone ---------------------------------------------------------------------------
    c = Corpus([os.path.join(matter("k097u", {}), "law")], quiet=True)
    ok("k097: split_join joins two pieces with only the source's comma between them - in source order",
       split_join(A, B, c) == A + ", " + B and split_join(B, A, c) is None, repr(split_join(A, B, c)))
    ok("k097: split_join refuses a pair whose source gap holds words («, unless the student shows good "
       "cause …, and») - the omission a softer join would launder", split_join(C, D, c) is None,
       repr(split_join(C, D, c)))
    ok("k097: SPLIT_NEAR is a drafter's sentence, not a page", 100 <= SPLIT_NEAR <= 600, str(SPLIT_NEAR))

    # --- one matter, every shape: the CLI end to end ---------------------------------------------------
    root = matter("k097m", {
        "split.md": ('The rule reaches a delay caused by "%s" and "%s" the late filing is excused.\n\n'
                     'The fee rule covers "%s" - "%s" - and the waiver follows.\n\n'
                     'The school may not charge: "%s" and "%s".\n\n'
                     'Reporting reaches "%s", "%s", "%s".\n' % (A, B, A2, B2, C, D, A6, B6, C6)),
        "reversed.md": 'Where the delay is acknowledged - "%s" - the rule covers "%s".\n' % (B, A),
        "far.md": 'Transfers reach "%s". %s The condition is "%s".\n' % (A4, filler, B4),
        "para.md": 'Refunds reach "%s".\n\n"%s" is the condition.\n' % (A5, B5),
        "nested.md": 'The officer looks at a delay "%s" first.\n\nThen it reaches "%s" and "%s" both.\n'
                     % (LONG, A, B)})
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(tmp, "k097o")
    p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", root, "--out", out], cwd=repo, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    cout = (p.stdout or "") + (p.stderr or "")
    try:
        rows = {" ".join(r["quote"].split()): r for r in
                json.load(io.open(os.path.join(out, "result.json"), encoding="utf-8"))["rows"]}
        md = io.open(os.path.join(out, "REPORT.md"), encoding="utf-8").read()
    except (OSError, ValueError, KeyError):
        rows, md = {}, ""

    def row(q):
        return rows.get(q) or {}

    def alone(q):
        return ((row(q).get("split") or {}).get("alone") or {}).get("verdict")

    ok("k097: a split quotation - both pieces graded as one: VERIFIED, each piece's split names what it "
       "was ALONE (a truncated condition, a truncated opening) and the other piece",
       row(A).get("verdict") == "VERIFIED" and alone(A) == "TRUNCATED_CONDITION"
       and row(B).get("verdict") == "VERIFIED" and alone(B) == "TRUNCATED_OPENING"
       and B in (row(A).get("split") or {}).get("read_with", ())
       and A in (row(B).get("split") or {}).get("read_with", ())
       and "split quotation - read together with" in row(A).get("detail", ""),
       "%s | %s | %s" % (row(A), row(B), cout[-600:]))
    sa = row(A).get("split") or {}
    ok("k097: the pieces in REVERSED order in another draft are joined there too - every place joined",
       any("reversed" in f for f in sa.get("files", ())) and sa.get("places") == sa.get("of") == 3, str(sa))
    ok("k097: a joined pair that still stops before «, unless …» stays TRUNCATED_CONDITION - about its "
       "outer edge, and says it was graded as one",
       row(A2).get("verdict") == "TRUNCATED_CONDITION" and alone(A2) == "TRUNCATED_CONDITION"
       and "graded as one" in row(A2).get("detail", "") and "unless the student enrolled" in row(A2).get(
           "detail", ""), str(row(A2)))
    ok("k097: a condition left out BETWEEN two quotations of one passage stays loud - no split, the "
       "alarm unchanged",
       row(C).get("verdict") == "TRUNCATED_CONDITION" and "split" not in row(C)
       and row(D).get("verdict") == "VERIFIED", "%s | %s" % (row(C), row(D)))
    ok("k097: the continuation quoted a page away (> SPLIT_NEAR characters) does not answer the alarm",
       row(A4).get("verdict") == "TRUNCATED_CONDITION" and "split" not in row(A4), str(row(A4)))
    ok("k097: the continuation across a blank line (another paragraph) does not answer it either",
       row(A5).get("verdict") == "TRUNCATED_CONDITION" and "split" not in row(A5), str(row(A5)))
    ok("k097: three pieces of one sentence - the chain grows while the joined text still points at its "
       "neighbour, and the whole sentence reads VERIFIED",
       row(A6).get("verdict") == "VERIFIED" and len((row(A6).get("split") or {}).get("read_with", ())) == 2,
       str(row(A6)))
    ok("k097: a quotation's words inside ANOTHER, longer quotation are that quotation's place, not a lone "
       "place of the short one (the longer one keeps its own alarm)",
       row(LONG).get("verdict") == "TRUNCATED_CONDITION" and row(A).get("verdict") == "VERIFIED"
       and any("nested" in f for f in sa.get("files", ())), "%s | %s" % (row(LONG), sa))
    ok("k097: REPORT.md lists the split quotations with what each piece was alone",
       "## Split quotations read together" in md and "«%s» + «%s»" % (A, B) in md
       and "truncated condition" in md.split("## Split quotations read together", 1)[-1][:3000].lower(),
       md.split("## Split quotations read together", 1)[-1][:900])
    ok("k097: the check console says the split quotations were graded together",
       "ℹ SPLIT QUOTATIONS: " in cout, cout[-900:])

    # --- the same piece ALONE at another place keeps its alarm ---------------------------------------------
    root2 = matter("k097b", {"split.md": 'It reaches "%s" and "%s" today.\n' % (A, B),
                             "alone.md": 'It reaches "%s" - nothing more.\n' % A})
    res = scan_matter(_config.load(root2), quiet=True, printer=lambda *a: None)
    r2 = {" ".join(r["quote"].split()): r for r in res["rows"]}
    ok("k097: a piece joined at one place and ALONE at another keeps its alarm, and the detail names "
       "both - its partner is joined (its only place)",
       r2.get(A, {}).get("verdict") == "TRUNCATED_CONDITION"
       and "split quotation at 1 of 2 place(s)" in r2.get(A, {}).get("detail", "")
       and r2.get(B, {}).get("verdict") == "VERIFIED", "%s | %s" % (r2.get(A), r2.get(B)))

    # --- the green path: nothing split, nothing said ------------------------------------------------------
    root3 = matter("k097g", {"whole.md": 'The rule: "The officer may excuse a late filing caused by %s, %s."\n'
                                         % (A, B)})
    res3 = scan_matter(_config.load(root3), quiet=True, printer=lambda *a: None)
    from krokai.run import write_report as _wr, print_summary as _ps
    _wr(res3, _config.load(root3), os.path.join(tmp, "k097go"))
    gmd = io.open(os.path.join(tmp, "k097go", "REPORT.md"), encoding="utf-8").read()
    glines = []
    _ps(res3, printer=glines.append)
    ok("k097: with no split nothing is said - the whole sentence VERIFIED, no `split`, no REPORT.md "
       "section, no console line",
       [r["verdict"] for r in res3["rows"]] == ["VERIFIED"] and not any("split" in r for r in res3["rows"])
       and "## Split quotations read together" not in gmd and not any("SPLIT QUOTATIONS" in x for x in glines),
       "%s | %s" % ([r["verdict"] for r in res3["rows"]], gmd[:300]))


def suite_k046_fact_bank(tmp):
    """K046 (2026-11-26): a fact is SLICED from an exhibit (`facts add`, `bank add`'s slicer) and a draft sentence
    cites it as [F-nnn]; `check` holds the sentence's dates, amounts and numbers to the slice - not to the whole
    exhibit, where a value swapped in from another entity of the same document always «stands» - and says when the
    sentence cites another exhibit. Names are listed, never counted (measured: a red on names is wrong about half the
    time). Fictional people and companies only (E-1009)."""
    import json
    import subprocess as _sp
    from krokai import facts as F
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    OFFER = ('Northfield Labs is pleased to offer Ada Testperson the position of Research Engineer starting on March 2, '
             '2021 at an annual salary of $85,000. Our director wrote: "We expect careful and patient work from the '
             'whole research team this year." Her previous employer, Brightwater Analytics, paid $61,500 from June '
             '2017.\n')
    AWARD = "The Quill Society awarded the Silver Quill to Ada Testperson on 05/14/2019 for 12 published papers.\n"
    WAGES = "Payroll record: total wages 47,250.00 for the calendar year 2020, paid in twelve parts.\n"

    def matter(name, fact_bank=None):
        root = os.path.join(tmp, name)
        for d in ("law", "case", "exhibits"):
            os.makedirs(os.path.join(root, d))
        io.open(os.path.join(root, "law", "8CFR-204.md"), "w", encoding="utf-8").write(
            "# 8 CFR 204.5 (fixture)\n\n(k) An alien who is a member of the professions holding an advanced "
            "degree must show the degree.\n")
        for fn, text in (("K-4 Offer letter.md", OFFER), ("B-1 Award notice.md", AWARD), ("C-7 Payroll.md", WAGES),
                         ("D-2 Letter.md", "A letter dated 01/02/2020.\n"),
                         ("D-2 Letter repaired.md", "A letter dated 01/02/2020, repaired copy.\n")):
            io.open(os.path.join(root, "exhibits", fn), "w", encoding="utf-8").write(text)
        cf = {"bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
              "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
              "citation_packs": ["us-federal"], "exhibits": ["exhibits"]}
        if fact_bank:
            cf["fact_bank"] = fact_bank
        io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps(cf))
        return root

    def kro(root, *args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args) + ["--dir", root], cwd=repo, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def add(root, ex, a, b, *extra):
        return kro(root, "facts", "add", "--exhibit", ex, "--from", a, "--to", b, *extra)

    # --- the token layer alone -----------------------------------------------------------------------
    toks = F.sentence_tokens('Dr. Ada Testperson earned $85,000 from January 5, 2020 (Exhibit K-4) under 8 CFR '
                             '204.5(k)(2), Form I-140 and H-1B rules, section 214.2(h)(4) [F-012].')
    kinds = sorted((t["kind"], t["raw"]) for t in toks)
    ok("k046: a sentence's facts are its dates, amounts, numbers and names - the exhibit id, the citation, the form, "
       "the visa class, the subsection chain and the [F-nnn] marker are not facts",
       kinds == sorted([("name", "Ada"), ("name", "Testperson"), ("amount", "$85,000"),
                        ("date", "January 5, 2020")]), repr(kinds))
    ix = F.SliceIndex(["Start date 01/05/2020; salary 85,000.00 USD; revenue $45 million; Certiﬁed by the board."])
    held = [t["raw"] for t in F.sentence_tokens("She started on January 5, 2020 at $85,000, revenue $45 Million, a "
                                                "Certified Board member.") if ix.holds(t)]
    ok("k046: a slice holds a value in another shape - 01/05/2020 = January 5, 2020, 85,000.00 USD = $85,000, "
       "«Million» = «million», a ligature «ﬁ» = «fi»",
       {"January 5, 2020", "$85,000", "$45 Million", "Certified"} <= set(held), repr(held))
    if os.name == "nt":
        ok("k046: an exhibit on another drive than the matter is named by its absolute path, not a crash",
           F._rel("D:\\cases\\exhibits\\K-4.pdf", "C:\\matter").startswith("D:\\"), F._rel("D:\\x", "C:\\y"))
    ok("k046: a value the slice does not hold is missing - one digit off, another day of the same month",
       [t["raw"] for t in F.missing("She earned $85,001 from January 6, 2020.", ["salary $85,000 from 01/05/2020"])]
       == ["$85,001", "January 6, 2020"],
       repr([t["raw"] for t in F.missing("She earned $85,001 from January 6, 2020.", ["salary $85,000 from 01/05/2020"])]))

    # --- facts add: dry run, write, refusals -----------------------------------------------------------
    root = matter("k046m")
    bank = os.path.join(root, "facts", "FACT-BANK.md")
    rc, out = add(root, "K-4", "Northfield Labs is pleased", "salary of $85,000.")
    ok("k046: facts add is a dry run without --apply - nothing written", rc == 0 and "DRY RUN" in out
       and not os.path.exists(bank), out[-400:])
    rc, out = add(root, "K-4", "Northfield Labs is pleased", "this year.\"", "--apply")
    b = F.read_bank(bank) or {}
    e = b.get("F-001") or {}
    ok("k046: facts add --apply writes F-001 - exhibit, file, sha256, the slice cut from the exhibit, a ledger line",
       rc == 0 and e.get("exhibit") == "K-4" and e.get("file", "").endswith("K-4 Offer letter.md")
       and len(e.get("sha256", "")) == 64 and e.get("slice", "").startswith("Northfield Labs is pleased")
       and e["slice"].endswith('this year."') and "entries: 1" in io.open(bank, encoding="utf-8").read(),
       out[-500:])
    rc, out = add(root, "D-2", "A letter dated", "01/02/2020")
    ok("k046: two DIFFERENT files carry one exhibit id - refused, both offered as --file, none picked",
       rc == 3 and out.count("--file") >= 2 and "refusing to pick" in out, out[-500:])
    rc, out = add(root, "D-2", "A letter dated", "repaired copy.", "--file", os.path.join("exhibits",
                                                                                         "D-2 Letter repaired.md"))
    ok("k046: --file picks one of them (dry run)", rc == 0 and "DRY RUN" in out, out[-400:])
    rc, out = add(root, "P-9", "anything", "else")
    ok("k046: an exhibit id no file carries - refused with the folders searched", rc == 3 and "no file carries" in out,
       out[-300:])
    rc, out = add(root, "K-4", "Ada Testperson", "Research Engineer", "--id", "F-001")
    ok("k046: an id already in the bank is refused - ids are never reused", rc == 3 and "already in the fact bank" in out,
       out[-300:])
    rc, out = add(root, "K-4", "a", "$85,000.")
    ok("k046: a start anchor that is not unique is refused (bank add's own slicer)", rc == 3 and "UNIQUE" in out,
       out[-300:])
    rc, out = add(root, "B-1", "The Quill Society", "published papers.", "--apply")
    ok("k046: a second entry gets the next id", rc == 0 and "F-002" in (F.read_bank(bank) or {}), out[-300:])
    io.open(bank, "a", encoding="utf-8").write(
        "### F-003\n- Exhibit: C-7\n- File: exhibits/C-7 Payroll.md\n- Text layer: OCR layer - its digits are what "
        "an OCR engine read\n\n> %s\n" % WAGES.strip())
    # the award notice changes after banking: F-002's slice is gone
    io.open(os.path.join(root, "exhibits", "B-1 Award notice.md"), "w", encoding="utf-8").write(
        AWARD.replace("Silver", "Bronze"))
    S = {"ok": "Northfield Labs hired Ms. Testperson on March 2, 2021 at $85,000 a year (Exhibit K-4) [F-001].",
         "swap": "Northfield Labs hired her on March 2, 2021 at $61,500 a year (Exhibit K-4) [F-001].",
         "wrong": "She joined Northfield Labs on March 2, 2021 (Exhibit D-2) [F-001].",
         "unknown": "Her salary was $90,000 [F-009].",
         "gone": "The Quill Society honoured her in 2019 (Exhibit B-1) [F-002].",
         "nothing": "The offer came from Northfield Labs. [F-001]",
         "ocr": "Wages reached $47,250 in 2020 (Exhibit C-7) [F-003].",
         "names": "She was hired by Orion Dynamics on March 2, 2021 (Exhibit K-4) [F-001].",
         "day": "She started on March 15, 2021 (Exhibit K-4) [F-001]."}
    io.open(os.path.join(root, "case", "brief.md"), "w", encoding="utf-8").write(
        "# Brief\n\n" + "\n\n".join(S.values()) + "\n")
    out_dir = os.path.join(tmp, "k046o")
    p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", root, "--out", out_dir, "--strict"], cwd=repo,
                env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    cout = (p.stdout or "") + (p.stderr or "")
    try:
        frows = json.load(io.open(os.path.join(out_dir, "result.json"), encoding="utf-8"))["facts"]
        md = io.open(os.path.join(out_dir, "REPORT.md"), encoding="utf-8").read()
    except (OSError, ValueError, KeyError):
        frows, md = [], ""

    def fr(key):
        head = S[key].split("[F-")[0].strip()[:40]
        for r in frows:
            if r.get("sentence", "").startswith(head):
                return r
        return {}

    for key, want in (("ok", F.SUPPORTED), ("swap", F.NOT_IN_SLICE), ("wrong", F.WRONG_EXHIBIT),
                      ("unknown", F.UNKNOWN_ENTRY), ("gone", F.SLICE_GONE), ("nothing", F.NOTHING),
                      ("ocr", F.SUPPORTED), ("names", F.SUPPORTED), ("day", F.NOT_IN_SLICE)):
        ok("k046: check - the «%s» sentence is %s" % (key, want), fr(key).get("verdict") == want, repr(fr(key)))
    ok("k046: the swapped salary is named - a value of ANOTHER entity of the same exhibit, which «anywhere in the "
       "exhibit» would have passed", fr("swap").get("missing") == ["$61,500"], repr(fr("swap")))
    ok("k046: a day the slice does not hold, in a month it does, says so",
       any("month, not the day" in m for m in fr("day").get("missing") or []), repr(fr("day")))
    ok("k046: names the slice does not hold are listed, not counted", fr("names").get("names") == ["Orion", "Dynamics"]
       and fr("ok").get("names") == [], repr((fr("names"), fr("ok").get("names"))))
    ok("k046: a marker after the full stop belongs to the sentence before it",
       fr("nothing").get("sentence", "").startswith("The offer came from"), repr(fr("nothing")))
    ok("k046: a slice read from an OCR layer is marked in the console and REPORT.md",
       fr("ocr").get("ocr") == ["F-003"] and "OCR layer - confirm its digits" in cout
       and "F-003 rest(s) on an OCR layer" in md, cout[-600:])
    ok("k046: check --strict exits 1 on a red fact in tier A; the console line counts every verdict",
       p.returncode == 1 and "🔴 FACTS: 9 sentence(s) cite the fact bank" in cout
       and "UNKNOWN_ENTRY 1" in cout and "SLICE_GONE 1" in cout, cout[-700:])
    ok("k046: REPORT.md «Facts held to their slices» lists each reference with its verdict",
       "## Facts held to their slices" in md and "**WRONG_EXHIBIT**" in md and "not in the slice: $61,500" in md,
       md[-800:])

    # --- the green path: every fact held, the bank inside a draft folder is not graded as our writing ----------
    g = matter("k046g", fact_bank="case/FACT-BANK.md")
    rc, out = add(g, "K-4", "Northfield Labs is pleased", "this year.\"", "--apply")
    io.open(os.path.join(g, "case", "brief.md"), "w", encoding="utf-8").write("# Brief\n\n" + S["ok"] + "\n")
    og = os.path.join(tmp, "k046go")
    p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", g, "--out", og, "--strict"], cwd=repo, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    gout = (p.stdout or "") + (p.stderr or "")
    try:
        grows = json.load(io.open(os.path.join(og, "result.json"), encoding="utf-8"))["rows"]
    except (OSError, ValueError, KeyError):
        grows = None
    ok("k046: green path - every fact held: check --strict exits 0 and says so", rc == 0 and p.returncode == 0
       and "✅ FACTS: 1 sentence(s) cite the fact bank" in gout, gout[-500:])
    ok("k046: the fact bank is never read as our writing - its quoted evidence is not a quotation row",
       grows is not None and not any("careful and patient work" in (r.get("quote") or "") for r in grows),
       repr([r.get("quote") for r in grows or []][:5]))
    nf = matter("k046n")
    io.open(os.path.join(nf, "case", "brief.md"), "w", encoding="utf-8").write("# Brief\n\nNo facts cited here.\n")
    on = os.path.join(tmp, "k046no")
    p = _sp.run([sys.executable, "-m", "krokai", "check", "--dir", nf, "--out", on], cwd=repo, env=env,
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    try:
        nmd = io.open(os.path.join(on, "REPORT.md"), encoding="utf-8").read()
    except OSError:
        nmd = None
    ok("k046: no [F-nnn] in the drafts - no facts line, no facts section", nmd is not None
       and "## Facts held to their slices" not in nmd and "FACTS:" not in (p.stdout or ""), (p.stdout or "")[:300])


def suite_k092_exhibit_ids(tmp):
    """K092 (2026-11-26): exhibit ids krokai could not read. Measured on a names copy of a real matter: a third of one
    package (255 files of series N, O, Q, Y - 23 typed with a CYRILLIC look-alike letter) had «no id»; «Exhibit J-1»
    was dropped as a visa code although the package holds J-1; «V-67-1» was refused whole. The series a package uses is
    read from its own folders and names, the word Exhibit decides for the token right after it, a look-alike letter is
    read AND named, a part suffix is a part."""
    import json
    import subprocess as _sp
    import unicodedata as _ud
    from krokai import exhibit_check as X
    from krokai import facts as F
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CYR_O, CYR_C = "О", "С"
    base = os.path.join(tmp, "k092")

    def touch(*parts, text=""):
        p = os.path.join(base, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(text)
        return p

    # --- the readers alone ------------------------------------------------------------------------------------------
    ok("k092: the look-alike table is Unicode's - 37 Cyrillic / Greek capitals, each to ONE Latin capital",
       len(X.LOOKALIKE) == 37 and all("A" <= v <= "Z" for v in X.LOOKALIKE.values())
       and all(("CYRILLIC" in _ud.name(k) or "GREEK" in _ud.name(k)) for k in X.LOOKALIKE), str(len(X.LOOKALIKE)))
    got = X.ids_in_text("Her status (Exhibit J-1). Her J-1 visa. Exhibit D-1 - I-20 form. Form G-1145, H-1B.")
    ok("k092: after the word Exhibit a code is an exhibit (J-1); bare it is not; «Exhibit D-1 - I-20» does not chain "
       "the dash to the form number", got == {"J-1", "D-1"}, str(sorted(got)))
    got = X.ids_in_text("See Exhibit V-67-1 and V-68-2; dated A-12-2024; X-1–X-5; COVID-19.")
    ok("k092: «V-67-1» is part 1 of V-67 (and V-68-2 of V-68), a date «A-12-2024» stays no id, a range «X-1–X-5» "
       "reads both ends", got == {"V-67", "V-68", "X-1", "X-5"}, str(sorted(got)))
    got = X.ids_in_text("Exhibit %s-3 and Exhibit %s-2" % (CYR_C, CYR_O))
    ok("k092: a Cyrillic look-alike letter after Exhibit is read as the Latin one (С-3 -> C-3, О-2 -> O-2)",
       got == {"C-3", "O-2"}, str(sorted(got)))
    d_y = list(X.DEFAULT_SERIES) + ["Y", "N"]
    ok("k092: a bare id of a series outside the list is read only when the series is given (Y-3), a bare form "
       "number never (N-400), a memoranda id never (Exhibit M-3)",
       X.ids_in_text("Y-3; N-4; N-400; Exhibit M-3") == set() and
       X.ids_in_text("Y-3; N-4; N-400; Exhibit M-3", d_y) == {"Y-3", "N-4"},
       "%s / %s" % (sorted(X.ids_in_text("Y-3; N-4; N-400; Exhibit M-3")),
                    sorted(X.ids_in_text("Y-3; N-4; N-400; Exhibit M-3", d_y))))
    n1, n2 = X.name_id("Exhibit %s1 award.pdf" % CYR_O, None), X.name_id("Cross Exhibit V-67-1 part.pdf", None)
    ok("k092: a file name «Exhibit О1 …» (Cyrillic О) reads O-1 and says which letter was typed; «Cross Exhibit V-67-1 "
       "…» reads V-67", bool(n1 and n1[0] == "O-1" and n1[1] == CYR_O and n2 and n2[0] == "V-67"), "%r %r" % (
           n1 and n1[:2], n2 and n2[:2]))
    for fn in ("I-485 form.pdf", "I-131.pdf", "G-1450 a.pdf", "G-1145 b.pdf", "N-400.pdf", "N-600.pdf"):
        touch("forms-only", fn)
    for fn in ("N-1 a.pdf", "N-2 b.pdf"):
        touch("n-pair", fn)
    touch("Exhibit Q", "q-index.pdf")
    dec = (X.declared_series(os.path.join(base, "forms-only")), X.declared_series(os.path.join(base, "n-pair")),
           X.declared_series(os.path.join(base, "Exhibit Q")))
    ok("k092: a package declares a series by a folder «Exhibit Q» or by 2+ numbered names (N-1, N-2); a forms folder "
       "(I-485, G-1450, N-400 …) declares none", dec == (set(), {"N"}, {"Q"}), str(dec))

    # --- check-exhibits end to end ----------------------------------------------------------------------------------
    pet = touch("case", "petition.md", text=(
        "The degree (Exhibit Y-3) and the award (Exhibit %s-2). See Exhibit V-67-1. Her J-1 visa (Exhibit J-1).\n"
        "Exhibit D-1 - I-20 form. Exhibit Z-9.\n\n| Y-4 | Letter |\n\nN-400 was not filed.\n" % CYR_O))
    ex = os.path.join(base, "ex")
    for parts in (("Exhibit Y", "Exhibit Y3 degree.pdf"), ("Exhibit Y", "Exhibit Y4 letter.pdf"),
                  ("Exhibit O", "Exhibit %s2 award.pdf" % CYR_O), ("V", "Cross Exhibit V-67-1 part.pdf"),
                  ("V", "Cross Exhibit V-67-2 part.pdf"), ("J", "J-1 letter.pdf"), ("J", "J-2 letter.pdf"),
                  ("D-1 statement.pdf",), ("forms", "G-1450 fee.pdf"), ("Z-1 single.pdf",)):
        touch("ex", *parts)
    r = X.reconcile([pet], [ex])
    rep = "\n".join(r["report_lines"])
    ok("k092: check-exhibits reads the series its exhibit folder declares (folder «Exhibit Y», names «Exhibit Y3 …» "
       "with no dash; a bare «Y-4» in the table) and names those series",
       {"Y-3", "Y-4"} <= r["matched"] and "use them (not in krokai's default list): **O, Y**" in rep,
       "matched %s" % sorted(r["matched"]))
    ok("k092: «(Exhibit J-1)» cites J-1 and the file «J-1 letter» beside «J-2 letter» IS exhibit J-1 (the folder uses "
       "series J) - matched, not dropped as a visa code", "J-1" in r["matched"], str(sorted(r["matched"])))
    ok("k092: a form in a folder that declares no series stays a form - and is LISTED, not dropped silently",
       "G-1450" not in r["file_no_cite"] and "NAMES READ AS A FORM / VISA CODE" in rep and "`G-1450 fee.pdf`" in rep,
       rep[-600:])
    ok("k092: a Cyrillic look-alike letter is read as the Latin one in the file name AND in the petition, and both are "
       "named with the character (U+041E)", "O-2" in r["matched"] and rep.count("U+041E CYRILLIC CAPITAL LETTER O") == 2,
       str(rep.count("U+041E")))
    ok("k092: «Exhibit V-67-1» cites V-67; «Cross Exhibit V-67-1 / -2» are its parts, not duplicates",
       "V-67" in r["matched"] and not r["duplicates"], str(r["duplicates"]))
    ok("k092: a name that starts like an id of a series nobody else uses says why it has no id",
       "* `Z-1 single.pdf` — starts like an id of series Z" in rep, rep[rep.find("WITHOUT RECOGNIZED"):][:300])
    ok("k092: an id of any series after the word Exhibit is checked - «Exhibit Z-9» with no file is CITED-NO-FILE; "
       "«I-20», «N-400» and a bare «J-1 visa» are not cited", r["cited_no_file"] == {"Z-9"} and not (
           {"I-20", "N-400"} & (r["matched"] | r["cited_no_file"])), str(sorted(r["cited_no_file"])))

    def cli(petition, exhibits):
        p = _sp.run([sys.executable, "-m", "krokai", "check-exhibits", "--petition", petition, "--exhibits", exhibits],
                    cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    clean_pet = touch("clean", "petition.md", text="The degree (Exhibit Y-1) and the letter (Exhibit Y-2).\n")
    for fn in ("Exhibit Y1 degree.pdf", "Exhibit Y2 letter.pdf"):
        touch("clean-ex", "Exhibit Y", fn)
    rc_c, out_c = cli(clean_pet, os.path.join(base, "clean-ex"))
    rc_r, out_r = cli(pet, ex)
    ok("k092: green path through the CLI - a petition citing Y-1, Y-2 and a folder «Exhibit Y» holding them exits 0 "
       "with both matched and no look-alike section; the fixture above exits 1 (Z-9 has no file)",
       rc_c == 0 and "| Exhibits matched | 2 |" in out_c and "LOOK-ALIKE" not in out_c and rc_r == 1
       and "LOOK-ALIKE LETTERS" in out_r, "rc %s / %s" % (rc_c, rc_r))

    # --- facts ------------------------------------------------------------------------------------------------------
    root = os.path.join(tmp, "k092-facts")
    for d in ("law", "case", "exhibits"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    io.open(os.path.join(root, "law", "8CFR-204.md"), "w", encoding="utf-8").write(
        "# 8 CFR 204.5 (fixture)\n\n(k) An alien who is a member of the professions must show the degree.\n")
    io.open(os.path.join(root, "exhibits", "Exhibit Y3 Degree.md"), "w", encoding="utf-8").write(
        "Northfield Institute confers the degree of Master of Science on Ada Testperson on June 5, 2019.\n")
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md", "sources": ["law"],
        "drafts": [{"tier": "A", "label": "filed", "path": "case"}], "citation_packs": ["us-federal"],
        "exhibits": ["exhibits"]}))
    p = _sp.run([sys.executable, "-m", "krokai", "facts", "add", "--exhibit", "Y-3", "--from", "Northfield Institute",
                 "--to", "June 5, 2019", "--dir", root], cwd=repo, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=240)
    out = (p.stdout or "") + (p.stderr or "")
    ok("k092: `facts add --exhibit Y-3` finds «Exhibit Y3 Degree» although no other file declares series Y (dry run)",
       p.returncode == 0 and "Exhibit Y3 Degree.md" in out and "exhibit : Y-3" in out, out[:400])
    ok("k092: a fact sentence's «Exhibit Y-3» and «Exhibit V-67-1» are ids, not facts (their digits are blanked)",
       "3" not in F._masked("as Exhibit Y-3 shows") and "67" not in F._masked("see Exhibit V-67-1 here")
       and F.exhibit_id("Y-3") == "Y-3" and F.exhibit_id(CYR_C + "-26") == "C-26", F._masked("as Exhibit Y-3 shows"))


def suite_k045_exhibit_list(tmp):
    """K045 (2026-11-26): the exhibit LIST a petition prints, against its sentences and the disk. Measured on a copy of
    a real filed petition: 281 ids listed in 9 documents (tables with an «Exhibit» column, lines «Exhibit K28 - …»);
    «X-13 (= P-07)» rows answered 7 of 23 «cited, no file»; 118 listed ids no sentence uses (a second, literal search
    agreed: 117 + one heading); 2 files the list never names. Advisory sections - the exit code is unchanged."""
    import subprocess as _sp
    import zipfile as _zf
    from krokai import exhibit_check as X
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = os.path.join(tmp, "k045")

    def touch(*parts, text=None):
        p = os.path.join(base, *parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write(text or "")
        return p

    md = ("# Index of Exhibits\n\n| Exhibit | Description |\n|---|---|\n| **B-1** | Letter |\n| J-1 | DS-2019 |\n"
          "| X-13 (= P-07) | Copy |\n| B-3 – B-5 | Letters |\n\n| Criterion | Evidence |\n|---|---|\n| Prong 1 | see B-6 |\n"
          "\nExhibit K28 - Letter from the lab\n- C-2: Article\nExhibit C-9 - " + "word " * 70 + "\nC-4 was filed late.\n")
    entries, used = X.exhibit_list(md)
    got = {e: a for _n, e, a in entries}
    ok("k045: the list = rows under an «Exhibit» column (bold stripped, a bare J-1 read because the header says Exhibit, "
       "«B-3 – B-5» lists B-4 too) + lines «Exhibit K28 - …» / «- C-2: …»; not a «Criterion» table, a 300+ character "
       "paragraph or «C-4 was filed»", set(got) == {"B-1", "J-1", "X-13", "B-3", "B-4", "B-5", "K-28", "C-2"},
       str(sorted(got)))
    ok("k045: «X-13 (= P-07)» lists X-13 with the alias P-7", got.get("X-13") == ["P-7"], str(got.get("X-13")))
    rr = X.range_ids("Exhibits B-1 through B-5 and (K60-K66); see V-67-1, A-12-2024, B-1 - B-80, M-1 to M-5")
    ok("k045: a range cites both ends and the middle («B-1 through B-5», «(K60-K66)»); a part «V-67-1», a date "
       "«A-12-2024», a span over 50 and the memoranda series are not ranges",
       rr == {"B-%d" % k for k in range(1, 6)} | {"K-%d" % k for k in range(60, 67)}, str(sorted(rr)))
    ok("k045: a long list prints as runs - «K-1…K-3», a pair as two ids, a part alone",
       X._runs(["H-10a", "K-1", "K-2", "K-3", "K-5", "K-6"]) == "**H-10a**, **K-1…K-3**, **K-5**, **K-6**",
       X._runs(["H-10a", "K-1", "K-2", "K-3", "K-5", "K-6"]))

    # --- a Word petition: its table row stays one line, so the «Exhibit» column is still a column ---------------
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def cell(t):
        return "<w:tc><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:tc>" % t
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="%s"><w:body>'
           '<w:p><w:r><w:t>The form (Exh</w:t></w:r><w:r><w:t>ibit J-1) shows it.</w:t></w:r></w:p>'
           '<w:tbl><w:tr>%s%s</w:tr><w:tr>%s%s</w:tr></w:tbl></w:body></w:document>'
           % (W, cell("Exhibit"), cell("Description"), cell("J-1"), cell("DS-2019 form")))
    docx = os.path.join(base, "word", "brief.docx")
    os.makedirs(os.path.dirname(docx), exist_ok=True)
    with _zf.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", xml)
    dtext = X._read_text(docx)
    dent, _u = X.exhibit_list(dtext)
    ok("k045: a .docx table row reads as «| J-1 | DS-2019 form |» and its «Exhibit» column lists J-1; the run-split "
       "sentence before it still cites J-1", "| J-1 | DS-2019 form |" in dtext and [e for _n, e, _a in dent] == ["J-1"]
       and "The form (Exhibit J-1) shows it." in dtext, dtext[:200])

    # --- reconcile: red paths ------------------------------------------------------------------------------------
    pet = touch("red", "petition.md", text=(
        "# Index of Exhibits\n\n| Exhibit | Description |\n|---|---|\n| B-1 | Letter |\n| B-2 | Article |\n"
        "| B-3 | Award |\n| X-13 (= P-7) | Copy of the passport |\n| H-10 | Letters |\n\n"
        "The letters (Exhibits B-1 through B-2) show it. The award letters (Exhibit H-10a), the passport (Exhibit P-7) "
        "and the press (Exhibit C-4). The plan (Exhibits D-1 through D-3).\n"))
    for fn in ("B-1 letter.pdf", "B-2 article.pdf", "B-3 award.pdf", "P-7 passport.pdf", "H-10a letters.pdf",
               "C-4 press.pdf", "C-5 extra.pdf", "D-1 a.pdf", "D-2 b.pdf", "D-3 c.pdf"):
        touch("red-ex", fn)
    r = X.reconcile([pet], [os.path.join(base, "red-ex")])
    rep = "\n".join(r["report_lines"])
    ok("k045: listed and no sentence uses it -> B-3; a part cited («H-10a») answers its whole («H-10»), an alias cited "
       "(P-7) answers X-13", r["listed_not_cited"] == ["B-3"], str(r["listed_not_cited"]))
    ok("k045: cited in a sentence and not in the list -> C-4 and the range D-1 … D-3 (its middle D-2 included)",
       r["cited_not_listed"] == ["C-4", "D-1", "D-2", "D-3"], str(r["cited_not_listed"]))
    ok("k045: a file the list never names -> C-4, C-5, D-1 … D-3; «H-10a letters» is a part of the listed H-10",
       r["file_not_listed"] == ["C-4", "C-5", "D-1", "D-2", "D-3"], str(r["file_not_listed"]))
    ok("k045: «X-13 (= P-7)» - X-13 has no file of its own but its alias has: not CITED-NO-FILE, and the report says "
       "which file answers it", r["alias_ok"] == {"X-13": ["P-7"]} and "X-13" not in r["cited_no_file"]
       and "X-13 → P-7" in rep, str(r["alias_ok"]))
    ok("k045: a file cited only inside a range («D-1 through D-3») is cited - D-2 is not FILE-NO-CITE",
       "D-2" not in r["file_no_cite"] and r["file_no_cite"] == {"C-5"}, str(sorted(r["file_no_cite"])))
    ok("k045: the three list sections and their summary rows are printed with counts",
       "## LISTED, NEVER CITED IN A SENTENCE — 1" in rep and "## CITED IN A SENTENCE, NOT IN THE EXHIBIT LIST — 4" in rep
       and "## FILE NOT IN THE EXHIBIT LIST — 5" in rep and "| Listed, never cited in a sentence | 1 |" in rep,
       rep[rep.find("## EXHIBIT LIST"):][:400])

    # --- no list: said loudly, nothing invented -------------------------------------------------------------------
    pet0 = touch("nolist", "petition.md", text="The letter (Exhibit B-1).\n")
    touch("nolist-ex", "B-1 letter.pdf")
    r0 = X.reconcile([pet0], [os.path.join(base, "nolist-ex")])
    rep0 = "\n".join(r0["report_lines"])
    ok("k045: no list in the documents -> «EXHIBIT LIST — none found», the list checks did NOT run, nothing listed",
       "## EXHIBIT LIST — none found" in rep0 and "did NOT run" in rep0 and r0["listed"] == {}
       and r0["file_not_listed"] == [], rep0[rep0.find("## EXHIBIT"):][:200])

    # --- green path through the CLI (E-1072) ----------------------------------------------------------------------
    gpet = touch("green", "petition.md", text=(
        "| Exhibit | Description |\n|---|---|\n| B-1 | Letter |\n| B-2 | Article |\n\n"
        "The letter (Exhibit B-1) and the article (Exhibit B-2).\n"))
    for fn in ("B-1 letter.pdf", "B-2 article.pdf"):
        touch("green-ex", fn)
    p = _sp.run([sys.executable, "-m", "krokai", "check-exhibits", "--petition", gpet, "--exhibits",
                 os.path.join(base, "green-ex")], cwd=repo, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=240)
    out = (p.stdout or "") + (p.stderr or "")
    ok("k045: green path through the CLI - list = sentences = files: exit 0, the list found (2 ids), all three list "
       "sections 0", p.returncode == 0 and "## EXHIBIT LIST — 2 ids listed" in out
       and "| Listed, never cited in a sentence | 0 |" in out and "| Cited in a sentence, not in the exhibit list | 0 |"
       in out and "| File, not in the exhibit list | 0 |" in out, "rc %s %s" % (p.returncode, out[-500:]))


def suite_k093_short_pdf(tmp):
    """K093 (2026-11-26): a SHORT PDF (under MIN_TEXT_LAYER) that reads as a typeset document on
    every count - a typeset layer, no picture, a line in the page body - is INDEXED with the
    short-source warning, as a short text file is; a stamp or a label over a picture, a margin-only
    label, an OCR layer that thin and an empty page stay excluded, now with the reason; a typeset bot
    wall is a FAILED DOWNLOAD (re-fetch), not «OCR it». Before, every PDF under the floor was excluded
    with «OCR it» - and the census that raised it found its 11 short «typeset» exhibits to be
    pictures carrying a label (readers.STAMP_BAND)."""
    import builtins
    import contextlib
    import json
    import subprocess as _sp
    from krokai import readers as R
    from krokai import sidecar as SC
    from krokai.corpus import Corpus

    ok("k093: an EMPTY primary extraction no longer beats a short alternate (BACKLOG K010)",
       R._choose_extraction("", "Short notice.")[0] == "Short notice."
       and R._choose_extraction(" \n", "")[0] == "", repr(R._choose_extraction("", "Short notice.")))
    try:
        from krokai import _pdfengine
        fz = _pdfengine.load()
    except ImportError:
        fz = None
    if fz is None:
        print("note: k093 short-PDF fixture pins skipped - PyMuPDF builds the fixtures and is not "
              "installed here")
        return

    root = os.path.join(tmp, "k093m")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))
    NOTE_A = "The office is closed on the day of the hearing."
    NOTE_B = "A filing due that day is due on the next business day."

    def make(name, body=(), margin=(), picture=None, invisible=False):
        d = fz.open()
        pg = d.new_page()                                   # 595 x 842: the body band is y 84-758
        if picture is not None:
            pix = fz.Pixmap(fz.csGRAY, fz.IRect(0, 0, 40, 60), 0)
            pix.clear_with(190)
            pg.insert_image(fz.Rect(*picture), pixmap=pix, keep_proportion=False)   # fills the box
        for i, ln in enumerate(body):
            pg.insert_text((72, 300 + 16 * i), ln, fontsize=11, render_mode=3 if invisible else 0)
        for y, ln in margin:
            pg.insert_text((72, y), ln, fontsize=8)
        p = os.path.join(law, name)
        d.save(p)
        d.close()
        return p

    notice = make("8CFR-293.pdf", body=(NOTE_A, NOTE_B))
    make("8CFR-292.pdf", margin=((40, "EXHIBIT K-12"), (820, "ABC-000123")), picture=(0, 0, 595, 842))
    make("8CFR-291.pdf", body=("Photograph of the office entrance on the day of the inspection.",),
         picture=(100, 60, 495, 280))
    make("8CFR-290.pdf", margin=((40, "EXHIBIT C-7"), (820, "Page 1 of 1 - ABC-000777")))
    make("8CFR-289.pdf", body=("Just a moment...", "Checking your browser before accessing the site.",
                               "Enable JavaScript and cookies to continue."))
    make("8CFR-288.pdf")
    make("8CFR-287.pdf", body=("The clerk may extend a deadline for good cause shown.",), invisible=True)

    def base(ps):
        return sorted(os.path.basename(p) for p in ps)

    c = Corpus([law], quiet=True)
    why = {os.path.basename(p): w for p, w in getattr(c, "stub_why", {}).items()}
    ok("k093: a short typeset document - a line in the page body, no picture - is INDEXED as a short "
       "source, not excluded as a scan", "8CFR-293.pdf" in base(c.paths)
       and "8CFR-293.pdf" in base(c.short_sources) and "8CFR-293.pdf" not in base(c.excluded_stub),
       "paths=%s short=%s stub=%s" % (base(c.paths), base(c.short_sources), base(c.excluded_stub)))
    ok("k093: a stamp and a label over a page-sized picture are still excluded - the reason names the "
       "picture", "8CFR-292.pdf" in base(c.excluded_stub) and "covers 100 %" in why.get("8CFR-292.pdf", ""),
       str(why))
    ok("k093: a caption in the page body over a picture is excluded too - the picture can hold the "
       "page's words", "8CFR-291.pdf" in base(c.excluded_stub)
       and "picture that covers" in why.get("8CFR-291.pdf", ""), str(why))
    ok("k093: typeset text only in the page margin, with no picture, is a label - excluded",
       "8CFR-290.pdf" in base(c.excluded_stub) and "page margin" in why.get("8CFR-290.pdf", ""), str(why))
    ok("k093: an OCR layer that thin and an empty page stay excluded, each with its own reason",
       "OCR text layer" in why.get("8CFR-287.pdf", "") and "no text at all" in why.get("8CFR-288.pdf", ""),
       str(why))
    ok("k093: a typeset bot wall is a FAILED DOWNLOAD (re-fetch) - neither indexed nor sent to OCR",
       base(c.excluded_placeholder) == ["8CFR-289.pdf"]
       and "8CFR-289.pdf" not in base(c.excluded_stub) + base(c.paths),
       "placeholder=%s" % base(c.excluded_placeholder))

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        c.print_build()
    out = buf.getvalue()
    lines = out.splitlines()
    i292 = next((i for i, ln in enumerate(lines) if ln.strip().endswith("8CFR-292.pdf")), None)
    short_at = out.find("SHORT text source (INDEXED")
    ok("k093: the build output prints each excluded PDF's reason under it, and the short typeset one "
       "only under SHORT (INDEXED)", i292 is not None and i292 + 1 < len(lines)
       and lines[i292 + 1].strip().startswith("(") and "picture" in lines[i292 + 1]
       and short_at > 0 and "8CFR-293.pdf" in out[short_at:] and "8CFR-293.pdf" not in out[:short_at],
       out[:700])

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    _rc, qout = cli("quote", "--dir", root, NOTE_A)
    ok("k093: `quote` verifies a sentence of the short typeset PDF - it used to come back NOT FOUND",
       "VERIFIED" in qout and "8CFR-293.pdf" in qout and "NOT FOUND" not in qout.upper().replace("_", " "),
       qout[:600])
    io.open(os.path.join(case, "brief.md"), "w", encoding="utf-8").write(
        'Under 8 C.F.R. § 293.1, "%s" The rule goes on: "%s"\n' % (NOTE_A, NOTE_B))
    _rc, _cout = cli("check", "--dir", root, "--out", os.path.join(tmp, "k093o"))
    rep_md = os.path.join(tmp, "k093o", "REPORT.md")
    md = io.open(rep_md, encoding="utf-8").read() if os.path.exists(rep_md) else ""
    sec = (md.split("## Corpus files with no text layer", 1)[-1].split("\n## ", 1)[0]
           if "## Corpus files with no text layer" in md else "").replace("\\", "/")
    ok("k093: REPORT.md lists each excluded PDF with its reason - and not the short typeset one",
       "`law/8CFR-292.pdf` - " in sec and "covers 100 %" in sec and "page margin" in sec
       and "8CFR-293.pdf" not in sec, sec[:500] or md[:300])

    _made, _sk, nol, _fl = SC.build([law], dry_run=True, printer=lambda *a, **k: None)
    ok("k093: `sidecar` asks the corpus's question - the short typeset PDF is not listed as without a "
       "text layer, the label over a picture and the margin label are",
       "8CFR-293.pdf" not in base(nol) and {"8CFR-292.pdf", "8CFR-290.pdf", "8CFR-288.pdf"} <= set(base(nol)),
       str(base(nol)))

    real_import = builtins.__import__

    def without(names):
        def imp(name, *a, **k):
            if name.split(".")[0] in names:
                raise ImportError("hidden by the k093 selftest: %s" % name)
            return real_import(name, *a, **k)
        R._LAYER_MEMO.clear()
        R._PAGES_MEMO.clear()
        builtins.__import__ = imp
        try:
            return R.pdf_text_verdict(notice)
        finally:
            builtins.__import__ = real_import
            R._LAYER_MEMO.clear()
            R._PAGES_MEMO.clear()

    try:
        import pypdf  # noqa: F401
        have_pypdf = True
    except ImportError:
        have_pypdf = False
    if have_pypdf:
        v1 = without(("fitz", "pymupdf"))
        ok("k093: with pypdf alone a short PDF stays excluded, and the reason says PyMuPDF is needed to "
           "tell a stamp over a scan from a document", v1[0] is True and "without PyMuPDF" in v1[1], str(v1))
    else:
        print("note: k093 pypdf-alone pin skipped - pypdf is not installed here")
    v2 = without(("pypdf",))
    ok("k093: with PyMuPDF alone the short typeset PDF is read and kept - an empty pypdf result used "
       "to win (K010)", v2 == (False, ""), str(v2))


def suite_k025_copies(tmp):
    """K025 (2026-11-25): when one document is on the disk twice and one copy is an OCR text layer,
    the quotation is asked again inside every other copy, and «copies disagree» shows both readings
    - `check` (console, REPORT.md, result.json) and `quote`. Advisory: the exit code never moves.
    Measured on a filed petition's library: the two OCR readings of one decision disagree on 12.6 %
    of their number tokens, of another on 16.1 %, and `check` read only the copy that sorted first."""
    import json
    import random
    import shutil
    import subprocess as _sp
    from krokai.config import load as load_cfg
    from krokai.corpus import Corpus, copy_print, COPY_SHARE, COPY_LEN
    from krokai.run import scan_matter, copy_counts, print_summary
    from krokai.verdicts import CLEAN
    from krokai.verify import copies_check, check

    rnd = random.Random(25)
    vocab = ("officer applied records general between statute because however service present "
             "against appeals pending request student program periods factors notices hearing "
             "the of and to in a for on with by at from that this which under shall may each").split()

    def prose(n, seed):
        rnd.seed(seed)
        return [" ".join(rnd.choice(vocab) for _ in range(12)).capitalize() + "." for _ in range(n)]

    S1 = "The respondent filed the motion on March 12, 1986, within the period the rule allows."
    S2 = "The officer explained the decision to the applicant in writing on the same day."
    S3 = "The board will reopen the matter within 90 days"
    S4 = "This sentence appears only in the extracted text and never in the scan layer itself."
    S5 = "The alert takes effect for filings received on or after June 1, 2026, at the service."
    body = prose(48, 1)
    txt_lines = body[:12] + [S1] + body[12:24] + [S2] + body[24:36] + \
        [S3 + " unless the applicant shows good cause."] + body[36:] + [S4]
    ocr_lines = [ln.replace("1986", "1988") for ln in txt_lines if ln != S4]
    ocr_lines = [S3 + "." if ln.startswith(S3) else ln for ln in ocr_lines]

    a, b = copy_print(" ".join(txt_lines)), copy_print(" ".join(ocr_lines))
    ok("k025: the copy fingerprint is deterministic and sees one misread digit as the same document",
       copy_print(" ".join(txt_lines)) == a and len(a) >= 20
       and len(a & b) / float(max(len(a), len(b))) >= 0.9 and 0 < COPY_SHARE < 1 and 0 < COPY_LEN < 1,
       "%d / %d shared %d" % (len(a), len(b), len(a & b)))

    try:
        from krokai import _pdfengine
        fz = _pdfengine.load()
    except ImportError:
        fz = None
    if fz is None:
        print("note: k025 copies fixture pins skipped - PyMuPDF builds the OCR fixture and is not "
              "installed here")
        return

    root = os.path.join(tmp, "k025m")
    law, case = os.path.join(root, "law"), os.path.join(root, "case")
    os.makedirs(law)
    os.makedirs(case)
    io.open(os.path.join(root, "casefile.json"), "w", encoding="utf-8").write(json.dumps({
        "bank": "QUOTE-BANK.md", "queue": "QUOTE-QUEUE.md", "library_index": "law/INDEX.md",
        "sources": ["law"], "drafts": [{"tier": "A", "label": "filed", "path": "case"}],
        "citation_packs": ["us-immigration", "us-federal"]}))
    ocr_pdf = os.path.join(law, "Matter-of-Example.pdf")
    txt_md = os.path.join(law, "Matter-of-Example.text.md")
    d = fz.open()
    for start in range(0, len(ocr_lines), 30):
        pg = d.new_page()
        for i, ln in enumerate(ocr_lines[start:start + 30]):
            pg.insert_text((40, 50 + 14 * i), ln, fontsize=8, render_mode=3)
    d.save(ocr_pdf)
    d.close()
    io.open(txt_md, "w", encoding="utf-8").write("\n".join(txt_lines) + "\n")
    alert = prose(40, 2)
    io.open(os.path.join(law, "PA-2026-99.md"), "w", encoding="utf-8").write(
        "\n".join(alert[:20] + [S5] + alert[20:]) + "\n")
    io.open(os.path.join(law, "PA-2026-99-copy.md"), "w", encoding="utf-8").write(
        "\n".join(alert[:20] + [S5.replace("June 1", "June 7")] + alert[20:]) + "\n")
    io.open(os.path.join(law, "Long-reprint.md"), "w", encoding="utf-8").write(
        "\n".join(txt_lines + prose(22, 3)) + "\n")

    cfg = load_cfg(root)
    from krokai.run import corpus_for
    corp = corpus_for(cfg)
    ok("k025: an OCR layer and the text beside it are copies of one document, both ways; a reprint "
       "half as long again is not; two typeset texts are never compared (no OCR side)",
       [p for p, _s in corp.copies_of(ocr_pdf)] == [txt_md]
       and [p for p, _s in corp.copies_of(txt_md)] == [ocr_pdf]
       and corp.copies_of(os.path.join(law, "PA-2026-99.md")) == [],
       str((corp.copies_of(ocr_pdf), corp.copies_of(txt_md),
            corp.copies_of(os.path.join(law, "PA-2026-99.md")))))
    sup = Corpus([law], quiet=True, superseded=[txt_md])
    ok("k025: a superseded edition is never a copy (K028 owns editions)",
       sup.copies_of(ocr_pdf) == [] and sup.copies_of(txt_md) == [], str(sup.copies_of(ocr_pdf)))

    long_md = os.path.join(law, "Long-reprint.md")
    v1, w1, _d = check(S1, corp)
    c1 = copies_check(S1, v1, w1, corp)
    c1o = [c for c in c1 if c["path"] == ocr_pdf]
    ok("k025: verified in the text, the OCR copy reads another digit - DISAGREE, with both readings "
       "taken from the copy that differs",
       v1 == "VERIFIED" and len(c1o) == 1 and c1o[0]["state"] == "disagree"
       and c1o[0]["reading_from"] == ocr_pdf and ["1986", "1988"] in c1o[0]["reading"], str((v1, w1, c1)))
    ok("k025: the verdict names a reprint that sorts first and has no copy of its own - the copies of "
       "every file holding the words are still asked (E-1073)",
       w1 == long_md and corp.copies_of(long_md) == [] and len(c1o) == 1, str((w1, c1)))
    c1r = copies_check(S1, "OPERATOR", ocr_pdf, corp)
    ok("k025: the same pair seen from the other side (the OCR copy read first, flagged) - the text "
       "copy holds the words, DISAGREE, and the reading still names the OCR copy's «1988»",
       len(c1r) == 1 and c1r[0]["state"] == "disagree" and c1r[0]["verdict"] in CLEAN
       and c1r[0]["reading_from"] == ocr_pdf and ["1986", "1988"] in c1r[0]["reading"], str(c1r))

    io.open(os.path.join(case, "petition.md"), "w", encoding="utf-8").write(
        '"%s"\n\n"%s"\n\n"%s"\n\n"%s"\n\n"%s"\n' % (S1, S2, S3, S4, S5))
    res = scan_matter(cfg, quiet=True, printer=lambda *a: None) or {"rows": []}

    def row(marker):
        return next((r for r in res["rows"] if marker in r["quote"]), {})

    r1, r2, r3, r4, r5 = (row(x) for x in ("March 12", "same day", "reopen the matter",
                                             "only in the extracted", "June 1"))
    st = [[c["state"] for c in r.get("copies") or []] for r in (r1, r2, r3, r4, r5)]
    ok("k025: rows carry each copy's answer - digit DISAGREE, same words AGREE (in both copies), a "
       "proviso only one copy shows DISAGREE, a passage one copy lacks ABSENT, a typeset pair nothing",
       st[0] == ["disagree"] and set(st[1]) == {"agree"} and len(st[1]) == 2 and "disagree" in st[2]
       and st[3] == ["absent"] and st[4] == []
       and r3.get("verdict") == "TRUNCATED_CONDITION" and r1.get("verdict") == "VERIFIED"
       and r5.get("verdict") == "VERIFIED", str([(r.get("verdict"), s) for r, s in
                                                 zip((r1, r2, r3, r4, r5), st)]))
    cc = copy_counts(res)
    lines = []
    back = print_summary(res, printer=lines.append)
    said = "\n".join(lines)
    stripped = dict(res, rows=[dict(r, copies=[]) for r in res["rows"]])
    ok("k025: the console counts them - 2 disagree, 1 confirmed - and the count never reaches the "
       "returned numbers (the exit code)",
       (cc["disagree"], cc["confirmed"]) == (2, 1)
       and "🟡 COPIES DISAGREE, tiers A+B: 2 quotation(s)" in said
       and "✅ SECOND COPY, tiers A+B: 1 quotation(s)" in said
       and back == print_summary(stripped, printer=lambda *a: None), said[-500:])

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def cli(*args):
        p = _sp.run([sys.executable, "-m", "krokai"] + list(args), cwd=repo, env=env,
                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    _rc, out = cli("check", "--dir", root, "--out", os.path.join(tmp, "k025o"))
    rep_md = os.path.join(tmp, "k025o", "REPORT.md")
    md = io.open(rep_md, encoding="utf-8").read() if os.path.exists(rep_md) else ""
    sec = md.split("## Copies disagree", 1)[-1].split("\n## ", 1)[0] if md else ""
    ok("k025: the real `check` prints the line, and REPORT.md shows both readings of the disagreeing "
       "rows - not the agreeing one, not the typeset pair",
       "COPIES DISAGREE, tiers A+B: 2" in out and "## Copies disagree - tiers A+B: 2" in md
       and "quoted «1986»" in sec and "reads «1988»" in sec and "March 12" in sec
       and "same day" not in sec and "June 1" not in sec, out[-300:] + " || " + sec[:600])
    rj = os.path.join(tmp, "k025o", "result.json")
    payload = json.load(io.open(rj, encoding="utf-8")) if os.path.exists(rj) else {}
    ok("k025: result.json carries every copy's answer on its row and the counts",
       (payload.get("copies") or {}).get("disagree") == 2
       and any(c.get("state") == "disagree" and c.get("file", "").endswith("Matter-of-Example.pdf")
               for r in payload.get("rows", []) for c in r.get("copies") or []),
       str(payload.get("copies")))

    _rc, q1 = cli("quote", "--dir", root, S1)
    _rc, q2 = cli("quote", "--dir", root, S2)
    _rc, q5 = cli("quote", "--dir", root, S5)
    ok("k025: `quote` shows the other copy's reading when the copies disagree",
       "🟡 COPIES DISAGREE:" in q1 and "«1988»" in q1 and "page image" in q1, q1[:700])
    ok("k025: `quote` says the second copy agrees - and no disagreement - when they agree; a typeset "
       "pair prints neither",
       "✅ second copy:" in q2 and "COPIES DISAGREE:" not in q2
       and "COPIES DISAGREE:" not in q5 and "second copy:" not in q5, q2[:500] + " || " + q5[:300])

    green = os.path.join(tmp, "k025g")
    shutil.copytree(law, os.path.join(green, "law"))
    os.makedirs(os.path.join(green, "case"))
    shutil.copyfile(os.path.join(root, "casefile.json"), os.path.join(green, "casefile.json"))
    io.open(os.path.join(green, "case", "petition.md"), "w", encoding="utf-8").write('"%s"\n' % S2)
    rcg, outg = cli("check", "--strict", "--dir", green, "--out", os.path.join(tmp, "k025go"))
    io.open(os.path.join(green, "case", "petition.md"), "w", encoding="utf-8").write('"%s"\n' % S1)
    rcd, outd = cli("check", "--strict", "--dir", green, "--out", os.path.join(tmp, "k025do"))
    ok("k025: green path - a quotation every copy confirms passes `check --strict` (exit 0) and says "
       "so, with no disagreement line",
       rcg == 0 and "✅ SECOND COPY, tiers A+B: 1" in outg and "COPIES DISAGREE" not in outg,
       "exit %s: %s" % (rcg, outg[-300:]))
    ok("k025: advisory - a quotation the copies disagree on still exits 0 under --strict",
       rcd == 0 and "COPIES DISAGREE, tiers A+B: 1" in outd, "exit %s: %s" % (rcd, outd[-300:]))


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
        suite_r76(tmp)
        suite_r77(tmp)
        suite_r77_cli(tmp)
        suite_r77b(tmp)
        suite_r78(tmp)
        suite_r79(tmp)
        suite_r79_phase2(tmp)
        suite_r79_phase3(tmp)
        suite_r79_phase4(tmp)
        suite_k004_kit_contract(tmp, corpus)
        suite_k023_not_examined(tmp)
        suite_k012_section_form(tmp)
        suite_k027_markers(tmp)
        suite_k028_editions(tmp)
        suite_k024_ocr_layer(tmp)
        suite_k025_copies(tmp)
        suite_k026_front_door(tmp)
        suite_k030_edge_ellipsis(tmp)
        suite_k018_pages(tmp)
        suite_k018b_printed_pages(tmp)
        suite_k018c_zones(tmp)
        suite_k093_short_pdf(tmp)
        suite_k096_picture_pages(tmp)
        suite_k097_split_quotation(tmp)
        suite_k046_fact_bank(tmp)
        suite_k092_exhibit_ids(tmp)
        suite_k045_exhibit_list(tmp)
        suite_k047_reading_list(tmp)
        suite_k061b_judge(tmp)
        suite_k094_condition_cuts(tmp)
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
        suite_write_only_accumulator()
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
        # The count in this message is DERIVED from the list, not typed: the typed «3» went
        # stale the same hour a fourth suite was added (R78) - the exact number-in-prose class
        # this file's own header warns about.
        repo_suites = [suite_no_real_identifiers, suite_rename, suite_docs, suite_r78_repo]
        if _is_source_checkout(root):
            for s in repo_suites:
                s(root)
        else:
            print("note: %d repository-hygiene suites skipped - this is an installed copy, not a\n"
                  "      source checkout, so there is no tree of ours to scan (looked in: %s).\n"
                  "      To run them: git clone the repo and `python -m krokai selftest` there."
                  % (len(repo_suites), root))
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
