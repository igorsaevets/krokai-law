# Instructions for an AI assistant installing this toolkit

**Human reading this: you do not need to.** Give your assistant the link to this repository and say:

> Install this for me, including the hooks. Follow INSTALL-FOR-AI.md.

Everything below is addressed to the assistant.

---

## Assistant: read this section before touching anything

You are installing a citation-verification toolkit into a legal matter folder. Five things matter
more than speed.

**1. You are editing the user's `settings.json`.** It may already contain hooks that belong to
something else — a secret scanner, an answer archiver, a formatter. The installer merges and never
replaces, but *you* must not hand-edit that file. Use the installer. If it refuses because the file
is not valid JSON, **stop and tell the user**; do not rewrite it.

**2. Do not put the user's own writing into `law/`.** That folder is primary sources only. If their
analysis ends up there, their quotations will verify against their own analysis and a mistake made
once will validate itself forever. This is the single most damaging thing you can get wrong here, and
it is silent.

**3. Do not invent the configuration.** Ask where their sources and drafts actually are, or look, and
say what you found. A wrong path produces an empty corpus, an empty corpus makes every quotation come
back `NOT_FOUND`, and that reads like catastrophe when it is a typo.

**4. Hooks take effect at the next session start, not this one.** Say so at the end, or the user will
test it, see nothing, and conclude the install failed.

**5. Report what you actually verified.** Not "installed successfully" — the counts, from commands
you ran, in this turn.

---

## Step 1 — check the environment

```bash
python --version          # 3.9 or newer
python -c "import pypdf" 2>&1 | tail -1
python -c "import fitz"  2>&1 | tail -1
python -c "import mammoth" 2>&1 | tail -1
```

Only Python itself is required. The three libraries are optional and each absence means one file type
reads as empty:

| missing | consequence |
|---|---|
| both `pypdf` **and** `fitz` (PyMuPDF) | every PDF is invisible; every quotation from one comes back `NOT_FOUND` |
| only one of the two | the cross-check that catches a word-splitting extraction cannot run — measured, one engine inflated a controlling opinion by 51 % in broken tokens |
| `mammoth` | `.docx` reads through the raw-XML pass only |

Install what is missing if the user allows it: `pip install pypdf pymupdf mammoth`. If they are on a
locked-down machine, continue without them and **say which file types will be invisible**.

## Step 2 — put the toolkit somewhere permanent

```bash
git clone https://github.com/<owner>/lawverbatim ~/tools/lawverbatim
```

No clone available? Download the ZIP and unpack it. The toolkit needs no installation step and no
`pip install` of itself — it runs from wherever the folder sits. That is deliberate: a tool a
paralegal cannot install is a tool that does not exist.

Verify:

```bash
cd ~/tools/lawverbatim && python -m lawverbatim selftest
```

Expect `self-test: N/N passed`. **If any check fails, stop and report it.** Do not install a checker
that fails its own checks.

## Step 3 — find out how the matter is laid out

Do not guess. Look, then confirm with the user:

```bash
ls -R <matter folder> | head -60
```

You are looking for three things:

- **primary sources** — statutes, regulations, decisions, agency manuals **as published**;
- **documents that get filed** — the expensive tier;
- **research notes, drafts, reviewers' answers** — the cheap tier.

Then say what you found and what you are about to configure, before you configure it.

## Step 4 — initialise

```bash
cd <matter folder>
python ~/tools/lawverbatim/lawverbatim init .
```

This writes a commented `casefile.json` plus `law/`, `case/`, `guides/`, `research/`, a quote-bank
template and a library index. It refuses to overwrite an existing `casefile.json` without `--force`.

Now edit `casefile.json` to match reality:

- `sources` — folders holding **only** primary sources. 🔴 Re-read point 2 above.
- `drafts` — tier `A` for what gets filed, `B` for guides, `C` for research.
- `citation_packs` — run `python -m lawverbatim packs` and pick. `us-federal` is the base and belongs in
  almost every list; add `us-immigration` or `us-tax` alongside it, not instead.
- `language` — `en` or `ru`, for verdict labels.
- `drop_cyrillic_quotes` — `true` when the user writes in Russian but the law is in English. It stops
  their own commentary being checked against a corpus of US statutes.

## Step 5 — make the PDFs searchable

