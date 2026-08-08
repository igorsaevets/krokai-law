# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- KROKAI-SELFTEST: DISCUSSES-PLACEHOLDERS - this log quotes the defects it records, and one
     of them is an unreplaced clone-URL placeholder. The self-test's placeholder check honours
     this declaration for a document that declares it, and refuses the declaration outright to
     README.md, README.ru.md, INSTALL.md and INSTALL-FOR-AI.md - the files a reader copies
     commands out of. Exempting a declared file is auditable; exempting a filename is the
     allowlist mistake that shipped a mangled LICENSE in a sibling project. -->

## [0.7.5] - 2026-08-07

**`pip install krokai` would have installed a tool that verifies nothing, and said nothing.**

Four call sites found this package's shipped data by walking one level up out of the package
directory - correct for a clone, where `krokai/` and `packs/` are siblings, and wrong the moment
pip is involved, because `site-packages/krokai/..` is `site-packages`:

| file | what it looked for | what it found once installed |
|---|---|---|
| `citations.py` | `<pkg>/../packs` | nothing. `available_packs()` returns `[]`, no error |
| `cli.py` | `<pkg>/../templates` | nothing |
| `install.py` | `<pkg>/../hooks` | nothing. `krokai install` refused to run |
| `consult.py` | `<pkg>/../channels.json` | nothing. `krokai review` raised SystemExit |

The first row is the dangerous one: no exception, no warning. The tool would have started, run,
printed a clean report, and checked zero citations.

None of it was visible from a checkout, which is the one layout where the bug cannot occur. The
suite passed 421/421 throughout.

- `krokai/_datadir.py` searches inside the package first, beside it second. Both layouts work, and
  the documented "copy the folder and run it" install is unchanged.
- Packaging is hatchling, not setuptools, because only `force-include` can map a directory that
  lives outside the package into the wheel. The repository layout does not move.
- `selftest.py` imported the hooks as a top-level `hooks` module, which needs the repo root on
  `sys.path`. Installed, it died at test 400 of 421.
- Three suites scan the source TREE. From `site-packages` they scanned pip's own vendored code and
  reported six LABELLED_SECRET findings in `pip/_internal/network/auth.py`. They now skip when this
  is not a checkout, and say so out loud - a test that quietly vanishes reads as one that passed.

Verified in both arms: installed wheel 397/397 with 24 hygiene tests skipped aloud, checkout
421/421 unchanged. 397 + 24 = 421.

CI gained an `installed` job that builds the wheel, installs it elsewhere and runs it from an
unrelated directory, plus `actionlint`.

First release on PyPI, published by Trusted Publishing. No API token exists in this repository.

## [0.7.4] — 2026-08-05

**Four findings from the round-21 review, adjudicated by execution. The worst one was caused by the
fix in 0.7.1.**

Three channels reviewed 0.7.0 independently — a fourth timed out — and converged on the same
places. Where they converged the claim was still re-derived here against the shipped code, and one
of their shared claims was already fixed and is recorded as refuted.

**A dated-edition marker bought an official stamp on any host.** The snapshot list holds path and
query fragments — `/annual/`, `/historical/`, `?date=` — and `classify_url` matched them as
substrings of the whole URL, ahead of every host test. So `https://evil.com/historical/report.xml`
classified as `snapshot`, whose label is **OFFICIAL BUT DATED**; `krokai fetch` downloaded it
without `--allow-unknown-source`, and `intake` wrote that phrase into the human-facing library
index. Measured: **5 of 5 hostile URLs** took the label. This is the second half of the substring
bug fixed in 0.4.0 — that round replaced the test on the `primary` branch and left the branches
either side of it, including the one that runs *first*, matching substrings. A pattern that names a
host now vouches for itself; one that names no host is a qualifier and applies only to a host
already vouched. All nine legitimate shapes still classify as before.

**A single line of scraped boilerplate deleted a whole statute from the corpus.** 0.7.1 moved the
placeholder test out of the length branch so a 900-character bot wall would be caught — correct —
and left tier 1 firing at *every* length. Measured: 9 920 characters of 8 U.S.C. 1255 plus one
footer reading `Please enable JavaScript to use this site` excluded the entire document, so every
correct quotation of it would return `NOT_FOUND`, which is this tool's accusation that the drafter
invented it. A scraped `.gov` page keeping a noscript footer is the ordinary case. A tier-1 string
now fires anywhere in a document small enough to *be* an error page, and above that size needs a
second, distinct tier-1 string. The whole existing suite passed throughout, because every control
in it was short.

