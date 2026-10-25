"""A PlanRange into what the plan range section prints. Every number is a PlanRange field,
formatted by networth.sim.rupees; the only arithmetic is the range bar's geometry."""

from __future__ import annotations

from typing import Final

from networth.sim import PlanRange, rupees
from networth.web.fmt import western_grouping

LABEL: Final = (
    "This replays real past months. It is not a forecast. Your plan is your choice. "
    "Research, not advice."
)
RUPEES_ONLY: Final = "Rupee plans only for now."
NO_TABLE: Final = (
    "The plan range isn't ready on this server yet. Its table of past months is built with "
    "uv run python -m networth.sim.data"
)

BAR_H: Final = 20
ROW_GAP: Final = 64
FIRST_ROW_Y: Final = 28
GRID_GAP: Final = 12
TIP_GAP: Final = 8
INVESTED_LABEL: Final = "what you put in"
INVESTED_NAME: Final = "What you put in"
CASE_NAMES: Final = ("Bad case", "Middle case", "Good case")


def _range(p10: int, median: int, p90: int) -> dict:
    return {"p10": rupees(p10), "median": rupees(median), "p90": rupees(p90)}


def bar_geometry(r: PlanRange) -> dict:
    """Shapes on one rupee scale from zero, so the two bars and the invested line can be read
    against each other. x is a percent of the chart's width and y is in pixels, so text and
    corners keep their size at every screen width."""
    hi = max(r.nominal_p90, r.real_p90, r.invested) or 1

    def x(v: int) -> float:
        return round(v / hi * 100, 2)

    rows = []
    for i, (series, name, p10, median, p90) in enumerate((
        ("before", "Before inflation", r.nominal_p10, r.nominal_median, r.nominal_p90),
        ("after", "After inflation", r.real_p10, r.real_median, r.real_p90),
    )):  # fmt: skip
        y = FIRST_ROW_Y + i * ROW_GAP
        rows.append({
            "series": series, "name": name, "label_y": y - 8, "y": y, "h": BAR_H,
            "x": x(p10), "w": round(x(p90) - x(p10), 2), "median_x": x(median),
            "grid_y": y + BAR_H + GRID_GAP,
            "cases": list(zip(CASE_NAMES, _range(p10, median, p90).values(), strict=True)),
        })  # fmt: skip
    base_y = rows[-1]["grid_y"]
    invested_x = x(r.invested)
    left_half = invested_x < 50
    return {
        "height": base_y + 22,
        "base_y": base_y,
        "tip_y": base_y + TIP_GAP,
        "rows": rows,
        "invested_x": invested_x,
        "invested_dx": 6 if left_half else -6,
        "invested_anchor": "start" if left_half else "end",
        "invested_label": INVESTED_LABEL,
        # Row names sit on the side away from the invested line so it never crosses them.
        "name_x": 100 if left_half else 0,
        "name_anchor": "end" if left_half else "start",
        "zero_label": rupees(0),
        "invested_name": INVESTED_NAME,
        "legend": [*((row["series"], row["name"]) for row in rows), ("invested", INVESTED_NAME)],
    }


def _recovery(months: int | None) -> str:
    if months is None:
        return "It was not back to the level before it by the end."
    return f"Getting back to the level before it took {months} month{'' if months == 1 else 's'}."


def plan_range_view(r: PlanRange, plan_label: str) -> dict:
    return {
        "plan": plan_label,
        "monthly": rupees(r.monthly_amount),
        "years": r.years,
        "invested": rupees(r.invested),
        "nominal": _range(r.nominal_p10, r.nominal_median, r.nominal_p90),
        "real": _range(r.real_p10, r.real_median, r.real_p90),
        "fall_limit": f"{r.fall_limit_pct}%",
        "hit_limit": f"{r.hit_limit_pct}%",
        "worst_fall_pct": f"{r.worst_fall_pct}%",
        "worst_fall_rupees": rupees(r.worst_fall_rupees),
        "recovery": _recovery(r.recovery_months),
        "paths": western_grouping(r.paths),
        "block_months": r.mean_block_months,
        "window": f"{r.window_start:%B %Y} to {r.window_end:%B %Y}",
        "method_version": r.method_version,
        "bar": bar_geometry(r),
        "label": LABEL,
    }
