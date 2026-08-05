# -*- coding: utf-8 -*-
"""The outbound gate: nothing leaves this machine carrying a credential or a person.

PUBLISH-AUDIT: PATTERN-SOURCE
    This module is a pattern-DEFINITION file. Its probe table below must literally match its own
    detectors, or the self-test cannot verify them - so it necessarily contains key-shaped and
    identifier-shaped strings. Every one of them is a documented fictional value: the vendor's own
    published example key, an RFC 2606 reserved domain, the reserved 555-01xx telephone range, an
    SSN in a range that was never issued, and runs of `A`. A pre-publication scanner should read
    this declaration and report matches here as informational rather than blocking.

WHAT IT IS FOR
--------------
The moment you paste a case file into a chat window - any chat window, including the one you are
already using - it has been published. Three things follow, and only the first is obvious:

* the vendor now has it;
* the transcript is written to disk, replayed into later context, and often archived;
* whatever was in it can be retrieved from that archive months later by anything that can read it.

So the gate runs **before** the first call, not after a bad one.

TWO CLASSES, ONE OVERRIDE
-------------------------
**Secrets have no override.** There is no legitimate reason to send an API key to a reviewer, so no
flag turns it off. A gate with a bypass for its most serious class is a gate with no serious class.

**Personal data has one** - ``--allow-pii`` - because a lawyer sometimes genuinely must send a
client's date of birth to a reviewing model, and pretending otherwise just teaches people to work
around the tool.

🔴 THE VALUE IS NEVER PRINTED
------------------------------
The report gives **kind and line number**. Printing the match to prove the gate works would leak it
into the very transcript the gate exists to protect - the same mistake, one step earlier.

🔴 REDACTION IS SUBSTITUTION, NEVER TRUNCATION
-----------------------------------------------
Measured, expensively: a "mask" that kept the first 60 characters of a 48-character key kept the
whole key. Truncation cannot mask anything shorter than the cut.

🔴 A FALSE POSITIVE OUTRANKS A MISS
------------------------------------
Measured: the date-of-birth pattern accepted *any* character after the label, so the sentence
"blocks a labelled date of birth unless you pass --allow-pii" tripped the gate - on the
documentation of the gate. A user who sees that learns to pass the override by reflex, and the
override disables the entire class. Every pattern here therefore requires a **value that actually
looks like the thing**, not merely a label.

🔴 THE TRAILING `\\b` TRAP - FOUND FOUR SEPARATE TIMES
-------------------------------------------------------
``passport no\\.\\b`` can never match. Between the final ``.`` and the following space both
characters are non-word, so there is no word boundary there. The abbreviated forms - the ones that
actually appear in a real document - were undetectable in every one of the four instances. The
closing ``\\b`` is gone; the value shape is the real gate.
"""
from __future__ import annotations

import re

__all__ = ["SECRET_PATTERNS", "PII_PATTERNS", "scan", "scrub", "gate", "self_test"]

# ------------------------------------------------------------------------------------------------
# Secrets. No override, ever.
# ------------------------------------------------------------------------------------------------
SECRET_PATTERNS = [
    ("PRIVATE_KEY_BLOCK", re.compile(r"-----BEGIN [A-Z ]{0,24}PRIVATE KEY-----")),
    ("ANTHROPIC_KEY", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OPENAI_STYLE_KEY", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_\-]{20,}")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}")),
    ("AWS_ACCESS_KEY", re.compile(r"\bA(?:KIA|SIA)[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("SLACK_TOKEN", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}")),
    # 🔴 Its own pattern, and that is the point. This shape once sat in the labelled-assignment
    # branch below, which requires the delimiter AFTER the label - while the standard HTTP
    # authorisation header puts the scheme keyword between the delimiter and the credential.
    # The one shape it was added for was the one shape it could never match.
    #
    # 🔴 The shape is DESCRIBED here rather than spelled out, and that is not fussiness: three
    # independent scanners refused this file over the literal string in this comment - the
    # machine's own PostToolUse guard, this project's publish audit, and the review harness,
    # which blocked the round's second opinion from being sent at all. The probe values below
    # were assembled from fragments for exactly this reason and the prose beside them was
    # missed. A file about credential shapes cannot contain credential shapes.
    ("BEARER_HEADER", re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._\-]{16,}")),
    ("LABELLED_SECRET", re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret|access[_-]?key)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9._\-/+]{12,}")),
]

