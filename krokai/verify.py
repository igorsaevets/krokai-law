# -*- coding: utf-8 -*-
"""The checker. One quotation in, one verdict out — the vocabulary is ``verdicts.ORDER``, and the
count is deliberately not written here: two modules carried two different stale counts for a
release while the list held a third (R76).

Reading order for this file: ``check()`` at the bottom is the decision tree; everything above it is
one test each. Every test carries the incident that produced it, because a rule whose reason is
lost gets "simplified" back out six months later by someone who cannot see what it was for.
"""
from __future__ import annotations

import difflib
import os
import re

from .normalize import (normalise, alnum, dehyph, editorial_marks, ellipsis_parts,
                        prepare_quote, source_marks, strip_all_marks, ELLIPSIS_RE)
from .verdicts import CLEAN

__all__ = ["check", "word_diff", "neighbours", "OPERATORS"]

# ------------------------------------------------------------------------------------------------
# Words whose loss or substitution inverts a legal sentence.
# ------------------------------------------------------------------------------------------------
OPERATORS = {
    "not", "no", "never", "unless", "except", "only", "may", "shall", "must", "and", "or",
    "any", "all", "before", "after", "without", "solely", "primarily", "less", "more", "least",
    "cannot",
    # Added after a measured miss: a conditional inverts a sentence exactly as "unless" does, and
    # every one of these was absent from the list while "and" was in it.
    "if", "when", "where", "while", "until",
    # Status words. Dropping the prefix is a one-character edit that reverses the holding.
    "unauthorized", "authorized", "ineligible", "eligible", "inadmissible", "admissible",
    "unlawful", "lawful", "undocumented",
}

# Multi-word limiters. `changed` holds single tokens, so these are matched against the JOINED
# changed span instead.
# 🔴 An earlier version listed the two-word entry "shall not" in the single-token set. Tokens are
# compared one at a time, so it could never match anything: dead code that read like a safety net.
# "shall" and "not" each fire on their own, which is what actually protects the sentence.
SCOPING = ["for purposes of", "within the meaning of", "as defined in", "subject to",
           "provided that", "except as", "in the case of", "pursuant to", "under this paragraph",
           "under this section", "other than", "not later than", "no later than"]

# A clause that NARROWS what precedes it. A quotation stopping immediately before one of these has
# kept the words and dropped the rule.
LIMITER_RE = re.compile(
    r"^(but|however|unless|except|provided|notwithstanding|although|though|nor|only|"
    r"other than|subject to|does not|do not|shall not|may not|cannot|is not|are not|"
    r"absent|save|to the extent)\b", re.I)

# Same idea for what an ellipsis swallows. Not every elision matters; these do.
# 🔴 R76: this list drifted BELOW `LIMITER_RE` — «although/though/nor/absent/save/to the
# extent/does not/do not/is not/are not» narrowed a tail but not a gap (grokbuild), and the
# article variants were half-covered: «if the» matched while «if an applicant» did not
# (lunapro). The condition words now take any of the three articles.
NARROWER_RE = re.compile(
    r"\b(but|however|unless|except|provided|notwithstanding|only|other than|subject to|"
    r"certain|specific|solely|for purposes of|does not include|do not include|shall not|"
    r"may not|although|though|nor|absent|save|to the extent|does not|do not|is not|are not|"
    r"(?:if|where|when)\s+(?:the|an?)\b)", re.I)

# 🔴 Words that REVERSE what follows them. A strict subset of OPERATORS, and the subsetting is the
# fix: "and"/"or"/"any" reverse nothing, and treating them as if they did buried the words that do
# under 254 false alarms in one run.
NEGATION = {"not", "no", "never", "unless", "except", "cannot", "without", "neither", "nor",
            "fails", "failed", "absent"}

# The source is RECITING someone - a commenter, a petitioner, a dissent. The words are real and the
# attribution is false. Advisory only: a well-drafted document may quote a commenter's objection on
# purpose and label it as such, and a blocking verdict there would be a false alarm.
SPEAKER_RE = re.compile(
    r"(Comment:|Commenters?\b|commenters? (stated|said|argued|asserted|suggested|requested|"
    r"expressed|noted|claimed|recommended|opposed)|[Pp]etitioner (contends|argues|stated)|"
    r"[Pp]laintiff (contends|argues|alleges)|dissent(ing)?\b|we reject|overruled by|"
    r"vacated by|superseded by|abrogated by)")
RESPONSE_RE = re.compile(r"(Response:|DHS responds|The (Service|Department) (agrees|disagrees)|"
                         r"We agree|We disagree|responds as follows)")

_STRIP = ".,;:()[]\"'`«»‘’“”"

# Projection used by the alphanumeric-branch boundary check: a token minus everything that is
# not a letter or digit. Distinct from `_STRIP`, which trims token EDGES only.
_ALNUM_ONLY = re.compile(r"[^0-9a-z]+")

# 🔴 Cite-token guard. `_STRIP` includes `(` and `)`, so `(b)(16)(i)` reaches `word_diff` as
# `b)(16)(i` — every character is still correct, but the digit rule below would promote it to
# OPERATOR by shape. That is the exact noise the digit rule exists to prevent from swallowing
# real signal. Match on the post-strip form.
#
# 🔴 REGEX MUST REQUIRE INTERNAL `)(` STRUCTURE.  Named by the T58 panel (Codex + Spark 11 +
# Spark 12 + agy 36flash converged). An earlier version `^\(?[a-z]{1,4}\)?(?:\(?[0-9ivxlcdm]
# {1,5}\)?)+$` matched anything of shape "letters + digits", including `v2`, `x64`, `a1`,
# `file1`, `test1`, `covid19`, `sec1` — non-citation labels whose edits are genuine and must
# stay in OPERATOR. Requiring at least one internal `)(` (paren-stripped `x)(y)` or whole
# `(x)(y)`) narrows to real citation shapes: `(a)(1)`, `(b)(16)(i)`, `b)(16)(i`, `b)(16)(ii`.
# Everything Codex named as a false positive fails this regex.
_CITE_TOKEN_RE = re.compile(
    r"^\(?[a-z]{1,4}\)\(?[a-z0-9ivxlcdm]{1,5}(?:\)\(?[a-z0-9ivxlcdm]{1,5})*\)?$",
    re.I,
)

