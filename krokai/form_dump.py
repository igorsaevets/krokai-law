# -*- coding: utf-8 -*-
"""Dump filled AcroForm field values from USCIS forms with dual-engine cross-verification.

Before filing, you need to know what actually stands in each field of a filled PDF form.
The text layer of a fillable PDF contains only the labels ("Family Name (Last Name)") — the
values the applicant typed live in /AcroForm /Fields as /V. Reading the text layer alone and
concluding the fields are empty is the silent error this tool exists to prevent.

Two extraction engines (fitz/PyMuPDF and pypdf) read the same PDF independently. Where they
agree, the value is defensible; where they disagree, the row is flagged for human review.
Either engine alone is sufficient — the cross-check is a bonus when both are installed.

G-1450 (USCIS credit-card authorisation) is excluded by default: cardholder data has no
review value and should not leave the machine.

Based on the dual-engine approach proven in the Batch Review project (extract_forms_r10.py).
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re

from .corpus import walk_error

# ------------------------------------------------------------------------------- constants

HARD_EXCLUDE = [
    (re.compile(r"g-?1450", re.I),
     "USCIS credit-card authorisation: cardholder data, no review value"),
]

NOISE_WIDGET = re.compile(r"barcode|PDF417", re.I)

STRUCT_ONLY = re.compile(
    r"^form1\[\d+\](\.#(subform|pageSet|area)\[\d+\])*$", re.I)

_SIG_TYPE = "/Sig"


def _is_noise(name):
    return bool(NOISE_WIDGET.search(name) or STRUCT_ONLY.match(name))


def _sha8(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:8]


# ------------------------------------------------------------------------------- fitz engine

def _extract_fitz(path):
    """Return (rows, page_count) using PyMuPDF. Rows sorted by reading order (page, y, x)."""
    try:
        import fitz
    except ImportError:
        return None, 0
    rows = []
    with fitz.open(path) as doc:
        pages = doc.page_count
        for i in range(pages):
            page = doc.load_page(i)
            for w in (page.widgets() or []):
                name = w.field_name or "p%d_unnamed" % (i + 1)
                if _is_noise(name):
                    continue
                v = w.field_value
                if v is True:
                    v = "[X]"
                elif v is False or v in (None, "", "Off"):
                    v = ""
                else:
                    v = str(v)
                rect = w.rect
                rows.append({
                    "page": i + 1,
                    "y": float(rect.y0),
                    "x": float(rect.x0),
                    "name": name,
                    "value": v,
                    "ftype": w.field_type_string or "?",
                })
    rows.sort(key=lambda r: (r["page"], round(r["y"], 1), round(r["x"], 1)))
    return rows, pages


# ------------------------------------------------------------------------------- pypdf engine

def _extract_pypdf(path):
    """Return {name -> value_str} for cross-check. No coordinates."""
    try:
        import pypdf
    except ImportError:
        return None
    try:
        r = pypdf.PdfReader(path)
        fields = r.get_fields() or {}
    except Exception as e:
        return {"__error__": "%s: %s" % (type(e).__name__, str(e)[:200])}
    page_of = {}
    for pi, page in enumerate(r.pages, 1):
        annots = page.get("/Annots")
        if not annots:
            continue
        try:
            annots = annots.get_object()
        except Exception:
            continue
        for a in annots:
            try:
                obj = a.get_object()
            except Exception:
                continue
            nm = obj.get("/T")
            parent = obj.get("/Parent")
            names = []
            if nm:
                names.append(str(nm))
            seen = 0
            while parent is not None and seen < 12:
                try:
                    pobj = parent.get_object()
                except Exception:
                    break
                pn = pobj.get("/T")
                if pn:
                    names.append(str(pn))
                parent = pobj.get("/Parent")
                seen += 1
            if names:
                full = ".".join(reversed(names))
                page_of.setdefault(full, pi)
    out = {}
    for name, f in fields.items():
        try:
            ftype = str(f.get("/FT") or "")
            if ftype == _SIG_TYPE:
                continue
            val = f.get("/V")
            if val is None:
                val = ""
            if not isinstance(val, (str, int, float)):
                continue
            val = str(val)
            if val.startswith("/"):
                val = val[1:]
            if val == "Off":
                val = ""
            out[str(name)] = {"value": val, "page": page_of.get(str(name), 0)}
        except Exception:
            out[str(name)] = {"value": "__READ_ERROR__", "page": 0}
    return out


# ------------------------------------------------------------------------------- cross-check

# Spellings of «this box is ticked» across engines. fitz reports boolean True (rendered
# "[X]" upstream); pypdf keeps the PDF's export value, which USCIS forms set to "Yes" and
# other producers to "On"/"1"/"true".
_CHECKED = {"[X]", "Yes", "On", "1", "true", "True"}


def _cross_check(fitz_rows, pypdf_map):
    """Compare fitz vs pypdf on shared fields. Returns a diagnostic dict."""
    if pypdf_map is None:
        return {"pypdf_available": False}
    if "__error__" in pypdf_map:
        return {"pypdf_error": pypdf_map["__error__"],
                "fitz_count": len(fitz_rows) if fitz_rows else 0,
                "pypdf_count": None,
                "value_divergent": None}
    if fitz_rows is None:
        return {"fitz_available": False, "pypdf_count": len(pypdf_map)}
    fitz_map = {r["name"]: r["value"] for r in fitz_rows}
    py_clean = {n: v["value"] for n, v in pypdf_map.items() if not _is_noise(str(n))}
    value_divs = []
    for n, fv in fitz_map.items():
        if n not in py_clean:
            continue
        pv = py_clean[n]
        fv_n = (fv or "").strip()
        pv_n = (pv or "").strip()
        if fv_n == pv_n:
            continue
        # 🔴 R76 (F14; agy36flash + agy37flash converged): the engines SPELL a checked
        # checkbox differently, so every ticked box was a false divergence and the agreement
        # number was noise. Checked-state equality is compared, not spelling.
        if fv_n in _CHECKED and pv_n in _CHECKED:
            continue
        value_divs.append({"name": n, "fitz": fv, "pypdf": pv})
    fitz_missing = sorted(n for n in py_clean if n not in fitz_map)
    shared = len(set(fitz_map) & set(py_clean))
    return {
        "fitz_count": len(fitz_map),
        "pypdf_count_all": len(pypdf_map),
        "pypdf_count_clean": len(py_clean),
        "shared": shared,
        "value_divergent": len(value_divs),
        "fitz_missing": len(fitz_missing),
        # R76: n/a when the engines share no fields - `max(1, 0)` used to print a plausible
        # «100.0% agreement» over zero compared values (spark12cont, kimik3, lunapro).
        "agreement_pct": (round(100 * (1 - len(value_divs) / float(shared)), 1)
                          if shared else None),
        "value_divergences": value_divs,
        "fitz_missing_sample": fitz_missing[:20],
    }


# ------------------------------------------------------------------------------- main entry

def dump_forms(dirs, out=None, nonempty=False):
    """Scan directories for PDF forms, extract filled fields, write reports.

    Returns a dict with manifest data suitable for machine consumption.
    """
    outdir = None
    if out:
        outdir = out if os.path.isabs(out) else os.path.abspath(out)
        os.makedirs(outdir, exist_ok=True)

    manifest = {"forms": [], "excluded": [], "errors": []}
    all_lines = []
    seen = set()

    for d in dirs:
        if not os.path.isdir(d):
            manifest["errors"].append({"dir": d, "error": "MISSING"})
            continue
        for root_dir, subdirs, files in os.walk(d, onerror=walk_error):
            subdirs.sort()
            for fname in sorted(files):
                if not fname.lower().endswith(".pdf"):
                    continue
                fpath = os.path.join(root_dir, fname)
                # 🔴 R76 (F2, execution-proven; 7 panel channels converged): dedup used to key
                # on the BASENAME across every walked directory, so `final/i-485.pdf` was
                # silently skipped once `draft/i-485.pdf` had been seen - not even an error
                # row - and the multi-copy diff below could never see two same-named copies,
                # its normal case. The key is the file, not its name.
                fkey = os.path.normcase(os.path.abspath(fpath))
                if fkey in seen:
                    continue
                seen.add(fkey)

                hit = next(((rx, why) for rx, why in HARD_EXCLUDE
                            if rx.search(fname)), None)
                if hit:
                    manifest["excluded"].append({"file": fpath, "reason": hit[1]})
                    all_lines.append("EXCLUDE  %s  (%s)" % (fname, hit[1]))
                    continue

                try:
                    fitz_rows, fitz_pages = _extract_fitz(fpath)
                    pypdf_map = _extract_pypdf(fpath)
                except Exception as e:
                    manifest["errors"].append({
                        "file": fpath,
                        "error": "%s: %s" % (type(e).__name__, str(e)[:200])})
                    all_lines.append("ERROR    %s  %s" % (fname, e))
                    continue

                # Determine primary rows and page count
                if fitz_rows is not None:
                    primary_rows = fitz_rows
                    pages = fitz_pages
                    engine = "fitz"
                elif pypdf_map is not None and "__error__" not in pypdf_map:
                    primary_rows = []
                    for name, info in sorted(pypdf_map.items()):
                        if _is_noise(name):
                            continue
                        primary_rows.append({
                            "page": info["page"],
                            "y": 0, "x": 0,
                            "name": name,
                            "value": info["value"],
                            "ftype": "?",
                        })
                    primary_rows.sort(key=lambda r: (r["page"], r["name"]))
                    pages = max((r["page"] for r in primary_rows), default=0)
                    engine = "pypdf"
                else:
                    manifest["errors"].append({
                        "file": fpath,
                        "error": "neither fitz nor pypdf available or readable"})
                    all_lines.append("ERROR    %s  no extraction engine available" % fname)
                    continue

                xc = _cross_check(fitz_rows, pypdf_map)
                filled = [r for r in primary_rows if r["value"]]
                digest = _sha8(fpath)

                # Per-form output
                form_lines = [
                    "=== FORM: %s ===" % fname,
                    "path: %s" % fpath,
                    "sha8: %s" % digest,
                    "pages: %s" % pages,
                    "engine: %s" % engine,
                    "widgets: %d total, %d filled" % (len(primary_rows), len(filled)),
                ]
                if xc.get("agreement_pct") is not None:
                    form_lines.append(
                        "cross-check: %s%% agreement (%d divergent)"
                        % (xc["agreement_pct"], xc["value_divergent"]))
                form_lines.append("")

                for r in primary_rows:
                    v = r["value"]
                    if nonempty and not v:
                        continue
                    marker = "" if v else "  [BLANK]"
                    form_lines.append(
                        "[p%2s] %s  <%s> = %s%s"
                        % (r["page"] or "?", r["name"], r["ftype"], v, marker))

                form_out = None
                if outdir:
                    stem = os.path.splitext(fname)[0]
                    form_out = os.path.join(outdir, stem + ".forms.txt")
                    # R76: two same-named forms from different folders both dump now (F2),
                    # so the second output name gets the content hash - never a silent
                    # overwrite of the first copy's dump.
                    if os.path.exists(form_out):
                        form_out = os.path.join(outdir, "%s.%s.forms.txt" % (stem, digest))
                    with io.open(form_out, "w", encoding="utf-8") as f:
                        f.write("\n".join(form_lines))

                all_lines.append(
                    "%s  pg=%d widgets=%d filled=%d  engine=%s  agree=%s%%"
                    % (fname[:55], pages, len(primary_rows), len(filled),
                       engine, xc.get("agreement_pct", "-")))

                manifest["forms"].append({
                    "file": fname,
                    "path": fpath,
                    "forms_txt": form_out,
                    "sha8": digest,
                    "pages": pages,
                    "engine": engine,
                    "widgets_total": len(primary_rows),
                    "widgets_filled": len(filled),
                    "cross_engine": xc,
                })

    # Cross-check report
    if outdir:
        xc_lines = [
            "# Cross-engine agreement: fitz vs pypdf", "",
            "**value_divergent** = same field name, different value.", ""]
        for f in manifest["forms"]:
            xc = f["cross_engine"]
            xc_lines.append("## %s" % f["file"])
            if xc.get("agreement_pct") is not None:
                xc_lines.append(
                    "- agreement: **%s%%** (divergent: %s, shared: %s)"
                    % (xc["agreement_pct"], xc["value_divergent"], xc.get("shared")))
            elif not xc.get("fitz_available", True):
                xc_lines.append("- fitz not available; single-engine (pypdf)")
            elif not xc.get("pypdf_available", True):
                xc_lines.append("- pypdf not available; single-engine (fitz)")
            if xc.get("value_divergences"):
                xc_lines.append("")
                xc_lines.append("| widget | fitz | pypdf |")
                xc_lines.append("|---|---|---|")
                for dv in xc["value_divergences"][:30]:
                    xc_lines.append(
                        "| `%s` | `%s` | `%s` |"
                        % (dv["name"], str(dv["fitz"])[:60], str(dv["pypdf"])[:60]))
            xc_lines.append("")
        with io.open(os.path.join(outdir, "cross-check.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(xc_lines))

        # I-485 diff across copies
        i485_forms = [f for f in manifest["forms"]
                      if re.match(r"i-?485", f["file"], re.I)]
        if len(i485_forms) >= 2:
            _write_multi_copy_diff(i485_forms, outdir, "i485-diff.md")

        with io.open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)

    return {"manifest": manifest, "report_lines": all_lines}


def _write_multi_copy_diff(form_entries, outdir, filename):
    """Field-by-field diff across multiple copies of the same form type."""
    maps = {}
    for f in form_entries:
        # R76: the dump path is carried in the manifest - re-deriving it from the basename
        # broke the moment collision suffixes existed (F2 fix).
        form_file = f.get("forms_txt") or os.path.join(
            outdir, os.path.splitext(f["file"])[0] + ".forms.txt")
        if not os.path.exists(form_file):
            continue
        m = {}
        with io.open(form_file, encoding="utf-8") as fh:
            for line in fh:
                mm = re.match(r"\[p\s*\d+\] (\S+)\s+<[^>]*>\s*=\s*(.*)$", line.rstrip("\n"))
                if mm:
                    name, val = mm.groups()
                    val = val.replace("  [BLANK]", "").strip()
                    m[name] = val
        maps[f["file"]] = m
    if len(maps) < 2:
        return
    all_names = set().union(*(set(m) for m in maps.values()))
    divergent = []
    for n in sorted(all_names):
        vals = [maps[k].get(n, "__MISSING__") for k in maps]
        if len(set(vals)) > 1:
            divergent.append((n, vals))
    diff_lines = [
        "# Field-by-field diff across copies", "",
        "**%d divergent widgets** out of %d across %d copies."
        % (len(divergent), len(all_names), len(maps)), "",
        "| widget | " + " | ".join(maps.keys()) + " |",
        "|---" * (len(maps) + 1) + "|",
    ]
    for n, vals in divergent:
        diff_lines.append(
            "| `%s` | " % n + " | ".join("`%s`" % str(v)[:40] for v in vals) + " |")
    with io.open(os.path.join(outdir, filename), "w", encoding="utf-8") as f:
        f.write("\n".join(diff_lines))
