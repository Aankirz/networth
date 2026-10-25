"""The track record: how often a rating's price part beat the market over the next 12 months.

Run: uv run python -m networth.ratings.track     # writes networth/ratings/backtest.json

    table = load()                      # the stored table, or None
    line = track_line(table, "stock", View.POSITIVE, "in")   # "in" beats the Nifty, "us" the S&P

Method, fixed before the first run (2026-10-25):
- Every month end from January 2015 to 12 months before the last price, every stock in the
  universe gets the price part of its score (score.price_part) from prices up to that day only.
- Its view comes from the same bands a full rating uses (model.view_for).
- A hit is the stock's next-12-month total return beating the Nifty 50's (^NSEI, price index).
- Funds the same way, on AMFI NAVs from mfapi.in, scored against their category's index.
- US stocks and ETFs the same way against the S&P 500 (^GSPC), on Yahoo's adjusted closes.

Only the price part is replayed. Growth, valuation, debt and news have no free point-in-time
history, so they are not in the test, and the page says so. The stock universe is today's
Nifty 50 (and today's largest US companies), so it carries survivorship bias: stocks that fell
out of the index are not in it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from networth.ratings import score
from networth.ratings.model import Track, View, view_for

TABLE: Final = Path(__file__).with_name("backtest.json")
START: Final = pd.Timestamp("2015-01-31")
HORIZON: Final = pd.DateOffset(months=12)
NIFTY: Final = "^NSEI"
SP500: Final = "^GSPC"
MARKET_INDEX: Final = {"in": NIFTY, "us": SP500}
MARKET_NAMES: Final = {"in": "the Nifty", "us": "the S&P 500"}
SINCE: Final = "2015"
MIN_CASES: Final = 30
MIN_EDGE: Final = 0.05  # 5 points over all tested cases, or the edge counts as weak

# Today's Nifty 50 on Yahoo, read 2026-10-25. TMPV is Tata Motors' passenger arm after the
# demerger; a ticker Yahoo has no history for is skipped and reported.
NIFTY_50: Final = (
    "ADANIENT ADANIPORTS APOLLOHOSP ASIANPAINT AXISBANK BAJAJ-AUTO BAJFINANCE BAJAJFINSV BEL "
    "BHARTIARTL CIPLA COALINDIA DRREDDY EICHERMOT ETERNAL GRASIM HCLTECH HDFCBANK HDFCLIFE "
    "HINDALCO HINDUNILVR ICICIBANK INDIGO INFY ITC JIOFIN JSWSTEEL KOTAKBANK LT M&M MARUTI "
    "MAXHEALTH NESTLEIND NTPC ONGC POWERGRID RELIANCE SBILIFE SBIN SHRIRAMFIN SUNPHARMA TATACONSUM "
    "TMPV TATASTEEL TCS TECHM TITAN TRENT ULTRACEMCO WIPRO"
).split()

# Today's largest US companies and the broad and sector ETFs the engine already tracks.
US_STOCKS: Final = (
    "AAPL MSFT NVDA AMZN GOOGL META BRK-B JPM V JNJ WMT PG XOM UNH HD MA KO PEP "
    "MRK COST ABBV CVX BAC ORCL CSCO ADBE CRM NFLX INTC AMD"
).split()
US_FUNDS: Final = ("SPY QQQ XLB XLE XLF XLI XLK XLP XLU XLV XLY").split()

LARGE, MID, SMALL, FLEXI = "large cap", "mid cap", "small cap", "flexi cap"
CATEGORY_INDEX: Final = {
    LARGE: "^NSEI",
    FLEXI: "^NSEI",
    MID: "^NSEMDCP50",
    SMALL: "NIFTYSMLCAP250.NS",
}
INDEX_NAMES: Final = {
    "^NSEI": "Nifty 50",
    "^NSEMDCP50": "Nifty Midcap 50",
    "NIFTYSMLCAP250.NS": "Nifty Smallcap 250",
}
# Direct growth plans on mfapi.in, scheme codes read 2026-10-25.
FUNDS: Final[Mapping[int, str]] = {
    120716: LARGE,
    118482: LARGE,
    119063: LARGE,
    120586: LARGE,
    118825: LARGE,  # incl. index
    118955: FLEXI,
    122639: FLEXI,
    119071: MID,
    118778: SMALL,
    125497: SMALL,
    125354: SMALL,
    130503: SMALL,
    120164: SMALL,
}


def category_of(name: str) -> str:
    n = name.lower()
    if "small" in n:
        return SMALL
    if "mid" in n:
        return MID
    if "flexi" in n or "multi" in n:
        return FLEXI
    return LARGE


@dataclass(frozen=True)
class Case:
    kind: str  # "stock" | "fund"
    asset: str
    at: str
    view: View
    beat: bool


GROUPS: Final = ("in_stock", "in_fund", "us_stock", "us_fund")


def cases(kind: str, asset: str, s: pd.Series, bench: pd.Series, nifty: pd.Series) -> list[Case]:
    fund = kind.endswith("fund")
    out = []
    last = min(s.index[-1], nifty.index[-1]) - HORIZON
    for at in pd.date_range(START, last, freq="ME"):
        part = score.price_part(score.upto(s, at), score.upto(bench, at), fund)
        if part is None:
            continue
        a, n = s[s.index <= at + HORIZON], nifty[nifty.index <= at + HORIZON]
        a0, n0 = score.upto(s, at).iloc[-1], score.upto(nifty, at).iloc[-1]
        beat = a.iloc[-1] / a0 > n.iloc[-1] / n0
        out.append(Case(kind, asset, at.date().isoformat(), view_for(round(part)), bool(beat)))
    return out


def summarize(all_cases: Sequence[Case], kind: str) -> dict:
    mine = [c for c in all_cases if c.kind == kind]
    base = sum(c.beat for c in mine) / len(mine) if mine else 0.0
    rows = []
    for v in View:
        got = [c for c in mine if c.view is v]
        if not got:
            continue
        rate = sum(c.beat for c in got) / len(got)
        rows.append(
            {
                "view": v.value,
                "n": len(got),
                "beat": sum(c.beat for c in got),
                "rate": f"{rate * 100:.0f}%",
                "excess": points(rate - base),
            }
        )
    return {
        "kind": kind,
        "n": len(mine),
        "assets": len({c.asset for c in mine}),
        "baseline": f"{base * 100:.0f}%",
        "baseline_rate": round(base, 4),
        "rows": rows,
    }


Loader = Callable[[str], pd.Series | None]


def build(stock: Loader, fund: Callable[[int], pd.Series | None], as_of: str) -> dict:
    nifty, sp = stock(NIFTY), stock(SP500)
    if nifty is None or sp is None:
        raise RuntimeError("no Nifty 50 or S&P 500 history")
    found: list[Case] = []
    skipped: list[str] = []
    listed = (
        [("in_stock", f"{s}.NS", nifty) for s in NIFTY_50]
        + [("us_stock", s, sp) for s in US_STOCKS]
        + [("us_fund", s, sp) for s in US_FUNDS]
    )
    for group, ticker, market in listed:
        s = stock(ticker)
        if s is None:
            skipped.append(ticker)
            continue
        found += cases(group, ticker.removesuffix(".NS"), s, market, market)
    benches = {t: stock(t) for t in set(CATEGORY_INDEX.values())}
    for code, cat in FUNDS.items():
        s, bench = fund(code), benches[CATEGORY_INDEX[cat]]
        if s is None or bench is None:
            skipped.append(f"MF{code}")
            continue
        found += cases("in_fund", f"MF{code}", s, bench, nifty)
    return {
        "method": __doc__.split("Method, ")[1].split("\n\n")[0].strip(),
        "caveat": "Only the price part of the score is replayed. The stock list is today's "
        "Nifty 50, so stocks that dropped out are missing (survivorship bias). The "
        "Nifty 50 here is the price index without dividends, about 1 point a year "
        "below its total return, which flatters funds and stocks a little.",
        "since": SINCE,
        "as_of": as_of,
        "skipped": skipped,
        "groups": [summarize(found, g) for g in GROUPS],
    }


def points(gap: float) -> str:
    n = round(gap * 100)
    return f"{n:+d} points" if n else "0 points"


def load(path: Path = TABLE) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def in_tens(rate: float) -> int:
    return round(rate * 10)


def track_line(table: dict | None, kind: str, view: View, market: str = "in") -> Track:
    noun = "fund" if kind in ("fund", "etf") else "stock"
    group = f"{market}_{noun}"
    beat_what = MARKET_NAMES[market]
    if kind == "ipo":
        return Track(
            "No tested record for IPOs: a new listing has no price history to replay.",
            0,
            0,
            SINCE,
            "Nothing to compare yet.",
            True,
        )
    g = next((g for g in (table or {}).get("groups", []) if g["kind"] == group), None)
    row = next((r for r in (g or {}).get("rows", []) if r["view"] == view.value), None)
    if g is None or row is None:
        return Track(
            f"No tested record for {view.value} ratings yet.",
            0,
            0,
            SINCE,
            "Nothing to compare yet.",
            True,
        )
    rate, base = row["beat"] / row["n"], g["baseline_rate"]
    weak = row["n"] < MIN_CASES or abs(rate - base) < MIN_EDGE
    text = (
        f"Ratings like this beat {beat_what} {in_tens(rate)} times in 10 since {SINCE} "
        f"({row['beat']} of {row['n']} tested {noun} months)."
    )
    edge = (
        f"Every tested {noun} beat it {in_tens(base)} times in 10, so the edge is "
        f"{points(rate - base)}."
    )
    if weak:
        edge += " That is too small to lean on."
    return Track(text, row["beat"], row["n"], SINCE, edge, weak)


def main() -> int:
    from networth.ratings.sources import LiveSources

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=TABLE)
    args = parser.parse_args()
    src = LiveSources()

    def stock(t: str) -> pd.Series | None:
        c = src.closes(t)
        return None if c is None else c.series

    def fund(code: int) -> pd.Series | None:
        got = src.fund_navs(code)
        return None if got is None else got[1].series

    table = build(stock, fund, dt.date.today().isoformat())
    args.out.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    for g in table["groups"]:
        print(f"{g['kind']}: {g['n']} cases over {g['assets']} assets, all beat {g['baseline']}")
        for r in g["rows"]:
            print(f"  {r['view']:<9} {r['beat']:>5}/{r['n']:<5} {r['rate']:>4}  {r['excess']}")
    if table["skipped"]:
        print("skipped (no history):", ", ".join(table["skipped"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