# An extractor drops a footnote INTO the sentence it annotates. Measured on an agency memorandum:
# "...the applicant may [14 See Matter of Blas, 15 I&N Dec. at 628 (...)] need to offset...".
# That is damage to the corpus copy, not a change in the quotation, and it must not read as one.
#
# 🔴 R76 (grokbuild, confirmed by probe): the citation group used to be OPTIONAL, so a BARE
# 1-3 digit insertion matched too — and «within [90] days» with the 90 omitted from the
# quotation was silently excused as a welded footnote, never reaching the digit→OPERATOR rule.
# The group is now mandatory: a bare welded footnote number will surface as OPERATOR, which is
# a loud false alarm about corpus damage — and a loud false alarm beats a silent false green.
FOOTNOTE_RE = re.compile(r"^\d{1,3}\s+(see|id\.?|ibid|supra|cf\.?|infra|accord)\b", re.I)


# ------------------------------------------------------------------------------------------------
def word_diff(quote, src):
    """Word-level difference instead of a similarity percentage.

    🔴 THE 85 % THRESHOLD WAS SELF-DECEPTION, AND IT WAS KILLED BY ARITHMETIC.

    A percentage cannot see negation. A 50-word quotation yields 45 overlapping 6-word shingles;
    inserting ONE word breaks at most 6 of them, so 39/45 = **86.6 %**, which clears an 85 %
    threshold. That is how ``shall`` -> ``shall not`` got filed under "typesetting artefact". All
    four independent reviewers flagged the same threshold, and the arithmetic settled it.

    Shingles now only **locate** a passage. Classification is this function's job.

    Returns `(changed_tokens, operator_hits, alignment_failed)`.

    🔴 The head/tail hole. An earlier version kept only the differences BETWEEN the first and last
    anchor, to ignore the deliberate overhang of the source window. That also hid every change in
    the QUOTATION's own tail - the single most valuable diagnosis this tool produces. All four
    reviewers stated the bug too broadly ("blind to changes at the start"); running the test showed
    the start is caught and only the **tail** is invisible. So: an out-of-span difference is kept
    when it consumes QUOTATION tokens, and dropped only when it is pure source overhang.
    """
    a = [w.strip(_STRIP).lower() for w in quote.split()]
    b = [w.strip(_STRIP).lower() for w in src.split()]
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    anchors = [k for k, o in enumerate(ops) if o[0] == "equal" and o[2] - o[1] >= 2]
    if not anchors:
        return ["<did not align>"], [], True
    lo, hi = anchors[0], anchors[-1]

    changed = []
    for k, (tag, i1, i2, j1, j2) in enumerate(ops):
        if tag == "equal":
            continue
        if (k < lo or k > hi) and i2 == i1:
            continue                       # pure source overhang outside the alignment: not ours
        ins = " ".join(b[j1:j2])
        if i2 == i1 and FOOTNOTE_RE.match(ins):
            continue                       # a footnote welded into the sentence by the extractor
        changed += [w for w in a[i1:i2] + b[j1:j2] if w and any(c.isalnum() for c in w)]

    hits = {w for w in changed if w in OPERATORS}
    span = " ".join(changed)
    hits |= {p for p in SCOPING if p in span}
    # 🔴 A changed token carrying a digit is a date, a threshold, or a paragraph number. Losing one
    # is never typography: "for the 2021-22 academic year" was once scored a minor difference.
    #
    # 🔴 EXCEPT when a citation-shaped token is IDENTICAL on both sides. The AOS observation was
    # that `(b)(16)(i)` in a span with other changes could end up in `changed` via alignment
    # cascade and get falsely promoted to OPERATOR. Sound guard: exclude a cite-shaped token
    # from OPERATOR only if the SAME token exists on the OTHER side (an alignment artifact,
    # not a real cite change). Codex T58 rejected the earlier blanket guard as a regression —
    # `(b)(16)(i)` → `(b)(16)(ii)` is a real pincite change and MUST stay OPERATOR-severity.
    q_cites = {w for w in a if _CITE_TOKEN_RE.match(w) and any(ch.isdigit() for ch in w)}
    s_cites = {w for w in b if _CITE_TOKEN_RE.match(w) and any(ch.isdigit() for ch in w)}
    identical_cites = q_cites & s_cites
    hits |= {w for w in changed
             if any(ch.isdigit() for ch in w)
             and not (_CITE_TOKEN_RE.match(w) and w in identical_cites)}
    return changed, sorted(hits), False


def _alnum_span(quote_n, path, corpus):
    """Map an alphanumeric-index hit back to the RAW source span that produced it.

    Returns ``(start, end, src)`` — offsets into ``src = corpus.text_of(path)`` — or ``None``.
    Extracted from ``_punctuation_detail`` in R76 because the located span is what lets the
    PUNCTUATION branch ask the questions the exact branch asks: what follows the span (a
    limiter?), what precedes it (a negation?), and whether the words inside it really are the
    same words (``word_diff``), rather than merely the same letters.
    """
    src = corpus.text_of(path)
    a = alnum(quote_n)
    i = alnum(src).find(a)
    if i < 0:
        return None
    # Walk the source, counting alphanumerics, to find the span that produced the match.
    seen, start, end = 0, None, None
    for k, ch in enumerate(src):
        if ch.isalnum():
            if seen == i:
                start = k
            seen += 1
            if seen == i + len(a):
                end = k + 1
                break
    if start is None or end is None:
        return None
    return start, end, src


