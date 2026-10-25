"""Record the site's market fixtures from real Yahoo Finance data through networth.market.

    uv run python site/e2e/record_market.py

Every number is the source's own close on the day recorded. Phase 13A has the data layer
(networth.market) but no card builder or strip route yet, so this writes the cards the way the
contract describes them; once 13A's builders land, record their JSON instead and delete this.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd

from networth import market
from networth.money import money

OUT = Path(__file__).parent / "fixtures"
STRIP = {"in": ("^NSEI", "^BSESN", "^NSEBANK", "^GSPC"), "us": ("^GSPC", "^IXIC", "^DJI", "^NSEI")}
SPARK_DAYS = 30
MINUS = "−"
SYMBOL = {"INR": "₹", "USD": "$"}


def grouped(n: float, currency: str) -> str:
    whole, frac = f"{abs(n):.2f}".split(".")
    body = market_grouping(int(whole), currency)
    return f"{body}.{frac}"


def market_grouping(n: int, currency: str) -> str:
    from networth.money import indian_grouping

    return indian_grouping(n) if currency == "INR" else f"{n:,}"


def signed(n: float, text: str) -> str:
    return f"{MINUS}{text}" if n < 0 else f"+{text}"


def price_text(n: float, currency: str) -> str:
    return f"{SYMBOL.get(currency, currency + ' ')}{grouped(n, currency)}"


def pct(x: float) -> str:
    return signed(x, f"{abs(x) * 100:.2f}%")


def direction(x: float) -> str:
    return "up" if x > 0 else "down" if x < 0 else "flat"


def day(d) -> str:
    return pd.Timestamp(d).strftime("%-d %b %Y")


def source(q_symbol: str, as_of) -> dict:
    return {
        "name": market.SOURCE_NAME,
        "url": market.source_url(q_symbol),
        "as_of": f"last close {day(as_of)}",
    }


def series(closes: pd.Series, name: str, label: str) -> dict:
    return {
        "name": name,
        "label": label,
        "points": [
            {"t": d.strftime("%Y-%m-%d"), "v": round(float(v), 2)} for d, v in closes.items()
        ],
    }


def tile(symbol: str) -> dict:
    q = market.quote(symbol)
    assert q, symbol
    last = q.closes.iloc[-SPARK_DAYS:]
    return {
        "symbol": q.symbol,
        "name": q.name,
        "level": grouped(q.price, q.currency),
        "change": signed(q.change, grouped(abs(q.change), q.currency)),
        "change_pct": pct(q.change_pct),
        "direction": direction(q.change),
        "series": series(last, q.name, f"{q.name}, last {SPARK_DAYS} trading days"),
        "source": source(q.symbol, q.day),
    }


def turn(intent: str, words: str, card: dict) -> dict:
    message = {
        "title": "",
        "body": [{"kind": "text", "text": words}],
        "detail": [],
        "footer": "",
        "preview": None,
    }
    return {
        "trace_id": uuid.uuid4().hex,
        "intent": intent,
        "message": message,
        "text": words,
        "card": card,
    }


def price_turn(symbol: str, name: str) -> dict:
    q = market.quote(symbol, name=name)
    assert q, symbol
    words = (
        f"{q.name} closed at {price_text(q.price, q.currency)} on {day(q.day)}, "
        f"{'up' if q.change >= 0 else 'down'} {abs(q.change_pct) * 100:.2f}% on the day."
    )
    return turn(
        "price",
        words,
        {
            "type": "price",
            "symbol": q.symbol,
            "name": q.name,
            "exchange": q.exchange,
            "currency": q.currency,
            "price": price_text(q.price, q.currency),
            "change": signed(q.change, price_text(abs(q.change), q.currency)),
            "change_pct": pct(q.change_pct),
            "direction": direction(q.change),
            "low_52w": price_text(q.low_52w, q.currency),
            "high_52w": price_text(q.high_52w, q.currency),
            "series": series(q.closes, q.name, f"{q.name}, a year of daily closes"),
            "source": source(q.symbol, q.day),
        },
    )


def position_turn(symbol: str, name: str, quantity: int, avg: float) -> dict:
    q = market.quote(symbol, name=name)
    assert q, symbol
    invested, value = quantity * avg, quantity * q.price
    gain = value - invested
    words = (
        f"Your {quantity} {q.name} shares are worth {money(value, q.currency)} at the last close, "
        f"{money(gain, q.currency, signed=True)} on the {money(invested, q.currency)} you put in."
    )
    return turn(
        "position",
        words,
        {
            "type": "position",
            "symbol": q.symbol,
            "name": q.name,
            "quantity": f"{quantity:,}",
            "avg_cost": price_text(avg, q.currency),
            "price": price_text(q.price, q.currency),
            "invested": money(invested, q.currency),
            "value": money(value, q.currency),
            "gain": money(gain, q.currency, signed=True),
            "gain_pct": pct(gain / invested),
            "direction": direction(gain),
            "low_52w": price_text(q.low_52w, q.currency),
            "high_52w": price_text(q.high_52w, q.currency),
            "series": series(q.closes, q.name, f"{q.name}, a year of daily closes"),
            "source": source(q.symbol, q.day),
        },
    )


def history_turn(symbol: str, years: int) -> dict:
    h = market.history(symbol, years)
    assert h, symbol
    weekly = h.closes.resample("W-FRI").last().dropna()
    weekly.iloc[-1] = h.closes.iloc[-1]
    falls = [
        {
            "fall": pct(-f.fall).replace("+", ""),
            "peak": day(f.peak),
            "trough": day(f.trough),
            "recovered": day(f.recovered) if f.recovered else None,
        }
        for f in market.drawdowns(h.closes)
    ]
    worst = falls[0]["fall"] if falls else None
    words = (
        f"{h.name} returned {pct(h.total)} over the last {years} years, "
        f"{pct(h.per_year)} a year on average."
        + (f" Its worst fall on the way was {worst}." if worst else "")
    )
    return turn(
        "price_history",
        words,
        {
            "type": "price_history",
            "symbol": h.symbol,
            "name": h.name,
            "from": day(h.closes.index[0]),
            "to": day(h.closes.index[-1]),
            "series": series(weekly, h.name, f"{h.name}, weekly closes over {years} years"),
            "returns": [
                {"label": f"{years} years", "value": pct(h.total)},
                {"label": "a year, on average", "value": pct(h.per_year)},
            ],
            "drawdowns": falls,
            "source": source(h.symbol, h.closes.index[-1]),
        },
    )


def write(name: str, body: dict) -> None:
    (OUT / f"{name}.json").write_text(
        json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    for m, symbols in STRIP.items():
        write(f"market-{m}", {"tiles": [tile(s) for s in symbols]})
    write("answer-price-inr", price_turn("TCS.NS", "Tata Consultancy Services"))
    write("answer-price-usd", price_turn("AAPL", "Apple Inc."))
    write("answer-position", position_turn("TCS.NS", "Tata Consultancy Services", 12, 3420.0))
    write("answer-history", history_turn("^NSEI", 10))
