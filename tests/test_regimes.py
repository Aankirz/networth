from __future__ import annotations

import csv
import datetime as dt
import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

import pytest

from networth.engine import backtest, macro, odds
from networth.engine.macro import Macro
from networth.engine.model import DATA_DIR, DEFAULT_DB, EventType, Region, write_db
from tests.canaries import REGIME_CANARIES
from tests.conftest import BOOK_EVENTS, book_series, row, write_events, write_prices

D = dt.date
GOLDEN = Path(__file__).parent / "fixtures" / "golden"
FED_CUT, FED_HIKE = EventType.FED_CUT, EventType.FED_HIKE
RBI_HIKE, RBI_CUT = EventType.RBI_HIKE, EventType.RBI_CUT


def months(first: dt.date, last: dt.date) -> list[dt.date]:
    out = [first]
    while out[-1] < last:
        y, m = divmod(out[-1].month, 12)
        out.append(D(out[-1].year + y, m + 1, 1))
    return out


def us_cpi(values: Mapping[dt.date, float], released: Mapping[dt.date, dt.date] = {}) -> Macro:
    return Macro({}, {Region.US: dict(values)}, {}, cpi_released={Region.US: dict(released)})


def in_cpi(values: Mapping[dt.date, float], released: Mapping[dt.date, dt.date] = {}) -> Macro:
    return Macro({}, {Region.IN: dict(values)}, {}, cpi_released={Region.IN: dict(released)})


USREC_2000S = {m: 1.0 if D(2001, 4, 1) <= m <= D(2001, 11, 1) else 0.0
               for m in months(D(2000, 1, 1), D(2003, 12, 1))}  # fmt: skip
RECESSION = Macro(usrec=USREC_2000S, cpi_yoy={}, gaps={})


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (D(2001, 1, 3), True),
        (D(2000, 4, 20), True),
        (D(2000, 3, 15), False),
        (D(2001, 11, 6), False),
        (D(2002, 12, 10), False),
        (D(2003, 1, 15), None),
    ],
)
def test_recession_followed_on_hand_written_dates(day, expected) -> None:
    assert macro.recession_followed(day, FED_CUT, RECESSION) is expected


@pytest.mark.parametrize(
    ("make", "type_", "day", "yoy", "expected"),
    [
        (us_cpi, FED_HIKE, D(2019, 3, 25), 4.0, True),
        (us_cpi, FED_HIKE, D(2019, 3, 25), 3.99, False),
        (us_cpi, FED_CUT, D(2019, 3, 25), 5.0, True),
        (in_cpi, RBI_HIKE, D(2019, 3, 20), 6.0, True),
        (in_cpi, RBI_CUT, D(2019, 3, 20), 5.99, False),
        (in_cpi, RBI_CUT, D(2019, 3, 20), 5.0, False),
    ],
)
def test_inflation_threshold_boundaries(make, type_, day, yoy, expected) -> None:
    assert macro.inflation_high(day, type_, make({D(2019, 2, 1): yoy})) is expected


def test_missing_print_is_unknown() -> None:
    assert macro.inflation_high(D(2019, 3, 25), FED_CUT, us_cpi({D(2019, 1, 1): 9.0})) is None
    assert macro.inflation_high(D(2019, 3, 25), FED_CUT, in_cpi({D(2019, 2, 1): 9.0})) is None


@pytest.mark.parametrize(
    ("make", "type_", "day", "expected"),
    [
        (us_cpi, FED_CUT, D(2019, 2, 20), False),
        (us_cpi, FED_CUT, D(2019, 2, 21), False),
        (us_cpi, FED_CUT, D(2019, 2, 22), True),
        (in_cpi, RBI_CUT, D(2019, 2, 13), False),
        (in_cpi, RBI_CUT, D(2019, 2, 14), False),
        (in_cpi, RBI_CUT, D(2019, 2, 15), True),
    ],
)
def test_release_lag_older_print_until_after_release_day(make, type_, day, expected) -> None:
    prints = make({D(2018, 12, 1): 1.0, D(2019, 1, 1): 9.0})
    assert macro.inflation_high(day, type_, prints) is expected


class LeakDetected(AssertionError):
    pass


