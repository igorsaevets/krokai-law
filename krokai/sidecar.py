# -*- coding: utf-8 -*-
"""PDF sidecars: making your own grep stop lying to you.

THE MEASUREMENT THAT PRODUCED THIS
-----------------------------------
A phrase known to be the *title* of an agency memorandum:

    · extracted from the PDF's text layer by a PDF library  -> FOUND
    · searched for with ripgrep across the whole folder     -> found ONLY in .md files, never in the PDF

Your grep tool does not read PDFs. In the corpus where this was measured that meant **67 files,
35 % of the law library, invisible to search**.

That is worse than an inconvenience, because of a rule that every careful research process has:
*a zero result is an assertion, not a fact.* For every provision that lived only inside a PDF,
"I searched and found nothing" had been a **false negative all along**, and there was nothing in
the process that could have noticed.

WHAT THIS DOES NOT FIX
----------------------
The checker reads PDFs directly and always did. Sidecars are not for the checker. They are for
**grep, for your editor's search, and for the AI reading your folder** - all of which are blind to
a PDF and none of which say so.

WHY A NEIGHBOUR FILE AND NOT A REPLACEMENT
-------------------------------------------
The PDF stays the primary source: page breaks, signatures and the exact layout the agency published
exist only there. The sidecar is a derivative and says so in its own header, in the file, so it can
never be quoted *instead of* the original by someone who opened the wrong one. Duplication is the
deliberate price - a few megabytes of text against false negatives in legal research.
"""
from __future__ import annotations

import io
import os
import time

from .corpus import walk
from .normalize import strip_invisibles
from .readers import read_pdf, MIN_TEXT_LAYER, EXTRACTOR_VERSION

__all__ = ["build", "SUFFIX"]

SUFFIX = ".text.md"

# 🔴🔴 THE SIDECAR MUST DECLARE ITSELF AS THIS TOOLKIT'S OUTPUT, OR IT BECOMES A PRIMARY SOURCE.
#
# Measured 2026-08-05: with the header below lacking the sentinel, `krokai sidecar` wrote a `.md`
# next to every PDF *inside a sources directory*, `Corpus` walked `.md`, the derived-name pattern
# matched nothing in `8CFR-245.text.md`, and the file was indexed as primary law. Two things
# followed, and the second is the serious one:
#
#   * the corpus doubled and the report's "primary sources only - N files" became untrue;
#   * the warning text of this very header verified as law. `check()` returned a CLEAN verdict for
#     "Page breaks, signatures and exact layout exist only there", citing the sidecar as its source.
#
# The sister project measured the same shape at scale before this was written down: 66 of its 269
# corpus files were its own sidecars, and a phrase that appears in no PDF anywhere verified against
# one. The mechanism that prevents it already existed here - `run.SENTINEL`, honoured by
# `Corpus(sentinel=...)` - and had simply never been applied to the one generator that writes into
# the library. The cure was sitting next to the disease.
#
# 🔴 It is a stamp in the CONTENT, never a rule about the name or the extension. The sister project
# proved that direction too: adding `.text.md` to a name-based exclusion pattern would have thrown
# out two genuine downloaded decisions that happen to use the same extension.
_SENTINEL = "KROKAI-TOOL-OUTPUT"

HEADER = """---
derived: true
source: {src}
extracted: {when}
tool: krokai sidecar
extractor: {extractor}
---

<!-- %s : an extracted text layer written by `krokai sidecar`. NOT a primary source. Quotations
     found in this file must never be counted as verified against the law. -->

> ⚠️ **THIS IS AN EXTRACTED TEXT LAYER, NOT THE PRIMARY SOURCE.** It exists so that grep, your
> editor and any AI reading this folder can see inside the PDF - measured: ripgrep does not find a
> phrase in a PDF even when the phrase is demonstrably in its text layer.
>
> **Quote and verify against the original,** `{srcname}`. Page breaks, signatures and exact layout
> exist only there. Rebuild with `krokai sidecar`.

---

""" % _SENTINEL


def _current(dst, src):
    """Is an existing sidecar still current?

    🔴 The extractor's version is part of the question, and leaving it out makes a repair
    invisible. The test used to be `mtime(dst) >= mtime(src)` alone. A downloaded statute never
    changes, so improving `read_pdf` - fixing a soft hyphen, dropping a signature blob - would
    have left every sidecar on disk exactly as wrong as before, with the suite green and the
    changelog claiming the fix. The sister project measured this compounding pair: a defect that
    corrupts, plus a freshness key that cannot see the repair. Its header printed the engine
    version too, and never compared it back.
    """
    if not os.path.exists(dst):
        return False
    if os.path.getmtime(dst) < os.path.getmtime(src):
        return False
    try:
        head = io.open(dst, encoding="utf-8", errors="replace").read(400)
    except OSError:
        return False
    return ("extractor: %s" % EXTRACTOR_VERSION) in head


def build(source_dirs, force=False, dry_run=False, cache_dir=None, printer=print):
    """Write `<name>.text.md` next to every PDF that has a usable text layer.

    Returns `(made, skipped, no_text_layer, failed)`.
    """
    made = skipped = failed = 0
    no_layer = []
    for src in walk(source_dirs, (".pdf",)):
        dst = src[:-4] + SUFFIX
        if not force and _current(dst, src):
            skipped += 1
            continue
        try:
            # 🔴 The invisible characters come out, and nothing else does. This file is written to
            # be SEARCHED; a soft hyphen renders as nothing and silently defeats every search for
            # the word it sits inside. Full normalisation is deliberately not applied - it would
            # collapse the line structure, and a sidecar nobody can read is a sidecar nobody checks
            # the original against.
            text = strip_invisibles(read_pdf(src, cache_dir))
        except Exception as exc:
            failed += 1
            printer("  FAILED  %s :: %s" % (os.path.basename(src)[:70], type(exc).__name__))
            continue
        if len(text.strip()) < MIN_TEXT_LAYER:
            no_layer.append(src)
            continue
        if dry_run:
            made += 1
            continue
        body = HEADER.format(src=os.path.basename(src), srcname=os.path.basename(src),
                             when=time.strftime("%Y-%m-%d"),
                             extractor=EXTRACTOR_VERSION) + text
        io.open(dst, "w", encoding="utf-8", newline="\n").write(body)
        made += 1
        printer("  %8d chars  %s" % (len(text), os.path.basename(src)[:66]))

    printer("\nsidecars: %d written · %d already current · %d without a text layer · %d failed"
            % (made, skipped, len(no_layer), failed))
    if no_layer:
        # 🔴 Handed to the human, never solved by a model. A language model transcribing a scanned
        # image produces plausible text; plausible text becomes a quotation; the quotation is then
        # treated as the primary source. The contamination is silent and it lands in the one
        # artefact this whole toolkit exists to keep clean.
        printer("\n🔴 NO TEXT LAYER - run these through a real OCR engine yourself.")
        printer("   Do NOT ask a language model to read the scan. It will produce plausible text, "
                "and plausible text in a quotation is exactly the failure being prevented here.")
        for p in no_layer:
            printer("     %s" % p)
    return made, skipped, no_layer, failed
