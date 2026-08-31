# -*- coding: utf-8 -*-
"""Detect and repair PDFs with broken text layers (PScript5 / Type 3 glyph substitution).

Some PDFs — typically saved through Windows virtual printers (PScript5.dll, old Adobe PostScript
drivers, or some LibreOffice PDF exports) — embed Type 3 fonts with no ToUnicode mapping. The
glyphs render visually correct, but the byte stream carries no relationship to Unicode: copying
text yields control characters or scrambled ASCII, and every text-based tool (search, AI parsers,
citation checkers) sees garbage.

Detection is cheap (pymupdf only). Repair needs heavier dependencies: rapidocr + numpy.
Both degrade gracefully when a dependency is missing — this follows the same pattern as the rest
of the package (see pyproject.toml header).
"""
from __future__ import annotations

import os
import sys


def _has_fitz():
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def _has_ocr():
    try:
        import numpy  # noqa: F401
        from rapidocr import RapidOCR  # noqa: F401
        return True
    except ImportError:
        return False


def _find_system_font(bold=False):
    """Locate a TrueType font file on the current platform. Returns None if not found."""
    if sys.platform == "win32":
        base = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        name = "arialbd.ttf" if bold else "arial.ttf"
        p = os.path.join(base, name)
        if os.path.isfile(p):
            return p
    elif sys.platform == "darwin":
        for candidate in ("/System/Library/Fonts/Helvetica.ttc",
                          "/Library/Fonts/Arial.ttf"):
            if os.path.isfile(candidate):
                return candidate
    else:
        for candidate in ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                          "/usr/share/fonts/TTF/DejaVuSans.ttf"):
            if os.path.isfile(candidate):
                return candidate
    return None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def is_broken_type3(path):
    """True when a PDF carries Type 3 fonts AND the text layer is mostly control characters.

    Type 3 fonts are not inherently broken — some PDFs use them correctly with a proper ToUnicode
    map. The combination of Type 3 AND a high control-character rate in the extracted text is the
    signal: the font draws the right glyphs, but the byte stream is a substitution cipher that no
    text tool can decode.

    Needs pymupdf (fitz). Returns False rather than raising when the dependency is missing.
    """
    if not _has_fitz():
        return False
    import fitz
    try:
        doc = fitz.open(path)
    except Exception:
        return False
    try:
        has_type3 = False
        for i in range(len(doc)):
            for fnt in doc[i].get_fonts():
                if fnt[1] == "Type3" or "Type3" in str(fnt[2]):
                    has_type3 = True
                    break
            if has_type3:
                break
        if not has_type3:
            return False
        text = doc[0].get_text() if len(doc) > 0 else ""
        ctrl = sum(1 for c in text if ord(c) < 32 and c not in "\r\n\t")
        return ctrl > 10
    finally:
        doc.close()