LEAK_RELEASED = {D(2020, 11, 1): D(2021, 1, 15), D(2019, 3, 1): D(2019, 4, 10)}
LEAK_CASES = [
    ("us_day_before_release", D(2019, 2, 20), FED_CUT, D(2018, 12, 1)),
    ("us_release_day", D(2019, 2, 21), FED_CUT, D(2018, 12, 1)),
    ("us_day_after_release", D(2019, 2, 22), FED_CUT, D(2019, 1, 1)),
    ("us_month_start", D(2019, 3, 1), FED_HIKE, D(2019, 1, 1)),
    ("us_late_month", D(2019, 3, 25), FED_HIKE, D(2019, 2, 1)),
    ("us_leap_february_release_day", D(2020, 3, 21), FED_CUT, D(2020, 1, 1)),
    ("us_leap_february_after", D(2020, 3, 22), FED_CUT, D(2020, 2, 1)),
    ("us_delayed_release_past_fixed_lag", D(2020, 12, 28), FED_CUT, D(2020, 10, 1)),
    ("us_delayed_release_day", D(2021, 1, 15), FED_HIKE, D(2020, 10, 1)),
    ("us_delayed_release_day_after", D(2021, 1, 16), FED_HIKE, D(2020, 11, 1)),
    ("us_early_release_day_after", D(2019, 4, 11), FED_HIKE, D(2019, 3, 1)),
    ("in_day_before_release", D(2019, 2, 13), RBI_HIKE, D(2018, 12, 1)),
    ("in_release_day", D(2019, 2, 14), RBI_CUT, D(2018, 12, 1)),
    ("in_day_after_release", D(2019, 2, 15), RBI_CUT, D(2019, 1, 1)),
    ("in_year_turn", D(2019, 1, 10), RBI_HIKE, D(2018, 11, 1)),
]
LEAK_MONTHS = months(D(2017, 1, 1), D(2021, 12, 1))


def check_reads(classify, name, day, type_, expected, released, months_) -> None:
    make = us_cpi if macro.CPI_REGION[type_] is Region.US else in_cpi
    for high, other in ((50.0, 0.0), (0.0, 50.0)):
        prints = make({m: high if m == expected else other for m in months_}, released)
        got = classify(day, type_, prints)
        if got is not (high > other):
            raise LeakDetected(f"{name}: read a print other than {expected:%Y-%m} ({got})")


def check_no_inflation_leak(classify: macro.Classifier) -> None:
    for name, day, type_, expected in LEAK_CASES:
        released = LEAK_RELEASED if macro.CPI_REGION[type_] is Region.US else {}
        check_reads(classify, name, day, type_, expected, released, LEAK_MONTHS)


def test_inflation_regime_does_not_leak(inflation_impl) -> None:
    check_no_inflation_leak(inflation_impl)


@pytest.mark.parametrize("canary", sorted(REGIME_CANARIES))
def test_leak_check_catches_every_canary(canary: str) -> None:
    with pytest.raises(LeakDetected):
        check_no_inflation_leak(REGIME_CANARIES[canary])


def test_a_month_published_without_a_print_is_not_public_before_its_release() -> None:
    released = {D(2025, 9, 1): D(2025, 10, 24), D(2025, 10, 1): D(2025, 12, 18),
                D(2025, 11, 1): D(2025, 12, 18)}  # fmt: skip
    prints = us_cpi({D(2025, 9, 1): 50.0, D(2025, 11, 1): 0.0}, released)
    assert macro.inflation_high(D(2025, 12, 10), FED_CUT, prints) is True
    assert macro.inflation_high(D(2025, 12, 19), FED_CUT, prints) is False


REAL_MACRO = DATA_DIR / "macro"


@pytest.mark.skipif(
    not (REAL_MACRO / "CPIAUCSL.csv").exists(), reason="run networth.engine.macro first"
)
def test_every_fed_event_reads_a_us_print_released_before_it(inflation_impl) -> None:
    released = Macro.load(REAL_MACRO).cpi_released[Region.US]
    assert released, "CPIAUCSL.csv has no release dates: rerun networth.engine.macro"
    events, _ = backtest.parse_events()
    fed = [e for e in events if e.type in (FED_HIKE, FED_CUT)]
    assert fed and min(e.date for e in fed) > min(released.values())
    months_ = sorted(released)
    for e in fed:
        newest = max(m for m, r in released.items() if r < e.date)
        check_reads(inflation_impl, e.id, e.date, e.type, newest, released, months_)


