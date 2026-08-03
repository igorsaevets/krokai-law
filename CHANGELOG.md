# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- KROKAI-SELFTEST: DISCUSSES-PLACEHOLDERS - this log quotes the defects it records, and one
     of them is an unreplaced clone-URL placeholder. The self-test's placeholder check honours
     this declaration for a document that declares it, and refuses the declaration outright to
     README.md, README.ru.md, INSTALL.md and INSTALL-FOR-AI.md - the files a reader copies
     commands out of. Exempting a declared file is auditable; exempting a filename is the
     allowlist mistake that shipped a mangled LICENSE in a sibling project. -->

## [0.6.0] — 2026-08-03

The release that came from being reviewed by the project this one was extracted from. It found
three defects by reading the source, and the sharpest one is the reason 0.5.0 is withdrawn.

### 🔴 0.5.0 IS WITHDRAWN — tag and release deleted, history rewritten

The 0.5.0 write-up of the grouped-identifier defect illustrated it **with the applicant's real
A-number and receipt number**, in four tracked files including two self-test fixtures. Those
values were published for roughly six hours in a single commit that was also the release tag.

They are gone from every reachable ref, but **treat them as disclosed**: GitHub can serve an
unreferenced object by its SHA until garbage collection, and anything that mirrored the repository
in that window kept a copy.

Two details worth carrying, because neither is obvious:

- **The self-test was what kept the values in the file.** They were the positive fixtures for
  `ALIEN_NUMBER`, so the detector fired on them and the suite went green. A passing test was
  evidence *for* the leak.
- **The probe line was printed on failure**, so the block leaked twice over: once by sitting in
  the file, once by publishing its fixture to the console whenever it went red.

The control that would have caught it now exists and is permanent — see *Added*.

### Fixed

- 🔴🔴 **The surname redaction did not exist.** `README` feature #6 promised the surname was cut;
  `FEATURES.md` explained it was configured per matter. In the code `gate()` had no `surnames`
  parameter, `config` had no such key, and no caller ever passed any. A brief carrying the
  client's full name passed the gate, which printed `clean`. Worse than a missed detection: the
  output asserted the opposite of what happened. Traced by an outside reviewer through the call
  chain; confirmed here by execution. `surnames` is now threaded from `casefile.json` through
  `gate`, `prepare` and `run_round`, the gate prints how many are configured — **including zero**
  — and the regression test runs the real CLI end to end, because every earlier probe called
  `scan()` directly and so supplied what the product did not.
- 🔴🔴 **`krokai quote` and `krokai check` disagreed on five of six realistic inputs.** One
  normaliser, three pipelines: the `check` path stripped markdown, the `quote` path did not. And
  the disagreement was not found-versus-missing — a quotation stopping one clause short of a
  limiter came back `TRUNCATED_CONDITION` one way and `PUNCTUATION` the other, so markdown residue
  **downgraded the most dangerous verdict this tool has into a cosmetic one**. `check()` now
  prepares the quotation itself and no caller can forget.
- 🔴 **`strip_markdown` deleted the CFR omitted-text marker `* * *` from quotations** while the
  corpus side deliberately kept it — the asymmetry `strip_scrape_artifacts` reasons about, seen
  from one side only. Markers are now preserved verbatim, and the negative control is that two
  adjacent bold spans are still stripped: the obvious pattern protects the `* *` between them.
- 🔴 **A source file under 200 characters was dropped from the corpus and the user was told to
  OCR it.** The floor answers "did the extraction fail?", which is a question about PDFs; applied
  to `.txt` and `.md` it threw out perfectly readable short provisions — a definition, a savings
  clause — and every quotation of them came back `NOT_FOUND`, which is this tool's fabrication
  signal. Short text sources are now indexed and reported separately, so a downloaded placeholder
  is still noticed without a real short provision being called invented.
- 🔴 **A filled PDF form read as a blank one.** Field values live in `/AcroForm /Fields` as `/V`,
  not in the page content, so a completed agency form and an empty one produced the same text.
  `read_pdf` now appends `field name = value` for every filled field, empty fields are not
  invented, and such a file is no longer diagnosed as a scan needing OCR.
- 🔴 **An exception message and a channel's stderr reached the report unscrubbed**, cut to 200
  characters — and this project's own gate docstring records that truncation is not a mask. Both
  now go through `scrub()`. This is what `scrub()` was written for; the port had dropped its call
  sites, which is why it looked like dead code.
- Secrets are scanned a second time over the whole payload with line breaks folded, because real
  briefs wrap and a key broken across a newline was invisible to every per-line pattern. Secrets
  only: for the class with an override, a manufactured adjacency would teach the `--allow-pii`
  reflex.
