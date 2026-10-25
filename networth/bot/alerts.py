"""Rare alerts: a confirmed event whose history is long and clearly uneven, sent at most
alert_max_per_month times a month to users who left alerts on.

    sent = run_alerts(store, bot, services, insights, now)

An Insight qualifies when its odds() row has at least alert_min_episodes episodes, is not a
weak signal, and its hit rate sits at least alert_min_gap from the normal rate. Each user gets
at most one alert per event, in their own markets, claimed before it is sent so a rerun never
sends it twice; a failed send releases its claim so the next run retries it. Paused, stopped
and pull-only (alerts off) users get nothing. The words are code-written in the user's language,
with no model: one title, the history line, a calm reminder that the plan is theirs, the footer.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Final

from networth import brief, guard
from networth.app.services import Services
from networth.app.store import Profile, Status, Step, Store
from networth.bot.message import Message, plain, say
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Bot
from networth.brief.lines import day_words, type_words
from networth.config import ProductConfig
from networth.engine.backtest import market_of
from networth.watcher.store import Insight

log = logging.getLogger("networth.bot")

TITLE: Final = {
    "en": "A rare one: {title} on {day}, confirmed.",
    "hi": "कभी-कभार आने वाला अलर्ट: {day} को {title} की पुष्टि हुई।",
    "hinglish": "Kabhi-kabhaar aane wala alert: {day} ko {title} confirm hua.",
}
SHOCKS: Final = {
    "en": "Shocks like this have happened before.",
    "hi": "ऐसे झटके पहले भी आए हैं।",
    "hinglish": "Aise jhatke pehle bhi aaye hain.",
}
YOURS: Final = {
    "en": "History's counts are context, not a forecast. Your plan doesn't change unless you "
    "change it.",
    "hi": "इतिहास की गिनती सिर्फ़ संदर्भ है, कोई अनुमान नहीं। आपका प्लान तभी बदलता है जब आप उसे बदलते हैं।",
    "hinglish": "History ki ginti sirf context hai, forecast nahin. Aapka plan tabhi badalta hai "
    "jab aap use badalte hain.",
}


def qualifies(i: Insight, rules: ProductConfig) -> bool:
    o = i.odds
    gap = abs(float(o["hit_rate"]) - float(o["baseline"]))
    return (i.trigger == "news" and int(o["n_episodes"]) >= rules.alert_min_episodes
            and not o["weak_signal"] and gap >= rules.alert_min_gap)  # fmt: skip


def event_key(i: Insight) -> str:
    return f"{i.type}:{i.event_date}"


def alert_message(i: Insight, lang: str | None) -> Message:
    o = i.odds
    line = brief.odds_line(i.type, o, int(o["n_episodes"]), False)
    title = say(TITLE, lang).format(title=type_words(i.type, lang).title,
                                    day=day_words(i.event_date, lang))  # fmt: skip
    body = (line.words(lang), *([say(SHOCKS, lang)] if i.type in brief.STRESS_TYPES else []),
            say(YOURS, lang))  # fmt: skip
    return Message(title, body)


def wants_alerts(p: Profile) -> bool:
    return p.step is Step.DONE and p.status is Status.ACTIVE and p.alerts_on


def for_user(p: Profile, rare: Sequence[Insight]) -> list[Insight]:
    """The first qualifying insight per event in the user's markets."""
    picked: dict[str, Insight] = {}
    for i in rare:
        if market_of(i.asset).value in p.markets:
            picked.setdefault(event_key(i), i)
    return list(picked.values())


def run_alerts(
    store: Store, bot: Bot, services: Services, insights: Iterable[Insight], now_month: str
) -> int:
    """now_month is "YYYY-MM", the month the cap counts in."""
    if services.cfg is None:
        return 0
    rules = services.cfg.product
    rare = [i for i in insights if qualifies(i, rules)]
    sent = 0
    for p in (p for p in store.profiles() if rare and wants_alerts(p)):
        for i in for_user(p, rare):
            m = alert_message(i, p.lang)
            text = plain(m)
            if not store.claim_alert(p.user_id, event_key(i), now_month,
                                     rules.alert_max_per_month, text):  # fmt: skip
                continue
            try:
                guard.log_verdict(services.guard_log, "alert", "template",
                                  guard.check(text, text))  # fmt: skip
                sent += send(store, bot, p, Reply(m), proactive=True, mail=services.mail)
            except Exception:
                store.release_alert(p.user_id, event_key(i))
                log.exception("alert %s for %s failed", event_key(i), p.user_id)
    return sent
