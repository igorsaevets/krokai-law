# -*- coding: utf-8 -*-
"""The single text normaliser. There is exactly one, on purpose.

WHY ONE
-------
In the project this toolkit was extracted from, the normaliser was retyped by hand three separate
times in a single day - once in a probe script, once in a hook, once in an end-of-round checker -
and **each copy forgot a different transform**. The result was three false alarms in one session:
a quotation that was perfectly correct was reported missing, because the copy doing the checking
did not know to strip a markdown blockquote marker, or bold-inside-a-quote, or a line wrap.

A false alarm in a verification tool is not a cosmetic defect. It is the failure mode that kills
the tool: a check that cries wolf gets ignored within a week, and then it catches nothing at all.
So: one implementation, imported everywhere, never re-typed.

THE CONTRACT
------------
Normalisation may change **whitespace, hyphenation and typography**. It may never change
**letters, digits, or word order**. That line is what keeps the tool honest: everything it forgives
is a rendering difference, and everything it refuses to forgive is a difference in the text.

Every transform below is traceable to one measured incident, cited in place. None of them is here
because it seemed sensible.
"""
from __future__ import annotations

import re

__all__ = [
    "normalise", "alnum", "dehyph", "strip_markdown", "strip_scrape_artifacts",
    "prepare_quote", "ellipsis_parts", "latin_share", "is_mostly_cyrillic",
    "strip_invisibles", "editorial_marks", "source_marks", "strip_all_marks",
]

# Typography a model re-types differently from the source while meaning the identical thing.
# A byte comparison fails on these while every word is perfect, so they are folded - and nothing
# else is.
_TYPOGRAPHY = (
    ("“", '"'), ("”", '"'),        # " "
    ("‘", "'"), ("’", "'"),        # ' '
    ("«", '"'), ("»", '"'),        # « »
    ("„", '"'), ("‚", "'"),        # „ ‚
    ("–", "-"), ("—", "-"),        # – —
    ("−", "-"),                          # −  (minus sign, not a hyphen)
    ("…", "..."),                        # …
    (" ", " "), (" ", " "),        # nbsp, thin space
    (" ", " "), (" ", " "),        # narrow nbsp, figure space
    ("﻿", ""),                           # BOM in the middle of a scraped file
    ("​", ""), ("‌", ""), ("‍", ""),   # zero-width space, ZWNJ, ZWJ
)

# 🔴 THE SOFT HYPHEN, U+00AD, IS INVISIBLE - AND THAT IS WHAT MAKES IT EXPENSIVE.
#
# A discretionary hyphen renders as a hyphen only where the renderer chooses to break the
# line, and as nothing everywhere else. It is never part of the text. What makes it dangerous
# rather than untidy is that you cannot see it: the source reads `application`, the quotation
# reads `application`, and they do not match.
#
# The sister project measured 709 of them in one library, every one at a line end,
# concentrated in three Supreme Court opinions - and its indexer had been deleting the
# character as invisible rubbish BEFORE joining the line, so there was nothing left to join
# and the fragments `immigra`, `applica` and `tion` entered its word list as words.
#
# Measured here 2026-08-05, before this existed: a correct quotation of a soft-hyphenated
# provision came back PUNCTUATION rather than VERIFIED, and a plain text search for
# `application` in the sidecar missed it entirely. A demoted verdict is quiet, which is
# exactly what makes it costly - it is the bin where "must be an extraction artefact" hides
# real errors.
#
# 🔴 ORDER IS THE WHOLE FIX. At a line end the soft hyphen and the line break have to go
# together; strip the character first and the whitespace collapse below turns
# `applica<SHY>\ntion` into `applica tion` - a space welded into the middle of a word, which
# is a worse corruption than the one being repaired.
_SOFT_BREAK_RE = re.compile(u"\u00ad[ \t]*\r?\n[ \t]*")
_SOFT_RE = re.compile(u"\u00ad")

