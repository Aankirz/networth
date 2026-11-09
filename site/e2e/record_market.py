"""Record the site's market fixtures from real Yahoo Finance closes through Phase 13A's code.

    uv run python site/e2e/record_market.py

The price, position, history and compare answers come from networth.chat.markets itself, the
same functions the chat runs, so their words and cards are what the server sends. Two things have
no 13A builder yet, so this writes them in the contract's shape with 13A's own formatters:

- the market strip (the site's proposed /api/.../market route);
- market_today, whose tiles are real closes but whose reasons are the confirmed stories in the
  test world's demo-dashboard.json, since this machine has no watcher database.

Once 13A builds those, record its JSON instead.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from pathlib import Path

import networth.web.routes  # noqa: F401, I001 - loads the web package in the order the app does
from networth import market
from networth.chat import markets
from networth.chat.answer import Answer
from networth.market import Found
from networth.web.api import demo_profile

OUT = Path(__file__).parent / "fixtures"
STRIP = {"in": ("^NSEI", "^BSESN", "^NSEBANK", "^GSPC"), "us": ("^GSPC", "^IXIC", "^DJI", "^NSEI")}
TODAY = ("^NSEI", "^BSESN", "^NSEBANK", "^NSEMDCP50", "NIFTYSMLCAP250.NS")
SPARK_DAYS = 30
MAX_REASONS = 4
TCS = Found("TCS.NS", "Tata Consultancy Services")
PROFILE, _ = demo_profile("2026-10-25T00:00:00+00:00")


def turn(intent: str, answer: Answer) -> dict:
    words = answer.template
    message = {"title": "", "body": [{"kind": "text", "text": words}], "detail": [],
               "footer": "", "preview": None}  # fmt: skip
    return {"trace_id": uuid.uuid4().hex, "intent": intent, "message": message,
            "text": words, "card": dict(answer.card or {"type": "text"})}  # fmt: skip


def index_tile(symbol: str) -> tuple[dict, market.Quote]:
    q = market.quote(symbol)
    assert q, symbol
    return {
        "symbol": q.symbol, "name": q.name,
        "level": markets.unit_price(q.price, q.currency, is_index=True),
        "change": markets.unit_price(q.change, q.currency, is_index=True),
        "change_pct": markets.pct(q.change_pct), "direction": markets.direction(q.change),
    }, q  # fmt: skip


def strip_tile(symbol: str) -> dict:
    tile, q = index_tile(symbol)
    closes = q.closes.iloc[-SPARK_DAYS:]
    return {**tile, "series": markets.series(q.name, f"last {SPARK_DAYS} closes", closes),
            "source": markets.source(q.symbol, markets.close_of(q.day))}  # fmt: skip


def market_today() -> dict:
    tiles, quotes = zip(*(index_tile(s) for s in TODAY), strict=True)
    news = json.loads((OUT / "demo-dashboard.json").read_text(encoding="utf-8"))["news"]["items"]
    reasons = [{"text": n["title"], "publishers": n["publishers"]} for n in news
               if not n["title"].startswith("Sample")][:MAX_REASONS]  # fmt: skip
    day = markets.day_words(quotes[0].day)
    moves = "; ".join(f"{t['name']} {t['change_pct']}" for t in tiles)
    words = f"At the close of {day}: {moves}."
    source = markets.source(quotes[0].symbol, markets.close_of(quotes[0].day))
    card = {"type": "market_today", "day": day, "tiles": list(tiles), "reasons": reasons,
            "source": source}  # fmt: skip
    return turn("what_happened_today", Answer.fixed({"en": words}, card=card))


def write(name: str, body: dict) -> None:
    text = json.dumps(body, indent=2, ensure_ascii=False) + "\n"
    (OUT / f"{name}.json").write_text(text, encoding="utf-8")


def found(*pairs: tuple[str, str]) -> Sequence[Found]:
    return [Found(s, n) for s, n in pairs]


if __name__ == "__main__":
    for m, symbols in STRIP.items():
        write(f"market-{m}", {"tiles": [strip_tile(s) for s in symbols]})
    apple = found(("AAPL", "Apple Inc."))
    write("answer-price-inr", turn("price", markets.price([TCS], PROFILE, "en")))
    write("answer-price-usd", turn("price", markets.price(apple, PROFILE, "en")))
    holding = "I hold 12 shares of TCS at an average of 3420"
    write("answer-position", turn("position", markets.position([TCS], holding, PROFILE, "en")))
    ten = "How has Nifty 50 done over the last 10 years?"
    nifty = found(("^NSEI", "Nifty 50"))
    write("answer-history", turn("price_history", markets.price_history(nifty, ten, PROFILE, "en")))
    versus = "TCS vs Infosys over the last 3 years"
    pair = found(("TCS.NS", "Tata Consultancy Services"), ("INFY.NS", "Infosys"))
    write("answer-compare", turn("compare", markets.compare(pair, versus, PROFILE, "en")))
    write("answer-market-today", market_today())
