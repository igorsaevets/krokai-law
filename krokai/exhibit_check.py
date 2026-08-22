# -*- coding: utf-8 -*-
"""Cross-check exhibits and forms between petition documents and the filing folder.

Before printing, you need to know: does every exhibit the petition promises actually exist as
a file, and does every file in the exhibit folder actually get mentioned somewhere? The first
class (cited, no file) is the one that costs a filing — the adjudicator follows the reference
and finds nothing. The second class (file, no citation) is either a forgotten argument or dead
weight; a human decides.

Forms get the same treatment: the petition says "Form I-485 (Exhibit A-1)" and the forms folder
should contain a file whose name starts with "I-485" or "i-485".

The tool reads petition documents (.md, .txt, .docx) and scans exhibit/form directories. It does
NOT read PDF content — only filenames. The match is by exhibit ID, never by description.
"""
from __future__ import annotations

import io
import os
import re


# ------------------------------------------------------------------------------- exhibit IDs

# Series letters allowed in exhibit IDs. Anything else that looks like "X-123" is noise
# (form numbers like G-1450, visa classes like H-1B, filing numbers like I-485).
# This default covers the conventions seen in real filings; callers can override.
DEFAULT_SERIES = "A B C D E F G H J K L M P V W X".split()

# Form numbers that LOOK like exhibit IDs but are not. Without this, "Form G-1145" in the
# petition text would register as exhibit G-1145 and then be reported missing from the exhibit
# folder — a false alarm on every run.
NOT_EXHIBIT = frozenset({
    "G-28", "G-325", "G-884", "G-1055", "G-1145", "G-1450",
    "F-1", "F-2", "F-3", "B-1", "B-2", "H-1", "H-1b", "H-2",
    "J-1", "J-2", "L-1", "L-1a", "L-1b", "E-1", "E-2", "E-3",
    "K-1", "K-2", "K-3", "K-4", "K-12",
})

# Series whose "exhibits" are the documents themselves (memoranda, legal-base appendices),
# not files in the exhibit tree. They live in the petition folder, not the exhibit folder.
DOC_SERIES = frozenset({"M", "W"})

# Exhibit-ID extraction from document TEXT. The pattern must be strict: in prose, "I-485",
# "H-1B", "F-1" are visa/form codes, not exhibit numbers. Only the declared series match.
# Sub-exhibit suffixes (D-19a, D-19c) are captured. Leading zeros are stripped in canon().
def _build_id_re(series):
    s = "|".join(sorted(series, key=len, reverse=True))
    return re.compile(
        r"(?<![A-Za-z])(?:Exhibit\s+)?(%s)\s*[-–—]\s*0*(\d{1,4})([a-zA-Z]?\d?)"
        r"(?![-–—\d])" % s, re.I)

# K-series: often written WITHOUT hyphen ("K1", "K12") in some briefs.
_K_RE = re.compile(r"(?<![A-Za-z])\bK\s*[-–—]?\s*0*(\d{1,4})([a-zA-Z]?)(?![-–—\d])")

# Exhibit-ID extraction from FILENAMES. More lenient: the hyphen between letter and number
# is optional because some files are named "Exhibit P01 - ..." without the hyphen.
def _build_file_re(series):
    s = "|".join(sorted(series, key=len, reverse=True))
    return re.compile(
        r"^(?:Exhibit\s+)?(%s)\s*[-–—]?\s*0*(\d{1,4})([a-zA-Z]?\d?)"
        r"(?![0-9])" % s, re.I)

# Multi-part file suffix: B-03_1, B-03_2 are parts of the same exhibit, not duplicates.
PART_RE = re.compile(r"[-_](\d{1,2})(?:\D|$)")

# Document file extensions. Sidecar files (.evidence.json, .unconfirmed.json, .progress.json,
# .txt sidecars) are auxiliary data, not exhibits. Including them inflates duplicate counts.
DOC_EXTS = frozenset({
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp",
    ".md", ".txt", ".rtf", ".odt", ".html", ".htm",
})

# Action markers left in filenames by humans — an unclosed task.
ACTION_RE = re.compile(
    r"(FIXME|TODO|ИСПРАВИТЬ|ОБНОВИТЬ|СДЕЛАТЬ|ПРОВЕРИТЬ|DRAFT|ЧЕРНОВИК)", re.I)


def canon(series, num, suf):
    """Canonicalize an exhibit ID: uppercase letter, stripped leading zeros, lowercase suffix."""
    return "%s-%s%s" % (series.upper(), num.lstrip("0") or "0", suf.lower())