**Sentences of 25 characters or fewer were invisible to the revision diff** — `Section 4 is
repealed.` is 22. An operative sentence is short *because* it is operative. The floor existed only
to drop fragments left by splitting on the stop inside `U.S.C.`, so a fragment is now identified by
what it is — no internal whitespace — rather than by being short.

**A relocated sentence was reported as no change at all.** Set comparison cannot see order, so
moving a conditioning sentence into another subsection gave `0 gone, 0 added, 100 % unchanged` — and
the bank check agreed, because the words really are still somewhere in the file. `revision_diff`
now also returns `moved`, and the report says what it means. The set comparison is kept: it is what
stops a chunk-boundary shift being reported as a deletion.

Also: `you do not have permission to view` is server language too, and sat in the gap between the
two placeholder tiers. The unwrap window went 3 → 5 — the class was real, every worked example
offered for it was a wrap no editor produces, and the cost was **measured** at 804 documents /
8.3 MB of ordinary prose: 1 finding at every width from 2 to 6, no new kinds. The width moved to
module level first, because the attempt to measure it through a local returned an identical 0 at
every width, which is what a disconnected knob looks like rather than what a safe change looks
like.

Self-test 401 → **421**. Refuted against the shipped tree: *"a long error page is indexed as law"*,
which all three channels reported and 0.7.1 had already fixed.

🔴 Not re-measured: the eCFR figures in 0.7.0's notes (57 gone / 64 new / 89.1 % unchanged) were
taken with the 25-character floor and no longer describe this code. eCFR's versioner API returned
503 on the retry, so they are marked stale rather than replaced with a guess.

## [0.7.3] — 2026-08-05

**The revision diff compared raw extractor output, so rendering was graded as a change in the law.**

Named independently by two review channels, which is the whole reason to ask more than one.
`read_any` output carries line wrapping, smart quotes, non-breaking spaces and unescaped entities,
and two extractions of the *same* provision differ in every one of them — so a re-download with no
legal change produced a wall of gone/added pairs, and the revision report, whose entire job is to be
believed, cried wolf.

This package already holds the doctrine: normalisation may change whitespace, hyphenation and
typography, and may never change letters, digits or word order. The revision detector was the one
place not applying it.

Measured after the fix: a rendering-only difference (line wraps, non-breaking spaces) is **0 gone,
0 added, 100 % unchanged**, while a real one-word edit — `shall prescribe` to `may prescribe` — is
still caught.

## [0.7.2] — 2026-08-05

**The review round on 0.7.1, and it found that the release's marquee feature defeated itself.**
Six findings, every one reproduced by execution before it was believed.

### 🔴🔴🔴 A quotation of superseded law came back `VERIFIED`

`intake` keeps both editions after a revision — deliberately, because a quotation taken from the
older one *was* a correct quotation of the law in force at the time. But both stayed in the sources
directory and **both were indexed**, so the superseded text answered as current law with a green
tick.

The module's own docstring asserted the opposite: *"a quotation taken from last year's edition will
not be found in this year's — which this tool reports as `NOT_FOUND`"*. Measured: it **is** found, in
the wrong edition, silently. **The revision machinery created the condition it exists to detect and
then suppressed its own alarm.** For a filing, "verified against a real file on disk" and "verified
against the text in force" had become indistinguishable.

Fixed with a verdict rather than by hiding the file: **`SUPERSEDED_EDITION`**, in `DANGEROUS`,
reachable only when the law register knows a newer edition of the same provision exists. It is
emphatically not an accusation of fabrication and its meaning says so — what is undecided is which
edition the filing should cite. `check()` applies it, not the report, because a check that runs
outside the path it protects is decorative: the hooks and the reviewer-answer audit call `check()`
directly and would otherwise have kept grading superseded law clean.

### 🔴🔴 The placeholder test could not fire above 200 characters

`looks_like_placeholder` documents tier 1 as firing "wherever they appear". The call site put it
inside the `< MIN_TEXT_LAYER` branch, so it could only ever fire in a file under 200 characters —
while a real bot wall is tens of kilobytes. The comment and the code contradicted each other and the
dangerous direction was the live one: a 900-character interstitial was indexed as primary law and
*"Checking your browser before accessing the site"* came back `VERIFIED`.