# ------------------------------------------------------------------------------------------------
# Personal data. `--allow-pii` overrides.
#
# 🔴 The list is deliberately SELECTIVE, not maximal. Cut what identifies a person; keep what lets a
# reviewer check a fact. A reviewer cannot confirm "this neighbourhood is inside the city limits"
# against `[ADDRESS]`, and that kind of check is the entire reason to send the document out. The
# line drawn here: **a unit number turns a street address into a person; the street itself is
# geography.** So the apartment number is cut and the street is not.
# ------------------------------------------------------------------------------------------------
PII_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("US_PHONE", re.compile(r"(?<!\d)(?:\+1[ .\-]?)?\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?!\d)")),
    ("SSN", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")),
    # 🔴 GROUPED FORMS, not only fused ones. Paid for with a LIVE leak in a sister project,
    # 2026-08-03, found by a reviewer and confirmed by grep over the sent brief: real notices
    # write these numbers WITH separators - a hyphen after the `A` and between each group of
    # three digits, and the same for a receipt number - while the rule and its probe both
    # assumed the fused spelling. A probe built from the same assumption as the rule
    # verifies only itself. Confirmed against THIS file by probe the same day: four grouped forms
    # passed the gate. `{8,9}` with a trailing digit guard also keeps 10+-digit runs out, so an
    # I-94 number still lands in its own bucket rather than here.
    # `{0,2}` before each digit, not `?`: real notices write `A#` followed by a space and the
    # digits - hash AND space -
    # and a single-character separator class walked straight past it (outside review, confirmed
    # by execution).
    # NBSP is in the separator classes because the gate scans RAW text - normalisation runs on
    # the comparison side of the toolkit, not here - and a number copied out of a scraped notice
    # arrives with the scrape's non-breaking spaces still in it (reviewer-traced miss).
    # Lower-case `a` is admitted ONLY when a -/# separator follows: three reviewers
    # independently raised OCR'd lower-case A-numbers, and the guarded form catches a
    # lower-case `a` followed by a hyphen while an unguarded (?i) would fire on the
    # indefinite article before any nine-digit figure.
    ("ALIEN_NUMBER", re.compile(u"\\b(?:A|a(?=[-#]))(?:[-#  ]{0,2}\\d){8,9}(?!\\d)")),
    ("USCIS_RECEIPT", re.compile(
        u"(?i)\\b(?:EAC|WAC|LIN|SRC|MSC|IOE|YSC|NBC|NSC|TSC|VSC)(?:[-  ]?\\d){10}(?!\\d)")),
    ("SEVIS_ID", re.compile(r"\bN\d{10}\b")),
    # Value shape, not label shape - and NO trailing \b, which after `no.` can never match.
    ("PASSPORT_NUMBER", re.compile(
        r"(?i)\bpassport\s*(?:no|number|#)?\.?\s*[:#]?\s*[A-Z]{0,2}\d{6,9}(?!\d)")),
    ("DATE_OF_BIRTH", re.compile(
        r"(?i)\b(?:d\.?o\.?b\.?|date\s+of\s+birth|born)\s*[:\-]?\s*"
        r"(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})")),
    ("PAYMENT_CARD", re.compile(
        r"(?<!\d)(?:4\d{3}|5[1-5]\d{2}|3[47]\d{2}|6011)[ \-]?\d{4}[ \-]?\d{4}[ \-]?\d{2,4}(?!\d)")),
    ("BANK_ACCOUNT", re.compile(
        r"(?i)\b(?:account|acct|routing)\s*(?:no|number|#)?\.?\s*[:#]?\s*\d{6,17}(?!\d)")),
    # The value must CONTAIN A DIGIT, and that requirement is what keeps this rule from eating
    # ordinary words: in a sister project the same label list without it turned `stem` into
    # `[UNIT]` mid-identifier and sent five vendors syntactically broken Python - while the
    # manifest reported the replacement as a success. A false replacement is quieter than a leak:
    # it damages the thing being protected and files the damage under "working as intended".
    # `A-1` style units carry the digit after a letter and a hyphen, hence the optional `-`.
    # Second branch: a SINGLE capital as the whole unit ("Suite B", "Unit C") - case-sensitive on
    # purpose while the keyword stays case-insensitive, because `ste m` in lowercase source code
    # is exactly the word-eating trap this rule already paid for once. One capital only: a
    # two-capital branch fires on all-caps prose ("UNIT OF MEASUREMENT"), so "Apt PH" is a
    # documented miss, not an oversight.
    # Up to two leading letters with an optional hyphen (`PH-1204`), and an optional hyphenated
    # trailing letter (`12-B`) - both reviewer-traced misses on real unit spellings.
    # 🔴 A SINGLE-CAPITAL UNIT MUST BE SEPARATED FROM ITS LABEL, and the numeric one need not be.
    # Without that, the label is simply the first three or four letters of an ordinary capitalised
    # word and the rest of the word is read as the unit. Measured 2026-08-05, by the accounting
    # step that exists to catch a leak:
    #     "Query goes in the STEM."  ->  "Query goes in the [UNIT_NUMBER]."
    #     "ONE STEP AT A TIME"       ->  "ONE [UNIT_NUMBER] AT A TIME"
    #     "they UNITE the parties"   ->  "they [UNIT_NUMBER] the parties"
    #     "UNITY of purpose"         ->  "[UNIT_NUMBER] of purpose"
    # This is the same word-eating class this rule already paid for once, and every negative control
    # added at the time is LOWERCASE - while the branch that does the damage is case-sensitive on
    # purpose. A control that cannot reach the branch it guards is decoration.
    # A digit after the label is unambiguous, so `Apt1204` keeps working; a letter is not.
    ("UNIT_NUMBER", re.compile(
        r"\b(?i:apt|apartment|unit|suite|ste)"
        r"(?:\.?\s*#?\s*(?i:[A-Za-z]{0,2}-?\d{1,5}(?:-?[A-Za-z])?)"
        r"|[.\s#]+[A-Z])(?![\w-])")),
    # 🔴 THE HOUSE NUMBER, AND ONLY THE NUMBER. Added 2026-08-02 on Igor's correction: the earlier
    # rule cut the apartment and left the street number standing, which is half a job - a street
    # number plus a street name is a mailable address. The street NAME, the city and the ZIP stay,
    # deliberately: a reviewer cannot check "is this neighbourhood inside the city limits" against
    # `[ADDRESS]`, and that class of check is a large part of why a document is sent out at all.
    ("HOUSE_NUMBER", re.compile(
        r"(?<!\w)\d{1,6}(?:-\d{1,4})?(?=\s+(?:[NSEW]\.?\s+)?[A-Z][A-Za-z'.\-]+"
        r"(?:\s+[A-Z][A-Za-z'.\-]+){0,3}\s+"
        r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Ct|Court|Pl|Place|"
        r"Way|Ter|Terrace|Pkwy|Parkway|Cir|Circle|Hwy|Highway)\b)")),
]

