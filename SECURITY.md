# Security

## Reporting a vulnerability

Use **GitHub's private vulnerability reporting** on this repository: the Security tab →
*Report a vulnerability*. Please do not open a public issue for anything exploitable.

🔴 If that button is not visible to you, the feature is not enabled and this document is lying.
Say so in a normal issue — without details — and it will be fixed. A published security channel that
does not exist is worse than none, and it has happened before: a project's `SECURITY.md` pointed
researchers at a button that had been disabled the whole time, and nothing ever checked.

**There is deliberately no security email.** A no-reply address attributes commits correctly and has
no mail exchanger at all, so mail to it is discarded without a bounce. A reporting channel that
silently swallows a report is worse than an absent one.

## What this software touches

This matters more than usual, because the intended users hold privileged material.

**At rest, on your machine.** It reads the folders you configure and writes reports, a quote queue
and PDF sidecars beside your sources. That is all.

**On the network: nothing.** No command in this toolkit contacts a vendor, an API, or an update
server. There is no telemetry. `lawverbatim selftest` passes on a machine with no network at all, and
that is asserted by the suite rather than promised in prose.

The one exception is explicit and yours: `lawverbatim review` can hand a brief to a **separate**,
separately-installed review harness that does contact vendors. It is not bundled, it must be found on
your machine or named by you, and the brief passes through the outbound gate first.

**Secrets are never printed.** The gate reports the *kind* of a match and the *line number*, never
the value — printing the match to prove the check works would leak it into the transcript, which is
the same mistake one step earlier.

## If you have leaked a credential

🔴 **Rotate it. Do not scrub the record.**

A key that has been written to a transcript is compromised. Transcript files are disk-backed,
replayed into later model context, and frequently archived; editing one afterwards does not un-send
it and does not remove it from any copy. Rotation is the only remedy that actually works, and it is
usually one click.

## Threat model, stated honestly

**In scope.** Reading only what you configure. Never printing a matched secret or identifier. Never
writing outside your matter folder and the system temp directory. Not contacting a network. Not
mangling another program's configuration file — the hook installer merges, backs up, and refuses to
touch a settings file it cannot parse.

**Out of scope.** This is not a sandbox and does not defend against a malicious file in your own law
folder. It parses PDFs, DOCX and XML using third-party libraries; a hostile file could in principle
exploit one of those, and the mitigation is that they are your own downloads from government sources.

**Not a legal control.** Passing the outbound gate is not a privilege determination. It is a
mechanical check with a stated pattern list, and it is the last thing between a paste and a vendor —
not a substitute for deciding what may leave your office.

## Personal data

The gate ships 11 personal-identifier detectors, and they are **selective on purpose**: cut what
identifies a person, keep what lets a reviewer check a fact. A reviewer cannot confirm "this
neighbourhood is inside the city limits" against `[ADDRESS]`, and that check is often the reason to
send the document out at all.

The line drawn: **a unit number turns a street address into a person; the street itself is
geography.**

The list is not, and cannot be, complete. Adding your own patterns is a small edit to
`lawverbatim/redact.py`, and the self-test will demand a probe line for any pattern you add — which is
the mechanism that keeps coverage honest.