# Provenance tags that a review brief REQUIRES a channel to emit, plus the editorial marks a
# careful drafter puts next to a government typo. They land inside the quoted span and then make a
# byte-exact quotation fail to match.
#
# Measured: the first run of the original tool flagged four verbatim regulatory passages as ALTERED
# for this reason alone. Both editorial conventions are stripped before comparison, so a project can
# use Bluebook "[sic]" inside the quotation marks for filings AND a bracketed note outside them for
# internal files, without either convention breaking verification.
#
# 🔴 TWO CLASSES, AND THE SPLIT IS LOAD-BEARING (R78 panel, three independent findings). A
# PROVENANCE tag ([OPENED], [MEMORY], ...) is the reviewer's own metadata and is NEVER the
# source's text - so it may never justify a marks-kept comparison, or a contaminated corpus
# that contains one gets promoted as "the source's own text". An EDITORIAL mark ([sic], [so in
# original]) legitimately appears IN sources - a court reciting a typo prints it on the page -
# so only this class earns the checker's second, marks-kept pass. The union is built from the
# two parts so the three regexes cannot drift apart.
_EDITORIAL_PAT = r"sic|so in original|так в источнике"
_PROVENANCE_PAT = (r"OPENED|SNIPPET|MEMORY|RETRIEVED|UNVERIFIED"
                   r"|ОТКРЫЛ|СНИППЕТ|ПАМЯТЬ")
_EDITORIAL_RE = re.compile(r"\s*\[(?:%s)\]" % _EDITORIAL_PAT, re.I)
_PROVENANCE_RE = re.compile(r"\s*\[(?:%s)\]" % _PROVENANCE_PAT, re.I)
_TAG_RE = re.compile(r"\s*\[(?:%s|%s)\]" % (_PROVENANCE_PAT, _EDITORIAL_PAT), re.I)

# `[text](url)` -> `text`.  A model turns a citation into a link; the link is not part of the text.
_MD_LINK_RE = re.compile(r"\[([^\]\n]{1,200})\]\((?:https?:|/|#)[^)\n]*\)")

# Footnote markers left behind by a web scraper, MID-SENTENCE.
#
# Two scrape vintages exist in the wild and they are NOT the same string: one writes
# `[\[14\]](https://…#footnote-14)`, a later one writes `[**[14]**](#footnote-14)`. Matching only
# the first leaves the second in the corpus, which turns a corrected quotation into a WORSE verdict
# after a real fix - the most confusing possible signal.
#
# NB: the anchor text itself contains `]` in BOTH vintages, so a `[^\]]` character class can never
# match it. A bounded non-greedy `.` is required. Measured: the class form left the marker in place
# and the fix looked like it had done nothing at all.
_FOOT_ANCHOR_RE = re.compile(r"\s*\[.{0,24}?\]\([^)]*#footnote[^)]*\)", re.I)
_FOOT_NUM_RE = re.compile(r"\s*\[(?:\*\*|\\)*\[?\d{1,3}\]?(?:\*\*|\\)*\]\([^)]*\)")
_SCRAPE_LINK_RE = re.compile(r"\s*\[link\]\([^)]*\)", re.I)

# Printing artefacts that sit INSIDE a sentence in official text dumps.
_PAGE_MARK_RE = re.compile(r"\[\[Page\s+[\w.-]+\]\]")

# The omitted-text marker of CFR and the Federal Register: asterisks SEPARATED BY WHITESPACE, and
# not glued to a word or to another asterisk. Both conditions are load-bearing - see the comment in
# `strip_markdown`, where a version without them ate the formatting it was meant to leave alone.
#
# 🔴 The boundary is `[*\w]`, not `\s`. The first version required WHITESPACE on both sides, and a
# reviewer found what that costs: `(* * *)`, `"* * *"` and `* * *.` all failed the lookahead on the
# closing bracket, quote or full stop, and the marker was stripped - `prescribe (* * *) and then`
# became `prescribe (  ) and then`. Measured, not argued. Punctuation around a marker is ordinary
# in a quotation, and it is exactly what distinguishes a quotation from raw source text.
#
# What the boundary must still exclude is an adjacent asterisk (`**bold** **bold**`, where the
# `* *` between the two spans is formatting) and a word character (`x*y`). Those are the two the
# control tests assert, in both directions.
# 🔴 The SEPARATOR class is as load-bearing as the boundary, and it was too narrow.
# A reviewer found `*\xa0*\xa0*` - the marker copied out of a scraped page, whose spaces are
# non-breaking - and `*\n*\n*`, the same marker across a line wrap. Both were eaten, and this
# module already reasons elsewhere that NBSP is what a scrape actually delivers. Newline is
# admitted too: `strip_markdown` runs before whitespace is folded, so the marker legitimately
# arrives wrapped. A bullet list (`* item\n* item`) is unaffected - the character after the
# asterisk is a space followed by a word, not another asterisk.
_OMIT_RE = re.compile(u"(?<![*\\w])\\*(?:[ \\t\u00a0\u2007\u202f\\r\\n]+\\*){1,8}(?![*\\w])")


