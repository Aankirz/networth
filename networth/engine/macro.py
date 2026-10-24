"""Macro series for the regime splits, and the regime rules that read them.

Run: uv run python -m networth.engine.macro

Every series is cached as data/macro/<NAME>.csv with columns date,value,released, date = the
first day of the observation month, released = the day that month was first published, where
known. data/macro/sources.json records where each came from (URL template, never the key), when,
and why a series is missing.

    USREC, FEDFUNDS, UNRATE              FRED, FRED_API_KEY from the environment or .env
    CPIAUCSL                             FRED/ALFRED initial releases: each month's first print
                                         and its first publication date
    IN_CPI                               MoSPI eSankhyiki, All-India CPI Combined General,
                                         the official year-on-year %, not an index level

Macro.load(as_of) is the vault's cut for macro data, as PriceBook.load is for prices: months
observed after as_of, and CPI prints released after as_of, are dropped before any rule sees
them. The rules in REGIMES are the only code that turns a date into a regime value.
"""

from __future__ import annotations

import csv
import datetime as dt
import functools
import json
import os
import ssl
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal, cast

import httpx2

from networth.engine.model import DATA_DIR, Episode, EventType, Region
from networth.net import IPV4_ANY, call_with_deadline, ipv4_client

MACRO_DIR: Final = DATA_DIR / "macro"
SOURCES_FILE: Final = "sources.json"
ENV_FILE: Final = DATA_DIR.parent / ".env"

RECESSION_WINDOW_MONTHS: Final = 12
INFLATION_HIGH_PCT: Final[Mapping[Region, float]] = {Region.US: 4.0, Region.IN: 6.0}
# Only for months with no recorded release date: US before ALFRED's archive, and all of India,
# whose CPI API publishes no release calendar.
CPI_RELEASE_LAG_DAYS: Final[Mapping[Region, int]] = {Region.US: 21, Region.IN: 14}

RegimeValue = Literal["yes", "no"]
YES: Final[RegimeValue] = "yes"
NO: Final[RegimeValue] = "no"
REGIME_VALUES: Final[tuple[RegimeValue, ...]] = (YES, NO)

USREC, US_CPI, IN_CPI = "USREC", "CPIAUCSL", "IN_CPI"
FRED_SERIES: Final = (USREC, US_CPI, "FEDFUNDS", "UNRATE")
FIRST_RELEASE_SERIES: Final = frozenset({US_CPI})
SERIES_TITLE: Final[Mapping[str, str]] = {
    USREC: "US recession months (USREC)", US_CPI: "US CPI", IN_CPI: "India CPI",
}  # fmt: skip
CPI_REGION: Final[Mapping[EventType, Region]] = {
    EventType.FED_HIKE: Region.US, EventType.FED_CUT: Region.US,
    EventType.RBI_HIKE: Region.IN, EventType.RBI_CUT: Region.IN,
}  # fmt: skip
CPI_SERIES: Final[Mapping[Region, str]] = {Region.US: US_CPI, Region.IN: IN_CPI}

TIMEOUT_S, CONNECT_TIMEOUT_S, DEADLINE_S = 60.0, 10.0, 90.0


