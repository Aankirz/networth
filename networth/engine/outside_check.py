"""Reproduce the pre-FOMC announcement drift (Lucca and Moench 2015) on daily closes.

Run: uv run python -m networth.engine.outside_check

The paper measures 2pm the day before to 2pm on the announcement day, from intraday data,
Sep 1994 to Mar 2011. We only have daily closes, so the window shifts to close->close:

    pre_fomc   close(D-1) -> close(D)    4pm(D-1)..4pm(D): most of the paper's 24 hours, minus
                                         2pm-4pm on D-1, plus about two hours after the
                                         announcement
    placebo    close(D-2) -> close(D-1)  the session before, entirely pre-announcement

D is a scheduled announcement date from fomc.csv. Each window is compared with every other
session of the same period (sessions that are not announcement days). A sign or size
mismatch is a finding to report, not something to tune away.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

import numpy as np
import pandas as pd

from networth.engine.fetch import load_series

FOMC_CSV: Final = Path(__file__).with_name("fomc.csv")
PAPER_URL: Final = "https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf"
PAPER_CLAIM: Final = (
    "We document that since 1994, the S&P500 index has on average increased 49 basis points "
    "in the 24 hours before scheduled FOMC announcements. These returns do not revert in "
    "subsequent trading days and are orders of magnitude larger than those outside the "
    "24-hour pre-FOMC window."
)
PAPER_CITATION: Final = (
    "Lucca and Moench, 'The Pre-FOMC Announcement Drift', Journal of Finance 70(1), 2015, "
    "pp. 329-371; NY Fed Staff Report 512"
)
PAPER_DRIFT_BP: Final = 49.0
# A daily-close mean within a factor of two of the paper's figure counts as the same rough size.
SIZE_FACTOR: Final = 2.0

PERIODS: Final[tuple[tuple[str, dt.date, dt.date | None], ...]] = (
    ("paper 1994-09..2011-03", dt.date(1994, 9, 1), dt.date(2011, 3, 31)),
    ("after 2011-04..", dt.date(2011, 4, 1), None),
    ("all", dt.date(1994, 1, 1), None),
)
SERIES: Final = ("SPY", "^GSPC")

Window = Literal["pre_fomc", "placebo"]
WINDOW_LAG: Final[dict[Window, int]] = {"pre_fomc": 0, "placebo": 1}


@dataclass(frozen=True)
class DriftResult:
    series: str
    period: str
    window: Window
    n_fomc: int
    n_other: int
    mean_fomc_bp: float
    mean_other_bp: float
    t_stat: float


def load_fomc_dates(path: Path = FOMC_CSV) -> list[dt.date]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return sorted(dt.date.fromisoformat(r["date"]) for r in rows if r["scheduled"].strip() == "1")


def welch_t(a: np.ndarray, b: np.ndarray) -> float:
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    return float((a.mean() - b.mean()) / math.sqrt(va + vb))


def drift(
    closes: pd.Series, fomc: Sequence[dt.date], window: Window, start: dt.date,
    end: dt.date | None, period: str,
) -> DriftResult:  # fmt: skip
    """Mean window return on announcement days vs every other session, in basis points.
    Raises ValueError if an announcement date is not a session of `closes`."""
    returns = closes.pct_change(fill_method=None)
    days = pd.DatetimeIndex([pd.Timestamp(d) for d in fomc])
    missing = days[~days.isin(closes.index)]
    if len(missing):
        raise ValueError(f"FOMC dates that are not {closes.name} sessions: {list(missing.date)}")
    shifted = returns.shift(WINDOW_LAG[window])
    in_period = (returns.index >= pd.Timestamp(start)) & (
        returns.index <= pd.Timestamp(end or returns.index[-1].date())
    )
    is_fomc = returns.index.isin(days)
    fomc_r = shifted[in_period & is_fomc].dropna().to_numpy()
    other_r = shifted[in_period & ~is_fomc].dropna().to_numpy()
    return DriftResult(
        series=str(closes.name),
        period=period,
        window=window,
        n_fomc=len(fomc_r),
        n_other=len(other_r),
        mean_fomc_bp=float(fomc_r.mean() * 1e4),
        mean_other_bp=float(other_r.mean() * 1e4),
        t_stat=welch_t(fomc_r, other_r),
    )


def verdict(r: DriftResult) -> str:
    same_sign = r.mean_fomc_bp > 0
    rough_size = PAPER_DRIFT_BP / SIZE_FACTOR <= r.mean_fomc_bp <= PAPER_DRIFT_BP * SIZE_FACTOR
    if same_sign and rough_size:
        return "MATCH: positive and within 2x of 49bp"
    why = "sign differs" if not same_sign else "size outside 25-98bp"
    return f"MISMATCH: {why} ({r.mean_fomc_bp:+.1f}bp vs the paper's +49bp)"


def report(results: Sequence[DriftResult]) -> str:
    lines = [
        f"Paper: {PAPER_CITATION}",
        f"URL:   {PAPER_URL}",
        f'Claim: "{PAPER_CLAIM}"',
        "",
        "Only daily closes are available, so the paper's 2pm->2pm window is shifted to "
        "close(D-1)->close(D). Placebo: close(D-2)->close(D-1). Other = every non-announcement "
        "session in the same period. Closes are auto-adjusted (SPY includes dividends).",
        "",
        f"{'series':<7} {'period':<24} {'window':<9} {'n_fomc':>6} {'mean_fomc':>10} "
        f"{'n_other':>7} {'mean_other':>10} {'welch_t':>8}",
    ]
    for r in results:
        lines.append(
            f"{r.series:<7} {r.period:<24} {r.window:<9} {r.n_fomc:>6} "
            f"{r.mean_fomc_bp:>8.1f}bp {r.n_other:>7} {r.mean_other_bp:>8.1f}bp {r.t_stat:>8.2f}"
        )
    lines.append("")
    for r in results:
        if r.window == "pre_fomc":
            lines.append(f"{r.series:<7} {r.period:<24} {verdict(r)}")
    return "\n".join(lines)


def run(closes_by_series: dict[str, pd.Series], fomc: Sequence[dt.date]) -> list[DriftResult]:
    return [
        drift(closes, fomc, window, start, end, period)
        for closes in closes_by_series.values()
        for period, start, end in PERIODS
        for window in WINDOW_LAG
    ]


def main(argv: Sequence[str] | None = None) -> int:
    fomc = load_fomc_dates()
    print(report(run({name: load_series(name) for name in SERIES}, fomc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
