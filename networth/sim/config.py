"""Every fixed choice of the plan range. docs/phases/phase-6-method.md explains each one; a change
here bumps METHOD_VERSION and gets a dated line there."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from networth.engine.model import DATA_DIR

METHOD_VERSION: Final = "plan-range-v1"
SEED: Final = 20261025
PATHS: Final = 10_000
MEAN_BLOCK_MONTHS: Final = 12
REBALANCE_MONTHS: Final = 12

# Upper bound of Profile.horizon_years -> simulated years. Onboarding stores 2, 4, 7 and 15.
HORIZON_YEARS: Final[tuple[tuple[int, int], ...]] = ((3, 3), (5, 5), (10, 10))
LONG_HORIZON_YEARS: Final = 15

BUCKETS: Final = ("safety", "core", "growth")
CPI: Final = "cpi"
COLUMNS: Final = (*BUCKETS, CPI)

SIM_DIR: Final = DATA_DIR / "sim"
TABLE_FILE: Final = "returns.csv"
SOURCES_FILE: Final = "sources.json"

CORE_TICKER: Final = "^NSEI"
GROWTH_TICKER: Final = "^NSEMDCP50"
SAFETY_FRED_ID: Final = "INDIR3TIB01STM"
# Inside the window only these CPI gaps may be filled, by a straight line (MoSPI has no print).
CPI_MAX_FILL_MONTHS: Final = 2

SOURCES: Final[Mapping[str, Mapping[str, str]]] = {
    "core": {
        "series": "Nifty 50, price index (^NSEI)",
        "url": "https://finance.yahoo.com/quote/%5ENSEI/history/",
        "note": "Price index: dividends are left out, so the range is conservative by about "
        "the dividend yield.",
    },
    "growth": {
        "series": "Nifty Midcap 50, price index (^NSEMDCP50)",
        "url": "https://finance.yahoo.com/quote/%5ENSEMDCP50/history/",
        "note": "Price index: dividends are left out. Index owner NSE Indices, "
        "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-midcap-50",
    },
    "safety": {
        "series": "3-month interbank rate, India (FRED INDIR3TIB01STM, OECD MEI)",
        "url": "https://fred.stlouisfed.org/series/INDIR3TIB01STM",
        "note": "% a year, turned into a monthly return as (1 + r/100)^(1/12) - 1.",
    },
    "cpi": {
        "series": "India CPI Combined, official YoY % (MoSPI, via networth/engine/macro.py)",
        "url": "https://api.mospi.gov.in/api/cpi",
        "note": "Monthly inflation = (1 + yoy/100)^(1/12) - 1. 2020-04 and 2020-05 have no "
        "print and take the straight line between 2020-03 and 2020-06.",
    },
}
