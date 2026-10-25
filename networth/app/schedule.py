"""Scheduled work, woken by Maritime because timers in a sleeping VM never fire.

    GET  /schedules   the jobs below, which Maritime polls and registers as wake triggers
    POST /chat        Maritime delivers a job's prompt here with source "scheduled"

Each job runs in a background thread so /chat answers inside Maritime's 30 s limit. /chat is
public and Maritime sends no secret with a scheduled prompt ("treat the URL itself as the
secret"), so anyone who learns the URL can forge one. What a forger can make us spend is
bounded, not zero: the watcher runs only inside its own cron window (MARKET_HOURS on weekdays)
and never within WATCHER_MIN_GAP of the last cycle, so forged calls add at most about one paid
cycle an hour on top of the two scheduled ones, during market hours only. The brief is claimed
once per user per day, alerts once per user per event, and one job at a time runs.

https://maritime.sh/docs/triggers
"""

from __future__ import annotations

import datetime as dt
import functools
import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Final
from zoneinfo import ZoneInfo

from networth.app.services import Services
from networth.app.store import Store
from networth.bot import alerts, briefs
from networth.bot.telegram import Bot
from networth.llm import OpenAIModels
from networth.watcher import prices, run
from networth.watcher.pull import ExaSearch
from networth.watcher.store import Insight
from networth.watcher.store import Store as WatcherStore

log = logging.getLogger("networth.app")

TZ: Final = "Asia/Kolkata"
WATCHER_PROMPT: Final = "RUN_WATCHER"
BRIEF_PROMPT: Final = "RUN_BRIEF"
WATCHER_MIN_GAP: Final = dt.timedelta(minutes=25)
MARKET_HOURS: Final = range(9, 16)  # the watcher cron's hour field, 9-15
CHAT_REPLY: Final = "Networth talks on Telegram: https://t.me/networth_professor_bot"


@dataclass(frozen=True)
class Schedule:
    id: str
    cron: str
    prompt: str
    tz: str = TZ
    enabled: bool = True


SCHEDULES: Final = (
    Schedule("watcher", "*/30 9-15 * * 1-5", WATCHER_PROMPT),  # every 30 min, NSE hours
    Schedule("brief", "0 8 * * *", BRIEF_PROMPT),  # 08:00 IST; each user's own day decides
)


def schedules() -> list[dict]:
    return [asdict(s) for s in SCHEDULES]


Cycle = Callable[[Services, dt.datetime], Sequence[Insight]]


def watcher_cycle(services: Services, now: dt.datetime) -> Sequence[Insight]:
    """One real watcher cycle; returns every insight decided in the last event_max_age_days,
    not only this cycle's. A VM that stopped between a cycle and its alerts then sends them on
    the next run, and the per-user, per-event alert claim keeps that from sending twice."""
    cfg = services.cfg
    if cfg is None:
        raise RuntimeError("watcher needs OPENAI_API_KEY and EXA_API_KEY")
    paths = run.Paths(services.data_dir)
    run.run_cycle(cfg, paths, ExaSearch(cfg, paths.call_log), OpenAIModels(cfg, paths.call_log),
                  now, functools.partial(prices.recent_closes,
                                         deadline_s=cfg.http.prices_deadline_s))  # fmt: skip
    store = WatcherStore.open(paths.watcher_db)
    try:
        return store.insights(since=now - dt.timedelta(days=cfg.event_max_age_days))
    finally:
        store.close()


def last_cycle_end(services: Services) -> dt.datetime | None:
    if not services.watcher_db.exists():
        return None
    store = WatcherStore.open(services.watcher_db)
    try:
        cycle = store.latest_cycle()
    finally:
        store.close()
    return cycle.finished_at if cycle else None


def in_watcher_window(now: dt.datetime) -> bool:
    local = now.astimezone(ZoneInfo(TZ))
    return local.weekday() < 5 and local.hour in MARKET_HOURS


def run_watcher(store: Store, bot: Bot, services: Services, now: dt.datetime,
                cycle: Cycle = watcher_cycle) -> str:  # fmt: skip
    if not in_watcher_window(now):
        return "watcher skipped: outside market hours"
    last = last_cycle_end(services)
    if last is not None and now - last < WATCHER_MIN_GAP:
        return f"watcher skipped: last cycle ended {last.isoformat(timespec='seconds')}"
    fresh = cycle(services, now)
    sent = alerts.run_alerts(store, bot, services, fresh, now.strftime("%Y-%m"))
    return f"watcher ran: {len(fresh)} insights, {sent} alerts sent"


def run_brief(store: Store, bot: Bot, services: Services, now: dt.datetime) -> str:
    return f"brief ran: {briefs.run_daily(store, bot, services, now)} sent"


JOB_LOCK: Final = threading.Lock()


def run_job(prompt: str, store: Store, bot: Bot, services: Services, now: dt.datetime,
            cycle: Cycle = watcher_cycle) -> str | None:  # fmt: skip
    """Runs the job a prompt names, one at a time. None when the prompt names no job or one
    is already running."""
    if prompt not in (WATCHER_PROMPT, BRIEF_PROMPT) or not JOB_LOCK.acquire(blocking=False):
        return None
    try:
        if prompt == WATCHER_PROMPT:
            return run_watcher(store, bot, services, now, cycle)
        return run_brief(store, bot, services, now)
    except Exception:
        log.exception("scheduled %s failed", prompt)
        return f"{prompt} failed"
    finally:
        JOB_LOCK.release()


def start_job(prompt: str, store: Store, bot: Bot, services: Services) -> threading.Thread:
    def work() -> None:
        outcome = run_job(prompt, store, bot, services, dt.datetime.now(dt.UTC))
        log.info("scheduled %s: %s", prompt, outcome)

    thread = threading.Thread(target=work, name=f"job-{prompt}", daemon=True)
    thread.start()
    return thread
