"""The leak test (Done-when 6).

Contract under test, for every Reaction:
  1. entry_date is the event's first usable session: the first session whose close is
     strictly after the event became known (16:00 New York, 15:30 Kolkata); with an unknown
     time, the first session dated after the event's local date, in every market. The
     expected dates below are written by hand from the rule, not computed by the engine.
  2. the return reads exactly two closes per series, close(entry) and close(entry +
     horizon). Poisoning every other close must change nothing.

Show it failing on a broken version:
    uv run pytest tests/test_leak.py --leak-impl=previous_close_entry
test_check_catches_every_canary keeps that proof in `make check` permanently.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from networth.engine import backtest
from networth.engine.backtest import Panel
from networth.engine.model import EraName, Market
from tests.canaries import CANARIES
from tests.conftest import event, make_panel, random_walk, row, sessions, write_events, write_prices

HORIZON = 5
NY, KOL = "America/New_York", "Asia/Kolkata"
D = dt.date

# (case, event date, time_known, event tz, asset market, expected first usable session)
CASES = [
    ("us_intraday", D(2019, 3, 13), "10:00", NY, Market.US, D(2019, 3, 13)),
    ("us_minute_before_close", D(2019, 3, 13), "15:59", NY, Market.US, D(2019, 3, 13)),
    ("us_at_close", D(2019, 3, 13), "16:00", NY, Market.US, D(2019, 3, 14)),
    ("us_unknown_time", D(2019, 3, 13), None, NY, Market.US, D(2019, 3, 14)),
    ("us_friday_evening", D(2019, 3, 15), "17:00", NY, Market.US, D(2019, 3, 18)),
    ("us_saturday", D(2019, 3, 16), "11:00", NY, Market.US, D(2019, 3, 18)),
    ("us_holiday_next", D(2019, 4, 18), "18:00", NY, Market.US, D(2019, 4, 22)),
    ("ist_morning_for_us", D(2019, 3, 13), "09:00", KOL, Market.US, D(2019, 3, 13)),
    ("ist_unknown_for_us", D(2019, 3, 13), None, KOL, Market.US, D(2019, 3, 14)),
    ("baghdad_for_us", D(2019, 3, 13), "05:34", "Asia/Baghdad", Market.US, D(2019, 3, 13)),
    ("in_minute_before_close", D(2019, 3, 13), "15:29", KOL, Market.IN, D(2019, 3, 13)),
    ("in_at_close", D(2019, 3, 13), "15:30", KOL, Market.IN, D(2019, 3, 14)),
    ("in_unknown_time", D(2019, 3, 13), None, KOL, Market.IN, D(2019, 3, 14)),
    ("in_holiday_next", D(2019, 3, 20), "16:00", KOL, Market.IN, D(2019, 3, 22)),
    ("fomc_for_india", D(2019, 3, 20), "14:00", NY, Market.IN, D(2019, 3, 22)),
    ("ny_predawn_for_india", D(2019, 3, 13), "04:00", NY, Market.IN, D(2019, 3, 13)),
    ("ny_0530_est_for_india", D(2019, 3, 8), "05:30", NY, Market.IN, D(2019, 3, 11)),
    ("ny_0530_edt_for_india", D(2019, 3, 11), "05:30", NY, Market.IN, D(2019, 3, 11)),
    ("ny_unknown_for_india", D(2019, 3, 13), None, NY, Market.IN, D(2019, 3, 14)),
]

# Events the panel cannot score honestly: must give None, never the first available close.
UNSCOREABLE = [
    ("before_data_start", D(2019, 2, 20), "10:00", NY, Market.US),
    ("exit_past_data_end", D(2019, 4, 29), "10:00", NY, Market.US),
]


class LeakDetected(AssertionError):
    pass


def poison_outside(panel: Panel, keep: set[int], seed: int = 7) -> Panel:
    """Same panel with every close not in `keep` multiplied by a random factor in [0.5, 2]."""
    rng = np.random.default_rng(seed)
    mask = np.ones(len(panel.sessions), dtype=bool)
    mask[list(keep)] = False

    def poisoned(closes: np.ndarray) -> np.ndarray:
        return np.where(mask, closes * rng.uniform(0.5, 2.0, len(closes)), closes)

    return dataclasses.replace(
        panel, series_close=poisoned(panel.series_close), bench_close=poisoned(panel.bench_close)
    )


def check_no_leak(react_fn, cases=CASES) -> None:
    """Raise LeakDetected naming the first case that breaks the contract."""
    panels = {m: make_panel(m) for m in Market}
    for name, day, hhmm, tz, market, expected in cases:
        panel = panels[market]
        ev = event(name, day, hhmm, tz)
        got = react_fn(ev, panel, HORIZON)
        if got is None or got.entry_date != expected:
            raise LeakDetected(f"{name}: entry {got and got.entry_date}, expected {expected}")
        i = panel.sessions.get_loc(pd.Timestamp(expected))
        if got.exit_date != panel.sessions[i + HORIZON].date():
            raise LeakDetected(f"{name}: exit {got.exit_date} is not entry + {HORIZON} sessions")
        again = react_fn(ev, poison_outside(panel, {i, i + HORIZON}), HORIZON)
        if not np.allclose(
            [again.raw_return, again.bench_return], [got.raw_return, got.bench_return],
            rtol=0, atol=1e-12,
        ):  # fmt: skip
            raise LeakDetected(f"{name}: return reads a close other than entry and exit")


def test_reactions_do_not_leak(react_impl) -> None:
    check_no_leak(react_impl)


@pytest.mark.parametrize("case", UNSCOREABLE, ids=lambda c: c[0])
def test_unscoreable_events_give_no_reaction(react_impl, case) -> None:
    name, day, hhmm, tz, market = case
    assert react_impl(event(name, day, hhmm, tz), make_panel(market), HORIZON) is None


@pytest.mark.parametrize("canary", sorted(CANARIES))
def test_check_catches_every_canary(canary: str) -> None:
    """If a broken react() ever passes the check, the check is what's broken."""
    with pytest.raises(LeakDetected):
        check_no_leak(CANARIES[canary])


