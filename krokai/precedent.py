# -*- coding: utf-8 -*-
"""fetch-precedent: download a court decision AND prove the download is the one you meant.

WHAT THIS ANSWERS
-----------------
An assistant asked to save the ``Matter of Smith`` decision saves ``another Smith`` from the same
reporter volume - same name, different party, different subject, different court. Every step of
the pipeline said VERIFIED, because the pipeline was answering the wrong question. Measured in
the sister project (AOS 2026, R79 study §5): the downloaded precedent was a case with the same
family name and a different disposition. Nothing in the URL, the anchor text or the file name
carried enough to distinguish them.

The fix is not to trust any of those, it is to READ THE DOWNLOADED TEXT and require three
distinctive tokens to appear in it BEFORE the file is kept:

* ``--party``    the applicant or petitioner's name, ideally as a distinctive fragment ("Smith,
                 12 I&N Dec. 205" is safer than "Smith"; a bare surname collides between cases)
* ``--subject``  the legal issue ("adjustment of status", "removal proceedings", "hardship
                 waiver") - a word the opinion body itself uses
* ``--court``    the deciding body ("BIA", "AAO", "Board of Immigration Appeals",
                 "Ninth Circuit", "Supreme Court")

If any of the three is missing from the extracted body, the download is deleted from the inbox
and the command exits non-zero with the list of missing criteria. Nothing is kept unless every
criterion is satisfied. There is no ``--force`` flag: a file that lands in the precedents folder
becomes a primary source, and forcing a wrong one in is the failure this module exists to catch.

🔴 CASE-INSENSITIVE, WHITESPACE-COLLAPSED, MATCH IN THE FIRST 200 KB
--------------------------------------------------------------------
* CI so ``BIA`` and ``bia`` and ``Bia`` all match. Legal PDFs vary.
* Whitespace collapsed so a line break between two words of the party name does not defeat the
  match. The check is *is this string present*, not *is this string a token*.
* Only the first 200 KB of extracted text are searched. A precedent's caption, court and issue
  live in the head of the document; a match past 200 KB has a much higher rate of coincidence
  (a footnote citing another case, a later case citing this one). Measured in the sister
  project: two false positives out of the six precedents in the R32 delivery both matched on
  footnote citations 30 pages in. 200 KB is roughly 40 typed pages.

🔴 THE FILE IS DELETED FROM THE INBOX ON FAILURE
-------------------------------------------------
A wrong-file precedent sitting in the inbox becomes an ``intake`` candidate at the next round,
and a wrong file in ``intake`` is a wrong file in the library. The correct state after a failed
verification is *nothing on disk*: the caller sees the failure, decides whether to widen the
criteria or try a different URL, and re-runs. Not deleting would preserve a wrong file for a
"you can look at it manually" that never happens.

🔴 A SUCCESSFUL SAVE WRITES ``verified_criteria`` INTO THE META
----------------------------------------------------------------
So a later reader can see what the file was checked against - and so the tests that assert this
mechanism has run can look at a file, not a log line. Same discipline as ``model_in_path:
False``: the record lives beside the file, not in a docstring.
"""
from __future__ import annotations

import io
import json
import os
import re
import time

__all__ = ["fetch_precedent", "verify_criteria", "SEARCH_HEAD_BYTES"]

# The head of the extracted text that carries the caption, court and issue. See docstring.
SEARCH_HEAD_BYTES = 200_000


