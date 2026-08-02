# -*- coding: utf-8 -*-
"""The corpus: every primary source you have on disk, indexed for exact search.

🔴🔴 THE ONE RULE THAT MAKES THIS TOOL MEAN ANYTHING
----------------------------------------------------
**The corpus contains primary sources and nothing else.**

Break it and the tool keeps running, keeps printing numbers, and the numbers become flattery. A
quotation copied from your own memo into your own brief will "verify" - against your own memo. A
mistake made once **validates itself** forever after.

Measured, twice, in opposite directions:

* One analytical file had been filed inside a statutes directory. Quotations copied out of it
  verified against it. The score came out 87.2 % where the honest figure was 75.6 %.
* Nobody had checked the other side. The tool's **own archived report** had been filed into the
  drafts directory, so it was re-verifying its own output: **1 443 of 1 606 misses came from that
  single file.**

So: files are screened per FILE, not per directory, and every exclusion is printed. A wrongly
excluded statute must be visible immediately, not discovered three rounds later.
"""
from __future__ import annotations

import bisect
import os
import re

from .normalize import alnum, dehyph
from .readers import corpus_text, MIN_TEXT_LAYER

__all__ = ["Corpus", "walk"]

# A file sitting in a sources directory that is OUR analysis rather than a primary source. The rule
# used to live on the directory; it belongs on the file.
DERIVED_DEFAULT = (r"ANALYSIS|SUMMARY|DIGEST|NOTES?|OUTLINE|CHECKLIST|STRATEG|MEMO|BRIEF|REVIEW|"
                   r"DRAFT|REPORT|OUR-|РАЗБОР|АНАЛИЗ|ВЫПИСКА|СВОДКА|ЗАМЕТ|конспект|ЧЕК-ЛИСТ|"
                   r"СТРАТЕГИ|ПРОВЕРКА|ИТОГ|отч[её]т|бриф|рецензи|наш[аи]?-")

DEFAULT_EXT = (".txt", ".xml", ".md", ".html", ".htm", ".pdf")


def walk(roots, exts, skip_dirs=()):
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames
                           if d not in skip_dirs and not d.startswith(".")]
            for fn in sorted(filenames):
                if fn.startswith("~$") or not fn.lower().endswith(exts):
                    continue
                p = os.path.join(dirpath, fn)
                k = os.path.normcase(os.path.abspath(p))
                if k not in seen:
                    seen.add(k)
                    yield p


