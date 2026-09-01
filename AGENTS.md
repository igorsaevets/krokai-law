# AGENTS.md — how an AI assistant works with krokai

You are reading the working discipline for **krokai**, a citation safety harness for
AI-assisted legal work. One sentence explains the whole tool: **a grounded citation does not
prove the quotation is real.** Measured, in a real matter: a model fetched the correct page,
attached a correct and verifiable link — and invented the text of the rule. Every "did it check
its sources" audit graded that answer clean. Only comparing the words against the document on
disk catches it. That comparison is this package.

If you are *installing* the toolkit, stop here and follow [INSTALL-FOR-AI.md](INSTALL-FOR-AI.md)
— it is the install runbook, this file is the working discipline. In a client matter that ran
`krokai init`, the matter's own `CLAUDE.md`/`AGENTS.md` carries the day-to-day block; this file
is the longer form behind it, printed on demand by `krokai agents`.

## How to run it — the command depends on where you stand

- Installed with pip: `krokai <command>` from anywhere.
- From a clone, standing in the clone root: `python -m krokai <command>`.
- From anywhere else: `python "<clone-folder>/krokai" <command>` — that trailing `krokai` is
  the package directory *inside* the clone. This is the form the install runbook prescribes,
  because from a matter folder the `-m` form fails with `No module named krokai` and reads
  like a broken install.

For the live command list run `--help`; for what is installed and configured, `doctor`; for the
citation packs that ship, `packs`. Ask the tool, never a document — a number or a list restated
in prose rots silently, and this repository has measured exactly that failure enough times to
refuse to restate its own counts here.

## The commands that matter daily

```
quote "<the quotation>"    check ONE quotation, right now, against the corpus
check                      check everything you wrote, before anything is filed
bank add                   write a bank entry: the quotation is SLICED from the source
                           between your --from/--to anchors, never typed, and verified
                           BEFORE the write. Dry-run by default; --apply writes
bank dismiss "<fragment>"  tick one queue line WITHOUT banking it; --why is required
coverage <draft ...>       bank <-> draft: mines (draft cites a rule the bank marks
                           against us), unapplied entries, paraphrases (address cited
                           but the bank's verbatim quotation is not in the draft),
                           bank entries missing pieces
library --bank             corpus <-> bank inventory: what is downloaded and not
                           analysed, what is banked but has no file
close                      mechanical end-of-round checks
gate <file>                outbound check for secrets and personal identifiers,
                           BEFORE pasting anything into another AI
review "<question>"        build a review brief, run outside reviewers, audit their quotations
selftest                   behavioural checks; contacts nothing
```

## The discipline — each rule was paid for before it was written

**Never type a quotation into the bank - slice it.** A model PRODUCES text rather than copying
it; re-typing six banked quotations by eye lost two markers of six, measured. `krokai bank add`
takes the quotation's opening and closing words and writes the slice of the source between them:
the text is never in the arguments, so there is nowhere to mistype it. When it refuses - a
repeated end anchor, a slice that stops before its proviso - the refusal is the feature. Do not
paste the text in by hand to get past it; extend the anchors until the slice is honest.

**The check that these words are in the source is not the check that the drafter should be
citing them.** `check` catches fabrication and `quote` catches the wrong verbatim; neither can
see that the paragraph the argument rests on is the paragraph the bank marks hostile. Before
anything is filed, run `krokai coverage <the draft file>` - it names the mines (draft cites a
rule the bank marks against us), the bank entries for us that the draft never uses, the
addresses the draft cites without the verbatim wording the bank already has, and the bank
entries themselves that are missing an application boundary. The categories are not opinions;
each was paid for by a measured filing in the sister project.

**A script's verdict is evidence; your hand search is not.** The pipeline strips soft hyphens,
non-breaking spaces, line-wrap hyphenation and markdown before comparing — a hand `grep` sees
none of that and returns a confident false zero on text the checker matches. Report verdicts
with their method ("krokai quote said X", not "I searched and found nothing"). And a zero from
*any* search tool needs a second instrument before you believe it.

**`NOT_FOUND` is not `INVENTED`.** The documented causes of a false `NOT_FOUND` come first, in
the ladder the tool itself prints under that verdict (the assistant block carries the same
ladder, and a self-test counts both against the code); fabrication is the conclusion that
survives all of them, never the starting hypothesis. Corpus damage — a missing text layer, a scrape that dropped footnotes, a
running header welded mid-sentence by a page break — is repaired **in the corpus copy**
(re-extract, re-download), never by widening the checker's forgiveness: an excuse wide enough
to swallow a page header also swallows a real edit of the same shape.

**A byte-match does not prove the text is right — corruption needs a second signature.** The
checker proves your quotation matches the copy on *your* disk. If the copy itself is suspect —
an impossible date, a mangled name — a second, independent copy of the same document is the only
confirmation; an official body's own published copy can carry the typo, and matching it exactly
just reproduces the typo with confidence.

**When you hunt what the string test cannot see, do not filter to the flagged list.** The
classes a byte comparison structurally misses — a headnote quoted under the opinion's pincite, a
quotation that is verbatim yet does not support the proposition, right words under the wrong
citation in prose — live inside `VERIFIED`, the basket every filter hides first. `quote` prints
the neighbouring sentences for a verified quotation, precisely because a verified one is the one
nobody opens again; read them for anything load-bearing.

**Never read a scanned PDF with a language model.** It produces plausible text, the plausible
text becomes a quotation, and the quotation is then treated as the primary source. `sidecar`
lists the files with no text layer; OCR belongs to an OCR engine run by a person.

**Nothing leaves the matter unchecked.** `gate <file>` before pasting into any other AI or web
tool. It blocks credentials outright and personal identifiers unless overridden, reporting the
kind and the line, never the value.

**Name every NEW file and folder in Latin — `A-Za-z0-9._-` only.** No Cyrillic, no other
scripts, avoid spaces. Non-ASCII names break the tooling around a matter in quiet ways, each one
measured rather than imagined: console code pages mangle them, a hook reading stdin in a
single-byte codec dies on them **without raising anything**, shells quote them differently, and
a path one tool wrote another cannot open. Existing non-Latin names stay as they are — renaming
breaks every reference to them; the rule is for what you create from now on.

## Outside reviewers: krokai audits, ai-second-opinion orchestrates

Sending one question to several independent models is a different job with its own tool:
[ai-second-opinion](https://github.com/igorsaevets/ai-second-opinion). The two are deliberately
not merged. `krokai review` builds the brief (carrying the citation rules above) and dispatches
the round — through ai-second-opinion when it is installed, otherwise over its own built-in
transport for the command-line channels it finds on the machine, and if nothing is ready it
leaves you the brief to send by hand. Then it does the step an orchestration harness
structurally cannot do: it checks every quotation the reviewers send back against the corpus on
disk, worst first, and its exit code reflects those verdicts (`review --audit <folder>` runs
that audit alone).

Treat a reviewer's agreement with the brief as measuring the brief, not the source; a reviewer's
claim about material it was not given is void by construction; and a verdict about *your* corpus
("not one quotation found") indicts the corpus configuration before it indicts the reviewer.

## Editing this repository

Read `CONTRIBUTING.md` first. House rules that bite: numbers about the code are read back out of
documents by `selftest`, so do not write counts into prose; every rule in the code carries the
incident that produced it, so do not "simplify" one away without reading its comment; and the
self-test suite asserts the *absence* of three deliberately removed features — if a test fails
because you rebuilt something, the test is right.
