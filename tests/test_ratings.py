"""The rating engine: every number sourced, missing data said and never filled, the track
record computed from history."""

from __future__ import annotations

import pandas as pd
import pytest

from networth.ratings import rate, rating_json, track
from networth.ratings.model import View, money, view_for
from tests.ratings_fakes import NOW, FakeSources, info, seen, walk

TABLE = {"groups": [
    {"kind": "in_stock", "baseline_rate": 0.55, "rows": [
        {"view": v.value, "n": 100, "beat": 60} for v in View]},
    {"kind": "in_fund", "baseline_rate": 0.8, "rows": [
        {"view": v.value, "n": 10, "beat": 9} for v in View]},
    {"kind": "us_stock", "baseline_rate": 0.58, "rows": [
        {"view": v.value, "n": 100, "beat": 58} for v in View]},
]}  # fmt: skip


def rated(query: str, sources: FakeSources | None = None, **kw: object):
    return rate(query, now=NOW, sources=sources or FakeSources(), table=TABLE, **kw)


@pytest.mark.parametrize("query", ["HDFCBANK", "MF120716", "SFCTECH", "AAPL", "nifty 50 index"])
def test_no_driver_lacks_a_source_and_a_time(query: str) -> None:
    card = rating_json(rated(query))
    assert card["drivers"]
    for d in card["drivers"]:
        assert d["value"] and d["source"]["name"] and d["source"]["url"], d
        assert d["source"]["as_of"][:4].isdigit(), d


def test_every_rating_has_a_view_a_score_and_a_track_line() -> None:
    for q in ("HDFCBANK", "MF120716", "SFCTECH"):
        r = rated(q)
        assert r.view is view_for(r.score) and 0 <= r.score <= 100
        assert r.track.text and r.outlook.endswith(".")


def test_missing_data_is_named_and_lowers_the_confidence() -> None:
    full = rated("HDFCBANK", FakeSources(stories=(seen("HDFC Bank profit rises"),)))
    bare_stock = info("HDFCBANK", revenue_growth=None, earnings_growth=None, pe=None, pb=None)
    bare = rated("HDFCBANK", FakeSources(stocks={"HDFCBANK.NS": bare_stock}, stories=None))
    assert full.confidence == "high" and not full.missing
    assert bare.confidence == "low"
    assert {d.key for d in bare.drivers} == {"momentum", "sector"}
    assert any(m.startswith("Growth") for m in bare.missing)
    assert any(m.startswith("News") for m in bare.missing)


def test_a_bank_gets_no_debt_driver_and_loses_no_confidence_for_it() -> None:
    r = rated("HDFCBANK", FakeSources(stories=()))
    assert "debt" not in {d.key for d in r.drivers}
    assert not any("Balance sheet" in m for m in r.missing)


def test_news_tone_counts_only_confirmed_stories_that_name_it() -> None:
    stories = (seen("HDFC Bank profit jumps on record lending"), seen("ICICI Bank slumps"))
    news = next(d for d in rated("HDFCBANK", FakeSources(stories=stories)).drivers
                if d.key == "news")  # fmt: skip
    assert news.value.startswith("1 confirmed story") and news.effect == "up"


def test_a_us_share_is_in_dollars_against_the_sp_500() -> None:
    r = rated("AAPL")
    assert r.currency == "USD"
    assert "S&P 500" in r.track.text
    assert "S&P 500" in next(d.value for d in r.drivers if d.key == "momentum")
    assert "Nifty" not in " ".join(d.value for d in r.drivers)


def test_an_ipo_reads_the_rhp_and_says_subscription_is_not_live() -> None:
    r = rated("SFCTECH")
    keys = {d.key for d in r.drivers}
    assert {"valuation", "financials", "fresh", "use"} <= keys
    assert any("bidding opens 27-Oct-2026" in m for m in r.missing)
    assert r.track.n == 0 and r.track.weak
    val = next(d for d in r.drivers if d.key == "valuation")
    assert "P/E 20.0" in val.value  # 330 / 16.52, both sourced


def test_an_unknown_name_is_a_lookup_error() -> None:
    empty = FakeSources(stocks={})
    empty.fund_search = lambda q: []  # type: ignore[method-assign]
    with pytest.raises(LookupError):
        rated("NOSUCHCO", empty)


def test_the_track_line_says_a_weak_edge_plainly() -> None:
    t = track.track_line(TABLE, "stock", View.STRONG, "in")
    assert t.text.startswith("Ratings like this beat the Nifty 6 times in 10 since 2015")
    assert t.weak and "too small" in t.edge  # 60% against 55% all-stock is 5 points, n=100
    us = track.track_line(TABLE, "stock", View.STRONG, "us")
    assert "S&P 500" in us.text and us.edge.endswith("0 points. That is too small to lean on.")


def test_the_backtest_hit_rate_is_computed_from_prices() -> None:
    def stock(t: str) -> pd.Series:
        return walk(0.12 if t == "TCS.NS" else 0.08, len(t))

    table = track.build(stock, lambda code: walk(0.1, code % 50), "2026-10-25")
    stocks = next(g for g in table["groups"] if g["kind"] == "in_stock")
    assert stocks["n"] == sum(r["n"] for r in stocks["rows"]) > 1000
    for r in stocks["rows"]:
        assert r["rate"] == f"{r['beat'] / r['n'] * 100:.0f}%"
    assert table["skipped"] == []


def test_the_stored_table_has_every_group_and_its_method() -> None:
    table = track.load()
    assert table is not None and "price part" in table["caveat"]
    assert [g["kind"] for g in table["groups"]] == list(track.GROUPS)
    for g in table["groups"]:
        assert g["n"] == sum(r["n"] for r in g["rows"])


@pytest.mark.parametrize(("amount", "currency", "words"), [
    (291000, "INR", "₹2.91 lakh"), (12000000, "INR", "₹1.2 crore"), (16000, "INR", "₹16,000"),
    (1.5e9, "INR", "₹150 crore"), (12400, "USD", "$12,400"), (1200000, "USD", "$1.2M"),
    (-1200, "INR", "−₹1,200"),
])  # fmt: skip
def test_money_follows_the_currency_as_13a_writes_it(amount, currency, words) -> None:
    assert money(amount, currency) == words


def test_an_ipo_writes_its_issue_in_crore_not_a_long_rupee_number() -> None:
    fresh = next(d for d in rated("SFCTECH").drivers if d.key == "fresh")
    assert fresh.value.startswith("₹150 crore fresh against about ₹517.53 crore")
