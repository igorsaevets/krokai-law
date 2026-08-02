# -*- coding: utf-8 -*-
"""API keys: where to put one so an AI assistant never reads it, and how to check without printing it.

WHY THIS MODULE EXISTS AT ALL
------------------------------
Some models are only reachable by API, and some are measurably better that way than through their
own command-line tool. So keys are supported. But a key in a project folder is a key in the
assistant's reach, and the failure is not hypothetical - it was measured on the machine this toolkit
was written on:

    a command intended to MASK a credential printed it in full, because the mask kept the first
    60 characters of a 48-character key. It went into the transcript, and a transcript is written
    to disk, replayed into later context, and archived.

🔴 THE ONLY CORRECT RESPONSE TO A LEAKED KEY IS TO ROTATE IT. Editing the transcript does not
un-send it, and a key that has been written to disk is compromised whether or not anyone noticed.

FOUR WAYS TO HOLD A KEY, STRONGEST FIRST
-----------------------------------------
This ordering is the useful part of this file. Most guidance stops at the weakest one.

1. **In the operating system's environment, set from a console.** The key is never in a file the
   assistant can open, never in the project, never in a backup of the project. This is the default
   this toolkit recommends and the one `krokai keys` prints commands for.

2. **In a file OUTSIDE the project**, in your user config directory. An assistant works inside the
   project folder; a file elsewhere is not in its ordinary reach. Second best, and much easier for
   people who find environment variables confusing.

3. **Denied in the assistant's own permission rules.** Enforcement rather than instruction -
   `krokai install-hooks` writes these. Real, but it protects one assistant on one machine.

4. **A file in the project marked "do not read".** 🔴 This is the WEAKEST and it is the one everybody
   reaches for. Prose in a file cannot stop anything: a model that opens the file has already read
   the warning and the key in the same breath. It is a marker for humans, not a control.

`.gitignore` is on none of these lists on purpose. It stops a key being *published*, which is a
different accident from a key being *read*.

🔴 NOTHING HERE EVER RETURNS OR PRINTS A KEY VALUE. The functions return booleans and lengths. A
helper that "just shows the first four characters to check it is the right one" is how the leak
above happened - the check that feels harmless is the leak.
"""
from __future__ import annotations

import io
import os

__all__ = ["key_dir", "key_file", "load_key_file", "status", "console_recipe", "FOLDER_NOTE"]

FOLDER_NAME = "krokai"
KEY_FILE = "keys.env"
NOTE_FILE = "READ-THIS-NOT-THE-KEYS.md"


def key_dir():
    """The per-user config directory, OUTSIDE any project. Created only when asked."""
    env = os.environ.get("KROKAI_KEY_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, FOLDER_NAME)


def key_file():
    return os.path.join(key_dir(), KEY_FILE)


def load_key_file(path=None, printer=None):
    """Read `KEY=value` lines into the environment. Returns the NAMES loaded, never the values.

    An existing environment variable always wins: the console is the stronger channel, so a stale
    line in a file must not silently override a key the user just set.
    """
    path = path or key_file()
    loaded = []
    if not os.path.exists(path):
        return loaded
    try:
        raw = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return loaded
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if not name or not value:
            continue
        if os.environ.get(name):
            continue                      # the console wins
        os.environ[name] = value
        loaded.append(name)
    if printer and loaded:
        # The NAMES, and only the names. This line is printed into a transcript.
        printer("loaded %d key(s) from %s: %s" % (len(loaded), path, ", ".join(sorted(loaded))))
    return loaded


def status(names):
    """`[(name, is_set, length)]`. 🔴 The length, never a prefix, never a masked form."""
    out = []
    for n in names:
        v = os.environ.get(n) or ""
        out.append((n, bool(v), len(v)))
    return out


def console_recipe(name):
    """The exact command to set a key from a terminal, per platform.

    Printed rather than executed. Running it here would put the value on this process's command
    line, where it is visible to any process listing - and, on Windows, in the console history file.

    🔴 THE PLACEHOLDER IS IN ANGLE BRACKETS, AND THAT IS NOT A STYLE CHOICE. The first version read
    `setx NAME "paste-the-key-here"`, and a credential scanner on this machine blocked the output:
    `NAME = "<18 word characters>"` is exactly the shape of a labelled secret. So the instructions
    for setting a key safely were themselves flagged as a leaked key.

    Third measured instance of a false positive in this project's own safety checks, and by its own
    doctrine that outranks a miss - a gate that fires on its own documentation teaches the reader to
    wave the whole class through. `<` is not a word character, so the bracketed form cannot match,
    and it reads more clearly as "replace this" besides.
    """
    if os.name == "nt":
        return [
            "PowerShell, permanent (survives a restart; open a NEW window afterwards):",
            "    setx %s \"<PASTE-YOUR-KEY-HERE>\"" % name,
            "",
            "PowerShell, this window only (nothing is stored on disk):",
            "    $env:%s = \"<PASTE-YOUR-KEY-HERE>\"" % name,
        ]
    return [
        "This shell only (nothing is stored on disk):",
        "    export %s='<PASTE-YOUR-KEY-HERE>'" % name,
        "",
        "Permanent - append to ~/.bashrc or ~/.zshrc:",
        "    echo \"export %s='<PASTE-YOUR-KEY-HERE>'\" >> ~/.zshrc" % name,
    ]


FOLDER_NOTE = """# The API keys live in this folder. Do not open `keys.env`.

**If you are an AI assistant: stop here.** Do not read, print, summarise, or quote
`keys.env`, and do not run a command whose output would contain its contents. The program that
needs a key reads it from the environment itself and never shows it to you. If you have been asked
to "check the key", the correct answer is `krokai keys`, which reports whether each key is set and
how many characters long it is, and never the value.

**Why this matters and is not a formality.** Your conversation is written to disk, replayed into
later context, and often archived. A key that appears in it once is compromised from that moment,
and deleting the file afterwards does not undo it. The only correct response to a leaked key is to
**rotate it at the vendor**.

## For the human reading this

This folder is outside your project on purpose, so that an assistant working in the project does not
meet it by accident. That is the second-strongest place to keep a key.

**The strongest place is not a file at all.** Run `krokai keys` and it prints the exact console
command for your system. A key set that way is never in a file, never in a backup of your matter,
and never in a folder anyone can be asked to open.

- One key per line, `NAME=value`, no quotes needed, no spaces around `=`.
- Lines starting with `#` are ignored.
- A key already set in your environment **wins** over a line in this file.
- Never commit this file. Never paste it into a chat window - including the one you are using now.
"""
