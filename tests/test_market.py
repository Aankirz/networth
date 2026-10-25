"""networth.market against a fake source: quotes, history, falls and finding names in a question."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from networth import market
from networth.market import Found


def series(values: list[float], start: str = "2021-01-01") -> pd.Series:
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)), dtype=float)


class FakeSource:
    def __init__(self, closes: dict[str, pd.Series], info: dict[str, dict] | None = None,
                 found: dict[str, list[dict]] | None = None) -> None:  # fmt: skip
        self._closes, self._info, self._found = closes, info or {}, found or {}
        self.searched: list[str] = []

    def closes(self, symbol: str, years: float) -> pd.Series:
        return self._closes.get(symbol, pd.Series(dtype=float))

    def info(self, symbol: str) -> dict:
        return self._info.get(symbol, {})

    def search(self, text: str) -> list[dict]:
        self.searched.append(text)
        return self._found.get(text, [])


SWIGGY = {"symbol": "SWIGGY.NS", "quoteType": "EQUITY", "longname": "Swiggy Limited"}
SWIGGY_BSE = {"symbol": "SWIGGY.BO", "quoteType": "EQUITY", "longname": "Swiggy Limited"}
TESLA = {"symbol": "TSLA", "quoteType": "EQUITY", "longname": "Tesla, Inc."}
TESLA_FUTURE = {"symbol": "STSLA=F", "quoteType": "FUTURE", "shortname": "Tesla futures"}


def test_a_quote_has_the_last_close_the_day_change_and_the_source_52_week_range() -> None:
    src = FakeSource({"SWIGGY.NS": series([300, 211.4, 176.0])},
                     {"SWIGGY.NS": {"currency": "INR", "exchange": "NSI", "yearLow": None,
                                    "low_52w": 174.95, "high_52w": 434.0}})  # fmt: skip
    q = market.quote("SWIGGY.NS", src, "Swiggy Limited")
    assert q is not None and (q.price, q.prev_close) == (176.0, 211.4)
    assert round(q.change_pct, 4) == round(176 / 211.4 - 1, 4)
    assert (q.low_52w, q.high_52w, q.exchange, q.currency) == (174.95, 434.0, "NSE", "INR")
    assert q.name == "Swiggy Limited" and q.day == dt.date(2021, 1, 5)


def test_a_symbol_the_source_does_not_know_gives_none_never_a_guess() -> None:
    assert market.quote("NOPE.NS", FakeSource({})) is None
    assert market.history("NOPE.NS", 5, FakeSource({})) is None


def test_history_returns_the_total_and_the_yearly_rate() -> None:
    days = pd.date_range("2016-01-01", "2026-01-01", freq="D")
    closes = pd.Series([100 * 2 ** (i / (len(days) - 1)) for i in range(len(days))], index=days)
    h = market.history("^NSEI", 10, FakeSource({"^NSEI": closes}))
    assert h is not None and h.name == "Nifty 50" and h.currency == "INR"
    assert round(h.total, 2) == 1.0, "about doubled: the span starts 3,650 days back"
    assert h.total == h.closes.iloc[-1] / h.closes.iloc[0] - 1
    assert round(h.per_year, 3) == round(2 ** (1 / h.years) - 1, 3)


def test_drawdowns_are_the_worst_separate_falls_with_their_recovery() -> None:
    s = series([100, 80, 100, 110, 66, 90, 120, 114, 100])
    falls = market.drawdowns(s)
    assert [round(f.fall, 2) for f in falls] == [0.4, 0.2, 0.17]
    assert falls[0].recovered == s.index[6].date()
    assert falls[2].recovered is None, "still below its peak at the end"


def test_a_dip_under_five_percent_is_not_a_fall() -> None:
    assert market.drawdowns(series([100, 97, 101, 99, 102])) == []


@pytest.mark.parametrize(("text", "symbols"), [
    ("How has Nifty 50 done over the last 5 years?", ["^NSEI"]),
    ("bank nifty vs sensex", ["^NSEBANK", "^BSESN"]),
    ("what did the s&p 500 and nasdaq do", ["^GSPC", "^IXIC"]),
    ("midcap or smallcap", ["^NSEMDCP50", "NIFTYSMLCAP250.NS"]),
])  # fmt: skip
def test_indices_are_found_by_the_names_people_use(text: str, symbols: list[str]) -> None:
    src = FakeSource({})
    assert [f.symbol for f in market.resolve(text, "INR", src)] == symbols
    assert src.searched == [], "an index name is never searched"


def test_a_rupee_reader_gets_the_nse_listing_and_futures_are_skipped() -> None:
    src = FakeSource({}, found={"swiggy": [SWIGGY_BSE, SWIGGY], "tesla": [TESLA_FUTURE, TESLA]})
    assert market.resolve("Should I invest in Swiggy shares now?", "INR", src) == (
        Found("SWIGGY.NS", "Swiggy Limited"),
    )
    assert market.resolve("what is tesla's current price", "INR", src) == (
        Found("TSLA", "Tesla, Inc."),
    )


def test_jio_means_reliance_and_is_not_searched() -> None:
    src = FakeSource({})
    (found,) = market.resolve("how good is jio stock as an investment", "INR", src)
    assert found.symbol == "RELIANCE.NS" and src.searched == []


def test_a_failing_search_finds_nothing() -> None:
    class Down(FakeSource):
        def search(self, text: str) -> list[dict]:
            raise ConnectionError("down")

    assert market.resolve("what is swiggy at", "INR", Down({})) == ()


@pytest.mark.parametrize(("text", "years"), [
    ("How has Nifty 50 done over the last 5 years?", 5), ("past ten years", 10),
    ("pichhle 3 saal mein", 3), ("Nifty 7 yrs", 7), ("what is tesla's price", None),
])  # fmt: skip
def test_years_asked(text: str, years: int | None) -> None:
    assert market.years_asked(text) == years
