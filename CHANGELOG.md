# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- KROKAI-SELFTEST: DISCUSSES-PLACEHOLDERS - this log quotes the defects it records, and one
     of them is an unreplaced clone-URL placeholder. The self-test's placeholder check honours
     this declaration for a document that declares it, and refuses the declaration outright to
     README.md, README.ru.md, INSTALL.md and INSTALL-FOR-AI.md - the files a reader copies
     commands out of. Exempting a declared file is auditable; exempting a filename is the
     allowlist mistake that shipped a mangled LICENSE in a sibling project. -->

## [0.3.0] — 2026-08-02

The release made by re-reading what 0.2.0 said about itself before publishing it. Everything below
was found by checking the documents against the code, not by running the tool.

### Fixed — seven claims this project made about itself and got wrong

- **`krokai --version` printed `0.1.0`** while the changelog documented `0.2.0`. Two homes for one
  fact, and the executed one was the stale one. A self-test now reads the newest changelog heading
  and compares it with `__version__`.
- **The personal-data detector count read 11 in three shipped documents and 12 in the table**, ever
  since the house-number detector was added — in a file whose entire promise is that its numbers
  were measured rather than estimated.
- 🔴 **The guard written to catch exactly that could not see the sentence carrying it.** A
  deliberately falsified `99` sat in `README.md` through a clean run, because the check demanded the
  word *detectors* between the number and the class and the README's second count has none. Fixed
  twice over: the word is optional now, **and** every document must be shown to state *both* counts
  where the check can read them. Correctness alone would have gone on passing.
- **The tier-D stamp still carried the previous product name.** Renaming without noticing would have
  dropped every existing report back into tier C, which is incident 3 — the largest number in the
  whole log. The tool now writes one stamp and recognises several.
- **A supported install died with no verdict.** `channels.json` sits beside the package, so copying
  only `krokai/` — install method 4, the locked-down work laptop — killed the suite with a bare path
  list, in front of an installer told to stop and report if any check fails. `SystemExit` does not
  derive from `Exception`, so the obvious catch caught nothing.
- **The changelog described `LICENSE`'s copyright holder, and described it wrongly.** It points at
  the file now instead of restating it.
- Placeholder clone URLs (`github.com/<owner>/…`) in four documents, including both READMEs — the
  first command a new reader runs.

### Added

- **`selftest` reads the documentation now.** Stated detector counts are compared with the tables,
  every relative link in `README.md` must resolve to a file, and no shipped document may contain a
  placeholder. Six negative controls prove each check fails when it should. The suite's own count is
  deliberately written down nowhere: it changes on almost every commit, and a guard that fires on
  every commit is a guard someone deletes.
- **Rename safety as an assertion** rather than a memory: what gets stamped must carry the current
  name, and the previous name must still be recognised.

### Changed

- The tier-D sentinel written into new reports is `KROKAI-TOOL-OUTPUT`. Reports already stamped with
  the previous name are still recognised, and will stay recognised.

## [0.2.0] — 2026-08-02

Corrects an architecture error in 0.1.0 that was found by a reader, not by a test.

### Changed — the correction

0.1.0 shipped the checker and pushed the whole second opinion into a separate program, on the
grounds that two files covering one subject drift apart and the read-only copy rots first. That
reasoning is sound and it was applied to the wrong boundary.

What went across the line with the transport was not transport. It was **trust**: deciding whether
an answer is usable, deciding whether its *sourcing* is usable, recording what was sent and to whom,
and stopping your own instruction files from reaching a vendor. Those belong beside *check the
reviewer's quotations*, which nobody proposed to move out.

    a separate harness, if installed  ->  transport: get answers back
    this toolkit                      ->  trust: what may go out and what may be believed

The practical cost of the old boundary fell entirely on the reader: `review` without that other
program installed printed instructions and did nothing.

### Added

- **`consult.py` and `channels.json`.** Multi-model review with the channel set in configuration
  rather than code. Shipped channels are **command-line tools on subscriptions you already pay
  for — no API key**. The one metered kind ships disabled, and a self-test asserts that no metered
  channel is ever enabled by default.
- **A plan printed before anything is sent**: channel, vendor, transport, cost, and whether the
  binary is actually installed. `--dry-run` is a complete preflight and spends nothing.
- **Failure grading from machine codes, never prose.** The predecessor searched warning text for
  substrings, and marked FAILED the honest *"my search found no confirmation"* its own brief asks
  for; `not set` matched the finding *"the regulation does not set a deadline"*. Five negative
  controls now hold that line.
- **Grounding classification** of every URL a reviewer cites — primary, annual-edition snapshot,
  commentary — labelled **derived** wherever shown, because a model can print a URL it never opened.
- **A neutral working directory** before dispatch, because one agent CLI was measured injecting the
  instruction file of its launch directory into the vendor's context, outside the outbound gate.
