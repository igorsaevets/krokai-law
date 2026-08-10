# -*- coding: utf-8 -*-
"""`krokai upgrade` — bring THIS install to the latest release, whichever install layout it is.

WHY THIS IS A SUBCOMMAND AND NOT A DOCUMENTED PROCEDURE
--------------------------------------------------------
This toolkit ships in four shapes on purpose — a pip install, an editable pip install
(`pip install -e .` for developers), a git clone, and a folder the user has to copy because
the machine refuses `pip install`. Each has a different update command. Documenting four
commands and asking the user to pick invites the same failure as documenting "add this block
to settings.json": the wrong one is chosen and the mechanism goes silent.

One subcommand detects the layout and does the right thing.

THE ASSISTANT-FIRST FLOW
------------------------
If the user pastes the repository URL to an AI assistant and says "update this":

    python -m krokai upgrade           # if pip-installed or clone on PATH
    python <clone>/krokai upgrade      # from the clone directory

That is enough. `upgrade` reports the current version, the latest on PyPI, and the layout it
detected before it does anything, so the assistant can echo those facts to the user rather
than paraphrasing "updated successfully".

WHAT IT DOES
------------
- **pip layout** (non-editable install under `site-packages`/`dist-packages`): runs
  `pip install -U krokai`.
- **editable pip layout** (`pip install -e .` — detected via PEP 610 `direct_url.json`):
  treated as the underlying git clone if the source dir is a repo, else as copy.
- **git layout** (repository root has a `.git` folder or file, AND its `origin` remote
  points at the krokai-law repository): runs `git pull --ff-only` in that root, after a
  pre-flight of `git status --porcelain` and ahead/behind against upstream.
- **copy layout** (none of the above): prints how to re-copy the folder from GitHub and
  exits non-zero, because a copied folder is not an installer's problem to solve.

Then, if a `casefile.json` is reachable from the current directory, refreshes the hooks in
that matter — in a FRESH SUBPROCESS so the new post-upgrade code runs, not stale in-memory
0.x code. This is the T58 panel fix (Codex + Spark 11 + Spark 12 named it); the previous
version re-imported `krokai.install.main` in-process and would have silently written a stale
`settings.json` the first time a future release changed the hook shape.

Finally: prints the top entry from the CHANGELOG so the reader knows what changed.

ALWAYS SAFE ON FAILURE
----------------------
Every path that could fail (network to PyPI, git pull with local commits, pip on a PEP 668
externally-managed environment) exits non-zero and prints the exact command to run by hand.
The update tool never "repairs" a state it does not understand.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from . import __version__

__all__ = ["cmd_upgrade", "detect_layout", "pypi_latest"]

PYPI = "https://pypi.org/pypi/krokai/json"
CHANGELOG_URL = "https://raw.githubusercontent.com/igorsaevets/krokai-law/main/CHANGELOG.md"
KROKAI_REMOTE_MARKER = "krokai-law"

_HEADING_RE = re.compile(r"^##\s*\[(?P<v>[0-9][^\]]*)\]", re.M)


def _editable_source_dir():
    """If this install is a PEP 660 editable install, return its source directory.
    Else None. Uses PEP 610 `direct_url.json` — the authoritative signal, not a filesystem hint.
    """
    try:
        from importlib.metadata import distribution, PackageNotFoundError
    except Exception:
        return None
    try:
        dist = distribution("krokai")
    except Exception:
        return None
    try:
        raw = dist.read_text("direct_url.json")
    except Exception:
        return None
    if not raw:
        return None
    try:
        info = json.loads(raw)
    except ValueError:
        return None
    if not info.get("dir_info", {}).get("editable"):
        return None
    url = info.get("url") or ""
    if not url.startswith("file://"):
        return None
    path = urllib.parse.unquote(url[len("file://"):])
    # Windows: file:///C:/foo -> `/C:/foo`; strip the leading `/`.
    if os.sep == "\\" and re.match(r"^/[A-Za-z]:", path):
        path = path[1:]
    return os.path.normpath(path) if os.path.isdir(path) else None


def _remote_names_krokai(root):
    """True when the git repo at `root` has an origin remote naming krokai-law."""
    try:
        out = subprocess.check_output(
            ["git", "-C", root, "remote", "-v"], text=True, stderr=subprocess.STDOUT, timeout=8)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return KROKAI_REMOTE_MARKER in out.lower()


def _has_git_meta(root):
    """.git can be a directory (regular clone) or a plain-text file (worktree/submodule).
    Both are valid git repos. Codex T58 named this asymmetry.
    """
    p = os.path.join(root, ".git")
    return os.path.isdir(p) or os.path.isfile(p)


def detect_layout():
    """Return `(layout, root)` where layout is one of "pip" | "git" | "copy".

    Detection order matters. Editable-first stops the layout confusion Spark 11 named:
    an editable install whose source is a git checkout would otherwise `git pull` the
    developer's own tree. `site-packages` check is a PATH-COMPONENT test, not a substring,
    so `~/my-site-packages-project/krokai` does not misdetect as pip. Git-layout requires
    the remote to name `krokai-law`, so a copied folder placed inside an unrelated user
    repo cannot be `git pull`-ed.
    """
    # 1. PEP 660 editable install: authoritative via direct_url.json.
    src = _editable_source_dir()
    if src is not None:
        if _has_git_meta(src) and _remote_names_krokai(src):
            return "git", src
        return "copy", src

    here = os.path.dirname(os.path.abspath(__file__))     # .../krokai
    root = os.path.dirname(here)                          # site-packages OR clone root

    # 2. Non-editable pip install: path-COMPONENT check.
    parts = os.path.normpath(root).replace(os.sep, "/").lower().split("/")
    if "site-packages" in parts or "dist-packages" in parts:
        return "pip", root

    # 3. Git clone whose remote actually names krokai-law.
    if _has_git_meta(root) and _remote_names_krokai(root):
        return "git", root

    # 4. Everything else: unmanaged copy. Includes copy-inside-git-repo (safe: no pull).
    return "copy", root


def pypi_latest(timeout=15):
    """Latest krokai version on PyPI, or None if PyPI is unreachable.

    None is not a failure — it is a plain fact that gets printed. The layout tool (pip/git)
    asks its own registry when it runs, so the update itself does not depend on this probe.
    """
    try:
        with urllib.request.urlopen(PYPI, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("info", {}).get("version") or None
    except Exception:
        return None


def _top_changelog_from_text(txt):
    hits = list(_HEADING_RE.finditer(txt))
    if not hits:
        return None, ""
    end = hits[1].start() if len(hits) > 1 else len(txt)
    return hits[0].group("v"), txt[hits[0].end():end].strip()


def _read_changelog(root):
    """`(version, body)` of the topmost entry, from local clone if available, else GitHub raw."""
    p = os.path.join(root, "CHANGELOG.md")
    if os.path.isfile(p):
        try:
            return _top_changelog_from_text(io.open(p, encoding="utf-8", errors="replace").read())
        except OSError:
            pass
    try:
        with urllib.request.urlopen(CHANGELOG_URL, timeout=15) as r:
            return _top_changelog_from_text(r.read().decode("utf-8", "replace"))
    except Exception:
        return None, ""


def _git_preflight(root):
    """Return `(ok, message)`. When not ok, message tells the user what to fix.

    A bare `git pull --ff-only` prints a cryptic fatal for the same non-zero exit whether the
    tree is dirty, diverged, upstream is missing, or the network failed. Three panel channels
    named this; the fix is to enrich the diagnosis before touching the network.
    """
    try:
        dirty = subprocess.check_output(
            ["git", "-C", root, "status", "--porcelain"], text=True, timeout=8)
    except Exception as exc:
        return False, "git status failed: %s" % exc
    if dirty.strip():
        return False, ("your git checkout has uncommitted changes; refusing to pull.\n"
                       "  Fix:  cd \"%s\" && git stash push -m 'krokai pre-upgrade' && "
                       "krokai upgrade && git stash pop" % root)
    try:
        # left = commits on local not upstream, right = commits on upstream not local
        counts = subprocess.check_output(
            ["git", "-C", root, "rev-list", "--left-right", "--count", "HEAD...@{u}"],
            text=True, stderr=subprocess.STDOUT, timeout=8).strip().split()
        left, right = int(counts[0]), int(counts[1])
    except Exception:
        # No upstream configured, or a very old git — let the pull surface the error.
        return True, ""
    if left and right:
        return False, ("your branch has diverged from upstream by %d local and %d remote "
                       "commit(s). Refusing to fast-forward.\n"
                       "  Fix:  cd \"%s\" && git log --oneline HEAD..@{u}  (inspect); "
                       "then decide `git rebase` or `git reset --hard @{u}` explicitly."
                       % (left, right, root))
    if left:
        return False, ("your branch is %d local commit(s) ahead of upstream. `krokai upgrade` "
                       "will not merge or rebase.\n"
                       "  Fix:  push, or `git reset --hard @{u}` explicitly if the commits "
                       "were not meant to keep." % left)
    return True, ""


def _cmd_for(layout, root):
    if layout == "pip":
        return "%s -m pip install -U krokai" % sys.executable
    if layout == "git":
        return "git -C \"%s\" pull --ff-only" % root
    return "manual re-copy (see the printed instructions)"


def _run_update(layout, root):
    if layout == "pip":
        return subprocess.call([sys.executable, "-m", "pip", "install", "-U", "krokai"])
    if layout == "git":
        ok, msg = _git_preflight(root)
        if not ok:
            print("\n%s" % msg)
            return 1
        return subprocess.call(["git", "pull", "--ff-only"], cwd=root)
    return 1


def _refresh_hooks(a):
    """Re-run `install-hooks` so `settings.json` points at the freshly downloaded scripts.

    🔴 T58 panel fix: this runs in a FRESH SUBPROCESS, not by importing `krokai.install` in
    process. After `pip install -U`, the current interpreter still holds the OLD in-memory
    module objects — `sys.modules` does not reload from disk. For 0.7.7→0.8.0 the shape is
    unchanged so an in-memory call would have worked, but the first future release that
    renames a hook or changes the settings shape would silently write a stale settings.json.
    Codex + Spark 11 + Spark 12 + agy 36flash all named this. The subprocess spawn runs the
    new code by definition. Silently skipped if the current tree has no `casefile.json`.
    """
    from .config import find_config
    cfgp = find_config(getattr(a, "dir", None) or os.getcwd())
    if not cfgp:
        print("\nno casefile.json in the current tree — hooks were NOT refreshed.")
        print("Run  krokai install-hooks  from inside your matter to point the hooks at the "
              "new copy.")
        return
    matter = os.path.dirname(cfgp)
    print("\nrefreshing hooks in matter: %s" % matter)
    cmd = [sys.executable, "-m", "krokai", "install-hooks",
           "--scope", getattr(a, "scope", "project"), "--dir", matter]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        print("install-hooks exited %d. Run by hand:\n  %s" % (exc.returncode, " ".join(cmd)))


def cmd_upgrade(a):
    """The subcommand. Argparse args: `--dry-run`, `--skip-hooks`, `--scope`, `--dir`."""
    layout, root = detect_layout()
    latest = pypi_latest()

    # Report the facts BEFORE doing anything. An assistant that prints "updated successfully"
    # is exactly the failure mode this whole toolkit exists to prevent one level up; the
    # update subcommand does not get to make the same mistake.
    print("current install")
    print("  version : %s" % __version__)
    print("  layout  : %s" % layout)
    print("  root    : %s" % root)
    print("  pypi    : %s" % (latest or "unreachable"))
    if latest and latest == __version__:
        print("\nyou are already on the latest release.")

    if getattr(a, "dry_run", False):
        print("\n--dry-run: nothing was executed. The command that WOULD run:")
        print("  " + _cmd_for(layout, root))
        if not getattr(a, "skip_hooks", False):
            print("  (then krokai install-hooks in the current matter, out-of-process)")
        return 0

    if layout == "copy":
        print("\nThis install is not tracked by git or pip. To update:")
        print("  1. Download the latest ZIP:")
        print("     https://github.com/igorsaevets/krokai-law/archive/refs/heads/main.zip")
        print("  2. Unpack it and replace the contents of:")
        print("     %s" % root)
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        print("  3. Re-register the hooks in your matter:")
        print("     python \"%s\" install-hooks" % pkg_dir)
        return 1

    if latest and latest != __version__:
        print("\nupdating %s -> %s" % (__version__, latest))
    else:
        print("\nrefreshing the install")

    ret = _run_update(layout, root)
    if ret != 0:
        # Handle PEP 668: pip refuses on system Python of Debian 12+/Ubuntu 23.04+.
        if layout == "pip":
            print("\n🔴 If pip printed 'error: externally-managed-environment', this is a system "
                  "Python protected by PEP 668. Two safe options:")
            print("  a) `%s -m pip install -U --user krokai`  (user site)" % sys.executable)
            print("  b) install into a virtual environment: "
                  "`python -m venv .venv && .venv/bin/pip install -U krokai`")
        return ret

    v_top, body = _read_changelog(root)
    if v_top:
        print("\n--- what changed in %s ---" % v_top)
        for line in body.splitlines()[:40]:
            print(line)
        print("---")

    if not getattr(a, "skip_hooks", False):
        _refresh_hooks(a)

    print("\n🔴 hooks take effect at the NEXT session start, not this one.")
    return 0