- The SSN probe used a value whose area code is real and issued, while the module claimed it was
  "in a range that was never issued". Replaced with one that violates three separate rules of
  SSA POMS RM 10201.035, cited in place.

### Added

- **`NO_SOURCE_ON_DISK` — a third bucket, because `NOT_FOUND` meant two things** and its own
  explanation said so: *"either the source is not downloaded, or invented."* Measured in the
  sister project on a real filing: **20 of 37 flagged items** were quotations of agency press
  releases whose sources are not in a corpus of law by construction. The genuine misses were
  hiding in them. A miss whose cited authority resolves to nothing on disk is now reported
  separately, counted separately, and never as a pass — and if the cited source **is** on disk,
  the verdict stays `NOT_FOUND` and says so, which is the stronger accusation.
- **A self-test that scans every file in the repository with the project's own detectors** and
  permits only the documented fictional values. The allow-list is a set of VALUES, never of
  filenames: exempting `redact.py` would have exempted the leak. It asserts its own coverage, and
  it proves it works by scanning a planted identifier in the same call. It caught the first draft
  of its own explanatory comment.
- `redact.FICTIONAL` — one home for every identifier-shaped literal in the tree, stating for each
  whether it is *documented invalid* by a primary source or merely *constructed implausible*.
- Every secret probe is assembled from fragments, so no key-shaped literal exists in the source.
  A reviewer measured their own scanner stripping five values out of this file before their model
  saw it; a `PUBLISH-AUDIT: PATTERN-SOURCE` declaration is prose, and no scanner reads prose.

## [0.5.0] — 2026-08-03 — WITHDRAWN, see 0.6.0

The release where the documented install command turned out to have never worked - found by
finally EXECUTING the install document in an empty folder instead of reading it - and where five
silent defects were confirmed by probe in one afternoon, every one of them a class already paid
for in the sister project this toolkit was extracted from.

### Fixed

- 🔴 **`python <clone>/krokai <command>` - the form INSTALL-FOR-AI.md prescribes - crashed with a
  relative-import error since the first release.** Directory-run gives `__main__.py` no parent
  package. Every earlier test had run `-m` from inside the clone, where the working directory
  quietly supplies what the documented command does not. `__main__.py` now bootstraps `sys.path`
  itself, and the self-test runs the package directory from a foreign working directory as a
  permanent regression lock.
- 🔴 **A citation could claim a neighbouring part's file.** `file_matches` compared numbers as
  substrings, so part 245 matched `8CFR-1245.2-EOIR.xml` and `part-245a`, and `usc 255` matched
  inside `1255` - and the address layer then BLESSED the wrong file. Numbers now match as tokens,
  in two name forms at once (separator-preserving and flattened), because each form is blind where
  the other sees: flattening finds `PM6020199…`, separators tell part 245 from part 245a.
- 🔴 **The name rule for numbered policy memoranda had never fired once**: the captured `602-0199`
  kept its dash while the flattened filename lost its own. Found by the verification suite for a
  different fix, which is the usual way.
- 🔴 **A truncated-but-alive PDF extraction beat a complete one.** The engine chooser only knew
  "fewer tokens = fewer split words", so 50 words could win over 5 000. Truncation is now measured
  in characters and splitting in tokens - splitting inserts spaces and cannot double the length;
  losing pages can - so the two failure modes cannot shadow each other.
- 🔴 **Two different quotations sharing their first 60 characters read as one banked entry.**
  Regulatory prose is full of shared openings ("The Secretary may in his discretion…"), and the
  second quotation silently never reached the queue. `in_bank` now compares the whole quotation,
  and a bank entry wrapped across several `> ` lines still matches.
- 🔴 **Alien numbers and receipt numbers written WITH separators walked through the outbound
  gate.** Real notices hyphenate them into groups; the rules and their probes both assumed the
  fused spelling, and a probe built from the same assumption as the rule verifies only itself.
  Grouped forms are now caught by rule, probe and negative control, and `Apt A-1` style unit
  numbers are caught too.

### Added

- **The lookalike detector now knows the NAMES of your official sources, not only the `gov`/`mil`
  labels.** `uscis.com` - the exact agency name in a foreign zone, not a typo - walked straight
  past the label test. Citation packs now declare `official_domains`, `krokai review` merges them
  into the grounding, and a host wearing a configured name as a whole label (`uscis.com`,
  `irs.com`, `uscis.phishing.example`) is flagged for a human. The residual stays printed instead
  of closed: a MISSPELLING (`ussciss.us`, live when checked) is undetectable by construction.
