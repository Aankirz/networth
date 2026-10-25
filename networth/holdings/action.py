"""How a confirmed list gets to the saved plan, in money. Pure; no IO.

    plan = action_plan(report, monthly=100_000, views={"Swiggy": View.WEAK})
    plan.trims     # what to sell first in the over-weight parts, weakest first, and how much
    plan.moves     # where that money goes: each under-weight part and its amount
    plan.months    # with new money alone, months until the holdings match the plan

Targets are the plan's percentages of today's total. Trims go weakest first: the worst rating
when one is given, then the deepest loss, then the biggest holding. New money is split across
the under-weight parts in proportion to how far each is below its target.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from networth.holdings.model import BUCKETS, Bucket
from networth.holdings.report import HoldingsReport, Row
from networth.ratings.model import View

WEAKEST_FIRST = (View.AVOID, View.WEAK, View.NEUTRAL, View.POSITIVE, View.STRONG)


@dataclass(frozen=True)
class Trim:
    name: str
    value: int  # the holding's value today
    amount: int  # how much of it to sell
    booked: int  # the gain (or, below zero, the loss) that selling this much books
    view: View | None

    @property
    def whole(self) -> bool:
        return self.amount >= self.value


@dataclass(frozen=True)
class Move:
    bucket: Bucket
    amount: int


@dataclass(frozen=True)
class ActionPlan:
    currency: str
    total: int
    targets: Mapping[Bucket, int]
    held: Mapping[Bucket, int]
    trims: tuple[Trim, ...]
    moves: tuple[Move, ...]  # to the under-weight parts, rebalancing now
    monthly: int | None
    split: tuple[Move, ...]  # the monthly amount across the under-weight parts
    months: int | None  # None without a monthly amount, or when new money can't get there

    @property
    def on_plan(self) -> bool:
        return not self.trims and not self.moves

    @property
    def booked(self) -> int:
        return sum(t.booked for t in self.trims)


def _order(row: Row, views: Mapping[str, View]) -> tuple[int, float, int]:
    view = views.get(row.name)
    rank = WEAKEST_FIRST.index(view) if view else len(WEAKEST_FIRST)
    loss = row.gain / row.invested if row.invested else 0.0
    return rank, loss, -row.value


def _trims(rows: list[Row], excess: int, views: Mapping[str, View]) -> list[Trim]:
    trims = []
    for row in sorted(rows, key=lambda r: _order(r, views)):
        if excess <= 0:
            break
        amount = min(row.value, excess)
        booked = round(row.gain * amount / row.value) if row.value else 0
        trims.append(Trim(row.name, row.value, amount, booked, views.get(row.name)))
        excess -= amount
    return trims


def _split(monthly: int, gaps: list[Move]) -> tuple[Move, ...]:
    whole = sum(g.amount for g in gaps)
    return tuple(Move(g.bucket, round(monthly * g.amount / whole)) for g in gaps) if whole else ()


def _months(report: HoldingsReport, held: Mapping[Bucket, int], over: list[Bucket],
            monthly: int | None) -> int | None:  # fmt: skip
    """Months of new money until each over-weight part is down to its share of a bigger total.
    None when a part the plan holds 0% of can't be diluted to zero."""
    pct = dict(zip(BUCKETS, report.plan_pct, strict=True))
    if not monthly or any(pct[b] == 0 for b in over):
        return None
    need = [math.ceil(max(held[b] * 100 / pct[b] - report.value, 0) / monthly) for b in over]
    return max(need, default=0)


def action_plan(report: HoldingsReport, monthly: int | None = None,
                views: Mapping[str, View] | None = None) -> ActionPlan:  # fmt: skip
    views = views or {}
    held = {b: sum(r.value for r in report.rows if r.bucket is b) for b in BUCKETS}
    targets = {b: round(report.value * p / 100)
               for b, p in zip(BUCKETS, report.plan_pct, strict=True)}  # fmt: skip
    over = [b for b in BUCKETS if held[b] > targets[b]]
    trims = [t for b in over
             for t in _trims([r for r in report.rows if r.bucket is b], held[b] - targets[b],
                             views)]  # fmt: skip
    gaps = [Move(b, targets[b] - held[b]) for b in BUCKETS if held[b] < targets[b]]
    split = _split(monthly, gaps) if monthly else ()
    return ActionPlan(report.currency, report.value, targets, held, tuple(trims), tuple(gaps),
                      monthly, split, _months(report, held, over, monthly))  # fmt: skip
