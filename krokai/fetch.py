# -*- coding: utf-8 -*-
"""Getting the text of the law onto your disk - deterministically, and noticing when it changes.

🔴🔴 THE ONE RULE: NO LANGUAGE MODEL MAY STAND BETWEEN THE SERVER AND THE FILE.
------------------------------------------------------------------------------
This is the rule the whole toolkit rests on, and it is easy to break by accident, because the most
convenient tools break it silently.

An assistant asked to "fetch this regulation" reaches for a web-fetch tool. Read that tool's own
description: it *converts the page to markdown and answers a prompt against it using a small fast
model*. What comes back is therefore **generated text about the page**, not a copy of the page. Save
it into the library and every quotation checked against it is being checked against a model's
paraphrase - while the report says `VERIFIED`. The failure is total and completely silent: the one
artefact this package exists to keep clean is the one that gets contaminated.

The prohibition is wider than one tool. Any route that carries the text through a context window is
the same defect, because from inside there is no way to tell copying from producing. `read_url`,
`scrape`, "summarise this page" - all of them end with the assistant *writing* the text out again.

So the only permitted path is:

    URL --(HTTP)--> bytes --(written unchanged)--> disk --(krokai's own readers)--> text

`requests` writes the response body to disk byte for byte. Extraction happens later, in `readers`,
from the file - the same deterministic code that reads every other source. Nothing in this module
produces a character of text.

🔴 WHY THE INBOX IS NOT THE LIBRARY
-----------------------------------
Downloads land in `.krokai/inbox/`, which is not a sources directory and is not walked by `Corpus`.
Nothing is a primary source because of where it came from; it becomes one when a person accepts it
with `krokai intake`. The sister project measured what the other arrangement costs: the folder WAS
the credential, so anything that reached a sources directory was treated as law, and 66 derived
files quietly became primary sources.

🔴 SILENCE IS NOT A PASS
------------------------
The lookalike test is a DETECTOR, not an allow-list. The sister project printed a green tick
whenever its typosquat detector stayed quiet - so `pastebin.com/raw/...` and `files.random-host.ru`
were written into the library under a "PRIMARY SOURCE" header and then verified against. A host
this tool knows nothing about is `unknown`, it says `unknown` in the file it writes, and it needs an
explicit flag. There are three answers here, not two.

🔴 A REVISION IS AN EVENT, NOT AN UPDATE
----------------------------------------
When the same provision comes back with different bytes, the old file is NOT overwritten. Agencies
re-issue text, and a quotation taken from last year's edition will not be found in this year's -
which this tool reports as `NOT_FOUND`, its fabrication signal. Measured in the sister project on
8 CFR 245, 2024 against 2026: 32 sentences gone, 29 new, and the systematic replacement of "alien"
with "noncitizen" throughout. Every banked quotation of that part would have turned red overnight,
correctly quoted and unverifiable, with nothing to distinguish it from an invention.

So a revision keeps both editions, writes the difference down, and re-checks every quotation in the
bank against the new text - because the answer to "did this break my work" is the only reason
anybody wants to know.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time

from .corpus import looks_like_placeholder
from .readers import MIN_TEXT_LAYER

__all__ = ["fetch_url", "intake", "trust_of", "INBOX", "REGISTRY", "sha256_of",
           "superseded_paths"]

INBOX = os.path.join(".krokai", "inbox")
REGISTRY = os.path.join(".krokai", "law_registry.json")
REVISIONS = os.path.join(".krokai", "revisions")

# What each trust level means for what happens next. `unknown` is a level, not a hole: it is what a
# host nobody has vouched for gets, and it is the reason `--allow-unknown-source` exists.
TRUST = {
    "primary": ("OFFICIAL", "the publisher's own copy"),
    "snapshot": ("OFFICIAL BUT DATED", "an official codification, not necessarily the text in "
                                       "force today - check the effective date"),
    "nonauthoritative": ("SECONDARY", "a reputable mirror; useful, and not the authority"),
    "lookalike": ("REFUSED", "wears an official name or an official label without being on the "
                             "official list"),
    "unknown": ("UNKNOWN", "this tool knows nothing about this host - silence from the lookalike "
                           "test is not a vouch"),
}

_UA = "krokai-law (+https://github.com/igorsaevets/krokai-law) python-requests"
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sha256_of(data):
    return hashlib.sha256(data).hexdigest()


def trust_of(url, cfg=None, packs=None):
    """`(level, headline, why)` for a URL, using the same classifier the review layer uses.

    One implementation of "is this host official", shared with `krokai review`. A second copy would
    drift, and this package has measured that twice.
    """
    from .consult import classify_url
    primary = list(getattr(packs, "official_domains", None) or [])
    if cfg is not None:
        try:
            g = (cfg.get("grounding", {}) or {})
            primary += [str(x) for x in (g.get("primary") or [])]
        except Exception:
            pass
    g = {"primary": primary, "snapshot": ["/annual/", "govinfo.gov/content/pkg/cfr-"],
         "nonauthoritative": ["law.cornell.edu", "justia.com", "courtlistener.com", "casetext.com"]}
    kind = classify_url(url, g)
    if kind not in TRUST:
        kind = "unknown"
    head, why = TRUST[kind]
    return kind, head, why


def _name_from(url, ctype):
    """A filename that keeps its EXTENSION, because the extension is what selects the reader.

    🔴 The first version appended the query string after the whole basename, so the canonical eCFR
    URL - `.../title-8.xml?part=245` - became `title-8.xml-part-245`. That ends in nothing
    `read_any` recognises, so the XML tags were never stripped and `&#xA7;` was never unescaped:
    the part sign became `S` in the corpus while every quotation still said `§`. This module's own
    end-to-end test caught it, by producing quotations made of markup.

    The extension is a dispatch key here, not decoration. Query goes in the STEM.
    """
    from urllib.parse import urlsplit
    parts = urlsplit(url)
    base = os.path.basename(parts.path) or (parts.netloc or "download")
    stem, ext = os.path.splitext(base)
    if not ext:
        ext = {"application/pdf": ".pdf", "text/html": ".html", "text/plain": ".txt",
               "application/xml": ".xml", "text/xml": ".xml",
               "application/json": ".json"}.get(
                   (ctype or "").split(";")[0].strip().lower(), ".txt")
    if parts.query:
        stem += "-" + _SAFE.sub("-", parts.query)[:60]
    stem = _SAFE.sub("-", stem).strip("-") or "download"
    return (stem[:110] + ext)[:120]


def fetch_url(url, root, cfg=None, packs=None, allow_unknown=False, timeout=45, printer=print):
    """Download one URL into the inbox, byte for byte. Returns the meta dict, or None.

    Nothing here interprets, summarises or rewrites the body. The bytes that arrive are the bytes
    written.
    """
    # 🔴 THE REFUSAL COMES FIRST, BEFORE ANY DEPENDENCY CHECK.
    #
    # The first version imported `requests` at the top of this function and returned early when it
    # was missing. CI caught it on every runner - none of them has `requests` - and the failure is
    # not merely a test artefact: it meant that on a machine without the optional library, asking to
    # download from a typosquat produced "install requests" instead of "REFUSED, this host wears an
    # official name it is not entitled to". A safety decision that depends on whether an optional
    # dependency happens to be installed is not a safety decision. Classify, refuse, and only then
    # worry about whether the download is even possible.
    kind, head, why = trust_of(url, cfg, packs)
    printer("source: %-18s %s" % (head, why))
    if kind == "lookalike":
        printer("🔴 REFUSED before any request was made. This host wears an official name or an "
                "official label and is not on the official list.")
        printer("   There is no flag for this one. A typosquat serving plausible text is the "
                "single worst thing that can enter a law library: it verifies.")
        return None
    if kind == "unknown" and not allow_unknown:
        printer("🔴 STOPPED. This tool knows nothing about this host - which is NOT the same as it "
                "being fine.")
        printer("   The lookalike test staying quiet is a detector not firing, never a vouch. A "
                "sister project printed a green tick on exactly this and wrote a paste-site URL "
                "into its law library under a PRIMARY SOURCE header.")
        printer("   If you have looked at it and you are sure: --allow-unknown-source. The file "
                "will be stamped UNKNOWN either way.")
        return None

    try:
        import requests
    except ImportError:
        printer("`requests` is not installed, so nothing can be downloaded. `pip install requests` "
                "- it is the only network dependency in this package, on purpose.")
        return None

    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": _UA})
    except Exception as exc:
        printer("🔴 the request failed: %s: %s" % (type(exc).__name__, exc))
        return None

    final = r.url
    if final != url:
        # 🔴 Classify the destination as well as the request. A redirect is a change of publisher,
        # and checking only the URL you typed means the check is done on a host that never served
        # you anything. Named independently by two reviewers of the sister project's fetcher.
        fkind, fhead, fwhy = trust_of(final, cfg, packs)
        printer("redirected -> %s" % final)
        printer("destination: %-13s %s" % (fhead, fwhy))
        if fkind == "lookalike":
            printer("🔴 REFUSED: the redirect lands on a lookalike host. Nothing was saved.")
            return None
        if fkind == "unknown" and not allow_unknown:
            printer("🔴 STOPPED: the redirect lands on a host this tool knows nothing about.")
            return None
        kind, head, why = fkind, fhead, fwhy

    if r.status_code != 200:
        printer("🔴 HTTP %d - nothing saved." % r.status_code)
        return None

    data = r.content
    ctype = r.headers.get("Content-Type", "")

    # 🔴 A 200 IS NOT A DOCUMENT. Servers answer 200 with an error page, a bot wall or a loading
    # stub, and that body saved into the library counts the topic as covered while the chapter is
    # missing - the stub failure this package documents elsewhere, arriving through the front door.
    if not (ctype or "").lower().startswith("application/pdf"):
        probe = data[:4000].decode("utf-8", "replace")
        if looks_like_placeholder(probe) and len(data) < 20000:
            printer("🔴 HTTP 200, but the body says it is an error page, a bot wall or a loading "
                    "stub. Nothing saved.")
            printer("   %s" % " ".join(probe.split())[:160])
            return None
    if not data:
        printer("🔴 empty body - nothing saved.")
        return None

    inbox = os.path.join(root, INBOX)
    os.makedirs(inbox, exist_ok=True)
    name = _name_from(final, ctype)
    dest = os.path.join(inbox, name)
    n = 1
    while os.path.exists(dest):
        stem, ext = os.path.splitext(name)
        dest = os.path.join(inbox, "%s-%d%s" % (stem, n, ext))
        n += 1
    with open(dest, "wb") as fh:
        fh.write(data)

    meta = {
        "url": url,
        "final_url": final,
        "sha256": sha256_of(data),
        "bytes": len(data),
        "content_type": ctype,
        "http_status": r.status_code,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "trust": kind,
        "trust_label": head,
        # 🔴 Recorded in the file, not merely promised in a docstring. If this is ever false, every
        # verdict downstream of the file is worthless, so it is written where a human and a script
        # can both read it back.
        "model_in_path": False,
        "how": "requests.get -> bytes -> disk, unchanged",
    }
    io.open(dest + ".meta.json", "w", encoding="utf-8", newline="\n").write(
        json.dumps(meta, ensure_ascii=False, indent=2))
    printer("saved %d bytes -> %s" % (len(data), os.path.relpath(dest, root)))
    printer("sha256 %s" % meta["sha256"])
    printer("")
    printer("It is in the INBOX, which is not a sources directory and is not searched. Look at it, "
            "then:  krokai intake --address \"<citation>\"")
    return meta


# =================================================================================================
#  Intake: from the inbox into the library, with revisions
# =================================================================================================
def _registry(root):
    p = os.path.join(root, REGISTRY)
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {}


def _write_registry(root, reg):
    """Atomic. 🔴 `open(path, "w")` truncates BEFORE anything is written, so an interruption - or an
    exception while building the new content - leaves an empty register where the record of every
    downloaded source used to be. Found in the sister project's index writer by a reviewer."""
    p = os.path.join(root, REGISTRY)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        json.dumps(reg, ensure_ascii=False, indent=2, sort_keys=True))
    os.replace(tmp, p)


