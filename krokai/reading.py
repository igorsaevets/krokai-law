"""K047 (2026-11-26): the reading list - every quotation of the FILED documents (tier A) beside the passage of the
source it was found in, with the question «does this passage support the sentence?». Flagged quotations come first,
in REPORT.md's order; the rest follow in the order of the facts noted beside them. `krokai check` writes it next to
REPORT.md on every run; it keeps no state and no «read» marks.

🔴 WHY A LIST AND NOT ANOTHER VERDICT. `check` compares words, and the classes a word comparison cannot see live
inside the clean verdicts: a verbatim quotation that does not support the sentence around it, a headnote quoted
under the opinion's pincite, a proviso one sentence away. REPORT.md details only the flagged rows (by design, ledger
E-1076), so a person who wanted to read the clean ones had nothing to read from. The reading is the lawyer's duty
either way: Lnu v. Blanche, 9th Cir. No. 24-4790 (2026-06-03), quoting Noland, 114 Cal. App. 5th at 445 - counsel
must read the authorities «to determine that the authorities stand for the propositions for which they are cited»;
the failures it names are quotations not in the authority (this package's comparison), authorities that do not
support the proposition (this list), and authorities that do not exist.

🔴 WHY NO VERDICT LABEL BESIDE A CLEAN QUOTATION. A label beside a row is advice, and advice gets followed. Goddard,
Roudsari & Wyatt 2012 (JAMIA 19:121, a systematic review of automation bias) name «the provision of information
versus recommendation» among the design factors that lower it. Jain et al., arXiv 2510.26518 v2 (2026): people
checking AI fact verdicts did better than unaided when shown only the search results and evidence - 79.3 % vs 71.3 %
on the claims the AI got right (p = .009), no loss on the ones it got wrong - while showing its label, explanation
and confidence led to over-reliance. So part 2 shows the words, the passage, the question and the plain facts that
put a quotation early; it never says the quotation passed.

🔴 THE ORDER IS A HEURISTIC, MEASURED FOR WHAT IT FIRES ON, NOT FOR WHAT IT FINDS. Nobody has labelled which clean
quotations are defective (K037's reading was skipped, 2026-11-26), so no fact is graded by the defects it finds.
K047 counted them on a copy of a filed petition, 68 clean quotations: a limiter word next to the words 27 (one
reader of the law text judged about 15 of those to bear on the quoted words - the rest sit in a sibling list item),
words left out 10, no citation beside it 17, numbers 31, an OCR layer 0, another speaker 0, a «may» against a
«must / shall» 0 (that draft writes must / shall only inside quotations - a second count over its whole text
agreed). Groups run strongest first: what makes the comparison itself unsafe (an OCR layer, another speaker), a
sentence stronger than its source, a limiter, left-out words, no citation, numbers; inside a group, more facts first,
then the quotation used in more places.
"""
from __future__ import annotations

import bisect
import io
import os
import re

from .extract import _alnum_projection, _occurrences
from .facts import _ABBR
from .normalize import normalise, prepare_quote, ellipsis_parts
from .readers import ocr_label
from .verdicts import CLEAN, label, meaning
from .verify import LIMITER_RE, _alnum_span

FILE = "READING-LIST.md"
TIER = "A"              # the filed tier: the list is about what leaves the office
SENTENCES = 2           # source sentences shown before and after the quoted words
CAP = 1500              # characters of source shown on each side, at most
PLACES = 5              # draft places shown for one quotation
CLAIM_CAP = 1200        # characters of one draft sentence shown, at most
QUESTION = "**Does this passage support the sentence?**"

# A full stop after one of these does not end a sentence: «8 U.S.C. 1255», «e.g. a», «Sec. 245», «No. 24-4790».
ABBR = frozenset(_ABBR) | frozenset(
    "u.s u.s.c c.f.r e.g i.e sec secs stat pub l cf id supp app cir fed reg regs art para paras pp p ch vol seq et "
    "al jan feb mar apr jun jul aug sep sept oct nov dec approx admin ann amend cl subch pt n nn ibid op atty".split())
_BOUND = re.compile(r"[.!?][\"'”’)\]]*\s+(?=[\"'“(\[]*[A-Z0-9§(\[])")
_WORD_BEFORE = re.compile(r"([A-Za-z][A-Za-z.'&]*)\.[\"'”’)\]]*$")


