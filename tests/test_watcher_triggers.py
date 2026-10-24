"""Classification once per confirmed story, news-first insights that carry odds() exactly,
and the price-first jump rule."""

from __future__ import annotations

import dataclasses
import datetime as dt
import functools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from networth import config
from networth.engine import backtest, odds
from networth.engine.model import DEFAULT_DB, EventType, Region, write_db
from networth.llm import Classified
from networth.watcher import classify, group, triggers
from networth.watcher.pull import pull
from networth.watcher.store import Store
from tests.watcher_fakes import EVENT_DAY, FAKE_ENV, NOW, FakeModels, FakeSearch

SINCE = NOW - dt.timedelta(hours=48)
OLDEST = triggers.oldest_event(NOW, 7)
WINDOW = 60
MULTIPLE = 2.5
DAILY = 0.01  # the alternating +-1% history has a std just above 1%


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


@pytest.fixture
def store(tmp_path: Path):
    s = Store.open(tmp_path / "watcher.sqlite")
    yield s
    s.close()


def confirmed_cycle(cfg, store, models):
    pull(cfg, FakeSearch(), store, NOW)
    group.assign_stories(store, models, cfg.group_batch_size, SINCE)
    verdicts = group.decide(store, cfg.confirm, NOW)
    return verdicts, classify.classify_confirmed(
        store,
        models,
        verdicts,
        classify.allowed_causes(),
        cfg.max_judge_calls_per_cycle,
        NOW,
    )


def no_prices(name: str) -> pd.Series:
    raise FileNotFoundError(name)


def test_only_confirmed_stories_are_classified_and_only_once(cfg, store) -> None:
    models = FakeModels()
    verdicts, first = confirmed_cycle(cfg, store, models)
    second = classify.classify_confirmed(
        store,
        models,
        verdicts,
        classify.allowed_causes(),
        cfg.max_judge_calls_per_cycle,
        NOW,
    )
    assert sorted(models.classified) == ["opec_cut", "rbi_hike"]
    assert (first.classified, second.classified) == (2, 0)


def test_stories_over_the_cap_wait_and_are_counted(cfg, store) -> None:
    pull(cfg, FakeSearch(), store, NOW)
    group.assign_stories(store, FakeModels(), cfg.group_batch_size, SINCE)
    verdicts = group.decide(store, cfg.confirm, NOW)
    out = classify.classify_confirmed(
        store, FakeModels(), verdicts, classify.allowed_causes(), 1, NOW
    )
    assert (out.classified, out.over_cap) == (1, 1)


def test_allowed_causes_come_from_events_csv() -> None:
    allowed = classify.allowed_causes()
    assert allowed[backtest.EventType.RBI_HIKE] == ("inflation",)


def rbi_insights(cfg, store, rates_db: Path) -> dict[str, dict]:
    verdicts, _ = confirmed_cycle(cfg, store, FakeModels())
    odds_fn = functools.partial(odds.odds, db=rates_db)
    triggers.write_insights(store, verdicts, cfg.triggers, odds_fn, no_prices, SINCE, NOW, OLDEST)
    return {i.asset: dict(i.odds) for i in store.insights() if i.type == "rbi_hike"}


def test_rbi_hike_insight_matches_odds_on_a_built_db(cfg, store, tiny_book, tmp_path) -> None:
    db = tmp_path / "rates.sqlite"
    write_db(db, backtest.build(*tiny_book))
    got = rbi_insights(cfg, store, db)
    assert got["^NSEBANK"] == odds.odds("rbi_hike", "^NSEBANK", db=db)


@pytest.mark.skipif(not DEFAULT_DB.exists(), reason="data/base_rates.sqlite not built")
def test_rbi_hike_insight_matches_odds_on_the_real_db(cfg, store) -> None:
    got = rbi_insights(cfg, store, DEFAULT_DB)
    assets = cfg.triggers.assets_by_type[backtest.EventType.RBI_HIKE]
    assert set(got) == set(assets)
    assert all(got[a] == odds.odds("rbi_hike", a) for a in assets)


def test_writing_insights_twice_keeps_one_row_each(cfg, store, tiny_book, tmp_path) -> None:
    db = tmp_path / "rates.sqlite"
    write_db(db, backtest.build(*tiny_book))
    rbi_insights(cfg, store, db)
    first = len(store.insights())
    rbi_insights(cfg, store, db)
    assert len(store.insights()) == first


def closes(last_move: float, end: str = "2026-06-30") -> pd.Series:
    moves = [DAILY if i % 2 else -DAILY for i in range(WINDOW)] + [last_move]
    days = pd.bdate_range(end=end, periods=len(moves) + 1)
    return pd.Series(100.0 * np.cumprod([1.0, *(1.0 + np.array(moves))]), index=days)


