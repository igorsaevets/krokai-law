# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-02

First release. Extracted from a working system that had been developed against a live matter over
several weeks, where every feature below was produced by a measured failure rather than a design
session. The complete list of those failures is the incident log in
[FEATURES.md](FEATURES.md#the-incident-log).

### Added

- **The checker.** Fifteen verdicts over every quotation in your drafts against every primary source
  on your disk. Three of them exist because a pass/fail tool answered *verified* about a defect that
  was heading for a filing: a quotation that stops one clause before the words limiting it, an
  ellipsis hiding the words that narrow a rule, and the right words under the wrong address.
- **Address binding.** *"Found in the corpus"* and *"found where you said"* are separate questions
  with separate failure modes. Four outcomes, and *"could not check"* is one of them — because for a
  document that gets filed, an unverifiable address must not render as a pass.
- **Citation packs** as data. Three ship — US federal, US immigration, US tax. Adding a body of law
  is a JSON file, not a code change.
- **The quote bank and the queue.** The bank is a decision a person makes and nothing writes to it
  automatically; the queue is a list of undone work that a hook writes after every turn. They are
  separate because automatic entry would bury the four quotations that matter under sixty-one that
  do not.
- **Three hooks** — the part that makes the rest happen without anyone remembering. The argument for
  them is a measurement: an instruction to check every quotation was obeyed while the task was about
  checking and **not once** across three rounds where the task was strategy. *Rules fire by topic,
  not by rule.*
- **A hook installer** that merges rather than replaces, backs up first, prints its diff, is
  idempotent and uninstalls exactly its own entries. Because a toolkit whose central mechanism needs
  a manual JSON edit will be installed with the mechanism missing.
- **PDF text sidecars.** Your file-search tool does not read PDFs and does not say so. In one
  measured library that was 67 files, 35 % of it, where every *"I searched and found nothing"* had
  been a false negative.
- **The outbound gate** — 10 credential detectors with no override, 11 personal-identifier detectors
  with one. It reports kind and line number and never the value. Its probe lines are derived from
  the pattern tables, so a newly added detector fails the suite until it is given one.
- **Prompt language** that gets an outside model to do legal research instead of refusing, with the
  measurement showing the refusal was about framing rather than subject matter — and the one line
  that measurably stops fabricated quotations.
- **Reviewer-answer auditing.** `lawverbatim review --audit` runs every quotation from every outside
  reviewer through the same checker as your own drafts. This is the step an orchestration harness
  cannot do, and it is the reason the two are separate programs.
- **A mutation bank.** Every defect class ever paid for, applied to quotations the checker already
  blessed, counting how many it still calls clean. Holes found for free rather than in a filing.
- **`casefile.json`.** The system this came from had absolute paths compiled into eleven scripts,
  including a cloud-synced folder name and a person's user account.
- **81 behavioural self-checks.** No network, no configuration, no credentials.

### Found by the toolkit's own tests, before release

Recorded because a changelog that lists only features is a sales document.

- An inserted negation was reported as `ALTERED` rather than `OPERATOR`. `ALTERED` is true and
  nearly useless — *"something after the halfway mark differs"* — when the thing that differs is
  `not`. The word-level comparison now runs at the anchor and upgrades the verdict.
- A hyphenation difference was reported as the drafter's punctuation problem rather than the corpus's
  damage, because the looser test ran first. Same evidence, opposite instruction. Narrower diagnosis
  first.
- `SCATTERED` was classified as both dangerous and clean. Caught by an invariant the suite asserts:
  every verdict must be in exactly one list, or anything that iterates will silently treat it as
  harmless.
- The mutation sample exercised one mutation of seven, because the sample quotation happened to
  contain no modal verb, no negation and no digit. A regression bank that only ever runs one
  mutation is not a regression bank.

### Found on the first run against real sources

- 🔴 **This toolkit's own quote-bank template was extracted as a quotation of law and reported
  `NOT_FOUND`** — a false alarm manufactured by its own template, which put house rules inside a
  blockquote. Blockquotes containing a markdown heading are now recognised as callouts; the test is
  narrow, because numbered lists inside quoted statutes are common and headings are not.
- *"Punctuation differs"* named no character, so the reader still had to diff it by hand — which
  means they do not, and the finding is skipped. It now names what differs: on the run that found
  this, ``the source also has `*` `` — a list bullet the drafter had silently swallowed while
  quoting across two items.

### Known limitations, stated rather than implied

- **It does not know whether a rule is still in force.** It compares against your disk. A repealed
  regulation verifies perfectly.
- **It cannot catch the right words under a pincite to the wrong page of the right document.** A
  published checklist once quoted a decision's editorial headnote while citing the page of the
  opinion, where the sentence differs by one word that mattered. Both sentences are genuinely in the
  PDF. No string comparison can catch this. It needs a reader.
- **A flag can mean the tool is wrong.** Your downloaded copy may itself be incomplete — measured, a
  scraped agency chapter held four of its six bullet points, so a correct quotation of the missing
  text came back flagged. The order in which to rule things out is printed with every miss.
- The copyright holder in `LICENSE` reads *the lawverbatim contributors*. A fork or a named maintainer
  should set it deliberately — and should know that a generator which rewrites author names across a
  repository can silently mangle a copyright line, which has happened.

[0.1.0]: https://github.com/<owner>/lawverbatim/releases/tag/v0.1.0