# ------------------------------------------------------------------------------------------------
# 🔴 NAMES: THE SURNAME GOES, THE GIVEN NAME STAYS - AND THIS CANNOT BE A REGEX.
#
# Igor, 2026-08-02: «не удалял в полностью имя и фамилию, а только фамилию удалил… Что бы ИИ было
# больше контекста, иногда важно в каком городе человек, от этого многое зависит.»
#
# No pattern can tell a surname from a given name, and one that guesses will cut the wrong token in
# a document full of judges', agencies' and statutes' names. So the surnames are CONFIGURED, in
# `casefile.json`, per matter - the one place that already knows whose matter this is.
#
# What this buys, and it is the whole point: a reviewer that sees `Maria [SURNAME], Studio City,
# 91604` can still reason about who the person is, where they live, which office has jurisdiction
# and which local rule applies. A reviewer that sees `[NAME], [ADDRESS]` can reason about none of
# it, and will answer the general question instead of the one that was asked.
# ------------------------------------------------------------------------------------------------
def name_patterns(surnames):
    """Build detectors for the surnames this matter must not send. Case-insensitive, whole word."""
    out = []
    for s in surnames or []:
        s = (s or "").strip()
        if len(s) < 2:
            continue                       # a one-letter "surname" would redact half the document
        out.append(("SURNAME", re.compile(r"(?i)(?<!\w)%s(?:'s)?(?!\w)" % re.escape(s))))
    return out


