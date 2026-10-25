"""Current prices from our own source, replacing the screenshot's or the broker's when they
resolve.

    priced = price_holdings(holdings, YahooPrices())   # pure apart from the lookups

Only a holding with an identifier (a ticker) is looked up. An Indian ticker tries NSE, then
BSE. A lookup that fails, times out or comes back in another currency leaves the holding's
own price in place; it never stops the report. Warnings name the error type only, never the
holding.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import warnings
from typing import Final, Protocol

from networth.holdings.model import Holding, Holdings, PriceFrom
from networth.net import call_with_deadline

log = logging.getLogger(__name__)

QUOTE_DEADLINE_S: Final = 20.0
HISTORY_PERIOD: Final = "5d"
INDIAN_EXCHANGES: Final = (".NS", ".BO")


class Prices(Protocol):
    def quote(self, symbol: str) -> tuple[float, str] | None:
        """(last close, its currency), or None when the symbol has no price."""
        ...


class YahooPrices:
    """The same yfinance path networth.sim.data uses, one short history per symbol."""

    def quote(self, symbol: str) -> tuple[float, str] | None:
        import yfinance as yf

        def fetch() -> tuple[float, str] | None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # yfinance trips pandas deprecation warnings
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=HISTORY_PERIOD, auto_adjust=False)
                if hist is None or hist.empty or "Close" not in hist:
                    return None
                closes = hist["Close"].dropna()
                currency = (ticker.history_metadata or {}).get("currency")
                if closes.empty or not currency:
                    return None
                return float(closes.iloc[-1]), str(currency).upper()

        return call_with_deadline(fetch, QUOTE_DEADLINE_S, "Yahoo quote")


def symbols(h: Holding) -> tuple[str, ...]:
    if h.identifier is None:
        return ()
    ticker = h.identifier.strip().upper()
    if h.currency == "INR" and "." not in ticker:
        return tuple(ticker + suffix for suffix in INDIAN_EXCHANGES)
    return (ticker,)


def _looked_up(h: Holding, prices: Prices) -> float | None:
    for symbol in symbols(h):
        try:
            quote = prices.quote(symbol)
        except Exception as exc:  # noqa: BLE001 - a failed lookup keeps the holding's own price
            log.warning("price lookup failed: %s", type(exc).__name__)
            continue
        if quote is not None and quote[0] > 0 and quote[1] == h.currency:
            return quote[0]
    return None


def price_holdings(holdings: Holdings, prices: Prices, now: dt.datetime | None = None) -> Holdings:
    """Every holding that resolves gets our price and LOOKED_UP; as_of moves to `now` when any
    did, since that is the date the report's values are for."""
    items = []
    for h in holdings.items:
        price = _looked_up(h, prices)
        items.append(h if price is None else dataclasses.replace(
            h, price=round(price, 4), price_from=PriceFrom.LOOKED_UP))  # fmt: skip
    if all(a is b for a, b in zip(items, holdings.items, strict=True)):
        return holdings
    as_of = now or dt.datetime.now(dt.UTC)
    return dataclasses.replace(holdings, items=tuple(items), as_of=as_of)
