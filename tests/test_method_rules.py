"""Done-when 7: episodes merge within 21 trading days, the baseline is seeded and
reproducible, weak_signal flips at 8. Plus the era, splice, day-0 and vault rules."""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import pandas as pd
import pytest

from networth.engine import backtest
from networth.engine.model import (
    WEAK_SIGNAL_MIN_EPISODES,
    EraName,
    EventType,
    Market,
    RatesDB,
    Region,
    write_db,
)
from tests.conftest import event, make_panel, sessions, write_prices

D = dt.date
WEEKDAYS_2019 = sessions(D(2019, 1, 1), D(2019, 12, 31))
HOLI = D(2019, 3, 21)
CALENDARS = backtest.EpisodeCalendars(
    us=WEEKDAYS_2019, india=sessions(D(2019, 1, 1), D(2019, 12, 31), {HOLI})
)


def ev(id: str, day: dt.date, type=EventType.FED_HIKE, region=Region.US, cause="inflation"):
    tz = "Asia/Kolkata" if region is Region.IN else "America/New_York"
    return event(id, day, None, tz, type=type, cause=cause, region=region)


def sizes(events) -> list[int]:
    return [len(ep.events) for ep in backtest.merge_episodes(events, CALENDARS)]


# ---- episodes ------------------------------------------------------------------------------


def test_events_21_trading_days_apart_merge() -> None:
    # sessions in (2019-03-01, 2019-04-01] on a weekday calendar: Mar 4..Apr 1 = 21
    assert sizes([ev("a", D(2019, 3, 1)), ev("b", D(2019, 4, 1))]) == [2]


def test_events_22_trading_days_apart_stay_separate() -> None:
    assert sizes([ev("a", D(2019, 3, 1)), ev("b", D(2019, 4, 2))]) == [1, 1]


def test_gaps_count_trading_days_not_weekdays() -> None:
    # 22 weekdays, but Holi closes the Indian market, so 21 Indian sessions: an India pair
    # merges; the same dates as a US pair do not.
    pair = (("a", D(2019, 3, 1)), ("b", D(2019, 4, 2)))
    india = [ev(i, d, EventType.RBI_HIKE, Region.IN) for i, d in pair]
    assert sizes(india) == [2]
    mixed = [india[0], ev("b", D(2019, 4, 2), EventType.RBI_HIKE, Region.US)]
    assert sizes(mixed) == [1, 1]


def test_chains_link_through_the_previous_event() -> None:
    days = [D(2019, 3, 1), D(2019, 3, 22), D(2019, 4, 12)]  # 15 and 15 sessions apart
    assert sizes([ev(f"e{i}", d) for i, d in enumerate(days)]) == [3]


def test_types_never_merge_with_each_other() -> None:
    a = ev("a", D(2019, 3, 1))
    b = ev("b", D(2019, 3, 1), EventType.RBI_HIKE, Region.IN)
    assert sizes([a, b]) == [1, 1]


def test_episode_id_and_cause_come_from_the_onset() -> None:
    a, b = ev("first", D(2019, 3, 1), cause="x"), ev("second", D(2019, 3, 5), cause="y")
    (episode,) = backtest.merge_episodes([b, a], CALENDARS)
    assert (episode.id, episode.cause) == ("fed_hike:first", "x")


def test_episode_ids_survive_dropping_later_events() -> None:
    early = [ev("a", D(2019, 3, 1)), ev("b", D(2019, 6, 3))]
    late = ev("c", D(2019, 10, 1))
    ids = {ep.id for ep in backtest.merge_episodes(early, CALENDARS)}
    assert ids <= {ep.id for ep in backtest.merge_episodes([*early, late], CALENDARS)}


# ---- baseline ------------------------------------------------------------------------------


def test_baseline_is_reproducible() -> None:
    once = backtest.baseline_hit_rate(make_panel(Market.US), 5)
    assert backtest.baseline_hit_rate(make_panel(Market.US), 5) == once


def test_baseline_seed_changes_the_draw() -> None:
    panel = make_panel(Market.US)
    draws = {backtest.baseline_hit_rate(panel, 5, seed=s) for s in range(5)}
    assert len(draws) > 1


def test_baseline_does_not_depend_on_build_order() -> None:
    panel = make_panel(Market.US)
    first = backtest.baseline_hit_rate(panel, 5)
    backtest.baseline_hit_rate(make_panel(Market.IN), 5)
    np.random.seed(123)
    assert backtest.baseline_hit_rate(panel, 5) == first


def test_baseline_scores_windows_of_the_horizon_length() -> None:
    # A raw-measured series that repeats every 5 sessions: a 5-session window always ends
    # where it began (no hit), a 3-session window from the cycle start always rises.
    panel = make_panel(Market.US)
    cycle = np.array([1.0, 2.0, 3.0, 4.0, 0.5])
    closes = np.resize(cycle, len(panel.sessions))
    planted = dataclasses.replace(panel, series_close=closes, measure="raw")
    assert backtest.baseline_hit_rate(planted, 5) == 0.0
    assert backtest.baseline_hit_rate(planted, 3) > 0.0


# ---- weak signal ---------------------------------------------------------------------------


def _scored(n: int):
    panel = make_panel(Market.US, end=D(2019, 12, 31))
    days = [panel.sessions[5 + 3 * k].date() for k in range(n)]
    events = [ev(f"e{k}", d) for k, d in enumerate(days)]
    reactions = [backtest.react(e, panel, 2) for e in events]
    episodes = [backtest.Episode(f"fed_hike:{e.id}", e.type, (e,)) for e in events]
    return panel, list(zip(episodes, reactions, strict=True))