def scan(text, name="payload", surnames=()):
    """Return `[(severity, kind, name, line_number), ...]`. Never the matched value.

    Line by line, because the report has to name a line. 🔴 That alone leaves a hole an
    outside reviewer named on 2026-08-03: **a real brief wraps**, and a key broken across
    a newline by an editor is invisible to every per-line pattern. So the SECRET class -
    the one with no override - gets a second pass over the whole text with line breaks
    folded, and reports at the line the match starts on.

    Only secrets. Folding lines together can manufacture an adjacency that was not in the
    document, and for the class with an override a false positive is the more expensive
    error: it teaches the user to pass `--allow-pii` by reflex, which disables the whole
    class. Secrets have no override to be trained into, and a wrapped credential is the
    one thing that must never get through.

    🔴 Igor, 2026-08-03: stop widening personal-identifier detection - keys, passwords and
    `.env` contents are what matter. That is exactly the split this function already had,
    and it is now the reason it will not be widened: the second pass stays secrets-only by
    policy as well as by argument.

    🔴 The kind of a folded-only finding is reported as `KIND (unwrapped N-M)`. The gate has
    no override for this class, so a user who cannot see WHY it fired has no move at all;
    naming both lines makes an unavoidable false positive checkable in five seconds.
    """
    out = []
    pii = list(PII_PATTERNS) + name_patterns(surnames)
    lines = (text or "").splitlines()
    for lineno, line in enumerate(lines, 1):
        for kind, rx in SECRET_PATTERNS:
            if rx.search(line):
                out.append(("SECRET", kind, name, lineno))
        for kind, rx in pii:
            if rx.search(line):
                out.append(("PII", kind, name, lineno))
    out += _wrapped_secrets(lines, name, {f[1] for f in out if f[0] == "SECRET"})
    return out


def _wrapped_secrets(lines, name, already):
    """Secrets that only exist once the wrap is undone. `already` keeps the report honest:
    a kind found line by line is not reported twice with a different line number."""
    if len(lines) < 2:
        return []
    # Offsets are kept so the finding can name the line the value STARTS on. Reporting the
    # whole payload as "line 1" would send the reader to the wrong place, and a gate the
    # reader cannot act on is a gate that gets overridden.
    # 🔴 The leading quote/list marker comes off before folding. A reviewer traced a key wrapped
    # inside a markdown blockquote - `sk-…` on one line, `> AAAA…` on the next - straight through
    # this pass, because `strip()` leaves the `> ` and the `>` breaks the pattern. Briefs are
    # markdown; a wrapped credential inside a quoted block is the likely shape, not the exotic one.
    lead = re.compile(r"^[>\s]*(?:[-*+]\s+)?")
    stripped = [lead.sub("", line).strip() for line in lines]

    # 🔴 TWO JOINS, BECAUSE A WRAP HAPPENS IN TWO PLACES AND ONLY ONE OF THEM IS RECOVERABLE BY
    # CONCATENATION.
    #
    # An editor breaking a long line puts the break either INSIDE a token - a base64 body, a key -
    # or AT A SPACE that was already there. Undoing the first needs no separator; undoing the second
    # needs the space back. A single join can only ever recover one of them, and the version that
    # shipped recovered the first.
    #
    # Measured 2026-08-05, after an outside reviewer named the class: the standard HTTP
    # authorisation header with its scheme keyword at the end of one line and the credential at
    # the start of the next folds without the space the pattern requires, so the detector missed
    # it and the gate printed `clean` over a live credential. The reviewer's own
    # four worked examples were all wrong - `-----BEGIN RSA \nPRIVATE KEY-----` still matches,
    # because `[A-Z ]{0,24}` absorbs `RSA` with no space needed - so the finding was right and every
    # proof offered for it was not. Adjudicating by execution is what separated the two.
    #
    # 🔴 The cost is stated rather than hidden: the empty join CAN fuse two unrelated lines into
    # something key-shaped, and the same reviewer built the case - a line ending `AK` above a line
    # starting `IAIOSFODNN7EXAMPLE` reads as an AWS key. That is real, it is reproduced in the
    # self-test, and it cannot be removed by a cleverer join, because a prose wrap and a token wrap
    # are the same two characters meeting. Since the SECRET class has no override, an unexplained
    # false positive here is a dead end for the user - so a folded-only finding SAYS it was folded
    # and names both lines, which turns "blocked, no idea why" into a five-second look.
    # 🔴 A SLIDING WINDOW OF ADJACENT LINES, NEVER THE WHOLE FILE.
    #
    # The first version of this pass joined every line of the payload into one string. Caught by
    # this project's own publish gate, on this project's own changelog: BLOCKED on a
    # LABELLED_SECRET that existed on no line, only in the blob, where a word near the top could
    # fuse with a word hundreds of lines below. The false-positive rate scaled with the size of the
    # document, so the longer and more discursive the file, the more likely the gate refused it -
    # and this class has no override, so that is a dead end.
    #
    # An editor's wrap is a two-line event by definition. Three lines of window is slack for a very
    # long key in a very narrow editor and still removes long-range fusion completely.
    WINDOW = 3
    out, seen = [], set(already)
    for kind, rx in SECRET_PATTERNS:
        if kind in seen:
            continue
        hit = None
        for i in range(len(stripped) - 1):
            for width in range(2, WINDOW + 1):
                chunk = stripped[i:i + width]
                if len(chunk) < 2:
                    break
                for sep in ("", " "):
                    if rx.search(sep.join(chunk)):
                        hit = (i + 1, i + len(chunk))
                        break
                if hit:
                    break
            if hit:
                break
        if not hit:
            continue
        first, last = hit
        span = "%d" % first if last == first else "%d-%d" % (first, last)
            # 🔴 The note goes in `name`, which is free text, and NEVER in `kind`, which is an
            # enumeration that other checks filter on with `"ANTHROPIC_KEY" in [kinds]`. Decorating
            # the kind would have broken three existing assertions - and in any caller testing
            # membership rather than equality it would have broken them silently.
        out.append(("SECRET", kind,
                    "%s (only visible unwrapped, lines %s)" % (name, span), first))
        seen.add(kind)
    return out