def normalise(s: str) -> str:
    """Fold whitespace, line-break hyphenation and typography. Nothing else, ever.

    Three traps, each already paid for by a wrong conclusion:

    1. **Line wrapping.** `"on March\\n9, 2020"` made a true quotation return zero hits and very
       nearly inverted a finding. Fixed by collapsing all runs of whitespace.

    2. **Line-break hyphenation in official text.** The raw Federal Register carries `on-\\nline`,
       not `on-line`. A verification script produced a false NOT FOUND on a correct quotation
       because of it.

       🔴 The fix is anchored to an actual line end, and that anchor is the whole point. The naive
       version was a blanket ``s.replace("- ", "-")`` and it silently corrupted the corpus: real
       English contains ``pre- and post-production`` - hyphen, space, same line - which the blanket
       rule welded into ``pre-and post-production``. Four independent reviewers flagged it; checking
       against the actual corpus proved them right. Anchoring to ``\\n`` fixes the first case and
       cannot touch the second.

    3. **Typography.** Smart quotes, en/em dashes, non-breaking spaces. These are rendering, not
       substance.

    4. **The soft hyphen and the zero-width characters.** Invisible by definition, so a
       byte comparison fails while both sides look identical on screen. See the note above
       ``_SOFT_BREAK_RE`` for why the line-end case has to be handled before the character
       is removed, and not after.
    """
    if not s:
        return ""
    for a, b in _TYPOGRAPHY:
        s = s.replace(a, b)
    s = _PAGE_MARK_RE.sub(" ", s)
    # Trap 4 - the soft hyphen, both together and then alone. Before the whitespace collapse,
    # and before the ASCII-hyphen rule, which cannot see U+00AD at all.
    s = strip_invisibles(s)
    # Trap 2 - ONLY at a physical line end.
    s = re.sub(r"(\w)-[ \t]*\r?\n[ \t]*", r"\1-", s)
    # Trap 1 - line wrapping and double spaces.
    return " ".join(s.split())


def strip_invisibles(s: str) -> str:
    """Remove the characters that render as nothing, and only those.

    Split out of ``normalise`` so the PDF sidecar can use it. The sidecar exists for grep, an
    editor's search and an AI reading the folder - and it was written as raw extractor output,
    so the one artefact in this package whose entire purpose is being findable was the one
    still carrying characters that defeat finding. Measured 2026-08-05: a plain search for
    `application` misses in a soft-hyphenated sidecar.

    It may NOT simply call ``normalise``: that collapses every run of whitespace, and a sidecar
    with no line structure is unreadable to the human who opens it to check. This transform is
    safe on a file kept for reading, because deleting a character that renders as nothing
    cannot change what the page says.

    Line-end first, then the bare character - see the note above ``_SOFT_BREAK_RE``. Reversed,
    the line break survives on its own and `applica<SHY>\\ntion` becomes `applica tion`.
    """
    if not s:
        return ""
    s = _SOFT_BREAK_RE.sub("", s)
    s = _SOFT_RE.sub("", s)
    for z in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        s = s.replace(z, "")
    return s


