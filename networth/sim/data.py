"""The aligned monthly return table the plan range resamples, cached as data/sim/returns.csv.

Run: uv run python -m networth.sim.data

Columns month,safety,core,growth,cpi hold each calendar month's return as a decimal (cpi is the
month's inflation). Every row is a month in which all four series have a value, from the first
such month to the last complete one, with no gaps. data/sim/sources.json records each series'
URL, its window and when it was fetched. A missing series stops the build with one line.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from networth.engine import macro
from networth.net import call_with_deadline, ipv4_client
from networth.sim import config

YAHOO_DEADLINE_S = 120.0


class MissingSeries(RuntimeError):
    """A series the table needs is absent or has a hole. The message is one printable line."""


@dataclass(frozen=True)
class Table:
    months: tuple[dt.date, ...]
    returns: np.ndarray  # (len(months), len(config.COLUMNS)), decimals, columns in COLUMNS order

    def column(self, name: str) -> np.ndarray:
        return self.returns[:, config.COLUMNS.index(name)]


def month_of(day: dt.date) -> dt.date:
    return day.replace(day=1)


def equity_returns(closes: Mapping[dt.date, float]) -> dict[dt.date, float]:
    """Month m's return: m's last close over the previous month's last close, minus 1."""
    last: dict[dt.date, tuple[dt.date, float]] = {}
    for day, close in closes.items():
        m = month_of(day)
        if m not in last or day > last[m][0]:
            last[m] = (day, close)
    ends = {m: close for m, (_, close) in last.items()}
    return {m: ends[m] / ends[prev] - 1.0 for m in ends
            if (prev := macro.add_months(m, -1)) in ends}  # fmt: skip


def rate_returns(rates_pct: Mapping[dt.date, float]) -> dict[dt.date, float]:
    return {m: (1.0 + r / 100.0) ** (1 / 12) - 1.0 for m, r in rates_pct.items()}


def filled_yoy(yoy: Mapping[dt.date, float]) -> dict[dt.date, float]:
    """Interior holes of up to CPI_MAX_FILL_MONTHS months take the straight line across."""
    out = dict(yoy)
    months = sorted(yoy)
    for a, b in zip(months, months[1:], strict=False):
        gap = (b.year - a.year) * 12 + b.month - a.month - 1
        if 0 < gap <= config.CPI_MAX_FILL_MONTHS:
            for k in range(1, gap + 1):
                out[macro.add_months(a, k)] = yoy[a] + (yoy[b] - yoy[a]) * k / (gap + 1)
    return out


def spliced(early: Mapping[dt.date, float], late: Mapping[dt.date, float]) -> dict[dt.date, float]:
    """The late series from its first month on, the early one before it."""
    switch = min(late)
    return {**{m: v for m, v in early.items() if m < switch}, **late}


def build_table(series: Mapping[str, Mapping[dt.date, float]], before: dt.date) -> Table:
    """Monthly returns by column -> the gap-free table of months before `before`, the first
    incomplete month. Raises MissingSeries when a column is empty or the window has a hole."""
    for name in config.COLUMNS:
        if not series.get(name):
            raise MissingSeries(f"sim table: no {name} data; see docs/phases/phase-6-method.md")
    start = max(min(series[n]) for n in config.COLUMNS)
    end = min(max(m for m in series[n] if m < before) for n in config.COLUMNS)
    months: list[dt.date] = []
    m = start
    while m <= end:
        missing = [n for n in config.COLUMNS if m not in series[n]]
        if missing:
            raise MissingSeries(f"sim table: {', '.join(missing)} has no value for {m:%Y-%m}")
        months.append(m)
        m = macro.add_months(m, 1)
    returns = np.array([[series[n][m] for n in config.COLUMNS] for m in months], dtype=float)
    return Table(tuple(months), returns)


def save_table(table: Table, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / config.TABLE_FILE).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["month", *config.COLUMNS])
        for m, row in zip(table.months, table.returns, strict=True):
            writer.writerow([m.isoformat(), *(repr(float(v)) for v in row)])


def load_table(directory: Path | None = None) -> Table:
    path = (directory or config.SIM_DIR) / config.TABLE_FILE
    if not path.exists():
        raise MissingSeries(f"no {path}: run uv run python -m networth.sim.data")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    months = tuple(dt.date.fromisoformat(r["month"]) for r in rows)
    returns = np.array([[float(r[n]) for n in config.COLUMNS] for r in rows], dtype=float)
    return Table(months, returns)


def yahoo_closes(ticker: str) -> dict[dt.date, float]:
    import yfinance as yf

    def fetch():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # yfinance trips pandas 3 deprecation warnings
            return yf.Ticker(ticker).history(period="max", auto_adjust=True)

    hist = call_with_deadline(fetch, YAHOO_DEADLINE_S, f"Yahoo {ticker}")
    if hist is None or hist.empty or "Close" not in hist:
        raise MissingSeries(f"sim table: Yahoo returned no data for {ticker}")
    closes = hist["Close"].dropna()
    return {ts.date(): float(v) for ts, v in closes.items() if v > 0}


def fetch_series() -> dict[str, dict[dt.date, float]]:
    cpi = macro.load_series(macro.IN_CPI, macro.MACRO_DIR)
    if cpi is None or not cpi.values:
        raise MissingSeries("sim table: no India CPI; run uv run python -m networth.engine.macro")
    client = ipv4_client(macro.TIMEOUT_S, macro.CONNECT_TIMEOUT_S)

    def fred(series_id: str) -> dict[dt.date, float]:
        return dict(macro.fetch_fred(series_id, client, first_release=False).values)

    return {
        "safety": spliced(rate_returns(fred(config.SAFETY_EARLY_FRED_ID)),
                          rate_returns(fred(config.SAFETY_FRED_ID))),
        "core": equity_returns(yahoo_closes(config.CORE_TICKER)),
        "growth": equity_returns(yahoo_closes(config.GROWTH_TICKER)),
        "cpi": spliced(equity_returns(fred(config.CPI_EARLY_FRED_ID)),
                       rate_returns(filled_yoy(cpi.values))),
    }  # fmt: skip


def write_sources(series: Mapping[str, Mapping[dt.date, float]], table: Table,
                  directory: Path) -> None:  # fmt: skip
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    out = {
        "fetched_at": now,
        "window": [f"{table.months[0]:%Y-%m}", f"{table.months[-1]:%Y-%m}"],
        "months": len(table.months),
        "series": {
            name: {
                **config.SOURCES[name],
                "first": f"{min(series[name]):%Y-%m}",
                "last": f"{max(series[name]):%Y-%m}",
            }  # fmt: skip
            for name in config.COLUMNS
        },
    }
    (directory / config.SOURCES_FILE).write_text(json.dumps(out, indent=1) + "\n", "utf-8")


def main() -> int:
    try:
        series = fetch_series()
        table = build_table(series, month_of(dt.date.today()))
    except Exception as exc:  # noqa: BLE001 - one clear line, then a non-zero exit
        print(f"FAILED: {macro._redacted(exc)}", file=sys.stderr)
        return 1
    save_table(table, config.SIM_DIR)
    write_sources(series, table, config.SIM_DIR)
    print(f"{len(table.months)} months, {table.months[0]:%Y-%m}..{table.months[-1]:%Y-%m}, "
          f"in {config.SIM_DIR / config.TABLE_FILE}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
