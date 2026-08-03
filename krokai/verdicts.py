# -*- coding: utf-8 -*-
"""The verdict vocabulary: fifteen outcomes, not two.

WHY NOT "PASS / FAIL"
---------------------
Because the interesting failures are not "the quotation is missing". They are the ones where the
**strings match and the meaning does not** - and a two-valued checker answers those with a
cheerful green.

Three of the fifteen exist solely because a pass/fail tool said VERIFIED about a defect that would
have gone into a filing:

* ``TRUNCATED_CONDITION`` - the quotation is an exact substring, and the source **continues** with
  the clause that limits it. Measured: 10 of 592 already-VERIFIED quotations, one of them in a
  document about to be filed. A substring test cannot express *completeness*, so completeness got
  its own test.
* ``ELLIPSIS_HIDES`` - every fragment of an ellipsis quotation exists, in order, in one document -
  and the **elided span** carries the words that narrow the rule to a class the client is not in.
* ``FOUND_ELSEWHERE`` - the words are in the corpus, verbatim, but **not in the document whose
  address stands next to them**.

SEVERITY IS NOT THE SAME AS SORT ORDER
--------------------------------------
The report sorts by "read this first", which is dominated by how expensive it is to be wrong, not
by how likely the tool is to be right. ``TRUNCATED_CONDITION`` outranks ``NOT_FOUND`` because a
missing source is usually a download you have not done, while a dropped proviso is an argument that
is not true.

🔴 A KNOWN LIMIT, STATED HERE SO IT IS NOT MISTAKEN FOR COVERAGE
----------------------------------------------------------------
No string comparison can catch **the right words under a pincite to the wrong page of the right
document**. Measured: a published checklist quoted a decision's editorial *headnote* while citing
the page of the *opinion*, where the sentence reads differently by one word that matters. Both
sentences are genuinely in the PDF, so this tool says VERIFIED and always will. That class needs a
reader - see ``judge.py``.
"""
from __future__ import annotations

__all__ = ["ORDER", "DANGEROUS", "CLEAN", "UNCHECKABLE", "LABEL", "MEANING", "MARK",
           "label", "meaning"]

# Read-this-first order. Not alphabetical, not by frequency: by what it costs to be wrong.
ORDER = [
    "TRUNCATED_CONDITION",
    "TRUNCATED_OPENING",
    "OPERATOR",
    "SPLICED",
    "FOUND_ELSEWHERE",
    "ELLIPSIS_HIDES",
    "NOT_FOUND",
    "NO_SOURCE_ON_DISK",
    "PARTIAL",
    "ALTERED",
    "SCATTERED",
    "WRONG_SPEAKER",
    "PUNCTUATION",
    "TYPESETTING",
    "ASSEMBLED",
    "VERIFIED",
]

# Verdicts that must be read by a human before the document goes anywhere.
DANGEROUS = ["TRUNCATED_CONDITION", "TRUNCATED_OPENING", "OPERATOR", "SPLICED", "FOUND_ELSEWHERE",
             "ELLIPSIS_HIDES", "PARTIAL", "ALTERED", "SCATTERED", "NOT_FOUND"]

# Verdicts meaning "the words are genuinely in the source". NOT the same as "the quotation is
# sound": WRONG_SPEAKER and ASSEMBLED are here and both can still be misleading in context.
#
# 🔴 SCATTERED is deliberately NOT here, and the self-test enforces it. Every sentence being
# verbatim while the sentences are not adjacent in the source is a defect, not a pass: it presents
# as one continuous passage something the authority never wrote as one. Putting it in both lists was
# a real slip in the first draft of this file, and the invariant below is what caught it.
CLEAN = ["VERIFIED", "ASSEMBLED", "PUNCTUATION", "TYPESETTING", "WRONG_SPEAKER"]

