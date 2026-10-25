"""Each driver's score, 0 to 100, from sourced numbers. Pure: no IO.

A scorer returns a Driver, a Missing (the data was not there; the confidence drops) or None
(the driver does not apply, such as debt for a bank). The price scorers take a cut-off date so
the backtest can replay them on history with no peeking.

Every mapping below was fixed before the backtest was run (2026-10-25).
"""

from __future__ import annotations

import datetime as dt
import math
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import pandas as pd

from networth.ratings.model import Driver, Source

MOMENTUM_DAYS: Final = 252  # 12 months of sessions
SKIP_DAYS: Final = 21  # the last month is left out, the usual 12-1 momentum
TREND_DAYS: Final = 200
SECTOR_DAYS: Final = 63  # 3 months
MONTHS: Final = 12
STRESS_TYPES: Final = frozenset(
    {"bank_stress", "pandemic", "military_conflict", "inr_shock", "oil_supply", "tariff"}
)
# ponytail: a word list for tone, not a model. Upgrade to the judge's own tone if it gets one.
UP_WORDS: Final = re.compile(
    r"\b(surges?|soars?|jumps?|rall(?:y|ies)|beats?|record|upgrade[sd]?|"
    r"wins?|gains?|rises?|profit (?:up|rises|jumps)|strong|boost)\b",
    re.I,
)
DOWN_WORDS: Final = re.compile(
    r"\b(falls?|slumps?|plunges?|drops?|probe|loss(?:es)?|downgrade[sd]?|"
    r"fraud|penalty|fine[sd]?|misses|weak|cuts?|crash(?:es)?|raid)\b",
    re.I,
)


@dataclass(frozen=True)
class Missing:
    key: str
    sentence: str  # "Expense ratio: no free source we can read yet."


Scored = Driver | Missing | None


def clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:+.{digits}f}%"


def upto(s: pd.Series, at: pd.Timestamp | None) -> pd.Series:
    return s if at is None else s[s.index <= at]


def ret(s: pd.Series, days: int, skip: int = 0) -> float | None:
    if len(s) < days + 1:
        return None
    end = s.iloc[-1 - skip]
    return float(end / s.iloc[-1 - days] - 1)


def cagr(s: pd.Series, years: float) -> float | None:
    start = s.index[-1] - pd.DateOffset(days=round(365.25 * years))
    before = s[s.index <= start]
    if before.empty:
        return None
    return float((s.iloc[-1] / before.iloc[-1]) ** (1 / years) - 1)


# --- price parts: these are the parts the backtest can replay ------------------------------


def momentum_score(s: pd.Series, bench: pd.Series) -> tuple[float, float] | None:
    """(12-1 month return over the benchmark's, score)."""
    a, b = ret(s, MOMENTUM_DAYS, SKIP_DAYS), ret(bench, MOMENTUM_DAYS, SKIP_DAYS)
    if a is None or b is None:
        return None
    return a - b, clip(50 + 100 * (a - b))


def trend_score(s: pd.Series) -> tuple[float, float] | None:
    """(price over its 200-session average, score)."""
    if len(s) < TREND_DAYS:
        return None
    r = float(s.iloc[-1] / s.iloc[-TREND_DAYS:].mean() - 1)
    return r, clip(50 + 250 * r)


def consistency_score(s: pd.Series, bench: pd.Series) -> tuple[int, float] | None:
    """(months of the last 12 it beat the benchmark, score)."""
    a, b = s.resample("ME").last(), bench.resample("ME").last()
    both = pd.concat([a, b], axis=1, join="inner").dropna().iloc[-(MONTHS + 1) :]
    if len(both) < MONTHS + 1:
        return None
    r = both.pct_change().dropna()
    beat = int((r.iloc[:, 0] > r.iloc[:, 1]).sum())
    return beat, 100.0 * beat / MONTHS


def price_part(s: pd.Series, bench: pd.Series, fund: bool) -> float | None:
    """The backtested score: momentum and trend for a share, momentum and consistency for a
    fund. None when there is not enough history."""
    m = momentum_score(s, bench)
    other = consistency_score(s, bench) if fund else trend_score(s)
    if m is None or other is None:
        return None
    return 0.6 * m[1] + 0.4 * other[1]


# --- drivers ---------------------------------------------------------------------------------


def momentum_driver(
    s: pd.Series, bench: pd.Series, src: Source, bench_name: str, weight: float
) -> Scored:
    m, t = momentum_score(s, bench), trend_score(s)
    if m is None or t is None:
        return Missing("momentum", "Price momentum: under a year of price history.")
    value = (
        f"{pct(m[0])} against the {bench_name} over 12 months (last month left out); "
        f"{pct(t[0])} from its 200-day average"
    )
    return Driver("momentum", "Price momentum", value, 0.6 * m[1] + 0.4 * t[1], weight, src)


