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
from typing import Final

from networth import brief, net
from networth.app.services import Services
from networth.app.store import Profile
from networth.chat.answer import Answer
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
CANT_SEARCH: Final = "I can't search the news right now, so I can't check this. Try again later."


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
             today: dt.date) -> tuple[str, str]:  # fmt: skip
    """(line, link) for a confirmed tip the judge maps to an event type, else ("", "")."""
    story = StoryForJudge("tip", claim[:TITLE_CHARS], tuple(briefs), today)
    c = services.models.classify_story(story, classify.allowed_causes())
    if not isinstance(c, Classified):
        return "", ""
    assets = services.cfg.triggers.assets_by_type.get(c.type, ())
    line = brief.history(c.type.value, profile, assets, services.rates_db)
    if line is None:
        return "", ""
    url = f"{services.public_url}/why/{line.type}/{line.asset}" if services.public_url else ""
    return f"\n\nWhat history says. {line.mark} {line.text}", f"\n{url}" if url else ""
    return "", ""


def hype(claim: str) -> list[str]:
    """The hype phrases in the tip, quoted as the sender wrote them."""
    return list(dict.fromkeys(m.group(0).strip() for m in HYPE.finditer(claim)))


def _answer(verdict_line: str, claim: str) -> Answer:
    """The verdict first, then the hype phrases the tip used. Quoted hype holds words the
    guard rejects in any model draft, so a tip with hype goes out as code wrote it."""
    signals = hype(claim)
    quoted = ", ".join(f'"{h}"' for h in signals)
    text = verdict_line + (f"\n\nThe message also uses hype: {quoted}. Real news rarely needs "
                           "it." if signals else "")  # fmt: skip
    return Answer(text, text, None if signals else TIP_TASK, kind="tip")


def check_tip(claim: str, profile: Profile, services: Services, now: dt.datetime) -> Answer:
    if services.search is None or services.models is None or services.cfg is None:
        return Answer(CANT_SEARCH, CANT_SEARCH)
    days = services.cfg.product.tip_lookback_days
    try:
        found = _articles(claim, services, now)
        briefs = [_brief(i, a) for i, a in enumerate(found)]
        same = services.models.same_claim(claim, briefs) if briefs else set()
    except net.CallFailed:
        return Answer(CANT_SEARCH, CANT_SEARCH)
    matching = [a for a, b in zip(found, briefs, strict=True) if b.id in same]
    if not matching:
        return _answer(f"Not confirmed. I searched the news from the last {days} days and no "
                       "publisher is reporting this.", claim)  # fmt: skip
    verdict = group.confirm(matching, services.cfg.confirm)
    who = ", ".join(verdict.publishers)
    if not isinstance(verdict, Confirmed):
        rule = services.cfg.confirm
        return _answer(f"Not confirmed. Only {who} reported this in the last {days} days. We "
                       f"call news confirmed when at least {rule.min_publishers} publishers "
                       f"report it within {rule.window_hours} hours, or an official source "
                       "posts it.", claim)  # fmt: skip
    official = f", and {verdict.primary_source} posted it" if verdict.primary_source else ""
    try:
        history, link = _history(claim, [b for b in briefs if b.id in same], profile, services,
                                 now.date())  # fmt: skip
    except net.CallFailed:
        history, link = "", ""
    return _answer(f"Confirmed. {who} reported it{official}.{history}{link}", claim)