def add_months(month: dt.date, k: int) -> dt.date:
    n = month.year * 12 + month.month - 1 + k
    return dt.date(n // 12, n % 12 + 1, 1)


def fixed_lag_release(month: dt.date, region: Region) -> dt.date:
    month_end = add_months(month, 1) - dt.timedelta(days=1)
    return month_end + dt.timedelta(days=CPI_RELEASE_LAG_DAYS[region])


@dataclass(frozen=True)
class MonthlySeries:
    name: str
    values: Mapping[dt.date, float]
    released: Mapping[dt.date, dt.date] = field(default_factory=dict)
    source: str = ""
    url_template: str = ""
    note: str = ""


@dataclass(frozen=True)
class Macro:
    """Everything the rules read, already cut at as_of."""

    usrec: Mapping[dt.date, float]  # month -> 1.0 inside an NBER recession, else 0.0
    cpi_yoy: Mapping[Region, Mapping[dt.date, float]]
    gaps: Mapping[str, str]
    cpi_released: Mapping[Region, Mapping[dt.date, dt.date]] = field(default_factory=dict)

    def release_date(self, month: dt.date, region: Region) -> dt.date:
        recorded = self.cpi_released.get(region, {}).get(month)
        return recorded or fixed_lag_release(month, region)

    def last_print_before(self, day: dt.date, region: Region) -> dt.date:
        """The newest CPI month whose release date is strictly before `day`."""
        month = day.replace(day=1)
        while self.release_date(month, region) >= day:
            month = add_months(month, -1)
        return month

    @classmethod
    def load(cls, directory: Path | None = None, as_of: dt.date | None = None) -> Macro:
        directory = directory or MACRO_DIR
        recorded = read_sources(directory)
        gaps: dict[str, str] = {}
        loaded: dict[str, MonthlySeries] = {}
        for name in (USREC, US_CPI, IN_CPI):
            series = load_series(name, directory)
            if series is None:
                gaps[name] = recorded.get(name, {}).get("gap") or (
                    f"no {name}.csv in {directory}: run python -m networth.engine.macro"
                )
            loaded[name] = series or MonthlySeries(name, {})
        # YoY of first prints is what M's release showed, except that M-12 may have been
        # revised by then.
        yoy = {Region.US: yoy_from_index(loaded[US_CPI].values), Region.IN: loaded[IN_CPI].values}
        full = cls(
            usrec=loaded[USREC].values,
            cpi_yoy={region: months for region, months in yoy.items() if months},
            gaps=gaps,
            cpi_released={region: loaded[name].released for region, name in CPI_SERIES.items()},
        )
        return full if as_of is None else full.cut(as_of)

    def cut(self, as_of: dt.date) -> Macro:
        """Months observed after as_of, and CPI prints released after as_of, dropped."""
        return Macro(
            usrec={m: v for m, v in self.usrec.items() if m <= as_of},
            cpi_yoy={
                region: {m: v for m, v in months.items() if self.release_date(m, region) <= as_of}
                for region, months in self.cpi_yoy.items()
            },
            gaps=self.gaps,
            cpi_released={
                region: {m: d for m, d in released.items() if d <= as_of}
                for region, released in self.cpi_released.items()
            },
        )


def yoy_from_index(index: Mapping[dt.date, float]) -> dict[dt.date, float]:
    return {
        m: (v / index[add_months(m, -12)] - 1.0) * 100.0
        for m, v in index.items()
        if add_months(m, -12) in index
    }


def recession_followed(day: dt.date, type_: EventType, macro: Macro) -> bool | None:
    """Any NBER recession month in M+1..M+12, M = the event's month. None until USREC covers
    the whole window."""
    month = day.replace(day=1)
    window = [add_months(month, k) for k in range(1, RECESSION_WINDOW_MONTHS + 1)]
    if any(m not in macro.usrec for m in window):
        return None
    return any(macro.usrec[m] == 1.0 for m in window)


def inflation_high(day: dt.date, type_: EventType, macro: Macro) -> bool | None:
    """YoY CPI of the last print released strictly before the event, at or above the region's
    threshold. None when that print is missing."""
    region = CPI_REGION[type_]
    yoy = macro.cpi_yoy.get(region, {}).get(macro.last_print_before(day, region))
    return None if yoy is None else yoy >= INFLATION_HIGH_PCT[region]


Classifier = Callable[[dt.date, EventType, Macro], bool | None]


@dataclass(frozen=True)
class RegimeRule:
    name: str
    hindsight: bool
    series_by_type: Mapping[EventType, str]
    classify: Classifier

    @property
    def types(self) -> frozenset[EventType]:
        return frozenset(self.series_by_type)


REGIMES: Final[Mapping[str, RegimeRule]] = {
    rule.name: rule
    for rule in (
        RegimeRule(
            "recession_followed",
            hindsight=True,
            series_by_type={EventType.FED_HIKE: USREC, EventType.FED_CUT: USREC},
            classify=recession_followed,
        ),
        RegimeRule(
            "inflation_high",
            hindsight=False,
            series_by_type={t: CPI_SERIES[region] for t, region in CPI_REGION.items()},
            classify=inflation_high,
        ),
    )
}


def regime_label(name: str, value: str) -> str:
    return f"{name}={value}"


def parse_label(label: str) -> tuple[RegimeRule, RegimeValue]:
    name, _, value = label.partition("=")
    if name not in REGIMES or value not in REGIME_VALUES:
        raise ValueError(
            f"unknown regime {label!r}; one of "
            f"{[regime_label(n, v) for n in REGIMES for v in REGIME_VALUES]}"
        )
    return REGIMES[name], cast(RegimeValue, value)


def episode_regimes(episode: Episode, macro: Macro) -> dict[str, RegimeValue]:
    """rule name -> yes/no for every rule that applies to the episode and can decide it, on
    the onset (the event whose reaction scores the episode)."""
    out = {}
    for rule in REGIMES.values():
        if episode.type in rule.types:
            decided = rule.classify(episode.onset.date, episode.type, macro)
            if decided is not None:
                out[rule.name] = YES if decided else NO
    return out


def series_path(name: str, directory: Path) -> Path:
    return directory / f"{name}.csv"


def save_series(series: MonthlySeries, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with series_path(series.name, directory).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "value", "released"])
        for m in sorted(series.values.keys() | series.released.keys()):
            value, released = series.values.get(m), series.released.get(m)
            writer.writerow([m, "" if value is None else repr(value), released or ""])


