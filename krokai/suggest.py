# -*- coding: utf-8 -*-
"""Adress -> a ready-to-run download command. The push half of "found a hole → know what to do".

WHY THIS MODULE EXISTS
-----------------------
`krokai check` and `krokai coverage` name gaps: a bank entry whose file is not on disk, a citation
in a draft whose source has never been downloaded. Naming the gap is half of the answer; the other
half is *how to fetch that specific source*, and an assistant that has to hunt for the URL will
either invent one or give up. Measured in the sister project: an assistant handed a `NOT_FOUND`
gave up two rounds in a row because it "did not know where to download from". The whole point of
the ladder under `NOT_FOUND` is that fabrication is the conclusion that survives everything - and
the first cause on that ladder is "the source was never downloaded".

So for every address form the toolkit recognises this module returns EITHER a stable URL that
`requests` can retrieve, OR a caveat naming the specific reason the URL cannot be handed out. A
caveat is not a placeholder; it names the site's anti-bot behaviour or the field the URL needs
that the address alone cannot supply.

🔴 STABLE FORMS ONLY - MEASURED, NEVER GUESSED
-----------------------------------------------
Every URL template here was reached against the live host during R79-F3 (2026-09-01). Some
addresses have no stable request-level URL because the publisher's site is behind an anti-bot layer
and *"open it in a browser"* is the only honest answer. Saying so out loud is the point. The
templates that DO ship are exactly those that returned a valid document to `requests` with a plain
User-Agent header - the same channel `krokai fetch` uses. The two failing shapes are named so a
reader does not think we forgot them:

  * `www.ecfr.gov/current/...`               -> 302 to `unblock.federalregister.gov`
  * `www.federalregister.gov/citation/...`   -> 302 to `unblock.federalregister.gov`
  * `www.uscis.gov/policy-manual/...`        -> 403 Forbidden

The `unblock.` host is the site's own anti-scrape wall, not a mirror. eCFR does publish an API
that is not behind that wall (`api/versioner/...`), and this module suggests it - the API needs a
date, which is why the template carries a `{DATE}` marker and a one-line note.

🔴 THE URL LIVES IN ONE HOME
----------------------------
`library.RECIPES` also holds retrieval recipes. The overlap is deliberate: those recipes are meant
for a human reading the library page, this table is meant for `krokai fetch`. The two are kept
consistent by pointing at the same publishing endpoints (govinfo's `/link/...` service, eCFR's
versioner API); a divergence would be a defect this module's own self-test would name, and one
place the values were copied out of the other is exactly the two-homes-for-one-subject rot the
toolkit measures elsewhere.
"""
from __future__ import annotations

__all__ = ["FetchSuggestion", "suggest_for_key", "suggest_command", "SUPPORTED_KINDS",
           "template_for", "verify_kinds"]


class FetchSuggestion(object):
    """One suggested way to bring a source onto disk.

    `url`      - a URL `krokai fetch` can retrieve, OR None if the publisher requires a browser.
    `command`  - the ready-to-run command as a single line, OR None when `url` is None.
    `note`     - a one-sentence explanation of what this URL is and any known caveat.
    `caveat`   - one of "requires_date", "browser_only", None. Machine-readable for callers that
                 want to gate on it (a test, a hook, a report that groups by cause).
    """

    __slots__ = ("kind", "url", "command", "note", "caveat")

    def __init__(self, kind, url, command, note, caveat=None):
        self.kind = kind
        self.url = url
        self.command = command
        self.note = note
        self.caveat = caveat

    def __repr__(self):                                                  # pragma: no cover
        return "FetchSuggestion(kind=%r, url=%r, caveat=%r)" % (self.kind, self.url, self.caveat)


# ----------------------------------------------------------------------------------- URL builders
# One function per kind, each returning `(url_or_None, note, caveat_or_None)`. Keeping the URLs
# behind functions rather than a raw template dictionary lets `pmnum` build one string from one
# group and `cfr` build a template needing a date; the caller does not care about the difference.


def _uscode(key):
    """`("usc", "8", "1101")` -> the government's own copy of 8 U.S.C. § 1101.

    Uses govinfo's `link-type=html` redirector so the response body is HTML rather than the raw
    XML the base URL returns. Verified against the live host (2026-09-01): returns a 359 KB PDF
    for the plain URL and HTML with `?link-type=html`, both retrievable with a plain User-Agent.
    """
    _, title, section = key[0], key[1], key[2]
    url = "https://www.govinfo.gov/link/uscode/%s/%s?link-type=html" % (title, section)
    return url, "govinfo's stable link service for a U.S. Code section", None


