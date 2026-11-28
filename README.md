# KrokAI Law — AI citation and quote checker for legal documents

[![selftest](https://github.com/igorsaevets/krokai-law/actions/workflows/selftest.yml/badge.svg)](https://github.com/igorsaevets/krokai-law/actions/workflows/selftest.yml)

**Check every quotation in your legal draft against the real source — before you file it.**

An AI assistant — ChatGPT, Claude, Gemini — drafts a USCIS petition, an RFE response or a brief in
minutes. Some of what it puts in quotation marks is not in the source (an AI "hallucination"): a
sentence the court never wrote, a regulation with its condition quietly dropped, the right words under
the wrong citation. **KrokAI Law** is a free, open-source command-line tool that compares every quoted
passage in your documents with the text of the law you downloaded, and tells you which quotations do
not match and how. It runs on your computer: the draft is not uploaded anywhere, and no AI model
decides the verdict.

*Русская версия: [README.ru.md](README.ru.md)*

| | |
|---|---|
| **The pain** | an invented or altered quotation looks exactly like a real one, and the person who signs pays for it |
| **The fix** | every quotation compared word for word with the statute, regulation, Policy Manual chapter or decision on your disk |
| **The result** | a list of what to fix, with the page each word stands on, before anything is filed |
| **The price** | free, MIT licence, no account, no API key |

---

## The problem: hallucinated quotations in legal filings

**Invented quotations look exactly like real ones.** A model was asked to open a federal regulation
and quote it. It opened the right page, attached a correct, working link — and invented the text of
the rule, word for word, in quotation marks. Every "did the AI check its sources?" audit graded that
answer clean, because those audits check that a page was *fetched*, not that the *words* are in it.

> **A citation with a working link does not prove the quotation is real.**
> Only comparing the words with the document does.

**Courts now deal with this every week.** A public database of court decisions about AI-hallucinated
filings counted **2,387** of them on 28 November 2026: 1,586 in the United States, 622 with false
quotations, 968 where the AI was used by a lawyer
([AI Hallucination Cases](https://www.damiencharlotin.com/hallucinations/)).

**The person who signs pays — in immigration too.** In June 2026 the Ninth Circuit fined two attorneys
in an immigration appeal $2,500 each and suspended them from practice before it for six months, for
briefs with "multiple nonexistent cases, misattributed quotations, and gross misrepresentations of
real cases" ([Lnu v. Blanche, No. 24-4790](https://cdn.ca9.uscourts.gov/datastore/opinions/2026/06/03/24-4790.pdf)).
In October 2026 the Board of Immigration Appeals suspended one of them from practice before the Board,
the Immigration Courts **and the Department of Homeland Security**, which USCIS is part of
([Matter of Sethi, 30 I&N Dec. 112 (BIA 2026)](https://www.justice.gov/eoir/media/1463921/dl)).

**"Is the case real?" is not enough.** The same order: a competent attorney "must do more than prompt
generative AI, check that the citations provided by the AI are real and the subject matter roughly on
point, and call it a day." One of the quotations it sanctioned was a real sentence — from a different
case. Paid research tools are not immune: a study of the AI research tools of LexisNexis and Thomson
Reuters found that they "each hallucinate between 17% and 33% of the time"
([Magesh et al.](https://arxiv.org/abs/2405.20362), *Journal of Empirical Legal Studies*, 2025).

**And it is not only the machine.** About half of the errors this tool was built to catch turned out to
be human. In one audit of already-published work: a decision quoted under the footnote of a different
decision; a clause dropped from the middle of a quotation; ten quotations marked "verified" that
stopped one comma before the words that limited them (`..., but do not include instances where...`). A tired person at eleven at night makes
these, and neither a spell-checker nor a re-read catches them.

## The solution: check every quotation against its source

1. **Keep the law you rely on in one folder.** Statutes, regulations, Policy Manual chapters,
   decisions — `krokai fetch` downloads them from the publisher byte for byte, with no AI model between
   the server and the file.
2. **Write as usual** — with ChatGPT, Claude, Gemini or any other assistant, or by hand.
3. **Run `krokai check`.** Every quotation in every draft gets a verdict: `verified`, `not found`,
   `truncated condition` (exact, but the source goes on with `unless…`), `operator` (`may` where the
   source says `must`), `found elsewhere` (the words are in another provision than the one you cite)
   and others — with the PDF page and the page the source prints. What you file is reported apart from
   notes and research.

Optional hooks run the check every time your assistant writes a quotation, not when someone remembers.

## Example: the quotation the Ninth Circuit sanctioned

The order quotes a sentence the brief attributed to *Kamalthas v. INS*, 251 F.3d 1279, 1284 (9th Cir.
2001) — "An adverse credibility determination is not necessarily a death knell to CAT protection." —
and finds: "This quotation does not appear in Kamalthas." With that opinion in the sources folder
(downloaded by `krokai fetch-precedent`), it takes one command (output shortened):

```text
$ krokai quote "An adverse credibility determination is not necessarily a death knell to CAT protection."
corpus: 2 files, 0.0 MB of text

NOT FOUND
  absent from the corpus, AND the cited source is one you have - so this is the shape a fabrication makes

🔴 NOT FOUND is not the same as INVENTED. Rule these out in order - only what
   survives all of them is a defect in the quotation:
     1. the source was never downloaded - ...
     ...
     6. the quotation was rewritten in OUR file - ...
```

A sentence the opinion really contains:

```text
$ krokai quote "the BIA has plainly overrelied on its prior adverse credibility finding against Kamalthas and failed to consider evidence of the relevant country conditions in the record"
corpus: 2 files, 0.0 MB of text

VERIFIED
  word for word in a file in your sources folder - which is not the same as 'in force today'
  found in: law\251.F3d.1279.99-71081.html
```

`krokai check` does the same for every quotation in every draft at once and writes `REPORT.md` (what
to fix, and what differs) and `READING-LIST.md` (each filed quotation beside its source passage).
The sanctioned sentence is itself real: *Shrestha v. Holder* (9th Cir. 2010) wrote it about Kamalthas,
and the court held that "It makes no difference that the quotation does in fact appear in another
case". If *Shrestha* is in your folder too, `check` finds the words there and names that file under
`Found in:`; it does not yet flag a court opinion cited by party names as the wrong address on its
own — read that line.

## Who it is for

- **People who write USCIS petitions** — EB-2 NIW, EB-1A, O-1, I-140, I-485 adjustment of status, RFE
  responses — on their own or in a small practice, with an AI assistant.
- **Immigration attorneys and paralegals** who sign what an assistant drafted. The built-in citation
  packs cover the INA, the CFR, the U.S. Code, the Federal Register, USCIS policy, the FAM and Board
  precedent.
- **Anyone filing legal text with quotations in it** — a tax pack ships too, and adding your own body
  of law is a JSON file, not a code change.

## How it differs from a citation checker

Most citation checkers answer "does this case exist?" A few commercial ones also compare a brief's
quotations with the cited case in their own databases (see
[what already exists](#things-that-already-exist-and-how-this-differs)). KrokAI Law:

- **checks the words**, not just the citation — and what comes right after them (`but`, `unless`,
  `except`), because a quotation that stops one clause early states a different rule;
- **checks the law a petition rests on** — regulations, the Policy Manual, AAO and BIA decisions, the
  FAM — in the exact copies you rely on, with the page each word stands on;
- **keeps your client's text on your computer**: the check runs locally, and an outbound gate stops
  credentials and personal identifiers before anything is sent to an outside AI;
- **is deterministic**: a verdict is a text comparison, never a model's opinion — the same draft gets
  the same answer;
- **is free and open source** (MIT), with no account and no API key.

## Start in a minute

```bash
pip install "krokai[all]"     # PDF, DOCX and web fetch included
cd /path/to/your/matter
krokai init .
krokai check
```

Or send your AI assistant this repository's link and say *"install this for me, including the
hooks"* — [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md) is written for the assistant. Every install method,
and how to update: [below](#install-in-about-a-minute).

## Questions people ask

### How do I check whether ChatGPT or Claude invented a quotation in my legal draft?

Put the sources the draft relies on in one folder — `krokai fetch` and `krokai fetch-precedent`
download them from the publisher — and run `krokai check`. A quotation whose words are in none of
your sources comes back `not found`; one that was changed or cut short is named by what happened to
it (`operator`, `truncated condition` and the others above). It works the same whoever wrote the
draft, a model or a person.

### Is there a free AI citation checker for legal documents?

This one: free and open source (MIT), no account, no API key, and it runs on your computer. It
checks the quoted words against the sources you keep. Whether a case exists and is still good law is
a citator's job (Westlaw's KeyCite, Lexis's Shepard's).

### Does it catch fake case citations?

Partly. `krokai fetch-precedent` keeps a downloaded decision only if the party, subject and court you
name appear in its text, so a case that does not exist cannot be fetched into your sources, and a
quotation attributed to it comes back `not found` — unless the words are real and come from another
decision you have (the [example above](#example-the-quotation-the-ninth-circuit-sanctioned) is that
case). It does not look a citation up in a case-law database.

### I write my EB-2 NIW or EB-1A petition with ChatGPT or Claude. What does this check?

Every quotation in the draft — of the USCIS Policy Manual, 8 C.F.R., the INA, AAO and BIA decisions —
against the copy of that source on your disk, with the page each word stands on. It does not judge
the petition's merits or whether the evidence meets the criteria.

### Does my draft leave my computer?

No. The check runs locally. Only the optional second-opinion commands (`krokai review`,
`krokai check --judge`) send text out, to the models you choose, and an outbound gate stops
credentials and personal identifiers first.

### How is it different from Westlaw Quick Check or BriefCatch RealityCheck?

Both are paid services that check a brief against their own databases: Westlaw compares case
quotations with Westlaw Edge, BriefCatch checks cited cases and federal statutes. KrokAI Law is free,
runs on your computer and checks the copies you keep — the Policy Manual, regulations and agency
decisions as well as court opinions. More in
[what already exists](#things-that-already-exist-and-how-this-differs).

---

## What it actually does

**1. Checks the words.** Every quoted passage in everything you wrote, against every source you have
downloaded. Not "is it roughly right" — is the string there.

**2. Checks the address.** Finding the words *somewhere* is not the same as finding them *where you
said*. If your document cites one provision and the sentence lives in another, you are told.

**3. Checks what comes next.** The most expensive defect in legal drafting is a quotation that is
exactly right and stops one clause too early. `krokai` reads what follows the quotation in the
source and flags it when the next words are `but`, `unless`, `except`, `provided that`.

**4. Keeps the sources — and fetches them.** A quote bank of everything you have personally opened
and confirmed, and an index of your downloaded law. Because "I could not find it" is only meaningful
if you know whether you ever downloaded it.

`krokai fetch <url>` brings the text down itself, and the one rule it enforces is the reason it
exists: **no language model stands between the server and the file.** Ask an assistant to "fetch this
regulation" and it reaches for a web tool that converts the page and answers a prompt against it
using a small fast model — so what lands on your disk is generated text *about* the page. Check your
quotations against that and the report says `VERIFIED` while the comparison is against a paraphrase.
`krokai` writes the bytes the server sent, unchanged, and reads them later with the same code it
reads everything else with.

Downloads wait in an inbox that is not searched. A host wearing an official name it is not entitled
to is refused outright; a host the tool knows nothing about says so and needs a flag, because a
detector staying quiet is not a recommendation.

**5. Notices when the law changes under you.** Fetch the same provision again and if the bytes differ
`krokai` keeps both editions, writes down what changed, and **re-checks every quotation in your bank
against the new text**. Measured on 8 CFR 245 between its 2024 and 2026 editions: 89 % unchanged, 57
sentences gone — and *alien* replaced by *noncitizen* throughout. Every quotation of that part taken
from the older edition would have started coming back "not found in your sources", which is exactly
what a fabricated quotation looks like.

**6. Asks other models, and distrusts them too.** One model can be confidently, fluently wrong.
`krokai review` sends the same question to several — using the AI subscriptions you already pay
for, no API key needed — and then runs **their** quotations through the same checker as your own.
That last step is the point: a reviewer's answer is input, not evidence.

**7. Stops your client's data leaving.** Before anything is sent anywhere, an outbound gate scans it
for credentials and personal identifiers, reports the kind and the line number, and **never prints
the value**. Secrets have no override.

The gate **refuses to send; it does not silently rewrite your document.** That distinction is
deliberate — a substitution that quietly eats a word damages the thing it was protecting and files
the damage under "working as intended" — and it means the tool tells you what to fix rather than
fixing it behind you.

What it looks for is deliberately partial rather than total: the house number goes and the street
and city stay, because a reviewer who cannot tell which city your client lives in will answer a
more general question than the one you asked. **Surnames are the one part you configure yourself**,
in `surnames` in `casefile.json`: no pattern can tell a surname from a given name, and one that
guesses will cut the wrong word in a document full of judges' and agencies' names. Leave it empty
and the gate says so out loud — it will not report `clean` about a check it never ran.

**8. Makes it automatic.** Optional hooks fire when your AI writes a quotation into a document —
not when you remember to check. This is the part that matters most, and the reason is below.

**9. Checks the argument against the decisions you have already made.** The words in your
quotations can be right, the addresses can be right, and the draft can still rest on a rule the
bank has flagged as *against us* — the classic case, measured verbatim in the sister project:
8 CFR 214.2(f)(8)(i) was in the bank as §Π-13 (against us), and the same filing cited it as
its own affirmative support. `krokai coverage <the draft file>` runs the four checks a string
comparison cannot: **mines** (draft cites a rule the bank marks against us), **unapplied**
(bank has an entry for us the draft never uses), **paraphrase only** (address is cited but the
bank's verbatim quotation is not in the draft — a summary is not a quotation, and an
adjudicator following the pincite finds words that do not match the source), and **entries
missing pieces** (an entry with no application boundary will be cited wider than it permits).
Companion: `krokai library --bank` cross-references the corpus with the bank — files
downloaded and never analysed on one side, bank entries whose source is missing on the other.

**10. Hands you the download command for every missing source.** Naming a `NOT_FOUND` is half
of the answer; the other half is *how to fetch that specific source*, and an assistant that
has to hunt for the URL either invents one or gives up. `krokai library --suggest-fetches`
prints a ready-to-run `krokai fetch <URL>` for every banked entry whose source is not on disk
— for citation kinds whose publisher has a stable request-level URL (U.S. Code, Federal
Register, Public Law, eCFR API). For the ones that are behind an anti-bot layer (USCIS Policy
Manual, policy memoranda) it prints the browser-only fallback rather than inventing a URL.
`krokai quote` prints the same command under the `NOT_FOUND` ladder when the citation next to
the quotation names a supported publisher. `SITE-ACCESS.md` in the matter root records which
publishers this environment can reach, updated the first time a fetch fails.

**11. Builds the legal appendix from the bank, with fresh verification.** The one section
of a filing that lists the rules the argument rests on. Traditionally hand-compiled — which
means it is hand-compiled from the bank the drafter *remembers*, not the bank the corpus can
still verify. `krokai appendix` re-runs `check` on every banked entry at build time, groups
what verifies under CFR / U.S. Code / INA / Public Law / Federal Register / Policy Manual,
and lists everything that did not verify in a loud `EXCLUDED` section that names the fresh
verdict. Silent exclusion is how a dropped proviso reaches a filing — this section refuses
to be silent. Measured on 8 CFR 245 between two editions: 32 sentences gone; every affected
banked quotation would have come back `NOT_FOUND`. The appendix built yesterday would not
notice; this one does, because there is no cache.

**12. Proves the precedent you downloaded is the one you asked for.** An assistant asked to
save the `Matter of Smith` decision saved a different Smith with a different disposition —
same reporter volume, wrong file. The URL, the anchor text and the file name all read fine;
only reading the extracted text catches it. `krokai fetch-precedent <URL> --party X
--subject Y --court Z` downloads the decision AND requires the party, subject and court to
appear in the first 200 KB of extracted text before the file is kept. Any missing token means
the download is deleted from the inbox immediately. No `--force` — the wrong-file failure
has no benign shape.

---

## Why a second opinion, and why it is not a separate download

A single model can produce a fluent, well-sourced, confident answer that is wrong — and you cannot
tell from the answer. Several models fail differently, so their **disagreement** is the signal. That
is the whole reason to ask more than one.

But asking several models is only half of it. Measured on the system this came from:

- one channel produced a quotation, both neighbouring sentences, and a tag claiming it had opened
  the page — and had invented all three;
- two channels returned the **same** pincite with two **different** "verbatim" texts. One was
  quoting the decision; the other was quoting a later decision's paraphrase of it. Filed under the
  first pincite, that is another authority's words under this authority's address;
- five channels agreed with each other, and every one of them had returned the asker's own mistake,
  because a fragment of the expected answer was sitting inside the question.

So the reviewers' answers go through the same checker your own drafts do. **This is the step an
orchestration tool structurally cannot perform** — it has your question and their answers, but not
your corpus.

If you already run a dedicated multi-model tool, `krokai` hands it the same gated brief and
audits everything it brings back. If you do not, the built-in channels run on the subscriptions you
already have. Either way the command works, because a feature that requires installing a second,
differently-named program is a feature most people will never actually have.

---

## The finding that shaped the whole design

An instruction file said, in bold: *check every quotation as it is entered.* It was followed
diligently — and then, in three consecutive working sessions, **the checker ran zero times**, while
those same sessions produced new quotations.

The pattern explains it. Everything worked while the task itself was about checking. The moment the
task became strategy, all of it went quiet.

> **Rules fire by topic, not by rule.**

An instruction is text competing for attention with the job in front of you. When the job *is* the
rule, the rule wins. When the job is something else, it loses — and nobody notices, because a rule
that did not fire leaves no trace.

Measured cost: **16 turns produced quotations of law and banked none.** The worst single turn
produced 65 quotations and banked none of them. Later checking of those 108 quotations found 21 that
were in no source on disk at all.

A hook is executed by the harness, not by the assistant. Topic cannot influence it. That is the
entire argument for the hooks, and it is why this is a tool and not a checklist.

The same measurement has a second half: even when a quotation **is** banked, somebody has to copy
it — and a model produces text rather than copying it. Re-typing six banked quotations by eye
lost two markers of six in the source project. So the bank is written by a gatekeeper,
`krokai bank add`: you give the opening words and the closing words, and the tool slices the text
between them out of the source file — the quotation is never in the arguments, so there is
nowhere to mistype it. The slice is verified *before* the write (one that stops a clause short of
`except as provided…` is refused, with the dropped continuation on screen), the address is checked
against the file, the *what this does NOT prove* boundary is mandatory, and a successful write
ticks the matching queue line itself. Dry-run by default; `--apply` writes.

---

## Install in about a minute

```bash
pip install krokai            # or: pip install "krokai[all]" for PDF + DOCX + web fetch
cd /path/to/your/matter
krokai init .
krokai check
```

**No programming needed, no account, no API key, nothing leaves your machine.** Five install
methods, including plain file copy for a locked-down work laptop: [INSTALL.md](INSTALL.md).

**Or hand it to your AI.** Send it the repository link and say *"install this for me, including the
hooks"* — [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md) is written for the assistant rather than for you,
and it verifies its own work at the end.

### Updating an existing install

One subcommand. From the matter folder or anywhere your `krokai` command works:

```bash
python -m krokai upgrade         # or:  python /path/to/krokai-law/krokai upgrade
```

It detects whether this copy lives under `site-packages` (uses pip), in a git clone (uses git),
or in a copied folder (prints how to re-copy), runs the right tool, refreshes the hooks in the
current matter, and prints what changed. `--dry-run` reports the detected layout and the exact
command it would run without touching anything.

**Or hand it to your AI.** Send it the repository link and say *"update this for me"* — the
same [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md#updating-an-existing-install) file has an "Updating"
section written for the assistant.

---

## What you get back

```
verdict                A filed B guides C research
truncated condition          2       0       0
operator                     1       0       1
found elsewhere              1       0       0
not found                    0       1       4
verified                    38      12      61
```

Your own writing is separated by what it costs to be wrong. A loose quotation in a research note is
not the same problem as one in a document that leaves the building, and mixing them corrupts the
number in both directions.

Each finding names the file, the quotation, the source it was found in, and **what specifically
differs** — not "there is a discrepancy" but `not`, or ``the source also has `*` ``, or *the source
continues: "…, but do not include instances where…"*.

**The page, two ways.** A match in a PDF names the page of the file and the page the source prints:
`PDF page 4 of 12, printed page 299` - the number the page shows on a line of its own, accepted only
when the file's numbered pages agree on one sequence (a page that shows none is counted only between
two that do). A Federal Register or Statutes at Large text from GPO is paged by its own page markers
(`printed pages 41300-41301`, `110 STAT. 3009-546`). Where the source proves nothing - no numbers,
two sequences, a page outside the numbered ones - the line says `printed page unknown` and why. It
is the page the file prints: a reprint of the reporter prints the reporter's page, a slip opinion
its own, so compare a pincite with it only when the file is the reporter's print.

**The zone of a decision.** In an I&N Dec. decision `quote` and `check` also name the part the words
stand in: `zone: the opinion`; `zone: the headnote only, not the opinion` - the summary EOIR adds above
the opinion when it publishes the decision (its Policy Manual, Part III, ch. 1.4: «Headnotes are
added»), so a pincite should rest on the opinion's own words; or `zone: a separate opinion only -
«DISSENTING OPINION: …»`, which also makes the quotation `WRONG_SPEAKER`. The parts are read from the
lines the decision prints between them - the first counsel, charge or panel line under the caption, a
dissent's heading - and a decision that prints none is `zone unknown` and why. A file is read as a
decision only by its own head; court opinions are not zoned.

Beside `REPORT.md`, every `check` writes `READING-LIST.md`: each quotation of the filed documents with
the sentence that uses it and the passage of the source around it, flagged ones first. Whether a
verbatim quotation actually *supports* its sentence is a question of reading, so the clean ones carry
no "passed" label - only the plain facts that put a quotation early (a limiter next to the words -
in a list, only in the list's opening words, the quoted item and what follows the last item, never in
a neighbouring item - words left out, no citation beside it).

**Optional: a model reads them first (`check --judge <channel>`).** Off unless you ask for it on the
command line. With an HTTP channel from `channels.json` that has its key and `model` set, `check`
sends one request per draft place of each clean filed quotation - the draft sentence (and the
sentence before it when the quotation stands alone), the quotation, the citation beside it and the
source passage shown in the list; no file name, nothing else of the draft - and puts the quotations
the model doubts (overstated, a condition left out, an exception that covers the sentence's own
facts) first in part 2 of `READING-LIST.md`. That order is all it changes: no verdict, no
`REPORT.md` line, no exit code, and the model's label or reason is never written beside a
quotation, because a label beside a row is advice that people follow. Every request goes through
`gate` with the matter's `surnames` first; a request the gate stops is not sent. A missing key, an
unset model or a failing model leaves the list in its plain order. The console prints what was
sent, what was held, the cost and the time.

### The verdicts, in plain words

| | |
|---|---|
| **verified** | the words are, exactly, in a file **in your sources folder** — read the warning under this table |
| **truncated condition** | 🔴 exact — and the source goes on with the clause that limits it |
| **truncated opening** | 🔴 exact — but a negation stands in front of it that you cut off |
| **operator** | 🔴 a word like *not*, *unless*, *only*, *may*, *shall* differs |
| **found elsewhere** | 🔴 the words exist, but not in the provision you cited |
| **spliced** | 🔴 your ellipsis joins two documents into one sentence |
| **ellipsis hides** | the fragments are all there; what the `…` removed narrows the rule |
| **altered** | the beginning is in the source, the whole is not — the tail changed |
| **partial** | half of it is there — read it |
| **not found** | absent: either not downloaded, or not real |
| **wrong speaker** | verbatim — but the source is quoting a *commenter*, not stating the rule |
| **punctuation** | same words and order, punctuation drifted |
| **typesetting** | your quotation is fine; the copy on disk is damaged |
| **scattered** | every sentence is real; they are not next to each other in the source |
| **assembled** | ellipsis quotation, all fragments in order, nothing material hidden |

> 🔴 **What `verified` does not mean.** It means the words are in a file you put in your sources
> folder. It does not mean the rule is in force, that the file is the current edition, that the
> download completed, or that the site you took it from was the real one. A repealed regulation
> verifies perfectly. So does last year's annual edition, and so does a chapter that lost two of its
> six bullet points on the way to your disk.
>
> This is the tool's own headline defect pointed at itself, and it is not a guess: four independent
> outside reviewers were asked, separately, what this design could not see about itself, and all
> four answered with this — the corpus is a set of downloads whose provenance is **asserted and
> never proven**. Nothing here checks a signature, a publication date, or a chain of custody.
> `krokai library` tells you what you have and when you fetched it. Deciding that it is still the
> law is a lawyer's job, and this tool does not do it.

---

## Things that already exist, and how this differs

Most of these were found by the outside reviewers of this design rather than by its author, which is
the honest way to report prior art; the two quotation checkers at the end were added on 28 November
2026. Feature descriptions are from each project's own page; none was tested here.

| | what it does | how this differs |
|---|---|---|
| [eyecite](https://github.com/freelawproject/eyecite) (open source) | *"Find legal citations in any block of text"* | extraction, not verification. Excellent at the step before this one |
| [citereview](https://github.com/kirinccchang/citereview) (open source) | validates citations against CourtListener, Cornell LII, GovInfo | checks the citation **exists**; this checks the **words** against a copy on your disk |
| Clearbrief, ProofBrief, briefcheckr (commercial) | citation checking inside Word, backed by commercial databases | Word-integrated and database-backed; this is a local corpus you control, offline, with no per-seat licence |
| Tracelaw (commercial) | runs several frontier models and cross-validates the findings | the closest to the second-opinion half — but the cross-validation is between models, not against primary text you hold |
| [Westlaw Quick Check Quotation Analysis](https://legal.thomsonreuters.com/en/c/quick-check-quotation-analysis) (commercial) | *"shows differences such as missing, added, or changed language between case quotes in your uploaded document, and the cited case language on Westlaw Edge"* | case law in the vendor's database, on an uploaded document; this checks statutes, regulations, agency guidance and decisions on your own disk, and uploads nothing |
| [BriefCatch RealityCheck](https://www.briefcatch.com/realitycheck) (commercial) | *"verifies cited cases and federal statutes"* and flags *"Quotations that do not match the source text"* | a paid service that checks against the vendor's sources; this compares with the copies you hold, on your own computer |

None of them was found to do the combination: **byte-for-byte checking against a corpus on your own
disk, plus multi-model second opinions whose quotations are then run through that same check.** Three
independent searches reported no confirmation of one. That is a statement about three searches, not
proof that none exists — if you know of one, please open an issue, because using it would be less
work than maintaining this.

---

## What it does not do, said plainly

- **It does not know whether a rule is still in force.** It compares against the copy on your disk.
  A repealed regulation verifies perfectly.
- **It cannot catch the right words under a pincite to the wrong page of the right document.** A
  published checklist once quoted a decision's editorial headnote while citing the page of the
  opinion, where the sentence reads differently by one word that mattered. Both sentences are
  genuinely in the PDF. This tool says *verified* about that, and always will.
- **It is not a lawyer and gives no advice.** It answers one question: are these words in that
  document.
- **A flag can mean the tool is wrong.** Your downloaded copy of a source may itself be incomplete —
  measured: a scraped agency chapter held four of its six bullet points, so a *correct* quotation of
  the missing text came back flagged. Before you "fix" a document because of a flag, open the live
  page. The order to rule things out is printed with every miss.
- **It does not yet reliably tie a court opinion cited by party names to its file.** A quotation that
  exists in a different opinion on your disk is graded as found, and only the `Found in:` line shows
  which opinion it was found in — the *Shrestha* case in the example above.

---

## Also in the box

- **A guard against sending client data to an AI.** 10 detectors for credentials with no override,
  12 for personal identifiers with one. It reports the kind and the line number and **never the
  value** — printing the match to prove the check works would leak it into the transcript, which is
  the same mistake one step earlier.
- **Prompt language that stops a model refusing legal work** — and the measurement showing the
  refusal was about framing, not subject matter. Same six questions, refused as *strategy*, answered
  in full as *source verification*. [FEATURES.md](FEATURES.md#prompts)
- **The one line that measurably stops fabricated quotations:** *a fabricated quotation is worse
  than a refusal.* With it, one model answered "I do not recall the exact wording" three times out
  of three and named that line as its reason.
- **PDF text sidecars,** because your search tool does not read PDFs and never told you. In one
  library that was 67 files — 35 % of it — invisible to every search, so every "I looked and found
  nothing" about them had been a false negative.
- **A regression harness** that mutates quotations the checker already blessed — inserting a `not`,
  cutting before a proviso, welding two sources — and counts how many it still calls clean. Holes
  found for free instead of in a filing.

---

## Reference

Full function-by-function reference, with the incident behind each one:
**[FEATURES.md](FEATURES.md)**

If the reader is your AI assistant, the working discipline written for it is
**[AGENTS.md](AGENTS.md)** — the same text `krokai agents` prints from any install, clone or pip.

---

## Found a bug? Want a feature? Want to work together?

| what | where |
|---|---|
| something is broken, or a verdict is wrong | [open an issue](../../issues) — include the quotation, the source text, the verdict you got and the one you expected |
| an idea, a question, a body of law you want a pack for | [discussions](../../discussions) |
| a security problem | [private advisory](../../security/advisories/new) — **not** a public issue |
| collaboration, consulting, or just to talk | [LinkedIn](https://www.linkedin.com/in/igorsaevets/) · [Facebook](https://facebook.com/igorsaevets) · [GitHub](https://github.com/igorsaevets) |

**There is deliberately no contact email.** The address on this repository's commits is GitHub's
no-reply relay: it attributes commits correctly and has **no mail exchanger at all**, so mail sent to
it is discarded without a bounce. A reporting channel that silently swallows a bug report is worse
than an absent one. Use the links above.

Maintained by **Igor Saevets** ([@igorsaevets](https://github.com/igorsaevets)), Los Angeles.

Licence: MIT. Nothing here contacts a vendor, and no test needs a key.
