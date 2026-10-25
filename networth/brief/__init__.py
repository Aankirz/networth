"""The investing-day brief: the month's confirmed events, where history leans after them, and
the user's own plan.

    events = month_events(watcher_db, today)
    draft = compose(events, profile, plan, rates_db, today, public_url)
    draft.text()      # the plain template, every number formatted by code from the engine
    draft.source()    # what guard.py checks the writer's version against

Code builds the draft: each scoreboard line is one engine row (odds() from the watcher's
Insight, or compare() for the user's market's sector group) in words from networth.web.names.
The writer only rewords draft.text(); guard.py holds it to the draft's numbers. Nothing here
ranks rows or says what to do: lines keep a fixed order and the plan line is the user's own.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from networth.app.store import Plan, Profile
from networth.bot.onboarding import format_money, plan_line
from networth.bot.telegram import Button, Keyboard
from networth.engine import odds as engine
from networth.engine.backtest import market_of
from networth.watcher.store import Store
from networth.web import names
from networth.web.fmt import percent

MONTH_DAYS: Final = 31
MAX_LINES: Final = 4
MAX_NEWS_EVENTS: Final = 3
MARKS: Final = {names.LeanKind.UP: "🟢", names.LeanKind.DOWN: "🔴", names.LeanKind.NONE: "⚪"}
CALLBACK_PREFIX: Final = "br"
HOME_MARKET: Final = {"INR": "in", "USD": "us"}  # the market whose event leads the scoreboard
NOTHING_NEW: Final = (
    "No confirmed news this month matched an event we have history for. "
    "Nothing needs your attention."
)
PLAN_CLOSE: Final = "History's counts are context. The plan is always your choice."


@dataclass(frozen=True)
class Event:
    """One confirmed event of the month, with the engine rows the watcher wrote for it."""

    type: str
    event_date: dt.date
    title: str
    odds: tuple[engine.OddsJSON, ...]  # the exact odds() dicts from its news-first Insights


@dataclass(frozen=True)
class Line:
    mark: str
    text: str
    type: str
    asset: str


@dataclass(frozen=True)
class Draft:
    header: str
    news: str
    lines: tuple[Line, ...]
    plan: str
    lead: Line | None  # the row the Why? button opens

    def text(self) -> str:
        parts = [self.header, self.news]
        if self.lines:
            board = "\n".join(f"{line.mark} {line.text}" for line in self.lines)
            parts.append(f"Where history leans after months like this:\n{board}")
        parts.append(self.plan)
        return "\n\n".join(parts)

    def source(self) -> str:
        return self.text()


def month_events(watcher_db: Path, today: dt.date) -> list[Event]:
    """Events with a news-first Insight dated in the last MONTH_DAYS, newest first."""
    if not watcher_db.exists():
        return []
    store = Store.open(watcher_db)
    try:
        titles = {s.id: s.title for s in store.stories()}
        insights = [i for i in store.insights() if i.trigger == "news"
                    and (today - i.event_date).days <= MONTH_DAYS]  # fmt: skip
    finally:
        store.close()
    events: dict[tuple[str, dt.date], list] = {}
    for i in insights:
        events.setdefault((i.type, i.event_date), []).append(i)
    out = [Event(t, d, titles.get(rows[0].story_id, t), tuple(r.odds for r in rows))
           for (t, d), rows in events.items()]  # fmt: skip
    return sorted(out, key=lambda e: e.event_date, reverse=True)


def _in_markets(asset: str, markets: Sequence[str]) -> bool:
    return market_of(asset).value in markets


def odds_line(
    type: str, row: engine.CompareAssetJSON | engine.OddsJSON, n: int, weak: bool
) -> Line:
    """One engine row in words: "Indian banks (Nifty Bank) beat the Nifty 50 in 14 of 22 past
    RBI rate hikes (normal: 56%)." The mark repeats the lean, so colour is never the only cue."""
    claim = "rose" if row["measure"] == "raw" else f"beat {names.benchmark_name(row['benchmark'])}"
    lean = names.lean(row["hit_rate"], row["baseline"], weak)
    text = (f"{names.asset_name(row['asset'])} {claim} in {row['n_hits']} of {n} "
            f"{names.TYPES[type].plural} (normal: {percent(row['baseline'])})."
            f"{' Weak signal.' if weak else ''}")  # fmt: skip
    return Line(MARKS[lean.kind], text, type, row["asset"])


