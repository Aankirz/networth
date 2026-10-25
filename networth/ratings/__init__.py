"""Rate a stock, a mutual fund, an ETF or an upcoming IPO.

    r = rate("HDFCBANK")                       # Rating: view, score, drivers, track record
    r = rate("Parag Parikh Flexi Cap", "fund")

The signature is the contract 13A codes against. rate() never fills in a number: a driver
without data goes in Rating.missing and lowers the confidence.
"""

from __future__ import annotations

import datetime as dt

from networth.ratings.model import (
    Driver,
    Kind,
    Rating,
    Source,
    Track,
    View,
    rating_json,
    slug_for,
)

__all__ = ["Driver", "Kind", "Rating", "Source", "Track", "View", "rate", "rating_json",
           "slug_for"]  # fmt: skip


def rate(query: str, kind: Kind | None = None, *, now: dt.datetime | None = None,
         sources: object | None = None) -> Rating:  # fmt: skip
    """query is a ticker ("HDFCBANK"), a fund or ETF name, or an IPO's name. kind is guessed
    when None. sources is the data bundle (tests pass fakes); None means the live free ones.
    Raises LookupError when nothing by that name can be found."""
    raise NotImplementedError("phase 13C: the engine lands in the next push")
