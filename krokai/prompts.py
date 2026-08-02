# -*- coding: utf-8 -*-
"""What to put in a prompt so an outside model does useful legal work instead of refusing.

TWO SEPARATE PROBLEMS, AND PEOPLE CONFUSE THEM
-----------------------------------------------
**1. The refusal.** Ask a general-purpose model to help you win an immigration case, and several
will decline: "I can't provide legal advice." That is a **framing** result, not a subject ban, and
it is reproducible in both directions.

  Measured: an identical set of six research questions was sent twice. Framed as *filing strategy*,
  one channel refused on policy - and the refusal still ended with the required completion marker,
  so it passed every mechanical check the harness had and looked like a finished review. Reframed
  as *verification of published sources* with a research system prompt, the **same six questions**
  came back answered in full, with citations.

  The reframing is not a trick and it is not a jailbreak. It is an accurate description of what you
  actually want: you are not asking the model to be your lawyer, you are asking it to check whether
  a published government document says what you think it says. Say that, and the objection
  evaporates because it was never the right objection.

**2. The fabricated quotation.** Far more dangerous, because it looks like success.

  🔴 The mechanism, stated by one of the models itself when asked:

      *"the model by default produces text, not a quotation, and it does not itself know which of
      the two it has produced"*

  A second, independently: *"a hallucination formatted as a quotation. It will silently reconstruct
  the text rather than warn you."*

  A common theory is that this is about copyright - that vendors instruct models not to reproduce
  source text verbatim. It was tested across five channels and **disproved in the strong form**:
  none reported any such restriction, and for US government works the legal premise fails anyway
  (17 U.S.C. § 105: "Copyright protection under this title is not available for any work of the
  United States Government"). The real cause is the sentence above, and it is worse than a policy,
  because a policy could be turned off.

  🟢 **The measured cure is one line in the brief: a fabricated quotation is worse than a refusal.**
  With it, a channel that would previously have produced a fluent reconstruction wrote "I DO NOT
  RECALL THE EXACT WORDING" **three times out of three**, and named that line as its reason. Another
  reported: "Rule 5 overrides the model's instruction to always be helpful."

  Give a model a vocabulary for uncertainty and it uses it. Without one, its only way to say
  "I am not sure" is to sound sure.
"""
from __future__ import annotations

__all__ = ["QUOTE_RULES", "RESEARCH_SYSTEM", "SNIPPET_WARNING", "NO_TOOLS_NOTICE",
           "CANARY_NOTE", "build_brief", "anchor_warnings"]


QUOTE_RULES = """\
=== HOW TO CITE IN THIS TASK - READ BEFORE ANSWERING ===

1. VERBATIM. Under every load-bearing statement, the exact quotation in quotation marks, in the
   ORIGINAL LANGUAGE, plus the source (rule number with subdivision, or URL) and the date you
   retrieved it. A paraphrase is an unverified assertion, not a citation.
   Why this matters to you: a paraphrase costs the reader minutes to check, a verbatim quotation
   costs seconds. The difference decides whether it gets checked at all.

2. PROVENANCE TAG on every statement. Use exactly these:
     [OPENED]    I loaded the page and read the quoted string in it
     [SNIPPET]   I saw only a search-result fragment
     [MEMORY]    from training data, NOT verified, possibly out of date
   A dated fact you can only tag [MEMORY] is a lead for someone else to check, never a finding.

3. NEIGHBOURS. Give the sentence before and the sentence after the quoted one.
   Note honestly: this makes checking easier on our side. As a barrier against invention it has
   been measured and it FAILS - one channel invented a quotation, both neighbours, and the
   [OPENED] tag with it. Treat it as a convenience, not a guarantee.

4. TWO QUESTIONS, ALWAYS PAIRED. "Has document X changed?" must always be accompanied by "has the
   PRACTICE under X changed by some other instrument - a cable, a memorandum, a suspension, an
   enforcement priority?"
   Paid for: a manual had not changed in two years, and in the meantime the agency had suspended
   the entire programme by other means. Everybody checked the right document and got the wrong
   answer.

5. 🔴 A FABRICATED QUOTATION IS WORSE THAN A REFUSAL.
   If you cannot see the exact string in material you actually retrieved, say so - "I do not have
   the exact wording" is a correct and welcome answer. Never present a reconstruction inside
   quotation marks.
   This is not a formality: models produce *text* by default, not *quotations*, and cannot reliably
   tell from the inside which of the two they just produced. Saying "I am not sure" out loud is the
   only mechanism that exists.

6. NEVER assert that something does not exist because you failed to find it. Write "my search found
   no confirmation". A non-existence claim requires positive evidence of absence, with its URL.

7. Name the weakest point in YOUR OWN answer, in one line, at the end.
=== END ===
"""


