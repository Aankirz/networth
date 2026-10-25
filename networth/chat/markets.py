"""Market answers: a price, a stretch of history, a holding typed as text, a comparison, and
Networth's read on a stock. Each leads with the number asked for, says its source and date, and
carries the typed card the site draws (docs/phases/phase-10-contract.md).

    routed = route(text, currency)           # (Intent, Found...) for a market question, or None
    answer = price(found, profile, lang)     # an Answer with .card set

Code writes every sentence from the source's numbers, so no number is ever guessed. A Hindi or
Hinglish reader gets the same facts reworded by the writer under the guard. When the source has
nothing, the answer says so plainly and carries a text card.
"""

from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

import pandas as pd

from networth import market
from networth.app.store import Profile
from networth.chat.answer import Answer
from networth.market import Fall, Found, History, Quote
from networth.money import MINUS, indian_grouping, money

MAX_POINTS: Final = 260  # about a year of trading days; longer series are thinned evenly
DEFAULT_YEARS: Final = 5
RATING_DEADLINE_S: Final = 3.0
NEAR_LOW: Final = 0.10  # within 10% of the 52-week low
NEAR_HIGH: Final = 0.05
BIG_FALL: Final = -0.20
STRONG_RISE: Final = 0.15
TRANSLATE_TASK: Final = """Rewrite the facts below as a short chat reply. Keep the first
sentence first, and keep every number, name and date exactly as written."""

# --- routing ---------------------------------------------------------------------------------

HOLDING: Final = re.compile(
    r"(?:hold|have|own|bought|got|holding|mere paas|mere pass)\s+(\d[\d,]*)\s*"
    r"(?:shares?|units?|stocks?)?\s*(?:of\s+[a-z .&]+?\s+)?"
    r"(?:at|@|for|pe|par)\s*(?:an?\s+)?(?:avg\.?|average(?: price| cost)?(?: of)?)?\s*"
    r"(?:rs\.?|₹|\$|inr|usd)?\s*(\d[\d,]*(?:\.\d+)?)",
    re.I,
)
SHARES_AT: Final = re.compile(
    r"(\d[\d,]*)\s*(?:[a-z.&]+\s+){0,3}?(?:shares?|units?)\s+"
    r"(?:of\s+[a-z .&]+?\s+)?(?:at|@)\s*(?:rs\.?|₹|\$)?\s*"
    r"(\d[\d,]*(?:\.\d+)?)",
    re.I,
)
VIEW_ASK: Final = re.compile(
    r"should i (?:buy|sell|invest|add|hold|exit|get out|keep|book)|"
    r"(?:is|how good is|how is)\b.*\b(?:good|worth|buy|investment|stock to)|"
    r"worth (?:buying|it|investing)|good (?:buy|investment|stock)|"
    r"kaisa hai|lena chahiye|le loon|lu kya|kharid|bech|खरीद|बेच|कैसा है",
    re.I,
)
HISTORY_ASK: Final = re.compile(
    r"(?:last|past|over|pichhle|pichle|पिछले)\s+\w+\s+(?:years?|yrs?|saal|साल)|"
    r"\b\d{1,2}\s*(?:years?|yrs?|saal|साल)\b|over the years|since \d{4}|long[- ]term|"
    r"how has .* (?:done|performed)|returns? (?:of|on|from)|cagr|history of",
    re.I,
)
PRICE_ASK: Final = re.compile(
    r"price|trading at|quote|kitne ka|kitna hai|kya rate|भाव|कीमत|share rate|"
    r"\bat what\b|how much is|where is .* (?:today|now)|level",
    re.I,
)
COMPARE_ASK: Final = re.compile(r"\bvs\.?\b|versus|compare|compared|better than", re.I)
MY_HOLDINGS: Final = re.compile(r"\bmy (?:holdings|portfolio|investments|funds)\b|portfolio", re.I)


@dataclass(frozen=True)
class Position:
    quantity: float
    avg_cost: float


def typed_position(text: str) -> Position | None:
    """ "I hold 390 at an average of 230", "390 shares at 230", "bought 50 @ 1,200"."""
    m = HOLDING.search(text) or SHARES_AT.search(text)
    if not m:
        return None
    qty, cost = (float(g.replace(",", "")) for g in m.groups())
    return Position(qty, cost) if qty > 0 and cost > 0 else None


