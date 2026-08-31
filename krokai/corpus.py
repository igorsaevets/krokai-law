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

# 🔴 `.docx` was missing here until 2026-08-03, and `read_any` had dispatched it the whole time.
# So `read_docx` existed, was tested, carried a long docstring about the tables the popular
# one-liner drops - and no `.docx` in a sources folder was ever opened, because `walk()` never
# yielded one. A quotation from a decision saved as Word came back NOT_FOUND, which is this tool's
# fabrication signal. Found by a reviewer noticing that the two tuples below disagreed.
DEFAULT_EXT = (".txt", ".xml", ".md", ".html", ".htm", ".pdf", ".docx", ".doc")

# Formats whose text is EXTRACTED by an engine that can fail. For these, and only these, a very
# short result means the extraction failed rather than that the document is short. The rest of
# DEFAULT_EXT is already text and is taken at whatever length it has.
EXTRACTED_EXT = (".pdf", ".docx", ".doc")


def _extracted_format(path):
    return path.lower().endswith(EXTRACTED_EXT)


# 🔴 THE SIGNAL WAS NEVER LENGTH. IT WAS ALWAYS "DID THE DOWNLOAD FAIL".
#
# 0.6.0 stopped excluding short text sources, because a real savings clause is 71 characters and
# throwing it out made a correct quotation of it come back NOT_FOUND - this tool's fabrication
# signal. An outside reviewer immediately named the other side of that trade: a scraped
# `404 Not Found` page is also short, and indexing it means a phrase from the placeholder now
# VERIFIES. Reproduced here on 2026-08-05 - `check()` returned VERIFIED citing the placeholder.
#
# Both halves are true, so the answer is neither of the two obvious ones. Length was only ever a
# proxy for "this file is not the chapter you think you downloaded", and the thing itself is
# readable: a failed download SAYS what it is. So the test is on the CONTENT - the same principle
# that decides derived files here, and for the same reason: a rule on a file's size or its name is
# a rule about the wrong thing.
#
# Deliberately narrow. Each entry is a server or a bot wall talking, not a phrase of English that a
# statute could contain.
#
# 🔴 THIS COMMENT USED TO SAY "the test applies ONLY to sources already under the floor - so a long
# document discussing 'access denied' is untouched". That stopped being true in 0.7.1, which moved
# the call out of the length branch on purpose, and the sentence stayed - describing a safety
# property the code no longer had, in the file a reader consults to find out whether it does. The
# negative controls it cited still passed, because they exercise TIER 2, which really is bounded.
# A stale comment is not a documentation defect when it is the thing that stops you re-checking.
# TIER 1 - fires wherever it appears in a document small enough to BE an error page, and above that
# size needs a second, distinct tier-1 string. The bound lives in `looks_like_placeholder`.
_PLACEHOLDER_RE = re.compile(
    r"(?i)(?:\b40[0-9]\s+(?:not\s+found|forbidden|bad\s+request|unauthorized)\b"
    r"|\b50[0-9]\s+(?:internal\s+server\s+error|service\s+unavailable|bad\s+gateway)\b"
    r"|\bthe\s+requested\s+(?:url|page|resource)\b[^.]{0,80}?\b(?:was\s+)?not\s+(?:be\s+)?found\b"
    r"|\byou\s+(?:do\s+not|don't)\s+have\s+permission\s+to\s+(?:access|view|open|see)\b"
    r"|\benable\s+javascript\b|\bjavascript\s+is\s+(?:required|disabled)\b"
    r"|\bjust\s+a\s+moment\b|\bchecking\s+your\s+browser\b"
    r"|\bverify\s+you\s+are\s+(?:a\s+)?human\b|\bare\s+you\s+a\s+robot\b"
    r"|\bunusual\s+traffic\b|\brate\s*limit\s+exceeded\b"
    r"|\bloading\s+document\b|\bplease\s+wait\s+while\b|\bthis\s+page\s+has\s+moved\b)")

# 🔴 TIER 2 - ordinary English that a short provision can legitimately contain. `access denied` is
# the phrase a due-process argument is built out of, and this project's own negative control caught
# tier 1 firing on exactly that sentence: "the applicant was denied access to the record and now
# argues that access denied in these circumstances violates due process". Excluding that file drops
# a real provision from the corpus, so a correct quotation of it comes back NOT_FOUND - which is
# this tool's fabrication signal. A false positive here is more expensive than a miss, so these
# fire only when the phrase IS essentially the whole file, which is what an error page looks like
# and what a sentence of law never does.
_AMBIGUOUS_RE = re.compile(r"(?i)\b(?:access\s+denied|permission\s+denied|page\s+not\s+found"
                           r"|not\s+found|forbidden|unauthorized)\b")