def superseded_paths(root):
    """Every file the register knows to have been replaced by a newer edition.

    🔴 Both editions stay on disk and both stay indexed, because a quotation taken from the
    older one WAS a correct quotation of the law in force at the time. What must change is the
    verdict, not the availability - and without this set the tool graded superseded law
    VERIFIED, which is the defect an outside reviewer found in the release that introduced
    revisions at all.
    """
    out = set()
    reg = _registry(root)
    path_to_entry = {e.get("path"): e for e in reg.values() if e.get("path")}
    for entry in reg.values():
        p = entry.get("supersedes")
        # `p not in out` handles both cycles and already-walked chains in O(1).
        while p and p not in out:
            out.add(p)
            prev = path_to_entry.get(p)
            p = prev.get("supersedes") if prev else None
    return out


def _sentences(t):
    """Sentences of NORMALISED text.

    🔴 Named independently by two review channels, which is the whole reason to ask more
    than one. The comparison used to run on raw `read_any` output, which carries line
    wrapping, smart quotes, non-breaking spaces and unescaped entities - and two extractions
    of the SAME provision differ in every one of them. So a re-download with no legal change
    produced a wall of gone/added pairs, and the revision report, whose entire job is to be
    believed, cried wolf.

    This package already holds the doctrine: normalisation may change whitespace,
    hyphenation and typography and may never change letters, digits or word order. The
    revision detector was the one place not applying it, and it was grading rendering as a
    change in the law.

    🔴 THE FLOOR WAS 25 CHARACTERS AND IT HID THE CHANGES MOST WORTH SEEING. All three channels of
    the round-21 review named it independently: `Section 4 is repealed.` is 22 characters, and so
    are a fee, a deadline and an effective date. An operative sentence is short precisely BECAUSE
    it is operative. Measured 2026-08-05: `_sentences("Section 4 is repealed.")` returned `[]`.

    The floor was there to drop the fragments left by splitting on the full stop inside `U.S.C.` or
    `Sec.`, so it is replaced by a test for what a fragment IS - no internal whitespace - plus a
    much lower floor. A noisier revision report is a cheap failure; a silent repeal is not.
    """
    from .normalize import normalise
    out = []
    for s in re.split(r"(?<=[.;:])\s+", normalise(t) or ""):
        s = s.strip()
        if len(s) > 10 and " " in s:
            out.append(s)
    return out


