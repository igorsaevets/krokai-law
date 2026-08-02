# -*- coding: utf-8 -*-
"""`casefile.json` - the one file that makes this toolkit yours.

WHY A CONFIG FILE AND NOT CONSTANTS
------------------------------------
The system this was extracted from had absolute paths compiled into eleven scripts, including a
cloud-synced folder name and a person's user account. That is fine for one matter and impossible
for anyone else - and it is also how a script quietly writes into someone's live folder.

Everything location-shaped lives here. Nothing in the package knows the name of your matter, your
disk layout, or the body of law you practise.

DISCOVERY
---------
Walks up from the working directory looking for `casefile.json`, the way git finds `.git`. So a
hook fired from a subfolder finds the same configuration as a command run from the root, which
matters because a hook that silently uses different settings than the CLI is worse than no hook.
"""
from __future__ import annotations

import json
import os

__all__ = ["Config", "find_config", "load", "DEFAULTS", "TEMPLATE"]

CONFIG_NAME = "casefile.json"

DEFAULTS = {
    "sources": ["law"],
    "drafts": [{"tier": "A", "label": "filed, and what it rests on", "path": "case"},
               {"tier": "B", "label": "guides and checklists", "path": "guides"},
               {"tier": "C", "label": "research and outside reviews", "path": "research"}],
    "bank": "case/QUOTE-BANK.md",
    "queue": "case/QUOTE-QUEUE.md",
    "fabrication_register": "case/FABRICATION-REGISTER.md",
    "library_index": "law/INDEX.md",
    "citation_packs": ["us-federal"],
    "language": "en",
    "min_quote_length": 45,
    "drop_cyrillic_quotes": False,
    "cache_dir": None,
    "skip_dirs": [".git", "node_modules", "__pycache__", ".venv", "venv",
                  ".playwright-mcp", "archive", "_archive"],
    "guard_watch": ["case", "guides"],
    "guard_ignore": ["research", "archive", "_archive", ".claude", "answers"],
}

TEMPLATE = {
    "_doc": "Configuration for the lawverbatim legal-citation toolkit. Paths are relative to this file.",

    "_sources": "Folders holding PRIMARY SOURCES ONLY - statutes, regulations, decisions, agency "
                "manuals as published. 🔴 Never put your own analysis here: a quotation copied out "
                "of your own memo would then verify against your own memo, and a mistake made once "
                "would validate itself forever.",
    "sources": ["law"],

    "_drafts": "Your own writing, in tiers by what it costs to be wrong. Tier A is what gets filed. "
               "The tiers are reported separately so that noise in research notes can never flatter "
               "or alarm the numbers for the document that leaves the building.",
    "drafts": [
        {"tier": "A", "label": "filed, and what it rests on", "path": "case"},
        {"tier": "B", "label": "guides and checklists", "path": "guides"},
        {"tier": "C", "label": "research and outside reviews", "path": "research"}
    ],

    "_bank": "The quote bank: every quotation you have personally opened and confirmed.",
    "bank": "case/QUOTE-BANK.md",
    "_queue": "Written by the stop hook. A to-do list of quotations that appeared in an answer and "
              "are not in the bank yet. NOT a second bank - the decision stays yours.",
    "queue": "case/QUOTE-QUEUE.md",
    "_fabrication_register": "Confirmed fabrications, with which model produced each. Include your "
                             "own errors or the file is advertising, not statistics.",
    "fabrication_register": "case/FABRICATION-REGISTER.md",
    "_library_index": "One line per downloaded source. Checked BEFORE any web search.",
    "library_index": "law/INDEX.md",

    "_citation_packs": "Which bodies of law you cite. Run `lawverbatim packs` to list what ships.",
    "citation_packs": ["us-federal"],

    "language": "en",
    "min_quote_length": 45,
    "_drop_cyrillic_quotes": "Set true when you work in Russian but the law is in English: it stops "
                             "your own commentary being checked against a corpus of US statutes.",
    "drop_cyrillic_quotes": False,

    "cache_dir": None,
    "skip_dirs": DEFAULTS["skip_dirs"],
    "_guard_watch": "Folders the PostToolUse hook watches. Keep it to what actually gets filed: a "
                    "guard that fires on scratch notes gets ignored, and then it guards nothing.",
    "guard_watch": ["case", "guides"],
    "guard_ignore": ["research", "archive", "_archive", ".claude", "answers"],
}


def find_config(start=None):
    """Walk up from `start` looking for casefile.json. Returns the path or None."""
    d = os.path.abspath(start or os.getcwd())
    last = None
    while d != last:
        p = os.path.join(d, CONFIG_NAME)
        if os.path.exists(p):
            return p
        last, d = d, os.path.dirname(d)
    return None


class Config(object):
    def __init__(self, data, path):
        self.path = path
        self.root = os.path.dirname(os.path.abspath(path))
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in (data or {}).items() if not k.startswith("_")})
        self.data = merged

    def __getitem__(self, k):
        return self.data[k]

    def get(self, k, default=None):
        return self.data.get(k, default)

    def abs(self, rel):
        if not rel:
            return None
        return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(self.root, rel))

    @property
    def source_dirs(self):
        return [self.abs(p) for p in self.data["sources"]]

    @property
    def draft_tiers(self):
        """`[(tier, label, absolute_path), ...]` sorted by tier so A is always reported first."""
        out = []
        for d in self.data["drafts"]:
            out.append((d.get("tier", "?"), d.get("label", ""), self.abs(d["path"])))
        return sorted(out, key=lambda t: t[0])

    @property
    def cache(self):
        c = self.data.get("cache_dir")
        if c:
            return self.abs(c)
        import tempfile
        return os.path.join(tempfile.gettempdir(), "lawverbatim-corpus-cache")

    def missing_paths(self):
        """Configured folders that do not exist.

        Reported loudly rather than created silently. A source folder that is not there produces a
        corpus of zero files, and a corpus of zero files makes **every** quotation come back
        NOT FOUND - which reads like catastrophe and is really a typo in a path.
        """
        out = []
        for p in self.source_dirs:
            if not os.path.isdir(p):
                out.append(("sources", p))
        for _t, _l, p in self.draft_tiers:
            if not os.path.isdir(p):
                out.append(("drafts", p))
        return out


def load(start=None, required=True):
    p = find_config(start)
    if not p:
        if not required:
            return None
        raise SystemExit(
            "no %s found in this folder or any parent.\n"
            "Run:  lawverbatim init\n"
            "It writes a commented %s and the folder skeleton next to it." % (CONFIG_NAME, CONFIG_NAME))
    with open(p, encoding="utf-8") as fh:
        return Config(json.load(fh), p)