def _punctuation_detail(quote_n, path, corpus):
    """Say WHAT the punctuation difference is.

    A bare "punctuation differs" is technically true and practically useless - the reader still has
    to diff it by hand, so they do not, and the finding is skipped. Measured on the first real run:
    a quotation spanning two bullets of a list in an agency manual, where the source has a `*` list
    marker between them that the drafter silently swallowed. Quoting across list items without
    marking the elision is a real (small) defect, and naming the character is what makes it fixable
    in five seconds.
    """
    span = _alnum_span(quote_n, path, corpus)
    if span is None:
        return ""
    start, end, src = span
    src_span = src[start:end]
    qp = [c for c in quote_n if not c.isalnum() and not c.isspace()]
    sp = [c for c in src_span if not c.isalnum() and not c.isspace()]
    extra = sorted(set(sp) - set(qp))
    missing = sorted(set(qp) - set(sp))
    bits = []
    if extra:
        bits.append("the source also has %s" % " ".join("`%s`" % c for c in extra[:6]))
    if missing:
        bits.append("our quotation adds %s" % " ".join("`%s`" % c for c in missing[:6]))
    if not bits:
        bits.append("spacing only")
    return "; ".join(bits)


def truncation_anywhere(quote_n, corpus):
    """Ask the truncation question about a quotation that is NOT an exact substring.

    🔴🔴 THE DEFECT THIS EXISTS FOR (measured 2026-08-19, present since the verdict tree was
    written). `truncated_condition` needs an exact hit, so it could only ever run on the
    exact-match branch. Every other route to a green verdict - PUNCTUATION, TYPESETTING, the
    shingle path - returned without ever asking whether the source continues with a limiter.
    That is not a guard on the verdict, it is a guard on one branch, and the difference
    between them is one character:

        the quotation as-is                -> TRUNCATED_CONDITION   loud, correct
        the same + a trailing full stop    -> PUNCTUATION           green
        the same + a line-break hyphen     -> PUNCTUATION           green

    The mechanism is that `alnum` drops ALL punctuation, so the alphanumeric index cannot
    tell "the same words with a comma moved" from "a PREFIX of the words, stopped before the
    proviso" - both are substrings of the same haystack. Ending a quotation with a full stop
    is the ordinary thing a drafter does, so the laundering needed no ill intent and left no
    trace.

    Worse than silence: `_punctuation_detail` then printed «our quotation adds `.`» - a
    precise, confident explanation of the WRONG difference, which is what makes a reader stop
    looking. A vaguer message would have done less damage.

    The repair introduces no new detector and no new class of alarm. It asks the EXISTING
    question on the projections that produced the match: strip the trailing punctuation the
    quoter added, heal a line-break hyphen, and if that lands on an exact span, the original
    guard applies unchanged.
    """
    # 🔴 FOUND BY THE REVIEW PANEL THAT REVIEWED THIS VERY FIX (7 of 13 channels converged,
    # reproduced by execution before it was believed). Stripping trailing punctuation also
    # eats a trailing ELLIPSIS - and an ellipsis is the drafter DISCLOSING the elision. The
    # first version of this helper reported «An applicant must file … the qualifying event…»
    # as TRUNCATED_CONDITION, i.e. it shouted equally loudly at honest citation practice and
    # at silent truncation, which destroys the distinction the verdict exists to draw.
    # A disclosed elision belongs to the ellipsis machinery below, which already asks what was
    # hidden (NARROWER_RE) - so hand it back rather than pre-empting it.
    # 🔴 v0.8.4: was `endswith(("...", "…"))`, which cannot see the Bluebook spaced form `. . .`.
    # Ends-with on a fixed pair of literals is the same class of mistake as the rest of this file:
    # a question about a CONCEPT answered by listing two of its spellings. ELLIPSIS_RE is the one
    # definition; `_TAIL_ELLIPSIS_RE` below anchors it to the end.
    if _TAIL_ELLIPSIS_RE.search(quote_n or ""):
        return None, None, None
    seen = set()
    for cand in (quote_n,
                 quote_n.rstrip(" .,;:!?»”\"'"),
                 dehyph(quote_n),
                 dehyph(quote_n).rstrip(" .,;:!?»”\"'")):
        cand = cand.strip()
        if len(cand) < 25 or cand in seen:
            continue
        seen.add(cand)
        p, limiter, tail = truncated_condition(cand, corpus)
        if p:
            return p, limiter, tail
    return None, None, None


def truncated_condition(quote_n, corpus, restrict_to=None):
    """Does an exactly-matching quotation stop right before the clause that limits it?

    Two independent signals, and **both** are required, because either alone cries wolf:

    1. the quotation does not end at a sentence boundary, and
    2. what follows it in the source opens with a limiter.

    Checked at EVERY occurrence: the same sentence lives in several preambles, and the first hit is
    not necessarily the copy that was quoted.

    ``restrict_to``: when given, only check occurrences in these paths. Used by
    ``tail_elision_hides`` to anchor the search to files where earlier fragments were found,
    preventing a short last fragment from matching in an unrelated statute (AOS R71, v2.8.5).
    """
    q = quote_n.rstrip()
    if q[-1:] in ".?!":
        return None, None, None                # a complete sentence: nothing was cut off
    for path, off in corpus.find_all_pos(quote_n):
        if restrict_to is not None and path not in restrict_to:
            continue
        tail = corpus.after(path, off, len(quote_n))
        if not tail:
            continue
        # 🔴 strip_all_marks BEFORE the limiter question (R78, probe-proven): a source-side
        # «[sic]» between the quotation's end and «, unless …» made the tail start with `[`,
        # LIMITER_RE saw no limiter, and a silent truncation was graded VERIFIED.
        nxt = strip_all_marks(tail).lstrip(" ,;:-")
        m = LIMITER_RE.match(nxt)
        if m:
            return path, m.group(0), " ".join(nxt.split()[:26])
    return None, None, None


_TAIL_ELLIPSIS_RE = re.compile(r"(?:%s)\s*[»\"'”)\]]*\s*$" % ELLIPSIS_RE.pattern)


