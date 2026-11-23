# -*- coding: utf-8 -*-
"""The one place that imports PyMuPDF.

PyMuPDF's module has been called `pymupdf` since 1.24.3 (2024-05-09); `fitz` stayed as a
compatibility alias. Since 2.0 (2026-10-19) importing `fitz` raises a FutureWarning on every run,
and an alias that warns is an alias that will go. When it goes, an `import fitz` raises
ImportError - and every caller in this package reads ImportError as "PyMuPDF is not installed":
`doctor` would print PyMuPDF MISSING on a machine that has it, and the two-engine cross-check that
catches a word-splitting extraction would quietly drop to one engine (K001 S6, K003).

So the current name is tried first, and `fitz` only for an install older than 1.24.3, which the
`pymupdf>=1.24` requirement still admits. Trying `pymupdf` first also keeps an unrelated PyPI
package that happens to be called `fitz` from being loaded as the PDF engine.

Callers keep their own `except` clauses: anything other than ImportError propagates exactly as it
did from `import fitz`.
"""


def load():
    """Return the PyMuPDF module, or raise ImportError when it is not installed."""
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        import fitz
        return fitz