- **"One provision, two texts."** The same provision quoted both clean and flagged anywhere in the
  matter is now paired and reported - ported from a measured incident where a correction landed in
  a memorandum body and missed the exhibit caption below it, so the truncated copy sat exactly
  where the officer looks first. Fix every occurrence, not the first.
- **`krokai init` writes an assistant block into the matter's `CLAUDE.md`** (append/refresh
  between markers, never replacing the file), with the real commands for that machine rendered in.
  A project-root `CLAUDE.md` is the one instruction surface re-read at every session start and
  after every `/compact` - the block existed as a template since 0.1.0, and nothing in the install
  path had ever placed it. `doctor` now reports both post-compact mechanisms - hooks wiring and
  this block - each with the exact command when absent.
- **Every address-bearing citation shape now carries a `sample` sentence, and the self-test pushes
  each through `find_positions -> keys`** - the scanner's own pipeline. Ported from a sister-project
  incident where an address kind was verified by calling the parser directly while the recogniser
  feeding it never matched that citation style: a probe into a function cannot see a hole in the
  pipeline that feeds it.
- **A four-channel outside review of this very diff, adjudicated by execution.** Confirmed and
  fixed: the extraction chooser fired in the WRONG direction (a truncated alternate beat a
  complete primary because "more tokens" read as "split words") and its 1.01× hair trigger let
  two hyphen artefacts outvote a missing paragraph; the `245a` veto missed `part245a` written
  without a separator; `www.uscis.gov` in the configuration taught the lookalike detector
  nothing; grouped identifiers with non-breaking spaces, an `A#`-with-space form, an OCR'd
  lower-case one, `Suite B` and `PH-1204` walked through the gate; and the CLAUDE.md writer had
  three corruption
  vectors - orphaned markers, non-UTF-8 files, CRLF files - now refused or preserved, with the
  write made atomic. Refuted with traces and kept as controls: the planted canary (4 of 4
  channels refuted it, quoting the code), plus two findings whose premises the pipeline
  disproves. Self-test grew from 208 to 292 checks; every confirmed finding is locked open.

## [0.4.0] — 2026-08-02

The release where the tool that checks other people's sources was caught calling a Russian domain,
a Chinese domain and an Italian city **official United States law**.

Everything here began as a port: a separate, private matter running the same disciplines produced a
list of improvements, and the question was which of them generalise. Answering it meant reading this
code against that list — and the two worst findings were not on the list at all. Both were found by
running probes; neither by reading.

### Fixed

- 🔴🔴 **A substring test promoted hostile domains to `primary`** — the bucket that means *this is
  the law itself*. The line was `host.endswith(s) or s in host`, and the second half of it graded
  `www.milano.it` (`.mil` sits inside `milano`), `uscis.gov.ru`, `law.gov.cn`, `www.mil.kg` and
  `ecfr.i0.gov.cm` as official law. Suffix matching is now anchored to a label boundary, so `.gov`
  matches `uscis.gov` and never `uscis.gov.ru`. The host is parsed by `urllib.parse.urlsplit`
  rather than by hand, which closes the `@`-userinfo, fragment and query bypasses OWASP's testing
  guide lists — that part came from a reviewer, not from the author.
- 🔴 **A citation to a government-lookalike host graded `OK`.** Such a host landed in `other`, which
  carried no warning at all, so nothing downgraded the round. There is now a `lookalike` bucket and
  a `GOV_LOOKALIKE_CITED` code for a host wearing `gov`/`mil` as a whole label while ending
  somewhere else. It is deliberately **threshold-free**: four independent reviewers were asked
  whether a similarity score belonged here and all four said no, in four different ways — the
  sharpest being that an edit distance can name the edit while a ratio can only say `0.75`, and
  *that* difference is the difference between a tripwire and a superstition. The three shapes tested
  are live domains, checked by DNS on 2026-08-02, not invented examples.
- 🔴 **`DIRTY` with the reason withheld.** `NO_TELEMETRY` counted toward the verdict, so with an
  external harness installed — the commonest configuration — *every* answer was `DIRTY`, always;
  and the console printer skipped that one code when listing warnings. A flawless answer citing one
  genuine government URL printed `[DIRTY] codex 379.0s 1620B cited 1 URL(s) (official 1)` and
  nothing else. Instrument codes are now reported and printed, and do not grade: what the answer did
  and what the instrument could see are two axes.
- **`VERIFIED` claimed more than it measured.** It said *"present word for word in a primary
  source"*; what it establishes is *word for word in a file in your sources folder*. A repealed
  regulation, last year's edition and a truncated scrape all pass. Four reviewers, asked separately
  what this design could not see about itself, all four named the corpus: its provenance is
  asserted and never proven. That gap is **not closed here.** It is now stated in the verdict
  itself, in both READMEs, and at length under *What is deliberately not covered*.