_AMBIGUOUS_MAX = 60

# 🔴 The size above which a document is no longer plausibly an error page. The largest bot wall
# this project has measured was 900 characters of extracted text; 4 000 is deliberately generous.
# Above it a single tier-1 phrase is a PHRASE, not a verdict - see `looks_like_placeholder`.
_PLACEHOLDER_MAX = 4000


def looks_like_placeholder(text):
    """True when a file is a failed download rather than a provision.

    Exported because the fetch layer asks the same question about bytes that have just arrived: a
    server can return HTTP 200 with a body that says 404, and saving that into the library is how a
    topic gets counted as covered while the chapter is missing.

    🔴🔴 THE PREVIOUS VERSION OF THIS FUNCTION DELETED REAL LAW FROM THE CORPUS, AND THE FIX THAT
    CAUSED IT WAS THE FIX FOR THE OPPOSITE BUG. 0.7.1 moved the call out of the `< MIN_TEXT_LAYER`
    branch so a 900-character bot wall could be caught - correct, and it left tier 1 firing at every
    length. Measured 2026-08-05: 9 920 characters of 8 U.S.C. 1255 plus one scraped footer line
    reading "Please enable JavaScript to use this site" excluded the ENTIRE document, so every
    correct quotation of that statute would come back NOT_FOUND, which is this tool's accusation
    that the drafter invented it. A scraped `.gov` page keeping a noscript footer is the ordinary
    case, not a contrived one. Found by a reviewer that read the widened call site and asked what
    ELSE now reaches it - the question the fix's own author did not ask.

    So: a tier-1 string fires anywhere in a document small enough to BE an error page, and above
    that size it needs corroboration - two distinct tier-1 strings. A real interstitial says
    "just a moment" AND "checking your browser" AND "enable javascript"; a statute that happens to
    contain one such phrase says it once.
    """
    t = (text or "").strip()
    hits = {m.group(0).lower() for m in _PLACEHOLDER_RE.finditer(t)}
    if hits and (len(t) <= _PLACEHOLDER_MAX or len(hits) >= 2):
        return True
    return len(t) <= _AMBIGUOUS_MAX and bool(_AMBIGUOUS_RE.search(t))


def walk_error(err):
    """`os.walk` swallows an unreadable directory SILENTLY unless told otherwise (R76, #324):
    a permissions error on one folder removed its whole subtree from the corpus with no
    printed sign, and a source that is not indexed produces NOT_FOUND - the fabrication
    signal - for honest quotations. Loud, never fatal: one bad directory must not kill a
    scan. Shared by every walker in the package."""
    print("  !! unreadable directory: %s (%s)"
          % (getattr(err, "filename", None) or "?", getattr(err, "strerror", None) or err))


