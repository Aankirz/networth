"""What a list of holdings adds up to, and how a confirmed one sits next to the saved plan.
Pure; no IO.

    s = summarize(holdings)        # value, invested, gain, each holding's rupees and share
    short_money(291000, "INR", "en")   # "₹2.91 lakh"

Every number comes from the stored list: units times the screenshot's price, units times the
average cost. A holding the screenshot shows no price for has no value here, never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from networth.holdings.model import Holding, Holdings, Kind
from networth.holdings.returns import invested
from networth.sim import rupees
from networth.web.fmt import western_grouping

LAKH: Final = 100_000
CRORE: Final = 10_000_000
MILLION: Final = 1_000_000
BIG_WORDS: Final = {
    "en": ("lakh", "crore"),
    "hi": ("लाख", "करोड़"),
    "hinglish": ("lakh", "crore"),
}


@dataclass(frozen=True)
class Item:
    n: int  # the line number in the stored list, which the fix buttons carry
    name: str
    kind: Kind
    value: int | None  # None when the screenshot shows no price
    share: int | None  # whole percent of the priced total; 0 means under 1%


@dataclass(frozen=True)
class Summary:
    currency: str
    count: int
    items: tuple[Item, ...]  # the biggest first; holdings with no price last
    value: int  # priced holdings only
    invested: int  # every holding
    gain: int | None  # None unless every holding is priced
    gain_pct: int | None
    unpriced: int
    shares: int  # single company shares
    listed: int
    more_below: bool


def _value(h: Holding) -> float | None:
    return h.units * h.price if h.price else None


def _share(value: float | None, total: float) -> int | None:
    if value is None or total <= 0:
        return None
    pct = 100 * value / total
    return round(pct) if pct >= 1 else 0


def _rounded(value: float | None) -> int | None:
    return None if value is None else round(value)


def summarize(h: Holdings) -> Summary:
    """Totals are summed before rounding, so they match the app's own printed totals."""
    values = [_value(x) for x in h.items]
    exact = sum(v for v in values if v is not None)
    cost = sum(invested(x) for x in h.items)
    pairs = enumerate(zip(h.items, values, strict=True), start=1)
    items = tuple(Item(n, x.name, x.kind, _rounded(v), _share(v, exact)) for n, (x, v) in pairs)
    ordered = tuple(sorted(items, key=lambda i: -1 if i.value is None else i.value, reverse=True))
    unpriced = sum(v is None for v in values)
    total = round(exact)
    gain = round(exact - cost) if unpriced == 0 else None
    cost = round(cost)
    pct = round(100 * gain / cost) if gain is not None and cost > 0 else None
    return Summary(h.currency, len(items), ordered, total, cost, gain, pct, unpriced,
                   sum(x.kind is Kind.STOCK for x in h.items), h.listed, h.more_below)  # fmt: skip


def short_money(n: int, currency: str, lang: str = "en") -> str:
    """₹2.91 lakh, ₹1.2 crore or ₹68,640, as a person says it; $12,345 or $1.2M for dollars."""
    n = abs(n)
    if currency != "INR":
        return (
            f"${f'{n / MILLION:.1f}'.rstrip('0').rstrip('.')}M"
            if n >= MILLION
            else (f"${western_grouping(n)}")
        )
    lakh, crore = BIG_WORDS.get(lang, BIG_WORDS["en"])
    for size, word in ((CRORE, crore), (LAKH, lakh)):
        if n >= size:
            return f"₹{f'{n / size:.2f}'.rstrip('0').rstrip('.')} {word}"
    return rupees(n)