Found by a reviewer reading the **call site** rather than the function, which is exactly where the
two disagreed.

### 🔴🔴 `intake` believed a hand-written `.meta.json`

The three trust levels, the no-flag lookalike refusal and the "silence is not a pass" doctrine were
all front-door controls on a house with an open side door: `intake` walks a plain writable directory
and read `trust` straight out of the file beside the download. A paste-site URL with a hand-written
meta took an **OFFICIAL** row in the human-facing library index. The label is re-derived from the
recorded URL now, the worse of the two answers wins, and an entry with no URL can claim nothing.

### 🔴 An extraction failure was reported as a change in the law

A new edition that could not be read produced `revision_diff(old, "")`: every sentence "gone", 0 %
similar, a report announcing the provision had been deleted in its entirety, and every banked
quotation marked lost. Refused now, with the true diagnosis.

### 🔴 Every ellipsis quotation was a permanent false alarm

`_bank_impact` used a substring test, and a quotation containing an ellipsis can never be a
substring of anything — so on **every** revision, every banked quotation citing with an ellipsis was
reported as no longer appearing, under a red heading saying it would come back as the fabrication
signal. The better the bank, the louder the false alarm, in the one document whose entire job is to
be believed. Fragments are now matched in order, without overlap.

### 🔴 The one handler whose purpose is to record a death recorded it nowhere

`bank_queue`'s top-level exception handler called `log(None, …)`, which returns immediately and
persists nothing unless `--verbose` is passed — which the harness never does. It finds a config now,
and falls back to stderr.

Self-test 383 → **401**.

> Adjudication: of the reviewer's findings, these six were confirmed by execution and applied. Its
> canary answer was correct. Three further claims turned out to be my own probes testing the wrong
> level rather than product defects, and are recorded as such rather than "fixed".

## [0.7.1] — 2026-08-05

**A refusal must not depend on an optional dependency being installed.**

`fetch_url` imported the network library before classifying the host. On a machine without it —
which is every CI runner, and that is how this was found — asking to download from a typosquat
answered *"install requests"* instead of *"REFUSED: this host wears an official name it is not
entitled to"*. A safety decision that depends on whether an optional package happens to be present
is not a safety decision. Classify, refuse, and only then ask whether the download is possible at
all. Verified by simulating a bare runner: both refusals fire with no network library importable.

> **`v0.7.0` is withdrawn rather than moved.** The tag existed for a few minutes, CI on it was red,
> and no release object was ever created — so nothing was consumed from it. It could have been
> quietly re-pointed at the fix; it was not, for the same reason `v0.5.0` was withdrawn instead of
> re-tagged the week before. **A tag must never denote two different trees.** The cost is one
> version number, which is cheap; a tag that silently changed meaning is not.

## [0.7.0] — 2026-08-05 · withdrawn, superseded by 0.7.1

Two things happened this round and they belong in one release: the toolkit learned to fetch the law,
and the main guard turned out never to have worked.

> **This is also the 0.6.1 that was planned.** The fixes and the new command were measured in the
> same sitting and share the same fixtures; splitting them into two tags would have published a
> version nobody ran end to end. If you are on 0.6.0, the hook fix below is the reason to upgrade,
> not the new command.

### 🔴🔴🔴 `quote_guard` was dead for any payload containing a non-ASCII character

The hook that catches an unverified quotation as it is written returned **exit 0 and said nothing**
whenever the event carried a single non-ASCII byte. Measured one variable at a time, calling it the
way the harness does — a subprocess with JSON bytes on stdin:

| stdin | console code page | result |
|---|---|---|
| UTF-8 bytes (what the harness sends) | cp1251 | **exit 0, silent** |
| the same bytes, `PYTHONIOENCODING=utf-8` | — | exit 2, fires |
| ASCII path, ASCII matter, **curly quotes in the quotation** | cp1251 | **exit 0, silent** |

The trigger is not an exotic file path. It is `U+201C` — the character a model emits and every
scraped source contains. `sys.stdin` decoded UTF-8 in the console code page, which is a single-byte
codec: it never raises, the JSON still parses, and every non-ASCII character silently becomes
something else. The quotation extractor then found nothing.