def consistency_driver(
    s: pd.Series, bench: pd.Series, src: Source, bench_name: str, weight: float
) -> Scored:
    c = consistency_score(s, bench)
    if c is None:
        return Missing("consistency", "Consistency: under 13 months of history.")
    return Driver(
        "consistency",
        "Consistency",
        f"Beat the {bench_name} in {c[0]} of the last {MONTHS} months",
        c[1],
        weight,
        src,
    )


def growth_driver(
    revenue: float | None, earnings: float | None, margin: float | None, src: Source, weight: float
) -> Scored:
    have = [g for g in (revenue, earnings) if g is not None]
    if not have:
        return Missing("growth", "Growth: no revenue or profit trend in the data.")
    parts = [
        f"revenue {pct(revenue)}" if revenue is not None else "",
        f"profit {pct(earnings)}" if earnings is not None else "",
    ]
    score = clip(45 + 125 * statistics.fmean(have))
    words = " and ".join(p for p in parts if p) + " year on year (latest quarter)"
    if margin is not None and margin < 0:
        score = min(score, 55.0)
        words += f"; still loss-making, margin {pct(margin)}"
    return Driver("growth", "Growth", words[0].upper() + words[1:], score, weight, src)


def ratio_score(r: float) -> float:
    """Half the peers' multiple scores about 75, double scores about 25."""
    return clip(50 - 36 * math.log(r), 5, 95)


def valuation_driver(
    own: float | None, peers: Sequence[tuple[str, float]], measure: str, src: Source, weight: float
) -> Scored:
    usable = [v for _, v in peers if v > 0]
    if own is None or own <= 0 or len(usable) < 2:
        return Missing("valuation", "Valuation against peers: no peer set or no multiple.")
    median = statistics.median(usable)
    named = ", ".join(n for n, v in peers if v > 0)
    value = f"{measure} {own:.1f} against a peer median of {median:.1f} ({named})"
    return Driver(
        "valuation", "Valuation against sector peers", value, ratio_score(own / median), weight, src
    )


def debt_driver(de_pct: float | None, is_lender: bool, src: Source, weight: float) -> Scored:
    if is_lender:
        return None  # borrowing is a lender's business; debt to equity says nothing here
    if de_pct is None:
        return Missing("debt", "Balance sheet: no debt figure in the data.")
    d = de_pct / 100
    score = 80.0 if d < 0.3 else 60.0 if d < 1 else 40.0 if d < 2 else 20.0
    return Driver("debt", "Balance sheet", f"Debt is {d:.2f}x equity", score, weight, src)


def tone(titles: Sequence[str], types: Sequence[str | None]) -> tuple[int, int]:
    up = sum(bool(UP_WORDS.search(t)) for t in titles)
    down = sum(bool(DOWN_WORDS.search(t)) for t in titles) + sum(t in STRESS_TYPES for t in types)
    return up, down


def news_driver(
    found: Sequence[tuple[str, str | None]] | None, src: Source | None, weight: float
) -> Scored:
    """found is (title, event type) for each confirmed story naming it in the last 30 days."""
    if found is None or src is None:
        return Missing("news", "News tone: the watcher's confirmed stories were not available.")
    up, down = tone([t for t, _ in found], [ty for _, ty in found])
    n = len(found)
    if n == 0:
        return Driver(
            "news",
            "News tone, 30 days",
            "No confirmed stories naming it in 30 days",
            50.0,
            weight,
            src,
        )
    mood = "positive" if up > down else "negative" if down > up else "mixed"
    noun = "story" if n == 1 else "stories"
    value = f"{n} confirmed {noun} in 30 days, tone {mood} ({up} up, {down} down)"
    return Driver(
        "news", "News tone, 30 days", value, clip(50 + 12 * (up - down), 10, 90), weight, src
    )


def sector_driver(
    sector: pd.Series | None, bench: pd.Series, name: str | None, src: Source | None, weight: float
) -> Scored:
    if sector is None or name is None or src is None:
        return Missing("sector", "Sector trend: no NSE sector index matches this company.")
    a, b = ret(sector, SECTOR_DAYS), ret(bench, SECTOR_DAYS)
    if a is None or b is None:
        return Missing("sector", "Sector trend: not enough sector history.")
    return Driver(
        "sector",
        "Sector trend",
        f"{name} {pct(a, 1)} over 3 months against the Nifty 50's {pct(b, 1)}",
        clip(50 + 200 * (a - b)),
        weight,
        src,
    )


def excess_driver(
    key: str,
    label: str,
    own: float | None,
    other: float | None,
    other_name: str,
    years: int,
    src: Source,
    weight: float,
) -> Scored:
    if own is None or other is None:
        return Missing(key, f"{label}: under {years} years of history.")
    value = f"{pct(own, 1)} a year over {years} years against {other_name} at {pct(other, 1)}"
    return Driver(key, label, value, clip(50 + 300 * (own - other)), weight, src)


def as_of_date(s: pd.Series) -> dt.date:
    return s.index[-1].date()