@lru_cache(maxsize=256)
def _found(text: str, currency: str | None) -> tuple[Found, ...]:
    # ponytail: one lookup per question text, cached so routing and answering share it
    return market.resolve(text, currency)


def route(text: str, currency: str | None) -> tuple[str, tuple[Found, ...]] | None:
    """The market intent a question asks for, with what it names, or None for every other
    question. Cheap words first; the name lookup runs only when one of them matches."""
    if MY_HOLDINGS.search(text) and not typed_position(text):
        return None
    position = typed_position(text)
    asks = [
        ("position", position is not None),
        ("price_history", bool(HISTORY_ASK.search(text))),
        ("stock_view", bool(VIEW_ASK.search(text))),
        ("price", bool(PRICE_ASK.search(text))),
        ("compare", bool(COMPARE_ASK.search(text))),
    ]
    if not any(hit for _, hit in asks):
        return None
    found = _found(text, currency)
    if not found:
        return None
    if position is not None:
        return ("stock_view" if VIEW_ASK.search(text) else "position"), found[:1]
    if len(found) >= 2 and (COMPARE_ASK.search(text) or HISTORY_ASK.search(text)):
        return "compare", found[:4]
    for intent, hit in asks[1:]:
        if hit and intent != "compare":
            return intent, found[:1]
    return None


# --- formatting ------------------------------------------------------------------------------


def unit_price(x: float, currency: str, is_index: bool = False) -> str:
    """₹1,190.50, $372.22, or an index level as 22,600.15."""
    whole, cents = divmod(round(abs(x) * 100), 100)
    grouped = indian_grouping(whole) if currency == "INR" else f"{whole:,}"
    body = f"{grouped}.{cents:02d}"
    if not is_index:
        body = f"{'₹' if currency == 'INR' else '$' if currency == 'USD' else currency + ' '}{body}"
    return f"{MINUS}{body}" if x < 0 else body


def pct(x: float, signed: bool = True) -> str:
    text = f"{abs(x) * 100:.1f}%"
    if not signed or text == "0.0%":
        return text
    return f"{MINUS}{text}" if x < 0 else f"+{text}"


def day_words(d: dt.date) -> str:
    return f"{d.day} {d:%b %Y}"


def direction(x: float) -> str:
    return "up" if x > 0 else "down" if x < 0 else "flat"


def source(symbol: str, as_of: str) -> dict:
    return {"name": market.SOURCE_NAME, "url": market.source_url(symbol), "as_of": as_of}


def close_of(d: dt.date) -> str:
    return f"close of {day_words(d)}"