def ids_in_text(text, series=None):
    """Extract all exhibit IDs from document text. Returns a set of canonical IDs."""
    if series is None:
        series = DEFAULT_SERIES
    id_re = _build_id_re(series)
    out = set()
    for m in id_re.finditer(text):
        eid = canon(*m.groups())
        if eid in NOT_EXHIBIT or eid.split("-")[0] in DOC_SERIES:
            continue
        out.add(eid)
    if "K" in series:
        for m in _K_RE.finditer(text):
            out.add(canon("K", m.group(1), m.group(2)))
    return out


# ------------------------------------------------------------------------------- form IDs

# Form references in text: "Form I-485", "Forms I-20", "Form G-1450", "Form ETA-9089"
FORM_TEXT_RE = re.compile(
    r"Forms?\s+((?:I|G|N|ETA)[-–—]?\d{2,5}[A-Z]?)", re.I)

# Form ID from filename: starts with form number pattern (case-insensitive)
FORM_FILE_RE = re.compile(
    r"^((?:I|G|N|ETA)[-–—]?\d{2,5}[A-Z]?)", re.I)


def canon_form(raw):
    """Canonicalize a form ID: uppercase, ensure hyphen after letter prefix."""
    s = raw.upper().replace("–", "-").replace("—", "-")
    if re.match(r"^[A-Z]{1,3}\d", s):
        m = re.match(r"^([A-Z]{1,3})(\d.*)$", s)
        if m:
            s = m.group(1) + "-" + m.group(2)
    return s


def forms_in_text(text):
    """Extract all form IDs from document text."""
    out = set()
    for m in FORM_TEXT_RE.finditer(text):
        out.add(canon_form(m.group(1)))
    return out


# ------------------------------------------------------------------------------- file reading

