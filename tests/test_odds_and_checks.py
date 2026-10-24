"""JSON shapes from a fixture-built sqlite file and from the real one when it exists,
check_events offline, outside_check on a planted drift."""

from __future__ import annotations

import datetime as dt
import json
import time

import numpy as np
import pandas as pd
import pytest

from networth.engine import backtest, check_events, odds, outside_check
from networth.engine.model import DEFAULT_DB, RatesDB, write_db
from tests.conftest import BOOK_EVENTS, row, sessions, write_events


def keys(td) -> set[str]:
    return set(td.__annotations__)


@pytest.fixture
def built_db(tiny_book, tmp_path):
    path = tmp_path / "rates.sqlite"
    write_db(path, backtest.build(*tiny_book))
    return path


def test_odds_has_the_spec_shape(built_db) -> None:
    out = odds.odds("oil_supply", "JETS", db=built_db)
    assert set(out) == keys(odds.OddsJSON)
    assert all(set(e) == keys(odds.EpisodeJSON) for e in out["episodes"])
    assert all(set(e) == keys(odds.EraJSON) for e in out["other_eras"])
    assert json.loads(json.dumps(out)) == out
    dates = [e["date"] for e in out["episodes"]]
    assert dates == sorted(dates) and len(dates) == out["n_episodes"]


def test_odds_lists_the_other_era_with_its_overlap(built_db) -> None:
    out = odds.odds("oil_supply", "JETS", db=built_db)
    assert out["era"] == "since_1998"
    (other,) = out["other_eras"]
    assert other["era"] == "since_1926" and other["series"] == "FF49:Trans"
    primary_ids = {e["episode_id"] for e in out["episodes"]}
    assert 0 < other["n_shared_with_primary"] <= len(primary_ids) < other["n_episodes"]


def test_missing_era_says_what_exists(built_db) -> None:
    with pytest.raises(odds.NoBaseRate, match="since_2007"):
        odds.odds("rbi_hike", "^NSEBANK", era="since_1997", db=built_db)


def test_unknown_inputs_are_rejected(built_db) -> None:
    for args in (("nope", "JETS"), ("oil_supply", "NOPE")):
        with pytest.raises(ValueError):
            odds.odds(*args, db=built_db)


def test_position_range_is_value_times_raw_quantiles(built_db) -> None:
    out = odds.position_range(2000, "JETS", "oil_supply", db=built_db)
    assert set(out) == keys(odds.PositionRangeJSON)
    db = RatesDB.open(built_db)
    (rate, *_) = db.base_rates(backtest.EventType.OIL_SUPPLY, "JETS", None)
    db.close()
    assert (out["p10"], out["median"], out["p90"]) == (
        round(2000 * rate.raw_p10),
        round(2000 * rate.raw_median),
        round(2000 * rate.raw_p90),
    )
    assert out["currency"] == "USD"
    assert odds.position_range(1000, "^NSEBANK", "rbi_hike", db=built_db)["currency"] == "INR"


def test_compare_scores_every_asset_on_the_same_episodes(built_db) -> None:
    out = odds.compare("oil_supply", ["JETS", "SPY"], db=built_db)
    assert set(out) == keys(odds.CompareJSON)
    assert all(set(a) == keys(odds.CompareAssetJSON) for a in out["assets"])
    jets_ids = [e["episode_id"] for e in odds.odds("oil_supply", "JETS", db=built_db)["episodes"]]
    assert out["episode_ids"] == jets_ids
    spy = out["assets"][1]
    assert spy["n_episodes_all"] > out["n_episodes"]


def test_compare_keeps_caller_order_and_rejects_bad_counts(built_db) -> None:
    out = odds.compare("oil_supply", ["SPY", "JETS"], db=built_db)
    assert [a["asset"] for a in out["assets"]] == ["SPY", "JETS"]
    for assets in (["JETS"], ["JETS", "JETS"], ["JETS", "SPY", "^BSESN", "^NSEI"]):
        with pytest.raises(ValueError):
            odds.compare("oil_supply", assets, db=built_db)


# ---- the real file (Done-when 5 and 8); skipped until backtest has run --------------------

real = pytest.mark.skipif(not DEFAULT_DB.exists(), reason="run networth.engine.backtest first")


@real
@pytest.mark.parametrize(("type_", "asset"), [("oil_supply", "JETS"), ("rbi_hike", "^NSEBANK")])
def test_real_rows_have_every_field(type_, asset) -> None:
    db = RatesDB.open(DEFAULT_DB)
    rows = db.base_rates(backtest.EventType(type_), asset, None)
    db.close()
    assert rows
    for r in rows:
        assert all(v is not None for k, v in vars(r).items() if k != "cause"), r


@real
def test_real_jets_has_both_us_eras() -> None:
    out = odds.odds("oil_supply", "JETS")
    assert {out["era"], *(e["era"] for e in out["other_eras"])} == {"since_1998", "since_1926"}


@real
def test_real_position_range_is_ordered_dollars() -> None:
    out = odds.position_range(2000, "JETS", "oil_supply")
    assert out["currency"] == "USD"
    assert out["p10"] <= out["median"] <= out["p90"]


# ---- check_events --------------------------------------------------------------------------