# 🔴 THE THIRD BUCKET, AND WHY TWO WERE NOT ENOUGH.
#
# `NOT_FOUND` used to mean two different things and its own MEANING string admitted it: *"either the
# source is not downloaded, or invented."* Those are not variations of one finding. One is a
# download you owe; the other is a sentence the authority never wrote. Describing the ambiguity is
# not the same as resolving it, and the tool had the information to resolve it all along - the
# address printed beside the quotation.
#
# Measured in the sister project on a real filing: **20 of 37 red items** were quotations of agency
# press releases and FAQ pages whose sources are not in the corpus BY CONSTRUCTION, because the
# corpus holds law. They were graded identically to genuine misses, so the list of things to read
# was two-thirds noise - and a list that is mostly noise is a list nobody finishes. The real misses
# were hiding among them.
#
# 🔴 UNCHECKABLE IS NOT A PASS, and the wording everywhere says so. The dangerous reading of this
# verdict is "the tool did not object", and a fabricated quotation under a fabricated citation would
# land here. Two things prevent that from becoming an escape hatch:
#   * it is excluded from CLEAN, counted separately, and never reported as a success;
#   * it is only reachable when the address resolves to NOTHING on disk. If the cited source IS on
#     disk and the words are not in it, the verdict stays NOT_FOUND - which is the fabrication
#     shape, and `fold()` says so in the detail rather than softening it.
UNCHECKABLE = ["NO_SOURCE_ON_DISK"]

# Invariant, asserted by the self-test: every verdict is in exactly one of the three lists. A
# verdict in none is unclassified and will be silently treated as harmless by anything that
# iterates - which is the mistake this invariant caught once already.

MARK = {
    "TRUNCATED_CONDITION": "!!", "TRUNCATED_OPENING": "!!", "OPERATOR": "!!",
    "SPLICED": "!!", "FOUND_ELSEWHERE": "!!",
    "ELLIPSIS_HIDES": "! ", "NOT_FOUND": "! ", "NO_SOURCE_ON_DISK": "? ",
    "PARTIAL": "! ", "ALTERED": "! ",
    "SCATTERED": "  ", "WRONG_SPEAKER": "~ ", "PUNCTUATION": "  ", "TYPESETTING": "~ ",
    "ASSEMBLED": "  ", "VERIFIED": "OK",
}

LABEL = {
    "en": {k: k.replace("_", " ").lower() for k in ORDER},
    "ru": {
        "VERIFIED": "ДОСЛОВНО",
        "TRUNCATED_CONDITION": "ОБРЕЗАНО УСЛОВИЕ",
        "TRUNCATED_OPENING": "ОБРЕЗАНО НАЧАЛО",
        "OPERATOR": "НЕСУЩЕЕ СЛОВО",
        "SPLICED": "СКЛЕЙКА",
        "FOUND_ELSEWHERE": "НАЙДЕНО НЕ ТАМ",
        "ELLIPSIS_HIDES": "МНОГОТОЧИЕ СКРЫЛО",
        "ASSEMBLED": "СБОРНАЯ",
        "PUNCTUATION": "ПУНКТУАЦИЯ",
        "TYPESETTING": "ВЁРСТКА",
        "SCATTERED": "ПО ЧАСТЯМ",
        "ALTERED": "ИЗМЕНЁН ХВОСТ",
        "PARTIAL": "ЧАСТИЧНО",
        "NOT_FOUND": "НЕ НАЙДЕНО",
        "NO_SOURCE_ON_DISK": "ИСТОЧНИКА НЕТ НА ДИСКЕ",
        "WRONG_SPEAKER": "ЧУЖОЙ ГОЛОС",
    },
}
LABEL["en"]["VERIFIED"] = "verified"
LABEL["en"]["NOT_FOUND"] = "not found"
LABEL["en"]["NO_SOURCE_ON_DISK"] = "no source on disk"

