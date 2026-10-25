"""Fake data sources for the rating tests: no network, every number made up and labelled."""

from __future__ import annotations

import dataclasses
import datetime as dt

import numpy as np
import pandas as pd

from networth.ratings.model import Source
from networth.ratings.sources import Closes, IpoDetail, IpoListing, Seen, StockInfo, Stories

NOW = dt.datetime(2026, 10, 25, 10, 0, tzinfo=dt.UTC)
DAYS = pd.bdate_range("2012-01-02", "2026-10-23")


def src(name: str = "Fake") -> Source:
    return Source(name, f"https://example.test/{name}", "2026-10-23")


def walk(drift: float, seed: int) -> pd.Series:
    rng = np.random.default_rng(seed)
    steps = drift / 252 + rng.normal(0, 0.01, len(DAYS))
    return pd.Series(100 * np.exp(np.cumsum(steps)), index=DAYS)


def info(symbol: str, **kw: object) -> StockInfo:
    base = dict(
        symbol=symbol,
        ticker=f"{symbol}.NS",
        name=f"{symbol} Limited",
        currency="INR",
        sector="Financial Services",
        industry="Banks - Regional",
        pe=15.0,
        pb=2.0,
        debt_to_equity=None,
        revenue_growth=0.2,
        earnings_growth=0.1,
        margin=0.2,
        is_fund=False,
        source=src("Yahoo"),
    )
    return StockInfo(**{**base, **kw})


class FakeSources:
    def __init__(
        self, stocks: dict[str, StockInfo] | None = None, stories: tuple[Seen, ...] | None = ()
    ) -> None:
        self.stocks = (
            stocks
            if stocks is not None
            else {
                "HDFCBANK.NS": info("HDFCBANK", name="HDFC Bank Limited"),
                "ICICIBANK.NS": info("ICICIBANK", pe=17.0),
                "SBIN.NS": info("SBIN", pe=10.0),
                "AAPL": info(
                    "AAPL",
                    ticker="AAPL",
                    name="Apple Inc.",
                    currency="USD",
                    sector="Technology",
                    industry="Consumer Electronics",
                    debt_to_equity=78.0,
                ),
            }
        )
        self._stories = stories
        self.ipo_list = [
            IpoListing(
                "SFCTECH",
                "SFC Environmental Technologies Limited",
                "Rs.313 to Rs.330",
                "27-Oct-2026",
                "29-Oct-2026",
                "Forthcoming",
                src("NSE"),
            )
        ]

    def stock(self, ticker: str) -> StockInfo | None:
        return self.stocks.get(ticker)

    def closes(self, ticker: str, period: str = "15y") -> Closes | None:
        return Closes(walk(0.08 + 0.01 * (len(ticker) % 5), len(ticker)), src(f"Yahoo:{ticker}"))

    def fund_search(self, query: str) -> list[tuple[int, str]]:
        return [(120716, "UTI Nifty 50 Index Fund - Direct Plan - Growth")]

    def fund_navs(self, code: int) -> tuple[str, Closes] | None:
        return f"Fund {code} - Direct Plan - Growth", Closes(walk(0.1, code % 97), src("mfapi"))

    def ipos(self) -> list[IpoListing]:
        return self.ipo_list

    def ipo_detail(self, symbol: str) -> IpoDetail | None:
        return IpoDetail("Fresh issue of Rs. 1500 million and OFS", None, None, src("NSE"))

    def stories(self, since: dt.datetime) -> Stories | None:
        if self._stories is None:
            return None
        return Stories(self._stories, src("Networth watcher"))


def seen(title: str, day: str = "2026-10-20", type_: str | None = None) -> Seen:
    return Seen(title, (title,), dt.date.fromisoformat(day), ("reuters.com", "mint.com"), type_)


def without(s: StockInfo, **kw: object) -> StockInfo:
    return dataclasses.replace(s, **kw)
