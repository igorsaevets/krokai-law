# Site access map for this matter

**What this file is for.** A per-matter record of which official publishers are reachable from
this environment and which are behind an anti-bot layer that plain HTTP requests cannot cross.
Update it the first time you hit a blocked site, so the next round does not spend time hunting
the same wall.

🔴 **This is a note pad, not a bypass tool.** If a publisher refuses automated fetches, that is
the publisher's decision and the answer is to open the page in a browser and save the chapter by
hand. Do not route around a robots.txt, a paywall or a CAPTCHA.

---

## Known-good channels (measured on 2026-09-01)

| Publisher | URL form | Works with `krokai fetch`? | Note |
|---|---|---|---|
| U.S. Code, any section | `https://www.govinfo.gov/link/uscode/{title}/{section}?link-type=html` | yes | govinfo's link-service, no rate limit |
| Federal Register, by vol/page | `https://www.govinfo.gov/link/fr/{volume}/{page}?link-type=html` | yes | same link-service |
| Public Law number | `https://www.govinfo.gov/link/plaw/{congress}/public/{num}?link-type=html` | yes | same link-service |
| eCFR versioner API (whole part) | `https://www.ecfr.gov/api/versioner/v1/full/{DATE}/title-{n}.xml?part={part}` | yes | needs `{DATE}` — get from `https://www.ecfr.gov/api/versioner/v1/titles.json` (`latest_issue_date` per title) |
| eCFR browser interface | `https://www.ecfr.gov/current/...` | **no** — 302 to `unblock.federalregister.gov` | use the versioner API above |
| Federal Register browser | `https://www.federalregister.gov/citation/...` | **no** — 302 to `unblock.federalregister.gov` | use the govinfo link service above, or the FR API |
| USCIS Policy Manual | `https://www.uscis.gov/policy-manual/volume-{v}-part-{p}-chapter-{c}` | **no** — 403 Forbidden | open in a browser, File → Save As into `law/`, `krokai intake --address "..."` |
| USCIS policy memoranda | `https://www.uscis.gov/laws-and-policy/other-resources/policy-memoranda` | **no** — anti-bot | open in a browser, save the PDF into `law/`, `krokai intake --address "PM-..."` |

**How to keep this table honest.** `krokai doctor --probe-sites` fires one request at each of
the known-good URLs above and prints the status code, redirect target and byte count. Run it
when a fetch stops working and update the row.

---

## Site-specific gotchas seen in THIS matter

*(Empty when the matter is fresh. Write down what you hit, the date and the exact URL. A future
round pays for silence here.)*

- (nothing recorded yet)

---

## When you hit a wall

1. **Copy the failing URL and the exact response** (`HTTP 403`, `302 to unblock.federalregister.gov`,
   `Connection reset`, `DNS did not resolve`). "It did not work" is not enough for the next round to
   act on.
2. **Add a row above** with the URL form, the response and the date. That row is what stops the
   next assistant from spending a round on the same wall.
3. **Use the browser fall-back** the row prescribes. `krokai intake --address "..."` accepts a
   file you saved by hand from a browser — the toolkit does not care how the bytes reached disk,
   only that a person looked at them.
4. **Never invent a URL.** If none of the rows above fit the citation and you cannot open the
   publisher's page in a browser, say so out loud in the report rather than fabricating a
   plausible one.