@pytest.mark.parametrize(("n", "weak"), [(7, True), (8, False)])
def test_weak_signal_flips_at_eight(n: int, weak: bool, tmp_path) -> None:
    assert WEAK_SIGNAL_MIN_EPISODES == 8
    panel, scored = _scored(n)
    row = backtest.base_rate_row(EventType.FED_HIKE, None, panel, scored, 0.5)
    assert row.weak_signal is weak
    build = backtest.Build(
        meta=backtest.BuildMeta(None, 1, 1, {}, "", (), dt.datetime.now(dt.UTC)),
        events=tuple(ep.onset for ep, _ in scored),
        episodes=tuple(ep for ep, _ in scored),
        reactions=tuple(r for _, r in scored),
        base_rates=(row,),
    )
    write_db(tmp_path / "x.sqlite", build)
    db = RatesDB.open(tmp_path / "x.sqlite")
    stored = db._conn.execute("SELECT weak_signal FROM base_rates").fetchone()[0]
    db.close()
    assert bool(stored) is weak


# ---- day 0 ---------------------------------------------------------------------------------


def test_day0_is_the_entry_sessions_own_move_and_stays_out_of_returns() -> None:
    panel = make_panel(Market.US)
    r = backtest.react(event("x", D(2019, 3, 13), "10:00"), panel, 5)
    i = panel.sessions.get_loc(pd.Timestamp(D(2019, 3, 13)))
    s, b = panel.series_close, panel.bench_close
    assert r.day0_raw == pytest.approx(s[i] / s[i - 1] - 1)
    assert r.day0_excess == pytest.approx(s[i] / s[i - 1] - b[i] / b[i - 1])
    assert r.raw_return == pytest.approx(s[i + 5] / s[i] - 1)


# ---- eras and the India benchmark ----------------------------------------------------------


def _rows(build, type_, asset):
    return {r.era: r for r in build.base_rates if r.type == type_ and r.asset == asset
            and r.cause is None}  # fmt: skip


def test_jets_gets_both_us_eras(tiny_book) -> None:
    rows = _rows(backtest.build(*tiny_book), EventType.OIL_SUPPLY, "JETS")
    assert set(rows) == {EraName.SINCE_1998, EraName.SINCE_1926}
    assert (rows[EraName.SINCE_1998].series, rows[EraName.SINCE_1998].benchmark) == ("JETS", "SPY")
    assert (rows[EraName.SINCE_1926].series, rows[EraName.SINCE_1926].benchmark) == (
        "FF49:Trans", "FF:Mkt")  # fmt: skip


def test_nsebank_gets_only_the_nifty_era(tiny_book) -> None:
    rows = _rows(backtest.build(*tiny_book), EventType.RBI_HIKE, "^NSEBANK")
    assert set(rows) == {EraName.SINCE_2007}
    assert rows[EraName.SINCE_2007].benchmark == "^NSEI (^BSESN before 2007-09-17)"


def test_sensex_gets_both_india_eras_scored_raw(tiny_book) -> None:
    rows = _rows(backtest.build(*tiny_book), EventType.RBI_HIKE, "^BSESN")
    assert set(rows) == {EraName.SINCE_2007, EraName.SINCE_1997}
    assert {r.measure for r in rows.values()} == {"raw"}


def test_india_benchmark_splices_nifty_returns_onto_the_sensex() -> None:
    days = sessions(D(2007, 9, 10), D(2007, 9, 21))
    bse = pd.Series(np.arange(1.0, 11.0) * 10, index=days)  # rises 10 a day
    nse = pd.Series([100.0, 50.0, 100.0, 200.0, 100.0], index=days[5:])  # from Sep 17
    level = backtest.splice([nse, bse])
    returns = level.pct_change().dropna()
    assert returns.loc["2007-09-14"] == pytest.approx(50 / 40 - 1)  # Sensex before the Nifty
    assert returns.loc["2007-09-18"] == pytest.approx(-0.5)  # the Nifty once it exists
    assert returns.loc["2007-09-20"] == pytest.approx(1.0)


def test_self_benchmarked_series_scores_raw_return(tiny_book) -> None:
    rows = _rows(backtest.build(*tiny_book), EventType.OIL_SUPPLY, "SPY")
    assert rows[EraName.SINCE_1998].measure == "raw"


# ---- vault ---------------------------------------------------------------------------------


def test_exclude_vault_ignores_every_2022_price(tiny_book, tmp_path) -> None:
    events, prices = tiny_book
    noisy = {}
    for path in prices.glob("*.csv"):
        frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")["close"]
        noise = np.random.default_rng(3).uniform(0.1, 10.0, len(frame))
        noisy[path.stem.replace("__", ":")] = frame.where(frame.index < "2022-01-01", frame * noise)
    other = write_prices(tmp_path / "noisy", noisy)

    def rows(p):
        built = backtest.build(events, p, exclude_vault=True)
        return sorted((dataclasses.astuple(r) for r in built.base_rates), key=repr)

    assert rows(prices) == rows(other)


def test_rows_are_tagged_when_they_include_vault_events(tiny_book) -> None:
    full = _rows(backtest.build(*tiny_book), EventType.OIL_SUPPLY, "JETS")
    assert full[EraName.SINCE_1998].includes_vault
    cut = _rows(backtest.build(*tiny_book, exclude_vault=True), EventType.OIL_SUPPLY, "JETS")
    assert not cut[EraName.SINCE_1998].includes_vault


def test_horizons_cover_every_type() -> None:
    assert set(backtest.HORIZONS) == set(EventType)