def strip_markdown(s: str, keep_tags: bool = False) -> str:
    """Remove formatting a drafter applied *inside* a quotation, plus provenance tags.

    A model bolds a word inside a quoted span for emphasis. That is presentation, and it makes the
    span unfindable in the source. So `**`, `__`, `*`, backticks and link syntax come off.

    Then the wrappers. A blockquote line frequently already carries its own quotation marks
    (`> "text"`), so both extractors fire and the wrapped copy fails to match. Symmetric wrappers
    are stripped - and **asymmetric ones too**: a span cut out of a longer sentence keeps only its
    closing guillemet, and that single character was enough to report perfectly good quotations as
    ALTERED across an entire first run.

    ``keep_tags`` keeps the EDITORIAL class (``[sic]``-family) in place - and still strips the
    provenance tags, because a provenance tag is never the source's text by definition. It
    exists for one caller: the checker's second pass over a quotation whose ``[sic]`` may be
    the SOURCE'S own text rather than the drafter's annotation - a court reciting a typo prints
    the ``[sic]`` on the page, and a faithful quotation of that page must keep it to match.
    Stripping everything is still the right default: the common case is the drafter's own
    editorial mark, which is not in any source. The split also lets a faithful source-``[sic]``
    quotation carry a provenance tag beside it without the tag blocking the kept-marks match
    (R78 panel: the all-or-nothing version failed exactly that mix).
    """
    if not s:
        return ""
    # 🔴 THE OMISSION MARKER IS TEXT, NOT FORMATTING - and this is the half of the asymmetry that
    # shipped. `strip_scrape_artifacts` already reasons about it from the CORPUS side and refuses
    # to touch `*` there, because CFR and the Federal Register print `* * *` where text is left
    # out. But `strip_markdown` runs on the QUOTE and did strip it, so a drafter quoting a
    # provision *including* its omission marker had the marker deleted on one side of the
    # comparison and kept on the other.
    #
    # Two details, each of which a simpler version gets wrong:
    #   * the marker requires WHITESPACE between the asterisks. `\\*(\\s*\\*)+` also matches the
    #     `**` of bold, and worse, it matches the `* *` sitting between two bolded words
    #     (`**a** **b**`), which protects a fragment of the formatting and leaves it in the text.
    #   * the span is restored VERBATIM, not rewritten to a canonical `* * *`. A source that
    #     prints four asterisks, or two spaces between them, must still match itself: the corpus
    #     side keeps whatever it has, so the quote side may not normalise.
    held = []

    def _hold(m):
        held.append(m.group(0))
        return "\x00%d\x00" % (len(held) - 1)

    s = _OMIT_RE.sub(_hold, s)
    s = _MD_LINK_RE.sub(r"\1", s)
    s = re.sub(r"\*\*|__|\*|`", "", s)
    s = _PROVENANCE_RE.sub("", s) if keep_tags else _TAG_RE.sub("", s)
    s = re.sub(r"(?m)^\s*>\s?", "", s)
    s = s.strip()
    for _ in range(4):
        t = s.strip()
        if len(t) > 2 and t[0] in '"«“„' and t[-1] in '"»”':
            s = t[1:-1]
        elif len(t) > 2 and t[0] in '"«“„':
            s = t[1:]
        elif len(t) > 2 and t[-1] in '»”':
            s = t[:-1]
        else:
            break
    s = s.strip()
    for i, span in enumerate(held):
        s = s.replace("\x00%d\x00" % i, span)
    return s


def editorial_marks(s: str):
    """ALL marks - editorial and provenance - present in a RAW quotation, as written.

    Returns the matched marks (``["[sic]", "[OPENED]"]``-shaped, whitespace trimmed). Used by
    ``verify.check`` for VISIBILITY: this function only REPORTS what ``strip_markdown`` would
    remove, so an excision is never silent - the AOS measurement behind this is a pipeline that
    cut marks from quotations and logged nothing, and the reader could not tell "matched as
    written" from "matched after surgery".
    """
    return [m.strip() for m in _TAG_RE.findall(s or "")]


def strip_all_marks(s: str) -> str:
    """Remove every ``_TAG_RE`` mark from a SOURCE-side span before a detector reads it.

    Exists for one measured hole (R78 panel, probe-proven on both branches): the source's own
    ``[sic]`` sitting between a quotation's end and the limiting clause blinded ``LIMITER_RE``
    - the tail began with ``[``, no limiter matched, and a silently truncated condition was
    graded VERIFIED with a confident wrong explanation. The detectors ask "does a limiter
    follow"; a bracketed mark between the two is typography of the page, not an answer.
    """
    return _TAG_RE.sub("", s or "")