def test_rules_apply_to_the_brief_types_and_say_hindsight() -> None:
    rules = macro.REGIMES
    assert rules["recession_followed"].types == {FED_HIKE, FED_CUT}
    assert rules["recession_followed"].hindsight is True
    assert rules["inflation_high"].types == {FED_HIKE, FED_CUT, RBI_HIKE, RBI_CUT}
    assert rules["inflation_high"].hindsight is False


def write_series(directory: Path, name: str, values: Mapping[dt.date, float]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{name}.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "value"])
        writer.writerows((m.isoformat(), v) for m, v in sorted(values.items()))


def test_saved_release_dates_load_back(tmp_path) -> None:
    series = macro.MonthlySeries(
        "CPIAUCSL",
        {D(1972, 7, 1): 125.31, D(2025, 9, 1): 324.368},
        released={D(2025, 9, 1): D(2025, 10, 24), D(2025, 10, 1): D(2025, 12, 18)},
    )
    macro.save_series(series, tmp_path)
    loaded = macro.load_series("CPIAUCSL", tmp_path)
    assert (loaded.values, loaded.released) == (series.values, series.released)


def test_load_cuts_months_and_unreleased_prints_at_as_of(tmp_path) -> None:
    span = months(D(2019, 1, 1), D(2022, 6, 1))
    write_series(tmp_path, "USREC", {m: 0.0 for m in span})
    cpi = {m: 100.0 * 1.05 ** (m.year - 2019) for m in span}
    macro.save_series(
        macro.MonthlySeries("CPIAUCSL", cpi, released={D(2021, 11, 1): D(2022, 1, 5)}), tmp_path
    )
    write_series(tmp_path, "IN_CPI", {m: 5.0 for m in span})
    loaded = Macro.load(tmp_path, as_of=D(2021, 12, 31))
    assert max(loaded.usrec) == D(2021, 12, 1)
    assert max(loaded.cpi_yoy[Region.US]) == D(2021, 10, 1)
    assert max(loaded.cpi_yoy[Region.IN]) == D(2021, 11, 1)
    assert min(loaded.cpi_yoy[Region.US]) == D(2020, 1, 1)
    assert loaded.cpi_yoy[Region.US][D(2021, 6, 1)] == pytest.approx(5.0)
    assert loaded.gaps == {}


def test_load_without_files_records_every_gap(tmp_path) -> None:
    loaded = Macro.load(tmp_path / "absent")
    assert set(loaded.gaps) == {"USREC", "CPIAUCSL", "IN_CPI"}
    assert loaded.cpi_yoy == {} and loaded.usrec == {}


FED_EVENTS = [
    row("fed_2001a", "2001-01-03", "fed_cut", "us"),
    row("fed_2003b", "2003-06-25", "fed_cut", "us"),
    row("fed_2019a", "2019-07-31", "fed_cut", "us"),
    row("fed_2021a", "2021-03-17", "fed_cut", "us"),
]
NBER = {m: 1.0 if D(2001, 4, 1) <= m <= D(2001, 11, 1) or D(2020, 3, 1) <= m <= D(2020, 4, 1)
        else 0.0 for m in months(D(1990, 1, 1), D(2023, 6, 1))}  # fmt: skip


def cpi_index() -> dict[dt.date, float]:
    out, level = {}, 100.0
    for m in months(D(1990, 1, 1), D(2023, 6, 1)):
        out[m] = level
        level *= (1.05 if m.year <= 2001 else 1.01) ** (1 / 12)
    return out


INDIA = {m: 9.0 if m.year <= 2013 else 3.0 for m in months(D(2009, 1, 1), D(2023, 6, 1))}


def write_macro(directory: Path, *, india: bool = True, garble_after: dt.date | None = None):
    def garbled(values, bad):
        return {m: bad(v) if garble_after and m >= garble_after else v for m, v in values.items()}

    write_series(directory, "USREC", garbled(NBER, lambda v: 1.0))
    write_series(directory, "CPIAUCSL", garbled(cpi_index(), lambda v: v * 3))
    if india:
        write_series(directory, "IN_CPI", garbled(INDIA, lambda v: 99.0))
    return directory


