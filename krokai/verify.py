# -*- coding: utf-8 -*-
"""The checker. One quotation in, one of fifteen verdicts out.

Reading order for this file: ``check()`` at the bottom is the decision tree; everything above it is
one test each. Every test carries the incident that produced it, because a rule whose reason is
lost gets "simplified" back out six months later by someone who cannot see what it was for.
"""
from __future__ import annotations

import difflib
import os
import re

from .normalize import normalise, alnum, dehyph, ellipsis_parts, prepare_quote
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
NARROWER_RE = re.compile(
    r"\b(but|however|unless|except|provided|notwithstanding|only|other than|subject to|"
    r"certain|specific|solely|for purposes of|does not include|do not include|shall not|"
    r"may not|if the|where the|when the)\b", re.I)

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
FOOTNOTE_RE = re.compile(r"^\d{1,3}(\s+(see|id\.?|ibid|supra|cf\.?|infra|accord))?\b", re.I)


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


def _punctuation_detail(quote_n, path, corpus):
    """Say WHAT the punctuation difference is.

    A bare "punctuation differs" is technically true and practically useless - the reader still has
    to diff it by hand, so they do not, and the finding is skipped. Measured on the first real run:
    a quotation spanning two bullets of a list in an agency manual, where the source has a `*` list
    marker between them that the drafter silently swallowed. Quoting across list items without
    marking the elision is a real (small) defect, and naming the character is what makes it fixable
    in five seconds.
    """
    src = corpus.text_of(path)
    a = alnum(quote_n)
    i = alnum(src).find(a)
    if i < 0:
        return ""
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
        return ""
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


def truncated_condition(quote_n, corpus):
    """Does an exactly-matching quotation stop right before the clause that limits it?

    Two independent signals, and **both** are required, because either alone cries wolf:

    1. the quotation does not end at a sentence boundary, and
    2. what follows it in the source opens with a limiter.

    Checked at EVERY occurrence: the same sentence lives in several preambles, and the first hit is
    not necessarily the copy that was quoted.
    """
    q = quote_n.rstrip()
    if q[-1:] in ".?!":
        return None, None, None                # a complete sentence: nothing was cut off
    for path, off in corpus.find_all_pos(quote_n):
        tail = corpus.after(path, off, len(quote_n))
        if not tail:
            continue
        nxt = tail.lstrip(" ,;:-")
        m = LIMITER_RE.match(nxt)
        if m:
            return path, m.group(0), " ".join(nxt.split()[:26])
    return None, None, None


def leading_cut(quote_n, corpus):
    """The mirror image. An exact substring can invert its own meaning by starting one word too
    late: the negation stands in FRONT of it, not behind.

    🔴 Two calibrations, both measured. Accepting any operator (including "and" and "or") produced
    **254 hits** - noise, not findings; only a NEGATION reverses what follows it. And it has to be
    NEAR: six tokens, not fourteen, or a "not" at the head of a long clause claims a span it does
    not govern.
    """
    for path, off in corpus.find_all_pos(quote_n):
        head = corpus.before(path, off, 220)
        if not head:
            continue
        if quote_n[:1].isupper() and head.rstrip().endswith((".", "!", "?", ":")):
            continue                           # our quotation starts a sentence: nothing precedes
        cut = re.split(r"(?<=[.!?])\s+", head)[-1]
        toks = [w.strip(_STRIP).lower() for w in cut.split()][-6:]
        bad = sorted({w for w in toks if w in NEGATION})
        if bad:
            return path, ", ".join(bad), " ".join(cut.split())[-140:]
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
    """
    n = normalise(prepare_quote(quote))
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
def _check_inner(quote, corpus):
    """Return `(verdict, path_or_None, detail)`.

    The order of the tree is the design. An exact match is tested first and then **immediately
    interrogated for completeness**, because "it is an exact substring" is the answer that hides the
    two most expensive defects. Only after that do the near-miss classifiers run, cheapest first.

    🔴 `prepare_quote` is called HERE rather than trusted to the callers. It used to be applied by
    `extract_quotes` and by `bank`, and simply not applied by `krokai quote` - so the same text got
    different verdicts depending on which door it came through. A rule that every caller must
    remember is a rule that one caller will forget, and this one had.
    """
    quote = prepare_quote(quote)
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
    if ("..." in n or "…" in quote) and len(parts) > 1:
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
    a = alnum(n)
    if len(a) >= 30:
        hit = corpus.find_alnum(a)
        if hit:
            # 🔴 See truncation_anywhere(). The alphanumeric index cannot distinguish a
            # punctuation drift from a PREFIX that stops before the limiting clause, so the
            # truncation question must be asked before this branch may call itself green.
            tp, _lim, ttail = truncation_anywhere(n, corpus)
            if tp:
                return "TRUNCATED_CONDITION", tp, "the source continues: «%s…»" % ttail
            return "PUNCTUATION", hit, _punctuation_detail(n, hit, corpus)

    # --- every sentence verbatim, but not adjacent -------------------------------------------------
    sents = [x.strip() for x in re.split(r"(?<=[.;:])\s+(?=[A-Z(])", n)]
    sents = [x for x in sents if len(x) >= 40]
    if len(sents) >= 2:
        where = [corpus.find(s) or corpus.find_alnum(alnum(s)) for s in sents]
        if all(where):
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

    return "NOT_FOUND", None, ""


def check(quote, corpus, *a, **kw):
    """`_check_inner`, plus the one question the text comparison cannot ask: is the file it found
    still the edition in force?

    🔴 This wraps rather than edits the comparison on purpose. The words really ARE in that file -
    that part of the answer is correct and must not be thrown away - and the superseded fact lives
    in the law register, which is not the corpus's business to parse. Wrapping keeps one place where
    the text question is answered and one place where the edition question is.

    It is applied HERE and not in the report, because a check that runs outside the path it protects
    is decorative: the hooks and the reviewer-answer audit call `check()` directly and would
    otherwise keep grading superseded law as clean.
    """
    verdict, where, detail = _check_inner(quote, corpus, *a, **kw)
    if where and verdict in CLEAN and getattr(corpus, "is_superseded", None) \
            and corpus.is_superseded(where):
        extra = ("the words are in `%s`, which the law register marks as SUPERSEDED by a newer "
                 "edition of the same provision. This is not an accusation - the quotation was "
                 "correct when it was taken. Decide whether the filing should cite the edition in "
                 "force at the time or the current text, and see the revision report."
                 % os.path.basename(where))
        return "SUPERSEDED_EDITION", where, (detail + " - " if detail else "") + extra
    return verdict, where, detail