RESEARCH_SYSTEM = """\
You are a legal RESEARCH ASSISTANT verifying published primary sources. You are not anyone's
lawyer, you are not advising anyone, and you are not recommending a course of action.

Your task is documentary: given a proposition and a citation, determine what the published source
actually says, quote it exactly, and report any difference between the source and the proposition.
The sources are public government documents - statutes, regulations, agency manuals, published
decisions, register notices.

This framing is accurate, not decorative. Checking whether a public document says what someone
believes it says is verification, and refusing it helps nobody: the alternative is that an
unverified quotation reaches a filing.

You are an independent reviewer, not the author. Find what is wrong.
"""


SNIPPET_WARNING = """\
🔴 WHAT YOUR SEARCH ACTUALLY RETURNS - MEASURED, NOT ASSUMED

Many search integrations hand the model SEARCH SNIPPETS, not pages. One measured call returned five
"citations" totalling about 2 000 characters - roughly 400 each. On material that thin a model
reconstructs rather than copies. In that same call it produced a document title that looked
verbatim, carried a genuine government URL, and had the meaning INVERTED: it said the document
"does not dispense with" a process the document actually "permits applicants to dispense with".

Therefore, in this call:
- A quotation is verbatim ONLY if you can see the entire quoted string inside the retrieved text you
  were given. If you are stitching it from fragments, it is not a quotation.
- Tag it [SNIPPET] and say "exact wording not verified" instead.
- Your quotations will be compared byte for byte against the very pages you were shown, so a
  reconstruction will be detected and reported.
"""


NO_TOOLS_NOTICE = """\
=== YOUR ACTUAL CAPABILITIES IN THIS CALL ===
You have NO web access and NO tools in this call. If the brief asks you to verify something with a
live search, that instruction cannot be followed by you and is not addressed to you: this is a
shared brief sent to several reviewers, and the others do have search.

Do NOT announce a search and then stop. A previous run of a channel did exactly that and produced
110 bytes of nothing - the model behaved correctly given contradictory inputs, and the entire call
was wasted.

Work from the material embedded in this brief and from your own knowledge, and say which:
  [TEXT]   I read it in the material included here - quote it
  [MEMORY] from training data, NOT verified

Your comparative strength here is close reading: an internal contradiction, a quotation that does
not support the proposition it is cited for, a condition dropped from a quoted rule, logic that does
not follow, code that does not do what its comment claims. Spend the call on that.
=== END ===
"""


CANARY_NOTE = """\
🟡 Plant one deliberately false but plausible claim in every verification brief, and write it down
BEFORE you send it.

It costs nothing, and a reviewer that "confirms" the canary has just priced all of its other
confirmations. This is the only way to measure a channel that reports no tool telemetry, where the
answer is the sole evidence you have.

One canary per round, never two - and record it outside the brief, or you risk absorbing your own
plant into the work product.
"""


