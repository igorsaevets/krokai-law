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
* recording what was sent, to whom, and whether that vendor keeps it;
* stopping your own instruction files from reaching the vendor in the first place.

Those are all **trust** controls, the same family as "check the reviewer's quotations against the
source". Transport is "make an HTTP call". The line was drawn in the wrong place, so the product had
a hole exactly where its audience needed it most.

So the line is now:

    a separate harness, if you have one  ->  TRANSPORT. Get answers back.
    this module                          ->  TRUST. What may go out, what may be believed,
                                             and a record of both.

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

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

__all__ = ["load_registry", "plan", "run_round", "triage", "grounding_of",
           "write_analytics", "append_ledger", "REGISTRY_NAME"]

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
    "KEY_NOT_SET": "this channel needs an environment variable that is not set",
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
    "UNKNOWN_RETENTION": "it is not recorded whether this vendor keeps what you sent",
}

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
    tried.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              REGISTRY_NAME))
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
    """Locate a separate review harness. Absence is 'not installed here', never 'does not exist'."""
    ch = (reg.get("channels") or {}).get("harness") or {}
    if explicit:
        return explicit if os.path.exists(explicit) else None
    env = os.environ.get(ch.get("env") or "KROKAI_REVIEW_HARNESS")
    if env and os.path.exists(env):
        return env
    for c in ch.get("candidates") or []:
        p = _expand(c)
        if os.path.exists(p):
            return p
    return None


def _bin_path(ch):
    """Resolve a channel's binary. Returns the resolved path or None."""
    import shutil
    env = ch.get("bin_env")
    if env and os.environ.get(env):
        cand = _expand(os.environ[env])
        return cand if os.path.exists(cand) else None
    return shutil.which(ch.get("bin") or "")


def selected(reg, only=(), skip=(), with_disabled=False):
    """Which channels this round would use, honouring enabled/--only/--skip."""
    out = {}
    for name, ch in (reg.get("channels") or {}).items():
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
    round ran with the wrong model, or that a vendor retains what you sent - cannot be undone by
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
    printer("  %-9s %-4s %-10s %-6s %-12s %-8s %s" %
            ("channel", "on?", "vendor", "how", "cost", "retains", "installed"))
    will_run = []
    for name, ch in sorted(chosen.items()):
        ready, why = "yes", ""
        kind = ch.get("kind")
        if kind == "cli":
            if not _bin_path(ch):
                ready, why = "NO", "`%s` not on PATH" % ch.get("bin")
                problems.append((name, why))
        elif kind == "http":
            for k in ("key_env", "base_url_env"):
                if ch.get(k) and not os.environ.get(ch[k]):
                    ready, why = "NO", "%s not set" % ch[k]
                    problems.append((name, why))
        # 🔴 "switched on" and "installed" are two independent facts, and collapsing them is how a
        # plan lies. A channel disabled in the registry does not run even though its binary is
        # present - and the first draft of this table printed that case as `ready: yes`, which any
        # reader takes to mean "will run".
        on = "on" if ch.get("enabled") else "off"
        if ch.get("enabled") and ready == "yes":
            will_run.append(name)
        printer("  %-9s %-4s %-10s %-6s %-12s %-8s %s %s" % (
            name, on, (ch.get("vendor") or "-")[:10], kind, ch.get("cost") or "-",
            (ch.get("retains") or "unknown")[:8], ready, why))
    printer("")
    runners = sorted(will_run)
    if harness and delegating:
        runners = ["harness -> " + os.path.basename(harness)] + runners
    printer("  will run: %s" % (", ".join(runners) or "NOTHING"))

    metered = [n for n in will_run if chosen[n].get("cost") == "metered"]
    if metered:
        printer("  🔴 METERED and will run: %s. These bill per call." % ", ".join(sorted(metered)))
    unknown = [n for n in will_run if (chosen[n].get("retains") or "unknown") == "unknown"]
    if unknown:
        printer("  ⚠️  retention not recorded for: %s" % ", ".join(sorted(unknown)))
        printer("     Sending IS publishing. 'Not checked' is not 'no'.")
    if allow_pii:
        printer("  🔴 --allow-pii is on: personal identifiers WILL leave this machine.")

    # 🔴 THE RISK THIS FEATURE CREATES, named where it is incurred. Raised by a reviewer of this
    # very design: asking N models the same question multiplies the confidentiality exposure by N.
    # Each vendor gets the whole payload, each keeps it under its own policy, and a breach at any
    # one of them is a breach of the lot. The ledger records that; recording is not mitigating.
    #
    # It is said here rather than in the documentation because a warning in a README is read once
    # and a warning in the plan is read every time - which is this project's oldest measurement:
    # rules fire by topic, not by rule.
    n = len(runners)
    if n > 1:
        printer("  ⚠️  %d independent vendors will each receive this material in full." % n)
        printer("     Multiplying the opinions multiplies the exposure. If one is breached, the")
        printer("     material is out - and the ledger below records that, it does not prevent it.")
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
        return _result(name, failures=[("TRANSPORT_ERROR", repr(exc)[:200])])

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
        r["failures"].append(("TRANSPORT_ERROR",
                              "exit %d: %s" % (p.returncode,
                                               (p.stderr or b"").decode("utf-8", "replace")[:200])))
    if not ch.get("telemetry"):
        r["quality"].append(("NO_TELEMETRY", ""))
    return _finish(r, marker, floor)