def revision_diff(old_text, new_text):
    """What actually changed, counted in SENTENCES rather than in diff lines.

    🔴 A unified diff over character chunks reports a chunk-boundary shift as a removal. The sister
    project's negative control failed on exactly that: a sentence it believed had vanished was
    present and intact, and only a set comparison over sentences showed the real change. A count
    that overstates deletions in a tool whose job is spotting deletions is worse than no count.

    🔴 A SET LOSES ORDER, AND ORDER IS OPERATIVE IN A STATUTE. Two channels put the same case:
    move a conditioning sentence from one subsection to another and `a - b` and `b - a` are both
    empty, so this reported `0 gone, 0 added, 100 % unchanged` - and `_bank_impact` agreed, because
    the sentence really is still somewhere in the file. Measured 2026-08-05 on two texts differing
    only in sentence order: similarity 1.00. The set comparison is kept, because it is what stops
    a chunk-boundary shift being reported as a deletion, and the order is reported ALONGSIDE it
    rather than folded into the similarity number: `moved` is a different question from `gone`.
    """
    ao, bo = _sentences(old_text), _sentences(new_text)
    a, b = set(ao), set(bo)
    gone, added = sorted(a - b), sorted(b - a)
    both = len(a & b)
    similarity = both / float(max(1, len(a | b)))
    # Of the sentences present in both, how many sit in a different position relative to the
    # others? Compared on the shared subsequence only, so an insertion elsewhere does not count
    # every following sentence as moved.
    shared_a = [s for s in ao if s in b]
    shared_b = [s for s in bo if s in a]
    moved = sum(1 for x, y in zip(shared_a, shared_b) if x != y)
    return {"gone": gone, "added": added, "kept": both, "similarity": similarity,
            "moved": moved}