def source_marks(s: str):
    """Only the EDITORIAL class (``[sic]``-family) - the marks that can be the source's own text.

    This is the gate for the checker's marks-kept second pass, and the narrowness is the fix:
    the first version gated on ALL marks, and the R78 panel showed what that buys - a corpus
    contaminated with a reviewer's ``[OPENED]`` promoted as "matched as the source's own text",
    and a ``[OPENED]`` colliding with the real word *opened* laundering a loud verdict through
    the punctuation branch. A provenance tag is never source text; it must never argue for one.
    """
    return [m.strip() for m in _EDITORIAL_RE.findall(s or "")]


def prepare_quote(s: str, keep_tags: bool = False) -> str:
    """Everything a QUOTATION passes through before it is compared with a source.

    🔴 There is exactly one normaliser in this package and there was still a drift, because the
    drift was never in the normaliser - it was in the COMPOSITION. Measured 2026-08-03 by an
    outside reviewer and reproduced here: `krokai check` reached `verify.check` through
    `extract_quotes`, which strips markdown; `krokai quote` handed the user's raw text straight to
    `verify.check`, which does not. Five of six realistic inputs got two different answers.

    And the answers were not "found" versus "not found", which would at least look like a bug. A
    quotation that stops one clause short of `except as provided in paragraph (k)` came back
    **TRUNCATED_CONDITION** through one entry point and **PUNCTUATION** through the other: the
    markdown residue turned the most dangerous verdict this tool has into a cosmetic one. Rows 1-4
    of that measurement are what a person actually pastes, because they are what a model emits -
    guillemets, bold for emphasis, the provenance tag the brief itself demands, a blockquote
    marker - and `krokai quote` is documented as the first command a new user runs.

    So the fix is not "remember to call `strip_markdown` in the other place too". `check()` calls
    this itself, and no caller can forget. Solving the retyped-function problem left the
    assembled-pipeline problem standing; they are the same defect wearing a different coat.
    """
    return strip_markdown(s or "", keep_tags=keep_tags)


def strip_scrape_artifacts(s: str) -> str:
    """Remove a scraper's leavings from a CORPUS file before indexing it.

    🔴 WHY THIS IS SEPARATE FROM ``strip_markdown``, and why the asymmetry was a real bug.

    ``strip_markdown`` runs on the QUOTE. For a long time the corpus went through ``normalise``
    alone, which does not touch link syntax. That asymmetry is the defect: agency policy manuals
    obtained by scraping carry ``[link](https://…)`` and ``[\\[14\\]](https://…#footnote-14)``
    sitting MID-SENTENCE, and such manuals footnote nearly every proposition. So a genuinely
    verbatim multi-sentence quotation **could not match**, and degraded to a partial verdict.

    It surfaced the right way round: the tool flagged two entries that had just been banked from an
    opened source. The flags were real; the cause was the corpus, not the quotations.

    🔴 Why NOT simply reuse ``strip_markdown`` here: it also strips ``*``, and Federal Register and
    CFR texts use ``* * *`` as the omitted-text marker. Deleting those would silently weld unrelated
    provisions together - a corpus corruption far worse than the false alarm being fixed. So this is
    link syntax only. Letters, digits and order are untouched: same contract as ``normalise``.
    """
    if not s:
        return ""
    s = _FOOT_ANCHOR_RE.sub("", s)
    s = _FOOT_NUM_RE.sub("", s)
    s = _SCRAPE_LINK_RE.sub("", s)
    return _MD_LINK_RE.sub(r"\1", s)


def alnum(s: str) -> str:
    """Letters and digits only, lowercased.

    Used for ONE purpose: telling *"the words are right and the punctuation drifted"* apart from
    *"the words are wrong"*. It never promotes a quotation to VERIFIED - a dropped comma is still a
    defect in a document that gets filed. It just is not fabrication, and the two need separate
    piles or the big pile buries the dangerous one.

    🔴 Known limitation, stated because a reviewer found it: this folding cannot distinguish
    ``no table`` from ``not able``. It is a locator of last resort, never a proof.
    """
    return "".join(ch.lower() for ch in (s or "") if ch.isalnum())