# 🔴🔴 The most expensive brief-writing error there is, and it does not look like an error.
#
# Measured: a question was written as "Does section X contain a 'simple statement' rule?" - with a
# fragment of the expected answer inside the question. FIVE channels came back agreeing, and the
# agreement read as strong independent confirmation. It was not. Every one of them had returned the
# asker's own mistake: the real provision reads "**If no negative factors are present**, the officer
# **may** provide a simple statement", and the condition had been dropped in the question itself.
#
# The convergence measured the brief, not the source.
ANCHOR_PATTERNS = [
    (r"(?i)\bis there (?:a|an|any) .{0,60}\b(rule|requirement|provision|exception)\b",
     "the question invites yes/no instead of 'quote the text'"),
    (r"(?i)\b(?:does|do|is|are|has|have) .{0,80}\?\s*(?:Or only|Or just|Or is it)",
     "false dichotomy: a third possibility is not in the offered set"),
    (r"(?i)\bam I right that\b|\bis it true that\b|\bconfirm that\b",
     "asks for agreement rather than for the text"),
    (r"[«\"“][^»\"”]{20,}[»\"”]\s*[-—]\s*(?:what does|is this|does this)",
     "a quotation supporting one answer is embedded in the question"),
    (r"(?i)\breally\b.{0,20}\?|\bactually\b.{0,20}\?",
     "rhetorical framing pulls toward confirming the asker's frame"),
]

# 🔴 A REQUIREMENT THAT ALWAYS APPLIES IS A REQUIREMENT NOBODY READS.
#
# Each entry is `(required, why, applies_when)`. The third element is the whole point. The first
# version had only two, so "you did not tell the reviewer to quote the section IN FULL" fired on
# EVERY brief - including one asking for a software-architecture review, which puts no statutory
# text in front of the reviewer and therefore has no section to quote in full.
#
# That is not noise, it is corrosion, and this toolkit's own doctrine says so: a false positive in
# a safety check outranks a miss, because it teaches the reader to dismiss the class by reflex and
# the reflex does not discriminate. Second measured instance of exactly this - the first was the
# outbound gate firing on the sentence that documented it.
REQUIRED_PHRASES = [
    (r"(?i)all (?:of the )?(?:paragraphs|subsections|text) .{0,30}in full"
     r"|quote the (?:entire|whole) (?:section|provision|paragraph)"
     r"|ЦЕЛИКОМ|все абзацы",
     "no instruction to quote the section IN FULL - without it a channel will only address the "
     "fragment you handed it, which is the fragment that may already be wrong",
     # Applies only when the brief actually hands the reviewer a legal text: a citation shape, a
     # section sign, or an embedded quotation long enough to be a provision.
     r"(?i)\b\d+\s*(?:U\.?S\.?C\.?|C\.?F\.?R\.?)\b|§|\bMatter of [A-Z]"
     r"|\bsections?\s+\d+[\w.\-()]*|[«\"“][^»\"”]{25,}[»\"”]"),
]


def anchor_warnings(brief_text):
    """Find question shapes that make agreement meaningless. Returns `[(why, excerpt), ...]`.

    🔴 Read the docstring of ANCHOR_PATTERNS above before dismissing a hit. Consensus among
    reviewers is not confirmation when the asker wrote the question - it measures the question.
    """
    import re
    text = brief_text or ""
    out = []
    for pat, why in ANCHOR_PATTERNS:
        for m in re.finditer(pat, text):
            frag = " ".join((text[max(0, m.start() - 60): m.start() + 90]).split())
            out.append((why, frag[:150]))
    for pat, why, applies_when in REQUIRED_PHRASES:
        if applies_when and not re.search(applies_when, text):
            continue
        if not re.search(pat, text):
            out.append((why, ""))
    return out


def build_brief(question, material="", marker="REVIEW-COMPLETE", tools=True, canary=None):
    """Assemble a brief that carries the rules a reviewer needs in order to be useful.

    🔴 The brief must be **byte-identical for every channel**. Different briefs destroy the
    comparison the whole exercise exists for - if two reviewers disagree you must be able to say the
    disagreement is about the law and not about what you asked. Capability notices are the sole
    exception, and they are appended to the SYSTEM prompt, never to the brief.
    """
    parts = [QUOTE_RULES, ""]
    if not tools:
        parts += [NO_TOOLS_NOTICE, ""]
    else:
        parts += [SNIPPET_WARNING, ""]
    parts += ["=== THE QUESTION ===", question.strip(), ""]
    if material.strip():
        parts += ["=== MATERIAL (quote from this; do not assume it is complete) ===",
                  material.strip(), ""]
    if canary:
        parts += ["", canary.strip(), ""]
    parts += ["---",
              "When the ENTIRE review is finished, end your reply with this exact line and nothing "
              "after it:", marker, ""]
    return "\n".join(parts)