def test_price_jump_fires_above_the_multiple_and_not_below() -> None:
    sigma = pd.Series([DAILY if i % 2 else -DAILY for i in range(WINDOW)]).std()
    above, below = 1.1 * MULTIPLE * sigma, 0.9 * MULTIPLE * sigma
    fired = triggers.price_jump(closes(above), None, MULTIPLE, WINDOW)
    assert fired is not None and fired.move == pytest.approx(above)
    assert triggers.price_jump(closes(below), None, MULTIPLE, WINDOW) is None
    assert triggers.price_jump(closes(-above), None, MULTIPLE, WINDOW) is not None


def test_price_jump_measures_the_excess_over_the_benchmark() -> None:
    market = closes(0.05)
    assert triggers.price_jump(market, None, MULTIPLE, WINDOW) is not None
    assert triggers.price_jump(market, market, MULTIPLE, WINDOW) is None


def test_price_jump_without_a_story_is_noted(cfg, store) -> None:
    cfg_one = dataclasses.replace(cfg.triggers, price_watch=(config.PriceWatch("XLK", None),))
    jump_day = closes(0.08, end="2026-10-23")
    assert jump_day.index[-1].date() >= SINCE.date()
    out = triggers.write_insights(
        store, {}, cfg_one, lambda t, a: {}, lambda name: jump_day, SINCE, NOW, OLDEST
    )
    assert out.insights == 0 and len(out.jumps) == 1
    assert any("price jump on XLK" in n and "no confirmed story" in n for n in out.notes)


def test_price_jump_with_a_confirmed_story_writes_a_price_insight(cfg, store) -> None:
    verdicts, _ = confirmed_cycle(cfg, store, FakeModels())
    watch = dataclasses.replace(cfg.triggers, price_watch=(config.PriceWatch("^NSEBANK", None),))
    jump_day = closes(0.08, end="2026-10-23")
    fake_odds = {"hit_rate": 0.5}
    triggers.write_insights(
        store, verdicts, watch, lambda t, a: fake_odds, lambda name: jump_day, SINCE, NOW, OLDEST
    )
    price = [i for i in store.insights() if i.trigger == "price"]
    assert [(i.asset, i.type, dict(i.odds)) for i in price] == [("^NSEBANK", "rbi_hike", fake_odds)]


def news_assets(cfg, store, answer) -> set[str]:
    verdicts, _ = confirmed_cycle(cfg, store, FakeModels({"rbi_hike": answer}))
    triggers.write_insights(
        store, verdicts, cfg.triggers, lambda t, a: {}, no_prices, SINCE, NOW, OLDEST
    )
    return {i.asset for i in store.insights() if i.trigger == "news"}


def bank_stress(region: Region, day: dt.date = EVENT_DAY) -> Classified:
    return Classified(EventType.BANK_STRESS, "bank_failure", day, region, "a bank failed")


@pytest.mark.parametrize(
    ("region", "assets"),
    [(Region.IN, {"^NSEBANK"}), (Region.US, {"XLF"}), (Region.GLOBAL, {"XLF", "^NSEBANK"})],
)
def test_a_story_only_reaches_assets_in_its_region(cfg, store, region, assets) -> None:
    assert set(cfg.triggers.assets_by_type[EventType.BANK_STRESS]) == {"XLF", "^NSEBANK"}
    assert news_assets(cfg, store, bank_stress(region)) == assets


@pytest.mark.parametrize(("age_days", "assets"), [(7, {"^NSEBANK"}), (8, set()), (18, set())])
def test_an_event_older_than_the_cutoff_writes_no_insight(cfg, store, age_days, assets) -> None:
    day = NOW.date() - dt.timedelta(days=age_days)
    assert news_assets(cfg, store, bank_stress(Region.IN, day)) == assets


def test_two_stories_of_one_event_write_one_insight_set_under_the_first(cfg, store) -> None:
    hike = Classified(EventType.RBI_HIKE, "inflation", EVENT_DAY, Region.IN, "repo rate raised")
    verdicts, _ = confirmed_cycle(cfg, store, FakeModels({"rbi_hike": hike, "opec_cut": hike}))
    triggers.write_insights(
        store, verdicts, cfg.triggers, lambda t, a: {}, no_prices, SINCE, NOW, OLDEST
    )
    first = next(s.id for s in store.stories() if s.title == "rbi_hike")
    got = sorted((i.asset, i.story_id) for i in store.insights())
    assert got == [("^NSEBANK", first), ("^NSEI", first)]
