"""Plan range: the user's own plan replayed over real past months, as a range in rupees.

    r = plan_range(plan, profile)                # pure over data/sim/returns.csv
    lines = plan_range_lines(r, "en")            # fixed sentences, numbers filled in
    text = plan_range_message(user_id, store)    # the bot's /range reply, None for USD or no plan

docs/phases/phase-6-method.md fixes every rule. Only the user's own plan is ever simulated:
nothing here compares plans, ranks them or suggests a change.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

from networth.app.store import Plan, Profile, Store
from networth.sim.data import Table

Lang = Literal["en", "hi", "hinglish"]


class NotRupees(ValueError):
    """The plan's amount is not in rupees. Phase 6 covers INR only."""


@dataclass(frozen=True)
class PlanRange:
    """Every number at the precision it is shown with: rupees to 3 significant figures,
    percentages and months whole. guard.check reads repr(r) as the source of every line."""

    targets_pct: tuple[int, int, int]  # safety, core, growth
    monthly_amount: int
    years: int
    fall_limit_pct: int
    paths: int
    mean_block_months: int
    invested: int
    nominal_p10: int
    nominal_median: int
    nominal_p90: int
    real_p10: int
    real_median: int
    real_p90: int
    hit_limit_pct: int  # share of paths whose worst fall reached fall_limit_pct
    worst_fall_pct: int  # median across paths
    worst_fall_rupees: int  # median across paths
    recovery_months: int | None  # median across paths; None = not back by the end
    window_start: dt.date
    window_end: dt.date
    method_version: str


def simulate(
    targets_pct: tuple[int, int, int],
    monthly_amount: int,
    years: int,
    fall_limit_pct: int,
    table: Table,
    *,
    paths: int | None = None,
    seed: int | None = None,
) -> PlanRange:
    raise NotImplementedError


def horizon_years(profile_years: int) -> int:
    raise NotImplementedError


def plan_range(
    plan: Plan,
    profile: Profile,
    *,
    paths: int | None = None,
    seed: int | None = None,
    table: Table | None = None,
) -> PlanRange:
    """Raises NotRupees for a USD amount. `table` defaults to the cached data/sim table."""
    raise NotImplementedError


def plan_range_lines(r: PlanRange, lang: Lang) -> list[str]:
    raise NotImplementedError


def plan_range_message(user_id: str, store: Store) -> str | None:
    raise NotImplementedError
