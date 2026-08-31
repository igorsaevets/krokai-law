# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- KROKAI-SELFTEST: DISCUSSES-PLACEHOLDERS - this log quotes the defects it records, and one
     of them is an unreplaced clone-URL placeholder. The self-test's placeholder check honours
     this declaration for a document that declares it, and refuses the declaration outright to
     README.md, README.ru.md, INSTALL.md and INSTALL-FOR-AI.md - the files a reader copies
     commands out of. Exempting a declared file is auditable; exempting a filename is the
     allowlist mistake that shipped a mangled LICENSE in a sibling project. -->

## [0.10.1] - 2026-08-31

The R76 panel's deferred backlog, closed item by item — PLUS the R77 panel round (five external
reviewers on the diff itself: grokbuild + spark12cont + agy31pro + agy37flash; codex-gpt-5.5
FAILED the round with a drafting monologue and its solo re-run was deferred). Every claim was
re-verified against the code — nine by probe — before its fix; each fix is pinned with a
positive AND a negative control in `suite_r77` / `suite_r77_cli` / `suite_r77b`. Three items
were deferred again with reasons (per-site address folding needs primary-citation semantics;
the `body_head` window and the minimum-length floors need a measured corpus first), and one
panel claim was refuted on re-reading: the guard hook's "cross-drive relpath crash" cannot
trigger — the config walk starts at the edited file's own folder, so the two paths share a
mount in every constructible case. The hardening went in anyway, with a log line, because an
exception path that bypasses the log makes "dead" look like "quiet".

### Fixed — panel round (R77 panel: F-A..F-G′)
- **A digit-prefix substring no longer blesses a wrong-title file** (F-B, grokbuild CRITICAL,
  probe-proven). `file_matches(("cfr","8","1"), "18CFR-part-1.xml", "")` used to return True —
  the weak-branch substring test `"8cfr" in "18cfrpart1"` succeeded because rule 1 had no
  digit-boundary. A digit anchor now gates the weak branch when the needle starts or ends with
  a digit; the symmetric end-guard survives a future `_NUM_TAIL_RE` change.
- **A new filename-level negative guard closes rule 2** (F-B extension, uncovered by executing
  the F-B fix, probe-proven). Rule 2 (`"part{g2}"` + `any: ["cfr", "title{g1}"]`) matched the
  same wrong-title file via `_has(part1)+_has(cfr)`; the head guard could not fire on the
  empty-body probe. `reject_if_filename_names` mirrors the head-guard design and is added to
  CFR/USC rules 2 and 3 in `us-federal.json`. Real download names like `part245-ecfr.xml` are
  unaffected (the scan requires `\b\d{1,2}(cfr|usc)` — a title-declaring prefix, not a bare
  digit sequence).
- **One stray foreign cross-reference no longer rejects a true title-8 file**
  (F-A, spark12cont CRITICAL + agy37flash CRITICAL + agy31pro HIGH, probe-proven). The
  expensive symmetric direction: `reject_if_head_names` turned a genuine `USCODE-2024-section1255`
  head citing `26 U.S.C. 7701` once into UNVERIFIABLE. Now: any own mention rescues (checked
  against the whole list of matches), and a per-scan `min_count` (2 on the four citation-form
  scans) requires the same foreign title to appear twice before rejecting. Heading-form scans
  keep default 1 — an em-dash banner is a file naming itself.
  **Priced-aloud residual:** a real title-26 file whose filename lacks its own title digits AND
  whose head names 26 exactly once can now false-match an 8-key via the title-less usc rule 2.
  Narrow corner; F-B's digit boundary kills the filename-titled cases, and rule 2's new
  filename guard kills the `\d{1,2}(cfr|usc)`-prefix cases. The panel unanimously rated
  false-REJECT of true law the worse direction; this is its price, priced aloud.
- **`SENTINEL_HEAD` unifies the sentinel window across the package** (F-C, grokbuild MAJOR +
  agy37flash MAJOR, probe-proven at offset 431). Three call sites read the tool-output header:
  `run._is_tool_output`, `sidecar._current`, `exhibit_check._is_tool_output`. Two said 400
  characters, one said 2000; a probe at offset 431 was invisible to two. A single constant
  `run.SENTINEL_HEAD = 2000` is imported by all three, and a class-pin in `suite_r77b` greps
  `\.read\((\d+)\)` in `krokai/*.py` + `hooks/*.py` and asserts no literal below 2000 remains
  — the pin that stops a fourth 400 from appearing when someone forgets to import.
- **Exhibit intake refuses .doc + corrupt .docx + unknown-binary soup** (F-D, agy37flash + 3
  channels, probe-proven three shapes). `.doc` silently returned "" (references vanished);
  a corrupt `.docx` was swallowed by `except Exception: return ""`; an unknown extension
  was decoded `errors="replace"` and searched for exhibit IDs — probe-proven with a `.sqlite`
  file where the soup hit an ID by luck. Now: `.doc` and corrupt `.docx` raise `MissingReader`
  with conversion advice; `_read_text` uses an ALLOW-list; unknown binaries return "" without
  opening. The reconcile side also learned to report an empty `.docx` (valid zip, empty body)
  as unread — before, only `.pdf` had an empty-text row.
- **`krokai check-exhibits` exits 1 over unread petitions** (F-E, grokbuild MAJOR,
  probe-proven). The round's exit-code theme (kimik3/lunapro's #339 was the same shape): a
  mixed folder reported "PETITION FILES NOT READ" AND exited 0, invisible to every hook and CI
  job. Now: unread non-empty → return 1. With F-D this also means a matter holding `.doc`
  petitions now exits 1 until they are converted — deliberate. No `--allow-unread` escape flag
  (R44 registry lesson: a documented escape becomes the default).
- **Mid-name exhibit IDs report as duplicates** (F-F, grokbuild MINOR, probe-proven). Position
  parity with the admission logic at exhibit_check.py:234: `_part_after_id` mirrors
  `id_re.search(fn[:50])` and searches for a part suffix AFTER the located ID (never across
  the whole basename). Two copies of `Letter B-03 old.pdf`/`Letter B-03 new.pdf` were
  previously excluded because the whole-name scan matched the exhibit's own `-03` — the R51
  position-keying lesson repeating.