def call_http(name, ch, system, brief, marker, floor, timeout, printer=print):
    import urllib.request
    import urllib.error

    base = os.environ.get(ch.get("base_url_env") or "")
    key = os.environ.get(ch.get("key_env") or "")
    if not base or not key:
        missing = [k for k in (ch.get("base_url_env"), ch.get("key_env"))
                   if k and not os.environ.get(k)]
        return _result(name, failures=[("KEY_NOT_SET", ", ".join(missing))])

    body = json.dumps({"model": ch.get("model"),
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": brief}]}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        # 🔴 The status and the body are reported; the request headers are NOT, because they carry
        # the key. A crash handler that dumps the request is how a credential reaches a log.
        return _result(name, seconds=round(time.time() - t0, 1),
                       failures=[("HTTP_ERROR", "%s %s" % (exc.code, exc.reason))])
    except Exception as exc:                                        # noqa: BLE001
        return _result(name, failures=[("TRANSPORT_ERROR", type(exc).__name__)])

    text = ""
    try:
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


def absorb_delegated(out_dir, marker, floor):
    """Grade and record the answers a delegated harness produced.

    🔴 THIS FUNCTION EXISTS BECAUSE THE FIRST LIVE ROUND EXPOSED THE HOLE IT FILLS. With a harness
    installed the built-in transports correctly stand down - and the analytics printed
    `OK 0 · DIRTY 0 · FAILED 0` over four real answers, while the send ledger recorded nothing at
    all. So in the most common configuration, the layer that claims to be the trust layer saw
    nothing and said so in a format that read like a clean result.

    No amount of re-reading found that. Running it did, on the first attempt, which is the whole
    argument for testing a review tool by reviewing something real with it.

    The grading is deliberately the SAME code as for the built-in transports. A trust layer that
    judged its own transports more strictly than a delegate's would be measuring the transport, not
    the answer.
    """
    rows = []
    for fn in sorted(os.listdir(out_dir)):
        if not fn.lower().endswith(".md") or fn.lower() in _OURS:
            continue
        path = os.path.join(out_dir, fn)
        if not os.path.isfile(path):
            continue
        text = io.open(path, encoding="utf-8", errors="replace").read()
        r = _result(os.path.splitext(fn)[0].lower(), text=text)
        # The delegate reports its own telemetry in its own format; this layer does not parse it.
        # Saying "not measured here" is honest. Saying "0" would not be.
        r["quality"].append(("NO_TELEMETRY", "graded from the answer; the harness keeps its own"))
        rows.append(_finish(r, marker, floor))
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
        printer("  the harness could not be run: %r" % (exc,))
        return 1


# =================================================================================================
# Reading the answer: what did it stand on?
# =================================================================================================

def classify_url(u, g):
    """Which of four things is this URL, read in order of how badly it can mislead you.

    🔴 Both sides are lower-cased. The first version lower-cased only the URL, so every pattern
    written the way a human writes it - `CFR-`, `/Historical/` - could never match. The check ran,
    reported nothing, and read as a clean result. Its own test caught it; nothing else would have,
    because a detector that never fires looks exactly like a corpus with nothing to find.
    """
    u = (u or "").lower()
    host = u.split("//", 1)[-1].split("/", 1)[0]
    # Snapshot BEFORE primary, deliberately: an annual edition lives on a government domain, so
    # asking "is it official?" first would answer yes and stop.
    if any(p.lower() in u for p in (g.get("snapshot") or [])):
        return "snapshot"
    if any(host.endswith(s.lower()) or s.lower() in host for s in (g.get("primary") or [])):
        return "primary"
    if any(s.lower() in u for s in (g.get("nonauthoritative") or [])):
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
    buckets = {"primary": [], "snapshot": [], "nonauthoritative": [], "other": []}
    for u in urls:
        buckets[classify_url(u, g)].append(u)
    return {"total": len(urls), **buckets}


def triage(result, g, retains="unknown"):
    """FAILED / DIRTY / OK, read from codes and counts only. Never from prose."""
    ground = grounding_of(result, g)
    quality = list(result.get("quality") or [])

    if ground["snapshot"]:
        quality.append(("DATED_EDITION_CITED",
                        "%d: %s" % (len(ground["snapshot"]), "; ".join(ground["snapshot"][:3]))))
    if ground["nonauthoritative"]:
        quality.append(("COMMENTARY_CITED",
                        "%d: %s" % (len(ground["nonauthoritative"]),
                                    "; ".join(ground["nonauthoritative"][:3]))))
    if ground["total"] == 0 and (result.get("text") or "").strip():
        quality.append(("NO_URLS_CITED", ""))
    if (retains or "unknown") == "unknown":
        quality.append(("UNKNOWN_RETENTION", ""))

    verdict = "FAILED" if result.get("failures") else ("DIRTY" if quality else "OK")
    return verdict, quality, ground


# =================================================================================================
# The record: what was sent, to whom, and whether they keep it
# =================================================================================================

def append_ledger(path, round_id, brief_sha, rows, allow_pii):
    """One line per channel per round. 🔴 The payload is never written - only its hash.

    Nobody else's harness records this, and for this audience it is not optional. "Which client
    material went to which vendor, and when" is a question a professional can be asked to answer
    under a duty of confidentiality, and reconstructing it afterwards from four vendors' web
    histories is not an answer. The hash proves WHICH text was sent without storing the text.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with io.open(path, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps({
                "round": round_id,
                "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "channel": r["channel"],
                "vendor": r.get("vendor"),
                "brief_sha256": brief_sha,
                "payload_sha256": r.get("payload_sha256"),
                "payload_bytes": r.get("payload_bytes"),
                "retains": r.get("retains"),
                "pii_allowed": bool(allow_pii),
                "verdict": r.get("verdict"),
                "answer_bytes": r.get("bytes"),
            }, ensure_ascii=False) + "\n")
    return path


def write_analytics(path, rows, seconds, brief_sha, lang="en"):
    """Write the instrument report to disk EVERY run, without being asked.

    A defect noticed in conversation has to be remembered and re-obeyed by whoever works next. A
    defect written to disk by the run that found it just sits there being true. This file is the
    difference between "I recall that channel grounding on a blog" and "the round says so, dated."
    """
    L = ["<!-- krokai: instrument report about the REVIEWERS. Not a source of law. -->",
         "# Round analytics", "",
         "%d channel(s) in %.1f s. Brief sha256 `%s`." % (len(rows), seconds, brief_sha[:16]),
         "",
         "`FAILED` no usable answer · `DIRTY` readable, sourcing suspect · `OK` nothing flagged.",
         "",
         "| channel | verdict | sec | answer B | URLs cited | official | of those, dated | "
         "commentary | retains |",
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
            len(gr.get("nonauthoritative") or []) or "", r.get("retains") or "unknown"))

    L += ["",
          "«—» means NOT MEASURED, never «zero».",
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
    scratch = os.path.join(os.environ.get("TEMP") or os.environ.get("TMPDIR") or ".",
                           "krokai-neutral-cwd")
    os.makedirs(scratch, exist_ok=True)
    try:
        os.chdir(scratch)
        printer("  cwd -> %s" % scratch)
        printer("     (neutral: stops your own instruction files reaching a vendor outside the gate)")
    except OSError as exc:
        printer("  could not change to a neutral directory (%r) - a CLI channel may pick up the "
                "instruction files in this folder" % (exc,))
    return scratch


def run_round(reg, system, brief, out_dir, marker="REVIEW-COMPLETE", only=(), skip=(),
              harness=None, use_harness=True, harness_args=(), allow_pii=False,
              dry_run=False, printer=print):
    """Gate, plan, dispatch, grade, record. Returns `(rows, out_dir)`.

    The caller is responsible for having run the outbound gate; `cmd_consult` does it. This
    function refuses to proceed without proof, because a gate that can be forgotten is decoration.
    """
    from .redact import scan

    leftover = scan(brief, "brief") + scan(system, "system")
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

    brief_sha = hashlib.sha256(brief.encode("utf-8")).hexdigest()
    round_id = time.strftime("%Y%m%d-%H%M%S")
    printer("  brief sha256 %s  (%d chars)" % (brief_sha[:16], len(brief)))

    origin = os.getcwd()
    neutral_cwd(printer=printer)
    t0 = time.time()
    try:
        delegated = []
        if delegating:
            call_delegate(harness, brief_path, system_path, out_dir, marker=marker,
                          extra=harness_args or (), printer=printer)
            delegated = absorb_delegated(out_dir, marker, floor)

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
        verdict, quality, ground = triage(r, g, ch.get("retains"))
        rows.append({**r, "verdict": verdict, "quality": quality, "ground": ground,
                     "vendor": ch.get("vendor"), "retains": ch.get("retains") or "unknown",
                     "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                     "payload_bytes": len(payload.encode("utf-8"))})

    for r in delegated:
        verdict, quality, ground = triage(r, g, "unknown")
        rows.append({**r, "verdict": verdict, "quality": quality, "ground": ground,
                     "vendor": "via harness", "retains": "unknown",
                     # The harness owns the envelope, so what it actually sent is its record, not
                     # this one. Claiming a payload hash here would be inventing evidence; the
                     # brief hash below is the part this layer can honestly attest to.
                     "payload_sha256": None,
                     "payload_bytes": None})

    secs = time.time() - t0
    printer("")
    printer("=" * 78)
    for r in rows:
        gr = r["ground"]
        printer("[%s] %-8s %ss  %sB  cited %d URL(s) (official %d%s%s)" % (
            r["verdict"], r["channel"], r.get("seconds"), r.get("bytes"), gr["total"],
            len(gr["primary"]) + len(gr["snapshot"]),
            ", of those dated %d" % len(gr["snapshot"]) if gr["snapshot"] else "",
            ", commentary %d" % len(gr["nonauthoritative"]) if gr["nonauthoritative"] else ""))
        for code, detail in r["failures"]:
            printer("    FAIL %-22s %s" % (code, FAILURE_MEANING.get(code, "")))
        for code, detail in r["quality"]:
            if code in ("NO_TELEMETRY", "UNKNOWN_RETENTION"):
                continue
            printer("    warn %-22s %s" % (code, detail or QUALITY_MEANING.get(code, "")))
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("OK", "DIRTY", "FAILED")}
    printer("=" * 78)
    printer("OK %d · DIRTY %d · FAILED %d" % (counts["OK"], counts["DIRTY"], counts["FAILED"]))

    ap = write_analytics(os.path.join(out_dir, "ANALYTICS.md"), rows, secs, brief_sha)
    printer("analytics written without being asked: %s" % ap)
    lp = append_ledger(os.path.join(out_dir, "..", "consult-ledger.jsonl"),
                       round_id, brief_sha, rows, allow_pii)
    printer("ledger appended (hashes only, never the text): %s" % os.path.abspath(lp))
    printer("")
    printer("🔴 NOTHING ABOVE SAYS THE ANSWERS ARE RIGHT. Now check their quotations:")
    printer("     krokai review --audit %s" % out_dir)
    printer("   Report per channel what you ACCEPTED, what you REJECTED with proof, and where they")
    printer("   disagreed with each other. The disagreement is the product.")
    return rows, out_dir