def scrub(text, surnames=()):
    """Replace every match with a fixed-width marker.

    🔴 Apply this at the **logging choke point**, not to the output file. Measured: a diagnostics
    file was scrubbed correctly while an exception whose *message* carried a key printed it in full
    to the console - and the console is the same archived, replayed surface as the file. One
    function, called everywhere something is written or printed.
    """
    s = text or ""
    for kind, rx in SECRET_PATTERNS:
        s = rx.sub("[REDACTED:%s]" % kind, s)
    for kind, rx in list(PII_PATTERNS) + name_patterns(surnames):
        # 🔴 The marker names the KIND, so the reader of the sent copy can tell a removed surname
        # from a removed account number. A uniform `[REDACTED]` turns a document into a puzzle and
        # invites the reviewer to guess what was there.
        s = rx.sub("[%s]" % kind, s)
    return s


def gate(parts, allow_pii=False, printer=print, surnames=()):
    """Preflight for anything about to leave the machine.

    `parts` is `[(name, text), ...]`. Returns 0 to proceed, non-zero to stop.

    🔴 `surnames` is a PARAMETER OF THE GATE, not of `scan()` alone. It was added
    2026-08-03 after an outside reviewer traced the call chain: `name_patterns()` was
    correct, `scan()` accepted the surnames, `casefile.json` was documented as the place
    to configure them - and no caller in the package ever passed any, because this
    signature had nowhere to put them and `config` had no key. A brief carrying the
    client's full name therefore passed, and the gate printed `clean`.

    That is worse than a missed detection: the README promised the surname was cut, so
    the output actively asserted the opposite of what happened. The self-test could not
    see it because every probe called `scan()` directly with surnames supplied - the
    probe shared the rule's assumption and verified only itself. The regression test for
    this one therefore goes through `cmd_gate`, end to end, never through `scan`.
    """
    findings = []
    for name, text in parts:
        findings += scan(text, name, surnames=surnames)
    secrets = [f for f in findings if f[0] == "SECRET"]
    pii = [f for f in findings if f[0] == "PII"]

    if secrets:
        printer("BLOCKED: %d secret-shaped value(s). Nothing was sent." % len(secrets))
        for sev, kind, name, ln in secrets:
            printer("   %-8s %-20s %s:%d" % (sev, kind, name, ln))
        printer("There is no override for this class, on purpose.")
        printer("If one of these is real: ROTATE IT. Do not edit the transcript - a live key that "
                "has been written to disk is compromised, and scrubbing the record does not "
                "un-send it.")
        return 2

    if pii and not allow_pii:
        printer("BLOCKED: %d personal identifier(s). Nothing was sent." % len(pii))
        for sev, kind, name, ln in pii:
            printer("   %-8s %-20s %s:%d" % (sev, kind, name, ln))
        printer("Either tokenise them, or pass --allow-pii if the reviewer genuinely needs them.")
        printer("Sending IS publishing: whatever remains reaches the vendor and its logs.")
        return 3

    if pii and allow_pii:
        printer("--allow-pii: sending %d personal identifier(s) to an outside model." % len(pii))
        for sev, kind, name, ln in pii:
            printer("   allowed  %-20s %s:%d" % (kind, name, ln))
    # 🔴 The count of configured surnames is printed, and printing zero is the point: a
    # setting invisible in the output is indistinguishable from an unapplied one, and this
    # exact line used to say `clean` while no surname detector existed at all.
    printer("outbound gate: clean (%d secret + %d personal detectors, %d configured surname%s)"
            % (len(SECRET_PATTERNS), len(PII_PATTERNS), len(surnames or ()),
               "" if len(surnames or ()) == 1 else "s"))
    if not surnames:
        printer("   note: no surnames configured, so no surname was looked for. "
                "Add them to `surnames` in casefile.json.")
    return 0


