"""Check a tip the user was sent against the news, by the same rule the watcher confirms with.

    answer = check_tip(claim, profile, services, now)

Search the last tip_lookback_days, keep only the articles the cheap model says report the same
claim, then group.confirm() them. A confirmed tip that the judge maps to an event type also
gets its history line from engine.odds(). Every sentence in the template is code-written.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Callable
from typing import Final

from networth import brief, net
from networth.app.services import Services
from networth.app.store import Profile
from networth.bot.message import LANGS, Link, say
from networth.brief.lines import Line
from networth.chat.answer import Answer
from networth.chat.today import EVERY_CASE
from networth.config import Query
from networth.engine.model import Region
from networth.llm import ArticleBrief, Classified, StoryForJudge
from networth.watcher import classify, group, pull
from networth.watcher.store import Article, Confirmed

log = logging.getLogger("networth.chat")

CLAIM_CHARS: Final = 300
TITLE_CHARS: Final = 120
TIP_TASK: Final = "Tell a beginner, in a short chat message, what we found about the tip they sent."
HYPE: Final = re.compile(
    r"\b(sure[- ]?shot|guarantee\w*|multi-?bagger\w*|will (double|triple)|double|triple|"
    r"(buy|sell)( \w+){0,3} now|insider\w*|urgent|jaldi|abhi|"
    r"before (friday|monday|tomorrow|it's too late)|"
    r"pakka|rocket\w*|to the moon|lock kar\w*)\b|🚀",
    re.IGNORECASE,
)
CANT_SEARCH: Final = {
    "en": "I can't search the news right now, so I can't check this yet. You can send it again "
    "in a few minutes.",
    "hi": "मैं अभी ख़बरें नहीं खोज पा रहा, इसलिए इसे जाँच नहीं सकता। कुछ मिनट बाद इसे फिर भेज सकते हैं।",
    "hinglish": "Main abhi news search nahin kar pa raha, isliye ise check nahin kar sakta. Kuch "
    "minute baad ise phir bhej sakte hain.",
}
NOT_FOUND: Final = {
    "en": "Not confirmed. I searched the last {days} days of news, and no publisher is "
    "reporting this.",
    "hi": "पुष्टि नहीं हुई। मैंने पिछले {days} दिनों की ख़बरें खोजीं, और कोई पब्लिशर इसे रिपोर्ट नहीं कर रहा।",
    "hinglish": "Confirm nahin hua. Maine pichhle {days} din ki news search ki, aur koi "
    "publisher ise report nahin kar raha.",
}
TOO_FEW: Final = {
    "en": "Not confirmed. Only {who} reported this in the last {days} days. We call news "
    "confirmed when at least {k} publishers report it within {h} hours, or an official source "
    "posts it.",
    "hi": "पुष्टि नहीं हुई। पिछले {days} दिनों में सिर्फ़ {who} ने इसे रिपोर्ट किया। हम किसी ख़बर "
    "को तभी पुष्ट मानते हैं जब कम से कम {k} पब्लिशर उसे {h} घंटों के अंदर रिपोर्ट करते हैं, या "
    "कोई आधिकारिक स्रोत उसे जारी करता है।",
    "hinglish": "Confirm nahin hua. Pichhle {days} din mein sirf {who} ne ise report kiya. Hum "
    "news ko tabhi confirmed maante hain jab kam se kam {k} publishers {h} ghante ke andar use "
    "report karte hain, ya koi official source use post karta hai.",
}
CONFIRMED: Final = {
    "en": "Confirmed. {who} reported it{official}.",
    "hi": "पुष्टि हुई। {who} ने इसे रिपोर्ट किया{official}।",
    "hinglish": "Confirmed. {who} ne ise report kiya{official}.",
}
OFFICIAL: Final = {
    "en": ", and {source} posted it",
    "hi": ", और {source} ने इसे जारी किया",
    "hinglish": ", aur {source} ne ise post kiya",
}
HISTORY_SAYS: Final = {
    "en": "What history says: {line}",
    "hi": "इतिहास क्या कहता है: {line}",
    "hinglish": "History kya kehti hai: {line}",
}
HYPE_NOTE: Final = {
    "en": "The message also uses hype: {quoted}. Real news rarely needs it.",
    "hi": "इस मैसेज में हाइप वाले शब्द भी हैं: {quoted}। असली ख़बर को इनकी ज़रूरत कम ही पड़ती है।",
    "hinglish": "Is message mein hype wale words bhi hain: {quoted}. Asli news ko inki zaroorat "
    "kam hi padti hai.",
}


def _articles(claim: str, services: Services, now: dt.datetime) -> list[Article]:
    cfg = services.cfg
    query = Query((), Region.IN, claim[:CLAIM_CHARS], (), "")
    since = now - dt.timedelta(days=cfg.product.tip_lookback_days)
    raw = services.search.search(query, since)
    parsed = (pull.parse_result(r, query, now, cfg.confirm) for r in raw)
    return list({a.url: a for a in parsed if a is not None}.values())


def _brief(i: int, a: Article) -> ArticleBrief:
    return ArticleBrief(f"a{i}", a.publisher, a.title, a.summary, a.published_at.date().isoformat())


def _history(claim: str, briefs: list[ArticleBrief], profile: Profile, services: Services,
             today: dt.date) -> Line | None:  # fmt: skip
    """The history line for a confirmed tip the judge maps to an event type, else None."""
    story = StoryForJudge("tip", claim[:TITLE_CHARS], tuple(briefs), today)
    c = services.models.classify_story(story, classify.allowed_causes())
    if not isinstance(c, Classified):
        return None
    assets = services.cfg.triggers.assets_by_type.get(c.type, ())
    return brief.history(c.type.value, profile, assets, services.rates_db)


def hype(claim: str) -> list[str]:
    """The hype phrases in the tip, quoted as the sender wrote them."""
    return list(dict.fromkeys(m.group(0).strip() for m in HYPE.finditer(claim)))


def _answer(verdict: Callable[[str], str], claim: str, line: Line | None = None,
            services: Services | None = None, lang: str = "en") -> Answer:  # fmt: skip
    """The verdict first, the history line if there is one, then the hype phrases the tip
    used. Quoted hype holds words the guard rejects in any model draft, so a tip with hype goes
    out as code wrote it, in the reader's language."""
    signals = hype(claim)
    quoted = ", ".join(f'"{h}"' for h in signals)

    def write(lang: str) -> str:
        parts = [verdict(lang)]
        if line is not None:
            parts.append(say(HISTORY_SAYS, lang).format(line=line.words(lang)))
        if signals:
            parts.append(say(HYPE_NOTE, lang).format(quoted=quoted))
        return "\n\n".join(parts)

    words = {lang: write(lang) for lang in LANGS}
    link = None
    if line is not None and services is not None and services.public_url:
        url = f"{services.public_url}/why/{line.type}/{line.asset}"
        link = Link(say(EVERY_CASE, lang), url)
    return Answer(words["en"], words["en"], None if signals else TIP_TASK, kind="tip",
                  words=words, link=link)  # fmt: skip


