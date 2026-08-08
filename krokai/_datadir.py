# -*- coding: utf-8 -*-
"""Find the data this package ships - `packs/`, `templates/`, `hooks/` - in BOTH install layouts.

🔴 WHY THIS FILE EXISTS. Three modules located their data by walking one level *up* out of the
package directory:

    krokai/citations.py   PACKS_DIR = <pkg>/../packs
    krokai/cli.py         ROOT      = <pkg>/..          -> ../templates/CLAUDE.md.snippet
    krokai/install.py     hooks_dir = <pkg>/../hooks

That is correct for a git clone, where `krokai/` and `packs/` are siblings, and it is wrong the
moment the package is installed: `<site-packages>/krokai/..` is `<site-packages>` itself, and
there is no `packs` directory there. The failure is silent rather than loud - `available_packs()`
returns `[]` when the directory is missing - so `pip install krokai` would have produced a tool
that starts, runs, reports success, and checks **nothing**. The count of citations it verified
would be zero and the output would not say so.

Both layouts are supported on purpose, so the resolver checks both rather than picking one:

  1. `<pkg>/<name>`     - the installed wheel. The build maps the top-level directories into the
                          package (see `force-include` in pyproject.toml), so the data travels
                          with the code and needs no `..`.
  2. `<pkg>/../<name>`  - the git clone, and the "copy the folder and run it" install that
                          `__main__.py` documents as supported for people who may not run pip.

The order matters. Package-internal wins, so an installed copy can never be silently served data
from an unrelated directory that happens to sit next to `site-packages`.
"""

import os

__all__ = ["data_dir", "data_file"]

_HERE = os.path.dirname(os.path.abspath(__file__))


def data_dir(name):
    """Absolute path to a shipped data directory. Returns the in-package path if neither
    candidate exists, so an error message names a stable location rather than a `..` chain."""
    inside = os.path.join(_HERE, name)
    beside = os.path.join(os.path.dirname(_HERE), name)
    if os.path.isdir(inside):
        return inside
    if os.path.isdir(beside):
        return beside
    return inside


def data_file(name):
    """Same search, for a single shipped file. `channels.json` is the one that needs it: its
    fallback path was `<pkg>/../channels.json`, so `krokai review` raised SystemExit on every
    installed copy while working perfectly from a clone."""
    inside = os.path.join(_HERE, name)
    beside = os.path.join(os.path.dirname(_HERE), name)
    if os.path.isfile(inside):
        return inside
    if os.path.isfile(beside):
        return beside
    return inside
