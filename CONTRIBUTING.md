# Contributing

## The one house rule

**A change to a detector or a verdict comes with the case that motivated it.**

Not a description of the case — the text. A quotation, the source text it should have matched, and
the verdict it produces now. That case becomes a permanent check in `verbatim/selftest.py`.

The reason is in the project's own history: every rule in this codebase whose reason was written down
survived, and the ones that were not got "simplified" back out by someone who could not see what they
were for. `normalise()` alone carries four transforms that each look like superstition and each cost
a wrong conclusion.

## Before opening a pull request

```bash
python -m verbatim selftest        # must be N/N
python -m verbatim gate --self-test
```

If you touched `verify.py`, also run the regression bank against a real corpus:

```bash
python -m verbatim mutate --limit 60
```

The number that matters is not the catch rate. It is whether your change **increased** the
false-clean count relative to the run before it.

## Adding a citation pack

A pack is a JSON file in `packs/`, and adding a body of law needs no Python. Field reference:
[FEATURES.md](FEATURES.md#citation-packs). Copy `us-federal.json` and work from it.

Two things to get right, both of which have bitten:

- **An alias table** when two citation systems name the same provision. Without it a correct pincite
  reads as a mismatch, and it is the kind of gap only one reviewer in four ever notices.
- **A negative guard** when two subdivisions share a number. In one agency manual, volume 7 part A
  chapter 8 and volume 7 part B chapter 8 are different chapters — and one of them was an entire
  argument.

Add a case to `suite_citations()` in the self-test. Note that the suite **derives** its expectations
from the shipped packs rather than restating them, so adding a pack must not turn existing checks
red. If it does, the check was copying configuration instead of computing it, and that is the bug.

## Adding a detector to the outbound gate

Add the pattern **and** a probe line in `POSITIVE`. The self-test fails otherwise, on purpose: probes
are derived from the tables so that a new pattern cannot ship untested. Coverage was once lopsided in
exactly the wrong direction — the class with a human override had six tests, the class with no
override had one.

Two rules that are not negotiable:

- **Require a value, not a label.** A pattern that fires on the word *passport* will fire on the
  sentence documenting it, users will learn to pass the override by reflex, and the override disables
  the whole class. If your pattern would match a sentence in this repository's own prose, add that
  sentence to `NEGATIVE` and make the pattern narrower.
- **No trailing `\b` after a label that can end in a full stop.** Between `.` and a space there is no
  word boundary, so `passport no\.\b` never matches. This has been found four separate times in one
  pattern set.

## Style

Match what is there. In particular: **a comment says why, not what.** `# strip the marker` is noise;
`# a blockquote marker survives normalisation and breaks byte comparison on a multi-line quotation -
this fired three times in one session` is the reason the line cannot be deleted safely.

Prefer one implementation over two. If you find yourself copying a helper, that is the signal to
import it: the normaliser in this project was retyped three times in a day and each copy forgot a
different transform.

## What will be declined

- **A similarity percentage as a verdict.** Percentages cannot see negation: inserting one word into
  a 50-word quotation breaks 6 shingles of 45 and scores 86.6 %, which is how `shall` → `shall not`
  once passed as a typesetting artefact.
- **Anything that reads a scanned page with a language model.** It produces plausible text, the
  plausible text becomes a quotation, and the quotation is then treated as the primary source.
- **Network access in `selftest`.** The suite's promise that it contacts nothing is what lets it run
  under privilege and in CI with no credentials.
- **A change that makes a report shorter by dropping the "could not check" outcomes.** `NOT_FOUND`
  meaning both *invented* and *never downloaded*, or a silent per-turn cap, is precisely how a real
  problem hides in a pile of shrugs.

## Reporting a bug in a verdict

Include the quotation, the source file (or enough of it), the verdict you got and the one you
expected. A verdict disagreement is usually not a matter of opinion — it is a missing test.
