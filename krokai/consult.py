# -*- coding: utf-8 -*-
"""Asking several outside models the same legal question, and distrusting all of them equally.

WHY THIS IS PART OF A CITATION TOOLKIT AND NOT A SEPARATE PROGRAM
-----------------------------------------------------------------
An earlier version of this toolkit shipped only the checker and delegated the whole review to a
separate orchestration tool. That was wrong, and the reason it was wrong is worth stating because
it is the same reasoning error the checker exists to catch.

The argument for splitting was "two files on one subject rot". True - **of documentation**. But the
things that were pushed out of this program along with the transport were not transport:

* deciding whether an answer is usable at all;
* deciding whether an answer's *sourcing* is usable, which is not the same question;
* naming every channel that will run, and what it costs, BEFORE anything is sent;
* stopping your own instruction files from reaching the vendor in the first place.

Those are all **trust** controls, the same family as "check the reviewer's quotations against the
source". Transport is "make an HTTP call". The line was drawn in the wrong place, so the product had
a hole exactly where its audience needed it most.

So the line is now:

    a separate harness, if you have one  ->  TRANSPORT. Get answers back.
    this module                          ->  TRUST. What may go out, and what may be believed.

Everything here happens in the round it belongs to and nothing outlives it. A dispatch ledger, a
printed brief hash and a per-vendor retention column were each built and then cut - see the note
further down. The only durable artefacts are the answers and the report about them, both inside the
round's folder.

And when no harness is installed, this module carries its own transport for command-line channels,
because a feature that requires a second unpublished tool is a feature the reader does not have.

WHY THE DEFAULT CHANNELS NEED NO API KEY
-----------------------------------------
The audience is lawyers, paralegals and founders, who already pay for one or more AI subscriptions
and generally do not have API keys - and should not be talked into getting one. A subscription is
several times cheaper for the same model, cannot run up an unplanned bill, and is one fewer
credential to leak. So the shipped channels are command-line tools driven over stdin, and the one
metered kind ships disabled with a warning.

🔴 THE VERDICT READS STRUCTURED FIELDS, NEVER PROSE
----------------------------------------------------
The system this was extracted from graded channels by searching their warning text for tell-tale
substrings, and it cost twice:

* the word ``refusal`` marked FAILED the exact behaviour the brief asks for - an honest "my search
  found no confirmation" is the second-best outcome, better than anything but a verified quote;
* ``not set`` matched the substantive finding "the regulation does not set a deadline", and
  ``truncated`` matched the good catch "the firm's version drops the condition".

Every one of those is an ordinary English word a reviewer may legitimately use *about the law*. The
fix there was a careful list of distinctive strings, which works until someone adds a message. The
fix here is structural: transports emit **machine codes** in ``failures`` and ``quality``, and the
grader never reads prose at all. A code cannot collide with English.
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

# Imported at module level, not inside a handler: a scrub that has to be imported while an
# exception is being formatted is a scrub that is skipped exactly when it matters.
from ._datadir import data_file
from .redact import scrub

__all__ = ["load_registry", "plan", "run_round", "triage", "grounding_of",
           "write_analytics", "REGISTRY_NAME"]

REGISTRY_NAME = "channels.json"

# A round is FAILED on any of these. They are codes, not sentences, and nothing outside this file
# is allowed to invent one: an unknown code prints as itself and grades DIRTY, never silently OK.
FAILURE_MEANING = {
    "BINARY_NOT_FOUND": "the command-line tool for this channel is not installed on this machine",
    "TIMED_OUT": "no answer within the timeout; a deep review can legitimately run 25-40 minutes",
    "EMPTY_ANSWER": "the channel returned nothing at all",
    "NO_END_MARKER": "the answer does not end with the required marker, so it is PARTIAL - a "
                     "truncated answer reads as a complete one and its last section is missing",
    "TOO_SHORT": "far below the floor for a real review; usually a refusal or a crash",
    "TRANSPORT_ERROR": "the call itself failed",
    "KEY_NOT_SET": "this channel needs an environment variable that is not set - run `krokai keys`",
    "MODEL_NOT_SET": "this channel has no model pinned, and guessing one fails at the vendor with a "
                     "message that does not say so",
    "HTTP_ERROR": "the endpoint answered with an error status",
    "POLICY_REFUSAL": "the channel declined to engage with the subject, and produced no review",
}

# A round is DIRTY on any of these: readable, but do not repeat anything from it unchecked.
#
# 🔴 THE NAMES SAY "CITED", NEVER "GROUNDED". Two independent reviewers attacked the same mechanism
# and both were right: a URL printed in an answer is produced by the same process that produces a
# fabricated quotation, so it is not an independent signal. A model that invents an [OPENED] tag
# about itself will invent a URL, and knowing that a primary source ends in `.gov` is exactly the
# knowledge needed to mint a plausible one. Calling the count "grounding" manufactures corroboration
# out of the model's own assertion - which is the failure this whole toolkit exists to prevent, one
# level down. The counts are kept, because what an answer ASKS YOU TO RELY ON is worth knowing; the
# word that implied retrieval is gone.
QUALITY_MEANING = {
    "GOV_LOOKALIKE_CITED": "cites a host that wears an official label (`gov`, `mil`) - or the NAME "
                           "of one of your configured official sources (`uscis`, `ecfr`) - as a "
                           "whole part of its name, while NOT ending in any official suffix you "
                           "have configured. Two things look like this and both need a human: a "
                           "domain impersonating a government site, and a real government whose "
                           "suffix is missing from `grounding.primary` in channels.json",
    "DATED_EDITION_CITED": "cites an ANNUAL EDITION. That IS official law - a dated codification, "
                           "not a lesser source - but it is not the text in force, and it sits on "
                           "a government domain, so an 'is this official?' check passes it happily",
    "COMMENTARY_CITED": "cites commentary - firm blogs, aggregators, news. Fine as a lead, not as "
                        "the source of a legal position",
    "NO_URLS_CITED": "no source URL anywhere in the answer, so nothing in it can be checked "
                     "mechanically. Not proof of invention; proof that you cannot verify it yet",
    "NO_TELEMETRY": "this channel reports nothing about which pages it opened. The URL counts here "
                    "are therefore what the answer PRINTED, and printing is not opening",
    "SEARCH_NOT_USED": "the channel had search available and issued none, so its answer is recall",
}

# Codes that describe the INSTRUMENT rather than the answer. They are reported and printed; they do
# not grade. See the docstring of `triage` for the measurement that separated them.
INSTRUMENT_ONLY = {"NO_TELEMETRY"}

_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]\},;]+", re.I)

# A policy refusal, not an honest "I could not confirm this". The distinction is the whole point:
# the brief explicitly asks for the second, so detecting it as a fault would penalise the behaviour
# being paid for. These shapes are about the MODEL declining, never about the LAW being silent.
_REFUSAL_RE = re.compile(
    r"(?i)\b(?:i (?:can'?t|cannot|am unable to|won'?t) (?:help|assist|provide|continue|comply)"
    r"|i'?m (?:not able|unable) to (?:help|assist|provide)"
    r"|(?:this|that) (?:request|content) violates"
    r"|against my (?:guidelines|policies)"
    r"|i must decline)\b")


# =================================================================================================
# Registry
# =================================================================================================

def load_registry(explicit=None, start=None):
    """Find and load `channels.json`. Explicit path, then next to casefile.json, then shipped.

    The shipped copy is the fallback, never the override: a registry the user has edited for their
    own machine must win over the one that came with the download, or their edit silently does
    nothing and they conclude the tool is broken.
    """
    tried = []
    if explicit:
        tried.append(explicit)
    if start:
        tried.append(os.path.join(os.path.dirname(os.path.abspath(start)), REGISTRY_NAME))
    cwd = os.path.abspath(start or os.getcwd())
    while True:
        tried.append(os.path.join(cwd, REGISTRY_NAME))
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    # The shipped copy, and it stays LAST so a user's own edit still wins. Was
    # `<pkg>/../channels.json`, i.e. `site-packages/channels.json` in an installed copy, which
    # never exists - so `krokai review` raised SystemExit for every pip user while working from a
    # clone. data_file() checks inside the package first, then beside it. See _datadir.py.
    tried.append(data_file(REGISTRY_NAME))
    for p in tried:
        if p and os.path.exists(p):
            with io.open(p, encoding="utf-8") as f:
                data = json.load(f)
            data["_loaded_from"] = p
            return data
    raise SystemExit("no %s found; looked in:\n  %s" % (REGISTRY_NAME, "\n  ".join(tried)))


def _expand(p):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(p)))


def find_harness(reg, explicit=None):
    """Locate a separate review harness. Absence is 'not installed here', never 'does not exist'.

    🔴 R77 (#342, agy37flash): the returned path is ABSOLUTE. A relative `--harness` was tested
    against the launch directory and then executed after `neutral_cwd()` had changed it - so the
    same path existed at the check and did not exist at the call, and the round died between the
    two with a "file not found" pointing at a file the user could see.
    """
    ch = (reg.get("channels") or {}).get("harness") or {}
    if explicit:
        return os.path.abspath(explicit) if os.path.exists(explicit) else None
    env = os.environ.get(ch.get("env") or "KROKAI_REVIEW_HARNESS")
    if env and os.path.exists(env):
        return os.path.abspath(env)
    for c in ch.get("candidates") or []:
        p = _expand(c)
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def _bin_path(ch):
    """Resolve a channel's binary. Returns the resolved path or None."""
    import shutil
    env = ch.get("bin_env")
    if env and os.environ.get(env):
        cand = _expand(os.environ[env])
        return cand if os.path.exists(cand) else None
    return shutil.which(ch.get("bin") or "")


def channel_items(reg):
    """Every real channel. One place, because there are five loops over this dictionary.

    🔴 Skips `_`-prefixed keys and anything that is not a mapping. This file's own convention is
    that an underscore key is documentation, and the first version put a prose note inside
    `channels` - so every loop over it crashed on a string. The convention is not the bug; five
    loops each re-deciding what a channel is, was.
    """
    for name, ch in (reg.get("channels") or {}).items():
        if name.startswith("_") or not isinstance(ch, dict):
            continue
        yield name, ch


def selected(reg, only=(), skip=(), with_disabled=False):
    """Which channels this round would use, honouring enabled/--only/--skip."""
    out = {}
    for name, ch in channel_items(reg):
        if ch.get("kind") == "delegate":
            continue
        if only and name not in only:
            continue
        if name in (skip or ()):
            continue
        if not ch.get("enabled") and not with_disabled and name not in (only or ()):
            continue
        out[name] = ch
    return out


# =================================================================================================
# The plan, printed BEFORE anything is spent or sent
# =================================================================================================

def plan(reg, chosen, harness=None, delegating=None, allow_pii=False, printer=print):
    """Print exactly what will happen. Returns the list of blocking problems.

    A plan is not decoration. Every paid channel in this design prints its resolved settings before
    it spends anything, because the failure this prevents - discovering after the bill that the
    round ran with the wrong model, or that a channel was not installed at all - cannot be undone by
    reading a log afterwards.
    """
    problems = []
    printer("")
    printer("PLAN  (nothing has been sent yet)")
    printer("  registry: %s" % reg.get("_loaded_from"))
    if delegating is None:
        delegating = bool(harness)
    if harness and delegating:
        printer("  harness:  %s" % harness)
    elif harness:
        # 🔴 Not the same sentence as "none installed". Telling a user their harness is absent when
        # they switched it off with a flag sends them looking for an installation problem that does
        # not exist.
        printer("  harness:  installed but IGNORED for this run (--no-harness): %s" % harness)
    else:
        printer("  harness:  none installed here - using the built-in command-line transports")
    printer("")
    printer("  %-9s %-4s %-12s %-6s %-13s %s" %
            ("channel", "on?", "vendor", "how", "cost", "installed"))
    will_run = []
    for name, ch in sorted(chosen.items()):
        ready, why = "yes", ""
        kind = ch.get("kind")
        if kind == "cli":
            if not _bin_path(ch):
                ready, why = "NO", "`%s` not on PATH" % ch.get("bin")
                problems.append((name, why))
        elif kind == "http":
            if not resolve_base(ch):
                ready, why = "NO", "%s not set" % (ch.get("base_url_env") or "base_url")
                problems.append((name, why))
            elif not resolve_key(ch)[0]:
                # The variable NAME, so the user knows what to set. Never a hint about the value.
                ready, why = "NO", "%s not set" % (ch.get("key_env") or "key")
                problems.append((name, why))
            elif (ch.get("model") or "set-me") == "set-me":
                ready, why = "NO", "pin `model` in channels.json"
                problems.append((name, why))
        # 🔴 "switched on" and "installed" are two independent facts, and collapsing them is how a
        # plan lies. A channel disabled in the registry does not run even though its binary is
        # present - and the first draft of this table printed that case as `ready: yes`, which any
        # reader takes to mean "will run".
        on = "on" if ch.get("enabled") else "off"
        if ch.get("enabled") and ready == "yes":
            will_run.append(name)
        printer("  %-9s %-4s %-12s %-6s %-13s %s %s" % (
            name, on, (ch.get("vendor") or "-")[:12], kind, ch.get("cost") or "-", ready, why))
    printer("")
    runners = sorted(will_run)
    if harness and delegating:
        runners = ["harness -> " + os.path.basename(harness)] + runners
    printer("  will run: %s" % (", ".join(runners) or "NOTHING"))

    metered = [n for n in will_run if chosen[n].get("cost") == "metered"]
    if metered:
        printer("  🔴 METERED and will run: %s. These bill per call." % ", ".join(sorted(metered)))
    if allow_pii:
        printer("  🔴 --allow-pii is on: personal identifiers WILL leave this machine.")

    # 🔴 THE RISK THIS FEATURE CREATES, named where it is incurred. Raised by a reviewer of this
    # very design: asking N models the same question multiplies the confidentiality exposure by N.
    # Each vendor gets the whole payload, each keeps it under its own policy, and a breach at any
    # one of them is a breach of the lot.
    #
    # It is said here rather than in the documentation because a warning in a README is read once
    # and a warning in the plan is read every time - which is this project's oldest measurement:
    # rules fire by topic, not by rule.
    n = len(runners)
    if n > 1:
        printer("  ⚠️  %d independent vendors will each receive this material in full." % n)
        printer("     Multiplying the opinions multiplies the exposure. If one is breached, the")
        printer("     material is out. Nothing downstream can undo that, so decide it here.")
    printer("")
    return problems


# =================================================================================================
# Transports. Each returns the same shape; each emits CODES, never prose the grader must parse.
# =================================================================================================

def _result(name, **kw):
    r = {"channel": name, "text": "", "seconds": None, "bytes": 0, "exit": None,
         "failures": [], "quality": [], "telemetry": None}
    r.update(kw)
    return r


def _finish(r, marker, floor):
    text = r.get("text") or ""
    r["bytes"] = len(text.encode("utf-8"))
    if not text.strip():
        r["failures"].append(("EMPTY_ANSWER", ""))
        return r
    if marker and not text.strip().endswith(marker):
        r["failures"].append(("NO_END_MARKER", "expected the last line to be %r" % marker))
    if len(text.strip()) < floor:
        r["failures"].append(("TOO_SHORT", "%d chars, floor is %d" % (len(text.strip()), floor)))
    m = _REFUSAL_RE.search(text)
    if m:
        # A refusal that still produced a full-length answer is a caveat, not a failure. Only a
        # refusal INSTEAD of a review is a failure - and `TOO_SHORT` above has already fired then.
        code = "POLICY_REFUSAL" if len(text.strip()) < floor * 2 else None
        if code:
            r["failures"].append((code, "at %r" % text[max(0, m.start() - 30):m.end() + 30]))
    return r


def call_cli(name, ch, payload, marker, workdir, floor, timeout, printer=print):
    binary = _bin_path(ch)
    if not binary:
        return _result(name, failures=[("BINARY_NOT_FOUND", ch.get("bin") or "?")])
    os.makedirs(workdir, exist_ok=True)
    outfile = os.path.join(workdir, name.upper() + ".md")
    prompt_file = os.path.join(workdir, "prompt.txt")
    if ch.get("prompt") == "file":
        io.open(prompt_file, "w", encoding="utf-8", newline="\n").write(payload)

    subs = {"workdir": workdir, "outfile": outfile, "prompt_file": prompt_file}
    argv = [binary] + [a.format(**subs) for a in (ch.get("argv") or [])]
    if ch.get("model"):
        argv += ["-m", ch["model"]]

    t0 = time.time()
    try:
        p = subprocess.run(
            argv,
            input=payload.encode("utf-8") if ch.get("prompt") == "stdin" else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except FileNotFoundError:
        return _result(name, failures=[("BINARY_NOT_FOUND", binary)])
    except subprocess.TimeoutExpired:
        return _result(name, seconds=round(time.time() - t0, 1),
                       failures=[("TIMED_OUT", "%ds" % timeout)])
    except Exception as exc:                                        # noqa: BLE001
        # 🔴 SCRUBBED, and the truncation is not what protects it. An exception's own message is
        # untrusted text: a spawn failure names the command line, and a command line can carry a
        # credential. This project measured the same thing in its parent - `diagnostics.json` was
        # clean while an exception message printed a key in full to the console, which is the same
        # archived, replayed surface. And `[:200]` is a cut, not a mask: the gate's own docstring
        # records a 60-character "mask" that kept a 48-character key whole.
        return _result(name, failures=[("TRANSPORT_ERROR", scrub(repr(exc))[:200])])

    text = ""
    if os.path.exists(outfile):
        text = io.open(outfile, encoding="utf-8", errors="replace").read()
    if not text.strip():
        text = (p.stdout or b"").decode("utf-8", "replace")
    r = _result(name, text=text, seconds=round(time.time() - t0, 1), exit=p.returncode)
    if p.returncode != 0 and not text.strip():
        # 🔴 The exit code is checked, but it is NOT trusted on its own. Measured on two separate
        # CLIs: one exits 0 having discarded the entire run, the other exits 0 on a hard HTTP 400.
        # The answer is the evidence; the exit code is a hint about where to look.
        # A channel CLI that fails often echoes its own argv, and this text is recorded and
        # printed. Scrubbed for the same reason as the branch above; measured with a probe that
        # made a subprocess write an assembled key to stderr.
        r["failures"].append(("TRANSPORT_ERROR",
                              "exit %d: %s" % (p.returncode,
                                               scrub((p.stderr or b"").decode("utf-8", "replace"))[:200])))
    if not ch.get("telemetry"):
        r["quality"].append(("NO_TELEMETRY", ""))
    return _finish(r, marker, floor)


def resolve_key(ch):
    """Return `(value, variable_name)`. The caller may print the NAME; never the value.

    Every helper here that touches a credential is written so the useful thing to log - which
    variable supplied it - is a different object from the thing that must never be logged.
    """
    for var in (ch.get("key_env"), ch.get("key_env_fallback")):
        if var and os.environ.get(var):
            return os.environ[var], var
    return "", (ch.get("key_env") or "")


def resolve_base(ch):
    return (ch.get("base_url") or os.environ.get(ch.get("base_url_env") or "") or "").rstrip("/")


def call_http(name, ch, system, brief, marker, floor, timeout, printer=print):
    """One API reviewer. Two request shapes, because the market uses two.

    `chat`     - OpenAI-style `/chat/completions`; the system prompt is a message.
    `messages` - Anthropic-style `/messages`; the system prompt is its OWN top-level field and the
                 answer is a LIST of content blocks.

    🔴 Sending the second in the first's shape does not fail loudly. The system prompt is dropped as
    an unrecognised field and the reply comes back looking complete - so a review whose entire
    framing was discarded reads exactly like a good one. That is why the shape is declared per
    channel in the registry instead of guessed from the URL.
    """
    import urllib.request
    import urllib.error

    base = resolve_base(ch)
    key, key_var = resolve_key(ch)
    if not base or not key:
        missing = []
        if not base:
            missing.append(ch.get("base_url_env") or "base_url")
        if not key:
            missing.append(key_var or "a key variable")
        return _result(name, failures=[("KEY_NOT_SET", ", ".join(missing))])

    model = ch.get("model") or ""
    if not model or model == "set-me":
        # Not a crash and not a default. A guessed model identifier is a hard failure at the vendor
        # with a confusing message; naming the omission here is the cheaper error.
        return _result(name, failures=[("MODEL_NOT_SET", "set `model` for this channel")])

    headers = {"Content-Type": "application/json"}
    if (ch.get("api") or "chat").lower() == "messages":
        url, shape = base + "/messages", "messages"
        payload = {"model": model, "max_tokens": int(ch.get("max_tokens") or 32000),
                   "system": system, "messages": [{"role": "user", "content": brief}]}
        headers["x-api-key"] = key
        headers["anthropic-version"] = ch.get("anthropic_version") or "2023-06-01"
    else:
        url, shape = base + "/chat/completions", "chat"
        payload = {"model": model,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": brief}]}
        headers["Authorization"] = "Bearer " + key

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        # 🔴 The status and reason are reported. The request is NOT: it carries the key in a header,
        # and an exception handler that dumps the request is exactly how a credential reaches a log.
        # Measured once on the machine this was written on, from a command whose PURPOSE was masking.
        return _result(name, seconds=round(time.time() - t0, 1),
                       failures=[("HTTP_ERROR", "%s %s" % (exc.code, exc.reason))])
    except Exception as exc:                                        # noqa: BLE001
        return _result(name, failures=[("TRANSPORT_ERROR", type(exc).__name__)])

    text = ""
    try:
        if shape == "messages":
            text = "".join(b.get("text") or "" for b in (data.get("content") or [])
                           if isinstance(b, dict) and b.get("type") == "text")
        else:
            text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return _result(name, failures=[("TRANSPORT_ERROR", "unparseable response body")])
    r = _result(name, text=text, seconds=round(time.time() - t0, 1),
                telemetry={"usage": data.get("usage")})
    if not ch.get("telemetry"):
        r["quality"].append(("NO_TELEMETRY", ""))
    return _finish(r, marker, floor)


# Files this module writes into the round folder itself. Anything else that appears is an answer.
_OURS = {"brief.md", "system.md", "analytics.md", "run.log"}


def absorb_delegated(out_dir, marker, floor, since=None):
    """Grade and record the answers a delegated harness produced.

    🔴 THIS FUNCTION EXISTS BECAUSE THE FIRST LIVE ROUND EXPOSED THE HOLE IT FILLS. With a harness
    installed the built-in transports correctly stand down - and the analytics printed
    `OK 0 · DIRTY 0 · FAILED 0` over four real answers. So in the most common configuration, the
    layer that claims to be the trust layer saw nothing and said so in a format that read like a
    clean result.

    No amount of re-reading found that. Running it did, on the first attempt, which is the whole
    argument for testing a review tool by reviewing something real with it.

    The grading is deliberately the SAME code as for the built-in transports. A trust layer that
    judged its own transports more strictly than a delegate's would be measuring the transport, not
    the answer.
    """
    rows, stale = [], []
    for fn in sorted(os.listdir(out_dir)):
        if not fn.lower().endswith(".md") or fn.lower() in _OURS:
            continue
        path = os.path.join(out_dir, fn)
        if not os.path.isfile(path):
            continue
        # 🔴 R77 (#341, kimik3/codex/lunapro): only answers WRITTEN BY THIS DISPATCH are graded.
        # A reused output folder held last round's answers, and they were absorbed as this
        # round's - a stale answer to an old brief read as a fresh voice agreeing. The margin
        # absorbs filesystem mtime granularity; the skip is printed, because a silently ignored
        # file in an answers folder is how the opposite defect starts.
        try:
            if since and os.path.getmtime(path) < since:
                stale.append(fn)
                continue
        except OSError:
            pass
        text = io.open(path, encoding="utf-8", errors="replace").read()
        r = _result(os.path.splitext(fn)[0].lower(), text=text)
        # The delegate reports its own telemetry in its own format; this layer does not parse it.
        # Saying "not measured here" is honest. Saying "0" would not be.
        r["quality"].append(("NO_TELEMETRY", "graded from the answer; the harness keeps its own"))
        rows.append(_finish(r, marker, floor))
    if stale:
        print("  skipped %d file(s) already in the folder BEFORE this dispatch (a previous "
              "round's answers): %s" % (len(stale), ", ".join(stale)))
    return rows


def call_delegate(harness, brief_path, system_path, out_dir, marker=None, extra=(), printer=print):
    """Hand the round to a separate harness.

    🔴 The marker is passed through, and forgetting it is not cosmetic. A harness that checks for
    its own default marker while the brief asks for a different one flags every complete answer as
    truncated - so a clean round reads as a total failure, and the obvious next move is to re-run
    it and pay twice. Caught here before the first real round, by reading the harness's own
    defaults rather than assuming they matched.
    """
    cmd = [sys.executable, harness, "--brief", brief_path, "--system", system_path,
           "--out", out_dir]
    if marker:
        cmd += ["--marker", marker]
    cmd += list(extra)
    printer("  delegating: %s" % " ".join(cmd))
    try:
        return subprocess.call(cmd)
    except Exception as exc:                                        # noqa: BLE001
        printer("  the harness could not be run: %s" % scrub(repr(exc)))
        return 1


# =================================================================================================
# Reading the answer: what did it stand on?
# =================================================================================================

# Labels that make a host look like the state speaking. A host carrying one of these as a WHOLE
# label - or as a whole hyphen-separated part of a label - while NOT ending in any configured
# official suffix is one of two things, and both deserve a human: a domain impersonating a
# government site, or a real government you have not configured.
#
# Whole-part, never substring. That distinction is the entire fix: `mil` inside `milano.it` is the
# first syllable of an Italian city, and `gov` inside `uscisdhs-gov.us` is a hyphen-delimited part
# doing impersonation work. A substring test cannot tell them apart and graded both as official law.
OFFICIAL_TOKENS = ("gov", "mil", "govt", "gouv", "gob", "govuk")


def host_of(u):
    """The bare host of a URL, lower-cased: no scheme, no credentials, no port, no trailing dot.

    Every one of those strippings is a documented parser bypass that would otherwise walk past a
    suffix test. `https://www.uscis.gov[@]evil.example/` has host `evil.example` - the real name sits
    to the LEFT of the `@`, where a naive split reads it as the host. (The `@` is bracketed here on
    purpose: written plainly, that example is email-shaped, and the outbound gate two modules over
    blocks it. Fifth measured instance of a detector firing on the documentation of the very thing
    it detects - and the cheap fix is always to change the DOCUMENT, never to teach the gate an
    exception, because an exception is what the reader learns to reach for next time.)
    `uscis.gov.` with a trailing
    root dot is the same name to every resolver and a different string to `endswith`. OWASP's Web
    Security Testing Guide lists `@`, `#` and percent-encoding among the standard evasions:
    https://owasp.org/www-project-web-security-testing-guide/stable/ (retrieved 2026-08-02).

    🔴 The parsing is delegated, not hand-rolled, and that was a review finding rather than my own
    judgement. `urlsplit().hostname` already lowercases, drops userinfo and the port, and unwraps an
    IPv6 literal - and it has been maintained against these evasions for longer than this file has
    existed. The manual path below survives only as a fallback for a string `urlsplit` refuses, and
    for a bare `host/path` with no scheme, where `.hostname` is None.
    """
    from urllib.parse import urlsplit
    s = (u or "").strip()
    try:
        h = urlsplit(s).hostname or ""
    except ValueError:                          # malformed IPv6 literal, bad port, and the like
        h = ""
    if not h:
        h = s.lower().split("//", 1)[-1].split("/", 1)[0]
        h = h.split("@")[-1].split("?")[0].split("#")[0]
        h = h.split("]", 1)[0].lstrip("[") if h.startswith("[") else h.split(":", 1)[0]
    return h.lower().rstrip(".")


def suffix_match(host, entry):
    """Label-anchored suffix test: `.gov` matches `uscis.gov` and NOT `uscis.gov.ru`.

    🔴 THIS REPLACES A SUBSTRING TEST, AND THE SUBSTRING TEST WAS THE WORST BUG THIS FILE HAS HAD.
    The old line was ``host.endswith(s) or s in host``, and the second half of that disjunction
    graded these as OFFICIAL PRIMARY LAW, measured by execution:

        www.milano.it        `.mil` is inside `milano`
        uscis.gov.ru         `.gov` is a label, the domain is Russian
        law.gov.cn           same shape
        www.mil.kg           same shape
        ecfr.i0.gov.cm       same shape

    `primary` is the strongest endorsement this tool can give a URL - it is the bucket that means
    "this is the law itself". Handing it to any host containing the three letters `gov` anywhere is
    worse than having no classifier: a wrong answer with an official-looking citation is the exact
    artefact the whole toolkit exists to catch, one level down.
    """
    e = (entry or "").lower().strip().lstrip(".")
    return bool(e) and (host == e or host.endswith("." + e))


def agency_labels(primary):
    """The names of the specific official bodies configured in `primary` - `uscis.gov` -> `uscis`.

    🔴 The `gov`/`mil` token test has a measured blind spot, found in a sister project the day
    after that test shipped: `uscis.com` - the EXACT agency name in a foreign zone, not a typo -
    walks straight past it, because it wears no official label at all. The only thing that can
    catch that shape is knowing the names you actually rely on, and those names arrive here two
    ways: specific domains a user adds to `grounding.primary`, and the `official_domains` a
    citation pack declares (merged in by `krokai review`).

    Only the FIRST label of a multi-label entry, and only when it is 3+ characters: deriving every
    label would turn `uscode.house.gov` into a claim over `house.com`, and two-letter fragments
    like `us` match half the internet. Three letters stay in because `irs` does - `irs.com` is a
    live commercial site that is not the agency, and a floor of four would have exempted the most
    impersonated name in the whole list; a control caught exactly that. Names that are also
    English words are a pack decision, not a floor decision - see `official_domains` in the
    immigration pack for the one that was left out on purpose. Generic single-suffix entries
    (`.gov`) contribute nothing here by construction.
    """
    out = set()
    for e in (primary or []):
        e = (e or "").lower().strip().lstrip(".")
        # A user who configures `www.uscis.gov` means uscis.gov. The first draft SKIPPED such an
        # entry entirely - `www` was filtered but nothing looked past it, so the one domain the
        # user most explicitly typed taught the detector nothing. Found by an outside review,
        # confirmed by execution.
        if e.startswith("www."):
            e = e[4:]
        if "." not in e:
            continue                        # ".gov" -> "gov": a suffix, not a name
        first = e.split(".")[0]
        if len(first) >= 3 and first not in OFFICIAL_TOKENS and first != "www":
            out.add(first)
    return out


def gov_lookalike(host, primary):
    """Does this host wear an official label - or a configured official NAME - without being on
    the official list?

    Two independent tests, each with a measured miss the other covers:
    * an official LABEL (`gov`, `mil`) as a whole part of the name - catches `uscis.gov.ru`,
      `uscisdhs-gov.us`; blind to `uscis.com`;
    * an official NAME (`uscis`, `ecfr`) as a whole part of the name - catches `uscis.com` and
      `uscis.phishing.example`; blind to a misspelling like `ussciss.us`, which is stated in the
      report as the residual hole rather than closed with a similarity threshold that four
      independent reviewers rejected.
    """
    # Defensive: every caller inside this module lower-cases first, but the function is exported,
    # and `USCIS.COM` passed a direct call untouched in an outside review's trace.
    host = (host or "").lower()
    if not host or any(suffix_match(host, e) for e in (primary or [])):
        return False
    parts = set()
    for label in host.split("."):
        parts.add(label)
        parts.update(label.split("-"))
    if parts.intersection(OFFICIAL_TOKENS):
        return True
    return bool(parts.intersection(agency_labels(primary)))


def _entry_match(host, hostpath, entry):
    """Does one configured pattern match this URL - as a HOST, or as a host plus a path prefix?

    A pattern that names a host (`govinfo.gov/content/pkg/CFR-`) vouches for itself: the host part
    is suffix-matched at a label boundary and the path part must really be in the path. A pattern
    that names no host (`/historical/`, `?date=`) is a QUALIFIER and cannot vouch for anything -
    see `classify_url`.

    🔴 The path is taken from `hostpath`, which excludes the query string. `?ref=govinfo.gov/...`
    is attacker-controlled text in someone else's URL and matched as a substring of the whole URL
    before this existed.
    """
    e = (entry or "").lower().strip().lstrip(".")
    if not e:
        return False
    if "/" in e:
        h, _, p = e.partition("/")
        return suffix_match(host, h) and ("/" + p) in hostpath
    return suffix_match(host, e)


def classify_url(u, g):
    """Which of five things is this URL, read in order of how badly it can mislead you.

    🔴 Both sides are lower-cased. The first version lower-cased only the URL, so every pattern
    written the way a human writes it - `CFR-`, `/Historical/` - could never match. The check ran,
    reported nothing, and read as a clean result. Its own test caught it; nothing else would have,
    because a detector that never fires looks exactly like a corpus with nothing to find.

    🔴 Order. `lookalike` runs first because it is the only bucket that can be actively hostile;
    `snapshot` runs before `primary` because an annual edition lives on a government domain, so
    asking "is it official?" first would answer yes and stop. A real `.gov` URL can never reach the
    lookalike test - ``gov_lookalike`` returns False for anything the official list already matches -
    so putting it first costs nothing.

    🔴🔴 A DATED-EDITION MARKER IS A QUALIFIER ON A VOUCHED HOST, NEVER A CREDENTIAL BY ITSELF.
    The snapshot list holds path and query fragments - `/annual/`, `/historical/`, `?date=` - and
    they used to be matched as substrings of the whole URL, ahead of every host test. So
    `https://evil.com/historical/report.xml` classified as `snapshot`, which is the label
    "OFFICIAL BUT DATED", and `krokai fetch` downloaded it without `--allow-unknown-source` and
    wrote that phrase into the human-facing library index. Measured 2026-08-05; all three channels
    of the round-21 review found it independently, and each one had to invent the counterexample
    URL to show it, which is why the run's own citation check then graded their reviews as citing
    dead pages.

    🔴 This is the SECOND HALF of the bug fixed in 0.4.0. That round replaced a substring test with
    `suffix_match` on the `primary` branch and left the two branches either side of it matching
    substrings - including the branch that runs FIRST. The visible half of a symmetric defect gets
    fixed and the invisible half survives: third measured instance in this package.
    """
    from urllib.parse import urlsplit
    u = (u or "").lower()
    host = host_of(u)
    try:
        hostpath = host + (urlsplit(u).path or "")
    except ValueError:
        hostpath = host
    primary = g.get("primary") or []
    if gov_lookalike(host, primary):
        return "lookalike"
    is_primary = any(suffix_match(host, s) for s in primary)
    is_nonauth = any(_entry_match(host, hostpath, s)
                     for s in (g.get("nonauthoritative") or []))
    for s in (g.get("snapshot") or []):
        e = (s or "").lower().strip()
        if not e:
            continue
        head = e.split("/", 1)[0]
        if head and "." in head:
            # Names a host, so it vouches for itself: `govinfo.gov/content/pkg/CFR-`.
            if _entry_match(host, hostpath, e):
                return "snapshot"
        elif (is_primary or is_nonauth) and e in u:
            # A bare marker - `/historical/`, `?date=` - only qualifies an already-vouched host.
            return "snapshot"
    if is_primary:
        return "primary"
    if is_nonauth:
        return "nonauthoritative"
    return "other"


def grounding_of(result, g):
    """Classify every URL the answer cites.

    🔴 This is DERIVED FROM THE TEXT, and that is stated wherever it is printed. It is weaker than
    telemetry - a channel can print a URL it never opened, which has been measured repeatedly - but
    it is the only grounding signal available for channels that report no telemetry at all, and on
    those the answer is the sole evidence there is.
    """
    urls, seen = [], set()
    for u in _URL_RE.findall(result.get("text") or ""):
        u = u.rstrip(".,)")
        if u.lower() not in seen:
            seen.add(u.lower())
            urls.append(u)
    buckets = {"primary": [], "snapshot": [], "lookalike": [], "nonauthoritative": [], "other": []}
    for u in urls:
        buckets[classify_url(u, g)].append(u)
    return {"total": len(urls), **buckets}


def triage(result, g):
    """FAILED / DIRTY / OK, read from codes and counts only. Never from prose.

    🔴 INSTRUMENT CODES DO NOT MOVE THE VERDICT, and separating them is a fix, not a relaxation.
    `NO_TELEMETRY` describes the CHANNEL, not the answer: it is constant across every run of that
    channel and says nothing about what came back. While it graded, the most common configuration -
    an external harness installed, so every answer absorbed - produced `DIRTY` for every answer ever,
    for a reason the console printer then deliberately skipped. Measured: a flawless answer citing
    one genuine government URL printed `[DIRTY] codex 379.0s 1620B cited 1 URL(s) (official 1)` and
    no explanation at all.

    A verdict that is always the same carries no information, and an unexplained one teaches the
    reader to ignore the column - this toolkit's own oldest doctrine, applied here to itself. The
    code is still reported, still written to the analytics file, and now actually printed; it just
    no longer pretends to be a judgement about the answer.
    """
    ground = grounding_of(result, g)
    quality = list(result.get("quality") or [])

    if ground["lookalike"]:
        # First in the list because it is the only finding here that can be actively hostile.
        quality.append(("GOV_LOOKALIKE_CITED",
                        "%d: %s" % (len(ground["lookalike"]), "; ".join(ground["lookalike"][:3]))))
    if ground["snapshot"]:
        quality.append(("DATED_EDITION_CITED",
                        "%d: %s" % (len(ground["snapshot"]), "; ".join(ground["snapshot"][:3]))))
    if ground["nonauthoritative"]:
        quality.append(("COMMENTARY_CITED",
                        "%d: %s" % (len(ground["nonauthoritative"]),
                                    "; ".join(ground["nonauthoritative"][:3]))))
    if ground["total"] == 0 and (result.get("text") or "").strip():
        quality.append(("NO_URLS_CITED", ""))

    about_the_answer = [q for q in quality if q[0] not in INSTRUMENT_ONLY]
    verdict = "FAILED" if result.get("failures") else ("DIRTY" if about_the_answer else "OK")
    return verdict, quality, ground


# NOT HERE: a persistent record of what was sent to which vendor and when.
#
# A dispatch ledger was built and then removed - Igor, 2026-08-02: «этот функционал делать не
# будем». Noted rather than silently dropped, because the next person to think of it should know it
# was considered and cut, not overlooked.
#
# What survives is the part that costs nothing and is used every round: the brief's SHA-256 is
# printed before dispatch, so "every channel got the same brief" is a fact rather than an intention.
# That is a check on THIS round. It is not a file that accumulates.


def write_analytics(path, rows, seconds, lang="en"):
    """Write the instrument report to disk EVERY run, without being asked.

    A defect noticed in conversation has to be remembered and re-obeyed by whoever works next. A
    defect written to disk by the run that found it just sits there being true. This file is the
    difference between "I recall that channel grounding on a blog" and "the round says so, dated."
    """
    L = ["<!-- krokai: instrument report about the REVIEWERS. Not a source of law. -->",
         "# Round analytics", "",
         "%d channel(s) in %.1f s." % (len(rows), seconds),
         "",
         "`FAILED` no usable answer · `DIRTY` readable, sourcing suspect · `OK` nothing flagged.",
         "",
         "| channel | verdict | sec | answer B | URLs cited | official | of those, dated | "
         "commentary | 🔴 lookalike |",
         "|---|---|---|---|---|---|---|---|---|"]

    def f(x):
        return "—" if x is None else x

    for r in rows:
        gr = r.get("ground") or {}
        # 🔴 An annual edition counts as OFFICIAL and is then called out as DATED. The first version
        # tabulated it opposite `primary`, so a channel citing three government codifications
        # printed as `primary 0` - which reads as "cited no official source" and is simply false.
        # An annual edition is the codification; it is just not the text in force.
        dated = len(gr.get("snapshot") or [])
        L.append("| %s | **%s** | %s | %s | %s | %s | %s | %s | %s |" % (
            r["channel"], r["verdict"], f(r.get("seconds")), f(r.get("bytes")),
            gr.get("total", 0), len(gr.get("primary") or []) + dated, dated or "",
            len(gr.get("nonauthoritative") or []) or "",
            len(gr.get("lookalike") or []) or ""))

    # 🔴 Every host the classifier did not recognise, listed by name. It changes no verdict - there
    # is no threshold here and no accusation - but it stops `other` being the silent bucket.
    #
    # The reason it cannot be a verdict: the detector above is threshold-free because it looks for an
    # official LABEL, and a typosquat carrying no such label is invisible to it by construction.
    # `ussciss.us` is the measured example, and it is not hypothetical - it resolved to a live host
    # when checked on 2026-08-02, as did `uscisdhs-gov.us` and `uscis-gov.co`. Catching that third
    # shape needs a list of the domains YOU rely on, which a general tool does not have. So the hole
    # is left open and printed instead of being closed with a similarity threshold that four
    # independent reviewers rejected. Naming what was not covered is the rule; a silent gap reads
    # as coverage.
    unknown = sorted({host_of(u) for r in rows for u in (r.get("ground") or {}).get("other") or []})
    if unknown:
        L += ["",
              "**Hosts this tool does not recognise** (no verdict attached - read them yourself; a "
              "MISSPELLING of an official name - ussciss.us is the measured, live example - "
              "cannot be detected mechanically here. The exact name in a wrong zone IS caught, but "
              "only for sources configured in `grounding.primary` or a pack's `official_domains`):",
              ""] + ["* `%s`" % h for h in unknown[:25]]
        if len(unknown) > 25:
            L.append("* … and %d more" % (len(unknown) - 25))

    L += ["",
          "«—» means NOT MEASURED, never «zero».",
          "",
          "🔴 The **lookalike** column counts hosts wearing an official label (`gov`, `mil`) - or "
          "the NAME of a configured official source (`uscis`, `ecfr`) - that do not end in a "
          "configured official suffix. It is never zero-by-default: it was added after a substring "
          "test graded `www.milano.it`, `uscis.gov.ru` and `law.gov.cn` as official law, and the "
          "name test was added after `uscis.com` - the exact agency name in a foreign zone - "
          "walked past the label test. A count above zero is either a domain impersonating a "
          "government or a real government missing from `grounding.primary` - and the two are told "
          "apart by a person, not here.",
          "",
          "🔴 **These are URLs the answer PRINTED. Printing is not opening.** The count is not "
          "evidence of retrieval and must not be read as corroboration: the same process that "
          "invents a quotation invents the link under it, and knowing that an official source ends "
          "in `.gov` is exactly what is needed to mint a convincing one. What the column is good "
          "for is the opposite question - what this answer is asking you to rely on.", ""]

    for r in rows:
        if not (r.get("failures") or r.get("quality")):
            continue
        L += ["## %s — %s" % (r["channel"], r["verdict"]), ""]
        for code, detail in r.get("failures") or []:
            L.append("* 🔴 **%s** — %s%s" % (code, FAILURE_MEANING.get(code, "unknown code"),
                                             (" (%s)" % detail) if detail else ""))
        for code, detail in r.get("quality") or []:
            L.append("* ⚠️ **%s** — %s%s" % (code, QUALITY_MEANING.get(code, "unknown code"),
                                             (" (%s)" % detail) if detail else ""))
        L.append("")

    L += ["---", "",
          "🔴 Nothing here says whether the answers are RIGHT. It says whether the instruments "
          "worked. Run `krokai review --audit <folder>` to check the quotations themselves "
          "against your own corpus - that is the step this report does not perform.", ""]
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L))
    return path


# =================================================================================================
# The round
# =================================================================================================

def neutral_cwd(printer=print):
    """Run from a directory that contains none of your files. Returns the path.

    🔴 CONFIRMED LEAK, and the reason this exists. One agent CLI injects the CLAUDE.md of whatever
    directory it is launched from into the vendor's context, and its own `--ignore-rules` flag does
    not stop it. Asked how it knew a line from a project instruction file, the model answered that
    the file had been "injected into my initial system context by the harness under a Project
    Context block" - and then quoted the sentence and located it correctly in the file.

    It costs twice over:
      INDEPENDENCE - a reviewer that has read your own instructions is not a second opinion. In the
                     first live run it cited the project's own instruction file back as corroboration.
      CONFIDENTIALITY - that file reaches the vendor on every call, OUTSIDE the outbound gate,
                     which only ever scanned the brief.

    Launching from a neutral directory fixed it: the same probe from a scratch folder answered
    "NOTHING IN CONTEXT". Every path this module builds is absolute by the time it is used.
    """
    # 🔴 R77 (#F-G′, grokbuild MINOR, probe-proven): the old chain fell to `"."` when both
    # TEMP and TMPDIR were unset, making the scratch RELATIVE and INSIDE the matter — so the
    # SystemExit guard below never fired and the CLAUDE.md-injection leak this function exists
    # to prevent proceeded silently. `tempfile.gettempdir()` walks TMPDIR→TEMP→TMP→OS
    # fallbacks and practically cannot come back unusable; the SystemExit still guards
    # makedirs/chdir failure (fail-closed BY DESIGN — the panel's «wrong exception class»
    # claim is REJECTED, see ADJUDICATION.md).
    scratch = os.path.join(tempfile.gettempdir(), "krokai-neutral-cwd")
    try:
        os.makedirs(scratch, exist_ok=True)
        os.chdir(scratch)
        printer("  cwd -> %s" % scratch)
        printer("     (neutral: stops your own instruction files reaching a vendor outside the gate)")
    except OSError as exc:
        # 🔴 R77 (#341, kimik3/codex/lunapro): a hard stop, not a warning. The docstring above
        # records the CONFIRMED leak this directory prevents; proceeding after the chdir failed
        # would dispatch CLI channels from the matter's own folder, sending the instruction
        # files to the vendor outside the gate - a confidentiality failure dressed as
        # convenience. The failure is all but impossible (TEMP exists on every living system),
        # which is exactly why paying for it with a refused round is cheap.
        raise SystemExit(
            "refusing to dispatch: could not enter a neutral working directory (%r).\n"
            "CLI channels launched from this folder would carry your own instruction files "
            "(CLAUDE.md and the like) to the vendor OUTSIDE the outbound gate - a confirmed "
            "leak, not a hypothesis. Fix TEMP/TMPDIR and run again." % (exc,))
    return scratch


def run_round(reg, system, brief, out_dir, marker="REVIEW-COMPLETE", only=(), skip=(),
              harness=None, use_harness=True, harness_args=(), allow_pii=False,
              dry_run=False, printer=print, surnames=()):
    """Gate, plan, dispatch, grade, record. Returns `(rows, out_dir)`.

    The caller is responsible for having run the outbound gate; `cmd_consult` does it. This
    function refuses to proceed without proof, because a gate that can be forgotten is decoration.

    🔴 `surnames` must be passed here TOO, not only to `prepare()`. This is the last check before
    the payload leaves, and a last check that knows less than the first one is not a check - it is
    a place for a difference to hide.
    """
    from .redact import scan

    leftover = scan(brief, "brief", surnames=surnames) + scan(system, "system", surnames=surnames)
    secrets = [x for x in leftover if x[0] == "SECRET"]
    if secrets:
        raise SystemExit("refusing to send: %d secret-shaped value(s) still in the payload"
                         % len(secrets))
    if [x for x in leftover if x[0] == "PII"] and not allow_pii:
        raise SystemExit("refusing to send: personal identifiers in the payload and --allow-pii "
                         "was not given")

    limits = reg.get("limits") or {}
    g = reg.get("grounding") or {}
    floor = int(limits.get("min_answer_chars") or 800)
    timeout = int(limits.get("timeout_seconds") or 2400)
    workers = int(limits.get("max_parallel") or 4)

    chosen = selected(reg, only, skip)
    delegating = bool(harness and use_harness)

    # 🔴 DOUBLE-SPEND GUARD. Caught before the first real round, not after the bill: with a harness
    # installed AND a built-in channel enabled, the same vendor was asked the same question twice.
    # That costs twice and is worse than costing twice - two answers from one model read as two
    # independent opinions agreeing, which is the single thing this whole exercise exists to avoid.
    #
    # The rule is deliberately blunt rather than clever: if a harness runs, the built-in transports
    # stand down unless you name them with --only. Working out which vendors a third-party harness
    # covers would mean parsing its registry, and a guess there fails silently in the expensive
    # direction.
    if delegating and not only:
        stood_down = sorted(chosen)
        chosen = {}
        if stood_down:
            printer("")
            printer("  A review harness is installed, so the built-in channels stand down: %s"
                    % ", ".join(stood_down))
            printer("  (otherwise the same vendor is asked twice - double cost, and the two "
                    "answers read as agreement)")
            printer("  Use --no-harness to use the built-in transports instead, or --only <name> "
                    "to add one alongside.")

    problems = plan(reg, chosen, harness=harness, delegating=delegating,
                    allow_pii=allow_pii, printer=printer)
    ready = {n: c for n, c in chosen.items()
             if n not in {p[0] for p in problems} and c.get("enabled")}

    if dry_run:
        printer("--dry-run: nothing was called, nothing was sent, nothing was billed.")
        return [], out_dir
    if not ready and not (harness and use_harness):
        printer("No channel is ready and no harness is installed. Nothing was sent.")
        printer("That is a statement about this machine, not about the world:")
        printer("  * install one of the command-line tools above, or")
        printer("  * set %s to your own harness, or" % (
            (reg.get("channels", {}).get("harness") or {}).get("env") or "KROKAI_REVIEW_HARNESS"))
        printer("  * run `krokai brief` and paste it into each model by hand, then")
        printer("    `krokai consult --audit <folder>` - which is the step that matters.")
        return [], out_dir

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    brief_path = os.path.join(out_dir, "brief.md")
    system_path = os.path.join(out_dir, "system.md")
    io.open(brief_path, "w", encoding="utf-8", newline="\n").write(brief)
    io.open(system_path, "w", encoding="utf-8", newline="\n").write(system)

    printer("  brief: %d chars" % len(brief))

    origin = os.getcwd()
    neutral_cwd(printer=printer)
    t0 = time.time()
    try:
        delegated = []
        if delegating:
            t_dispatch = time.time() - 2          # margin for coarse filesystem mtimes
            call_delegate(harness, brief_path, system_path, out_dir, marker=marker,
                          extra=harness_args or (), printer=printer)
            delegated = absorb_delegated(out_dir, marker, floor, since=t_dispatch)

        jobs = {}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            for name, ch in sorted(ready.items()):
                wd = os.path.join(out_dir, name + "-ws")
                if ch.get("kind") == "cli":
                    # 🔴 Only the HTTP kind has a real system slot. A command-line channel takes one
                    # prompt, so the framing has to ride in front of the brief - and it MUST reach
                    # them: the same six questions framed as filing strategy were refused on policy
                    # and, framed as source verification, answered in full. The refusal still ended
                    # with the completion marker, so every mechanical check passed it.
                    payload = system.rstrip() + "\n\n---\n\n" + brief
                    jobs[name] = (ch, payload, ex.submit(
                        call_cli, name, ch, payload, marker, wd, floor, timeout, printer))
                else:
                    payload = system + "\n" + brief
                    jobs[name] = (ch, payload, ex.submit(
                        call_http, name, ch, system, brief, marker, floor, timeout, printer))
            results = {n: (ch, pl, fut.result()) for n, (ch, pl, fut) in jobs.items()}
    finally:
        os.chdir(origin)

    rows = []
    for name, (ch, payload, r) in sorted(results.items()):
        if r.get("text"):
            io.open(os.path.join(out_dir, name.upper() + ".md"), "w",
                    encoding="utf-8", newline="\n").write(r["text"])
        verdict, quality, ground = triage(r, g)
        rows.append({**r, "verdict": verdict, "quality": quality, "ground": ground,
                     "vendor": ch.get("vendor")})

    for r in delegated:
        verdict, quality, ground = triage(r, g)
        rows.append({**r, "verdict": verdict, "quality": quality, "ground": ground,
                     "vendor": "via harness"})

    secs = time.time() - t0
    printer("")
    printer("=" * 78)
    for r in rows:
        gr = r["ground"]
        printer("[%s] %-8s %ss  %sB  cited %d URL(s) (official %d%s%s%s)" % (
            r["verdict"], r["channel"], r.get("seconds"), r.get("bytes"), gr["total"],
            len(gr["primary"]) + len(gr["snapshot"]),
            ", of those dated %d" % len(gr["snapshot"]) if gr["snapshot"] else "",
            ", commentary %d" % len(gr["nonauthoritative"]) if gr["nonauthoritative"] else "",
            ", 🔴 LOOKALIKE %d" % len(gr["lookalike"]) if gr["lookalike"] else ""))
        for code, detail in r["failures"]:
            printer("    FAIL %-22s %s" % (code, FAILURE_MEANING.get(code, "")))
        for code, detail in r["quality"]:
            # 🔴 Nothing is silently skipped here any more. The one code that used to be skipped was
            # the only code that could produce the verdict on the line above, so the most common
            # configuration printed a judgement with its reason deliberately withheld.
            if code in INSTRUMENT_ONLY:
                printer("    inst %-22s does not affect the verdict: %s"
                        % (code, "this channel reports nothing about which pages it opened"))
                continue
            printer("    warn %-22s %s" % (code, detail or QUALITY_MEANING.get(code, "")))
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("OK", "DIRTY", "FAILED")}
    printer("=" * 78)
    printer("OK %d · DIRTY %d · FAILED %d" % (counts["OK"], counts["DIRTY"], counts["FAILED"]))

    ap = write_analytics(os.path.join(out_dir, "ANALYTICS.md"), rows, secs)
    printer("analytics written without being asked: %s" % ap)
    printer("")
    printer("🔴 NOTHING ABOVE SAYS THE ANSWERS ARE RIGHT. Now check their quotations:")
    printer("     krokai review --audit %s" % out_dir)
    printer("   Report per channel what you ACCEPTED, what you REJECTED with proof, and where they")
    printer("   disagreed with each other. The disagreement is the product.")
    return rows, out_dir