- **`neutral_cwd` uses `tempfile.gettempdir()` instead of `"."`** (F-G′, grokbuild MINOR,
  probe-proven). The old chain fell to `"."` when both TEMP and TMPDIR were unset, making the
  scratch RELATIVE and INSIDE the matter — so the SystemExit guard never fired and the
  CLAUDE.md-injection leak the function exists to prevent proceeded silently. `gettempdir()`
  walks TMPDIR→TEMP→TMP→OS fallbacks and practically cannot come back unusable; SystemExit
  still guards `makedirs`/`chdir` failure. The panel's "wrong exception class" claim was
  REJECTED as documented (fail-closed by design; SystemExit is this codebase's idiom, see
  `legal-toolkit/CLAUDE.md`).
- **KeyMap failure prints move to stderr** (spark12cont MINOR). Address rule crash messages
  used to pollute `krokai check`'s stdout, which parsers scanned line-by-line. Still loud —
  the whole point of #356 — just on the honest stream. `suite_r77`'s pin captures stderr too.
- **`form_dump` sentinel imports are lazy** (grokbuild/spark/agy37flash MINOR — a run-chain
  eager cross-module import is a future-cycle magnet). Module-level `_STAMP_TXT`/`_STAMP_MD`
  moved into a `_stamp(kind)` helper; the `SENTINEL` import happens on first call and never
  reaches the module globals. Pinned in `suite_r77b`.
- **`quote_guard` reuses the display relpath** (cleanup, not a fix; the panel's L196 unguarded
  crash claim was REJECTED as unreachable). The message reuses `rel_disp` from the guarded
  block above; L196 no longer computes relpath independently.

### Notes carried but NOT code changes (documented, backlog)
- The three source-text pins in `suite_r77` (L3048 fetch, L3092 upgrade, L3179 quote_guard)
  grep source text instead of driving behavior. Deferred to backlog #361 — conversion needs a
  hook-subprocess harness setup and is best done as its own change.
- Two "EOF marker not found" stderr lines during selftest are pypdf noise on the F-E broken-PDF
  fixture — cosmetic; backlog to wrap in `contextlib.redirect_stderr`.
- `publish.yml` triggers PyPI publishing on tag `v*` via Trusted Publishing, and a PyPI version
  number can never be reused (even after yank) — the ship checklist push-main-then-tag order
  is now load-bearing, not stylistic.

### Fixed — exit codes a script can finally trust
- **`krokai review` reflects the QUOTATION audit in its exit code** (kimik3, lunapro). Both the
  full round and `--audit` discarded the audit rows: a reviewer's fabricated quotation printed a
  red table and exited 0 — invisible to every hook and CI job. A non-clean audited quotation now
  exits 5, distinct from 1 (a channel failed): transport and trust are different alarms.
- **`krokai check --strict-address`** (opt-in): the address layer's own doctrine — «NO_NEARBY_CITATION
  on something you file means do not award a green» — was prose with no mechanism. With the flag,
  a filed-tier quotation with no checkable address exits 5.
- **`krokai fix-pdfs` exits 1 when repairs failed** (lunapro), and says which files are still
  broken. An all-fail batch used to print "Nothing to fix." and exit 0.

### Fixed — silent losses
- **`krokai review` now loads `keys.env`** (orgemini37flash). The documented second-best home for
  a key was read by `krokai keys` — the command that only reports — and by nothing that dispatches.
- **Exhibit reconciliation reads PDF petitions** (spark12cont +3) and reports every petition file
  it could NOT read as a loud section instead of a silent zero — the mixed-folder case dropped
  every reference living only in the PDFs. `.docx` petitions no longer break words at run
  boundaries («Exh|ibit» — probe-proven, agy31pro), and table cells are still walked.
- **The DUPLICATE class was unreachable** (kimik3, grokbuild; probe-proven): the part-suffix
  regex matched the exhibit's own number («B-03 old.pdf» "has a part suffix" via `-03`), so
  `all(...)` held for every hyphenated ID. The suffix is now searched only AFTER the matched ID.
- **`scan_form_dir` no longer counts this toolkit's own output as forms** (goog37flash): it had
  no extension filter, so `I-485.forms.txt` registered as a second copy of the form. Both
  exhibit and form walkers now skip sentinel-stamped files, and `form-dump` stamps everything it
  writes — an unstamped dump inside a sources folder was the 0.6.x sidecar incident waiting to
  repeat.
- **The quote-guard hook reads `NotebookEdit`** (orglm53): the tool was in its list, but the
  hook read only `file_path` while the tool sends `notebook_path` — so notebook edits were
  never guarded. `new_source` is now also read.
- **`bank.candidates` keeps the LONGER quotation** (probe-proven): a full provision arriving
  after its own clause was silently swallowed by the symmetric containment dedup — the guard
  then never saw the quotation most worth checking.
- **OCR sanitize keeps every script** (qwen38max): the allowlist held ASCII plus one Cyrillic
  block, so `José`, Greek, Hebrew and CJK became spaces in the repaired text layer. Now
  keep-what-is-printable; controls and U+FFFD still fold to spaces. `EXTRACTOR_VERSION` bumped
  so cached extractions notice.
- **`.doc` refuses loudly** (grokbuild): binary Word decoded as UTF-8 soup — probe: 3 798
  characters from a 4 KB file — passed every floor and indexed. Now `MissingReader`, with
  conversion advice, and the corpus reports the file unreadable.
- **`read_docx` no longer doubles the body** (agy31pro, lunapro): the raw-XML pass re-read
  `document.xml` even when mammoth had already returned the body, tables included
  (probe-proven) — every phrase count over a .docx measured the reader, not the document. The
  XML pass now takes the body only when mammoth produced nothing; footnotes/headers stay.