@pytest.fixture
def world(tmp_path):
    events = write_events(tmp_path / "events.csv", [*BOOK_EVENTS, *FED_EVENTS])
    return events, write_prices(tmp_path / "prices", book_series())


def built(world, tmp_path, name="rates", **kwargs) -> Path:
    path = tmp_path / f"{name}.sqlite"
    write_db(path, backtest.build(*world, **kwargs))
    return path


def test_split_returns_both_sides_with_hindsight(world, tmp_path) -> None:
    db = built(world, tmp_path, macro_dir=write_macro(tmp_path / "macro"))
    out = odds.split("fed_cut", "SPY", "recession_followed", db=db)
    assert set(out) == set(odds.SplitJSON.__annotations__)
    assert (out["era"], out["regime"], out["hindsight"]) == ("since_1998", "recession_followed",
                                                            True)  # fmt: skip
    yes, no = out["sides"]
    assert all(set(s) == set(odds.SideJSON.__annotations__) for s in out["sides"])
    assert (yes["value"], yes["regime"]) == ("yes", "recession_followed=yes")
    assert yes["episode_ids"] == ["fed_cut:fed_2001a", "fed_cut:fed_2019a"]
    assert no["episode_ids"] == ["fed_cut:fed_2003b", "fed_cut:fed_2021a"]
    assert (out["n_episodes_all"], out["n_unclassified"]) == (4, 0)
    assert all(s["hindsight"] is True and s["weak_signal"] is True for s in out["sides"])
    assert all(s["baseline"] == out["baseline"] for s in out["sides"])
    assert all(s["n_hits"] <= s["n_episodes"] == 2 for s in out["sides"])


def test_split_counts_the_unclassified_and_is_not_hindsight_for_inflation(world, tmp_path):
    db = built(world, tmp_path, macro_dir=write_macro(tmp_path / "macro"))
    out = odds.split("rbi_hike", "^BSESN", "inflation_high", era="since_1997", db=db)
    yes, no = out["sides"]
    assert [e.split(":")[1] for e in yes["episode_ids"]] == ["rbi_2010a", "rbi_2011b", "rbi_2014a"]
    assert [e.split(":")[1] for e in no["episode_ids"]] == ["rbi_2018b", "rbi_2023a"]
    assert (out["n_episodes_all"], out["n_unclassified"]) == (6, 1)
    assert out["hindsight"] is False and not any(s["hindsight"] for s in out["sides"])
    us = odds.split("fed_cut", "SPY", "inflation_high", db=db)
    assert [s["episode_ids"] for s in us["sides"]] == [
        ["fed_cut:fed_2001a"], ["fed_cut:fed_2003b", "fed_cut:fed_2019a", "fed_cut:fed_2021a"]
    ]  # fmt: skip


def test_an_empty_side_is_still_returned(world, tmp_path) -> None:
    db = built(world, tmp_path, macro_dir=write_macro(tmp_path / "macro"))
    yes, no = odds.split("fed_cut", "SPY", "recession_followed", cause="cause_b", db=db)["sides"]
    assert (yes["n_episodes"], yes["n_hits"], yes["hit_rate"], yes["median"]) == (0, 0, None, None)
    assert yes["weak_signal"] is True and yes["episode_ids"] == []
    assert no["episode_ids"] == ["fed_cut:fed_2003b"]


def test_odds_with_a_regime_is_the_odds_shape_plus_regime(world, tmp_path) -> None:
    db = built(world, tmp_path, macro_dir=write_macro(tmp_path / "macro"))
    out = odds.odds("fed_cut", "SPY", db=db, regime="recession_followed=yes")
    assert set(out) == set(odds.RegimeOddsJSON.__annotations__)
    assert set(out) - set(odds.OddsJSON.__annotations__) == {"regime", "hindsight"}
    assert (out["regime"], out["hindsight"]) == ("recession_followed=yes", True)
    assert [e["episode_id"] for e in out["episodes"]] == ["fed_cut:fed_2001a", "fed_cut:fed_2019a"]
    plain = odds.odds("fed_cut", "SPY", db=db)
    assert set(plain) == set(odds.OddsJSON.__annotations__) and out["era"] == plain["era"]
    low = odds.odds("rbi_hike", "^NSEBANK", db=db, regime="inflation_high=no")
    assert low["hindsight"] is False and low["n_episodes"] == 2