def tail_elision_hides(quote_n, quote_raw, corpus):
    """The elision nobody looks at: the one at the END of the quotation.

    🔴🔴 THE DEFECT, and it is one I introduced myself. Measured 2026-08-19.

    ``Corpus.gaps`` computes ``for k in range(len(parts) - 1)`` - the spans BETWEEN fragments.
    A quotation that ENDS with an ellipsis has elided the TAIL of the sentence, and a tail is
    not between anything, so no gap is ever computed for it and ``NARROWER_RE`` never sees it.
    Worse, ``check`` only enters the ellipsis section when ``len(parts) > 1``, and a quotation
    that merely ends with an ellipsis yields ONE fragment - so it did not reach that machinery
    at all and fell through to PUNCTUATION, green.

    In legal drafting the proviso is at the END of the sentence: "..., provided that",
    "..., unless", "..., except that", "... subject to". The one elision position the
    instrument did not examine is the position where the limiter almost always is.

    Demonstrated with one variable - where the ellipsis sits, same hidden words, same source:

        «An applicant must file … and the Secretary may extend»  -> ELLIPSIS_HIDES   loud
        «An applicant must file …»                              -> PUNCTUATION      GREEN

    🔴 AND THE GREEN ONE EXPLAINED ITSELF WRONGLY: «our quotation adds `.`». That is the R50
    defect verbatim - a confident description of the WRONG difference, which is what stops a
    reader looking. It was reintroduced by the v0.8.2 fix: that fix correctly stopped calling a
    disclosed elision TRUNCATED_CONDITION (the review panel was right), but the comment
    justifying it said the case "belongs to the ellipsis machinery below", and the machinery
    below could not be reached. A claim about control flow that was never executed.

    The repair keeps BOTH findings. A disclosed elision is not silent truncation, so the verdict
    is not TRUNCATED_CONDITION; but what it hides can still narrow the rule, so it is not
    silence either. It is the ELLIPSIS verdict, which exists for exactly this.

    MEASURED ON A REAL FILING before it was believed - 1 118 quotations that end in an ellipsis:
    552 already loud, 539 stay green, and 26 turn loud (2.3% of the population). Read by eye,
    all 26 hide a real carve-out: "employee means an individual..." hiding "but does not mean
    independent contractors"; "No appeal lies from the denial..." hiding "but the applicant
    retains the right to renew"; "Applications that are rejected and returned..." hiding "do
    not retain a filing date".

    The 25-character floor is not a threshold invented for this check. A 27th alarm read
    «(ii) Physicians working in shortage areas ... (I) In general...», whose last fragment is a
    14-character heading that occurs all over the U.S. Code - so the locator matched a different
    statute and reported the continuation of the wrong place. That is the short-fragment problem
    ``ellipsis_parts`` already documents, and 25 is already this codebase's floor for "this
    fragment proves something on its own". Applying it removes exactly that one alarm and no
    other.
    """
    if not (_TAIL_ELLIPSIS_RE.search(quote_n or "")
            or _TAIL_ELLIPSIS_RE.search(quote_raw or "")):
        return None, None, None
    parts = ellipsis_parts(quote_n, 10)
    if not parts:
        return None, None, None
    last = parts[-1]
    # 🔴 AOS R71 (v2.8.5): anchor the search to files where EARLIER fragments were found.
    # Without this, a 25-character last fragment like "the Secretary may" matches in an unrelated
    # statute, the locator finds a limiter in the wrong place, and the verdict is a false
    # ELLIPSIS_HIDES. Proven by probe_d6_false_negative.py (AOS R70) and confirmed by a
    # 12-channel panel: grok420 + agy37flash found the same scenario independently.
    anchor_files = set()
    for p in parts[:-1]:
        if len(p) >= 10:
            for hit_path, _ in corpus.find_all_pos(p, cap=5):
                anchor_files.add(hit_path)
    if len(last) < 25:
        # 🔴 R76 (spark11, confirmed by probe P5): a last fragment of 10-24 characters is KEPT
        # by `ellipsis_parts` (floor 10) yet used to be DECLINED here (floor 25) - so a hidden
        # «, unless …» after a 21-character tail sailed through to ASSEMBLED, green. The R56
        # six-shape enumeration never tried that window. The 25-floor exists because a short
        # fragment matches everywhere; the ANCHOR removes that ambiguity, so a short tail is
        # checked when anchors exist and declined only when there is nothing to anchor to -
        # in which case the whole quotation is one short fragment and comes back NOT_FOUND.
        if not anchor_files:
            return None, None, None
        return truncated_condition(last, corpus, restrict_to=anchor_files)
    return truncated_condition(last, corpus,
                               restrict_to=anchor_files or None)


def tail_short_enough_to_decline(quote_n, quote_raw):
    """True when the last fragment of a tail-ellipsis quotation is under the 25-character floor.

    🔴🔴 SUPERSEDED IN R76 — THE R56 CLAIM «THE DECLINE CANNOT BE REACHED WITH A CLEAN VERDICT»
    WAS WRONG, AND THE ERROR WAS IN THE ENUMERATION, NOT THE REASONING. R56 ran six shapes and
    every one came back loud, so the floor was called belt-over-braces and no disclosure
    shipped. The six shapes never tried a last fragment of 10-24 characters: long enough for
    ``ellipsis_parts`` (floor 10) to KEEP it, short enough for the old tail check (floor 25) to
    DECLINE it. spark11 named that window in R76 and probe P5 confirmed it by execution — a
    21-character tail hiding «, unless …» came back ASSEMBLED, green, unexamined. R56's own
    hedge («a claim about six synthetic shapes, not about filings») was the honest sentence in
    the paragraph.

    The R76 repair changes what this predicate means: ``tail_elision_hides`` now ANCHORS a
    short last fragment to the files where the earlier fragments were found and asks
    ``truncated_condition`` there — the anchor removes the matches-everywhere ambiguity that
    justified the floor. The check declines only when there is nothing to anchor to, i.e. the
    whole quotation is one short fragment, which cannot be located and comes back NOT_FOUND
    (loud). This predicate still answers only «is the tail under the floor», which is now a
    precondition of the decline, not the decline itself; ``suite_r51_tail_elision`` pins the
    new behavior — a sub-25 anchored tail hiding a limiter must come back ELLIPSIS_HIDES.
    """
    if not (_TAIL_ELLIPSIS_RE.search(quote_n or "")
            or _TAIL_ELLIPSIS_RE.search(quote_raw or "")):
        return False
    parts = ellipsis_parts(quote_n, 10)
    return bool(parts) and len(parts[-1]) < 25