### Fixed — misdiagnoses and rot
- **«Download it» is no longer said about a file already on disk** (orgrok420): when the cited
  address resolves to a file the corpus EXCLUDED — a bot wall saved as the chapter, a scan, an
  empty download — the NO_SOURCE_ON_DISK advice now names the file and the exclusion reason.
- **A broken pack rule is printed, not swallowed** (qwen38max, orglm53): `KeyMap.resolve`'s bare
  `except: continue` made a rule crash indistinguishable from a non-matching file.
- **`us-federal` addresses now know their titles** (lunapro): `26USC-1255` satisfied a key for
  8 U.S.C. § 1255 — the USC filename rule had lost the title the CFR rule always carried. Both
  shapes also gained a negative head guard: a file whose own head names a DIFFERENT title is
  rejected for that key.
- **The corpus PDF stub test uses the per-page rate** (lunapro): `no_text_layer` carried the
  41-page-scan lesson and nothing in the corpus path called it — long thin scans passed the
  document-wide floor exactly as documented against.
- **The tool-output sentinel is read from a 2000-character window** (agy37flash), and a new
  test enumerates every stamped writer in the package against that window.
- **`fetch` probes the whole refusable region for placeholder text** (grokbuild, lunapro) —
  4 000 of a possible 20 000 bytes left the tell-tale of most modern interstitials unread — and
  a trailing-slash URL takes its extension from Content-Type instead of minting `.gov` from the
  hostname (goog37flash; probe-proven), which had been re-opening the unstripped-markup defect
  this module documents for query strings.
- **A reused answers folder cannot resurrect last round's answers** (kimik3, codex, lunapro):
  `absorb_delegated` grades only files written by THIS dispatch and prints what it skipped.
  A failed `neutral_cwd` now REFUSES the round instead of dispatching CLI channels from the
  matter's own folder — the leak it prevents is confirmed, not hypothetical.
- **`krokai upgrade` refreshes hooks in every install layout** (agy37flash, goog36/37flash,
  orgemini37flash): the refresh spawned `-m krokai` from the matter's cwd, where a clone or
  copy layout has no `krokai` on `sys.path`. It now runs the package directory, which
  `__main__.py` supports in all four layouts. `find_harness` returns absolute paths — a
  relative one was checked in the launch directory and executed after the cwd had changed.
- **`review.py`'s dead twin of `find_harness`/`run_harness` deleted** — nothing imported it,
  which is precisely how a fork rots while looking authoritative. One home: `consult.py`.

## [0.10.0] - 2026-08-31

19-channel independent audit round (R76). Every fix below was reproduced by execution BEFORE it
was fixed and is pinned by a regression test in `suite_r76`.

### Fixed — false-green paths (the tool's own worst failure class)
- **The anchor-miss repair no longer launders dangerous verdicts.** `address.fold()` used to
  overwrite ANY verdict — including TRUNCATED_CONDITION — with VERIFIED the moment the text was
  even loosely contained in the cited file; a truncated quotation is a substring of the full
  provision by construction, so the repair blessed exactly what it should have flagged. Named
  independently by 12 of 17 reviewing channels. Now: the truncation and leading-negation
  questions are re-asked AT the cited file, the superseded-edition question is re-asked at the
  repaired path, a dangerous verdict upgrades only on EXACT containment, and the containment
  tier caps the outcome (exact→VERIFIED, dehyphenated→TYPESETTING, alphanumeric→PUNCTUATION).
- **The alphanumeric branch now asks the exact branch's questions at the located span.** An
  internal punctuation drift plus a stop-before-limiter came back PUNCTUATION (green); a cut
  leading «no» plus a drift came back PUNCTUATION; «no table» quoted from «not able» came back
  PUNCTUATION «spacing only». All three now come back loud (TRUNCATED_CONDITION /
  TRUNCATED_OPENING / OPERATOR). Genuine punctuation drift and intra-word hyphen variants
  («non-immigrant»/«nonimmigrant») stay green — pinned by controls.
- **A 10–24 character tail fragment is anchored, not waved through.** `ellipsis_parts` keeps
  fragments ≥10; the tail check declined under 25 — so a hidden «, unless …» after a
  21-character tail sailed to ASSEMBLED, green. The window the R56 enumeration never tried.
  A short tail is now checked in the files where the earlier fragments anchored.
- **A bare omitted digit is no longer excused as a welded footnote.** `FOOTNOTE_RE`'s citation
  group was optional, so dropping «90» from «within 90 days» never reached the digit→OPERATOR
  rule. The group is now mandatory; a real welded footnote number will surface loud.
- **Sentences verbatim in two DIFFERENT files are SPLICED, not SCATTERED.**
- **The superseded chain survives a third edition.** The registry keeps one entry per provision,
  so from the third edition on, the first edition silently left the superseded set and verified
  green. New intake entries carry the whole chain in `superseded_paths`.
- **Every CLI door now builds the corpus through `run.corpus_for`.** `krokai quote`,
  `review --audit` and `mutate --report` built a bare corpus — no sentinel, no superseded set —
  so sidecars indexed as law and SUPERSEDED_EDITION was unreachable from those commands.
- **The reader cache key includes `EXTRACTOR_VERSION`**, and a failed Type 3 repair is printed
  and never cached — broken extractions used to be served forever with no signal.

### Fixed — silent losses and misdiagnoses
- `citation_window` locates line-wrapped and markdown-formatted quotations through an
  alphanumeric-projection fallback; the miss used to be silent and turned the address layer off.
- The 🔴/🟡 NOT_FOUND classifier resolves the cited key through the keymap instead of searching
  the citation string in the corpus body — confirmed fabrications drifted into «probably a gap».
- `dump-forms` dedups by full path, not basename (a second `i-485.pdf` was silently skipped);
  collision-safe dump names; checked-checkbox spellings («[X]» vs «Yes») no longer count as
  cross-engine divergence; agreement is n/a over zero shared fields.
- Every directory walker reports unreadable directories (`os.walk` `onerror`) and sorts
  subdirectories for a deterministic corpus order.
