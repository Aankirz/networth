"""The plan range's return table, built from hand-made series. No network."""

from __future__ import annotations

import datetime as dt

import pytest

from networth.sim import config
from networth.sim.data import (
    MissingSeries,
    build_table,
    equity_returns,
    filled_yoy,
    load_table,
    rate_returns,
    save_table,
)

D = dt.date


def months(start: D, n: int) -> list[D]:
    out = [start]
    for _ in range(n - 1):
        m = out[-1]
        out.append(D(m.year + m.month // 12, m.month % 12 + 1, 1))
    return out


def flat(start: D, n: int, value: float) -> dict[D, float]:
    return dict.fromkeys(months(start, n), value)


def test_equity_return_uses_each_months_last_close() -> None:
    closes = {D(2020, 1, 30): 90.0, D(2020, 1, 31): 100.0, D(2020, 2, 3): 50.0,
              D(2020, 2, 28): 110.0}  # fmt: skip
    assert equity_returns(closes) == {D(2020, 2, 1): pytest.approx(0.10)}


def test_a_rate_of_twelve_percent_a_year_compounds_back_to_twelve() -> None:
    (monthly,) = rate_returns({D(2020, 1, 1): 12.0}).values()
    assert (1 + monthly) ** 12 == pytest.approx(1.12)


def test_two_missing_cpi_months_take_the_straight_line() -> None:
    yoy = {D(2020, 3, 1): 6.0, D(2020, 6, 1): 3.0}
    assert filled_yoy(yoy)[D(2020, 4, 1)] == pytest.approx(5.0)
    assert filled_yoy(yoy)[D(2020, 5, 1)] == pytest.approx(4.0)


def test_a_longer_cpi_hole_is_left_open() -> None:
    yoy = {D(2020, 1, 1): 6.0, D(2020, 5, 1): 3.0}
    assert D(2020, 3, 1) not in filled_yoy(yoy)


def test_window_is_the_overlap_and_stops_before_the_open_month() -> None:
    series = {
        "safety": flat(D(2011, 11, 1), 30, 0.005),
        "core": flat(D(2010, 1, 1), 60, 0.01),
        "growth": flat(D(2012, 1, 1), 40, 0.02),
        "cpi": flat(D(2012, 3, 1), 40, 0.004),
    }
    table = build_table(series, before=D(2013, 6, 1))
    assert (table.months[0], table.months[-1]) == (D(2012, 3, 1), D(2013, 5, 1))
    assert table.column("growth").tolist() == [0.02] * len(table.months)


def test_a_hole_inside_the_window_fails_with_the_series_and_month() -> None:
    series = {name: flat(D(2012, 1, 1), 24, 0.01) for name in config.COLUMNS}
    del series["core"][D(2012, 7, 1)]
    with pytest.raises(MissingSeries, match="core has no value for 2012-07"):
        build_table(series, before=D(2030, 1, 1))


def test_an_empty_series_fails_by_name() -> None:
    series = {name: flat(D(2012, 1, 1), 24, 0.01) for name in config.COLUMNS}
    series["safety"] = {}
    with pytest.raises(MissingSeries, match="no safety data"):
        build_table(series, before=D(2030, 1, 1))


def test_saved_table_reads_back_unchanged(tmp_path) -> None:
    series = {name: flat(D(2012, 1, 1), 12, 0.01 * (i + 1))
              for i, name in enumerate(config.COLUMNS)}  # fmt: skip
    table = build_table(series, before=D(2030, 1, 1))
    save_table(table, tmp_path)
    again = load_table(tmp_path)
    assert again.months == table.months
    assert again.returns.tolist() == table.returns.tolist()


def test_missing_table_names_the_build_command(tmp_path) -> None:
    with pytest.raises(MissingSeries, match="python -m networth.sim.data"):
        load_table(tmp_path)