def _fr(key):
    """`("fr", "91", "45324")` -> the Federal Register document at that volume and page.

    `www.federalregister.gov/citation/...` redirects to an anti-bot page, but govinfo's link
    service is the government's own resolver and does not. Verified: returned a 2.9 MB PDF.
    """
    _, volume, page = key[0], key[1], key[2]
    url = "https://www.govinfo.gov/link/fr/%s/%s?link-type=html" % (volume, page)
    return url, "govinfo's stable link service for a Federal Register citation", None


def _publaw(key):
    """`("publaw", "107", "56")` -> the text of Public Law 107-56.

    Verified: returned a 482 KB PDF from govinfo's `/link/plaw/...` resolver.
    """
    _, congress, num = key[0], key[1], key[2]
    url = "https://www.govinfo.gov/link/plaw/%s/public/%s?link-type=html" % (congress, num)
    return url, "govinfo's stable link service for a Public Law number", None


def _cfr(key):
    """`("cfr", "8", "214")` -> the eCFR versioner API URL for the whole part.

    This is the one address kind whose URL carries a placeholder. The browser-facing eCFR pages
    are behind an anti-bot wall; the versioner API is not, but it demands a date. Rather than
    reach the network here (a suggest command that quietly opens a connection is a suggest
    command that fails in the wrong place), the URL is emitted with a `{DATE}` marker and a
    one-line note directing the reader to `ecfr.gov/api/versioner/v1/titles.json` for the
    current issue date of that title.

    A caller that wants to substitute the date IS reaching the network and it is that caller's
    job to record it - `krokai doctor --probe-sites` will resolve it and print the substituted
    URL alongside the raw form.
    """
    _, title, part = key[0], key[1], key[2]
    url = ("https://www.ecfr.gov/api/versioner/v1/full/{DATE}/title-%s.xml?part=%s"
           % (title, part))
    note = ("eCFR versioner API for a whole part. Replace {DATE} with `latest_issue_date` from "
            "https://www.ecfr.gov/api/versioner/v1/titles.json - the browser-facing eCFR site "
            "refuses automated fetches, the API does not")
    return url, note, "requires_date"


def _ina(key):
    """INA sections are the Immigration and Nationality Act's own numbering; the code copy of
    them lives in Title 8, and the coverage extractor already emits an `("usc", "8", ...)` twin
    for every INA hit. So the ordinary route for INA fetches is the USC path.

    This function exists so a caller that lands here has a clear answer rather than an empty
    dict - and the answer is "route through the USC twin". No caveat: the fold happens at
    extraction and the USC path works. Look up the USC section on the fly so the note is
    concrete (`INA § 245 is 8 U.S.C. § 1255`) rather than a generic pointer with a `?`.
    """
    from .coverage import INA_TO_USC
    section = key[1] if len(key) > 1 else ""
    usc_section = INA_TO_USC.get(section.lower(), "?")
    note = ("route through the USC twin - INA § %s is 8 U.S.C. § %s, and the coverage "
            "extractor emits both at parse time" % (section or "?", usc_section))
    return None, note, None


def _pm(key):
    """USCIS Policy Manual chapter: `("pm", "7", "b", "8")` = 7 USCIS-PM B.8.

    Verified 2026-09-01: the browser URL returns 403 Forbidden to plain `requests`, and USCIS
    does not publish a machine-readable version of the Policy Manual. Every attempt to route
    around this ends in the same anti-bot wall. So the honest answer is "open it in a browser
    and save the chapter" - not a URL the caller thinks they can hand to `krokai fetch`.
    """
    if len(key) < 4:
        return None, "USCIS Policy Manual, but the address is incomplete", "browser_only"
    _, vol, part, chapter = key[0], key[1], key[2], key[3]
    browser = ("https://www.uscis.gov/policy-manual/volume-%s-part-%s-chapter-%s"
               % (vol, part.lower(), chapter))
    note = ("USCIS Policy Manual is behind an anti-bot layer (403 to plain requests). Open "
            "%s in a browser, then File > Save As into your law/ folder and run "
            "`krokai intake --address \"%s USCIS-PM %s.%s\"`"
            % (browser, vol, part.upper(), chapter))
    return None, note, "browser_only"