- `reviewer` answer audit: sort order derives from `verdicts.ORDER` (four verdicts used to rank
  below VERIFIED); the harness's own round artifacts (ANALYTICS.md and friends) are no longer
  graded as reviewers' answers.
- `library.orphans` derives its extensions from `corpus.DEFAULT_EXT` (`.docx` was invisible) and
  honours `skip_dirs`; `krokai close` passes them.
- `intake` removes an ALREADY-HAVE duplicate from the inbox instead of re-announcing it forever;
  a tail-ellipsis banked quotation present in a new edition is no longer reported lost.

### Added
- `verdicts.SIX_CAUSES` — the six causes of a false NOT_FOUND, previously pointed at by three
  places and existing nowhere.
- Bare section references («Section 245.2(a)», «§ 1255(k)») recognised as neighbour citations
  in the base pack — previously invisible, so a NOT_FOUND beside one was misclassified
  «evidentiary».
- SCATTERED renders a non-blank mark, and the summary table prints each verdict's mark.
- Matter template: name every new file and folder in Latin (`A-Za-z0-9._-`) — non-ASCII names
  break the scripts around a matter in quiet ways.

## [0.9.3] - 2026-08-22

### Added
- **FRAGMENTS verdict** — a new 16th verdict for quotations where large shingles (>=8 words)
  exist verbatim in the corpus but the full quotation does not. Sits between ELLIPSIS_HIDES and
  NOT_FOUND in severity order. Prevents a public accusation of fabrication when the real cause is
  an outdated edition, a corpus gap, or a silent splice. Ported from AOS verify_batch.py R66-O4.

### Fixed
- **Tail-ellipsis anchoring** (AOS R71, v2.8.5): `tail_elision_hides` now restricts the search
  to files where earlier fragments were found. Without this, a short last fragment like "the
  Secretary may" could match in an unrelated statute, producing a false ELLIPSIS_HIDES. Proven by
  probe and confirmed by a 12-channel panel (grok420 + agy37flash found the scenario independently).
- **Ellipsis-alnum guard** (AOS R66-D4): an ellipsis quotation no longer enters the alphanumeric
  branch, where `alnum()` would concatenate "A ... B" into "AB" and falsely report PUNCTUATION —
  a green verdict on a quotation that silently skipped text. Panel finding, 5/11 rated HIGH.
- `truncated_condition` gains a `restrict_to` parameter for the anchoring fix above.

## [0.9.2] - 2026-08-22

### Added
- **Form field dumper** (`krokai/form_dump.py`, `krokai dump-forms`): extracts filled AcroForm
  field values from USCIS PDF forms with dual-engine cross-verification.
  - Dual engine: fitz (PyMuPDF) for coordinate-sorted reading order, pypdf for independent
    verification. Either engine works alone; both together produce a cross-check report.
  - G-1450 exclusion: credit-card authorisation forms are skipped by default (cardholder data).
  - Cross-engine agreement report (`cross-check.md`) with per-form divergence counts.
  - Multi-copy field diff (`i485-diff.md`) when two or more copies of the same form are found.
  - Machine-readable manifest (`manifest.json`) for downstream tooling.
  - `[BLANK]` markers on empty fields — the absence of an answer in a USCIS form is itself
    a statement.
  - Tested on real AOS filing package: 17 forms, 5 G-1450s excluded, 0 errors, 99.1-100%
    cross-engine agreement.

## [0.9.1] - 2026-08-22

### Added
- **Exhibit / form cross-checker** (`krokai/exhibit_check.py`): verifies that exhibits and forms
  referenced in petition documents actually exist as files on disk, and flags orphan files that
  no petition mentions. Designed for pre-print review of immigration filing packages.
  - `ids_in_text(text)` — extract exhibit IDs from document text, with guards against
    A-numbers, receipt numbers, and form codes that look like exhibit IDs.
  - `forms_in_text(text)` — extract form IDs (I-485, G-1450, ETA-9089, etc.).
  - `scan_exhibit_dir(root)` / `scan_form_dir(root)` — recursive file scanners.
  - `reconcile(petition_paths, exhibit_dirs, form_dirs)` — the full cross-check, producing
    a structured report with four verdict classes: CITED-NO-FILE, FILE-NO-CITE, DUPLICATE,
    and form-level equivalents.
- New CLI command: `krokai check-exhibits --petition <paths> --exhibits <dirs> [--forms <dirs>]`.
  Reads petition documents (.md, .txt, .docx), scans exhibit and form directories, reports
  mismatches. Exits 1 when any cited exhibit or form is missing.

## [0.9.0] - 2026-08-22

### Added
- **PDF repair pipeline** (`krokai/repair.py`): detect and fix PDFs with broken PScript5 / Type 3
  text layers — the glyph-substitution cipher that makes text extraction return control characters.
  - `is_broken_type3(path)` — lightweight detection (pymupdf only).
  - `scan_broken_pdfs(directory)` — recursive scanner.
  - `fix_broken_pdf(src, dest)` — renders at 300 DPI, runs RapidOCR (PP-OCRv6), overlays invisible
    TrueType text layer. Cross-platform font discovery (Windows/macOS/Linux).
  - `fix_batch(directory, output_dir)` — batch repair with progress callback.
- Three new CLI commands: `krokai scan-pdfs`, `krokai fix-pdf`, `krokai fix-pdfs`.
- Auto-repair in `read_pdf()`: when both extraction engines return garbage and the PDF is a broken
  Type 3 document, the repair pipeline runs transparently (if rapidocr is installed).
- `engines_available()` now reports RapidOCR presence.
- New `[ocr]` install extra: `pip install "krokai[ocr]"` installs rapidocr + onnxruntime + numpy.

## [0.8.7] - 2026-08-19

**A review panel called the silent 25-character floor a real defect. It is unreachable, and the
one reviewer who said what would change its mind is why we know.**