```bash
python -m lawverbatim sidecar
```

Your own file-search tool does not read PDFs, and it does not tell you so. In one measured library
that was 67 files — 35 % of it — where every "I searched and found nothing" had been a false negative.

If it reports files with **no text layer**, list them for the user and stop there. 🔴 **Do not offer
to read the scans yourself.** You will produce plausible text, the plausible text will become a
quotation, and the quotation will then be treated as the primary source. That contamination is silent
and it defeats the entire point of the toolkit. OCR belongs to an OCR engine, run by a person who can
see the page.

## Step 6 — the first check

```bash
python -m lawverbatim check
```

Read the output before you summarise it:

- **Corpus of 0 files** → a path is wrong. Fix `casefile.json`; do not report results.
- **Files excluded as derived** → the tool thinks some of the user's own analysis is in `law/`. If it
  is right, move the file. **If it is wrong — if it excluded a real statute — say so loudly** and fix
  the pattern. A wrongly excluded source is invisible from then on.
- **Everything `NOT_FOUND`** → almost always an empty or wrong corpus, not a document full of
  fabrications. Check before alarming anyone.

## Step 7 — install the hooks

This is the step that matters most, and the reason is worth stating to the user rather than skipping.

An instruction in a project file said, in bold, *"check every quotation as it is entered"*. Measured
over a real transcript: it was obeyed while the task was about checking, and **not once** across three
rounds where the task was strategy — rounds that produced new quotations. **Rules fire by topic, not
by rule.** A hook is executed by the harness, and topic cannot influence it.

```bash
python -m lawverbatim install-hooks --dry-run     # look at the diff first
python -m lawverbatim install-hooks
```

Default scope is the project's `.claude/settings.json`. Use `--scope user` for the global one only if
the user asks — a citation checker firing in every unrelated project is noise.

Three hooks are registered:

| event | script | what it does |
|---|---|---|
| `PostToolUse` on Edit/Write | `quote_guard.py` | a long quotation of law entered a filed document and is not in the bank |
| `Stop` | `bank_queue.py` | queues every quotation of law from the answer that is not banked |
| `SessionStart` | `session_anchor.py` | states queue, index and sidecar status as **facts** |

The installer backs up the existing file, prints what it will change, is idempotent, and
`--uninstall` removes exactly its own entries.

## Step 8 — verify, then report

```bash
python -m lawverbatim doctor
python -m lawverbatim close
```

`doctor` must end with `STATUS: READY`. 🔴 If it prints `READY` and exits non-zero, that is a bug —
report it. A status line that contradicts its own exit code teaches people to ignore both.

Then tell the user, using **numbers you just saw**:

```
Installed at <path>.
Self-test: N/N.
Corpus: N source files, N MB. N excluded as your own writing: <list>. N with no text layer: <list>.
First check: N quotations, N needing a human in the filed tier.
Hooks: 3 registered in <path to settings.json>, backup at <path>.
🔴 Hooks start working at your NEXT session, not this one.
Not checked: whether any rule is still in force, and whether any quotation is apt.
```

---

## What to tell the user afterwards, in their words

- **`lawverbatim check`** before anything is filed.
- **`lawverbatim quote "<a quotation>"`** to check one, right now.
- **`lawverbatim close`** at the end of a working session.
- **`lawverbatim gate <file>`** before pasting anything into another AI — it blocks credentials outright
  and personal identifiers unless overridden, and it reports the kind and the line, never the value.
- The quote bank is **theirs**. Nothing writes to it automatically. The queue asks the question; the
  bank stores the answer, including the mandatory line **what this quotation does NOT prove**.

## Things you may be tempted to do, and should not

| tempting | why not |
|---|---|
| Hand-edit `settings.json` to "make it cleaner" | it may hold hooks that are load-bearing for something else |
| Put reviewers' answers in `law/` because they contain quotations | they are not primary sources; they would validate themselves |
| Read a scanned PDF and add the text | you will hallucinate, and it will be cited as the source |
| Report "installed successfully" without running `doctor` | the user cannot tell the difference, which is exactly why it matters |
| Silently fix a path that looked wrong | say what you changed and why; a config nobody understands is a config nobody maintains |
| Run `check` and summarise only the total | the tier breakdown is the point — a loose quotation in a research note is not the same problem as one in a filing |