def sentence_spans(text):
    """[(start, end)] of the sentences of `text`: a stop followed by a capital, a digit, «§» or a bracket ends one,
    unless the full stop closes an abbreviation, a single letter or a dotted word («U.S.», «C.F.R.»). K047 checked it
    against K037's splitter (another word list, other code): no extra boundary inside 67 of 68 own-sentence parts."""
    out, start = [], 0
    for m in _BOUND.finditer(text):
        if text[m.start()] == ".":
            w = _WORD_BEFORE.search(text[max(start, m.start() - 40):m.start() + 1])
            if w and (w.group(1).lower() in ABBR or len(w.group(1)) == 1 or "." in w.group(1)):
                continue
        out.append((start, m.end()))
        start = m.end()
    if start < len(text):
        out.append((start, len(text)))
    return out or [(0, len(text))]


def _at(spans, pos):
    for k, (x, y) in enumerate(spans):
        if x <= pos < y:
            return k
    return len(spans) - 1


def _flat(s):
    return " ".join((s or "").split())


def _plain(s):
    """Source text for display: whitespace folded, the source's own emphasis markers dropped - the list's bold marks
    the quoted words, and a law page's «**January 1, 2010**» table cells read as quoted (K047: 4 of 72 passages)."""
    return _flat(s).replace("**", "").replace("__", "")


# ----------------------------------------------------------------------------------------------- the source side
def locate(quote, verdict, path, corpus):
    """[(start, end)] of the quoted words in the source's text - one span per piece of an ellipsis quotation - or
    None. The preparation `check` uses (normalise + prepare_quote), then the letters-and-digits projection it falls
    back to; on the K047 copy this located 68 of 68 clean quotations."""
    if not path or corpus is None or path not in getattr(corpus, "_index_of", {}):
        return None
    src = corpus.text_of(path)
    parts = [quote]
    if verdict == "ASSEMBLED" or "..." in quote or "…" in quote:
        parts = list(ellipsis_parts(quote, minlen=1)) or [quote]
    out, lo = [], 0
    for part in parts:
        n = normalise(prepare_quote(part))
        if not n.strip():
            continue
        i = src.find(n, lo)
        if i < 0:
            i = src.find(n)
        if i >= 0:
            out.append((i, i + len(n)))
        else:
            hit = _alnum_span(n, path, corpus)
            if not hit:
                return None
            out.append((hit[0], hit[1]))
        lo = out[-1][1]
    return sorted(out) or None


def passage(text, segs, n=SENTENCES, cap=CAP):
    """The quoted words in their source with `n` sentences on each side. `pieces` = [(text, quoted?)] - the words
    an ellipsis left out are the unquoted pieces; `own_before` / `own_after` = the rest of the quoted words' own
    sentence; `next` = the sentence after it."""
    a, b = segs[0][0], max(y for _x, y in segs)
    lo, hi = max(0, a - 8000), min(len(text), b + 8000)
    win = text[lo:hi]
    sp = sentence_spans(win)
    ia, ib = _at(sp, a - lo), _at(sp, max(a - lo, b - lo - 1))
    s0, s1 = sp[max(0, ia - n)][0], sp[min(len(sp) - 1, ib + n)][1]
    before, after = win[s0:a - lo], win[b - lo:s1]
    pieces, end = [], a
    for x, y in segs:
        if x > end:
            pieces.append((text[end:x], False))
        pieces.append((text[max(x, end):y], True))
        end = max(end, y)
    return {"before": before[-cap:], "after": after[:cap],
            "cut_before": len(before) > cap or (s0 == 0 and lo > 0),
            "cut_after": len(after) > cap or (s1 == len(win) and hi < len(text)),
            "pieces": pieces,
            "own_before": win[sp[ia][0]:a - lo], "own_after": win[b - lo:sp[ib][1]],
            "next": win[sp[ib + 1][0]:sp[ib + 1][1]] if ib + 1 < len(sp) else ""}


# ------------------------------------------------------------------------------------------------ the draft side
# A paragraph ends at a blank line or where a markdown block starts: a quote line, a list item, a heading, a table row.
_BLOCK = re.compile(r"\n(?:[ \t]*\n)+|\n(?=[ \t]*(?:[>#|*+-]|\d{1,3}[.)])[ \t])")
_QUOTE_MARK = re.compile(r"(?:^|\n)[ \t]*>[ \t]?")