def check_tip(claim: str, profile: Profile, services: Services, now: dt.datetime,
              lang: str = "en") -> Answer:  # fmt: skip
    if services.search is None or services.models is None or services.cfg is None:
        return Answer.fixed(CANT_SEARCH)
    days = services.cfg.product.tip_lookback_days
    try:
        found = _articles(claim, services, now)
        briefs = [_brief(i, a) for i, a in enumerate(found)]
        same = services.models.same_claim(claim, briefs) if briefs else set()
    except net.CallFailed:
        return Answer.fixed(CANT_SEARCH)
    matching = [a for a, b in zip(found, briefs, strict=True) if b.id in same]
    if not matching:
        return _answer(lambda lang: say(NOT_FOUND, lang).format(days=days), claim)
    verdict = group.confirm(matching, services.cfg.confirm)
    who = ", ".join(verdict.publishers)
    if not isinstance(verdict, Confirmed):
        rule = services.cfg.confirm
        return _answer(lambda lang: say(TOO_FEW, lang).format(
            who=who, days=days, k=rule.min_publishers, h=rule.window_hours), claim)  # fmt: skip
    try:
        line = _history(claim, [b for b in briefs if b.id in same], profile, services,
                        now.date())  # fmt: skip
    except net.CallFailed:
        line = None

    def told(lang: str) -> str:
        official = (say(OFFICIAL, lang).format(source=verdict.primary_source)
                    if verdict.primary_source else "")  # fmt: skip
        return say(CONFIRMED, lang).format(who=who, official=official)

    return _answer(told, claim, line, services, lang)
