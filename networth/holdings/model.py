"""What a user already owns, as read from a screenshot or a broker, and which bucket each holding
sits in.

    h = Holding("Nippon India Nifty 50 BeES", 12.0, 245.5, currency="INR", kind=Kind.ETF)
    bucket_for(h.name, h.kind)                 # Bucket.CORE, from the BUCKET_RULES table
    holdings = Holdings("tg:42", Source.SCREENSHOT, as_of, (h,), confirmed=False)

The bucket table is the only place a holding gets a bucket. A holding it can't place keeps
bucket None, and the user is asked; nothing here guesses.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class Bucket(StrEnum):
    SAFETY = "safety"
    CORE = "core"
    GROWTH = "growth"


BUCKETS: Final = (Bucket.SAFETY, Bucket.CORE, Bucket.GROWTH)


class Kind(StrEnum):
    """What the instrument is, as the screenshot or the broker labels it."""

    STOCK = "stock"
    MUTUAL_FUND = "mutual_fund"
    ETF = "etf"
    FD = "fd"
    BOND = "bond"
    OTHER = "other"


class Source(StrEnum):
    SCREENSHOT = "screenshot"
    SNAPTRADE = "snaptrade"


class PriceFrom(StrEnum):
    LOOKED_UP = "looked_up"  # our own price source, at as_of
    SCREENSHOT = "screenshot"  # the number the user's screenshot showed
    BROKER = "broker"  # the price SnapTrade returned
    NONE = "none"  # no current price: the holding is valued at what it cost


@dataclass(frozen=True)
class Holding:
    name: str
    units: float
    avg_cost: float  # per unit, in currency
    currency: str  # "INR" or "USD"
    kind: Kind = Kind.OTHER
    identifier: str | None = None  # a ticker or ISIN, only when the source showed one
    bought_on: dt.date | None = None
    price: float | None = None  # current price per unit
    price_from: PriceFrom = PriceFrom.NONE
    bucket: Bucket | None = None  # None until the table or the user places it


@dataclass(frozen=True)
class Holdings:
    user_id: str
    source: Source
    as_of: dt.datetime
    items: tuple[Holding, ...]
    confirmed: bool = False
    unread: tuple[str, ...] = ()  # what the reader saw but could not read, in its words
    currency: str = field(init=False)

    def __post_init__(self) -> None:
        currencies = {h.currency for h in self.items}
        if len(currencies) > 1:
            raise ValueError(f"holdings in more than one currency: {sorted(currencies)}")
        default = "USD" if self.source is Source.SNAPTRADE else "INR"  # SnapTrade is US brokers
        object.__setattr__(self, "currency", currencies.pop() if currencies else default)

    @property
    def unplaced(self) -> tuple[int, ...]:
        """1-based line numbers whose bucket the user still has to say."""
        return tuple(i for i, h in enumerate(self.items, start=1) if h.bucket is None)


SECTOR: Final = (
    r"bank|banking|financial services|pharma|healthcare|technology|tech|infra\w*|psu|energy|"
    r"auto|fmcg|consumption|realty|metal|defen[cs]e|manufacturing|semiconductor"
)
# Checked in order on the lower-cased name; the first match places the holding. Debt words come
# before sector words so "Banking & PSU Debt Fund" is safety, not a banking sector fund.
BUCKET_RULES: Final[tuple[tuple[re.Pattern[str], Bucket], ...]] = tuple(
    (re.compile(rf"\b({pattern})\b"), bucket)
    for pattern, bucket in (
        (r"liquid|overnight|money market|gilt|debt|bond|treasury|t-bill|fixed deposit|"
         r"ultra short|short duration|savings", Bucket.SAFETY),
        (SECTOR, Bucket.GROWTH),
        (r"small ?cap|mid ?cap|midcap|smallcap", Bucket.GROWTH),
        (r"nifty 50|nifty next 50|nifty 100|sensex|s&p 500|total (stock )?market|"
         r"index|bees|etf", Bucket.CORE),
    )
)  # fmt: skip
# A name no rule matched falls back on the kind. A mutual fund the rules can't place (an
# active flexi-cap fund, say) stays unplaced, and so does anything "other".
KIND_BUCKETS: Final[Mapping[Kind, Bucket]] = {
    Kind.STOCK: Bucket.GROWTH,
    Kind.ETF: Bucket.CORE,
    Kind.FD: Bucket.SAFETY,
    Kind.BOND: Bucket.SAFETY,
}


def bucket_for(name: str, kind: Kind) -> Bucket | None:
    """A single stock is growth whatever its name says: "HDFC Bank" is a stock, not a fund."""
    if kind is Kind.STOCK:
        return Bucket.GROWTH
    lowered = name.lower()
    for pattern, bucket in BUCKET_RULES:
        if pattern.search(lowered):
            return bucket
    return KIND_BUCKETS.get(kind)


def placed(h: Holding) -> Holding:
    """h with the table's bucket, unless the user already said one."""
    return h if h.bucket is not None else dataclasses.replace(h, bucket=bucket_for(h.name, h.kind))


def to_json(holdings: Holdings) -> str:
    def item(h: Holding) -> dict:
        row = dataclasses.asdict(h)
        row["bought_on"] = h.bought_on.isoformat() if h.bought_on else None
        return row

    return json.dumps({
        "user_id": holdings.user_id, "source": holdings.source.value,
        "as_of": holdings.as_of.isoformat(), "confirmed": holdings.confirmed,
        "unread": list(holdings.unread), "items": [item(h) for h in holdings.items],
    }, ensure_ascii=False)  # fmt: skip


def from_json(text: str) -> Holdings:
    raw = json.loads(text)
    items = tuple(
        Holding(
            name=r["name"],
            units=r["units"],
            avg_cost=r["avg_cost"],
            currency=r["currency"],
            kind=Kind(r["kind"]),
            identifier=r["identifier"],
            bought_on=dt.date.fromisoformat(r["bought_on"]) if r["bought_on"] else None,
            price=r["price"],
            price_from=PriceFrom(r["price_from"]),
            bucket=Bucket(r["bucket"]) if r["bucket"] else None,
        )  # fmt: skip
        for r in raw["items"]
    )
    return Holdings(raw["user_id"], Source(raw["source"]), dt.datetime.fromisoformat(raw["as_of"]),
                    items, raw["confirmed"], tuple(raw["unread"]))  # fmt: skip