def _normalise_for_search(text):
    """Lower-case, whitespace-collapsed. Case matters nowhere in a legal caption, and line
    wrapping is a rendering choice this check must not be sensitive to."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower())


def verify_criteria(text, party, subject, court):
    """The mechanical check `fetch_precedent` runs after download.

    Returns `(ok, missing)`. `missing` is a list of `("party"|"subject"|"court", value)`
    tuples for the criteria that were not found. When all three are found, `ok` is True and
    `missing` is empty.

    Split out for the self-test: the shape of the function is the specification of the check,
    and pinning it in isolation is what stops a future edit widening the head window silently.
    """
    head = _normalise_for_search((text or "")[:SEARCH_HEAD_BYTES])
    missing = []
    for label, value in (("party", party), ("subject", subject), ("court", court)):
        needle = _normalise_for_search(value or "")
        if not needle:
            missing.append((label, value or ""))
            continue
        if needle not in head:
            missing.append((label, value or ""))
    return (not missing, missing)


def _refuse_bad_criteria(party, subject, court, printer):
    """Empty or whitespace-only criteria arrive as programmer error - the CLI already requires
    the three flags. This exists so a caller of `fetch_precedent` from Python cannot bypass
    the guard by passing an empty string, which would match everywhere.
    """
    problems = []
    for name, value in (("--party", party), ("--subject", subject), ("--court", court)):
        if not (value or "").strip():
            problems.append(name)
    if problems:
        printer("🔴 REFUSED: empty criterion %s. An empty needle matches everywhere - a "
                "'verified' precedent under an empty criterion is a laundered wrong file."
                % ", ".join(problems))
        return True
    return False


def _delete_from_inbox(inbox_path, printer):
    """Best-effort delete of the file and its .meta.json. A precedent that failed verification
    must not sit in the inbox for the next `intake`. If the delete itself fails - permissions,
    a lock - the caller must know: the file is still on disk and it is the wrong file.
    """
    left = []
    for p in (inbox_path, inbox_path + ".meta.json"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError as exc:                                          # noqa: BLE001
            left.append((p, str(exc)))
    if left:
        printer("🔴 CLEANUP FAILED - the wrong file is still on disk:")
        for p, msg in left:
            printer("   %s   (%s)" % (p, msg[:120]))
        printer("   Delete it by hand BEFORE the next `krokai intake`.")


def fetch_precedent(url, party, subject, court, root, cfg=None, packs=None,
                    dest_dir=None, allow_unknown=False, timeout=45, printer=print):
    """Download a precedent and keep it only if it names the party, subject and court.

    Returns `(True, dest_path, meta)` on success, `(False, None, reason_dict)` on failure.
    `reason_dict` holds `stage` (``fetch``|``read``|``verify``) and the details for that
    stage - the shape a hook or CI job needs to gate on which failure happened.

    ``dest_dir`` defaults to ``<root>/precedents/``. Successful writes go there, not into the
    same folder as ``law/``: precedents are a distinct kind of primary source (a decision,
    not a statute), the intake path knows this distinction, and a mixed folder is what turned
    a scraped headnote into a "verified" statute quotation in the sister project.
    """
    if _refuse_bad_criteria(party, subject, court, printer):
        return False, None, {"stage": "refuse", "reason": "empty criterion"}

    from .fetch import fetch_url, INBOX
    from .readers import read_any

    meta = fetch_url(url, root, cfg=cfg, packs=packs, allow_unknown=allow_unknown,
                     timeout=timeout, printer=printer)
    if not meta:
        return False, None, {"stage": "fetch", "reason": "download refused or failed"}

    # `fetch_url` names the file it wrote via `saved ... -> <relpath>` but does not return the
    # path. Re-derive from the inbox: the most recently written non-.meta file is ours, and
    # the meta contents match. A more robust route (having fetch_url return the path) would be
    # nicer but out of scope here.
    inbox_dir = os.path.join(root, INBOX)
    inbox_path = None
    for name in sorted(os.listdir(inbox_dir), reverse=True):
        if name.endswith(".meta.json"):
            continue
        cand = os.path.join(inbox_dir, name)
        try:
            m = json.load(io.open(cand + ".meta.json", encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("sha256") == meta.get("sha256"):
            inbox_path = cand
            break
    if not inbox_path:
        printer("🔴 could not locate the freshly downloaded file in the inbox - refusing to "
                "verify anything")
        return False, None, {"stage": "read", "reason": "download not found in inbox"}

    try:
        text = read_any(inbox_path)
    except Exception as exc:                                            # noqa: BLE001
        printer("🔴 could not extract text from %s: %s: %s"
                % (os.path.basename(inbox_path), type(exc).__name__, exc))
        _delete_from_inbox(inbox_path, printer)
        return False, None, {"stage": "read", "reason": "extraction failed",
                             "error": type(exc).__name__}

    if not (text or "").strip():
        printer("🔴 the downloaded file has NO extractable text - a scan, a JS-only page, or a "
                "reader missing an engine. Nothing kept.")
        _delete_from_inbox(inbox_path, printer)
        return False, None, {"stage": "read", "reason": "no extractable text"}

    ok, missing = verify_criteria(text, party, subject, court)
    if not ok:
        printer("")
        printer("🔴 THIS IS NOT THE PRECEDENT YOU ASKED FOR - %d criteri%s missing from the "
                "first %d KB of extracted text:"
                % (len(missing), "on" if len(missing) == 1 else "a",
                   SEARCH_HEAD_BYTES // 1000))
        for label, value in missing:
            printer("   --%-8s %s" % (label, value))
        printer("")
        printer("   AOS measured: an assistant saved 'another Smith' from the same volume; the "
                "'wrong file' shape lives in exactly this window. Nothing kept.")
        _delete_from_inbox(inbox_path, printer)
        return False, None, {"stage": "verify", "reason": "criteria not found",
                             "missing": missing}

    # ---- everything passed: move into the precedents folder, stamp the meta ---------------
    dest_root = dest_dir or os.path.join(root, "precedents")
    os.makedirs(dest_root, exist_ok=True)
    base = os.path.basename(inbox_path)
    dest = os.path.join(dest_root, base)
    n = 1
    while os.path.exists(dest):
        stem, ext = os.path.splitext(base)
        dest = os.path.join(dest_root, "%s-%d%s" % (stem, n, ext))
        n += 1
    os.replace(inbox_path, dest)

    meta_out = dict(meta)
    meta_out["verified_criteria"] = {
        "party": party,
        "subject": subject,
        "court": court,
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "search_head_bytes": SEARCH_HEAD_BYTES,
    }
    io.open(dest + ".meta.json", "w", encoding="utf-8", newline="\n").write(
        json.dumps(meta_out, ensure_ascii=False, indent=2))
    try:
        os.remove(inbox_path + ".meta.json")
    except OSError:
        pass
    printer("")
    printer("✅ verified and saved -> %s" % os.path.relpath(dest, root))
    printer("   party:   %s" % party)
    printer("   subject: %s" % subject)
    printer("   court:   %s" % court)
    return True, dest, meta_out