def _negation_in_head(quote_n, head):
    """The core of ``leading_cut``, on an already-located head. Returns ``(bad, cut)`` or
    ``(None, None)``. Split out in R76 so the alphanumeric branch can ask the same question
    about the span it located - the detector logic exists once."""
    if not head:
        return None, None
    if quote_n[:1].isupper() and head.rstrip().endswith((".", "!", "?", ":")):
        return None, None                      # our quotation starts a sentence: nothing precedes
    cut = re.split(r"(?<=[.!?])\s+", head)[-1]
    toks = [w.strip(_STRIP).lower() for w in cut.split()][-6:]
    bad = sorted({w for w in toks if w in NEGATION})
    if bad:
        return ", ".join(bad), " ".join(cut.split())[-140:]
    return None, None


def leading_cut(quote_n, corpus, restrict_to=None):
    """The mirror image. An exact substring can invert its own meaning by starting one word too
    late: the negation stands in FRONT of it, not behind.

    🔴 Two calibrations, both measured. Accepting any operator (including "and" and "or") produced
    **254 hits** - noise, not findings; only a NEGATION reverses what follows it. And it has to be
    NEAR: six tokens, not fourteen, or a "not" at the head of a long clause claims a span it does
    not govern.

    ``restrict_to``: only consider occurrences in these paths - used by ``address.fold`` (R76) to
    ask the question at the CITED file before an anchor-miss repair may upgrade a verdict.
    """
    for path, off in corpus.find_all_pos(quote_n):
        if restrict_to is not None and path not in restrict_to:
            continue
        bad, cut = _negation_in_head(quote_n, corpus.before(path, off, 220))
        if bad:
            return path, bad, cut
    return None, None, None


def neighbours(quote, corpus, cap=3, window=420):
    """The sentence before and the sentence after a located quotation, in the source's own words.

    Returns `[(path, before, after), ...]`, one entry per occurrence, `cap` at most.

    🔴 WHY THIS IS NOT THE SAME THING AS ``truncated_condition``, WHICH ALREADY EXISTS.
    That function decides, and it decides conservatively: it fires only when the quotation stops
    mid-sentence AND the next words open with one of a listed set of limiters. It is a **detector**,
    so it must not cry wolf, so it is deliberately narrow. This is not a detector. It hands a person
    the two sentences and lets them read - which catches the whole class the detector's word list
    does not contain, at the cost of catching nothing on its own.

    Both are needed and neither replaces the other. Measured in a sister project the day the
    equivalent was built: the very first entry it was pointed at was a regulation quoted up to
    ``...before the decision is rendered``, immediately followed in the source by
    ``, except as provided in paragraphs (b)(16)(ii), (iii), and (iv) of this section``. Reading the
    exceptions showed the conclusion survived - but "the conclusion survives" was a guess until
    somebody opened them, and nothing in the pipeline had ever asked.

    🔴 It is offered for a VERIFIED quotation, which is the counter-intuitive part and the point. A
    flagged quotation already sends you to the source. A verified one is the one you stop looking at.

    Same preparation as `check`, and for the same reason: `krokai quote` calls both with the user's
    raw text, so a difference between them shows up as "the checker found it and the neighbours are
    blank" - which reads as "there is nothing after it" and is the opposite of the truth.

    🔴 Which is exactly what happened when `check` learned the marks-kept second pass and this
    function did not (R78 panel): a source-``[sic]`` quotation verified through the kept pass,
    then neighbours searched the STRIPPED string, found nothing, and printed nothing - for the
    verdict whose whole reason to show neighbours is that nobody re-opens it. Same fallback,
    same gate.
    """
    n = normalise(prepare_quote(quote))
    if not corpus.find_all_pos(n, cap=1) and source_marks(quote):
        n = normalise(prepare_quote(quote, keep_tags=True))
    out = []
    for path, off in corpus.find_all_pos(n, cap=cap):
        head = corpus.before(path, off, window)
        tail = corpus.after(path, off, len(n), window)
        # Last complete sentence before; first complete sentence after. A leading fragment is dropped
        # rather than shown, because half a sentence out of context is how a reader is misled by a
        # tool that was trying to help.
        prev = [s for s in re.split(r"(?<=[.!?;:])\s+", head) if s.strip()]
        nxt = re.split(r"(?<=[.!?])\s+", tail.lstrip(" ,;:-"))
        before = " ".join(prev[-1].split()) if len(prev) > 1 else ""
        after = " ".join(nxt[0].split()) if nxt else ""
        out.append((path, before, after))
    return out


def wrong_speaker(quote_n, corpus):
    """Is the span sitting inside a recital rather than in the source's own voice?

    A rulemaking preamble quotes objections it then rejects. A decision recites the losing party's
    argument. Quoting those as the authority's holding is a real and common error - and it is
    advisory here, not blocking, because quoting a commenter *and saying so* is legitimate.
    """
    for path, off in corpus.find_all_pos(quote_n, cap=8):
        head = corpus.before(path, off, 1400)
        last_speaker = last_response = None
        for m in SPEAKER_RE.finditer(head):
            last_speaker = m.start()
        for m in RESPONSE_RE.finditer(head):
            last_response = m.start()
        if last_speaker is not None and (last_response is None or last_speaker > last_response):
            return path, " ".join(head[last_speaker:last_speaker + 120].split())
    return None, None