def _address_keys(address, packs):
    return packs.keys(packs.find(address or "")) if packs else set()


def intake(root, cfg, packs, address=None, dest_dir=None, allow_unindexed=False, printer=print):
    """Move everything in the inbox into the library, keyed by its citation address.

    Returns a list of `(status, filename, note)`.
    """
    from .readers import read_any
    inbox = os.path.join(root, INBOX)
    if not os.path.isdir(inbox):
        printer("nothing in the inbox (%s does not exist yet)" % INBOX)
        return []

    files = [f for f in sorted(os.listdir(inbox)) if not f.endswith(".meta.json")]
    if not files:
        printer("the inbox is empty. `krokai fetch <url>` puts things in it.")
        return []

    reg = _registry(root)
    out = []
    library = dest_dir or (cfg.source_dirs[0] if cfg.source_dirs else root)
    os.makedirs(library, exist_ok=True)

    for fn in files:
        src = os.path.join(inbox, fn)
        try:
            meta = json.load(io.open(src + ".meta.json", encoding="utf-8"))
        except Exception:
            meta = {"sha256": sha256_of(open(src, "rb").read()), "trust": "unknown",
                    "trust_label": "UNKNOWN", "url": "", "model_in_path": None}

        if meta.get("model_in_path"):
            # There is no flag for this. A file whose text passed through a model is not a source.
            out.append(("REFUSED", fn, "a model stood in the path; this is not a primary source"))
            continue

        addr = address or meta.get("address") or ""
        keys = _address_keys(addr, packs)
        if not keys:
            # 🔴 REFUSE rather than file it somewhere plausible. Putting a document in a law folder
            # is what makes it law here, so "put it wherever" IS issuing a certificate of primary
            # authority at random. The sister project reached the same conclusion independently.
            out.append(("NO ADDRESS", fn,
                        "give --address \"8 CFR 245.1\" (or a citation the packs recognise). "
                        "Refusing: a file placed in a sources folder becomes a primary source, so "
                        "guessing where it goes means issuing that status at random"))
            continue

        key = sorted(keys)[0]
        kid = "|".join(key)
        text = read_any(src)

        # 🔴 AN EXTRACTION FAILURE IS NOT A CHANGE IN THE LAW. Without this, a new edition
        # that cannot be read - a scan, a corrupt download, a format the readers do not
        # handle - produced `revision_diff(old, "")`: every sentence "gone", 0 % similar, a
        # report announcing the provision had been deleted in its entirety, and every banked
        # quotation marked lost. Refusing is the only honest answer.
        if len(text.strip()) < MIN_TEXT_LAYER:
            out.append(("UNREADABLE", fn,
                        "only %d characters could be extracted - refusing rather than "
                        "reporting it as a change in the law. OCR it, or fetch another format"
                        % len(text.strip())))
            continue

        # 🔴 THE TRUST LABEL IS RE-DERIVED, NEVER READ OUT OF THE FILE BESIDE IT.
        # `.meta.json` sits in a writable directory, and `intake` walks whatever is in the
        # inbox - so a file dropped there by hand with a hand-written meta claiming
        # `"trust": "primary"` was registered as OFFICIAL and written into the human-facing
        # library index with that word. Measured: a paste-site URL took an OFFICIAL row. The
        # three trust levels were a front-door control on a house with an open side door.
        # The WORSE of the two answers wins, and an entry with no URL cannot claim anything.
        claimed = meta.get("trust") or "unknown"
        actual = trust_of(meta.get("url") or "", cfg, packs)[0] if meta.get("url") \
            else "unknown"
        rank = {"primary": 3, "snapshot": 2, "nonauthoritative": 1, "unknown": 0,
                "lookalike": -1}
        kind = actual if rank.get(actual, 0) <= rank.get(claimed, 0) else claimed
        if kind == "lookalike":
            out.append(("REFUSED", fn, "the recorded URL is a lookalike host"))
            continue
        meta["trust"], meta["trust_label"] = kind, TRUST[kind][0]

        prev = reg.get(kid)
        dest = os.path.join(library, fn)

        if prev and prev.get("sha256") == meta.get("sha256"):
            out.append(("ALREADY HAVE", fn, "same address, identical bytes - nothing to do"))
            continue

        if prev and os.path.exists(prev.get("path", "")):
            # ---- A REVISION -------------------------------------------------------------------
            n = int(prev.get("revision", 1)) + 1
            stem, ext = os.path.splitext(fn)
            dest = os.path.join(library, "%s__rev%d%s" % (stem, n, ext))
            old_text = read_any(prev["path"])
            d = revision_diff(old_text, text)
            os.replace(src, dest)
            rev_dir = os.path.join(root, REVISIONS)
            os.makedirs(rev_dir, exist_ok=True)
            report = os.path.join(rev_dir, "%s-rev%d.md" % (_SAFE.sub("-", kid), n))
            io.open(report, "w", encoding="utf-8", newline="\n").write(
                _revision_report(addr, prev, meta, d, cfg, text, packs))
            reg[kid] = {"path": dest, "sha256": meta.get("sha256"), "address": addr,
                        "revision": n, "url": meta.get("url", ""), "trust": meta.get("trust"),
                        "fetched_at": meta.get("fetched_at"), "supersedes": prev.get("path")}
            out.append(("🔴 REVISION", os.path.basename(dest),
                        "%d sentence(s) gone, %d new, %d moved, %.1f%% unchanged - the previous "
                        "edition is KEPT, and %s says what it means for the bank"
                        % (len(d["gone"]), len(d["added"]), d.get("moved", 0),
                           100 * d["similarity"], os.path.relpath(report, root))))
        else:
            os.replace(src, dest)
            reg[kid] = {"path": dest, "sha256": meta.get("sha256"), "address": addr,
                        "revision": 1, "url": meta.get("url", ""), "trust": meta.get("trust"),
                        "fetched_at": meta.get("fetched_at")}
            out.append(("added", os.path.basename(dest), "%s · %s" % (addr, meta.get("trust_label"))))

        try:
            os.remove(src + ".meta.json")
        except OSError:
            pass

        from .library import add_entry
        add_entry(cfg.abs(cfg["library_index"]), citation=addr,
                  what=meta.get("trust_label", "UNKNOWN"),
                  filename=os.path.basename(dest),
                  edition=(meta.get("fetched_at") or "")[:10],
                  notes=("from %s" % meta.get("url", ""))[:120])

    _write_registry(root, reg)
    return out