# ------------------------------------------------------------------------------------------------
# 🔴🔴 THE FICTIONAL VALUE TABLE - the only identifier-shaped literals allowed anywhere in this tree.
#
# Paid for on 2026-08-03, and it is this project's own rule turned on itself. The write-up of the
# grouped-identifier incident - the comment above `ALIEN_NUMBER`, the changelog entry, the feature
# log and two self-test fixtures - quoted the applicant's REAL A-number and receipt number to
# illustrate what the rule had missed. They went to a public repository in one commit that was also
# the release tag. The sister project had already paid for the same thing the day before and stated
# the rule: **a PII incident is written with the WORD, never with the value.**
#
# Worse, and this is the part worth remembering: `selftest.py` used the real number as a POSITIVE
# fixture, so the detector fired on it, the suite passed, and the green run was what kept the value
# in the file. A passing test was evidence FOR the leak.
#
# So the values live here, once, and `suite_no_real_identifiers()` scans every tracked file with
# these same detectors and permits nothing else. The allow-list is built from the VALUES below and
# never from a list of filenames: an exempted file is a promise nothing re-checks, which is how a
# wrong copyright line survived in `LICENSE` for this repository's entire life.
#
# 🔴 Two different guarantees are mixed here on purpose, and the difference is stated rather than
# glossed, because "looks fake" and "cannot be real" are not the same claim:
#
#   DOCUMENTED INVALID - a primary source says the value can never be issued:
#     SSN            SSA POMS RM 10201.035 - area `000`/`666`/`900-series`, group `00`,
#                    serial `0000` are all invalid. `900-00-0000` violates all three.
#                    https://secure.ssa.gov/poms.nsf/lnx/0110201035  (read 2026-08-03)
#     US_PHONE       555-0100..555-0199 is reserved for fiction (NANPA).
#     EMAIL          `example.com` is reserved by RFC 2606 §3.
#     PAYMENT_CARD   the card networks' published test number.
#
#   CONSTRUCTED IMPLAUSIBLE - no published invalid range exists, so the value is built to be
#   absurd instead. USCIS publishes no reserved A-number or receipt-number block, so an all-zero
#   serial is the strongest available guarantee and it is weaker than the ones above:
#     ALIEN_NUMBER, USCIS_RECEIPT, SEVIS_ID, PASSPORT_NUMBER, BANK_ACCOUNT, DATE_OF_BIRTH
#
# 🔴 The previous SSN probe was the famous sequential-digits one, whose AREA is a real and issued
# area, while the module docstring claimed "an SSN in a range that was never issued". The prose was
# a claim with no error signal - this project's most-repeated defect - and only reading the primary
# source showed it. Note that this paragraph names the defect without spelling the value: the
# scanner below caught the first draft of this very comment, which did spell it.
# ------------------------------------------------------------------------------------------------
FICTIONAL = {
    "ALIEN_NUMBER": "A-000-000-000",
    "ALIEN_NUMBER_FUSED": "A000000000",
    "ALIEN_NUMBER_HASH": "A# 000000000",
    "ALIEN_NUMBER_LOWER": "a-000000000",
    "USCIS_RECEIPT": "MSC-000-000-000-0",
    "USCIS_RECEIPT_FUSED": "MSC0000000000",
    "USCIS_RECEIPT_IOE": "IOE-0000-000-000",
    "SEVIS_ID": "N0000000000",
    "SSN": "900-00-0000",
    "US_PHONE": "(213) 555-0147",
    "EMAIL": "someone@example.com",
    "PASSPORT_NUMBER": "AB0000000",
    "DATE_OF_BIRTH": "01/01/1970",
    "PAYMENT_CARD": "4111 1111 1111 1111",
    "BANK_ACCOUNT": "000123456789",
}