`tail_elision_hides` declines to examine a quotation's tail when the fragment before the final
ellipsis is under 25 characters, and returns the same `None, None, None` it returns for "checked,
nothing hidden". Put to an eleven-channel review panel, every channel that answered called it a
real defect — a tool whose output decides whether a filing's quotations are safe must not report
*could not check* as *checked, clean*. Three of them (`grokbuild`, `spark12cont`, `mimo25pro`)
additionally argued **against** a fourth verdict state and for a counted disclosure on the
existing one, which is what the sibling path forty lines below already does. A disclosure was
written on the strength of that.

Then the shapes were enumerated and run against a corpus containing all of them:

| quotation shape | verdict | tail unexamined? |
|---|---|---|
| single fragment, long, tail hides a limiter | `ELLIPSIS_HIDES` | no |
| single fragment, long, tail hides nothing | `ELLIPSIS_HIDES` | no |
| single fragment, **short (<25)** | `NOT_FOUND` | — quotation not locatable |
| multi fragment, **last fragment short** | `OPERATOR` | — short fragment dropped upstream |
| multi fragment, last fragment long | `ELLIPSIS_HIDES` | no |
| no trailing ellipsis | `VERIFIED` | n/a |

**Zero shapes reach a clean verdict with an unexamined tail.** `ellipsis_parts` already discards
sub-floor fragments *before* `tail_elision_hides` reads `parts[-1]`, so the value is short only
when the whole quotation is one short fragment — and a quotation that short cannot be located, so
it comes back `NOT_FOUND`, which is loud.

`agy37flash` called this exactly, in its own *what would change my conclusion*: **"If `verify.py`
has an upstream pre-filter that guarantees `parts[-1]` is always ≥ 25 characters, the branch would
be dead code rather than an active defect."** It does. That single sentence was worth more than
the four verdicts that agreed with each other, and it is the reason a reviewer is asked what would
change its mind rather than only what it concludes.

So **no disclosure ships** — a guard that cannot fire is decoration with a green tick, a defect
this project has named repeatedly. What ships instead is `tail_short_enough_to_decline` plus an
assertion that pins the finding: if a future change to `ellipsis_parts` lets a short tail through
to a clean verdict, the suite goes red and the panel's finding becomes live. The assertion carries
its own positive control, because "no clean verdict over an unexamined tail" is trivially satisfied
by a predicate that never fires.

**Not disproved — unreachable on every shape tried.** Six synthetic shapes are not a filing; the
population that settles it is the 384 unread tail-ellipsis quotations from real material.

## [0.8.6] - 2026-08-19

**A scanner tested only on the tree it ships with has been tested on one sample. 0.8.5's new
detector called correct code a defect, and the suite that proves it works was green throughout.**