def _read_docx(path):
    """Extract text from a .docx file using only stdlib (zipfile + xml.etree)."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        parts = []
        for t in tree.iter("{%s}t" % ns):
            if t.text:
                parts.append(t.text)
        return " ".join(parts)
    except Exception:
        return ""


def _read_text(path):
    """Read a text file, returning empty string on failure or for binary files."""
    low = path.lower()
    if low.endswith(".docx"):
        return _read_docx(path)
    if low.endswith((".pdf", ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff",
                     ".bmp", ".webp", ".zip", ".7z", ".rar", ".doc",
                     ".xlsx", ".xls", ".pptx", ".ppt")):
        return ""
    try:
        return io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


# ------------------------------------------------------------------------------- scanning

def scan_exhibit_dir(root, series=None):
    """Walk an exhibit directory tree and extract exhibit IDs from filenames.

    Returns:
        files: dict mapping canonical exhibit ID to list of full file paths
        problems: list of (kind, path) tuples for files with issues
    """
    if series is None:
        series = DEFAULT_SERIES
    file_re = _build_file_re(series)
    id_re = _build_id_re(series)
    files = {}
    problems = []
    if not os.path.isdir(root):
        return files, problems
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            ext = os.path.splitext(fn)[1].lower()
            if ext not in DOC_EXTS:
                continue
            m = file_re.match(fn) or id_re.search(fn[:50])
            if not m:
                problems.append(("NO-ID", full))
                continue
            eid = canon(*m.groups())
            if eid in NOT_EXHIBIT or eid.split("-")[0] in DOC_SERIES:
                problems.append(("NOT-EXHIBIT", full))
                continue
            files.setdefault(eid, []).append(full)
            if ACTION_RE.search(fn):
                problems.append(("ACTION-MARKER", full))
    return files, problems


def scan_form_dir(root):
    """Walk a forms directory and extract form IDs from filenames.

    Returns:
        files: dict mapping canonical form ID to list of full file paths
        problems: list of (kind, path) tuples
    """
    files = {}
    problems = []
    if not os.path.isdir(root):
        return files, problems
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            m = FORM_FILE_RE.match(fn)
            if not m:
                problems.append(("NO-FORM-ID", full))
                continue
            fid = canon_form(m.group(1))
            files.setdefault(fid, []).append(full)
    return files, problems


# ------------------------------------------------------------------------------- reconcile

def reconcile(petition_paths, exhibit_dirs, form_dirs=None, series=None, out=None):
    """Cross-check petition references against exhibit/form directories.

    Args:
        petition_paths: list of paths to petition documents (.md, .txt, .docx)
        exhibit_dirs: list of paths to exhibit directories
        form_dirs: optional list of paths to form directories
        series: exhibit series letters (default: DEFAULT_SERIES)
        out: optional path to write the report

    Returns:
        dict with keys: cited_no_file, file_no_cite, duplicates, matched,
                        form_cited_no_file, form_file_no_cite, form_matched,
                        problems, report_lines
    """
    if series is None:
        series = DEFAULT_SERIES
    L = []

    def say(s=""):
        L.append(s)

    say("# Exhibit / Form reconciliation: documents vs. disk")
    say("")

    # --- read petition documents ---
    cited = set()
    cited_forms = set()
    per_doc = {}
    per_doc_forms = {}
    docs_read = 0
    for p in petition_paths:
        if os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                fp = os.path.join(p, fn)
                if os.path.isfile(fp):
                    text = _read_text(fp)
                    if text:
                        refs = ids_in_text(text, series)
                        frefs = forms_in_text(text)
                        per_doc[fn] = refs
                        per_doc_forms[fn] = frefs
                        cited |= refs
                        cited_forms |= frefs
                        docs_read += 1
        elif os.path.isfile(p):
            text = _read_text(p)
            if text:
                fn = os.path.basename(p)
                refs = ids_in_text(text, series)
                frefs = forms_in_text(text)
                per_doc[fn] = refs
                per_doc_forms[fn] = frefs
                cited |= refs
                cited_forms |= frefs
                docs_read += 1

    say("petition documents read: **%d**" % docs_read)
    if per_doc:
        for fn in sorted(per_doc):
            say("  - `%s` — %d exhibit refs, %d form refs"
                % (fn, len(per_doc[fn]), len(per_doc_forms.get(fn, set()))))
    say("")

    if docs_read == 0:
        say("## REFUSED: no petition documents read")
        say("")
        say("Zero documents read means zero references found, which means zero defects — ")
        say("but that is an artifact of empty input, not a measurement. Check the paths.")
        return {"report_lines": L, "refused": True}

    say("exhibit IDs cited in petitions: **%d**" % len(cited))
    say("form IDs cited in petitions: **%d** — %s" % (
        len(cited_forms), ", ".join(sorted(cited_forms)) or "none"))
    say("")

    # --- scan exhibit directories ---
    on_disk = {}
    all_problems = []
    for d in exhibit_dirs:
        say("exhibit directory: `%s`" % d)
        if not os.path.isdir(d):
            say("  (does not exist)")
            continue
        files, problems = scan_exhibit_dir(d, series)
        for eid, paths in files.items():
            on_disk.setdefault(eid, []).extend(paths)
        all_problems.extend(problems)
    total_exhibit_files = sum(len(v) for v in on_disk.values())
    say("exhibit files on disk: **%d** files in **%d** exhibit IDs" % (
        total_exhibit_files, len(on_disk)))
    say("")

    # --- scan form directories ---
    form_on_disk = {}
    if form_dirs:
        for d in form_dirs:
            say("form directory: `%s`" % d)
            if not os.path.isdir(d):
                say("  (does not exist)")
                continue
            files, problems = scan_form_dir(d)
            for fid, paths in files.items():
                form_on_disk.setdefault(fid, []).extend(paths)
            all_problems.extend(problems)
        say("form files on disk: **%d** files in **%d** form IDs" % (
            sum(len(v) for v in form_on_disk.values()), len(form_on_disk)))
        say("")

    # --- exhibits: cited but no file ---
    cited_no_file = cited - set(on_disk)
    say("## CITED-NO-FILE: referenced in petition, no file on disk — %d" % len(cited_no_file))
    say("")
    if cited_no_file:
        say("The adjudicator follows the reference and finds nothing. This is the class that "
            "costs a filing.")
        say("")
        for eid in sorted(cited_no_file, key=lambda s: (s[0], int(re.sub(r"\D", "", s[2:]) or "0"), s)):
            who = sorted(d for d, ss in per_doc.items() if eid in ss)
            say("* **%s** — cited in: %s" % (eid, ", ".join(who)))
    else:
        say("*(none)*")
    say("")

    # --- exhibits: file exists but not cited ---
    file_no_cite = set(on_disk) - cited
    say("## FILE-NO-CITE: file exists, not referenced in any petition document — %d"
        % len(file_no_cite))
    say("")
    if file_no_cite:
        say("Not a defect by itself — may be a supporting document or a forgotten argument. "
            "A human decides.")
        say("")
        for eid in sorted(file_no_cite, key=lambda s: (s[0], int(re.sub(r"\D", "", s[2:]) or "0"), s)):
            paths = on_disk[eid]
            say("* **%s** — %s" % (eid, os.path.basename(paths[0])))
    else:
        say("*(none)*")
    say("")

    # --- duplicates (multiple files, no part suffix) ---
    duplicates = {k: v for k, v in on_disk.items()
                  if len(v) > 1 and not all(PART_RE.search(os.path.basename(x)) for x in v)}
    say("## DUPLICATE: one ID, multiple files without part suffix (_1, _2) — %d" % len(duplicates))
    say("")
    if duplicates:
        say("Multi-part exhibits with `_1`, `_2` suffixes are legitimate and excluded. "
            "These may be two versions of the same document.")
        say("")
        for k in sorted(duplicates):
            say("* **%s**" % k)
            for f in duplicates[k]:
                try:
                    sz = os.path.getsize(f)
                except OSError:
                    sz = 0
                say("    * `%s` (%d bytes)" % (os.path.basename(f), sz))
    else:
        say("*(none)*")
    say("")

    # --- forms: cited but no file ---
    form_cited_no_file = set()
    form_file_no_cite = set()
    form_matched = set()
    if form_dirs:
        form_cited_no_file = cited_forms - set(form_on_disk)
        form_file_no_cite = set(form_on_disk) - cited_forms
        form_matched = cited_forms & set(form_on_disk)

        say("## FORM-CITED-NO-FILE: form referenced in petition, no file on disk — %d"
            % len(form_cited_no_file))
        say("")
        if form_cited_no_file:
            for fid in sorted(form_cited_no_file):
                who = sorted(d for d, ss in per_doc_forms.items() if fid in ss)
                say("* **%s** — cited in: %s" % (fid, ", ".join(who)))
        else:
            say("*(none)*")
        say("")

        say("## FORM-FILE-NO-CITE: form file exists, not referenced — %d" % len(form_file_no_cite))
        say("")
        if form_file_no_cite:
            for fid in sorted(form_file_no_cite):
                paths = form_on_disk[fid]
                say("* **%s** — %s" % (fid, os.path.basename(paths[0])))
        else:
            say("*(none)*")
        say("")

    # --- action markers in filenames ---
    acts = [p for k, p in all_problems if k == "ACTION-MARKER"]
    if acts:
        say("## ACTION MARKERS in filenames (FIXME/TODO/DRAFT) — %d" % len(acts))
        say("")
        say("A marker in the filename is an unclosed task left by a human.")
        say("")
        for p in acts:
            say("* `%s`" % os.path.basename(p))
        say("")

    # --- files without recognized ID ---
    noname = [p for k, p in all_problems if k == "NO-ID"]
    if noname:
        say("## FILES WITHOUT RECOGNIZED EXHIBIT ID — %d" % len(noname))
        say("")
        for p in noname:
            say("* `%s`" % os.path.basename(p))
        say("")

    # --- numbering gaps ---
    say("## Numbering gaps by series")
    say("")
    say("A gap is not a defect — a number may have been retired. This is a map for humans.")
    say("")
    by_s = {}
    for eid in on_disk:
        parts = eid.split("-", 1)
        if len(parts) == 2:
            try:
                n = int(re.sub(r"[^0-9]", "", parts[1]) or "0")
            except ValueError:
                continue
            by_s.setdefault(parts[0], set()).add(n)
    for s in sorted(by_s):
        nums = sorted(by_s[s])
        if not nums:
            continue
        holes = [i for i in range(1, max(nums) + 1) if i not in nums]
        say("* **%s**: %d IDs, max %d, gaps: %s"
            % (s, len(nums), max(nums), ", ".join(map(str, holes)) or "none"))
    say("")

    # --- summary ---
    say("## Summary")
    say("")
    matched = cited & set(on_disk)
    say("| Category | Count |")
    say("|---|---|")
    say("| Exhibits matched | %d |" % len(matched))
    say("| Cited, no file | %d |" % len(cited_no_file))
    say("| File, no citation | %d |" % len(file_no_cite))
    say("| Duplicates | %d |" % len(duplicates))
    if form_dirs:
        say("| Forms matched | %d |" % len(form_matched))
        say("| Form cited, no file | %d |" % len(form_cited_no_file))
        say("| Form file, no citation | %d |" % len(form_file_no_cite))
    say("")

    # --- write report ---
    report_text = "\n".join(L) + "\n"
    if out:
        os.makedirs(os.path.dirname(out) if os.path.dirname(out) else ".", exist_ok=True)
        io.open(out, "w", encoding="utf-8", newline="\n").write(report_text)

    return {
        "cited_no_file": cited_no_file,
        "file_no_cite": file_no_cite,
        "duplicates": duplicates,
        "matched": matched,
        "form_cited_no_file": form_cited_no_file,
        "form_file_no_cite": form_file_no_cite,
        "form_matched": form_matched,
        "problems": all_problems,
        "report_lines": L,
        "refused": False,
    }