def history(type: str, profile: Profile, assets: Sequence[str], rates_db: Path) -> Line | None:
    """The odds() line for the first asset with history in the user's markets, home market
    first, or None."""
    home = HOME_MARKET.get(profile.currency or "INR", "in")
    mine = sorted((a for a in assets if _in_markets(a, profile.markets)),
                  key=lambda a: not _in_markets(a, [home]))  # fmt: skip
    for asset in mine:
        try:
            row = engine.odds(type, asset, db=rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        return odds_line(type, row, row["n_episodes"], row["weak_signal"])
    return None


def scoreboard(event: Event, markets: Sequence[str], rates_db: Path) -> list[Line]:
    """The event's own Insight rows in the user's markets, then the first sector group of each
    of those markets, in names.SCOREBOARD_GROUPS order, up to MAX_LINES. No ranking."""
    lines = [odds_line(o["type"], o, o["n_episodes"], o["weak_signal"])
             for o in event.odds if _in_markets(o["asset"], markets)]  # fmt: skip
    for market in (m for m in names.SCOREBOARD_GROUPS if m in markets):
        group = names.SCOREBOARD_GROUPS[market][0]
        try:
            c = engine.compare(event.type, group, db=rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        shown = {line.asset for line in lines}
        lines += [odds_line(c["type"], a, c["n_episodes"], c["weak_signal"])
                  for a in c["assets"] if a["asset"] not in shown]  # fmt: skip
    return lines[:MAX_LINES]


def _news_line(events: Sequence[Event]) -> str:
    if not events:
        return NOTHING_NEW
    named = [f"{names.TYPES[e.type].title} on {e.event_date:%b} {e.event_date.day}"
             for e in events[:MAX_NEWS_EVENTS]]  # fmt: skip
    return f"This month's news, in one line. {'; '.join(named)}."


def compose(
    events: Sequence[Event],
    profile: Profile,
    plan: Plan | None,
    rates_db: Path,
    today: dt.date,
) -> Draft:
    markets = profile.markets
    home = HOME_MARKET.get(profile.currency or "INR", "in")
    mine = [e for e in events if any(_in_markets(o["asset"], markets) for o in e.odds)]
    lead = sorted(mine, key=lambda e: not any(_in_markets(o["asset"], [home]) for o in e.odds))
    amount = format_money(profile.monthly_amount or 0, profile.currency or "INR")
    header = f"Investing day, {today:%b} {today.day}. {amount} ready."
    lines = tuple(scoreboard(lead[0], markets, rates_db)) if lead else ()
    yours = f"Your plan. You chose {plan_line(plan)}." if plan else "You haven't picked a plan."
    return Draft(
        header, _news_line(mine), lines, f"{yours} {PLAN_CLOSE}", lines[0] if lines else None
    )


def buttons(draft: Draft, public_url: str | None, page_url: str | None = None) -> Keyboard:
    """Invest as planned, Change my plan and My range call back; the scoreboard, Why? and the
    user's own page open pages."""
    first = (Button("Invest as planned", f"{CALLBACK_PREFIX}:ok"),
             Button("Change my plan", f"{CALLBACK_PREFIX}:plan"))  # fmt: skip
    rows: list[tuple[Button, ...]] = [first]
    if draft.lead is not None and public_url:
        lead = draft.lead
        rows.append((Button("Show the scoreboard", "", f"{public_url}/scoreboard/{lead.type}"),
                     Button("Why?", "", f"{public_url}/why/{lead.type}/{lead.asset}")))  # fmt: skip
    mine = (Button("My page", "", page_url),) if page_url else ()
    rows.append((*mine, Button("My range", f"{CALLBACK_PREFIX}:range")))
    return tuple(rows)