`suite_write_only_accumulator` shipped yesterday with a positive control, a negative control and a
coverage assertion — and it was still wrong for anybody but us. Run against a foreign codebase
(this project's own review harness, ~40 000 lines) it flagged:

```python
def record_refusal(msg, hard, soft):     # hard/soft: filled here, read by the CALLER
    if is_soft(msg):
        soft.append(msg[len(SOFT):])
    else:
        hard.append(msg)
```

Two names appended to and never read — *inside this file, under these names*. The nine call sites
pass `warn`, `note` and `fail`, and read them there. The helper is correct; the detector was not.

The reason 0.8.5's controls did not catch it is worth stating plainly: **krokai contains no helper
of that shape**, so the in-tree scan was green by accident of sample, not by correctness. A
detector's controls test the detector against the cases its author thought of; only a foreign
codebase tests it against the cases they did not.

- **Fixed.** A name bound as a parameter of any enclosing function is excluded. The exclusion is
  lexical and deliberately generous — it can miss a module-level accumulator that happens to share
  a name with some parameter elsewhere in the file. That trade is chosen knowingly: **a false
  positive in a safety gate is worse than a miss**, because it teaches the reader to wave the check
  through, and that disables the whole class — including the real `NEIGHBOUR_SKIPS` this suite
  exists to catch.
- **Two permanent cases added.** The 0.8.5 false positive, verbatim in shape; and — in the same
  file as a real defect — proof that the new exemption did **not** blunt the detector. A fix that
  silences a check passes every test that only asks for silence.

Nothing else changed. 488 self-tests (486 + these two).

## [0.8.5] - 2026-08-19

**A list that is only ever appended to is a silent drop wearing a variable name. Found in my own
code, by the project I had just sent a patch to, one day after I wrote the rule it breaks.**

The sister project's round 49 reviewed a patch written for it here, and found:

```python
NEIGHBOUR_SKIPS = []      # (файл, сколько блоков вырезано) — печатается в конце прогона
```

Declared with that comment. Appended to in exactly one place. **Read in none.** 104 rows vanished
from a report without a word — in code whose entire purpose was to stop a silent drop. The comment
was an assertion by its author about a program that never did it.

Same shape as 0.8.3's `tail_elision_hides` justification: *a sentence about control flow that was
never executed.* The difference is that this one is mechanically detectable, so it need not be
remembered. `suite_write_only_accumulator` walks the package with `ast` and fails on any name that
is `append`/`add`/`extend`/`update`-ed and never loaded back.

The suite carries a **positive control**, because that is what decides whether it is a measurement
or a decoration: a known-bad snippet must come back red in the same run, and a `scanned >= 8`
coverage assertion proves the walk actually opened the package. Verified independently by
neutralising the sister project's repair on the live file — the detector went red on the version
that provably had the defect and stayed green on the repaired one.

No behaviour change. `krokai` itself was already clean of this class; the point is that "clean" is
now a result rather than an opinion.

## [0.8.4] - 2026-08-19

**The 0.8.3 repair recognised two spellings of an ellipsis and missed the one legal citation
actually prescribes. Found by the panel that reviewed 0.8.3, confirmed by execution the same hour.**

The Bluebook (rule 5.3) marks an omission with three periods **separated by spaces**: `. . .`.
Three separate places in this codebase each spelled "an ellipsis" for themselves, and all three
wrote `...` or `…`:

| where | what it said |
|---|---|
| `ellipsis_parts` | `re.split(r"\.\.\.\|…", q)` |
| `truncation_anywhere` | `quote_n.rstrip().endswith(("...", "…"))` |
| `check()`'s ellipsis branch | `if ("..." in n or "…" in quote)` |

The consequence was not silence — it was the opposite, and worse. A quotation ending `. . .` fell
past the ellipsis machinery entirely and came back **`TRUNCATED_CONDITION`**: *"you cut this off
silently."* That is the exact false accusation against honest citation practice that 0.8.2 was
written to remove, still live one release later for the one dialect that matters most in law.

Measured on a real filing: **80 quotations** use the spaced form. They were invisible both to the
0.8.3 measurement (so the 1 118 population was a count about a dialect) and to the repair.

`ELLIPSIS_RE` is now defined once in `normalize.py` and imported by everything that asks the
question. `\.\s?\.\s?\.` allows **at most one space** between periods, so `U.S.`, `see id. at 12`
and `decided in 1990. J. Smith wrote` cannot match — letters sit between their periods. Four
negative controls assert that on real citation shapes rather than on the argument.

The general lesson, which is the round's: **a question about a CONCEPT, answered by listing two of
its spellings.** Every defect in the 0.8.x series has that shape — a guard on one branch of six, a
gap computed between fragments but not at the tail, an exhibit id matched by shape rather than
position. Naming the concept once and referring to it is the repair in each case.

## [0.8.3] - 2026-08-19

**The sentence 0.8.2 used to justify itself was not true of the code, and the hole it left is the
one an immigration filing actually has: the elision at the END of a quotation.**

0.8.2 said a disclosed elision "belongs to the ellipsis machinery below, which already asks what
was hidden". `check()` enters that machinery only when `len(parts) > 1`, and a quotation that
merely *ends* with an ellipsis splits into **one** fragment. It never arrived. It fell through to
`PUNCTUATION` — green — with the detail line **«our quotation adds `.`»**, which is the exact
confident-wrong-answer defect 0.8.1 was written to remove, reintroduced one release later by the
comment that claimed to have handled it. A statement about control flow, written in prose, never
executed.

Underneath it, a defect older than either release: `Corpus.gaps` computes
`for k in range(len(parts) - 1)` — the spans **between** fragments. A tail is not between anything,
so the span a trailing ellipsis hides was never handed to `NARROWER_RE` at all, in any code path.
In legal drafting the proviso is at the end of the sentence — `", provided that"`, `", unless"`,
`", except that"`, `" subject to"` — so the single elision position the tool did not examine is the
position where the limiter almost always is.

One variable, same hidden words, same source:

| where the ellipsis sits | verdict before |
|---|---|
| in the middle | `ELLIPSIS_HIDES` — loud, correct |
| **at the end** | **`PUNCTUATION` — green** |

`tail_elision_hides()` asks the existing two-signal `truncated_condition` about the last fragment,
and returns `ELLIPSIS_HIDES` — not `TRUNCATED_CONDITION`, because the drafter *did* disclose, and
not silence, because what was disclosed still narrows the rule. Both findings survive: 0.8.2's
panel was right about the name, 0.8.3 is right about the colour.

**Measured on a real filing before it was believed.** Of 1 118 quotations that end in an ellipsis:
552 were already loud, 539 stay green, **26 turn loud (2.3%)**. All 26 read by eye, all 26 hide a
real carve-out — `"employee means an individual…"` hiding *"but does not mean independent
contractors"*; `"No appeal lies from the denial…"` hiding *"but the applicant retains the right to
renew"*; `"Applications that are rejected and returned…"` hiding *"do not retain a filing date"*.

A 27th alarm was a false one and produced the only threshold here: its last fragment was
`«(I) In general»`, fourteen characters, a heading that occurs throughout the U.S. Code — so the
locator matched a different statute and reported that one's continuation. The 25-character floor is
not invented for this check; `ellipsis_parts` already uses 25 for *"this fragment proves something
on its own"*. It removes exactly that alarm and no other.

`suite_r51_tail_elision` locks it with two positive and three negative controls, and one of the
positives asserts the **detail line** rather than the verdict — because the regression was never
only about the colour, it was about telling the reader a confident wrong thing.

## [0.8.2] - 2026-08-19

**The fix in 0.8.1 shouted at honest citation practice. The review panel that reviewed the fix
found it, 7 channels of 13 converging on the same hole, and it reproduced on the first try.**

`truncation_anywhere` strips trailing punctuation so it can re-locate an exact span. That strip
also ate a trailing **ellipsis** — and an ellipsis is the drafter *disclosing* the elision. So
`«…within 180 days of the qualifying event…»` came back `TRUNCATED_CONDITION`, exactly as loudly as
a silent truncation of the same sentence.

That is the failure mode 0.8.1's own changelog warned about — "a false alarm in a safety gate
teaches the reader to click past it" — introduced by the very change that quoted the warning. The
distinction the verdict exists to draw is *disclosed* versus *silent*, and the first version erased
it.

A disclosed elision is now handed back to the ellipsis machinery, which already asks what the
elision hid (`NARROWER_RE`) instead of assuming. `NEG-3` covers both spellings, `...` and `…`.

Sequence worth recording, because it is the argument for running the panel at all: the fix was
built with controls, proven to bite, shipped — and a hole in it was still found by outside readers
within the hour. Suite: 467/467.

## [0.8.1] - 2026-08-19

**A green verdict could be bought with one character. The truncation guard covered one branch of
six, and adding a full stop to a truncated quotation moved it from the loudest verdict to a
cosmetic one.**

`truncated_condition` needs an exact substring hit, so it could only ever run on the exact-match
branch — and it was called there, once, together with `leading_cut` and `wrong_speaker`.
`_check_inner` has 20 returns, 8 of them green, and **6 of those 8 returned without consulting any
guard**. That is not a guard on the verdict; it is a guard on one branch.

Measured with one distortion — a sentence cut off before its proviso — presented three ways. The
meaning is identical every time; only the surface differs:

| what the drafter pasted | before | after |
|---|---|---|
| the quotation as-is | `TRUNCATED_CONDITION` | `TRUNCATED_CONDITION` |
| the same + a trailing full stop | **`PUNCTUATION`** | `TRUNCATED_CONDITION` |
| the same + a line-break hyphen | **`PUNCTUATION`** | `TRUNCATED_CONDITION` |

The mechanism: `alnum` drops *all* punctuation, so the alphanumeric index cannot tell "the same
words with a comma moved" from "a **prefix** of the words, stopped before the proviso" — both are
substrings of the same haystack. Ending a quotation with a full stop is the ordinary thing to do, so
the laundering needed no ill intent and left no trace.

Worse than silence: `_punctuation_detail` then printed ``our quotation adds `.` `` — a precise,
confident explanation of the *wrong difference*, which is exactly what makes a reader stop looking.

**Fixed** by `truncation_anywhere()`, which asks the existing question on the projections that
produced the match (strip the trailing punctuation the quoter added, heal a line-break hyphen,
retry). It is called before `PUNCTUATION`, before `TYPESETTING`, and on the shingle path's green
exit. No new detector and no new class of alarm — the same alarm, on the branches that skipped it.

**The regression lock is the part worth copying.** The existing suite passed *before* this fix and
after it: every truncation case it owned was written without trailing punctuation, so it could not
fail on the bug. `suite_r50_no_green_without_guard` states the bug in the shape it had — three
positive controls and, deliberately, **two negative controls** asserting that a complete quotation
with an added full stop, and a genuine punctuation drift, both stay green. Turning every near-miss
red would pass the positives and produce a worse tool, because a false alarm in a safety gate
teaches the reader to click past it. Proven to bite: with the helper neutralised, 2 of the 5 go red
and the other 3 stay green.

Found while auditing a sibling instrument on a live filing, which has the identical shape. Measured
there over 14 902 quotations: 3 939 green verdicts, of which **1 960 were reached by a branch that
never consulted a guard**, and 20 sit on a source that demonstrably continues with a limiter. The
20 is a floor, not a total — it counts only cases where an exact span could be re-located.

**Known and NOT changed.** A quotation of a whole sentence whose *next* sentence is the carve-out
still returns `VERIFIED`. Quoting the first sentence is verbatim and complete, and it is also a
common way a rule gets misrepresented. Flagging it needs a false-alarm rate measured on real
material first, so it is recorded rather than half-fixed.

## [0.8.0] - 2026-08-10

**One subcommand updates any install. Four extractor misses closed, one verifier trap closed.**

The subcommand `krokai upgrade` detects whether this install lives under `site-packages` (pip),
in a git clone, or a copied folder — and runs the right tool for each. On success it re-runs
`install-hooks` in the current matter so `settings.json` points at the freshly downloaded
scripts, and prints the top of this file so the reader knows what changed. `--dry-run` reports
what it WOULD run without touching anything. It never mutates a settings file for a matter it
cannot find (a `casefile.json` up the tree), and it never repairs a state it does not
understand — a git clone with local commits refuses `--ff-only` and says so.

The assistant-facing brief is updated: `INSTALL-FOR-AI.md` now has an "Updating an existing
install" section that documents the find-the-install chain (`pip show krokai` → the matter's
own `settings.json` → common paths → ask), what `upgrade` prints, and what the assistant
should REPORT at the end. The point of naming this in an assistant brief rather than a human
one is the same as everything else in that file: the failure mode "updated successfully" is
what the shipping toolkit exists to prevent one level down, and the update path does not get
to make the same mistake.