def load_series(name: str, directory: Path) -> MonthlySeries | None:
    path = series_path(name, directory)
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [(dt.date.fromisoformat(r["date"]), r) for r in csv.DictReader(fh)]
    return MonthlySeries(
        name,
        values={m: float(r["value"]) for m, r in rows if r["value"]},
        released={m: dt.date.fromisoformat(r["released"]) for m, r in rows if r.get("released")},
    )


def read_sources(directory: Path) -> dict[str, dict[str, str]]:
    path = directory / SOURCES_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


FRED_URL: Final = "https://api.stlouisfed.org/fred/series/observations"
FRED_FIRST_RELEASE: Final = {
    "output_type": "4", "realtime_start": "1776-07-04", "realtime_end": "9999-12-31",
}  # fmt: skip
MOSPI: Final = "https://api.mospi.gov.in/api/cpi"
MONTHS: Final = {
    name: i
    for i, name in enumerate(
        ("January", "February", "March", "April", "May", "June", "July", "August",
         "September", "October", "November", "December"),
        start=1,
    )
}  # fmt: skip


@dataclass(frozen=True)
class CpiSegment:
    label: str
    url_template: str
    first: dt.date
    last: dt.date | None
    is_all_india_general: Callable[[Mapping[str, object]], bool]


_GENERAL_2010_2012 = "state_code=99&sector_code=3&Format=JSON&limit=200&year={year}&page={page}"
# Each month comes from the base that was the official headline when that month was released:
# the 2012 base started with the January 2015 print (its 2013 rows carry no YoY), and the 2024
# base with the January 2026 print.
IN_CPI_SEGMENTS: Final = (
    CpiSegment(
        "CPI-C base 2010",
        f"{MOSPI}/getCPIIndex?base_year=2010&series=Current&{_GENERAL_2010_2012}",
        dt.date(2012, 1, 1),
        dt.date(2014, 12, 1),
        lambda r: r.get("group") == "General",
    ),
    CpiSegment(
        "CPI-C base 2012",
        f"{MOSPI}/getCPIIndex?base_year=2012&series=Current&group_code=0&{_GENERAL_2010_2012}",
        dt.date(2015, 1, 1),
        dt.date(2025, 12, 1),
        lambda r: r.get("group") == "General",
    ),
    CpiSegment(
        "CPI base 2024",
        f"{MOSPI}/getCPIData?base_year=2024&series=Current&state_code=1&sector_code=3"
        "&division_code=0&Format=JSON&limit=100&year={year}&page={page}",
        dt.date(2026, 1, 1),
        None,
        lambda r: r.get("division") == "CPI (General)",
    ),
)
IN_CPI_NOTE: Final = (
    "official YoY %; MoSPI publishes no CPI-Combined YoY before 2012-01 and none for 2020-04 "
    "and 2020-05 (COVID), so RBI events that would read those prints are unclassified"
)