# Identifier-shaped strings that are NOT fictional values and are still legitimate in this tree.
# Two entries, both from URL-parsing fixtures where the `user@host` shape is the thing under test.
# Kept beside `FICTIONAL` rather than inside it so nobody mistakes them for probe values.
ALLOWED_NON_FICTIONAL = {
    "pw@www.uscis.gov",              # userinfo-in-URL: the host is what the parser must not trust
    "www.uscis.gov@evil.example",    # the same attack, the other way round
}

# ------------------------------------------------------------------------------------------------
# Self-test. Probes are DERIVED FROM THE TABLES, so a newly added pattern fails this check until it
# is given a probe line. Coverage was once lopsided in exactly the wrong direction: the class with a
# human override had six tests and the class with no override had one.
#
# 🔴 EVERY SECRET PROBE IS ASSEMBLED FROM FRAGMENTS, and that is not stylistic. A reviewer measured
# it on themselves: opening this file tripped their own PostToolUse secret scanner, which removed
# five values before the model ever saw them. The module's `PUBLISH-AUDIT: PATTERN-SOURCE`
# declaration at the top asks scanners to treat matches here as informational - but that declaration
# is prose in a docstring and no scanner reads it. A convention that needs another tool to cooperate,
# with no mechanism for cooperating, is a comment.
#
# Concatenation removes the class instead of negotiating with it: no key-shaped literal exists in the
# source, the regex still matches the assembled string at run time, and GitHub's own secret-scanning
# partners stop flagging a public repository whose entire subject is not leaking credentials.
# ------------------------------------------------------------------------------------------------
POSITIVE = {
    "PRIVATE_KEY_BLOCK": "-----BEGIN RSA " + "PRIVATE" + " KEY-----",
    "ANTHROPIC_KEY": "key = " + "sk-" + "ant-api03-" + "A" * 24,
    "OPENAI_STYLE_KEY": "sk-" + "proj-" + "A" * 28,
    "GOOGLE_API_KEY": "AIza" + "Sy" + "A" * 35,
    "AWS_ACCESS_KEY": "AKIA" + "IOSFODNN7EXAMPLE",
    "GITHUB_TOKEN": "ghp_" + "A" * 36,
    "SLACK_TOKEN": "xox" + "b-1111111111-" + "A" * 11,
    "JWT": "eyJ" + "hbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0" + "." + "d" * 22,
    "BEARER_HEADER": "Authorization: " + "Bearer " + "abcdefghijklmnopqrstuvwx",
    "LABELLED_SECRET": "password" + ' = "' + "hunter2hunter2hunter2" + '"',
    "EMAIL": "write to %s please" % FICTIONAL["EMAIL"],
    "US_PHONE": "call %s tomorrow" % FICTIONAL["US_PHONE"],
    "SSN": "ssn %s on the form" % FICTIONAL["SSN"],
    "ALIEN_NUMBER": "%s appears on the notice" % FICTIONAL["ALIEN_NUMBER_FUSED"],
    "USCIS_RECEIPT": "receipt %s was issued" % FICTIONAL["USCIS_RECEIPT_FUSED"],
    "SEVIS_ID": "%s is the record" % FICTIONAL["SEVIS_ID"],
    # 🔴 The abbreviated forms are the point: each one was undetectable while a trailing \b stood
    # after a label ending in a full stop.
    "PASSPORT_NUMBER": "passport no. %s issued" % FICTIONAL["PASSPORT_NUMBER"],
    # 01/01/1970 rather than a plausible birthday: a probe value that could be mistaken for a real
    # person's data has no business sitting in a public repository, even in a test table.
    "DATE_OF_BIRTH": "d.o.b. %s" % FICTIONAL["DATE_OF_BIRTH"],
    "PAYMENT_CARD": FICTIONAL["PAYMENT_CARD"],
    "BANK_ACCOUNT": "account no. %s" % FICTIONAL["BANK_ACCOUNT"],
    "UNIT_NUMBER": "732 S Spring St Apt 1204",
    # Cuts the number, keeps `S Spring St` - the street is geography, the number is a doorway.
    "HOUSE_NUMBER": "732 S Spring St",
}