- **`prove()` could not prove a statute, and would not say why.** It returned the same bare `False`
  for *the identity check failed* and for *you asked me to check nothing* — and a statute, a
  regulation or a treaty has no party name to check. Not-checked is now reported as not-checked.

### Added

- **The brief asks for the three things the grader was already grading on.** `DATED_EDITION_CITED`
  has downgraded rounds for as long as the analytics have existed, while nothing in the brief ever
  told a reviewer to distinguish the date a rule was published from the date it took effect. An
  instrument stricter than its instructions does not measure care; it measures guessing. Added:
  **effective date** (with the annual-edition trap named), **no unsupported synthesis** (joining two
  real sources into a proposition present in neither — both citations check out and the sentence
  between them exists nowhere), and **two layers in order** (collect the sources with no
  conclusions, then conclude only from what is physically in layer one). A self-test asserts that
  every grading code has something in the brief it grades against.
- **`krokai quote` prints the sentence before and the sentence after** a located quotation. Shown
  for a quotation that *passed*, which is the point: a flagged quotation already sends you to the
  source, and a verified one is the one nobody opens again. It does not replace the
  `truncated condition` verdict — that is a detector, deliberately narrow; this is two sentences
  handed to a person.
- **Unrecognised hosts are named in the round report.** A typosquat carrying no official-looking
  label cannot be caught by a label-based detector, and closing that with a threshold was rejected.
  So the hole is printed instead: `other` is no longer a silent bucket.

### Changed

- Eleven **negative controls** now exist as a separate exercise: each breaks one new check on a copy
  of the tree and requires the suite to go red. Two did not fire on the first attempt — the corpus
  window clamps could be deleted with the suite staying green, because the assertion had been
  written where the damage is *read* rather than where it is *produced*, and every caller cuts the
  window at a sentence boundary before anything downstream can see the overrun. Third measured
  instance in this project of a guard that is correct and uncovering.
- Self-test: 161 checks → 208.

## [0.3.1] — 2026-08-02

Everything the tag `v0.3.0` did not contain, because a changelog entry describing code its own tag
never held is the same defect 0.3.0 was about.

### Added

- **Continuous integration** — this project's argument for its hooks, turned on itself: *run the
  suite before you push* is a rule, and rules fire by topic. No secret, no vendor. It settles two
  claims no local run can: the **Python 3.9 floor** `INSTALL.md` states and nothing had ever
  verified (green on a real 3.9.25 runner), and the suite on a machine with **no PDF or .docx
  library** — the state a locked-down work laptop is actually in. Five jobs, Ubuntu 3.9/3.11/3.13
  and Windows 3.13.
- **A build badge**, which is the opposite of the numbers this release spent its time deleting: a
  claim with an error signal. If the suite breaks, the front page says so without anyone editing it.
- **An issue form for a wrong verdict**, asking for the four things that make one reproducible. The
  README asked for them in prose already; a form is a mechanism.

### Fixed

- 🔴 **`README.ru.md` was two sections behind `README.md`** — the second-opinion architecture, and
  worse, the **prior-art table**. That is not a translation gap: a Russian reader was shown a tool
  with no precedent and no invitation to name one. Both sections are written, and a test now requires
  the two versions to credit the same outside projects. The negative control names `eyecite` and
  `citereview` by URL when the table is removed.
- 🔴 **The CI step checking that `doctor`'s status agrees with its exit code died on its own first
  run**, and the tool was fine. GitHub runs `bash -e`, so `cmd; rc=$?` aborts the step the instant
  cmd is non-zero — before the line that would have reported it. **A check that captures an exit
  code cannot fail informatively under `-e`; it can only vanish.** `cmd || rc=$?` is the form that
  works.
- `actions/checkout` and `actions/setup-python` were pinned three majors back, and the runner was
  already printing a deprecation notice — a version written down once and never asked about again.

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

[0.3.1]: https://github.com/igorsaevets/krokai-law/releases/tag/v0.3.1
[0.3.0]: https://github.com/igorsaevets/krokai-law/releases/tag/v0.3.0
[0.2.0]: https://github.com/igorsaevets/krokai-law/commit/8c6648c
[0.1.0]: https://github.com/igorsaevets/krokai-law/commit/002f6d1

0.1.0 and 0.2.0 link to commits, not to releases: they were real states of this repository
and they were never published, so a release tag for either would be a link to something that
does not exist. 0.3.0 is the first published version.