def _revision_report(addr, prev, meta, d, cfg, new_text, packs):
    """The report exists to answer one question: which banked quotations just stopped matching?"""
    lines = [
        "# Revision of %s" % (addr or "an unidentified provision"),
        "",
        "| | |", "|---|---|",
        "| previous | `%s` |" % prev.get("path", ""),
        "| previous sha256 | `%s` |" % (prev.get("sha256") or "")[:16],
        "| new sha256 | `%s` |" % (meta.get("sha256") or "")[:16],
        "| source | %s |" % (meta.get("url") or ""),
        "| retrieved | %s |" % (meta.get("fetched_at") or ""),
        "| unchanged | %.1f%% of sentences |" % (100 * d["similarity"]),
        "| moved | %d sentence(s) kept, in a different place |" % d.get("moved", 0),
        "",
        "🔴 **A sentence that MOVED is not a sentence that stayed.** Set comparison cannot see "
        "order, so relocating a conditioning sentence into another subsection reported 0 gone, "
        "0 new and 100 % unchanged. The words are still in the document and the rule they "
        "condition may no longer be the same one. Read the moved count before trusting the "
        "unchanged percentage."
        if d.get("moved") else "",
        "",
        "🔴 **The previous edition has NOT been deleted.** A quotation taken from it is still a "
        "correct quotation of the text that was in force when it was taken. What changes is which "
        "edition a filing should cite.",
        "",
        "## Sentences that are gone (%d)" % len(d["gone"]),
        "",
    ]
    for s in d["gone"][:60]:
        lines.append("- %s" % s[:300])
    if len(d["gone"]) > 60:
        lines.append("- …and %d more" % (len(d["gone"]) - 60))
    lines += ["", "## Sentences that are new (%d)" % len(d["added"]), ""]
    for s in d["added"][:60]:
        lines.append("- %s" % s[:300])
    if len(d["added"]) > 60:
        lines.append("- …and %d more" % (len(d["added"]) - 60))

    lines += ["", "## What this does to the quote bank", ""]
    try:
        lines += _bank_impact(cfg, new_text, packs)
    except Exception as exc:                                          # noqa: BLE001
        lines.append("could not re-check the bank (%s) - do it by hand with `krokai check`"
                     % type(exc).__name__)
    return "\n".join(lines) + "\n"