def test_check_events_reports_every_problem(tmp_path) -> None:
    rows = [
        row("ok", "2019-03-01", "fed_hike", "us"),
        {**row("t", "2019-03-01", "fed_hike", "us"), "type": "coup"},
        {**row("r", "2019-03-01", "fed_hike", "us"), "region": "eu"},
        {**row("d", "2019-03-01", "fed_hike", "us"), "date": "01/03/2019"},
        {**row("h", "2019-03-01", "fed_hike", "us"), "time_known": "4pm"},
        {**row("z", "2019-03-01", "fed_hike", "us"), "tz": "Mars/Olympus"},
        row("ok", "2019-03-02", "fed_hike", "us"),
    ]
    report = check_events.check(write_events(tmp_path / "e.csv", rows), url_status=None)
    assert sorted(p.field for p in report.problems) == ["date", "id", "region", "time_known",
                                                        "type", "tz"]  # fmt: skip
    assert not report.ok


def test_check_events_flags_dead_links_without_network(tmp_path) -> None:
    path = write_events(tmp_path / "e.csv", BOOK_EVENTS)
    dead = "https://example.org/oil_2016a"

    def fake(url: str) -> int | str:
        return 404 if url == dead else 301

    report = check_events.check(path, url_status=fake)
    assert [(d.event_id, d.result) for d in report.dead_links] == [("oil_2016a", 404)]


def test_check_events_enforces_targets(tmp_path) -> None:
    report = check_events.check(write_events(tmp_path / "e.csv", BOOK_EVENTS), url_status=None)
    assert "pandemic has 0 rows, need 5" in report.target_failures
    assert any(t.startswith("13 rows") for t in report.target_failures)


def test_real_event_library_parses_and_meets_targets() -> None:
    report = check_events.check(url_status=None)
    assert not report.problems and not report.target_failures


# ---- outside_check -------------------------------------------------------------------------


def test_outside_check_finds_a_planted_drift() -> None:
    days = sessions(dt.date(2000, 1, 3), dt.date(2003, 12, 31))
    rng = np.random.default_rng(5)
    fomc = list(days[::40].date)
    r = rng.normal(0, 0.001, len(days))
    r[days.isin(pd.to_datetime(fomc))] += 0.005
    closes = pd.Series(100 * np.cumprod(1 + r), index=days, name="SPY")
    result = outside_check.drift(closes, fomc, "pre_fomc", dt.date(2000, 1, 1), None, "t")
    assert 40 < result.mean_fomc_bp - result.mean_other_bp < 60
    assert result.t_stat > 5
    assert outside_check.verdict(result).startswith("MATCH")
    placebo = outside_check.drift(closes, fomc, "placebo", dt.date(2000, 1, 1), None, "t")
    assert abs(placebo.mean_fomc_bp) < 10 and outside_check.verdict(placebo).startswith("MISMATCH")


def test_outside_check_rejects_a_non_session_fomc_date() -> None:
    days = sessions(dt.date(2000, 1, 3), dt.date(2000, 3, 31))
    closes = pd.Series(np.linspace(100, 110, len(days)), index=days, name="SPY")
    with pytest.raises(ValueError, match="not SPY sessions"):
        outside_check.drift(
            closes, [dt.date(2000, 1, 8)], "pre_fomc", dt.date(2000, 1, 1), None, "t"
        )


def test_paper_claim_is_quoted_verbatim() -> None:
    assert outside_check.PAPER_URL.endswith("/sr512.pdf")
    assert "49 basis points" in outside_check.PAPER_CLAIM


def _one_link_events(tmp_path):
    return check_events.parse_events(
        write_events(tmp_path / "e.csv", [row("a", "2019-03-01", "fed_hike", "us")])
    )[0]


def test_a_stuck_url_fails_within_its_deadline(tmp_path) -> None:
    def stuck(url: str) -> int:
        time.sleep(5)
        return 200

    started = time.monotonic()
    dead, checked = check_events.check_links(_one_link_events(tmp_path), stuck, deadline=0.3)
    assert time.monotonic() - started < 2
    assert checked == 1 and len(dead) == 1 and "timeout after 0.3s" in str(dead[0].result)


def test_a_fetcher_that_raises_is_a_failure(tmp_path) -> None:
    def boom(url: str) -> int:
        raise OSError("network unreachable")

    dead, _ = check_events.check_links(_one_link_events(tmp_path), boom, deadline=1)
    assert len(dead) == 1 and "network unreachable" in str(dead[0].result)


class _FlakyOpener:
    """Stands in for the urllib opener: fails with a transport error `failures` times."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def open(self, req, timeout):
        self.calls += 1
        if self.calls <= self.failures:
            raise check_events.urllib.error.URLError("nodename nor servname provided")
        return _OkResponse()


class _OkResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def read(self, n: int) -> bytes:
        return b"x"


def test_one_transport_blip_is_retried(monkeypatch) -> None:
    monkeypatch.setattr(check_events, "_OPENER", _FlakyOpener(failures=1))
    assert check_events.http_status("https://example.org") == 200


def test_a_persistent_transport_error_still_fails(monkeypatch) -> None:
    monkeypatch.setattr(check_events, "_OPENER", _FlakyOpener(failures=5))
    result = check_events.http_status("https://example.org")
    assert isinstance(result, str) and "URLError" in result
