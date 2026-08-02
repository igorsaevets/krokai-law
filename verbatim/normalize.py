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
    "ellipsis_parts", "latin_share", "is_mostly_cyrillic",
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
)

# Provenance tags that a review brief REQUIRES a channel to emit, plus the two editorial marks a
# careful drafter puts next to a government typo. They land inside the quoted span and then make a
# byte-exact quotation fail to match.
#
# Measured: the first run of the original tool flagged four verbatim regulatory passages as ALTERED
# for this reason alone. Both editorial conventions are stripped before comparison, so a project can
# use Bluebook "[sic]" inside the quotation marks for filings AND a bracketed note outside them for
# internal files, without either convention breaking verification.
_TAG_RE = re.compile(
    r"\s*\[(?:OPENED|SNIPPET|MEMORY|RETRIEVED|UNVERIFIED"
    r"|ОТКРЫЛ|СНИППЕТ|ПАМЯТЬ"
    r"|sic|so in original|так в источнике)\]",
    re.I)

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
    """
    if not s:
        return ""
    for a, b in _TYPOGRAPHY:
        s = s.replace(a, b)
    s = _PAGE_MARK_RE.sub(" ", s)
    # Trap 2 - ONLY at a physical line end.
    s = re.sub(r"(\w)-[ \t]*\r?\n[ \t]*", r"\1-", s)
    # Trap 1 - line wrapping and double spaces.
    return " ".join(s.split())


def strip_markdown(s: str) -> str:
    """Remove formatting a drafter applied *inside* a quotation, plus provenance tags.

    A model bolds a word inside a quoted span for emphasis. That is presentation, and it makes the
    span unfindable in the source. So `**`, `__`, `*`, backticks and link syntax come off.

    Then the wrappers. A blockquote line frequently already carries its own quotation marks
    (`> "text"`), so both extractors fire and the wrapped copy fails to match. Symmetric wrappers
    are stripped - and **asymmetric ones too**: a span cut out of a longer sentence keeps only its
    closing guillemet, and that single character was enough to report perfectly good quotations as
    ALTERED across an entire first run.
    """
    if not s:
        return ""
    s = _MD_LINK_RE.sub(r"\1", s)
    s = re.sub(r"\*\*|__|\*|`", "", s)
    s = _TAG_RE.sub("", s)
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
    return s.strip()


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
    parts = [p.strip(" .,;:-—") for p in re.split(r"\.\.\.|…", q or "")]
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