def mospi_client() -> httpx2.Client:
    """MoSPI's server still needs TLS legacy renegotiation. Certificates are still verified."""
    context = ssl.create_default_context()
    context.options |= ssl.OP_LEGACY_SERVER_CONNECT
    transport = httpx2.HTTPTransport(local_address=IPV4_ANY, retries=0, verify=context)
    return httpx2.Client(
        transport=transport, timeout=httpx2.Timeout(TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
    )


def _get_json(client: httpx2.Client, url: str, what: str, params: Mapping | None = None):
    resp = call_with_deadline(lambda: client.get(url, params=params), DEADLINE_S, what)
    resp.raise_for_status()
    return resp.json()


def fetch_fred(series_id: str, client: httpx2.Client, first_release: bool) -> MonthlySeries:
    params = {"series_id": series_id, "api_key": fred_key(), "file_type": "json",
              **(FRED_FIRST_RELEASE if first_release else {})}  # fmt: skip
    body = _get_json(client, FRED_URL, f"FRED {series_id}", params)
    obs = {dt.date.fromisoformat(o["date"]): o for o in body["observations"]}
    if len(obs) != len(body["observations"]):
        raise ValueError(f"FRED {series_id}: two observations for one month")
    values = {m: float(o["value"]) for m, o in obs.items() if o["value"] != "."}  # "." = missing
    if not values:
        raise ValueError("FRED returned no observations")
    released = {}
    if first_release:
        # ALFRED's archive starts on its earliest realtime_start: months first seen that day
        # were published before it, on a day it does not record.
        archive_start = min(o["realtime_start"] for o in obs.values())
        released = {
            m: dt.date.fromisoformat(o["realtime_start"])
            for m, o in obs.items()
            if o["realtime_start"] != archive_start
        }
    shown = {**params, "api_key": "<FRED_API_KEY>"}
    url = f"{FRED_URL}?" + "&".join(f"{k}={v}" for k, v in shown.items())
    source = "FRED/ALFRED initial releases" if first_release else "FRED"
    return MonthlySeries(series_id, values, released, source, url)


def _mospi_rows(client: httpx2.Client, segment: CpiSegment, year: int) -> Iterator[Mapping]:
    page = 1
    while True:
        url = segment.url_template.format(year=year, page=page)
        body = _get_json(client, url, f"MoSPI {segment.label} {year}")
        yield from body.get("data") or []
        if page >= (body.get("meta_data") or {}).get("totalPages", 1):
            return
        page += 1


def fetch_in_cpi(client: httpx2.Client, today: dt.date) -> MonthlySeries:
    values: dict[dt.date, float] = {}
    for seg in IN_CPI_SEGMENTS:
        last = seg.last or today
        for year in range(seg.first.year, last.year + 1):
            for row in _mospi_rows(client, seg, year):
                month = dt.date(int(row["year"]), MONTHS[row["month"]], 1)
                if not (seg.is_all_india_general(row) and seg.first <= month <= last
                        and row.get("inflation")):  # fmt: skip
                    continue
                if month in values:
                    raise ValueError(f"MoSPI {seg.label}: two General rows for {month}")
                values[month] = float(row["inflation"])
    if not values:
        raise ValueError("MoSPI returned no All-India CPI rows")
    source = "MoSPI eSankhyiki: " + ", ".join(
        f"{s.label} {s.first:%Y-%m}..{f'{s.last:%Y-%m}' if s.last else 'now'}"
        for s in IN_CPI_SEGMENTS
    )
    url = " | ".join(s.url_template for s in IN_CPI_SEGMENTS)
    return MonthlySeries(IN_CPI, values, source=source, url_template=url, note=IN_CPI_NOTE)


def fred_key(env_file: Path = ENV_FILE) -> str:
    """FRED_API_KEY from the environment, else .env. Never printed."""
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and name.strip() == "FRED_API_KEY":
                key = value.strip().strip("'\"")
    if not key:
        raise RuntimeError("FRED_API_KEY is missing from the environment and .env")
    return key


def _redacted(exc: BaseException) -> str:
    """The error text with the FRED key cut out: httpx puts the request URL in its errors."""
    text = f"{type(exc).__name__}: {exc}"
    try:
        return text.replace(fred_key(), "<FRED_API_KEY>")
    except RuntimeError:
        return text


def fetchers(today: dt.date) -> dict[str, Callable[[], MonthlySeries]]:
    fred = ipv4_client(TIMEOUT_S, CONNECT_TIMEOUT_S)
    out: dict[str, Callable[[], MonthlySeries]] = {
        s: functools.partial(fetch_fred, s, fred, s in FIRST_RELEASE_SERIES) for s in FRED_SERIES
    }
    out[IN_CPI] = lambda: fetch_in_cpi(mospi_client(), today)
    return out


def run(directory: Path | None = None) -> dict[str, str]:
    """Download every series. Returns {name: 'ok' | 'FAILED: reason'}; a failure keeps any
    cached file, and with no cached file records the reason as a gap in sources.json."""
    directory = directory or MACRO_DIR
    directory.mkdir(parents=True, exist_ok=True)
    sources = read_sources(directory)
    status: dict[str, str] = {}
    now = dt.datetime.now(dt.UTC)
    for name, fetch in fetchers(now.date()).items():
        try:
            series = fetch()
        except Exception as exc:
            status[name] = f"FAILED: {_redacted(exc)}"
            if load_series(name, directory) is None:
                sources[name] = {"gap": status[name], "fetched_at": now.isoformat()}
            continue
        save_series(series, directory)
        sources[name] = {"source": series.source, "url": series.url_template, "note": series.note,
                         "fetched_at": now.isoformat(timespec="seconds"), "gap": ""}  # fmt: skip
        status[name] = "ok"
    (directory / SOURCES_FILE).write_text(json.dumps(sources, indent=1) + "\n", encoding="utf-8")
    return status


def print_coverage(status: Mapping[str, str], directory: Path | None = None) -> None:
    directory = directory or MACRO_DIR
    sources = read_sources(directory)
    print(f"{'series':<10} {'first':<7}  {'last':<7}  {'months':>6}  source / status")
    for name, state in status.items():
        series = load_series(name, directory)
        if series is None:
            print(f"{name:<10} {'-':<7}  {'-':<7}  {'-':>6}  GAP: {sources[name]['gap']}")
            continue
        values, released = series.values, series.released
        first, last = min(values), max(values)
        info = sources.get(name, {})
        print(f"{name:<10} {first:%Y-%m}  {last:%Y-%m}  {len(values):>6}  "
              f"{info.get('source', '?')} [{state}]")  # fmt: skip
        if released:
            print(f"{'':<10} release dates for {len(released)} months, "
                  f"{min(released):%Y-%m}..{max(released):%Y-%m}")  # fmt: skip
        if info.get("note"):
            print(f"{'':<10} note: {info['note']}")


def main() -> int:
    status = run()
    print_coverage(status)
    failed = [name for name, state in status.items() if state.startswith("FAILED")]
    if failed:
        print(f"\n{len(failed)} series FAILED: {', '.join(failed)}")
        return 1
    print(f"\nall {len(status)} series present in {MACRO_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