# ---- through the real build, with every close outside the window poisoned x1000 ------------

BUILD_ENTRY, BUILD_EXIT = D(2019, 3, 14), D(2019, 4, 12)  # fed_hike: 21 sessions, by hand
POISON = 1000.0


def _build_world(root: Path, poison: bool):
    root.mkdir(parents=True)
    days = sessions(D(2019, 3, 1), D(2019, 6, 28), {D(2019, 4, 19)})
    clean = {"SPY": random_walk(days, 21, "SPY"), "XLE": random_walk(days, 22, "XLE")}
    keep = days.isin(pd.to_datetime([BUILD_ENTRY, BUILD_EXIT]))
    prices = {n: s.where(keep, s * POISON) for n, s in clean.items()} if poison else clean
    events = write_events(
        root / "events.csv", [row("hike", "2019-03-13", "fed_hike", "us", time="16:00")]
    )
    return clean, events, write_prices(root / "prices", prices)


def test_build_reads_only_the_window_closes(react_impl, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backtest, "react", react_impl)
    clean, events, prices = _build_world(tmp_path / "poisoned", poison=True)
    _, clean_events, clean_prices = _build_world(tmp_path / "clean", poison=False)
    poisoned_build = backtest.build(events, prices)
    clean_build = backtest.build(clean_events, clean_prices)

    got = {r.asset: r for r in poisoned_build.reactions if r.era is EraName.SINCE_1998}
    for asset in ("XLE", "SPY"):
        r = got[asset]
        assert (r.entry_date, r.exit_date) == (BUILD_ENTRY, BUILD_EXIT), asset
        s, b = clean[asset], clean["SPY"]
        entry, exit_ = pd.Timestamp(BUILD_ENTRY), pd.Timestamp(BUILD_EXIT)
        assert r.raw_return == pytest.approx(s[exit_] / s[entry] - 1, abs=1e-12), asset
        assert r.bench_return == pytest.approx(b[exit_] / b[entry] - 1, abs=1e-12), asset

    def scored(build):
        return {
            (r.asset, r.era): (r.n_hits, r.median, r.p10, r.p90, r.raw_median, r.raw_p10)
            for r in build.base_rates
        }

    poisoned_rows, clean_rows = scored(poisoned_build), scored(clean_build)
    assert poisoned_rows.keys() == clean_rows.keys()
    for key, values in clean_rows.items():
        assert np.allclose(poisoned_rows[key], values, rtol=0, atol=1e-12), key