### Extractor: four measured misses closed, back-ported from the source project's hooks

Each was execution-verified in the source project; every one lands as a new self-test here, so
the guard cannot silently regress.

- **Multi-line blockquote paragraph.** A norm wrapped at fewer than 55 characters per line
  yielded ZERO candidates: measured on a four-line source, four lines, no matches. The new
  `_BLOCKQ_PARA_RE` joins consecutive `>` lines before the length gate. The paragraph pass
  runs first, so the single-line pass and the inline-quote pass are dedup'd against it.
- **Indented blockquote.** A blockquote inside a list (`   > ...`) was invisible; the regex
  anchored on `^>` at column zero only. Measured in the source project's own queue file: 77
  indented blockquotes, 39 of them inside the file the queue hook writes. The guard was blind
  to nearly half of its own history.
- **Line-wrapped straight quote.** A single `\n` inside `"…"` terminated the extraction; a
  paragraph break should terminate, a soft wrap should not. Execution proof: the same
  quotation, one line vs wrapped, previously exited 2 vs 0 through `quote_guard`.
- **Curly single quotes as delimiters.** `‘…’` produced zero candidates. ASCII `'` remains
  deliberately not a delimiter — it would match `student's` and manufacture a false quotation
  out of prose. The negative control is a self-test.

### Verifier: `word_diff` no longer promotes a stripped citation token to OPERATOR when it is an alignment artifact

`_STRIP` includes `(` and `)`, so `(b)(16)(i)` reaches `word_diff` as `b)(16)(i` — every
character is still correct, but the digit rule would then promote it to OPERATOR by shape.
The new `_CITE_TOKEN_RE` recognises the citation shape (whole or paren-stripped, always
requiring an internal `)(` structure) and the guard excludes a cite-shaped token from
OPERATOR only when the SAME token exists on the OTHER side — an alignment artifact, not a
real cite change. A real pincite change like `(b)(16)(i)` → `(b)(16)(ii)` still fires
OPERATOR, because the two tokens are not identical. Codex + Spark 11 + Spark 12 named the
earlier blanket guard as a regression (it demoted real pincite edits to ALTERED); this design
survives both tests and is locked in with self-tests, including counter-tests that
non-citation labels like `v1→v2`, `x64→x86`, `a1→a2`, `file1→file2` also stay OPERATOR.

`_STRIP` also gained the smart-quote set `«»‘’“”`, so a quote at a smart-quoted word boundary
strips cleanly rather than reaching the diff as an extra token.

### `krokai upgrade` — layout detection hardened

Panel-driven fixes to `upgrade.py`:

