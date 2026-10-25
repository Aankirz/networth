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
    r"auto|fmcg|consumption|realty|metal|defen[cs]e|manufacturing|semiconductor|nifty it"
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
# An NSE ETF ticker ("BANKBEES", "LIQUIDBEES", "GILT5YBEES") is one run of capitals, so the
# word rules above never see "bank" or "liquid" in it. These read the ticker, in the same order:
# debt first, then a sector, then a broad index. An ISIN is not a ticker and is never read.
# Only an INR holding is read this way: the patterns are NSE ticker names.
TICKER_RULES: Final[tuple[tuple[re.Pattern[str], Bucket], ...]] = tuple(
    (re.compile(pattern), bucket)
    for pattern, bucket in (
        (r"LIQUID|GILT|GSEC|SDL|EBBETF|BBETF|OVERNIGHT|MONEY", Bucket.SAFETY),
        (r"BANK|BNK|BK|PHARMA|HEALTH|INFRA|PSU|CPSE|FMCG|CONSUM|AUTO|METAL|ENERGY|REALTY|^IT"
         r"|MIDCAP|MID150|SMALLCAP|SMLCAP", Bucket.GROWTH),
        (r"NIFTY|NIF50|SENSEX|JUNIOR|BEES|ETF", Bucket.CORE),
    )
)  # fmt: skip
TICKER: Final = re.compile(r"[A-Z0-9&-]{3,20}")
ISIN: Final = re.compile(r"[A-Z]{2}[A-Z0-9]{9}\d")
# A name no rule matched falls back on the kind. A mutual fund the rules can't place (an
# active flexi-cap fund, say) stays unplaced, and so does anything "other".
KIND_BUCKETS: Final[Mapping[Kind, Bucket]] = {
    Kind.STOCK: Bucket.GROWTH,
    Kind.ETF: Bucket.CORE,
    Kind.FD: Bucket.SAFETY,
    Kind.BOND: Bucket.SAFETY,
}


def ticker_of(name: str, identifier: str | None) -> str | None:
    """The ETF's exchange ticker: the identifier, or a name that is only a ticker."""
    for text in (identifier, name):
        token = (text or "").strip().upper()
        if TICKER.fullmatch(token) and not ISIN.fullmatch(token):
            return token
    return None


def bucket_for(name: str, kind: Kind, identifier: str | None = None,
               currency: str = "INR") -> Bucket | None:  # fmt: skip
    """A single stock is growth whatever its name says: "HDFC Bank" is a stock, not a fund. An
    Indian ETF's ticker is read first, since a screenshot may show only "BANKBEES". The ticker
    rules are NSE names: a US ticker such as ITOT is placed by its name, as before."""
    if kind is Kind.STOCK:
        return Bucket.GROWTH
    ticker = ticker_of(name, identifier) if kind is Kind.ETF and currency == "INR" else None
    for pattern, bucket in TICKER_RULES if ticker else ():
        if pattern.search(ticker):
            return bucket
    lowered = name.lower()
    for pattern, bucket in BUCKET_RULES:
        if pattern.search(lowered):
            return bucket
    return KIND_BUCKETS.get(kind)


def placed(h: Holding) -> Holding:
    """h with the table's bucket, unless the user already said one."""
    if h.bucket is not None:
        return h
    return dataclasses.replace(h, bucket=bucket_for(h.name, h.kind, h.identifier, h.currency))


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