class Corpus(object):
    """Three parallel indexes over the same documents, so a near-miss can be classified.

    * ``joined``  - normalised text. The exact index.
    * ``ajoined`` - letters and digits only. Answers *"same words, punctuation drifted"*.
    * ``hjoined`` - hyphens healed. Answers *"the SOURCE is line-broken, our quotation is fine"*.

    All three are one big string per index with a ``\\x00`` separator between documents, and file
    ownership is recovered by bisecting the offset table. ``\\x00`` is not alphanumeric and appears
    in no real document, so a match can never straddle two files - which would invent a sentence
    that exists in neither.
    """

    SEP = "\n\x00\n"

    def __init__(self, roots, exts=DEFAULT_EXT, derived_re=DERIVED_DEFAULT,
                 skip_dirs=(), cache_dir=None, quiet=False, sentinel=None):
        self.paths, self.starts, self.astarts, self.hstarts = [], [], [], []
        self.excluded_derived, self.excluded_stub, self.unreadable = [], [], []
        drx = re.compile(derived_re, re.I) if derived_re else None
        # One string or several. Several, because a renamed tool must still recognise the stamp it
        # wrote under its old name - see the note beside SENTINELS in run.py.
        sents = (sentinel,) if isinstance(sentinel, str) else tuple(sentinel or ())

        buf, abuf, hbuf = [], [], []
        pos = apos = hpos = 0
        for p in walk(roots, exts, skip_dirs):
            if drx and drx.search(os.path.basename(p)):
                self.excluded_derived.append(p)
                continue
            try:
                t = corpus_text(p, cache_dir)
            except Exception as exc:
                self.unreadable.append((p, type(exc).__name__))
                continue
            if any(s in t[:400] for s in sents):
                self.excluded_derived.append(p)      # stamped as this toolkit's own output
                continue
            if len(t.strip()) < MIN_TEXT_LAYER:
                # A scan without OCR, or a stub page. Reported, never silently indexed as empty:
                # a quotation from such a file produces a NOT FOUND that blames the quotation.
                self.excluded_stub.append(p)
                continue
            at, ht = alnum(t), dehyph(t)
            self.paths.append(p)
            self.starts.append(pos)
            self.astarts.append(apos)
            self.hstarts.append(hpos)
            buf.append(t)
            abuf.append(at)
            hbuf.append(ht)
            pos += len(t) + len(self.SEP)
            apos += len(at) + 1
            hpos += len(ht) + len(self.SEP)

        self.texts = buf
        self.joined = self.SEP.join(buf)
        self.ajoined = "\x00".join(abuf)
        self.hjoined = self.SEP.join(hbuf)
        self.ends = [s + len(t) for s, t in zip(self.starts, self.texts)]
        self._index_of = {p: i for i, p in enumerate(self.paths)}
        if not quiet:
            self.print_build()

    # -- reporting ------------------------------------------------------------------------------
    def print_build(self):
        print("corpus: %d files, %.1f MB of text" % (len(self.paths), len(self.joined) / 1e6))
        if self.excluded_derived:
            print("  EXCLUDED as derived (our own writing inside a sources directory) - %d:"
                  % len(self.excluded_derived))
            for p in self.excluded_derived:
                print("     %s" % p)
            print("     (if a primary source is in this list, fix the pattern - do not stay silent)")
        if self.excluded_stub:
            print("  NO TEXT LAYER (scan without OCR, or a stub) - %d:" % len(self.excluded_stub))
            for p in self.excluded_stub:
                print("     %s" % p)
            print("     A quotation from these produces a FALSE miss. OCR them with a real OCR "
                  "engine - never by asking a language model to read the image.")
        for p, err in self.unreadable:
            print("  !! unreadable: %s (%s)" % (p, err))

    # -- lookup ---------------------------------------------------------------------------------
    def _owner(self, i):
        return self.paths[bisect.bisect_right(self.starts, i) - 1]

    def find(self, needle):
        i = self.joined.find(needle)
        return None if i < 0 else self._owner(i)

    def find_pos(self, needle):
        i = self.joined.find(needle)
        return (None, -1) if i < 0 else (self._owner(i), i)

    def find_all_pos(self, needle, cap=40):
        """EVERY occurrence, not just the first.

        A single sentence can sit in three different Federal Register preambles. Asking *"what
        follows this quotation"* only at the first hit answers the question about the wrong copy.
        """
        out, i = [], self.joined.find(needle)
        while i >= 0 and len(out) < cap:
            out.append((self._owner(i), i))
            i = self.joined.find(needle, i + 1)
        return out

    def find_alnum(self, needle):
        i = self.ajoined.find(needle)
        return None if i < 0 else self.paths[bisect.bisect_right(self.astarts, i) - 1]

    def find_hyph(self, needle):
        i = self.hjoined.find(needle)
        return None if i < 0 else self.paths[bisect.bisect_right(self.hstarts, i) - 1]

    def all_in_order(self, parts):
        """Is there ONE file holding every fragment, in order, without overlap?

        Three defects lived in the obvious version of this function:

        1. 🔴 **One document, not "the corpus".** Searching each fragment across the whole corpus and
           calling it a match welds two unrelated authorities into a sentence that exists in neither.

        2. 🔴 **The first occurrence is the wrong occurrence.** ``str.find`` returns the earliest
           hit anywhere, and one provision is quoted in several preambles, so the earliest hits of
           different fragments legitimately land in different files. Measured cost of getting this
           wrong: **26 false accusations against 4 real ones.** The correct test is *"is there at
           least one document where all fragments appear in order"*.

        3. 🔴 **Non-overlapping.** Advancing the cursor by one character let fragment N+1 start
           *inside* fragment N and still count as "after" it. Measured impact on the corpus at the
           time: zero cases - which is exactly why it had to be fixed then, rather than after it
           mattered.

        Returns `(path, [offsets])`, choosing the placement with the smallest total gap so that
        "what the ellipsis hides" describes the passage actually meant.
        """
        best = (None, None, None)
        if not parts:
            return None, None
        for path, txt in zip(self.paths, self.texts):
            start = -1
            for _ in range(200):
                s0 = txt.find(parts[0], start + 1)
                if s0 < 0:
                    break
                start = s0
                cur, offs, ok = s0 + len(parts[0]) - 1, [s0], True
                for p in parts[1:]:
                    i = txt.find(p, cur + 1)
                    if i < 0:
                        ok = False
                        break
                    offs.append(i)
                    cur = i + len(p) - 1
                if not ok:
                    continue
                gap = sum(offs[k + 1] - (offs[k] + len(parts[k])) for k in range(len(parts) - 1))
                if best[0] is None or gap < best[2]:
                    best = (path, offs, gap)
            if best[0] is not None and best[2] == 0:
                break                                  # contiguous: cannot do better
        return best[0], best[1]

    # -- context --------------------------------------------------------------------------------
    def window(self, path, offset, span, before=120, after=220):
        """🔴 Both ends are clamped to the FILE. An earlier version clamped only the low end, so a
        window near the end of a document ran past the separator and quoted the *next* document as
        though it belonged to this one. Confirmed by execution, not by reading."""
        k = self._index_of[path]
        lo = max(self.starts[k], offset - before)
        hi = min(self.ends[k], offset + span + after)
        return self.joined[lo:hi]

    def after(self, path, offset, span, n=260):
        k = self._index_of[path]
        lo = offset + span
        return self.joined[lo: min(self.ends[k], lo + n)]

    def before(self, path, offset, n=220):
        k = self._index_of[path]
        return self.joined[max(self.starts[k], offset - n): offset]

    def text_of(self, path):
        return self.texts[self._index_of[path]]

    def gaps(self, path, parts, offs):
        """What the ellipses actually hide, in the source's own words."""
        txt = self.text_of(path)
        out = []
        for k in range(len(parts) - 1):
            a = offs[k] + len(parts[k])
            b = offs[k + 1]
            if b > a:
                out.append(" ".join(txt[a:b].split()))
        return out
