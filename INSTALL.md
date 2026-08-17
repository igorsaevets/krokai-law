# Installing

Five ways, in order of how much you are allowed to install on the machine. **All five end up at the
same place**; none needs an account, an API key, or a network connection at run time.

Requirements: **Python 3.9 or newer.** That is the only hard one.

---

## 0. pip

```bash
pip install krokai                       # working tool, no optional readers
pip install "krokai[all]"                # + pypdf, pymupdf, mammoth, requests — recommended
cd /path/to/your/matter
krokai init .
krokai doctor        # ends with STATUS: READY
```

The `krokai` command lands on your PATH; the `python /path/…` forms below are for people who
cannot pip-install and are running from a folder they copied in place. `krokai --version` prints
the installed version; `pip show krokai` prints the folder pip put it in.

Behind the scenes: `krokai[all]` is the same list of libraries the "optional libraries" table
lower on this page enumerates — installing the extra adds each one and no more.

---

## 1. Let your AI do it

Give your assistant the link to this repository and say:

> Install this for me, including the hooks. Follow INSTALL-FOR-AI.md.

[INSTALL-FOR-AI.md](INSTALL-FOR-AI.md) is written for the assistant rather than for you. It tells it
what to check before touching your settings file, what it must **not** do — the two failure modes
that are silent and expensive — and what to verify before reporting success. It ends with a report
made of numbers from commands it actually ran, not from a claim that it worked.

## 2. Clone

```bash
git clone https://github.com/igorsaevets/krokai-law ~/tools/krokai
cd ~/tools/krokai
python -m krokai selftest        # expect N/N passed
```

Then, in your matter folder:

```bash
python ~/tools/krokai/krokai init .
```

🔴 **Two command forms exist and only one works everywhere.** `python -m krokai …` works while
your terminal is INSIDE the clone. `python ~/tools/krokai/krokai …` — the package folder itself —
works from anywhere, including your matter folder, which is where you will actually be standing.
This document uses the second form for every command run from a matter. (The first release's
documents used `-m` throughout, and the from-the-matter commands had never worked; found by
executing the instructions in an empty folder, which reading them had not.)

## 3. Download and unpack

No git? Download the ZIP from the repository page, unpack it anywhere, and use the same commands. The
package is pure Python and needs no build step.

## 4. Copy the folder

On a locked-down work laptop where you cannot install anything: copy the folder onto the machine and
run it in place.

```bash
python /wherever/you/put/krokai/krokai init .
python -m krokai check          # from the matter folder, with the toolkit on PYTHONPATH
```

or, without touching `PYTHONPATH`:

```bash
python /wherever/you/put/krokai/krokai check --dir .
```

This method is supported on purpose and tested. A tool a paralegal cannot install is a tool that
does not exist.

---

## Optional libraries — what each absence costs

None is required. Each missing one makes a whole file type read as **empty**, which is worse than an
error because an empty file produces confident `NOT_FOUND` verdicts.

```bash
pip install pypdf pymupdf mammoth
```

| library | without it |
|---|---|
| `pypdf` **or** `pymupdf` | at least one is needed or **every PDF is invisible** |
| both | 🔴 the cross-check that catches a word-splitting extraction cannot run. Measured on a real corpus: one engine reported **51 % more** alphabetic tokens than the other on a controlling opinion, because it split words apart — and that degrades a verbatim quotation into a flagged one for reasons that look like the quotation's fault |
| `mammoth` | `.docx` is read through the raw-XML pass only. Usable, but the popular alternative drops **tables silently** — measured at −10 % of the text — so the XML pass is the safety net, not the primary reader |

`python -m krokai doctor` prints exactly which are present and what each absence means.

---

## Setting up a matter

```bash
cd /path/to/your/matter
python ~/tools/krokai/krokai init .
```

Creates:

```
casefile.json          the only file you edit — every path lives here
law/                   PRIMARY SOURCES ONLY
law/INDEX.md           one line per download; checked before any web search
case/                  what gets filed
case/QUOTE-BANK.md     quotations you have personally opened and confirmed
guides/                checklists, templates
research/              notes, drafts, reviewers' answers
```

### 🔴 The one rule that makes the tool mean anything

**`law/` holds primary sources and nothing else.**

Put your own analysis in there and the tool keeps running, keeps printing numbers, and the numbers
become flattery: a quotation copied out of your own memo verifies against your own memo. A mistake
made once validates itself forever after.

Measured, in both directions. An analytical file inside a statutes folder pushed a score to 87.2 %
where the honest figure was 75.6 %. And in the other direction, an archived copy of the tool's *own
report* sitting in a drafts folder produced **1 443 of 1 606** misses on its own output.

The tool screens per file and prints every exclusion. If it excludes something that really is a
statute, fix the pattern — do not ignore it.

### Choosing citation packs

```bash
python ~/tools/krokai/krokai packs
```

`us-federal` is the base and belongs in almost every configuration. Add `us-immigration` or `us-tax`
**alongside** it, not instead — specialist citations resolve into the Code and the CFR, and the base
pack is what knows those.

Adding your own body of law is a JSON file, not a code change. See
[FEATURES.md](FEATURES.md#citation-packs).

---

## The hooks

This is the step that makes everything else automatic, and it is the one people skip.

```bash
python ~/tools/krokai/krokai install-hooks --dry-run     # see the diff
python ~/tools/krokai/krokai install-hooks
```

**Why bother.** An instruction file in a real matter said, in bold, *"check every quotation as it is
entered"*. Measured over the working transcript, it was obeyed while the task was about checking, and
**not once** across three rounds where the task was strategy — rounds that produced new quotations.

> Rules fire by topic, not by rule.

A hook is executed by the harness, not by the assistant, so what the session happens to be about
cannot influence it. Measured cost of relying on the instruction: **16 turns produced quotations of
law and banked none of them.**

**What it does to your settings file.** It merges — other hooks are read, left alone, and preserved.
It backs the file up first. It is idempotent, so running it twice does not duplicate anything, and
`--uninstall` removes exactly its own entries. If your `settings.json` is not valid JSON it refuses
to touch it and says so.

🔴 **`settings.json` is read when a session starts.** Newly installed hooks do nothing in the session
that installed them. Start a new session, then run `python ~/tools/krokai/krokai doctor`.

---

## Confirming it works

```bash
python ~/tools/krokai/krokai doctor      # ends with STATUS: READY
python ~/tools/krokai/krokai check       # the whole-matter pass
python ~/tools/krokai/krokai close       # end-of-session checks
```

`doctor` prints what is installed, what is configured, and what is missing. If it ever prints
`READY` while exiting non-zero, that is a bug worth reporting: a status line that contradicts its own
exit code teaches people to ignore both.

---

## Uninstalling

```bash
python ~/tools/krokai/krokai install-hooks --uninstall
```

Then delete the folder. `casefile.json`, your quote bank, your library index and your reports are
plain files in your matter and are yours — nothing of yours lives inside the toolkit.
