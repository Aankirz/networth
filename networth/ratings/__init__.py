"""Rate a stock, a mutual fund, an ETF or an upcoming IPO.

    r = rate("HDFCBANK")                       # Rating: view, score, drivers, track record
    r = rate("Parag Parikh Flexi Cap", "fund")
    r = rate("AAPL")                           # a US share: dollars, against the S&P 500

The score is the weighted mean of the drivers that have data. A driver without data is never
filled in: it goes in Rating.missing, and the share of weight it carried lowers the confidence.
The track line is the measured hit rate of the rating's view band (networth.ratings.track).
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Final

from networth.ratings import kinds, track
from networth.ratings.kinds import Rated
from networth.ratings.model import (
    Driver,
    Kind,
    Rating,
    Source,
    Track,
    View,
    rating_json,
    slug_for,
    view_for,
)
from networth.ratings.sources import LiveSources, Sources

__all__ = ["Driver", "Kind", "Rating", "Source", "Track", "View", "rate", "rating_json", "slug_for"]

FUND_CODE: Final = re.compile(r"^MF(\d+)$", re.I)
HIGH, MEDIUM = 0.85, 0.6
DEFAULT_WATCHER_DB: Final = Path(__file__).resolve().parents[2] / "data" / "watcher.sqlite"


def rate(
    query: str,
    kind: Kind | None = None,
    *,
    now: dt.datetime | None = None,
    sources: Sources | None = None,
    table: dict | None = None,
) -> Rating:
    """query is a ticker ("HDFCBANK", "AAPL", "NIFTYBEES"), a fund's name or "MF<scheme code>",
    or an upcoming IPO's NSE symbol or name. kind is guessed when None. sources is the data
    bundle (tests pass fakes); None means the live free ones. table is the backtest table;
    None reads the stored one. Raises LookupError when nothing by that name can be found."""
    now = now or dt.datetime.now(dt.UTC)
    src = sources or LiveSources(DEFAULT_WATCHER_DB)
    rated = resolve(query.strip(), kind, src, now)
    if rated is None:
        raise LookupError(query)
    return assemble(query, rated, now, track.load() if table is None else table)


def resolve(q: str, kind: Kind | None, src: Sources, now: dt.datetime) -> Rated | None:
    if not q:
        return None
    code = FUND_CODE.match(q)
    if code and kind in (None, "fund"):
        return kinds.rate_fund(int(code.group(1)), src)
    if kind in (None, "ipo"):
        listing = find_ipo(q, src)
        if listing is not None:
            return kinds.rate_ipo(listing, src)
    if kind in (None, "stock", "etf"):
        tickers = (q.upper(),) if "." in q else (f"{q.upper()}.NS", q.upper())
        for t in tickers if " " not in q else ():
            info = src.stock(t)
            if info is not None:
                return (
                    kinds.rate_etf(info, src) if info.is_fund else kinds.rate_stock(info, src, now)
                )
    if kind in (None, "fund"):
        code_found = find_fund(q, src)
        if code_found is not None:
            return kinds.rate_fund(code_found, src)
    return None


def find_ipo(q: str, src: Sources):  # noqa: ANN201 - IpoListing | None
    try:
        listings = src.ipos()
    except Exception:  # noqa: BLE001 - NSE down means no IPO match; the other kinds still try
        return None
    folded = q.casefold()
    return next(
        (
            x
            for x in listings
            if x.symbol.casefold() == folded or (len(folded) > 3 and folded in x.name.casefold())
        ),
        None,
    )


def find_fund(q: str, src: Sources) -> int | None:
    try:
        found = src.fund_search(q)
    except Exception:  # noqa: BLE001 - mfapi down means no fund match
        return None
    plain = [
        (c, n)
        for c, n in found
        if re.search(r"direct", n, re.I)
        and re.search(r"growth", n, re.I)
        and not re.search(r"idcw|dividend", n, re.I)
    ]
    picked = plain or found
    return picked[0][0] if picked else None


def confidence(rated: Rated) -> str:
    have = sum(d.weight for d in rated.drivers)
    lost = sum(rated.weights.get(m.key, 0.0) for m in rated.missing)
    share = have / (have + lost) if have + lost else 0.0
    return "high" if share >= HIGH else "medium" if share >= MEDIUM else "low"


def lower(label: str) -> str:
    return label[0].lower() + label[1:]


def outlook(name: str, view: View, drivers: tuple[Driver, ...], conf: str, missing: int) -> str:
    ups = [lower(d.label) for d in sorted(drivers, key=lambda d: -d.score) if d.effect == "up"]
    downs = [lower(d.label) for d in sorted(drivers, key=lambda d: d.score) if d.effect == "down"]
    parts = [f"Over the next 12 months we see {name} as {view.value}"]
    if ups:
        parts.append(f"helped by {' and '.join(ups[:2])}")
    if downs:
        parts.append(f"held back by {' and '.join(downs[:2])}")
    gap = f" ({missing} input{'' if missing == 1 else 's'} missing)" if missing else ""
    tail = f", with {conf} confidence{gap}"
    return ", ".join(parts) + tail + "."


def assemble(query: str, rated: Rated, now: dt.datetime, table: dict | None) -> Rating:
    total = sum(d.weight for d in rated.drivers)
    score = round(sum(d.score * d.weight for d in rated.drivers) / total) if total else 50
    view = view_for(score)
    conf = "low" if not rated.drivers else confidence(rated)
    return Rating(
        query,
        rated.name,
        rated.symbol,
        rated.kind,
        view,
        score,
        conf,
        outlook(kinds.short_name(rated.name), view, rated.drivers, conf, len(rated.missing)),
        rated.drivers,
        tuple(m.sentence for m in rated.missing),
        track.track_line(table, rated.kind, view, rated.market),
        now.isoformat(timespec="seconds"),
        rated.currency,
    )
