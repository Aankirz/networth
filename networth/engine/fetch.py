"""Download daily price history into data/prices/ and print a coverage table.

Run: uv run python -m networth.engine.fetch [--refresh]

Every series is stored as data/prices/<name>.csv with columns date,close.
Yahoo closes are auto-adjusted (dividends and splits), so returns are total returns.
Kenneth French industry and market returns are turned into index levels starting at 1.0.
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import urllib.request
import warnings
import zipfile
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PRICES_DIR = DATA_DIR / "prices"

US_TICKERS = [
    "SPY", "^GSPC", "^SP500TR", "QQQ", "TLT", "GLD", "BTC-USD", "JETS",
    "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC",
    "BZ=F",
]  # fmt: skip
IN_TICKERS = [
    "^BSESN", "^NSEI", "^NSEBANK", "^CNXIT", "^CNXAUTO", "^CNXPHARMA", "^CNXFMCG",
    "^CNXMETAL", "^CNXENERGY", "^CNXREALTY", "^CNXPSUBANK", "^CNXINFRA",
    "INR=X", "NIFTYBEES.NS", "GOLDBEES.NS",
]  # fmt: skip

# Exact files listed on the French data library page
# (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), checked 2026-10-24.
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FRENCH_INDUSTRIES = "49_Industry_Portfolios_daily_CSV.zip"
FRENCH_FACTORS = "F-F_Research_Data_Factors_daily_CSV.zip"
FRENCH_MARKET = "FF:Mkt"

CACHE_HOURS = 20
USER_AGENT = "Mozilla/5.0 (networth-engine)"


def series_path(name: str) -> Path:
    return PRICES_DIR / f"{name.replace(':', '__')}.csv"


def load_series(name: str, prices_dir: Path | None = None) -> pd.Series:
    """Read one stored series as a float Series indexed by normalized Timestamps."""
    path = (prices_dir or PRICES_DIR) / f"{name.replace(':', '__')}.csv"
    df = pd.read_csv(path, parse_dates=["date"])
    return df.set_index("date")["close"].astype(float).sort_index().rename(name)


def is_fresh(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < CACHE_HOURS * 3600


def save_series(name: str, closes: pd.Series) -> None:
    closes = closes.dropna()
    closes = closes[closes > 0]
    if closes.empty:
        raise ValueError("no usable rows")
    out = pd.DataFrame({"date": closes.index.strftime("%Y-%m-%d"), "close": closes.values})
    out.to_csv(series_path(name), index=False)


def fetch_yahoo(ticker: str) -> None:
    import yfinance as yf

    with warnings.catch_warnings():
        warnings.simplefilter(
            "ignore"
        )  # yfinance trips pandas 3 deprecation warnings on every call
        hist = yf.Ticker(ticker).history(period="max", auto_adjust=True)
    if hist is None or hist.empty or "Close" not in hist:
        raise ValueError("yfinance returned no data")
    closes = hist["Close"]
    closes.index = pd.to_datetime(closes.index.date)
    save_series(ticker, closes[~closes.index.duplicated(keep="last")])


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def read_french_csv(zip_bytes: bytes) -> pd.DataFrame:
    """Return the first (value-weighted) daily table of a French zip, as decimals."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        text = zf.read(zf.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(","))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.strip() or not line.strip()[0].isdigit():
            break
        block.append(line)
    df = pd.read_csv(io.StringIO("\n".join(block)), skipinitialspace=True)
    df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df = df.set_index("date").astype(float)
    return df.where(df > -99.0) / 100.0  # -99.99 and -999 mark missing data


def returns_to_levels(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.dropna()).cumprod()


def fetch_french() -> list[str]:
    industries = read_french_csv(download(FRENCH_BASE + FRENCH_INDUSTRIES))
    factors = read_french_csv(download(FRENCH_BASE + FRENCH_FACTORS))
    save_series(FRENCH_MARKET, returns_to_levels(factors["Mkt-RF"] + factors["RF"]))
    names = [FRENCH_MARKET]
    for col in industries.columns:
        name = f"FF49:{col.strip()}"
        save_series(name, returns_to_levels(industries[col]))
        names.append(name)
    return names


def run(refresh: bool) -> dict[str, str]:
    """Fetch everything. Returns {series name: 'ok' | 'cached' | 'FAILED: reason'}."""
    PRICES_DIR.mkdir(parents=True, exist_ok=True)
    status: dict[str, str] = {}
    for ticker in US_TICKERS + IN_TICKERS:
        if not refresh and is_fresh(series_path(ticker)):
            status[ticker] = "cached"
            continue
        try:
            fetch_yahoo(ticker)
            status[ticker] = "ok"
        except Exception as exc:  # report every failure in the table, never skip silently
            status[ticker] = f"FAILED: {exc}"
    if not refresh and is_fresh(series_path(FRENCH_MARKET)):
        status["FF49 + FF:Mkt"] = "cached"
    else:
        try:
            fetch_french()
            status["FF49 + FF:Mkt"] = "ok"
        except Exception as exc:
            status["FF49 + FF:Mkt"] = f"FAILED: {exc}"
    return status


def coverage_rows(names: list[str]) -> list[tuple[str, str, str, int]]:
    rows = []
    for name in names:
        s = load_series(name)
        rows.append((name, s.index[0].date().isoformat(), s.index[-1].date().isoformat(), len(s)))
    return rows


def print_coverage(status: dict[str, str]) -> None:
    print(f"{'series':<16} {'first':<10}  {'last':<10}  {'rows':>6}  status")
    for ticker in US_TICKERS + IN_TICKERS:
        state = status[ticker]
        if state.startswith("FAILED"):
            print(f"{ticker:<16} {'-':<10}  {'-':<10}  {'-':>6}  {state}")
            continue
        _, first, last, n = coverage_rows([ticker])[0]
        print(f"{ticker:<16} {first:<10}  {last:<10}  {n:>6}  {state}")
    french = status["FF49 + FF:Mkt"]
    if french.startswith("FAILED"):
        print(f"{'FF49 + FF:Mkt':<16} {'-':<10}  {'-':<10}  {'-':>6}  {french}")
        return
    ff = sorted(p.stem.replace("__", ":") for p in PRICES_DIR.glob("FF*.csv"))
    rows = coverage_rows(ff)
    first, last = min(r[1] for r in rows), max(r[2] for r in rows)
    print(f"{'FF:Mkt + FF49':<16} {first:<10}  {last:<10}  {rows[0][3]:>6}  {french} "
          f"({len(rows)} series: market + 49 industries, value-weighted)")  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="ignore the cache")
    args = parser.parse_args()
    status = run(args.refresh)
    print_coverage(status)
    failed = [name for name, state in status.items() if state.startswith("FAILED")]
    if failed:
        print(f"\n{len(failed)} series FAILED: {', '.join(failed)}")
        return 1
    print(f"\nall {len(status)} sources present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
