"""Deliberately broken versions of backtest.react. Test-only.

Each has react's signature and one realistic bug. test_leak.py proves the leak check catches
every one on every run. `pytest tests/test_leak.py --leak-impl=<name>` swaps one in for the
real function so the leak test can be watched going red.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from collections.abc import Callable
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from networth.engine import backtest
from networth.engine.backtest import Panel
from networth.engine.model import Event, KnownTime, Reaction, UnknownTime

ReactFn = Callable[[Event, Panel, int], Reaction | None]
_react = backtest.react  # bound at import, so a canary patched over backtest.react cannot recurse


def _window(event: Event, panel: Panel, i: int | None, horizon: int) -> Reaction | None:
    if i is None or i < 1 or i + horizon >= len(panel.sessions):
        return None
    return backtest.reaction_between(event, panel, i, i + horizon)


def _first_close_after(panel: Panel, at: dt.datetime, side: str = "right") -> int:
    return int(np.searchsorted(panel.close_utc, pd.Timestamp(at).tz_convert("UTC").value, side))


def previous_close_entry(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """The classic event-study anchor: enters at the close before the first usable session."""
    i = backtest.entry_index(event, panel)
    return _window(event, panel, None if i is None else i - 1, horizon)


def date_only(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """Ignores the clock: every event counts from the first session on or after its date."""
    i = int(panel.sessions.searchsorted(pd.Timestamp(event.date), side="left"))
    return _window(event, panel, i, horizon)


def market_clock(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """Reads time_known in the asset's market zone instead of the event's own tz."""
    if isinstance(event.time, UnknownTime):
        return _react(event, panel, horizon)
    zone = backtest.MARKET_CLOSE[panel.market][1]
    wall = event.time.at.astimezone(ZoneInfo(event.tz)).replace(tzinfo=zone)
    return _window(event, panel, _first_close_after(panel, wall), horizon)


def unknown_is_midnight(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """Treats an unknown time as 00:00 local instead of after the close."""
    if isinstance(event.time, KnownTime):
        return _react(event, panel, horizon)
    midnight = dt.datetime.combine(event.date, dt.time(0, 0), ZoneInfo(event.tz))
    moved = dataclasses.replace(event, time=KnownTime(midnight))
    return _react(moved, panel, horizon)


def inclusive_close(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """`>=` instead of `>`: an event released exactly at the close counts that close."""
    if isinstance(event.time, UnknownTime):
        return _react(event, panel, horizon)
    return _window(event, panel, _first_close_after(panel, event.time.at, "left"), horizon)


def peek_past_exit(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """Right dates on the label, but the exit close is read one session late."""
    right = _react(event, panel, horizon)
    late = _react(event, panel, horizon + 1)
    if right is None or late is None:
        return right
    return dataclasses.replace(right, raw_return=late.raw_return, bench_return=late.bench_return)


CANARIES: dict[str, ReactFn] = {
    f.__name__: f
    for f in (
        previous_close_entry,
        date_only,
        market_clock,
        unknown_is_midnight,
        inclusive_close,
        peek_past_exit,
    )
}
