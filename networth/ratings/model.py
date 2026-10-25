"""What a rating is. Pure data, no IO.

    Rating(view=View.POSITIVE, score=64, drivers=(Driver(...), ...), track=Track(...), ...)

Every Driver carries the Source its number came from and the time it was read. A driver whose
data is missing is never built: its name goes in Rating.missing and the confidence drops.
"""

from __future__ import annotations

import enum
import re
from dataclasses import asdict, dataclass
from typing import Final, Literal

Kind = Literal["stock", "fund", "etf", "ipo"]
Effect = Literal["up", "down", "flat"]
Confidence = Literal["high", "medium", "low"]


class View(enum.StrEnum):
    STRONG = "Strong"
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    WEAK = "Weak"
    AVOID = "Avoid"


# Score bands, fixed before the backtest was run (2026-10-25). Changing one is a method change.
BANDS: Final = ((75, View.STRONG), (60, View.POSITIVE), (45, View.NEUTRAL), (30, View.WEAK))


def view_for(score: int) -> View:
    return next((v for floor, v in BANDS if score >= floor), View.AVOID)


@dataclass(frozen=True)
class Source:
    name: str  # "Yahoo Finance", "mfapi.in", "NSE", "Networth watcher"
    url: str
    as_of: str  # ISO time the number was read, or the date it is for


@dataclass(frozen=True)
class Driver:
    key: str  # "growth", "valuation", "debt", "momentum", "news", "sector", ...
    label: str  # "Growth", "Valuation against peers", ...
    value: str  # the sourced number, formatted: "Revenue +18% a year"
    score: float  # 0 to 100, this driver's part of the score
    weight: float
    source: Source

    @property
    def effect(self) -> Effect:
        return "up" if self.score >= 60 else "down" if self.score < 40 else "flat"


@dataclass(frozen=True)
class Track:
    """How often ratings in this band beat the Nifty 50 over the next 12 months."""

    text: str  # "Ratings like this beat the Nifty 6 times in 10 since 2015."
    hits: int
    n: int
    since: str  # "2015"
    edge: str  # "+4 points over all stocks' 52%", the honest comparison
    weak: bool  # True when the measured edge is too small or the sample too thin


@dataclass(frozen=True)
class Rating:
    query: str  # what was asked
    name: str
    symbol: str
    kind: Kind
    view: View
    score: int  # out of 100
    confidence: Confidence
    outlook: str  # one sentence, 12 months
    drivers: tuple[Driver, ...]
    missing: tuple[str, ...]  # drivers we had no data for, said plainly
    track: Track
    as_of: str
    currency: str = "INR"  # "INR" or "USD": the market it trades in, and how money is written

    @property
    def slug(self) -> str:
        return slug_for(self.symbol)


def money(n: float, currency: str) -> str:
    """The one place a rating writes an amount."""
    # ponytail: the pages' own formatter until 13A's shared money() lands; swap the import then.
    from networth.web.fmt import money as fmt_money

    return fmt_money(round(n), currency, signed=False)


def slug_for(symbol: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", symbol.lower()).strip("-")


def rating_json(r: Rating, public_url: str | None = None) -> dict:
    """The contract's RatingCard."""
    drivers = [
        {
            "key": d.key,
            "label": d.label,
            "value": d.value,
            "effect": d.effect,
            "source": asdict(d.source),
        }
        for d in r.drivers
    ]
    return {
        "type": "rating",
        "slug": r.slug,
        "name": r.name,
        "kind": r.kind,
        "view": r.view.value,
        "score": r.score,
        "confidence": r.confidence,
        "outlook": r.outlook,
        "drivers": drivers,
        "missing": list(r.missing),
        "track": asdict(r.track),
        "as_of": r.as_of,
        "url": f"{public_url or ''}/r/{r.slug}",
        "currency": r.currency,
    }
