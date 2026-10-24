"""Shared fixtures. No test touches the network or data/.

Price fixtures are seeded random walks on hand-written session calendars, so holidays are
known exactly. They are wrapped as backtest.Panel through the real constructor, or written in
fetch.py's on-disk format for end-to-end builds.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from networth.engine import backtest
from networth.engine.model import EraName, Event, EventType, KnownTime, Market, Region, UnknownTime

US_HOLIDAYS_2019 = {dt.date(2019, 4, 19)}  # Good Friday
IN_HOLIDAYS_2019 = {dt.date(2019, 3, 4), dt.date(2019, 3, 21)}  # Mahashivratri, Holi
HOLIDAYS = {Market.US: US_HOLIDAYS_2019, Market.IN: IN_HOLIDAYS_2019}


def sessions(
    start: dt.date, end: dt.date, holidays: set[dt.date] = frozenset()
) -> pd.DatetimeIndex:
    days = pd.bdate_range(start, end)
    return days[~days.isin(pd.to_datetime(sorted(holidays)))]


def random_walk(index: pd.DatetimeIndex, seed: int, name: str = "") -> pd.Series:
    steps = np.random.default_rng(seed).normal(0.0, 0.01, len(index))
    return pd.Series(100.0 * np.exp(np.cumsum(steps)), index=index, name=name)


def make_panel(
    market: Market, *, start: dt.date = dt.date(2019, 3, 1), end: dt.date = dt.date(2019, 4, 30)
) -> backtest.Panel:
    """Fake asset 'A' against benchmark 'B' on the 2019 calendar of `market`."""
    days = sessions(start, end, HOLIDAYS[market])
    era = EraName.SINCE_1998 if market is Market.US else EraName.SINCE_2007
    return backtest.make_panel(
        "A", era, market, random_walk(days, 1, "A"), random_walk(days, 2, "B"), "B", "excess"
    )


def event(
    id: str,
    day: dt.date,
    time_known: str | None,
    tz: str = "America/New_York",
    type: EventType = EventType.FED_HIKE,
    cause: str = "inflation",
    region: Region = Region.US,
) -> Event:
    when = (
        KnownTime(dt.datetime.combine(day, dt.time.fromisoformat(time_known), ZoneInfo(tz)))
        if time_known
        else UnknownTime(day)
    )
    return Event(id, day, when, tz, region, type, cause, f"headline {id}", (f"https://x/{id}",))


def write_prices(dirpath: Path, series: dict[str, pd.Series]) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    for name, s in series.items():
        out = pd.DataFrame({"date": s.index.strftime("%Y-%m-%d"), "close": s.to_numpy()})
        out.to_csv(dirpath / f"{name.replace(':', '__')}.csv", index=False)
    return dirpath


EVENT_COLUMNS = list(backtest.CSV_COLUMNS)


def write_events(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EVENT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in EVENT_COLUMNS})
    return path


def row(id: str, date: str, type: str, region: str, *, time: str = "", tz: str = "") -> dict:
    tz = tz or ("Asia/Kolkata" if region == "in" else "America/New_York")
    return {
        "id": id, "date": date, "time_known": time, "tz": tz, "region": region, "type": type,
        "cause": "cause_a" if id.endswith("a") else "cause_b", "headline": f"headline {id}",
        "source_url": f"https://example.org/{id}",
    }  # fmt: skip


BOOK_EVENTS = [
    row("oil_1999a", "1999-03-23", "oil_supply", "global"),
    row("oil_2008b", "2008-07-11", "oil_supply", "global"),
    row("oil_2016a", "2016-11-30", "oil_supply", "global"),
    row("oil_2018b", "2018-05-08", "oil_supply", "global", time="14:00"),
    row("oil_2019a", "2019-09-16", "oil_supply", "global"),
    row("oil_2020b", "2020-03-09", "oil_supply", "global"),
    row("oil_2023a", "2023-04-03", "oil_supply", "global"),
    row("rbi_2010a", "2010-03-19", "rbi_hike", "in"),
    row("rbi_2011b", "2011-05-03", "rbi_hike", "in", time="12:00"),
    row("rbi_2014a", "2014-01-28", "rbi_hike", "in"),
    row("rbi_2018b", "2018-06-06", "rbi_hike", "in"),
    row("rbi_2023a", "2023-02-08", "rbi_hike", "in"),
    row("rbi_2000a", "2000-07-21", "rbi_hike", "in"),
]


def book_series() -> dict[str, pd.Series]:
    us = sessions(dt.date(1990, 1, 1), dt.date(2023, 6, 30))
    spy, ff = us[us >= "1997-01-01"], us
    jets = us[us >= "2015-04-30"]
    bse = us[us >= "1997-07-01"]
    nse = us[us >= "2007-09-17"]
    return {
        "SPY": random_walk(spy, 11), "JETS": random_walk(jets, 12),
        "FF:Mkt": random_walk(ff, 13), "FF49:Trans": random_walk(ff, 14),
        "^BSESN": random_walk(bse, 15), "^NSEI": random_walk(nse, 16),
        "^NSEBANK": random_walk(nse, 17),
    }  # fmt: skip


@pytest.fixture
def tiny_book(tmp_path: Path) -> tuple[Path, Path]:
    """(events.csv, prices dir): enough to see 'both eras where the data exists' end to end."""
    events = write_events(tmp_path / "events.csv", BOOK_EVENTS)
    return events, write_prices(tmp_path / "prices", book_series())


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--leak-impl",
        default="real",
        help="run test_leak against a deliberately broken react() from tests/canaries.py, "
        "to show the leak test failing: e.g. --leak-impl=previous_close_entry",
    )


@pytest.fixture
def react_impl(request: pytest.FixtureRequest):
    from tests import canaries

    name = request.config.getoption("--leak-impl")
    return backtest.react if name == "real" else canaries.CANARIES[name]