def _bank_impact(cfg, new_text, packs):
    """Every quotation in the bank, against the NEW edition only.

    🔴 This is the half that makes a revision actionable. Without it the user is told that the law
    changed and left to work out which of their own quotations that breaks - which is the question,
    and it is the one a machine can answer in a second and a person cannot.
    """
    from .bank import read_bank
    from .extract import extract_quotes
    from .normalize import normalise, prepare_quote, ellipsis_parts

    bank = read_bank(cfg.abs(cfg["bank"]))
    quotes = extract_quotes(bank, 45)
    if not quotes:
        return ["The bank holds no quotations yet, so nothing to re-check."]
    hay = normalise(new_text)

    def still_there(q):
        """🔴 An ellipsis is citation style, not an alteration - and a quotation containing
        one can never be a substring of anything. Without this, EVERY banked quotation with
        an ellipsis was reported lost on EVERY revision, unconditionally, under a red heading
        telling the reader it would come back as the fabrication signal. A well-kept bank
        cites with ellipses, so the better the bank the louder the false alarm - in the one
        document whose entire job is to be believed. Named by an outside reviewer.
        """
        prepared = normalise(prepare_quote(q))
        if prepared in hay:
            return True
        parts = ellipsis_parts(prepared, 25)
        if len(parts) < 2:
            return False
        cur = -1
        for part in parts:                     # every fragment, in order, without overlap
            i = hay.find(part, cur + 1)
            if i < 0:
                return False
            cur = i + len(part) - 1
        return True

    lost = [q for q in quotes if not still_there(q)]
    out = ["%d quotation(s) in the bank; **%d no longer appear in the new edition**."
           % (len(quotes), len(lost)), ""]
    if lost:
        out += ["🔴 Each of these was correct when it was banked. In the new edition it will come "
                "back `NOT_FOUND`, which is this tool's fabrication signal - so decide, per "
                "quotation, whether the filing should cite the edition in force at the time or "
                "the current text. Do not silently 'correct' them.", ""]
        for q in lost[:40]:
            out.append("- > %s" % q[:280])
        if len(lost) > 40:
            out.append("- …and %d more" % (len(lost) - 40))
    else:
        out.append("Every banked quotation is still present verbatim in the new edition.")
    return out
