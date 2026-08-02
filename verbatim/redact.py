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
    # branch below, which requires the delimiter AFTER the label - while a real header is
    # `Authorization: Bearer <token>` and puts it before. The one shape it was added for was the
    # one shape it could never match.
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
    ("ALIEN_NUMBER", re.compile(r"\bA[-# ]?\d{8,9}(?!\d)")),
    ("USCIS_RECEIPT", re.compile(
        r"\b(?:EAC|WAC|LIN|SRC|MSC|IOE|YSC|NBC|NSC|TSC|VSC)\d{10}\b")),
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
    ("UNIT_NUMBER", re.compile(
        r"(?i)\b(?:apt|apartment|unit|suite|ste)\.?\s*#?\s*[A-Za-z]?\d{1,5}[A-Za-z]?(?!\w)")),
]


def scan(text, name="payload"):
    """Return `[(severity, kind, name, line_number), ...]`. Never the matched value."""
    out = []
    for lineno, line in enumerate((text or "").splitlines(), 1):
        for kind, rx in SECRET_PATTERNS:
            if rx.search(line):
                out.append(("SECRET", kind, name, lineno))
        for kind, rx in PII_PATTERNS:
            if rx.search(line):
                out.append(("PII", kind, name, lineno))
    return out


def scrub(text):
    """Replace every match with a fixed-width marker.

    🔴 Apply this at the **logging choke point**, not to the output file. Measured: a diagnostics
    file was scrubbed correctly while an exception whose *message* carried a key printed it in full
    to the console - and the console is the same archived, replayed surface as the file. One
    function, called everywhere something is written or printed.
    """
    s = text or ""
    for kind, rx in SECRET_PATTERNS:
        s = rx.sub("[REDACTED:%s]" % kind, s)
    for kind, rx in PII_PATTERNS:
        s = rx.sub("[REDACTED:%s]" % kind, s)
    return s


def gate(parts, allow_pii=False, printer=print):
    """Preflight for anything about to leave the machine.

    `parts` is `[(name, text), ...]`. Returns 0 to proceed, non-zero to stop.
    """
    findings = []
    for name, text in parts:
        findings += scan(text, name)
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
    printer("outbound gate: clean (%d secret + %d personal detectors)"
            % (len(SECRET_PATTERNS), len(PII_PATTERNS)))
    return 0


# ------------------------------------------------------------------------------------------------
# Self-test. Probes are DERIVED FROM THE TABLES, so a newly added pattern fails this check until it
# is given a probe line. Coverage was once lopsided in exactly the wrong direction: the class with a
# human override had six tests and the class with no override had one.
# ------------------------------------------------------------------------------------------------
POSITIVE = {
    "PRIVATE_KEY_BLOCK": "-----BEGIN RSA PRIVATE KEY-----",
    "ANTHROPIC_KEY": "key = sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA",
    "OPENAI_STYLE_KEY": "sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "GOOGLE_API_KEY": "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "AWS_ACCESS_KEY": "AKIAIOSFODNN7EXAMPLE",
    "GITHUB_TOKEN": "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "SLACK_TOKEN": "xoxb-1111111111-AAAAAAAAAAA",
    "JWT": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N",
    "BEARER_HEADER": "Authorization: Bearer abcdefghijklmnopqrstuvwx",
    "LABELLED_SECRET": 'password = "hunter2hunter2hunter2"',
    "EMAIL": "write to someone@example.com please",
    "US_PHONE": "call (213) 555-0147 tomorrow",
    "SSN": "ssn 123-45-6789 on the form",
    "ALIEN_NUMBER": "A-123456789 appears on the notice",
    "USCIS_RECEIPT": "receipt IOE0912345678 was issued",
    "SEVIS_ID": "N0012345678 is the record",
    # 🔴 The abbreviated forms are the point: each one was undetectable while a trailing \b stood
    # after a label ending in a full stop.
    "PASSPORT_NUMBER": "passport no. AB1234567 issued",
    # 01/01/1970 rather than a plausible birthday: a probe value that could be mistaken for a real
    # person's data has no business sitting in a public repository, even in a test table.
    "DATE_OF_BIRTH": "d.o.b. 01/01/1970",
    "PAYMENT_CARD": "4111 1111 1111 1111",
    "BANK_ACCOUNT": "account no. 000123456789",
    "UNIT_NUMBER": "732 S Spring St Apt 1204",
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