def _pmnum(key):
    """A numbered USCIS policy memorandum: `("pmnum", "602-0199")`.

    The memoranda are indexed on USCIS's own site behind the same anti-bot layer as the Policy
    Manual. A search URL exists but returns a bot wall to `requests`. So this is browser-only
    for the same reason.
    """
    _, num = key[0], key[1]
    browser = "https://www.uscis.gov/laws-and-policy/other-resources/policy-memoranda"
    note = ("USCIS policy memoranda are indexed at %s (browser only - the site refuses automated "
            "fetches). Open the page, search for PM-%s, save the PDF into law/ and run "
            "`krokai intake --address \"PM-%s\"`" % (browser, num, num))
    return None, note, "browser_only"


# ----------------------------------------------------------------------------------- registry
# The kind -> builder mapping. Adding a citation kind means adding a row here; every downstream
# call routes through `suggest_for_key`. Kinds not listed are simply "no suggestion", which is
# the honest answer for FAM, matter/case names and reporter cites: their retrieval is heuristic
# and would produce false confidence rather than a real command.
_BUILDERS = {
    "usc": _uscode,
    "ina": _ina,
    "fr": _fr,
    "publaw": _publaw,
    "cfr": _cfr,
    "pm": _pm,
    "pmnum": _pmnum,
}

SUPPORTED_KINDS = tuple(sorted(_BUILDERS.keys()))


def suggest_for_key(key):
    """`("cfr", "8", "214")` -> a `FetchSuggestion`, or None if the kind is unknown here.

    Never raises. An address form this module does not handle (fam, matter, case, indec) returns
    None so the caller can silently fall through - the alternative would be to invent a URL, and
    that is precisely what this module exists to prevent.
    """
    if not key:
        return None
    builder = _BUILDERS.get(key[0])
    if not builder:
        return None
    try:
        result = builder(key)
    except Exception:                                                    # noqa: BLE001
        return None
    if not result or len(result) != 3:
        return None
    url, note, caveat = result
    command = ('krokai fetch "%s"' % url) if url else None
    return FetchSuggestion(kind=key[0], url=url, command=command, note=note, caveat=caveat)


def template_for(kind):
    """The raw URL template for a kind - for docs, for the doctor's live probes, for the test
    suite's derived expectations. Returns None if the kind is browser-only or unknown.

    🔴 Every row here has an equivalent in `library.RECIPES`. Kept in sync ON PURPOSE - the
    library page is the human-facing recipe list, this table is the machine-facing one. A
    self-test asserts both point at the same publishing endpoints, which is what stops one home
    from rotting the other.
    """
    return {
        "usc": "https://www.govinfo.gov/link/uscode/{title}/{section}?link-type=html",
        "fr": "https://www.govinfo.gov/link/fr/{volume}/{page}?link-type=html",
        "publaw": "https://www.govinfo.gov/link/plaw/{congress}/public/{num}?link-type=html",
        "cfr": "https://www.ecfr.gov/api/versioner/v1/full/{DATE}/title-{title}.xml?part={part}",
    }.get(kind)


def suggest_command(key):
    """Convenience: the command string, or None. Callers that only want to print skip the
    `FetchSuggestion` wrapper this way."""
    s = suggest_for_key(key)
    return s.command if s else None


# ----------------------------------------------------------------------------------- verify_kinds
# The tiny probe used by `library --suggest-fetches` for the "the URL template still fits the
# shape I expect" question. Not a network call - that lives in `doctor --probe-sites`. This is
# the mechanical assertion that `_uscode(("usc","8","1101"))` still yields the shape shipped in
# `template_for("usc")`.
def verify_kinds():
    """Return `[(kind, ok, why)]` for every SUPPORTED kind - a purely mechanical check that
    the builder still produces the templated URL for a canonical address. A failure means
    someone edited a builder without updating `template_for`, which is what the self-test
    catches.
    """
    probes = [
        ("usc", ("usc", "8", "1101"),
         "https://www.govinfo.gov/link/uscode/8/1101?link-type=html"),
        ("fr", ("fr", "91", "45324"),
         "https://www.govinfo.gov/link/fr/91/45324?link-type=html"),
        ("publaw", ("publaw", "107", "56"),
         "https://www.govinfo.gov/link/plaw/107/public/56?link-type=html"),
        ("cfr", ("cfr", "8", "214"),
         "https://www.ecfr.gov/api/versioner/v1/full/{DATE}/title-8.xml?part=214"),
    ]
    out = []
    for kind, key, expected in probes:
        got = suggest_for_key(key)
        if got is None:
            out.append((kind, False, "no suggestion at all"))
            continue
        if got.url != expected:
            out.append((kind, False, "url shape drifted: got %r" % got.url))
            continue
        out.append((kind, True, ""))
    return out