def test_rows_without_a_regime_are_unchanged_by_macro_data(world, tmp_path) -> None:
    with_macro = backtest.build(*world, macro_dir=write_macro(tmp_path / "macro"))
    without = backtest.build(*world)
    assert with_macro.base_rates == without.base_rates
    assert with_macro.regime_rates and not without.regime_rates
    paths = built(world, tmp_path, "a", macro_dir=tmp_path / "macro"), built(world, tmp_path, "b")
    tables = [
        sqlite3.connect(p).execute("SELECT * FROM base_rates ORDER BY type, cause, asset, era")
        .fetchall()
        for p in paths
    ]  # fmt: skip
    assert tables[0] == tables[1]


def test_pre_vault_build_never_reads_2022_macro_data(world, tmp_path) -> None:
    def regime_rows(directory):
        return backtest.build(*world, exclude_vault=True, macro_dir=directory).regime_rates

    clean = regime_rows(write_macro(tmp_path / "clean"))
    garbled = regime_rows(write_macro(tmp_path / "garbled", garble_after=D(2021, 12, 1)))
    assert clean == garbled
    recession = [r for r in clean if r.regime.startswith("recession_followed")]
    assert recession
    assert not any("fed_cut:fed_2021a" in r.rate.episode_ids for r in recession)


def test_missing_india_cpi_is_a_clear_error(world, tmp_path) -> None:
    db = built(world, tmp_path, macro_dir=write_macro(tmp_path / "macro", india=False))
    with pytest.raises(odds.NoRegimeData, match="no India CPI"):
        odds.split("rbi_hike", "^NSEBANK", "inflation_high", db=db)
    with pytest.raises(odds.NoRegimeData, match="no India CPI"):
        odds.odds("rbi_hike", "^NSEBANK", db=db, regime="inflation_high=yes")
    assert odds.split("fed_cut", "SPY", "inflation_high", db=db)["sides"][0]["n_episodes"] == 1


def test_unknown_or_inapplicable_regimes_are_rejected(world, tmp_path) -> None:
    db = built(world, tmp_path, macro_dir=write_macro(tmp_path / "macro"))
    for args in (
        ("rbi_hike", "^NSEBANK", "recession_followed"),
        ("fed_cut", "SPY", "nope"),
        ("oil_supply", "SPY", "inflation_high"),
    ):
        with pytest.raises(ValueError):
            odds.split(*args, db=db)
    for label in ("inflation_high=maybe", "nope=yes", "recession_followed"):
        with pytest.raises(ValueError):
            odds.odds("fed_cut", "SPY", db=db, regime=label)


def test_fixture_book_answers_match_the_pre_phase_golden(tiny_book, tmp_path) -> None:
    db = tmp_path / "r.sqlite"
    write_db(db, backtest.build(*tiny_book))
    out = {
        "odds_rbi_hike_NSEBANK": odds.odds("rbi_hike", "^NSEBANK", db=db),
        "odds_oil_supply_JETS": odds.odds("oil_supply", "JETS", db=db),
        "position_range_2000_JETS_oil_supply": odds.position_range(
            2000, "JETS", "oil_supply", db=db
        ),
    }
    expected = (GOLDEN / "fixture_book.json").read_text(encoding="utf-8")
    assert json.dumps(out, indent=1, sort_keys=True) + "\n" == expected


real = pytest.mark.skipif(not DEFAULT_DB.exists(), reason="run networth.engine.backtest first")


@real
@pytest.mark.parametrize(
    ("golden", "call"),
    [
        ("odds_rbi_hike_NSEBANK.json", lambda: odds.odds("rbi_hike", "^NSEBANK")),
        ("odds_fed_cut_XLF.json", lambda: odds.odds("fed_cut", "XLF")),
        ("position_range_2000_JETS_oil_supply.json",
         lambda: odds.position_range(2000, "JETS", "oil_supply")),
        ("compare_fed_cut_XLF_QQQ.json", lambda: odds.compare("fed_cut", ["XLF", "QQQ"])),
    ],
    ids=lambda x: x if isinstance(x, str) else "",
)  # fmt: skip
def test_real_answers_match_the_pre_phase_golden(golden, call) -> None:
    assert json.dumps(call()) == (GOLDEN / golden).read_text(encoding="utf-8")