- **Editable installs are detected via PEP 610 `direct_url.json`** (the authoritative signal),
  not by looking for `site-packages` in the module path. An editable install (`pip install
  -e .`) resolves `krokai.__file__` to the source dir, not `site-packages` — the old check
  would have misdetected it as `git` and pulled the developer's own tree.
- **`site-packages` / `dist-packages` is now a path-COMPONENT check**, not a substring, so a
  folder called `my-site-packages-project` does not misdetect as pip.
- **`git` layout requires the `origin` remote to name `krokai-law`** before `git pull` runs.
  A copied krokai folder placed inside an unrelated user repo (Spark 11's dangerous case) now
  falls through to `copy` layout instead of `git pull`-ing the user's own tree.
- **`.git` FILE (git worktree / submodule) is recognised** alongside `.git` directory (Codex).
- **`git pull --ff-only` gets a preflight**: `git status --porcelain` + `git rev-list
  --left-right --count HEAD...@{u}` tell the user what specifically is wrong (dirty tree,
  local commits, diverged history) before touching the network. The bare git error is not
  the UX for an AI-assisted installer.
- **PEP 668 externally-managed** is handled: pip's non-zero exit prints the two safe options
  (`--user`, or a virtual environment) rather than a raw error.
- **`_refresh_hooks` runs in a fresh subprocess** via `sys.executable -m krokai install-hooks`
  so post-update hook logic runs from the NEWLY downloaded code, not the stale 0.x objects
  still cached in `sys.modules` from before the update. For 0.7.7→0.8.0 the shape is
  unchanged so it did not matter; for the first release that renames a hook or changes the
  settings shape it would have silently written a stale `settings.json`. Named by Codex +
  Spark 11 + Spark 12 + agy 36flash.

### Assistant brief: `INSTALL-FOR-AI.md#updating-an-existing-install`

The find-the-install ladder now leads with **PATH** (`command -v krokai` / `Get-Command
krokai`), then `pipx list`, `uv tool list`, `pip show`, the matter's `settings.json`, common
paths, ask. `pipx` and `uv tool` install isolated venvs that `pip show` in the outer
interpreter cannot see; the console-script entry point makes PATH the fastest and most
reliable rung. Missing PATH-first was Codex + Spark 11 + Spark 12 finding.

### Self-test: 427 → **460**

Every new capability and every panel finding lands as a new test.

- `suite_bank`: 5 extractor cases + 1 negative control (ASCII apostrophe is not a delimiter).
- `suite_word_diff`: 2 cite-guard cases + 4 non-citation label counter-tests
  (`v1→v2`, `x64→x86`, `a1→a2`, `file1→file2` all still fire OPERATOR).
- `suite_upgrade` (NEW): 17 tests covering `detect_layout` shape, `_editable_source_dir`,
  `_has_git_meta` for both directory and worktree file forms, `_remote_names_krokai`
  negative case, `_top_changelog_from_text` extraction and boundary, cite-regex control set,
  and an out-of-process `krokai upgrade --dry-run` smoke that asserts the report signature
  and that the word "successfully" never appears.

The clone suite runs 460/460; the `installed` CI job runs the same suite on the wheel and
skips 3 repo-hygiene suites that only make sense in a checkout.

## [0.7.7] - 2026-08-07

**A bare `pip install krokai` read a PDF as "" and reported the document as checked.**

0.7.6 shipped with `dependencies = []`, on the reasoning that every third-party import here already
sits in a `try/except` with a working degraded path, so a hard requirement would break exactly the
locked-down machines this tool is aimed at. The reasoning about *installability* was right. The
conclusion that it was therefore safe was wrong, and two independent external reviewers said so in
the same round.

Measured on the published 0.7.6 wheel in an empty virtualenv, before the fix:

    read_pdf(sample.pdf)   -> ''
    read_docx(sample.docx) -> ''
    read_any(sample.pdf)   -> ''

No error. No warning. The checker then saw an empty document and reported zero quotations found,
which is indistinguishable from a clean bill of health. **That is the same shape as the packs
defect fixed in 0.7.5, one layer up: a tool that succeeds at nothing is worse than one that fails,
because nobody investigates a clean report.** In a product whose entire premise is "a grounded
citation does not prove the quote is real", shipping a silent no-op is the worst available bug.

The cause was `except Exception`, which swallows `ImportError` next to a corrupt file. The
distinction is now drawn at the import rather than at the result, because an empty text layer is a
real and common answer - a scanned statute genuinely reads as "" - and must not become an error.

- New `krokai.readers.MissingReader`, raised when a file's FORMAT needs an engine that is absent.
  The message says what did NOT happen ("nothing was examined", not "nothing was found") and names
  the exact command: `pip install "krokai[pdf]"`.
- Six regression tests, including the control that matters: with the engines present, an unreadable
  PDF must still return "" and must NOT raise, or every scanned statute in a corpus becomes a crash.

`dependencies = []` stays. Optional was never the problem; silent was.

## [0.7.6] - 2026-08-07

**The git tag did not point at the commit PyPI actually published, in a project about provenance.**

0.7.5 went out mid-sequence: the tag was pushed, the publish workflow uploaded, and only then did
the self-test catch that the new CHANGELOG heading used `## 0.7.5` while the version-agreement
check reads the Keep a Changelog form `^## \[([0-9][^\]]*)\]`. The heading was fixed and the tag
moved - but a PyPI version can never be re-uploaded, so the second publish run returned
`400 Bad Request` and the artefact in the index stayed on the earlier commit.

The difference was exactly one line, in a changelog heading, verified with
`git diff --stat 26dda3d de3dd45`. Nothing about the code differed. It would have been reasonable
to leave it.

It is fixed anyway, because "the tag names something other than what shipped" is the precise
failure this toolkit exists to catch one level down, and a rule you suspend for yourself when the
discrepancy is small is not a rule. 0.7.6 is 0.7.5 plus the heading, published from the commit its
tag names.

Worth keeping: PyPI's own Sigstore attestation binds the upload to a commit, so the ground truth
was public and immutable the whole time regardless of what the git tag claimed.

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