def thinned(closes: pd.Series) -> list[dict]:
    step = max(1, -(-len(closes) // MAX_POINTS))
    picked = closes.iloc[::step]
    if picked.index[-1] != closes.index[-1]:
        picked = pd.concat([picked, closes.iloc[-1:]])
    return [{"t": d.date().isoformat(), "v": round(float(v), 2)} for d, v in picked.items()]


def series(name: str, label: str, closes: pd.Series) -> dict:
    return {"name": name, "label": label, "points": thinned(closes)}


# --- cards -----------------------------------------------------------------------------------


def price_card(q: Quote) -> dict:
    return {
        "type": "price", "symbol": q.symbol, "name": q.name, "exchange": q.exchange,
        "currency": q.currency, "price": unit_price(q.price, q.currency, q.is_index),
        "change": unit_price(q.change, q.currency, q.is_index), "change_pct": pct(q.change_pct),
        "direction": direction(q.change),
        "low_52w": unit_price(q.low_52w, q.currency, q.is_index),
        "high_52w": unit_price(q.high_52w, q.currency, q.is_index),
        "series": series(q.name, "a year of daily closes", q.closes),
        "source": source(q.symbol, close_of(q.day)),
    }  # fmt: skip


def fall_row(f: Fall) -> dict:
    return {"fall": pct(-f.fall), "peak": day_words(f.peak), "trough": day_words(f.trough),
            "recovered": day_words(f.recovered) if f.recovered else None}  # fmt: skip


def history_card(h: History, years: int) -> dict:
    start, end = h.closes.index[0].date(), h.closes.index[-1].date()
    return {
        "type": "price_history", "symbol": h.symbol, "name": h.name,
        "from": day_words(start), "to": day_words(end),
        "series": series(h.name, f"daily closes, {years} years", h.closes),
        "returns": [{"label": f"{years} year{'' if years == 1 else 's'}", "value": pct(h.total)},
                    {"label": "a year, on average", "value": pct(h.per_year)}],
        "drawdowns": [fall_row(f) for f in market.drawdowns(h.closes)],
        "source": source(h.symbol, f"daily closes to {day_words(end)}"),
    }  # fmt: skip


@dataclass(frozen=True)
class Worth:
    invested: float
    value: float

    @property
    def gain(self) -> float:
        return self.value - self.invested

    @property
    def gain_pct(self) -> float:
        return self.gain / self.invested if self.invested else 0.0


def worth(q: Quote, p: Position) -> Worth:
    return Worth(p.quantity * p.avg_cost, p.quantity * q.price)


def position_card(q: Quote, p: Position) -> dict:
    w = worth(q, p)
    qty = f"{p.quantity:,.0f}" if p.quantity == int(p.quantity) else f"{p.quantity:,}"
    return {
        "type": "position", "symbol": q.symbol, "name": q.name, "quantity": qty,
        "avg_cost": unit_price(p.avg_cost, q.currency), "price": unit_price(q.price, q.currency),
        "invested": money(w.invested, q.currency), "value": money(w.value, q.currency),
        "gain": money(w.gain, q.currency, signed=True), "gain_pct": pct(w.gain_pct),
        "direction": direction(w.gain),
        "low_52w": unit_price(q.low_52w, q.currency),
        "high_52w": unit_price(q.high_52w, q.currency),
        "series": series(q.name, "a year of daily closes", q.closes),
        "source": source(q.symbol, close_of(q.day)),
    }  # fmt: skip


def compare_card(hs: Sequence[History], years: int) -> dict:
    start = max(h.closes.index[0] for h in hs)
    end = min(h.closes.index[-1] for h in hs)
    rebased = [h.closes[(h.closes.index >= start) & (h.closes.index <= end)] for h in hs]
    rebased = [s / s.iloc[0] * 100 for s in rebased]
    span = [History(h.symbol, h.name, h.currency, s) for h, s in zip(hs, rebased, strict=True)]
    worst = [market.drawdowns(h.closes, 1) for h in span]
    falls = [pct(-w[0].fall) if w else "none over 5%" for w in worst]
    rows = [
        {
            "label": f"{years} year{'' if years == 1 else 's'}",
            "values": [pct(h.total) for h in span],
        },
        {"label": "a year, on average", "values": [pct(h.per_year) for h in span]},
        {"label": "worst fall", "values": falls},
    ]
    return {
        "type": "compare", "from": day_words(start.date()), "to": day_words(end.date()),
        "series": [series(h.name, "rebased to 100", h.closes) for h in span],
        "columns": [h.name for h in span], "rows": rows,
        "source": source(hs[0].symbol, f"daily closes to {day_words(end.date())}"),
    }  # fmt: skip


# --- words -----------------------------------------------------------------------------------


def missing(found: Sequence[Found]) -> Answer:
    names = ", ".join(f.name or f.symbol for f in found) or "that"
    words = (f"I couldn't get prices for {names} from {market.SOURCE_NAME} just now, so I'm "
             "not giving a number. Asking again in a minute usually works.")  # fmt: skip
    return Answer.fixed({"en": words}, kind="market", card={"type": "text"})


def facts_answer(words: str, card: dict, lang: str, kind: str) -> Answer:
    """English as written; any other language reworded by the writer, numbers kept."""
    if lang == "en":
        return Answer.fixed({"en": words}, kind=kind, card=card)
    return Answer(words, words, TRANSLATE_TASK, kind=kind, card=card)


def price_line(q: Quote) -> str:
    move = (f"{direction(q.change)} {unit_price(abs(q.change), q.currency, q.is_index)} "
            f"({pct(q.change_pct)}) on the day")  # fmt: skip
    return (f"{q.name} closed at {unit_price(q.price, q.currency, q.is_index)} on "
            f"{day_words(q.day)}, {move}.")  # fmt: skip


def range_line(q: Quote) -> str:
    low, high = (unit_price(x, q.currency, q.is_index) for x in (q.low_52w, q.high_52w))
    from_high = q.price / q.high_52w - 1 if q.high_52w else 0.0
    return f"Its 52-week range is {low} to {high}; it is {pct(from_high, False)} below the high."


def source_line(symbol: str, d: dt.date) -> str:
    return f"Source: {market.SOURCE_NAME}, {close_of(d)} ({market.source_url(symbol)})."


def price(found: Sequence[Found], profile: Profile, lang: str) -> Answer:
    q = market.quote(found[0].symbol, name=found[0].name)
    if q is None:
        return missing(found[:1])
    words = "\n\n".join([price_line(q), range_line(q), source_line(q.symbol, q.day)])
    return facts_answer(words, price_card(q), lang, "price")


def history_words(h: History, years: int) -> str:
    start, end = h.closes.index[0].date(), h.closes.index[-1].date()
    lvl = h.symbol in market.BY_SYMBOL
    first, last = (
        unit_price(float(x), h.currency, lvl) for x in (h.closes.iloc[0], h.closes.iloc[-1])
    )
    lead = (f"{h.name} is {direction(h.total)} {pct(h.total, False)} over the last {years} "
            f"year{'' if years == 1 else 's'}, from {first} on {day_words(start)} to {last} on "
            f"{day_words(end)}: about {pct(h.per_year)} a year.")  # fmt: skip
    falls = market.drawdowns(h.closes)
    lines = [lead]
    if falls:
        f = falls[0]
        back = (f"back to its peak by {day_words(f.recovered)}" if f.recovered
                else "not back to that peak yet")  # fmt: skip
        lines.append(f"The worst fall in that time was {pct(f.fall, False)}, from "
                     f"{day_words(f.peak)} to {day_words(f.trough)}, {back}.")  # fmt: skip
    lines.append(f"Source: {market.SOURCE_NAME}, daily closes to {day_words(end)} "
                 f"({market.source_url(h.symbol)}).")  # fmt: skip
    return "\n\n".join(lines)


def price_history(found: Sequence[Found], text: str, profile: Profile, lang: str) -> Answer:
    years = market.years_asked(text) or DEFAULT_YEARS
    h = market.history(found[0].symbol, years, name=found[0].name)
    if h is None:
        return missing(found[:1])
    return facts_answer(history_words(h, years), history_card(h, years), lang, "price_history")


def position_line(q: Quote, p: Position) -> str:
    w = worth(q, p)
    qty = f"{p.quantity:,.0f}" if p.quantity == int(p.quantity) else f"{p.quantity:,}"
    gain = f"{direction(w.gain)} {money(abs(w.gain), q.currency)} ({pct(w.gain_pct)})"
    return (f"Your {qty} {q.name} shares at {unit_price(p.avg_cost, q.currency)} cost "
            f"{money(w.invested, q.currency)} and are worth {money(w.value, q.currency)} at the "
            f"{day_words(q.day)} close of {unit_price(q.price, q.currency)}: "
            f"{gain}.")  # fmt: skip


def position(found: Sequence[Found], text: str, profile: Profile, lang: str) -> Answer:
    p = typed_position(text)
    q = market.quote(found[0].symbol, name=found[0].name)
    if q is None or p is None:
        return missing(found[:1])
    move = f"On the day it moved {pct(q.change_pct)}."
    words = "\n\n".join([position_line(q, p), f"{range_line(q)} {move}",
                         source_line(q.symbol, q.day)])  # fmt: skip
    return facts_answer(words, position_card(q, p), lang, "position")


def compare(found: Sequence[Found], text: str, profile: Profile, lang: str) -> Answer:
    years = market.years_asked(text) or DEFAULT_YEARS
    hs = [market.history(f.symbol, years, name=f.name) for f in found]
    if any(h is None for h in hs):
        return missing([f for f, h in zip(found, hs, strict=True) if h is None])
    card = compare_card(hs, years)  # type: ignore[arg-type]
    totals = card["rows"][0]["values"]
    yearly = card["rows"][1]["values"]
    parts = [f"{name} {t} ({y} a year)" for name, t, y in zip(card["columns"], totals, yearly,
                                                                strict=True)]  # fmt: skip
    worst = ", ".join(f"{n} {v}" for n, v in zip(card["columns"], card["rows"][2]["values"],
                                                  strict=True))  # fmt: skip
    words = "\n\n".join([
        f"Over the last {years} year{'' if years == 1 else 's'} ({card['from']} to {card['to']}): "
        + "; ".join(parts) + ".",
        f"Worst falls in that time: {worst}.",
        f"Source: {market.SOURCE_NAME}, daily closes to {card['to']}.",
    ])  # fmt: skip
    return facts_answer(words, card, lang, "compare")


# --- Networth's read -------------------------------------------------------------------------

VIEW_LEADS: Final = {
    "Strong": "I would add to {name} now.",
    "Positive": "I would hold {name} and add on dips.",
    "Neutral": "I would hold {name}, but not add more right now.",
    "Weak": "I would not add to {name} right now.",
    "Avoid": "I would stay away from {name} for now.",
}


def rated(symbol: str):  # noqa: ANN201 - networth.ratings.Rating | None
    """Phase 13C's rating, if it answers inside the deadline; None otherwise."""
    try:
        from networth.ratings import rate
    except ImportError:
        return None
    pool = cf.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(rate, symbol.removesuffix(".NS")).result(timeout=RATING_DEADLINE_S)
    except Exception:  # noqa: BLE001 - no rating in time means the read from the facts
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def year_return(q: Quote) -> float:
    return float(q.closes.iloc[-1] / q.closes.iloc[0] - 1) if len(q.closes) > 1 else 0.0


def facts_read(q: Quote) -> tuple[str, list[str]]:
    """The lead and its reasons from price facts alone, when no rating is in."""
    yr, low_gap = year_return(q), q.price / q.low_52w - 1 if q.low_52w else 1.0
    high_gap = 1 - q.price / q.high_52w if q.high_52w else 1.0
    reasons = [f"It is {pct(yr)} over the past year and {pct(high_gap, False)} below its "
               f"52-week high."]  # fmt: skip
    if yr <= BIG_FALL and low_gap <= NEAR_LOW:
        reasons.append("It is trading near its 52-week low, and the fall has not turned yet.")
        return VIEW_LEADS["Weak"].format(name=q.name), reasons
    if yr >= STRONG_RISE and high_gap <= NEAR_HIGH:
        reasons.append("It is close to its 52-week high, so a fresh buy pays for the run-up.")
        return VIEW_LEADS["Neutral"].format(name=q.name), reasons
    if yr >= STRONG_RISE:
        return VIEW_LEADS["Positive"].format(name=q.name), reasons
    return VIEW_LEADS["Neutral"].format(name=q.name), reasons


def stock_view(found: Sequence[Found], text: str, profile: Profile, lang: str) -> Answer:
    q = market.quote(found[0].symbol, name=found[0].name)
    if q is None:
        return missing(found[:1])
    r = rated(q.symbol)
    if r is not None:
        lead = f"Networth's read: {VIEW_LEADS[str(r.view.value)].format(name=q.name)}"
        reasons = [f"Score {r.score}/100 ({r.view.value}, {r.confidence} confidence). {r.outlook}"]
        reasons += [f"{d.label}: {d.value} ({d.source.name})." for d in r.drivers[:3]]
        reasons.append(r.track.text)
    else:
        first, reasons = facts_read(q)
        lead = f"Networth's read: {first}"
    p = typed_position(text)
    lines = [lead]
    if p is not None:
        lines.append(position_line(q, p))
    lines += [price_line(q), " ".join(reasons), source_line(q.symbol, q.day)]
    card = position_card(q, p) if p is not None else price_card(q)
    return facts_answer("\n\n".join(lines), card, lang, "stock_view")