`_bootstrap` had forced UTF-8 on **stderr and stdout** since the first day of the project, with a
docstring explaining why. It never touched stdin. That asymmetry is the lesson worth carrying:
**the visible half of a symmetric defect gets fixed on day one, and the invisible half survives
indefinitely.** Mojibake going out is something you see; mojibake coming in is something that does
nothing.

Fixed by reading `sys.stdin.buffer` and decoding explicitly. And because a silent hook and a healthy
one produced the same observation — nothing — `quote_guard` now **writes one log line per
invocation naming the decision it reached**, including the quiet ones.

The "already raised this" memo moved out of the machine's temp directory into the matter, gained a
file scope and a 12-hour expiry. It was keyed on the hash of the quotation alone, so raising
something while drafting matter A silenced it for ever in matter B — and it silently poisoned the
experiment that was measuring the hook, because the first arm recorded the hash and every later arm
read as dead.

### 🔴🔴 The tool's own output was being indexed as primary law

`krokai sidecar` writes an extracted text layer next to each PDF, *inside a sources directory*.
`Corpus` walks `.md`. Nothing in the sidecar declared what it was, so it was indexed as law — and
the warning header of the sidecar itself came back as a **CLEAN verdict**: "Page breaks, signatures
and exact layout exist only there" verified, citing the sidecar as its source.

The mechanism that prevents this already existed (`run.SENTINEL`, honoured by `Corpus(sentinel=…)`)
and had never been applied to the one generator that writes into the library. The cure was sitting
next to the disease. The stamp is in the **content**, never a rule about the name or extension —
a sister project measured that an extension rule would have thrown out two genuinely downloaded
decisions.

`bank_queue` built its corpus without the sentinel at all, so the hook and `krokai check` were
grading against two different libraries.

### 🔴🔴 A signature field became searchable law

The AcroForm reader added in 0.6.0 fixed a real defect — a filled USCIS form reading as blank — and
opened a new one, which is the shape worth remembering: **fixing a false negative by widening what
gets indexed widens it too far unless something says stop.**

Every govinfo PDF is digitally signed; a `/Sig` field's value is a **dictionary** holding the PKCS#7
certificate chain, and `str()` of it went into the corpus. Measured on a signed fixture: 4 267
characters of certificate, from which the phrase *"U.S. Government Printing Office, Washington"*
came back **VERIFIED as law**.

Two independent tests now: the field type, and a refusal to stringify anything that is not a scalar.
`Off` in a text field is still kept; an unticked checkbox is still dropped.

### 🔴 A 40-page scan read as a document with a text layer

`no_text_layer` compared the whole document against a 200-character floor, so per-page furniture
accumulated and **the longer the scan, the safer it looked**. A 40-page PDF holding 7.8 characters a
page passed as readable. There is now a per-page rate as well as a total, applied from three pages
up so that a genuine one-page proclamation is not condemned.

### 🔴 The soft hyphen

`U+00AD` renders as a hyphen only where a line breaks and as nothing elsewhere — so it is never part
of the text, and it silently defeats every comparison and every search. A correct quotation of a
soft-hyphenated provision came back `PUNCTUATION` instead of `VERIFIED`, and a plain search for the
word missed entirely in the sidecar. Order is the whole fix: the character and the line break have
to go together, or the whitespace collapse welds a space into the middle of a word.

Zero-width space, ZWNJ and ZWJ go the same way. `strip_invisibles()` is shared with the sidecar
writer, which needs the repair without the whitespace folding — a sidecar with no line structure is
one nobody can read.

### 🔴 A failed download could verify as law

0.6.0 stopped excluding short text sources, because a real 71-character savings clause was being
thrown out and a correct quotation of it came back `NOT_FOUND`. A reviewer named the other side of
that trade the same week: a scraped `404 Not Found` body is also short, and indexing it made a
phrase from the placeholder **verify**.

Both are true, so the answer is neither. **Length was only ever a proxy** for "the download failed",
and the thing itself is readable — a failed download says what it is. The test is on the content now,
in two tiers: strings only a server says fire anywhere; ordinary English like *access denied* fires
only when it is essentially the whole file. That second tier exists because this project's own
negative control caught the first draft firing on *"the applicant was denied access to the record
and now argues that access denied in these circumstances violates due process"* — and excluding that
file would drop a real provision and make a correct quotation of it read as invented.

### 🔴 Secrets: a credential wrapped at a space