def claim(body, a, b):
    """The draft sentence that holds body[a:b]: {"sentence", "outside", "lead"}. `outside` = the sentence without
    the quoted words. When the quotation fills its whole sentence - a blockquote, a quotation standing alone - the
    sentence it serves is the one before it, returned as `lead`."""
    starts = [0] + [m.end() for m in _BLOCK.finditer(body)]
    ka = bisect.bisect_right(starts, a) - 1
    kb = bisect.bisect_right(starts, max(a, b - 1)) - 1
    pa = starts[ka]
    pe = starts[kb + 1] if kb + 1 < len(starts) else len(body)
    par = body[pa:pe]
    sp = sentence_spans(par)
    ia, ib = _at(sp, a - pa), _at(sp, max(a - pa, b - pa - 1))
    s0, s1 = sp[ia][0], sp[ib][1]
    outside = par[s0:a - pa] + " " + par[b - pa:s1]
    lead = ""
    if not re.search(r"[A-Za-zЀ-ӿ]{3}", _QUOTE_MARK.sub(" ", outside)):
        if ia > 0:
            lead = par[sp[ia - 1][0]:sp[ia - 1][1]]
        else:
            k = ka - 1
            while k >= 0 and not body[starts[k]:starts[k + 1]].strip():
                k -= 1
            if k >= 0:
                prev = body[starts[k]:starts[k + 1]]
                ps = sentence_spans(prev)
                lead = prev[ps[-1][0]:] if ps else prev
    qa, qb = a - pa - s0, b - pa - s0
    raw = par[s0:s1]
    shown = raw
    if len(_flat(raw)) > CLAIM_CAP:              # a long sentence: the window around the quoted words, not its head
        room = max(150, (CLAIM_CAP - (qb - qa)) // 2)
        lo, hi = max(0, qa - room), min(len(raw), qb + room)
        shown = ("… " if lo else "") + raw[lo:hi] + (" …" if hi < len(raw) else "")
    lead = _flat(_QUOTE_MARK.sub(" ", lead))
    if len(lead) > CLAIM_CAP:                    # a lead's end stands next to the quotation
        lead = "… " + lead[-CLAIM_CAP:].split(" ", 1)[-1]
    return {"sentence": _flat(_QUOTE_MARK.sub(" ", raw)), "outside": _flat(_QUOTE_MARK.sub(" ", outside)),
            "lead": lead, "shown": _flat(_QUOTE_MARK.sub(" ", shown))}


# ---------------------------------------------------------------------------------------------------- the facts
_LIMITS = re.compile(r"(?:^|[\s,;:(\[—–-])" + LIMITER_RE.pattern.lstrip("^"), re.I)
_ENUM = re.compile(r"^[\s\"'“(\[]*(?:\([A-Za-z0-9]{1,4}\)\s*)*")
_PERMIT = re.compile(r"\b(may(?!\s+not\b)|can(?!not\b)(?!\s+not\b)|generally|ordinarily|usually|typically)\b", re.I)
_OBLIGE = re.compile(r"\b(must|shall|required|requires|mandatory|entitled|always|automatically|necessarily)\b",
                     re.I)
_EDGE_OPEN = re.compile(r"^[\s\"'“(\[]*(?:\.\.\.|…)")
_EDGE_CLOSE = re.compile(r"(?:\.\.\.|…)[\s\"'”.)\]]*$")
# K018c: «headnote» - the words stand only in a decision's headnote (`verify.zone_of`): not the authority's own words,
# so it ranks with «another speaker».
PRIORITY = ("ocr", "speaker", "headnote", "modal", "limiter", "omitted", "uncited", "digits")
NAMES = {"ocr": "an OCR layer", "speaker": "another speaker", "headnote": "the headnote only", "modal": "may against must",
         "limiter": "a limiter next to the words", "omitted": "words left out", "uncited": "no citation beside it",
         "digits": "numbers"}


def signals(row, pas, claims):
    """[(name, note)] - plain facts about one clean quotation, in PRIORITY order. A note says what is there; it never
    grades the quotation."""
    q = row.get("quote") or ""
    out = []
    lab = ocr_label(row.get("ocr_layer"))
    if lab:
        out.append(("ocr", "%s - the words were compared with what the OCR read, not with the page" % lab))
    if row.get("verdict") == "WRONG_SPEAKER":
        out.append(("speaker", "the source recites someone here (a commenter, a party, a dissent)%s"
                    % ((": " + _flat(row.get("detail"))[:200]) if row.get("detail") else "")))
    if (row.get("zone") or {}).get("zone") == "headnote":
        out.append(("headnote", "the words stand only in the decision's headnote - the summary added above the opinion "
                    "when it was published - and nowhere in the opinion itself"))
    pm = _PERMIT.search(q)
    if pm:
        for c in claims:
            om = _OBLIGE.search(" ".join((c.get("outside") or "", c.get("lead") or "")))
            if om:
                out.append(("modal", "the source says «%s»; the sentence around it says «%s»"
                            % (pm.group(1), om.group(1))))
                break
    if pas:
        found = []
        for where, text, opening in (("earlier in the quoted words' own sentence", pas["own_before"], False),
                                     ("later in their own sentence", pas["own_after"], False),
                                     ("opening the next sentence", pas["next"], True)):
            m = LIMITER_RE.match(_ENUM.sub("", text)) if opening else _LIMITS.search(text)
            if m:
                found.append("«%s» %s" % (m.group(1), where))
        if found:
            out.append(("limiter", "in the source: " + "; ".join(found)))
        gaps = [t for t, quoted in pas["pieces"] if not quoted]
        edge = [w for w, rx in (("opens", _EDGE_OPEN), ("closes", _EDGE_CLOSE)) if rx.search(q)]
        if gaps or edge:
            out.append(("omitted", "; ".join(
                (["words left out between the quoted pieces: %d characters, in italics below"
                  % sum(len(_flat(g)) for g in gaps)] if gaps else []) +
                ["the quotation %s with an ellipsis - the words it leaves out stand in the passage" % w
                 for w in edge])))
    if not row.get("near"):
        out.append(("uncited", "no citation printed beside the quotation; the words were found in `%s`"
                    % (row.get("where") or "?")))
    if re.search(r"\d", q):
        out.append(("digits", "numbers in the quotation"))
    return out


def order_key(entry):
    """Strongest fact first, then more facts, then the quotation used in more places, then REPORT.md's order."""
    names = [n for n, _note in entry["signals"]]
    top = min((PRIORITY.index(n) for n in names), default=len(PRIORITY))
    return (top, -len(names), -len(entry["places"]), -len(entry["row"].get("sites") or ()), entry["index"])


def build(res):
    """The list's entries: every row with a site in the filed tier, flagged ones first in REPORT.md's order (the
    rows arrive sorted that way), then the clean ones by `order_key`."""
    corpus = res.get("corpus")
    bodies = {rel: body for t, rel, body, _m in (res.get("docs") or []) if str(t)[:1] == TIER}
    proj, entries = {}, []
    for k, r in enumerate(res.get("rows") or []):
        files = sorted({s["file"] for s in r.get("sites") or () if str(s.get("tier"))[:1] == TIER})
        if not files:
            continue
        places = []
        for rel in files:
            if rel not in bodies:
                continue
            if rel not in proj:
                proj[rel] = _alnum_projection(bodies[rel])
            places += [(rel, claim(bodies[rel], a, b)) for a, b in _occurrences(proj[rel], r["quote"])]
        segs = locate(r["quote"], r["verdict"], r.get("where_abs"), corpus)
        pas = passage(corpus.text_of(r["where_abs"]), segs) if segs else None
        flagged = r["verdict"] not in CLEAN
        entries.append({"row": r, "index": k, "flagged": flagged, "places": places, "passage": pas,
                        "signals": [] if flagged else signals(r, pas, [c for _f, c in places])})
    return [e for e in entries if e["flagged"]] + sorted((e for e in entries if not e["flagged"]), key=order_key)


def counts(entries):
    rest = [e for e in entries if not e["flagged"]]
    return {"quotations": len(entries), "flagged": len(entries) - len(rest), "rest": len(rest),
            "facts": {n: sum(1 for e in rest if any(s == n for s, _x in e["signals"])) for n in PRIORITY},
            "none": sum(1 for e in rest if not e["signals"])}


def summary(c):
    """One line - the console and the file say the same."""
    facts = ", ".join("%s %d" % (NAMES[n], c["facts"][n]) for n in PRIORITY)
    return ("%d quotation(s) of the filed documents: %d flagged first, then %d by the facts noted (%s; none %d)"
            % (c["quotations"], c["flagged"], c["rest"], facts, c["none"]))


def _quote_block(text, cap=None):
    t = _flat(text)
    if cap and len(t) > cap:
        t = t[:cap].rsplit(" ", 1)[0] + " …"
    return "> " + t


def _source_lines(e, lang="en"):
    r, pas = e["row"], e["passage"]
    where = r.get("where") or ""
    page = (r.get("page") or {}).get("label") if isinstance(r.get("page"), dict) else ""
    zone = (r.get("zone") or {}).get("label") if isinstance(r.get("zone"), dict) else ""   # K018c
    head = "**In the source** - `%s`%s:" % (where, "".join(", " + x for x in (page, zone) if x))
    if not pas:
        if e["flagged"]:
            return ["**In the source:** no passage shown - the quoted words are not in a source as written. "
                    "REPORT.md, section «%s», shows what was found." % label(r["verdict"], lang)]
        return ["**In the source:** no passage could be cut from `%s` - open it at the quoted words." % where]
    body = []
    for text, quoted in pas["pieces"]:
        body.append(("**%s**" if quoted else "_[left out: %s]_") % _plain(text))
    line = "%s%s %s %s%s" % ("… " if pas["cut_before"] else "", _plain(pas["before"]), " ".join(body),
                             _plain(pas["after"]), " …" if pas["cut_after"] else "")
    return [head, "> " + line.strip()]


def write(entries, out_dir, lang="en", sentinel="", judge=None):
    """READING-LIST.md in `out_dir`; returns its path. It carries the tool-output sentinel at its head, so a
    later check never counts its quotations as the matter's own writing. `judge` (K061b, `check --judge`): the
    entries arrive with the model's doubts first in part 2; the file says how part 2 was ordered and by which
    model - and nothing about any one quotation (judge.py says why)."""
    c = counts(entries)
    part2 = ("Part 2 holds the rest, ordered by the facts noted beside each one - %s - and then the ones with "
             "none of them." % ", ".join(NAMES[n] for n in PRIORITY))
    head2 = "## Part 2 - the rest, by the facts noted (%d)"
    if judge:
        part2 = ("Part 2 holds the rest. You asked a model to read them (`check --judge %s`, model `%s`; it was "
                 "sent each one's draft sentence, quotation, citation and passage as shown here): the ones it "
                 "doubted come first, then the others, each group ordered by the facts noted beside each one - "
                 "%s. The model's doubt only moved a quotation up; a quotation it did not doubt is not cleared "
                 "by it, so read every passage." % (judge["channel"], judge["model"],
                                                    ", ".join(NAMES[n] for n in PRIORITY)))
        head2 = "## Part 2 - the rest, a model's doubts first, then by the facts noted (%d)"
    md = ["<!-- %s : generated by `krokai check` - the quotations of the filed documents beside their sources. "
          "Not a primary source and not our argument. -->" % sentinel,
          "# Reading list - the filed documents' quotations beside their sources", "",
          "Every quotation in the filed documents (tier A), the sentence that uses it and the passage of the "
          "source it was found in. The check compared the words; whether a passage supports the sentence that "
          "quotes it is a question of reading, which no word comparison answers - read each passage and answer "
          "the question under it yourself.", "",
          "Part 1 holds the quotations the check flagged, in REPORT.md's order (REPORT.md says what is wrong with "
          "each). %s This file keeps no marks: every `krokai check` writes it anew." % part2, "",
          summary(c) + ".", ""]
    if not entries:
        md += ["No quotation was found in a document of the filed tier (A). REPORT.md covers every tier.", ""]
    n = 0
    for part, title in ((True, "## Part 1 - flagged (%d)" % c["flagged"]),
                        (False, head2 % c["rest"])):
        sel = [e for e in entries if e["flagged"] is part]
        if not sel:
            continue
        md += [title, ""]
        for e in sel:
            n += 1
            r = e["row"]
            md += ["### %d. %s" % (n, "; ".join(r.get("cites") or ()) or "no citation printed beside it"), ""]
            if part:
                md += ["**%s** - %s" % (label(r["verdict"], lang), meaning(r["verdict"], lang)), ""]
            else:
                md += ["**Noted:** " + (" · ".join(note for _n, note in e["signals"]) or "nothing"), ""]
            for j, (rel, cl) in enumerate(e["places"][:PLACES]):
                if cl["lead"]:
                    md += ["**In the draft** - `%s`, the sentence before the quotation:" % rel,
                           _quote_block(cl["lead"]), ""]
                else:
                    md += ["**In the draft** - `%s`:" % rel, _quote_block(cl["shown"]), ""]
            if len(e["places"]) > PLACES:
                md += ["… and %d more place(s) in the draft." % (len(e["places"]) - PLACES), ""]
            if not e["places"]:
                md += ["**In the draft:** used in %s" % ", ".join("`%s`" % s["file"] for s in r.get("sites") or ()
                                                                 if str(s.get("tier"))[:1] == TIER), ""]
            md += ["**Quoted:**", _quote_block(r["quote"]), ""]
            md += _source_lines(e, lang) + [""]
            if e["passage"]:
                md += [QUESTION, ""]
    path = os.path.join(out_dir, FILE)
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(md))
    return path, c
