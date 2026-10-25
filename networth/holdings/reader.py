"""A holdings screenshot in, a list of holdings out, validated at this boundary.

    holdings = read_screenshot(image_bytes, "en", reader=models, user_id="tg:42")

The image is passed to the vision model and nowhere else: not to disk, not to a log. A row the
model read but that can't be trusted (no units, no cost, a second currency) is moved to
`unread` with the reason, so the confirm prompt says what was missed instead of guessing.
"""

from __future__ import annotations

import datetime as dt
from typing import Final, Protocol

from networth.holdings.model import Holding, Holdings, Kind, PriceFrom, Source, placed
from networth.llm import WireHolding, WireHoldings

CURRENCIES: Final = ("INR", "USD")
MAGIC: Final = ((b"\x89PNG", "image/png"), (b"\xff\xd8", "image/jpeg"), (b"RIFF", "image/webp"))
NOT_READ: Final = "the screenshot could not be read"


class HoldingsReader(Protocol):
    def read_holdings(self, image: bytes, mime: str, lang: str) -> WireHoldings | None: ...


def mime_of(image: bytes) -> str:
    return next((mime for magic, mime in MAGIC if image.startswith(magic)), "image/jpeg")


def _date(text: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(text) if text else None
    except ValueError:
        return None


def parse_row(row: WireHolding) -> Holding | str:
    """A Holding, or why the row is left out. Average cost comes from the invested total when
    only that is printed; the current price from the row's value when only that is printed."""
    name = row.name.strip()
    if not name:
        return "a row with no name"
    if row.currency not in CURRENCIES:
        return f"{name}: no ₹ or $ amount"
    if row.units <= 0:
        return f"{name}: no units shown"
    avg_cost = row.avg_cost if row.avg_cost > 0 else row.invested / row.units
    if avg_cost <= 0:
        return f"{name}: no buy cost shown"
    price = row.current_price if row.current_price > 0 else row.current_value / row.units
    try:
        kind = Kind(row.kind)
    except ValueError:
        kind = Kind.OTHER
    return placed(Holding(
        name=name, units=row.units, avg_cost=round(avg_cost, 4), currency=row.currency,
        kind=kind, identifier=row.identifier.strip() or None, bought_on=_date(row.bought_on),
        price=round(price, 4) if price > 0 else None,
        price_from=PriceFrom.SCREENSHOT if price > 0 else PriceFrom.NONE,
    ))  # fmt: skip


def read_screenshot(
    image_bytes: bytes,
    lang: str,
    *,
    reader: HoldingsReader,
    user_id: str = "",
    now: dt.datetime | None = None,
) -> Holdings:
    """What was read, unconfirmed, plus a list of what wasn't. Rows in a second currency are
    left out: one report is in one currency."""
    wire = reader.read_holdings(image_bytes, mime_of(image_bytes), lang)
    as_of = now or dt.datetime.now(dt.UTC)
    if wire is None:
        return Holdings(user_id, Source.SCREENSHOT, as_of, (), unread=(NOT_READ,))
    parsed = [parse_row(r) for r in wire.rows]
    rows = [h for h in parsed if isinstance(h, Holding)]
    unread = [*(s.strip() for s in wire.unread if s.strip()), *(p for p in parsed
              if isinstance(p, str))]  # fmt: skip
    if rows:
        main = max(CURRENCIES, key=lambda c: sum(h.currency == c for h in rows))
        unread += [f"{h.name}: in {h.currency}, not {main}" for h in rows if h.currency != main]
        rows = [h for h in rows if h.currency == main]
    return Holdings(user_id, Source.SCREENSHOT, as_of, tuple(rows), unread=tuple(unread))