# ------------------------------------------------------------------------------------------------
def _check_inner(quote, corpus, keep_tags=False):
    """Return `(verdict, path_or_None, detail)`.

    The order of the tree is the design. An exact match is tested first and then **immediately
    interrogated for completeness**, because "it is an exact substring" is the answer that hides the
    two most expensive defects. Only after that do the near-miss classifiers run, cheapest first.

    🔴 `prepare_quote` is called HERE rather than trusted to the callers. It used to be applied by
    `extract_quotes` and by `bank`, and simply not applied by `krokai quote` - so the same text got
    different verdicts depending on which door it came through. A rule that every caller must
    remember is a rule that one caller will forget, and this one had.

    ``keep_tags`` is `check()`'s second pass: the ``[sic]`` a court prints on its own page must
    stay in the quotation to match. See the note in `check()` below.
    """
    quote = prepare_quote(quote, keep_tags=keep_tags)
    n = normalise(quote)
    if not n:
        return "NOT_FOUND", None, ""

    # --- exact hit: now prove it is also COMPLETE and IN ITS OWN VOICE ---------------------------
    hit = corpus.find(n)
    if hit:
        p, limiter, tail = truncated_condition(n, corpus)
        if p:
            return "TRUNCATED_CONDITION", p, "the source continues: «%s…»" % tail
        p2, bad, head = leading_cut(n, corpus)
        if p2:
            return ("TRUNCATED_OPENING", p2,
                    "immediately before it in the source: «…%s» (governing words: %s)"
                    % (head, bad))
        p3, who = wrong_speaker(n, corpus)
        if p3:
            return ("WRONG_SPEAKER", p3,
                    "advisory: the span follows «%s» - check that our text says this is "
                    "not the authority's own position" % who)
        return "VERIFIED", hit, ""

    # --- ellipsis quotation ----------------------------------------------------------------------
    parts = ellipsis_parts(n, 10)
    short = [p for p in parts if len(p) < 25]
    # 🔴🔴 R51. Stands BEFORE the `len(parts) > 1` gate on purpose, because the case it exists for
    # is the case that gate excludes: a quotation ending in an ellipsis has ONE fragment. It also
    # covers a MULTI-fragment quotation that ends in an ellipsis, whose tail no gap reaches either.
    tp, _tlim, ttail = tail_elision_hides(n, quote, corpus)
    if tp:
        return "ELLIPSIS_HIDES", tp, ("the elision at the END hides: «%s…»"
                                      % " ".join(ttail.split())[:200])
    if (ELLIPSIS_RE.search(n) or ELLIPSIS_RE.search(quote or "")) and len(parts) > 1:
        one, offs = corpus.all_in_order(parts)
        if one:
            gaps = corpus.gaps(one, parts, offs)
            material = [g for g in gaps if g and NARROWER_RE.search(g)]
            widest = max([len(g) for g in gaps] or [0])
            if material or widest > 800:
                why = ("the ellipsis hides: «%s»"
                       % " ⟂ ".join(g[:160] for g in material[:2]) if material else "")
                if widest > 800:
                    why = (why + "; " if why else "") + (
                        "%d characters elided - that is not shortening a phrase" % widest)
                return "ELLIPSIS_HIDES", one, why
            note = ("; %d short fragment(s) checked for position only" % len(short)) if short else ""
            if gaps:
                return "ASSEMBLED", one, ("hidden: «%s»"
                                          % " ⟂ ".join(g[:90] for g in gaps[:2])) + note
            return "ASSEMBLED", one, note.lstrip("; ")
        hits = [corpus.find(p) for p in parts]
        if all(hits):
            return "SPLICED", hits[0], "the fragments exist, but no one document holds them in order"
        if any(hits):
            miss = [i + 1 for i, h in enumerate(hits) if not h]
            return "ALTERED", next(h for h in hits if h), (
                "fragment(s) %s of %d not present verbatim" % (", ".join(map(str, miss)), len(parts)))

    # --- the SOURCE is line-broken, our quotation is fine -----------------------------------------
    # A line-break hyphen in the source ("inadmis-\nsibility") makes a perfect quotation fail. That
    # is damage to the corpus copy; calling it "fix before filing" would be a false alarm.
    #
    # 🔴 This runs BEFORE the punctuation test, and the order is deliberate. Folding hyphens is a
    # strict subset of what the alphanumeric index forgives, so a hyphen-only difference matches
    # both - and if the looser test runs first it wins, and the user is told "punctuation drifted"
    # (your problem) instead of "the source is line-broken" (the corpus's problem). Same evidence,
    # opposite instruction. Narrower diagnosis first.
    hh = corpus.find_hyph(dehyph(n))
    if hh:
        # 🔴 Guard first, THEN diagnose. A word broken across a line is the corpus copy's
        # problem; a clause cut off before its proviso is ours, and ours outranks.
        tp, _lim, ttail = truncation_anywhere(n, corpus)
        if tp:
            return "TRUNCATED_CONDITION", tp, "the source continues: «%s…»" % ttail
        return "TYPESETTING", hh, "word broken across a line in the source"

    # --- same words, drifted punctuation ----------------------------------------------------------
    # 🔴 AOS R66-D4 (panel 5/11 HIGH): an ellipsis quotation must NOT enter this branch.
    # `alnum()` strips ALL punctuation including the ellipsis, so "A ... B" becomes "AB" and
    # falsely matches as PUNCTUATION — a green verdict on a quotation that silently skipped text.
    a = alnum(n)
    if len(a) >= 30 and not ELLIPSIS_RE.search(n):
        hit = corpus.find_alnum(a)
        if hit:
            # 🔴 See truncation_anywhere(). The alphanumeric index cannot distinguish a
            # punctuation drift from a PREFIX that stops before the limiting clause, so the
            # truncation question must be asked before this branch may call itself green.
            tp, _lim, ttail = truncation_anywhere(n, corpus)
            if tp:
                return "TRUNCATED_CONDITION", tp, "the source continues: «%s…»" % ttail
            # 🔴 R76 (probes P3/P4/P7): `truncation_anywhere` needs one of its four projections
            # to be an EXACT substring, so an INTERNAL punctuation drift defeated it - and this
            # branch also never asked about a leading negation or about word boundaries. Three
            # measured launderings through one door: drift+truncation -> green; a cut leading
            # «no» + drift -> green; «no table» quoted from «not able» -> green «spacing only».
            # The located span lets the branch ask the exact branch's questions at the exact
            # branch's cost. First occurrence only - the same limitation `_punctuation_detail`
            # always had.
            span = _alnum_span(n, hit, corpus)
            if span:
                start, end, src = span
                # Same strip_all_marks guard as truncated_condition - this is the second of the
                # two call sites that ask "does a limiter follow", and the R78 probe reddened
                # both (the branch-counting lesson: a guard on one branch of two is half a guard).
                nxt = strip_all_marks(src[end:end + 220]).lstrip(" ,;:-")
                m = LIMITER_RE.match(nxt)
                if m:
                    return ("TRUNCATED_CONDITION", hit,
                            "the source continues: «%s…»" % " ".join(nxt.split()[:26]))
                bad, cut = _negation_in_head(n, src[max(0, start - 220):start])
                if bad:
                    return ("TRUNCATED_OPENING", hit,
                            "immediately before it in the source: «…%s» (governing words: %s)"
                            % (cut, bad))
                # Word-BOUNDARY check, not a word check: the span's letters equal the
                # quotation's by construction, so the only real question is whether the
                # SPACES moved. Intra-token punctuation («non-immigrant» vs «nonimmigrant»)
                # is forgiven - both project to one token - or the common style variant
                # would come back as a loud false alarm.
                qtoks = [t for t in (_ALNUM_ONLY.sub("", w.lower()) for w in n.split()) if t]
                stoks = [t for t in (_ALNUM_ONLY.sub("", w.lower())
                                     for w in src[start:end].split()) if t]
                if qtoks != stoks:
                    changed, hitwords, unaligned = word_diff(n, src[start:end])
                    if not unaligned:
                        if hitwords:
                            return "OPERATOR", hit, ", ".join(hitwords)
                        if changed:
                            return ("ALTERED", hit,
                                    "same letters, different word boundaries: %s"
                                    % ", ".join(sorted(set(changed))[:8]))
            return "PUNCTUATION", hit, _punctuation_detail(n, hit, corpus)

    # --- every sentence verbatim, but not adjacent -------------------------------------------------
    sents = [x.strip() for x in re.split(r"(?<=[.;:])\s+(?=[A-Z(])", n)]
    sents = [x for x in sents if len(x) >= 40]
    if len(sents) >= 2:
        where = [corpus.find(s) or corpus.find_alnum(alnum(s)) for s in sents]
        if all(where):
            # 🔴 R76 (codex + goog37flash, confirmed by probe P10): SCATTERED's meaning says
            # «not adjacent in the source», singular - but nothing required one source. Two
            # sentences from two DIFFERENT files read as an intra-document rearrangement when
            # they are a cross-document splice, which is SPLICED's own definition.
            if len(set(where)) > 1:
                return ("SPLICED", where[0],
                        "each sentence is verbatim in a DIFFERENT document: %s"
                        % ", ".join(sorted({os.path.basename(w) for w in where})))
            return "SCATTERED", where[0], ""

    # --- the opening is present and the whole is not => the TAIL was changed -----------------------
    #
    # 🔴 IMPROVEMENT OVER THE ORIGINAL. The original returned ALTERED here and stopped, and ALTERED
    # is true but nearly useless: "something after the halfway mark differs". If the thing that
    # differs is `not`, the reader needs to be told *that*, not sent to diff it by hand. So the
    # word-level comparison runs at the anchor and upgrades the verdict when a load-bearing word was
    # touched. Caught by the self-test: an inserted negation was being reported as ALTERED.
    words = n.split()
    half = " ".join(words[: max(6, len(words) // 2)])
    if len(half) >= 30:
        hit, hpos = corpus.find_pos(half)
        if not hit:
            hit = corpus.find_alnum(alnum(half))
            hpos = -1
        if hit:
            if hpos >= 0:
                changed, hitwords, unaligned = word_diff(
                    n, corpus.window(hit, hpos, len(n)))
                if hitwords and not unaligned:
                    return "OPERATOR", hit, ", ".join(hitwords)
            return "ALTERED", hit, ""

    # --- locate by shingles, then CLASSIFY by word diff --------------------------------------------
    if len(words) >= 12:
        sh = [" ".join(words[i:i + 6]) for i in range(len(words) - 5)]
        step = max(1, len(sh) // 9)
        sample = sh[::step][:9]
        hits = [corpus.find_pos(s) for s in sample]
        frac = sum(1 for p, _ in hits if p) / float(len(sample))
        if not frac:
            frac = sum(1 for s in sample if corpus.find_alnum(alnum(s))) / float(len(sample))
        anchor = next(((p, o) for p, o in hits if p), (None, -1))
        if frac >= 0.5 and anchor[0]:
            changed, hitwords, unaligned = word_diff(
                n, corpus.window(anchor[0], anchor[1], len(n)))
            if unaligned:
                # 🔴 An earlier version returned PARTIAL here, which reads as "mostly fine". It is
                # the opposite: half the shingles are present and the words will not line up at all.
                return "PARTIAL", anchor[0], "did not align - read it with your own eyes"
            if hitwords:
                return "OPERATOR", anchor[0], ", ".join(hitwords)
            if not changed:
                # The last route by which a green verdict can be issued without the
                # truncation question. Expected to fire rarely - reaching here means no
                # exact, alnum or dehyph span matched, so truncation_anywhere usually finds
                # nothing. It is here so the rule reads "no green without the guard", with no
                # exception a future reader has to rediscover the hard way.
                tp, _lim, ttail = truncation_anywhere(n, corpus)
                if tp:
                    return "TRUNCATED_CONDITION", tp, "the source continues: «%s…»" % ttail
                return "TYPESETTING", anchor[0], ""
            return "PARTIAL", anchor[0], ", ".join(sorted(set(changed))[:8])
        if frac >= 0.5:
            return "PARTIAL", None, ""

    # 🔴 AOS R66-O4: large shingle search BEFORE declaring NOT_FOUND. A long quotation whose
    # full text is absent may still have 8-16 word chunks present verbatim — an outdated edition
    # of a regulation, a corpus gap, or a silent splice without ellipsis. Declaring NOT_FOUND —
    # this tool's fabrication signal — without checking costs a public accusation that may be
    # wrong. Five of eight NOT_FOUND entries in the sister project were later found to be
    # "source not downloaded", not fabrications.
    hits = _fragment_hits(n, corpus)
    if hits:
        hosts = sorted({p for _, p in hits})
        return "FRAGMENTS", hits[0][1], (
            "%d large shingle(s) (>=%d words) found in the corpus, full quotation not. "
            "Documents with fragments: %d. Read the six causes of a false NOT_FOUND before "
            "concluding fabrication; found: %s"
            % (len(hits), 8, len(hosts),
               " | ".join("'%s'" % s[:80].replace("\n", " ")
                          for s, _ in hits[:3])))

    return "NOT_FOUND", None, ""


def _fragment_hits(text, corpus, min_words=8, min_chars=40, max_hits=5):
    """Large shingles that exist verbatim in the corpus, searched before NOT_FOUND.

    Sizes 16, 12, 10, 8 — largest first. A 16-word hit covers several 8-word windows, so
    ``used_ranges`` prevents double counting. ``max_hits=5`` caps the report: five places
    already show whether the quotation is fragmentary or absent.
    """
    if not text:
        return []
    words = text.split()
    if len(words) < min_words:
        return []
    hits = []
    used_ranges = []
    for size in (16, 12, 10, min_words):
        if size < min_words:
            continue
        for i in range(len(words) - size + 1):
            j = i + size
            if any(a < j and i < b for a, b in used_ranges):
                continue
            shingle = " ".join(words[i:j])
            if len(shingle) < min_chars:
                continue
            p = corpus.find(shingle) or corpus.find_alnum(alnum(shingle))
            if p:
                hits.append((shingle, p))
                used_ranges.append((i, j))
                if len(hits) >= max_hits:
                    return hits
    return hits


def check(quote, corpus, *a, **kw):
    """`_check_inner`, plus the two questions the text comparison cannot ask: did an editorial
    mark belong to the source, and is the file it found still the edition in force?

    🔴 This wraps rather than edits the comparison on purpose. The words really ARE in that file -
    that part of the answer is correct and must not be thrown away - and the superseded fact lives
    in the law register, which is not the corpus's business to parse. Wrapping keeps one place where
    the text question is answered and one place where the edition question is.

    It is applied HERE and not in the report, because a check that runs outside the path it protects
    is decorative: the hooks and the reviewer-answer audit call `check()` directly and would
    otherwise keep grading superseded law as clean.

    🔴 THE ``[sic]`` THAT IS THE SOURCE'S OWN TEXT (R78, probe-proven). ``strip_markdown`` cuts
    the editorial marks from the quotation because the common case is the drafter's annotation,
    which is in no source. But a court reciting a government typo prints ``[sic]`` on its own
    page, and a FAITHFUL quotation of that page came back PARTIAL - the tool punished exactly
    the practice it exists to protect. So: when EDITORIAL-class marks were present and the
    stripped comparison is not clean, one more pass runs with those marks kept. A quotation
    that OMITS the source's ``[sic]`` has no marks to keep, retries nothing, and stays loud -
    cutting a character of the source is still a report-worthy difference.

    🔴 THREE CONSTRAINTS ON THE SECOND PASS, each one a refuted laundering (R78 panel,
    probe-proven before repair):
      * gate on ``source_marks`` (the ``[sic]`` family), never on provenance tags - a
        ``[OPENED]`` colliding with the real word *opened* laundered a missing-word PARTIAL
        into a green PUNCTUATION whose note then claimed the tag was "the source's own text";
      * the win set is the EXACT-ANCHORED verdicts only (VERIFIED, WRONG_SPEAKER, and the two
        truncations) - a promotion through the forgiving alnum branch is what made that
        laundering possible, and a truncation found by the kept pass is the sharper diagnosis,
        not a defeat (a source-``[sic]`` quotation cut before its proviso must say
        TRUNCATED_CONDITION, not the stripping artifact PARTIAL);
      * the kept pass may land in a DIFFERENT file than the first (nothing constrains ``w2``):
        which file the citation *names* is the address layer's question, not this function's.

    🔴 AND NO EXCISION IS SILENT. Whatever branch decided the verdict, if marks were stripped on
    the way in, the detail says so - here, once, above ALL of `_check_inner`'s returns, because a
    note added on one branch of twenty is the R50 defect by construction.
    """
    verdict, where, detail = _check_inner(quote, corpus, *a, **kw)
    marks = editorial_marks(quote)
    kept = source_marks(quote)
    if kept and verdict not in CLEAN:
        v2, w2, d2 = _check_inner(quote, corpus, keep_tags=True)
        if v2 in ("VERIFIED", "WRONG_SPEAKER", "TRUNCATED_CONDITION", "TRUNCATED_OPENING"):
            verdict, where = v2, w2
            detail = ((d2 + " - " if d2 else "")
                      + "%s matched as the source's own text (kept, not stripped)"
                      % ", ".join(kept[:4]))
            # Provenance tags were still stripped on the winning pass; only they get the note.
            marks = [m for m in marks if m not in kept]
    if marks:
        detail = ((detail + "; " if detail else "")
                  + "editorial/provenance mark(s) stripped before comparison: %s"
                  % ", ".join(marks[:4]))
    if where and verdict in CLEAN and getattr(corpus, "is_superseded", None) \
            and corpus.is_superseded(where):
        extra = ("the words are in `%s`, which the law register marks as SUPERSEDED by a newer "
                 "edition of the same provision. This is not an accusation - the quotation was "
                 "correct when it was taken. Decide whether the filing should cite the edition in "
                 "force at the time or the current text, and see the revision report."
                 % os.path.basename(where))
        return "SUPERSEDED_EDITION", where, (detail + " - " if detail else "") + extra
    return verdict, where, detail