def dehyph(s: str) -> str:
    """Heal a hyphen used for line justification: ``inadmis-sibility`` -> ``inadmissibility``.

    Applied to BOTH sides of a comparison and never stored as the corpus.

    It also heals ``hyphen + whitespace``, which the strict ``normalise`` deliberately does not.
    That looks contradictory and is not: in prose, ``pre- and post-production`` is real English and
    must survive; in text extracted from a **PDF**, the space after a justification hyphen is the
    extractor's artefact. Measured on a published court reporter, which renders

        ...the social and humane considerations pre- sented in his behalf...

    and a byte-correct quotation of it was reported NOT FOUND.

    This is safe against false positives precisely because it runs on both sides: ``pre- and
    post-production`` becomes ``preand post-production`` in the quotation and in the corpus alike,
    so it still matches itself and nothing else. The error it removes - a false NOT FOUND that sends
    a drafter to "correct" a quotation that was already right - is the more expensive one.
    """
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s or "")
    return re.sub(r"(\w)-(\w)", r"\1\2", s)


# 🔴🔴 ONE SPELLING OF "AN ELLIPSIS", FOR EVERY PLACE THAT ASKS THE QUESTION.
#
# Found by the review panel that reviewed the v0.8.3 repair, and confirmed by execution the same
# hour. Three separate places each spelled the ellipsis themselves, and all three spelled it
# `...` or `…` — omitting `. . .`, **the spaced form that legal citation actually prescribes**
# (The Bluebook, rule 5.3: an omission is marked by three periods separated by spaces). Measured
# on the live filing: 80 quotations carry the spaced form.
#
# The consequence was not silence, it was the opposite and worse. A quotation ending `. . .` fell
# past the ellipsis machinery entirely and was reported `TRUNCATED_CONDITION` — "you cut this off
# silently" — which is the exact false accusation against honest practice that v0.8.2 was written
# to remove. So the 0.8.1 defect was still live for the one dialect that matters most, one release
# after being fixed for the two that matter least.
#
# `\.\s?\.\s?\.` and not `\.\s*\.` : at most ONE space between periods. "U.S." cannot match (letters
# sit between the periods) and neither can a sentence boundary followed by an initial ("in 1990. J.
# Smith"), because that has a letter between them too.
ELLIPSIS_RE = re.compile(r"\.\s?\.\s?\.|…")


def ellipsis_parts(q: str, minlen: int = 25):
    """Split a quotation on its ellipses. Cutting with an ellipsis is legitimate citation style,
    not an alteration, so the fragments are checked one at a time; the ellipsis itself is ours and
    appears in no source.

    ``minlen`` is a parameter and not a constant for a measured reason. A fixed floor of 25
    **silently discarded** shorter fragments, and that is worse than it sounds: the discarded piece
    is not merely unverified - the surviving pieces are then checked "in order" ACROSS it, so a
    middle fragment could be absent from the source entirely while the quotation still reads clean.

    The batch checker therefore passes 10 for the ordering test and reports anything under 25 as
    *checked for position only*: short strings match everywhere, so their presence proves little on
    its own, but their POSITION still does.
    """
    parts = [p.strip(" .,;:-—") for p in ELLIPSIS_RE.split(q or "")]
    return [p for p in parts if len(p) >= minlen]


def latin_share(s: str) -> float:
    """Fraction of alphabetic characters that are ASCII letters.

    🔴 The obvious implementation is wrong, and it shipped once. The original test was
    ``[a-zA-Z]{40}`` - forty CONSECUTIVE latin letters - which never occurs in English text because
    words are separated by spaces. The check silently returned "0 quotations" on a file full of
    quotations. The correct signal for *"this is source text in the original language"* is the
    latin **share**, never a run.
    """
    letters = [c for c in (s or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isascii()) / float(len(letters))


def is_mostly_cyrillic(s: str, threshold: float = 0.4) -> bool:
    """True when the span is the drafter's own commentary rather than a source quotation.

    Only meaningful for a project whose working language differs from the language of the law. It is
    a cheap, high-precision filter: a quotation of a US statute is English, so a mostly-Cyrillic span
    inside quotation marks is a gloss, and checking it against a corpus of statutes would produce a
    guaranteed false NOT FOUND.
    """
    letters = [c for c in (s or "") if c.isalpha()]
    if not letters:
        return False
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    return cyr > len(letters) * threshold