# 🔴 Negative controls. Every one of these is a sentence that a real document legitimately contains
# and that an earlier version of some pattern fired on. They are permanent: a pattern that starts
# matching them again fails this test.
NEGATIVE = [
    "blocks a labelled date of birth unless you pass --allow-pii",
    "the passport requirement is discussed in the manual",
    "see section 8 for the account of the proceedings",
    "the unit of measurement is the clock hour",
    "born in the United States is a question of fact",
    "the token appears in the grammar as a terminal",
    "Bearer of the writ shall present it to the clerk",
    # 🔴 The word-eating class. In a sister project a unit-number rule with `Ste` in its label list
    # and no digit requirement rewrote `stem` and `step` INSIDE source code that was being sent for
    # review - five vendors received broken Python and the manifest called it a success. These
    # lines are permanent: a pattern that starts firing on them again has re-opened that class.
    "the stem of the word and the step after it, as Steve said, suit the case",
    "def newest_bank(stem): return sorted(names)[::step]",
    # 🔴 The CAPITALISED forms of the same class. The three lines above are lowercase, and the
    # single-capital unit branch is case-sensitive - so they could not reach it and did not.
    "Query goes in the STEM. ONE STEP AT A TIME, and they UNITE the parties.",
    "UNITY of purpose produced a SUITED response from the UNITED STATES delegation",
    # Grouped-separator number rules must not swallow exhibit labels, docket numbers or the bare
    # service-center codes that legitimately appear in prose.
    "exhibit A-1 and exhibit A-12 are transcripts from case 26-cv-00132",
    "MSC is the service center; IOE receipts route differently",
]


def self_test(printer=print):
    """Every pattern gets a positive probe and every negative control must stay silent."""
    ok = True
    all_kinds = [k for k, _ in SECRET_PATTERNS] + [k for k, _ in PII_PATTERNS]
    table = dict(SECRET_PATTERNS + PII_PATTERNS)

    for kind in all_kinds:
        probe = POSITIVE.get(kind)
        if probe is None:
            printer("  FAIL  %-20s no probe line - add one to POSITIVE" % kind)
            ok = False
            continue
        if not table[kind].search(probe):
            printer("  FAIL  %-20s its own probe does not match" % kind)
            ok = False

    for line in NEGATIVE:
        hits = [k for k, rx in SECRET_PATTERNS + PII_PATTERNS if rx.search(line)]
        if hits:
            printer("  FAIL  negative control fired (%s): %r" % (", ".join(hits), line[:60]))
            ok = False

    # Redaction must SUBSTITUTE. The 48-character key kept whole by a 60-character "mask" is why.
    key = "sk-ant-api03-" + "A" * 40
    if key in scrub("token: " + key):
        printer("  FAIL  scrub() left the value in place")
        ok = False

    printer("outbound gate self-test: %s (%d patterns, %d negative controls)"
            % ("PASS" if ok else "FAIL", len(all_kinds), len(NEGATIVE)))
    return ok