def walk(roots, exts, skip_dirs=()):
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=walk_error):
            # sorted: the corpus index order - and therefore which duplicate a global search
            # hits FIRST - must not depend on the filesystem's mood (R76, #324 second half).
            dirnames[:] = sorted(d for d in dirnames
                                 if d not in skip_dirs and not d.startswith("."))
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
                 skip_dirs=(), cache_dir=None, quiet=False, sentinel=None,
                 superseded=()):
        self.paths, self.starts, self.astarts, self.hstarts = [], [], [], []
        self.excluded_derived, self.excluded_stub, self.unreadable = [], [], []
        self.excluded_empty, self.short_sources = [], []
        self.excluded_placeholder = []
        # Paths the law register knows to have been replaced by a newer edition of the same
        # provision. They stay INDEXED on purpose - the words really are in a source on this
        # disk, and pretending otherwise would produce a NOT_FOUND, which in this tool's
        # vocabulary accuses the drafter of inventing it. What changes is the verdict.
        self.superseded = {os.path.normcase(os.path.abspath(p)) for p in (superseded or ())}
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
            # 🔴 THE FLOOR APPLIES ONLY WHERE IT MEANS WHAT IT SAYS.
            #
            # `MIN_TEXT_LAYER` answers one question: *did the extraction fail?* That question
            # exists for a PDF or a DOCX, where 40 characters out of a 20-page document means the
            # text layer is a scan and needs OCR. It does not exist for a `.txt` or a `.md`: those
            # are exactly as long as they are, and plenty of real law is short - a definition, a
            # savings clause, a one-paragraph proclamation, a two-sentence policy update.
            #
            # Applied to every format alike, the floor threw a perfectly readable 71-character
            # provision out of the corpus and then advised the user to OCR it. A correct quotation
            # of that provision came back NOT FOUND, which in this tool's vocabulary is the
            # fabrication signal. **The check that exists to catch invented law was reporting real
            # law as invented**, with a diagnosis that could not be acted on.
            #
            # Found the way these things are found: a test fixture of mine fell under the floor
            # twice in two rounds. The first time I lengthened the fixture. The second time I asked
            # why the floor was there - and a trap that catches the author of the tests twice is a
            # defect in the tool, not in the tests.
            # 🔴 And the fix is NOT "drop the floor for text". Two useful signals were riding on
            # one test and the merge cost the more important one:
            #   * "your extraction failed, OCR it"      - must EXCLUDE: the text is not there.
            #   * "this looks like a downloaded placeholder rather than the real chapter"
            #                                            - must WARN AND INDEX: it may equally be
            #                                              a real short provision, and excluding it
            #                                              makes a correct quotation unverifiable.
            # Excluding on the second signal is how a true statement about a placeholder became a
            # false statement about a savings clause.
            if _extracted_format(p):
                if len(t.strip()) < MIN_TEXT_LAYER:
                    self.excluded_stub.append(p)
                    continue
            elif not t.strip():
                # A plain-text source is indexed whatever its length; only a genuinely EMPTY one is
                # excluded, and it gets its own bucket so the advice printed is the true advice.
                self.excluded_empty.append(p)
                continue
            elif len(t.strip()) < MIN_TEXT_LAYER:
                self.short_sources.append(p)         # warned below, and indexed all the same
            # 🔴 THE PLACEHOLDER TEST RUNS ON EVERY TEXT SOURCE, NOT ONLY SHORT ONES.
            #
            # It used to sit inside the `< MIN_TEXT_LAYER` branch, so the tier-1 strings that
            # `looks_like_placeholder` documents as firing "wherever they appear" could not
            # fire anywhere except in a file under 200 characters. The comment and the call
            # site contradicted each other and the dangerous direction was the live one:
            # measured 2026-08-05, a 900-character bot wall was indexed as primary law and
            # "Checking your browser before accessing the site" came back VERIFIED. A modern
            # interstitial is tens of kilobytes; the length gate excluded exactly the ones
            # that matter. Found by an outside reviewer reading the call site rather than the
            # function - which is where the two disagreed.
            if looks_like_placeholder(t):
                self.excluded_placeholder.append(p)
                if p in self.short_sources:
                    self.short_sources.remove(p)
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
        if self.excluded_empty:
            # A separate bucket with separate advice. Telling someone to OCR a `.md` file is worse
            # than saying nothing: it is a diagnosis they cannot act on, for a cause that is not
            # theirs, and it sends them away from the real one.
            print("  EMPTY source file (no text at all) - %d:" % len(self.excluded_empty))
            for p in self.excluded_empty:
                print("     %s" % p)
            print("     These are empty, not unreadable - a failed download or a placeholder. "
                  "Re-fetch them; no OCR will help.")
        if self.excluded_placeholder:
            # Its own bucket and its own advice. This is neither "OCR it" nor "it is short": the
            # download did not bring back the document, and the fix is to fetch it again - very
            # often from a different URL, because a server that answers with a bot wall will keep
            # answering with one.
            print("  FAILED DOWNLOAD - the file says so itself (not the chapter) - %d:"
                  % len(self.excluded_placeholder))
            for p in self.excluded_placeholder:
                print("     %s" % p)
            print("     A server error page, a bot wall or a loading stub was saved instead of the "
                  "text. NOT indexed: a phrase from it would otherwise verify as law. Re-fetch it, "
                  "and open the file once to see what came back.")
        if self.short_sources:
            print("  SHORT text source (INDEXED, but check it) - %d:" % len(self.short_sources))
            for p in self.short_sources:
                print("     %s" % p)
            print("     Under %d characters. Either a real short provision - a definition, a "
                  "savings clause - or a placeholder you downloaded instead of the chapter. "
                  "It IS searchable either way; open it and decide." % MIN_TEXT_LAYER)
        for p, err in self.unreadable:
            print("  !! unreadable: %s (%s)" % (p, err))

    def is_superseded(self, path):
        return bool(path) and os.path.normcase(os.path.abspath(path)) in self.superseded

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
