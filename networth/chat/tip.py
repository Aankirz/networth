"""Check a tip the user was sent against the news, by the same rule the watcher confirms with.

    answer = check_tip(claim, profile, services, now)

Search the last tip_lookback_days, keep only the articles the cheap model says report the same
claim, then group.confirm() them. A confirmed tip that the judge maps to an event type also
gets its history line from engine.odds(). Every sentence in the template is code-written.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Final

from networth import brief, net
from networth.app.services import Services
from networth.app.store import Profile
from networth.chat.answer import Answer
from networth.config import Query
from networth.engine import odds as engine
from networth.engine.backtest import market_of
from networth.engine.model import Region
from networth.llm import ArticleBrief, Classified, StoryForJudge
from networth.watcher import classify, group, pull
from networth.watcher.store import Article, Confirmed

log = logging.getLogger("networth.chat")

CLAIM_CHARS: Final = 300
TITLE_CHARS: Final = 120
TIP_TASK: Final = "Tell a beginner, in a short chat message, what we found about the tip they sent."
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
    assets = [a for a in services.cfg.triggers.assets_by_type.get(c.type, ())
              if market_of(a).value in profile.markets]  # fmt: skip
    for asset in assets:
        try:
            row = engine.odds(c.type.value, asset, db=services.rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        line = brief.odds_line(c.type.value, row, row["n_episodes"], row["weak_signal"])
        url = f"{services.public_url}/why/{c.type.value}/{asset}" if services.public_url else ""
        return f"\n\nWhat history says. {line.mark} {line.text}", f"\n{url}" if url else ""
    return "", ""


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
        text = (
            f"I searched the news from the last {days} days and found no publisher "
            "reporting this. That doesn't prove it's false, but nothing confirms it."
        )
        return Answer(text, text, TIP_TASK, kind="tip")
    verdict = group.confirm(matching, services.cfg.confirm)
    who = ", ".join(verdict.publishers)
    if not isinstance(verdict, Confirmed):
        rule = services.cfg.confirm
        text = (f"Only {who} reported this in the last {days} days. We call news confirmed "
                f"when at least {rule.min_publishers} publishers report it within "
                f"{rule.window_hours} hours, or an official source posts it. So this one is "
                "not confirmed.")  # fmt: skip
        return Answer(text, text, TIP_TASK, kind="tip")
    official = f", and {verdict.primary_source} posted it" if verdict.primary_source else ""
    try:
        history, link = _history(claim, [b for b in briefs if b.id in same], profile, services,
                                 now.date())  # fmt: skip
    except net.CallFailed:
        history, link = "", ""
    text = f"This is reported. {who} reported it{official}.{history}{link}"
    return Answer(text, text, TIP_TASK, kind="tip")