The whole-text pass folded lines with no separator, which recovers a break **inside** a token and
loses one **at a space**. Take the standard HTTP authorisation header: put the scheme keyword at
the end of one line and the credential at the start of the next, fold with no separator, and the
space the pattern requires is gone - so the detector missed it and the gate printed `clean` over a
live credential. Both joins are tried now.

> The illustration above deliberately describes the shape instead of spelling it. Writing the
> literal string here made this project's own publish gate refuse the release - correctly, because
> that string IS the shape of a credential assignment. The rule this project already had for
> personal data - *an incident is written with the word, never with the value* - turns out to
> cover credentials too.

The reviewer who named the class offered four worked examples and **every one of them was wrong** —
`-----BEGIN RSA \nPRIVATE KEY-----` still matches, because `[A-Z ]{0,24}` absorbs `RSA` with no
space needed. Right finding, wrong proof, separated by running it.

The cost is stated rather than hidden: the empty join can fuse two unrelated lines into something
key-shaped, and a false positive in a class with **no override** is a dead end for the user. So a
folded-only finding says it was folded and names both lines.

### Added — `krokai fetch` and `krokai intake`

The toolkit can now put the law on your disk itself, which is what its own `NOT_FOUND` advice has
been telling people to do since 0.1.0.

🔴 **No language model may stand between the server and the file.** An assistant asked to fetch a
regulation reaches for a web-fetch tool — and those tools *convert the page and answer a prompt
against it using a small fast model*. What comes back is generated text about the page, not a copy
of it. Save that into the library and every quotation is checked against a paraphrase while the
report says `VERIFIED`. The permitted path is `requests` → bytes → disk, unchanged; extraction
happens later, from the file, by the same readers everything else uses. `model_in_path: false` is
recorded in the metadata rather than promised in a docstring, and a file that claims otherwise is
refused with no flag to override it.

* **Three trust levels, and silence is not one of them.** The lookalike test is a *detector*, not an
  allow-list. A sister project printed a green tick whenever its typosquat detector stayed quiet and
  wrote a paste-site URL into its law library under a "PRIMARY SOURCE" header. A host this tool knows
  nothing about is `unknown`, says so in the file it writes, and needs `--allow-unknown-source`. A
  lookalike is refused outright and **there is no flag for it**.
* The destination of a **redirect** is classified as well as the URL you typed.
* An **HTTP 200 is not a document**: a body that says 404, a bot wall or a loading stub is refused.
* Downloads land in `.krokai/inbox/`, which is not a sources directory and is not searched. Nothing
  becomes a primary source by arriving; a person accepts it with `intake`.
* `intake` **refuses to file a document whose citation it cannot resolve.** Putting a file in a law
  folder is what makes it law here, so guessing where it goes is issuing that status at random.

🔴 **A revision is an event, not an update.** When the same address comes back with different bytes
the old edition is kept, the difference is written down **counted in sentences** (a unified diff
reports a chunk-boundary shift as a deletion, and a tool for spotting deletions must not overstate
them), and **every quotation in the bank is re-checked against the new text**. Verified live against
eCFR's dated snapshots of 8 CFR 245: 2024 against 2026 is 89.1 % unchanged, 57 sentences gone,
64 new — and the systematic replacement of *alien* with *noncitizen* throughout, including the
heading of § 245.23. Every banked quotation of that part would have turned red overnight, correctly
quoted and unverifiable, with nothing to distinguish it from an invention.

### Fixed — smaller, each measured

* A row added to the library index landed **below** the table when the file ended in prose, and
  markdown stops rendering a table at the first non-row line. It is inserted inside the table now, or
  refused loudly if there is no table; the write is atomic.
* The register is written through `os.replace`. `open(path, "w")` truncates before anything is
  written, so an interruption left an empty file where the record of every download used to be.
* The sidecar freshness key includes the extractor version. It was `mtime` alone — and a downloaded
  statute never changes, so every improvement to `read_pdf` would have left every sidecar on disk
  exactly as wrong as before, with the suite green and the changelog claiming the fix.
* The omission marker `* * *` survives non-breaking spaces and a line wrap between the asterisks.
* A query string no longer destroys a downloaded file's extension — the extension is the key that
  selects the reader, so `title-8.xml?part=245` saved as `title-8.xml-part-245` meant tags were never
  stripped and `&#xA7;` never unescaped. Caught by this module's own end-to-end run, which started
  producing quotations made of markup.

Self-test 344 → **383**.

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
