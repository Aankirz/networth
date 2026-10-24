"""Rare alerts: a confirmed event whose history is long and clearly uneven, sent at most
alert_max_per_month times a month to users who left alerts on.

    sent = run_alerts(store, bot, services, insights, now)

An Insight qualifies when its odds() row has at least alert_min_episodes episodes, is not a
weak signal, and its hit rate sits at least alert_min_gap from the normal rate. Each user gets
at most one alert per event, in their own markets, claimed before it is sent so a rerun never
sends it twice. Paused, stopped and pull-only (alerts off) users get nothing.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Final

from networth import brief
from networth.app.services import Services
from networth.app.store import Profile, Status, Step, Store
from networth.bot.outbox import send
from networth.bot.telegram import Bot
from networth.chat.answer import Answer, deliver
from networth.config import ProductConfig
from networth.engine.backtest import market_of
from networth.watcher.store import Insight
from networth.web import names

log = logging.getLogger("networth.bot")

ALERT_TASK: Final = "Tell a beginner, in a short chat message, about this rare market alert."


def qualifies(i: Insight, rules: ProductConfig) -> bool:
    o = i.odds
    gap = abs(float(o["hit_rate"]) - float(o["baseline"]))
    return (i.trigger == "news" and int(o["n_episodes"]) >= rules.alert_min_episodes
            and not o["weak_signal"] and gap >= rules.alert_min_gap)  # fmt: skip


def event_key(i: Insight) -> str:
    return f"{i.type}:{i.event_date}"


def alert_text(i: Insight) -> str:
    o = i.odds
    line = brief.odds_line(i.type, o, int(o["n_episodes"]), False)
    return (f"A rare one. {names.TYPES[i.type].title}, {i.event_date:%b} {i.event_date.day}, "
            f"confirmed.\n\n{line.mark} {line.text}\n\nHistory's counts are context, not a "
            "forecast. Your plan doesn't change unless you change it.")  # fmt: skip


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
            text = alert_text(i)
            if not store.claim_alert(p.user_id, event_key(i), now_month,
                                     rules.alert_max_per_month, text):  # fmt: skip
                continue
            try:
                reply = deliver(Answer(text, text, ALERT_TASK, kind="alert"), p.lang or "en",
                                services)  # fmt: skip
                sent += send(store, bot, p, reply, proactive=True)
            except Exception:
                log.exception("alert %s for %s failed", event_key(i), p.user_id)
    return sent