- **`ANALYTICS.md` written every run, unasked** — an instrument report about the reviewers that
  states plainly it says nothing about whether they are right.
- Further self-checks. The total is deliberately not recorded here: it was written down as
  **123** while the suite actually stood at 147, which is the same defect this release is
  mostly about. `krokai selftest` prints the number it just ran.

### Changed by an outside review of this release

Four independent models were sent this design. Their disagreement was the product; two of them
converged on the same weakness, which is what made it credible.

- 🔴 **"Grounding" was renamed, because the word was doing work it had not earned.** Two reviewers
  independently attacked the same mechanism: a URL printed in an answer is produced by the *same
  process* that produces a fabricated quotation, so it is not an independent signal — and knowing
  that an official source ends in `.gov` is exactly the knowledge needed to mint a convincing one.
  Presenting the count as grounding manufactures corroboration out of the model's own assertion,
  which is this toolkit's founding failure repeated one level down. The counts stay, because *what
  an answer asks you to rely on* is worth knowing. The word that implied retrieval is gone, and the
  report now says **printing is not opening**.
- 🔴 **An annual edition is official law.** It was tabulated opposite `primary`, so a channel citing
  three government codifications printed as `primary 0` — which reads as *cited nothing official*
  and is false. It is the codification; it is simply not the text in force. Now counted as official
  **and** flagged as dated.
- **The exposure a second opinion creates is now printed in the plan**: *N independent vendors will
  each receive this material in full.* Multiplying the opinions multiplies the confidentiality risk,
  and naming it is not preventing it. In the plan rather than the documentation, because a warning
  in a README is read once.
- **Prior art added to the README** — `eyecite`, `citereview`, and three commercial tools, none of
  which the author had found.

Recorded and **not** adopted: two reviewers proposed storing an encrypted copy of every payload so a
ledger could reproduce it. That would create a second copy of the client's material inside the tool
built to stop exactly that. The whole ledger has since been cut — see below.

### Removed before release

- **Every record of what was sent where.** Three features, cut in sequence on the author's
  instruction: the persistent dispatch ledger, the brief hash printed before sending, and the
  per-vendor retention column in the plan. What replaced them is nothing, deliberately — the round
  produces the answers, the report, and the check of their quotations, and nothing outlives it.
  A self-test asserts all three stay absent, because each reads as obviously useful in isolation and
  would otherwise be reinvented by someone who could not see it had been weighed.

### Fixed — all seven found before the first paid round, six by reading the plan

- The same vendor would have been asked the same question **twice** when a harness was installed
  alongside a built-in channel — double cost, and two answers from one model read as two independent
  opinions agreeing.
- The completion marker was not passed to a delegated harness, so every complete answer would have
  been reported truncated, inviting a re-run and a second bill.
- `--harness-args` was accepted and silently ignored.
- The historical-edition check **could never fire**: URLs were lower-cased and the patterns were not.
  It ran, found nothing, and read as a clean result. Its own test caught it.
- A disabled-but-installed channel printed as `ready: yes`, which reads as *will run*.
- *"Installed but ignored by a flag"* printed as *"none installed"*, sending the reader to look for
  an installation problem that did not exist.
- 🔴 **"Quote the section IN FULL" was demanded of every brief**, including one containing no
  statutory text at all. Second measured instance of a false positive in this toolkit's own safety
  checks — and by its own doctrine that outranks a miss, because it teaches the reader to dismiss
  the whole class by reflex. Every requirement now declares when it applies.

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
- **Reviewer-answer auditing.** `krokai review --audit` runs every quotation from every outside
  reviewer through the same checker as your own drafts. This is the step an orchestration harness
  cannot do. ~~And it is the reason the two are separate programs.~~ **SUPERSEDED in 0.2.0** — that
  conclusion was wrong, and the correction is the headline of the next release.
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
- **Read `LICENSE` for the copyright holder; it is not restated here.** An earlier draft of this line
  named a holder the file did not contain — a second copy of a fact, disagreeing with the first. A
  fork should set the holder deliberately, and should know that a generator rewriting author names
  across a repository can silently mangle a copyright line. That has happened, in a sibling project,
  and it shipped that way for the repository's entire life because a per-file allowlist told the leak
  scan to skip `LICENSE`.

[0.3.0]: https://github.com/igorsaevets/krokai-law/releases/tag/v0.3.0
[0.2.0]: https://github.com/igorsaevets/krokai-law/commit/8c6648c
[0.1.0]: https://github.com/igorsaevets/krokai-law/commit/002f6d1

0.1.0 and 0.2.0 link to commits, not to releases: they were real states of this repository
and they were never published, so a release tag for either would be a link to something that
does not exist. 0.3.0 is the first published version.
