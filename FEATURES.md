# Every feature, and the mistake that paid for it

This file is the complete function-by-function reference. It is organised around a rule the project
it grew from applies to itself:

> **A rule whose reason has been lost gets simplified back out six months later by someone who
> cannot see what it was for.**

So nothing below is described only by what it does. Each entry says **why it exists**, and where a
number appears it was measured on real documents, not estimated. Where something is unknown or
unverified it says so.

**Contents**

[The core claim](#the-core-claim) ·
[normalize](#normalize) · [extract](#extract) · [readers](#readers) · [corpus](#corpus) ·
[verify](#verify) · [address](#address) · [citation packs](#citation-packs) ·
[bank and queue](#bank-and-queue) · [library](#library) · [sidecar](#sidecar) ·
[redact](#redact) · [prompts](#prompts) · [mutations](#mutations) ·
[config](#config) · [run and report](#run-and-report) · [hooks](#hooks) · [install](#install) ·
[selftest](#selftest) ·
[The incident log](#the-incident-log) · [What is deliberately not covered](#what-is-deliberately-not-covered)

---

## The core claim

A model was asked to open a federal regulation and quote it. It fetched the correct page, attached
a correct link to the correct URL, and invented the text of the rule. Occurrences of the invented
sentence in the live regulation: **zero**. Not one fragment — the three distinctive phrases in it
returned 0, 0 and 0, and 0 again in the neighbouring title that might have contained them.

Every "did the AI check its sources" audit called that answer **1/1 grounded, clean**, because such
audits check delivery of a page and not the presence of words.

Two reviewers had predicted exactly this mode before it happened — *"URL attachment confirms context
delivery; it does not guarantee quote verbatim fidelity"* — and one asked for precisely this
program: *"a postprocessor that independently opens primary sources and compares quoted spans byte
for byte."*

Everything here follows from that.

---

## normalize

`lawverbatim/normalize.py` — the single text normaliser. **There is exactly one.**

### Why one

In the source project the normaliser was retyped three times in a single day — once in a probe
script, once in a hook, once in an end-of-round checker — and **each copy forgot a different
transform**. Three false alarms in one session, on quotations that were perfectly correct.

A false alarm in a verification tool is not cosmetic. It is the failure mode that kills the tool: a
check that cries wolf is ignored within a week, and then it catches nothing.

### The contract

May change **whitespace, hyphenation, typography**. May never change **letters, digits, word
order**. Everything it forgives is a rendering difference; everything it refuses to forgive is a
difference in the text.

### `normalise()`

| transform | the incident |
|---|---|
| collapse all whitespace | `"on March\n9, 2020"` made a true quotation return zero hits and nearly inverted a conclusion |
| heal a hyphen **at a line end only** | raw Federal Register text carries `on-\nline`, not `on-line`; a verification script produced a false NOT FOUND on a correct quotation |
| fold smart quotes, dashes, non-breaking spaces | a model re-types `"` as `"`; the words are perfect and a byte comparison fails |
| strip `[[Page NNNNN]]` | printers' page markers sit **inside** a sentence in GPO text |

🔴 **The hyphen anchor is the whole point.** The naive version was a blanket `replace("- ", "-")`
and it silently corrupted the corpus: real English contains `pre- and post-production` — hyphen,
space, same line — which the blanket rule welded into `pre-and post-production`. Four independent
reviewers flagged it; checking the actual corpus proved them right. Anchoring to `\n` fixes the
first case and cannot touch the second.

### `strip_markdown()`

Removes formatting applied *inside* a quotation (`**bold**`, backticks, link syntax), provenance
tags, and quotation-mark wrappers.

- **Provenance tags.** A review brief requires channels to tag each claim `[OPENED]` / `[SNIPPET]` /
  `[MEMORY]`. Those land inside the quoted span. The first run flagged four verbatim regulatory
  passages as ALTERED for this reason alone.
- **`[sic]` and `[so in original]` are both stripped.** This lets a project use the Bluebook form
  *inside* the quotation marks for filings and a bracketed note *outside* them for internal files —
  two conventions, neither of which breaks verification.
- 🔴 **Asymmetric wrappers too.** A span cut out of a longer sentence keeps only its closing
  guillemet, and that one character was enough to report good quotations as ALTERED across a whole
  first run.

### `strip_scrape_artifacts()`

Removes a web scraper's leavings from a **corpus** file before indexing it.

🔴 **Why it is separate from `strip_markdown`, and why the asymmetry was a real bug.**
`strip_markdown` runs on the *quotation*. For a long time the corpus went through `normalise` alone,
which does not touch link syntax. Agency policy manuals obtained by scraping carry
`[link](https://…)` and `[\[14\]](https://…#footnote-14)` **mid-sentence**, and such manuals footnote
nearly every proposition — so a genuinely verbatim multi-sentence quotation *could not match*.

It surfaced the right way round: the tool flagged two entries that had just been banked from an
opened source. The flags were real; the cause was the corpus.

🔴 **Why not simply reuse `strip_markdown` here:** it also strips `*`, and CFR and Federal Register
texts use `* * *` as the omitted-text marker. Deleting those would silently weld unrelated
provisions together — a corpus corruption far worse than the false alarm being fixed.

🔴 **Two scrape vintages, two different strings.** One writes `[\[14\]](https://…#footnote-14)`, a
later one `[**[14]**](#footnote-14)`. Matching only the first left the second in place — which turned
a corrected quotation into a *worse* verdict after a real fix. And the anchor text itself contains
`]` in both, so a `[^\]]` character class can never match it; a bounded non-greedy `.` is required.
Measured: the class form left the marker untouched and the fix looked like it had done nothing.

### `alnum()` · `dehyph()` · `latin_share()` · `is_mostly_cyrillic()` · `ellipsis_parts()`

- **`alnum`** — letters and digits only. Used for exactly one purpose: separating *"the words are
  right, the punctuation drifted"* from *"the words are wrong"*. It never promotes anything to
  verified. 🔴 Stated limitation: it cannot distinguish `no table` from `not able`.
- **`dehyph`** — heals justification hyphens, applied to **both sides** and never stored. It also
  heals hyphen-plus-space, which `normalise` deliberately does not: in prose `pre- and
  post-production` must survive, but in text extracted from a **PDF** the space after a
  justification hyphen is the extractor's artefact. Measured on a published reporter that renders
  `pre- sented`, where a byte-correct quotation came back NOT FOUND. Safe because both sides get the
  same treatment.
- **`latin_share`** — 🔴 the obvious implementation shipped and was wrong. The first version required
  40 **consecutive** latin letters, which never occurs in English because words are separated by
  spaces. The check silently returned "0 quotations" on a file full of them.
- **`ellipsis_parts(minlen)`** — 🔴 `minlen` is a parameter, not a constant, for a measured reason. A
  fixed floor of 25 **silently discarded** shorter fragments, and the surviving fragments were then
  checked "in order" *across* the discarded one — so a middle fragment could be absent from the
  source entirely while the quotation still read clean.

---

## extract

`lawverbatim/extract.py` — pulling quoted spans out of your own document. The half nobody expects to be
hard.

### `blocks()` — a block is a **paragraph**, not a line

Markdown wraps a quotation across lines, and a line-based extractor sees the wreckage:

```
> "Family ties to the United States
> and the closeness of the underlying relationships" · "Length of lawful residence...
```

Line two on its own looks exactly like a mangled quotation. The first run reported four of these as
ALTERED. Every one was verbatim correct in the source.

**Table rows stay separate.** Joining them would let a quotation match across two cells, inventing
the opposite error.

### `_split_blockquote()` — one line is often not one quotation

Three shapes measured on real files:

```
«A» · «B»                              two quotations joined by our own bullet
"text." Matter of Blas, 15 I&N Dec.    a quotation followed by its citation
> «text» — and our own gloss            a quotation plus commentary
```

Treating the whole line as one quotation makes all three fail against a real source, and **that
failure is indistinguishable from fabrication**.

### Callout suppression

🔴 Found on the very first real run of this toolkit: its own quote-bank template puts house rules
inside a `>` block for emphasis, and the whole block was extracted as a quotation of law and reported
NOT FOUND — *a false alarm manufactured by the tool's own template.*

A blockquote containing a markdown **heading** is a callout, not a quotation. The test is
deliberately narrow: `## ` essentially never appears inside quoted statutory text, whereas numbered
lists inside quoted statutes appear constantly — so a heading is the signal and a numbered list is
**not**. Quoted spans *inside* the callout are still extracted.

### `citation_window()` — two rings, and the difference matters

- **near (±140 characters, and not inside the span)** is the quotation's **address**.
- **far (±400)** is used only to classify a *miss*.

🔴 A reference *inside* the quoted text is part of the quoted text — it is what the source cites, not
where the source lives. Measured: `"...limits stated in 8 C.F.R. § 214.2(f)(6)"` inside a quotation
from an agency newsletter bound that quotation to part 214, and the resulting mismatch was an
accusation against an innocent document.

---

## readers

`lawverbatim/readers.py` — getting text out of a file without silently losing part of it.

### `read_pdf()` — two engines, and keep the one that did not break words

Two defects, and the second hid behind the first.

1. **A dead extraction.** Easy to detect: near-zero characters.
2. 🔴 **A complete but word-broken extraction** — `resu lt`, `unauthor ized`, `per iod`. This passes
   a "did we get text" gate and gets **cached**. Cross-engine count over a real 66-PDF corpus:
   **four files where the first engine reports MORE alphabetic tokens than the second**, i.e. it
   split words. The worst was a controlling court of appeals opinion at **3 295 tokens against
   2 179 — 51 % inflation** — and that case was one of three the whole argument rested on.

Why it matters beyond tidiness: a verbatim quotation crossing such a break degrades to a
punctuation-level verdict rather than a loud miss. But a degraded verdict is exactly what invites
*"must be an extraction artefact"* — **and that phrase is a conclusion, not an explanation.** It is
the bin where real errors hide.

**The test:** fewer alphabetic tokens over the same pages means fewer split words, so the engine
reporting fewer tokens is the better reading.

🔴 **A near-empty result is never cached.** An earlier version wrote the empty result and keyed the
cache on `(path, size, mtime)`, so installing the second engine tomorrow changed nothing — the
poisoned entry would be served until the *file* changed, which for a downloaded statute is never.

### `read_docx()` — body **plus** a raw-XML pass

The popular one-liner drops **tables silently** — measured at **−10 % of the text** on a real set of
case files — and also headers, footers, footnotes and unaccepted revisions. Those are precisely
where a citation likes to sit: a footnote *is* the pincite.

### `read_any()` — entity unescaping is not cosmetic

🔴 Official XML stores the section sign as `&#xA7;`. Without unescaping, `§ 103.2` in the corpus
becomes `S 103.2` while the quotation still says `§ 103.2`, and a provably correct quotation cannot
be found. That single defect depressed a whole verification run's numbers and inflated its
"extraction artefact" bin.

### `no_text_layer()`

🔴 Reported to the human and **never** solved by asking a language model to read the scan. Not
squeamishness: a model transcribing an image produces plausible text, the plausible text becomes a
quotation, and the quotation is then treated as the primary source. The failure is silent and it
contaminates the one artefact the system exists to keep clean.

🔴 **A stub is more dangerous than a missing file.** A 1.8 KB placeholder where a 60 KB chapter
should be still *looks* downloaded: the index counts the topic as covered, and every quotation from
it fails in a way that blames the quotation.

---

## corpus

`lawverbatim/corpus.py` — every primary source you have, indexed for exact search.

### 🔴🔴 The one rule that makes the tool mean anything

**The corpus contains primary sources and nothing else.** Break it and the tool keeps running, keeps
printing numbers, and the numbers become flattery — a quotation copied from your own memo verifies
against your own memo, and a mistake made once **validates itself forever**.

Measured twice, in opposite directions:

- One analytical file had been filed inside a statutes directory. Quotations copied out of it
  verified against it. The score read **87.2 %** where the honest figure was **75.6 %**.
- Nobody had checked the other side. The tool's **own archived report** had been filed into the
  drafts directory, so it was re-verifying its own output: **1 443 of 1 606 misses came from that one
  file.**

So files are screened **per file, not per directory**, and every exclusion is printed. A wrongly
excluded statute must be visible immediately, not discovered three rounds later.

🔴 **A name pattern cannot keep up with names.** Tier D was first detected by filename; one hour
later the tool's own report went back into tier C because it had been archived under a title the
pattern did not know. The generator now **stamps** what it writes and the walker reads the stamp.

### Three parallel indexes

`joined` (exact) · `ajoined` (alphanumeric only) · `hjoined` (hyphens healed). One string per index
with a `\x00` separator, ownership recovered by bisecting the offset table. `\x00` is not
alphanumeric and appears in no real document, so **a match can never straddle two files** — which
would invent a sentence that exists in neither.

### `all_in_order()` — three defects in the obvious version

1. 🔴 **One document, not "the corpus".** Searching each fragment across the whole corpus and calling
   it a match welds two unrelated authorities into a sentence that exists in neither.
2. 🔴 **The first occurrence is the wrong occurrence.** `str.find` returns the earliest hit anywhere,
   and one provision is quoted in several preambles, so the earliest hits of different fragments
   legitimately land in different files. **Measured cost: 26 false accusations against 4 real ones.**
3. 🔴 **Non-overlapping.** Advancing the cursor by one character let fragment N+1 start *inside*
   fragment N and still count as after it. Measured impact at the time: **zero cases** — which is
   exactly why it had to be fixed then rather than after it mattered.

### `window()`

🔴 Both ends clamped to the file. An earlier version clamped only the low end, so a window near the
end of a document ran past the separator and quoted the *next* document as though it belonged to
this one. Confirmed by execution, not by reading.

---

## verify

`lawverbatim/verify.py` + `lawverbatim/verdicts.py` — one quotation in, one of fifteen verdicts out.

### Why fifteen and not two

Because the interesting failures are not "the quotation is missing". They are the ones where **the
strings match and the meaning does not** — and a two-valued checker answers those with a cheerful
green.

Three verdicts exist solely because a pass/fail tool said VERIFIED about a defect heading for a
filing:

- **`TRUNCATED_CONDITION`** — exact substring, and the source *continues* with the clause that limits
  it. **10 of 592 already-verified quotations**, one in a document about to be filed:
  ours `...inadvertence, oversight, or neglect on the part of the DSO` /
  source `..., but do not include instances where a pattern of repeated violations...`
  A substring test cannot express *completeness*, so completeness got its own test.
- **`ELLIPSIS_HIDES`** — all fragments present, in order, in one document, and the **elided span**
  narrows the rule: ours `the statutory exemptions created by Congress ... continue to exist` /
  source `...created by Congress FOR CERTAIN [named] APPLICANTS FOR ADJUSTMENT OF STATUS continue to
  exist`.
- **`FOUND_ELSEWHERE`** — the words are in the corpus, verbatim, but not in the document whose
  address stands beside them.

### The decision tree

An exact match is tested first and then **immediately interrogated for completeness**, because "it
is an exact substring" is the answer that hides the two most expensive defects. Then the near-miss
classifiers, cheapest first.

🔴 **Order within the near-miss classifiers is deliberate.** The hyphen test runs *before* the
punctuation test. Folding hyphens is a strict subset of what the alphanumeric index forgives, so a
hyphen-only difference matches both — and if the looser test runs first it wins, and the user is told
*"punctuation drifted"* (your problem) instead of *"the source is line-broken"* (the corpus's
problem). Same evidence, opposite instruction. Narrower diagnosis first. Caught by this toolkit's own
self-test.

### `word_diff()` — 🔴🔴 the 85 % threshold was killed by arithmetic

A percentage cannot see negation. A 50-word quotation yields 45 overlapping 6-word shingles;
inserting **one** word breaks at most 6 of them, so 39/45 = **86.6 %**, which clears an 85 %
threshold. That is how `shall` → `shall not` was filed under *"typesetting artefact"*. All four
independent reviewers flagged the same threshold; the arithmetic settled it.

**Shingles now only locate. Classification is word-level.**

🔴 **The head/tail hole.** An earlier version kept only differences *between* the first and last
anchor, to ignore the source window's overhang — which also hid every change in the quotation's own
**tail**, the single most valuable diagnosis the tool produces. All four reviewers stated the bug too
broadly ("blind to changes at the start"); **running the test showed the start is caught and only the
tail is invisible.** Nobody separated those two cases by reasoning about it.

🔴 **A changed token carrying a digit is never typography** — a date, a threshold, a paragraph
number. `for the 2021-22 academic year` had been scored a minor difference.

🔴 **A two-word entry in a single-token list is dead code that reads like a safety net.** `"shall
not"` sat in the operator set, which compares one token at a time, so it could never match anything.
`shall` and `not` each fire on their own, and that is what actually protects the sentence.

### `truncated_condition()` — two signals, both required

The quotation must **not** end at a sentence boundary, **and** what follows must open with a limiter.
Either alone cries wolf. Checked at **every** occurrence, because the same sentence lives in several
preambles and the first hit is not necessarily the copy that was quoted.

### `leading_cut()` — two calibrations, both measured

🔴 Accepting *any* operator, including `and` and `or`, produced **254 hits** — noise, not findings.
Only a **negation** reverses what follows it. And it must be **near**: six tokens, not fourteen, or a
`not` at the head of a long clause claims a span it does not govern.

### `wrong_speaker()`

A rulemaking preamble quotes objections it then rejects; a decision recites the losing party's
argument. Quoting those as the authority's holding is common. **Advisory, not blocking** — quoting a
commenter *and saying so* is legitimate, and a blocking verdict there would be a false alarm.

### `ALTERED` upgraded to `OPERATOR`

🔴 **An improvement over the original.** The original returned ALTERED and stopped. ALTERED is true
but nearly useless — *"something after the halfway mark differs"*. If the thing that differs is `not`,
the reader needs to be told **that**. The word-level comparison now runs at the anchor and upgrades
the verdict. Caught by the self-test: an inserted negation was being reported as ALTERED.

### `SCATTERED` is not clean

🔴 A slip in the first draft of `verdicts.py`, caught by an invariant the self-test asserts: every
verdict must be in **exactly one** of the dangerous/clean lists. `SCATTERED` was in both. Every
sentence being verbatim while they are not adjacent in the source is a **defect**: it presents as one
continuous passage something the authority never wrote as one.

---

## address

`lawverbatim/address.py` — *"found in the corpus"* is not the claim *"found where you said"*.

Measured: a quotation of a signature statute was compared against a completely unrelated regulation
and flagged for a changed operative word. The quotation was perfect; the file holding the real
provision sat on the same disk.

### Four outcomes, and "could not tell" is one of them

`MATCHED` · `MISMATCH` · `NO_NEARBY_CITATION` · `ADDRESS_NOT_IN_CORPUS`

The last two exist so that *"I could not check"* never quietly renders as *"it checked out"*. For a
document that gets filed, `NO_NEARBY_CITATION` means **do not award a green** — not because something
is wrong, but because nothing can be verified about an address that was never written down.

### Deliberately lazy matching

A policy manual chapter reprinting a regulation contains that regulation's number, so it passes as an
acceptable home — same words, same agency. What gets caught is the provable case: a file in which the
cited provision is **not mentioned at all**. An accusation is made only where it can be demonstrated.

### Anchor-miss repair, and its floor

If the global search landed in file X while the cited address points at file Y, the text is re-tested
inside Y. If it is there, the verdict is repaired with an explicit note that the previous one was an
anchor miss.

🔴 **Gated at 60 characters**, contributed by one reviewer: a short stock phrase can occur by
coincidence inside the file at the cited address, and without the floor the repair would bless a
coincidence.

🔴 **The first build of this layer accused the innocent** — it bound quotations to citations within
±400 characters and to citations *inside* the quotation itself. It was recalibrated and the whole run
repeated **before** the numbers were shown to anyone, because a report where a third of the
accusations are false teaches the reader to skim.

---

## citation packs

`lawverbatim/citations.py` + `packs/*.json` — how the toolkit recognises the address of a rule.

Three ship: **`us-federal`** (CFR, U.S. Code, Federal Register, federal courts, public laws),
**`us-immigration`** (INA, USCIS Policy Manual, FAM, I&N Dec., *Matter of*, numbered policy memos,
legacy HQ memoranda), **`us-tax`** (IRC, Treasury regulations, revenue rulings and procedures,
notices, Tax Court, private letter rulings).

`us-tax` ships as a second worked example so that *"packs are pluggable"* is a demonstrated claim and
not a promise.

### The alias table

🔴 Two citation systems name the same provision — an act section number and a code section number.
Without the mapping they are simply different addresses, and a correct pincite reads as a mismatch.
In the original project **exactly one reviewer of four** supplied that table; nobody else noticed it
was missing.

Where the section numbers are identical and only the title differs (`I.R.C. § 162` = `26 U.S.C.
§ 162`), a pack omits the map and the captured value passes through.

### File matching is declarative

Per-kind probes: flattened-filename tokens, body regexes with minimum counts, and a **negative
guard**.

🔴 The negative guard exists because of a specific near-miss: in an agency manual, *volume 7 part A
chapter 8* and *volume 7 part B chapter 8* are different chapters that share a number, and one of
them was the entire argument. If the file's own header names a part and it is not yours, the file is
rejected before any other test. Three independent reviewers named this on the same day.

Filenames are compared **flattened** (lowercase, `-`, `_` and spaces removed) because real downloads
are named `8CFR-part-214-ecfr-2026-07-29.xml`, `8cfr_214.xml` and `8 CFR 214.xml` interchangeably,
and a naming convention is not a fact about the law.

### `is_primary()`

Splits a miss into *"the source must be on this disk"* and *"this was never going to be on this
disk"*. Measured on a real corpus: of **1 606** misses, **625** were tool output, **479** legal,
**502** evidentiary. One number, three meanings — and filing all three under one heading is how a
real fabrication hides in a pile of shrugs.

### One deliberate curiosity

`us-tax` recognises private letter rulings **on purpose**, and labels them
`(NOT precedent - IRC 6110(k)(3))`. Seeing one in a draft is the point.

---

## bank and queue

`lawverbatim/bank.py` — two files that do opposite jobs.

**The bank is a decision.** *This quotation matters, here is its address, here is where the source
sits on disk, here is how to re-check it in a minute, and here is what it does NOT prove.* A person
writes it. Nothing writes to it automatically, ever.

**The queue is a list of undone work.** A hook writes it after every turn.

### 🔴 Why they are not one file

Automatic entry would turn the bank into a dump. Measured: **a single turn produced 65 legal
quotations**. Writing all of them in would bury the four that mattered under sixty-one that did not,
and an unreadable bank is an unopened bank. The queue poses the question; the bank stores the answer.

### 🔴 The mandatory field

**"What this does NOT prove"** is required. Paid for twice: a decision was quoted in a filed
checklist under the footnote number of a *different* decision, with the limiting clause removed —
and the case itself had come out **against** a party in the client's position. Every character of the
quotation was correct.

### 🔴 The "against us" section

A bank holding only the convenient quotations is a way of learning the inconvenient ones from the
adjudicator instead of from yourself.

### `in_bank()` — normalised on **both** sides

🔴 A blockquote captured together with its guillemets normalises to straight quotes, the bank has
none, and the substring stops matching — so a quotation banked yesterday raises an alarm today. That
exact false positive fired on the first run of the guard hook, and it is the one that teaches people
to ignore the guard.

### `append_queue()` — everything fresh, including clean verdicts

*"Found verbatim"* is not *"appropriate"*. The "what this does not prove" analysis exists only in a
bank entry, and that is what catches an excised condition.

🔴 **A per-turn cap is stated out loud.** Silent truncation reads as *"everything is covered"*.

### 🔴 The template contains no long English prose in quotation marks

Because the bank is itself checked, and prose in quotes would be extracted as a quotation of law and
reported NOT FOUND — a false alarm manufactured by the tool's own template. Measured on the first
real run.

---

## library

`lawverbatim/library.py` — download it once, index it, check the index before the internet.

**The rule:** downloaded a source? Save it — to the library folder **and** as a line in the index.

Before this rule existed, sources were fetched into a temp folder and abandoned; two rounds later the
same statute was fetched again and the wording someone had already reconciled was gone. Worse: a
quotation whose source was never saved comes back NOT FOUND, and **NOT FOUND is indistinguishable
from *invented*** unless you know the library has a hole. Measured: **2 of 8 bank entries flagged
NOT FOUND were missing downloads, not bad quotations.**

### `prove()` — 🔴 both the party and the subject

Measured: a search for a case by surname returned **a different case with the same surname** —
different docket, different year, unpublished, on an unrelated area of law. The name matched and the
court matched. Nothing else did.

### `orphans()` — both directions

An unindexed file gets downloaded again. An indexed file that no longer exists makes the index a
promise the library cannot keep — **and a promise nothing re-checks is exactly how a stale library
survives.**

### `RECIPES`

Retrieval routes established by measurement, not by reading documentation, because the obvious method
fails for most of them — and often fails as a **200 with an empty body** rather than an error.
Includes the note that a rule's **preamble** must be read before building an argument on its text:
the regulation does not show you which softening the agency already considered and rejected.
Measured — a provision read as a narrow prohibition had a preamble recording, verbatim, the rejected
objection asking for exactly the exemption the argument depended on.

### 🔴🔴 The copy you have may be silently incomplete

Measured: a scraped copy of one agency chapter carried **four of six** bullet points in a list. Not a
truncated line — the last two simply were not there. A quotation of the missing text came back
flagged, **and the quotation was right**.

**A flag can mean the corpus is wrong.** Before "fixing" a document because of a flag, open the live
page.

---

## sidecar

`lawverbatim/sidecar.py` — making your own search stop lying to you.

A phrase known to be the title of an agency memorandum:

```
· extracted from the PDF text layer by a PDF library  -> FOUND
· searched for with ripgrep across the folder         -> found ONLY in .md, never in the PDF
```

In the corpus where this was measured: **67 files, 35 % of the law library, invisible to search.**

That is worse than an inconvenience, because of a rule every careful research process has: *a zero
result is an assertion, not a fact.* For every provision living only inside a PDF, "I searched and
found nothing" had been a **false negative all along**, and nothing in the process could have noticed.

**It does not fix the checker** — that reads PDFs directly and always did. Sidecars are for grep, for
your editor, and for the AI reading your folder, all of which are blind to a PDF and none of which
say so.

**A neighbour file, not a replacement.** The PDF stays the primary source; the sidecar declares itself
derived in its own header so it can never be quoted *instead of* the original.

---

## redact

`lawverbatim/redact.py` — the outbound gate.

The moment you paste a case file into a chat window it has been published: the vendor has it, the
transcript is written to disk and replayed into later context, and it can be retrieved from that
archive months later by anything that can read it. So the gate runs **before** the first call.

### Two classes, one override

**Secrets have no override** — there is no legitimate reason to send an API key to a reviewer, and a
gate with a bypass for its most serious class has no serious class. **10 detectors.**

**Personal data has one** (`--allow-pii`), because a lawyer sometimes genuinely must send a client's
date of birth to a reviewing model, and pretending otherwise teaches people to work around the tool.
**11 detectors.**

### 🔴 The value is never printed

Kind and line number only. Printing the match to prove the gate works would leak it into the very
transcript the gate protects — the same mistake, one step earlier.

### 🔴 Redaction is substitution, never truncation

Measured, expensively: a "mask" that kept the first 60 characters of a 48-character key kept the
**whole key**. Truncation cannot mask anything shorter than the cut.

### 🔴 A false positive outranks a miss

Measured: the date-of-birth pattern accepted *any* character after the label, so the sentence *"blocks
a labelled date of birth unless you pass --allow-pii"* tripped the gate — **on the documentation of
the gate**. A user who sees that learns to pass the override by reflex, and the override disables the
entire class. Every pattern therefore requires a **value that actually looks like the thing**.

That sentence is now a permanent **negative control** in the self-test, alongside six others.

### 🔴 The trailing `\b` trap — found four separate times

`passport no\.\b` can never match. Between the final `.` and the following space both characters are
non-word, so there is no word boundary. **The abbreviated forms — the ones that appear in real
documents — were undetectable in every one of the four instances.**

### 🔴 A header puts its delimiter before the label

`Authorization: Bearer <token>` — the `bearer` shape once sat in the labelled-assignment branch,
which requires the delimiter *after* the label. **The one shape it was added for was the one shape it
could never match.** It has its own pattern now.

### 🔴 Selective, not maximal

Cut what identifies; keep what lets a reviewer check a fact. A reviewer cannot confirm *"this
neighbourhood is inside the city limits"* against `[ADDRESS]`, and that kind of check is the reason
to send the document out at all. The line: **a unit number turns a street address into a person; the
street itself is geography.** So the apartment number is cut and the street is not.

### 🔴 Scrub at the logging choke point, not the output file

Measured: a diagnostics file was scrubbed correctly while an exception whose *message* carried a key
printed it in full to the console — and the console is the same archived, replayed surface.

### `self_test()`

Probes are **derived from the tables**, so a newly added pattern fails until it is given one.
Coverage had been lopsided in exactly the wrong direction: the class with a human override had six
tests and the class with no override had one.

---

## prompts

`lawverbatim/prompts.py` — what to put in a prompt so an outside model does useful legal work.

### Problem 1: the refusal is a **framing** result

An identical set of six research questions, sent twice. Framed as *filing strategy*, one channel
refused on policy — and 🔴 **the refusal still ended with the required completion marker**, so it
passed every mechanical check the harness had and looked like a finished review. Reframed as
*verification of published sources* with a research system prompt, the **same six questions** came
back answered in full, with citations.

This is not a trick and not a jailbreak. It is an accurate description of what you actually want: you
are not asking the model to be your lawyer, you are asking it whether a published government document
says what you think it says. Say that, and the objection evaporates because it was never the right
objection.

`RESEARCH_SYSTEM` is that framing, ready to use.

### Problem 2: the fabricated quotation, which looks like success

🔴 The mechanism, stated by one of the models when asked directly:

> *"the model by default produces text, not a quotation, and it does not itself know which of the two
> it has produced"*

And independently by another: *"a hallucination formatted as a quotation. It will silently reconstruct
the text rather than warn you."*

**The copyright theory was tested and disproved in the strong form.** Five channels; none reported any
such restriction, and for US government works the legal premise fails anyway — 17 U.S.C. § 105:
*"Copyright protection under this title is not available for any work of the United States
Government."* (The narrow exception at § 105(b)–(c) covers civilian faculty of the service academies
and touches neither the CFR nor decisions.) The real cause is the sentence above, and it is **worse**
than a policy, because a policy could be switched off.

🟢 **The measured cure is one line: a fabricated quotation is worse than a refusal.** With it, a
channel that would previously have produced a fluent reconstruction wrote *"I DO NOT RECALL THE EXACT
WORDING"* **three times out of three**, and named that line as its reason. Another reported: *"Rule 5
overrides the model's instruction to always be helpful."*

Give a model a vocabulary for uncertainty and it uses it. Without one, its only way to say *"I am not
sure"* is to sound sure.

### `QUOTE_RULES` — the seven requirements

1. **Verbatim**, in the original language, with source and date. *Why it helps you and not only them:*
   a paraphrase costs minutes to check, a verbatim quotation costs seconds — and that difference
   decides whether it gets checked at all.
2. **A provenance tag on every statement** — `[OPENED]` / `[SNIPPET]` / `[MEMORY]`. Measured to work:
   channels write "my search found no confirmation" honestly *when the format gives them a way to*.
3. **The neighbouring sentences.** 🔴 Reported honestly as a convenience, **not** a barrier: measured,
   one channel invented the quotation, both neighbours, and the `[OPENED]` tag with it.
4. **The two-question rule** — *"has document X changed"* always paired with *"has the practice under
   X changed by some other instrument"*. Paid for: a manual unchanged in two years while the agency
   had suspended the entire programme by other means. Everyone checked the right document and got the
   wrong answer.
5. **A fabricated quotation is worse than a refusal.**
6. **Never claim non-existence from a failed search.**
7. **Name the weakest point in your own answer.** Cheap self-calibration; channels answer this more
   honestly than a direct question about confidence.

### `SNIPPET_WARNING` — what a search integration actually returns

🔴 Measured on a live channel: five "citations" totalling about **2 000 characters — roughly 400
each**. Snippets, not pages. On material that thin the model reconstructs. In that same call it
produced a document title that looked verbatim, carried a genuine government URL, and had the meaning
**inverted** — it said the document *"does not dispense with"* a process the document actually
*"permits applicants to dispense with"*.

The cure was measured too: forbidding a snippet from being presented as a quotation, after which the
same channel refused to quote and said why.

### `anchor_warnings()` — 🔴🔴 the most expensive brief-writing error, which does not look like one

A question was written as *"Does section X contain a 'simple statement' rule?"* — with a fragment of
the **expected answer inside the question**. **Five channels came back agreeing**, and the agreement
read as strong independent confirmation.

It was not. Every one had returned the asker's own mistake: the real provision reads *"**If no
negative factors are present**, the officer **may** provide a simple statement"*, and the condition
had been dropped in the question itself.

> **Convergence measures the brief, not the source.**

`anchor_warnings()` detects the shapes that cause it, and also flags a brief that lacks the
instruction *quote the entire section in full* — without which a channel only addresses the fragment
you handed it, which is the fragment that may already be wrong.

### `CANARY_NOTE`

🟡 Plant one deliberately false but plausible claim, and **write it down before you send it**. A
reviewer that "confirms" the canary has just priced all of its other confirmations. It is the only
way to measure a channel that reports no tool telemetry, where the answer is the sole evidence there
is. One per round — and recorded outside the brief, or you risk absorbing your own plant.

---

## mutations

`lawverbatim/mutations.py` — measuring how often the checker says *clean* about something that is not.

From a reviewing model, about the project this came from:

> *"right now you learn about your gaps from incidents in filings — the most expensive testing method
> that exists."*

Every defect class ever paid for becomes a **mutation** applied to quotations the checker already
calls clean. A mutant still called clean is a hole, found for free.

| mutation | the incident |
|---|---|
| `insert-operator` | `shall` → `shall not`, the 85 %-similarity hole |
| `drop-negation` | the same hole, other direction |
| `digit` | a date or threshold altered |
| `tail` | the last words rewritten — a model that fetched the right page |
| `cut-condition` | cut right before `, but ...` — 10 found among already-verified quotations |
| `synonym` | one word paraphrased — *"produces text, not a quotation"* |
| `splice` | two quotations welded with an ellipsis |
| `wrong-address` | right words, wrong citation |

🔴 **A mutation counts as caught only if the REASON is right.** `cut-condition` is credited only when
the verdict is the truncation verdict itself. Any other dangerous verdict there is an accident — the
right answer for the wrong reason, which will not survive the next refactor.

Reference figure from the source project: **243 mutants, 0 false-clean.**

---

## config

`lawverbatim/config.py` — `casefile.json`, the one file that makes the toolkit yours.

The system this was extracted from had absolute paths compiled into eleven scripts, including a
cloud-synced folder name and a person's user account. Fine for one matter, impossible for anyone
else — and also how a script quietly writes into someone's live folder.

**Discovery walks up** from the working directory, the way git finds `.git`, so a hook fired from a
subfolder finds the same configuration as a command run from the root. A hook that silently uses
different settings from the CLI is worse than no hook.

🔴 **Missing folders are reported loudly, never created silently.** A source folder that is not there
produces a corpus of zero files, and a corpus of zero files makes **every** quotation come back
NOT FOUND — which reads like catastrophe and is really a typo in a path.

---

## run and report

`lawverbatim/run.py` — the whole-matter pass.

**Tiers.** Your own writing is not one pile: what gets filed and what sits in a research note fail at
different costs. Tier **D** is this tool's own output and reviewers' answers — still checked, because
a reviewer's invented quotation is worth catching, but never mixed with tier A.

**Every command that can be wrong about the world prints what it looked at.** A checker whose output
is a single number teaches you to trust the number; one that says *"42 source files, 3 with no text
layer, 2 excluded as your own writing"* lets you notice that the folder you meant is not the folder it
read.

**Miss classification.** A `NOT_FOUND` is labelled *evidentiary* (no legal citation nearby — a
reference letter, a news article), *legal and the source is on disk* 🔴, or *legal but the authority is
not in the corpus* 🟡. The three need separate piles, or the big pile buries the dangerous one.

---

## hooks

`hooks/` — three of them, and the argument for their existence is in the README.

### `quote_guard.py` — PostToolUse on Edit/Write

Fires when a long quotation in the language of the law enters a document that gets filed and is not
in the quote bank.

**It does not block.** The file is already written, and blocking would be wrong anyway: a quotation
has to be written down before it can be checked. This is a correction loop.

**It does not run the checker.** Six or seven seconds on every edit is a tax on every edit, and most
edits have nothing to do with quotations. It reminds, and shows exactly what to check.

**It ignores research folders, scratch and archives.** A guard that fires on drafts becomes noise, and
noise is how a guard gets ignored — which is the same as not having one.

**It never repeats itself.** Measured overhead in the original: **75 ms** per edit.

🔴 Its message names **three** things to check, not one: is the phrase in the source; is the address
right; **was a condition cut off**.

🔴 It forces UTF-8 on stderr before anything else. Without it the message arrives as mojibake on
Windows — the warning is unreadable exactly where it matters. Caught on the first test run.

### `bank_queue.py` — Stop

After each answer, extracts quotations of law, drops those already banked, runs the rest through the
same checker, appends to the queue.

**Always exits 0.** A Stop hook returning 2 prevents the turn from ending and can loop.

**This is not automated monitoring.** It contacts nothing and watches no external state; it reads
output already on your disk.

🔴 It shares the "last answer" detection with the answer archiver deliberately — *after the last tool
call the assistant is no longer doing, it is writing*. Two copies of that logic would diverge within a
month.

### `session_anchor.py` — SessionStart

🔴 An audit of a live legal project found there was **no SessionStart hook at all**: nothing met the
assistant at the beginning of a session, so everything that had to happen "on entry" lived in an
instructions file — that is, it was *context*, not a *mechanism*.

🔴 **It emits facts, not orders.** *"The queue has 4 open items"* is a fact. *"You must clear the
queue"* is an instruction arriving from a file the user did not write in this session, and an
assistant properly wary of injected instructions is right to discount it. Facts do not trigger that
defence and are more useful anyway.

It also states **what it did not check**, because a status line reporting only good news is read as an
all-clear.

---

## install

`lawverbatim/install.py` — wiring the hooks into `settings.json` without destroying what is there.

"Add this block to your settings.json" is how people end up with a broken settings.json, and the
hooks are the part that makes everything else work without anybody remembering anything. **A toolkit
whose central mechanism requires a manual JSON edit will be installed with the mechanism missing.**

1. **Merge, never replace.** Other hooks in that file belong to the user and may be load-bearing — a
   secret scanner, an answer archiver. Clobbering them to install a citation checker would be an
   unusually poor trade.
2. **Idempotent.** Ours are recognised by marker, not by position, so running twice does not
   duplicate and `--uninstall` is exact.
3. **Back up first, print the diff, support `--dry-run`.** Editing another program's configuration is
   not a step to take silently.

🔴 **`settings.json` is read when a session starts.** A freshly installed hook does nothing in the
session that installed it. Measured the hard way; printed at the end of every run.

---

## selftest

`lawverbatim selftest` — **81 behavioural checks**, no network, no configuration, no credentials.

**It builds its own corpus.** A test that needs your files is a test nobody runs, and the interesting
assertions are about *specific text*.

🔴 **Expectations are derived, not copied.** Where a test asserts something about data that ships —
the packs, the detector tables — it computes the expectation rather than restating it. Measured
elsewhere: adding a fourth item to such a list turned four *correct* tests red because the tests had
the list hardcoded. A test that duplicates configuration is a second home for it.

**Four real defects in this toolkit were found by its own self-test before any release:** an inserted
negation reported as ALTERED rather than OPERATOR; a hyphenation problem reported as the drafter's
punctuation rather than the corpus's damage; a mutation sample that exercised one mutation out of
seven; and `SCATTERED` classified as both dangerous and clean.

**Two more were found by the first run against real sources:** the tool's own quote-bank template
being extracted as a quotation of law, and a bare *"punctuation differs"* that named no character.

---

## The incident log

Every measured failure referenced above, in one list, for the reader who wants the evidence rather
than the design.

| # | what happened | what it produced |
|---|---|---|
| 1 | A model fetched the right page, cited the right URL, invented the rule text. Live check: 0 occurrences, three distinctive phrases at 0/0/0 | the whole tool |
| 2 | An analytical file inside a statutes folder; quotations verified against themselves. 87.2 % where honest was 75.6 % | per-file corpus screening |
| 3 | The tool's own archived report inside the drafts folder: **1 443 of 1 606** misses from one file | tier D + a sentinel stamp |
| 4 | `shall` → `shall not` scored 86.6 % similarity and passed an 85 % threshold | word-level diff |
| 5 | **10 of 592** verified quotations stopped one clause before a limiter, one in a filed document | `TRUNCATED_CONDITION` |
| 6 | An ellipsis quotation hiding the words that narrowed the rule to a class the client was not in | `ELLIPSIS_HIDES` |
| 7 | Comparing first occurrences across the corpus: **26 false** splice accusations against 4 real | one-document, in-order test |
| 8 | A decision quoted under another decision's footnote number, with the limiting clause removed, from a case that came out the other way | the bank's mandatory field |
| 9 | A blanket hyphen rule corrupting `pre- and post-production` in the corpus | line-end anchoring |
| 10 | `pre- sented` in a court reporter → false NOT FOUND on a byte-correct quotation | `dehyph` on both sides |
| 11 | Scrape footnotes mid-sentence → verbatim manual quotations could not match | `strip_scrape_artifacts` |
| 12 | Two scrape vintages, two footnote strings; matching one made a real fix look like nothing | both patterns, bounded `.` |
| 13 | One PDF engine inflating a controlling opinion by **51 %** in split tokens | two engines, fewer-tokens wins |
| 14 | A scraped agency chapter holding **4 of 6** bullet points; the flagged quotation was right | "a flag can mean the corpus is wrong" |
| 15 | `&#xA7;` → `S` making `§ 103.2` unfindable | entity unescaping |
| 16 | grep blind to **67 PDFs, 35 %** of a law library | sidecars |
| 17 | **16 turns** with legal quotations and zero bank entries; worst turn 65 quotations | the hooks |
| 18 | The checker ran in one stretch of answers and **zero times** in the rounds either side | *rules fire by topic, not by rule* |
| 19 | **2 of 8** bank entries flagged NOT FOUND because the source was never downloaded | the library index |
| 20 | A same-surname decoy case accepted: right name, right court, wrong everything else | `prove()` |
| 21 | A DOB pattern firing on the sentence documenting it | value-shaped patterns + negative controls |
| 22 | A 60-character "mask" over a 48-character key | substitution, never truncation |
| 23 | A key printed in full by an exception message while the output file was clean | scrub at the choke point |
| 24 | `passport no\.\b` unmatchable — four separate instances | delete the trailing `\b` |
| 25 | A search returning **~400 characters per "page"**; a title reconstructed with the meaning inverted | snippet warning |
| 26 | A question containing a fragment of its expected answer; **five channels agreed** with the asker's own error | `anchor_warnings()` |
| 27 | A policy refusal that still emitted the completion marker and passed every mechanical check | research framing + reading the answer |
| 28 | A manual unchanged for two years while the programme was suspended by other means | the two-question rule |
| 29 | Right words, wrong pincite — headnote quoted, opinion cited | **not caught**; needs a reader |
| 30 | A verdict list where one verdict was both dangerous and clean | a self-test invariant |

---

## What is deliberately not covered

- **Whether a rule is still in force.** The checker compares against your disk. A repealed regulation
  verifies perfectly. Nothing here touches the network.
- **Whether a quotation is apt.** `VERIFIED` means the string is present, not that it supports the
  proposition it is cited for.
- **The right words under a pincite to the wrong page of the right document** (incident 29). A
  published checklist quoted a decision's editorial *headnote* while citing the page of the *opinion*,
  where the sentence differs by one word that mattered. Both sentences are genuinely in the PDF. **No
  string comparison can catch this, and this one never will.** It needs a reader — a person, or a
  model given the source window and asked two specific questions: *is the address right* and *was a
  condition excised*.
- **OCR.** Files without a text layer are listed for you to run through a real OCR engine. 🔴 Never a
  language model: it produces plausible text, plausible text becomes a quotation, and the quotation is
  then treated as the primary source.
- **Deciding what your matter needs.** The queue asks; you answer.
