"""What a holding cost, what it is worth and how it has done, as plain numbers.

    invested(h), value(h)                     # units x average cost, units x price
    holding_return(h, today)                  # Return("xirr" | "simple" | "short", pct)
    total_return(items, today)                # XIRR over every lot, or simple when it can't be
    xirr([(day, -100.0), (later, 121.0)])     # 0.1: the yearly rate that zeroes the flows

A holding with no current price is valued at what it cost, so its gain is 0. A return is
annualised only over a year or more of known dates; anything shorter or undated stays a plain
gain over cost and says so.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from networth.holdings.model import Holding

DAYS_A_YEAR: Final = 365.0
YEAR_DAYS: Final = 365  # held at least this long before a return is called yearly
LOW_RATE: Final = -0.9999
HIGH_RATE: Final = 100.0
BISECT_STEPS: Final = 200
TOLERANCE: Final = 1e-9

ReturnKind = Literal["xirr", "simple", "short"]


@dataclass(frozen=True)
class Return:
    """xirr: a yearly rate over known dates. simple: gain over cost, no buy date. short: gain
    over cost, held under a year, not annualised. pct to one decimal, as it is shown."""

    kind: ReturnKind
    pct: float


def invested(h: Holding) -> float:
    return h.units * h.avg_cost


def value(h: Holding) -> float:
    return h.units * h.price if h.price is not None else invested(h)


def _simple(cost: float, worth: float) -> float:
    return worth / cost - 1.0 if cost > 0 else 0.0


def _pct(rate: float) -> float:
    return round(rate * 100, 1) + 0.0  # + 0.0 turns -0.0 into 0.0


def _npv(rate: float, flows: Sequence[tuple[dt.date, float]]) -> float:
    start = min(day for day, _ in flows)
    return sum(cf / (1.0 + rate) ** ((day - start).days / DAYS_A_YEAR) for day, cf in flows)


def xirr(flows: Sequence[tuple[dt.date, float]]) -> float | None:
    """The yearly rate at which the flows (money in negative, value out positive) net to zero,
    by bisection. None when no rate in the searched range does."""
    lo, hi = LOW_RATE, HIGH_RATE
    f_lo, f_hi = _npv(lo, flows), _npv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, flows)
        if abs(f_mid) < TOLERANCE or hi - lo < TOLERANCE:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def _kind(h: Holding, today: dt.date) -> ReturnKind:
    if h.bought_on is None:
        return "simple"
    return "xirr" if (today - h.bought_on).days >= YEAR_DAYS else "short"


def holding_return(h: Holding, today: dt.date) -> Return:
    kind, gain = _kind(h, today), _simple(invested(h), value(h))
    if kind != "xirr" or h.bought_on is None:
        return Return(kind, _pct(gain))
    years = (today - h.bought_on).days / DAYS_A_YEAR
    return Return(kind, _pct((1.0 + gain) ** (1.0 / years) - 1.0))


def total_return(items: Sequence[Holding], today: dt.date) -> Return:
    """XIRR when every lot is dated and held a year or more, "short" when every lot is dated
    and under a year old, else simple."""
    gain = _simple(sum(invested(h) for h in items), sum(value(h) for h in items))
    kinds = {_kind(h, today) for h in items}
    if kinds == {"xirr"}:
        flows = [(h.bought_on, -invested(h)) for h in items if h.bought_on is not None]
        rate = xirr([*flows, (today, sum(value(h) for h in items))])
        if rate is not None:
            return Return("xirr", _pct(rate))
    return Return("short" if kinds == {"short"} else "simple", _pct(gain))