MEANING = {
    "en": {
        # 🔴 "in a file you put in your sources folder", NOT "in the law". Four independent reviewers
        # of this design, asked separately what defect the analysis could not see, named the same
        # one: the corpus is a set of downloads whose provenance is asserted and never proven, so a
        # repealed, superseded, mis-scraped or wrong-year file verifies exactly as well as the law
        # does. The old wording - "present word for word in a primary source" - claimed the second
        # thing while measuring the first, which is this toolkit's own headline defect turned inward.
        "VERIFIED": "word for word in a file in your sources folder - which is not the same as "
                    "'in force today'",
        "TRUNCATED_CONDITION": "!! exact - but the source CONTINUES with the clause that limits it",
        "TRUNCATED_OPENING": "!! exact - but the quotation starts AFTER a negation that governs it",
        "OPERATOR": "!! the difference touches not/unless/only/may/shall - the rule may be inverted",
        "SPLICED": "!! the fragments exist, but no single document holds them in order",
        "FOUND_ELSEWHERE": "!! verbatim in the corpus - but NOT in the document cited beside it",
        "ELLIPSIS_HIDES": "! the fragments are there; the ellipsis hides words that narrow the rule",
        "NOT_FOUND": "absent from the corpus, AND the cited source is one you have - so this is "
                     "the shape a fabrication makes",
        "NO_SOURCE_ON_DISK": "? NOT CHECKED - the address beside it names something you have not "
                             "downloaded. This is not a pass: get the source and run again",
        "PARTIAL": "! 50-85 % located - read it",
        "ALTERED": "! the opening is in the source, the whole is not => the TAIL was changed",
        "SCATTERED": "each sentence is verbatim, but they are not adjacent in the source",
        "WRONG_SPEAKER": "~ verbatim - but the source is reciting a commenter or a party here",
        "PUNCTUATION": "same words, same order, punctuation differs",
        "TYPESETTING": "~ the CORPUS copy is damaged (line-break hyphen, welded footnote, header)",
        "ASSEMBLED": "ellipsis quotation, all fragments found in order, nothing material hidden",
    },
    "ru": {
        "VERIFIED": "дословно есть в первоисточнике",
        "TRUNCATED_CONDITION": "!! дословно — но источник продолжается оговоркой, которую цитата обрывает",
        "TRUNCATED_OPENING": "!! дословно — но цитата начата ПОСЛЕ отрицания, которое ею управляет",
        "OPERATOR": "!! расхождение задело not/unless/only/may/shall — смысл может быть перевёрнут",
        "SPLICED": "!! куски есть, но ни в одном документе не идут подряд",
        "FOUND_ELSEWHERE": "!! дословно есть в корпусе — но НЕ в том документе, чей адрес указан рядом",
        "ELLIPSIS_HIDES": "! куски найдены, многоточие скрыло слова, сужающие норму",
        "NOT_FOUND": "в корпусе нет, а указанный источник у вас ЕСТЬ — это форма выдумки",
        "NO_SOURCE_ON_DISK": "? НЕ ПРОВЕРЕНО — адрес рядом называет то, что не скачано. "
                             "Это не «чисто»: скачайте источник и прогоните снова",
        "PARTIAL": "! найдено 50–85 % — разбирать",
        "ALTERED": "! начало есть, целого нет ⇒ изменён хвост",
        "SCATTERED": "каждое предложение дословно, но в источнике они не рядом",
        "WRONG_SPEAKER": "~ дословно — но источник здесь пересказывает комментатора или сторону",
        "PUNCTUATION": "слова и порядок те же, знаки разошлись",
        "TYPESETTING": "~ испорчен КОРПУС (перенос, колонтитул, вклеенная сноска), а не цитата",
        "ASSEMBLED": "цитата с многоточием, все куски найдены по порядку",
    },
}


def label(verdict, lang="en"):
    return LABEL.get(lang, LABEL["en"]).get(verdict, verdict)


def meaning(verdict, lang="en"):
    return MEANING.get(lang, MEANING["en"]).get(verdict, "")