def scan_broken_pdfs(directory, skip_dirs=None):
    """Walk *directory* and return a list of ``(relative_path, absolute_path)`` for every
    PDF that looks like a broken PScript5/Type 3 document.

    *skip_dirs* is an iterable of directory basenames to skip (e.g. ``["Fixed_Broken_PDFs"]``).
    """
    if not _has_fitz():
        raise RuntimeError(
            "pymupdf (fitz) is required for PDF scanning.\n"
            "Install it:  pip install pymupdf   (or pip install \"krokai[pdf]\")")
    skip = set(skip_dirs or [])
    found = []
    from .corpus import walk_error
    for root, dirs, files in os.walk(directory, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for fn in files:
            if not fn.lower().endswith(".pdf"):
                continue
            full = os.path.join(root, fn)
            try:
                if is_broken_type3(full):
                    found.append((os.path.relpath(full, directory), full))
            except Exception:
                pass
    return found


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------

def _sanitize_ocr_text(text):
    """Clean OCR output: normalise whitespace, replace non-breaking spaces and soft hyphens."""
    out = []
    for c in text:
        o = ord(c)
        if o in (0xA0, 0x200B, 0x200E, 0x200F):
            out.append(" ")
        elif o in (0xAD, 0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015):
            out.append("-")
        elif 32 <= o <= 126 or c in "©®™№€£¥°±§«»—–" or ("Ѐ" <= c <= "ӿ"):
            out.append(c)
        else:
            out.append(" ")
    return "".join(out)


def fix_broken_pdf(src_path, dest_path, dpi=300, callback=None):
    """Repair a broken PScript5/Type 3 PDF by re-rendering and overlaying an OCR text layer.

    1. Each page is rendered at *dpi* resolution (300 = print quality, 150 = faster/smaller).
    2. RapidOCR (PP-OCRv6) extracts text with coordinates.
    3. A new PDF is built: the rendered image as the visual layer, invisible TrueType text on top.

    *callback*, if provided, is called as ``callback(page_num, total_pages, chars)`` after each
    page is processed.

    Returns ``(total_pages, total_chars)`` on success.
    Raises ``RuntimeError`` when a required dependency is missing.
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError("pymupdf (fitz) is required.  pip install pymupdf")
    try:
        import numpy as np
    except ImportError:
        raise RuntimeError("numpy is required.  pip install numpy")
    try:
        from rapidocr import RapidOCR
    except ImportError:
        raise RuntimeError(
            "rapidocr is required for PDF repair.\n"
            "Install it:  pip install rapidocr onnxruntime numpy")

    ocr = RapidOCR()
    font_path = _find_system_font(bold=False)

    doc_orig = fitz.open(src_path)
    doc_out = fitz.open()
    total_chars = 0
    total_pages = len(doc_orig)

    try:
        for page_num in range(total_pages):
            page_orig = doc_orig[page_num]
            rect = page_orig.rect
            pix = page_orig.get_pixmap(dpi=dpi)
            page_out = doc_out.new_page(width=rect.width, height=rect.height)
            page_out.insert_image(rect, pixmap=pix)

            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n)
            scale_x = float(rect.width) / float(pix.width)
            scale_y = float(rect.height) / float(pix.height)

            ocr_res = ocr(img_array)
            page_chars = 0

            if ocr_res.txts:
                for box, text, _score in zip(ocr_res.boxes, ocr_res.txts, ocr_res.scores):
                    if not text.strip():
                        continue
                    bx0 = float(min(p[0] for p in box)) * scale_x
                    by0 = float(min(p[1] for p in box)) * scale_y
                    bx1 = float(max(p[0] for p in box)) * scale_x
                    by1 = float(max(p[1] for p in box)) * scale_y
                    box_h = float(by1 - by0)
                    font_sz = float(max(5.0, min(40.0, box_h * 0.85)))
                    baseline_y = float(by1 - (box_h * 0.15))
                    clean = _sanitize_ocr_text(text)
                    pt = fitz.Point(bx0, baseline_y)
                    if font_path:
                        page_out.insert_text(pt, clean, fontsize=font_sz,
                                             fontfile=font_path, render_mode=3)
                    else:
                        page_out.insert_text(pt, clean, fontsize=font_sz,
                                             fontname="helv", render_mode=3)
                    page_chars += len(clean)

            total_chars += page_chars
            if callback:
                callback(page_num + 1, total_pages, page_chars)

        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        doc_out.save(dest_path, deflate=True)
    finally:
        doc_out.close()
        doc_orig.close()

    return total_pages, total_chars


def fix_batch(directory, output_dir, skip_dirs=None, dpi=300, log=None):
    """Scan *directory* for broken PDFs and fix them into *output_dir*, preserving subdirectory
    structure. Returns a list of ``(rel_path, pages, chars)`` for each fixed file.

    *log* is an optional callable that receives status strings.
    """
    _log = log or (lambda msg: None)
    broken = scan_broken_pdfs(directory, skip_dirs=skip_dirs)
    _log("Found %d broken PDF(s) to fix." % len(broken))
    results = []
    for rel, full in broken:
        dest = os.path.join(output_dir, rel)
        try:
            pages, chars = fix_broken_pdf(full, dest, dpi=dpi,
                                          callback=lambda p, t, c: _log(
                                              "  %s  page %d/%d: %d chars" % (rel, p, t, c)))
            _log("  OK -> %s (%d pages, %d chars)" % (dest, pages, chars))
            results.append((rel, pages, chars))
        except Exception as e:
            _log("  ERROR fixing %s: %s" % (rel, e))
    return results
