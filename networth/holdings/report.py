"""The holdings report: what the user holds, their mix next to their saved plan, and what
history says about both. Pure; no IO.

    r = holdings_report(holdings, profile, plan, table=table)   # None until confirmed and placed
    r.rows[0].invested, r.held_pct, r.history.held.hit_limit_pct

Every number is stored at the precision it is shown with (money in whole rupees or dollars,
percentages whole or to one decimal), so guard.check(line, repr(r)) passes for every line.
Only two mixes are ever simulated: the one the user holds and the one they saved.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from networth.app.store import Plan, Profile
from networth.holdings.model import BUCKETS, Bucket, Holding, Holdings, PriceFrom, Source
from networth.holdings.returns import Return, holding_return, invested, total_return, value
from networth.sim import PlanRange, horizon_years, simulate
from networth.sim.data import Table

FALL_PCT: Final = 20
UNIT_DECIMALS: Final = 3
COST_DECIMALS: Final = 2


class NoHistory(StrEnum):
    NOT_RUPEES = "not_rupees"  # the plan range is rupee-only
    NO_AMOUNT = "no_amount"  # the profile has no monthly amount or horizon yet
    NO_TABLE = "no_table"  # the returns table isn't built on this server


@dataclass(frozen=True)
class Row:
    n: int  # the 1-based line number the user sees
    name: str
    bucket: Bucket
    units: float
    avg_cost: float
    invested: int
    value: int
    gain: int
    ret: Return
    price_from: PriceFrom


@dataclass(frozen=True)
class MixHistory:
    targets_pct: tuple[int, int, int]
    hit_limit_pct: int
    worst_fall_pct: int
    nominal_median: int


@dataclass(frozen=True)
class History:
    held: MixHistory
    plan: MixHistory
    fall_pct: int
    monthly_amount: int
    years: int
    paths: int
    invested: int
    window_start: int  # first year of the table
    window_end: int


@dataclass(frozen=True)
class HoldingsReport:
    currency: str
    source: Source
    as_of: dt.date
    rows: tuple[Row, ...]
    count: int
    invested: int
    value: int
    gain: int
    ret: Return
    held_pct: tuple[int, int, int]  # safety, core, growth by current value
    plan_pct: tuple[int, int, int]
    looked_up: int  # holdings priced by our own source
    from_source: int  # priced from the screenshot or the broker
    unpriced: int  # no current price: valued at cost
    history: History | NoHistory


def holding_row(n: int, h: Holding, today: dt.date) -> Row:
    """h must be placed (bucket set)."""
    cost, worth = round(invested(h)), round(value(h))
    assert h.bucket is not None, "rows are built from placed holdings"
    return Row(n, h.name, h.bucket, round(h.units, UNIT_DECIMALS),
               round(h.avg_cost, COST_DECIMALS), cost, worth, worth - cost,
               holding_return(h, today), h.price_from)  # fmt: skip


def largest_remainder(weights: tuple[float, float, float]) -> tuple[int, int, int]:
    """Whole percentages summing to exactly 100 (all zero when there is no weight)."""
    total = sum(weights)
    if total <= 0:
        return (0, 0, 0)
    raw = [100 * w / total for w in weights]
    whole = [int(x) for x in raw]
    by_remainder = sorted(range(len(raw)), key=lambda i: raw[i] - whole[i], reverse=True)
    for i in by_remainder[: 100 - sum(whole)]:
        whole[i] += 1
    return (whole[0], whole[1], whole[2])


def _mix(r: PlanRange) -> MixHistory:
    return MixHistory(r.targets_pct, r.hit_limit_pct, r.worst_fall_pct, r.nominal_median)


def _history(currency: str, held: tuple[int, int, int], plan: tuple[int, int, int],
             profile: Profile, table: Table | None, paths: int | None,
             seed: int | None) -> History | NoHistory:  # fmt: skip
    if currency != "INR" or (profile.currency or "INR") != "INR":
        return NoHistory.NOT_RUPEES
    amount, horizon = profile.monthly_amount, profile.horizon_years
    if amount is None or horizon is None:
        return NoHistory.NO_AMOUNT
    if table is None:
        return NoHistory.NO_TABLE
    held_r, plan_r = (simulate(t, amount, horizon_years(horizon), FALL_PCT, table,
                               paths=paths, seed=seed) for t in (held, plan))  # fmt: skip
    return History(_mix(held_r), _mix(plan_r), FALL_PCT, amount, held_r.years, held_r.paths,
                   held_r.invested, held_r.window_start.year, held_r.window_end.year)  # fmt: skip


def _count(items: tuple[Holding, ...], *froms: PriceFrom) -> int:
    return sum(h.price_from in froms for h in items)


def holdings_report(
    holdings: Holdings,
    profile: Profile,
    plan: Plan,
    *,
    seed: int | None = None,
    table: Table | None = None,
    paths: int | None = None,
) -> HoldingsReport | None:
    """None for an unconfirmed list, an empty one, or one with a holding not yet placed."""
    if not holdings.confirmed or not holdings.items or holdings.unplaced:
        return None
    today = holdings.as_of.date()
    rows = tuple(holding_row(n, h, today) for n, h in enumerate(holdings.items, start=1))
    safety, core, growth = (sum(r.value for r in rows if r.bucket is b) for b in BUCKETS)
    held = largest_remainder((safety, core, growth))
    planned = (plan.targets_pct["safety"], plan.targets_pct["core"], plan.targets_pct["growth"])
    cost, worth = sum(r.invested for r in rows), sum(r.value for r in rows)
    items = holdings.items
    return HoldingsReport(
        currency=holdings.currency, source=holdings.source, as_of=today, rows=rows,
        count=len(rows), invested=cost, value=worth, gain=worth - cost,
        ret=total_return(items, today), held_pct=held, plan_pct=planned,
        looked_up=_count(items, PriceFrom.LOOKED_UP),
        from_source=_count(items, PriceFrom.SCREENSHOT, PriceFrom.BROKER),
        unpriced=_count(items, PriceFrom.NONE),
        history=_history(holdings.currency, held, planned, profile, table, paths, seed),
    )  # fmt: skip
