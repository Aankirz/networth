"""Turn events.csv and data/prices/ into data/base_rates.sqlite.

Run: uv run python -m networth.engine.backtest [--exclude-vault] [--out PATH]

    events.csv --parse_events--> Event[] --merge_episodes(calendar)--> Episode[]
    data/prices --PriceBook.load(as_of)--> PriceBook --panel(asset, era)--> Panel
    (Event, Panel, horizon) --react--> Reaction        # the no-peeking rule lives here only
    (Panel, horizon) --baseline_hit_rate--> float
    Reaction[] of episode onsets --summarize--> BaseRate
    (same onsets, same baseline) filtered by macro.REGIMES value --> RegimeRate
    Build --model.write_db--> sqlite

--exclude-vault is one parameter, as_of = 2021-12-31, applied at the two inputs: events after
as_of are dropped before episodes are merged, and every price after as_of is removed from the
PriceBook. Nothing downstream knows about the vault, so nothing downstream can leak it. Macro
data is cut the same way by macro.Macro.load(as_of).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import re
import sys
import zlib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from networth.engine import fetch, macro
from networth.engine.model import (
    DEFAULT_DB,
    PRE_VAULT_DB,
    VAULT_START,
    BaseRate,
    Build,
    BuildMeta,
    Episode,
    EraName,
    Event,
    EventType,
    KnownTime,
    Market,
    Measure,
    Reaction,
    RegimeRate,
    Region,
    UnknownTime,
    is_hit,
    summarize,
    write_db,
)

EVENTS_CSV: Final = Path(__file__).with_name("events.csv")

# Rules fixed before any result was looked at (2026-10-24). Changing one is a method change and
# goes in the phase report.
HORIZONS: Final[Mapping[EventType, int]] = {
    # The user decides once a month, on investing day, so the default horizon is one month of
    # sessions (21). Policy moves, budgets, tariffs, elections, rupee shocks and conflicts are
    # priced within days, and a month covers the follow-through and the next data print.
    EventType.OIL_SUPPLY: 21,
    EventType.FED_HIKE: 21,
    EventType.FED_CUT: 21,
    EventType.RBI_HIKE: 21,
    EventType.RBI_CUT: 21,
    EventType.UNION_BUDGET: 21,
    EventType.INR_SHOCK: 21,
    EventType.MILITARY_CONFLICT: 21,
    EventType.TARIFF: 21,
    EventType.ELECTION: 21,
    # Contagion and pandemics unfold over a quarter, not a month (LTCM 1998, 2008, SVB 2023,
    # March 2020), so one quarter of sessions.
    EventType.BANK_STRESS: 63,
    EventType.PANDEMIC: 63,
}
if set(HORIZONS) != set(EventType):
    raise RuntimeError(f"HORIZONS is missing {set(EventType) - set(HORIZONS)}")

EPISODE_GAP_SESSIONS: Final = 21
BASELINE_WINDOWS: Final = 1000
BASELINE_SEED: Final = 20261024
MAX_ENTRY_GAP_DAYS: Final = 10  # a "first usable session" further away than this is a data hole

MARKET_CLOSE: Final[Mapping[Market, tuple[dt.time, ZoneInfo]]] = {
    Market.US: (dt.time(16, 0), ZoneInfo("America/New_York")),
    Market.IN: (dt.time(15, 30), ZoneInfo("Asia/Kolkata")),
}

NIFTY_START: Final = dt.date(2007, 9, 17)


@dataclass(frozen=True)
class Benchmark:
    """label is what rows show. components are the series it is built from: one series, or
    a per-day splice that takes the first component's daily return where it has one, else the
    next one's. A measured series that is a component is the market itself and scores raw."""

    label: str
    components: tuple[str, ...]


SPY_BENCH: Final = Benchmark("SPY", ("SPY",))
FRENCH_BENCH: Final = Benchmark(fetch.FRENCH_MARKET, (fetch.FRENCH_MARKET,))
INDIA_BENCH: Final = Benchmark(f"^NSEI (^BSESN before {NIFTY_START})", ("^NSEI", "^BSESN"))


@dataclass(frozen=True)
class Era:
    """One era. proxied=True measures the asset's French industry proxy instead of the asset.

    An older, non-proxied era includes an asset only if the asset's own series starts before
    the newest era of that market starts; otherwise it would repeat the newer era. That rule is
    why ^NSEBANK has no since_1997 row and the Sensex does.
    """

    name: EraName
    market: Market
    start: dt.date
    benchmark: Benchmark
    proxied: bool


ERAS: Final[tuple[Era, ...]] = (  # newest first within each market
    Era(EraName.SINCE_1998, Market.US, dt.date(1998, 12, 22), SPY_BENCH, proxied=False),
    Era(EraName.SINCE_1926, Market.US, dt.date(1926, 7, 1), FRENCH_BENCH, proxied=True),
    Era(EraName.SINCE_2007, Market.IN, NIFTY_START, INDIA_BENCH, proxied=False),
    Era(EraName.SINCE_1997, Market.IN, dt.date(1997, 7, 1), INDIA_BENCH, proxied=False),
)

FRENCH_PROXY: Final[Mapping[str, str]] = {
    "SPY": "FF:Mkt", "^GSPC": "FF:Mkt", "^SP500TR": "FF:Mkt",
    "JETS": "FF49:Trans",  # airlines sit inside Transportation
    "XLB": "FF49:Chems", "XLE": "FF49:Oil", "XLF": "FF49:Banks", "XLI": "FF49:Mach",
    "XLK": "FF49:Chips", "XLP": "FF49:Food", "XLU": "FF49:Util", "XLV": "FF49:Drugs",
    "XLY": "FF49:Rtail", "XLRE": "FF49:RlEst", "XLC": "FF49:Telcm",
}  # fmt: skip
if not set(FRENCH_PROXY) <= set(fetch.US_TICKERS):
    raise RuntimeError("FRENCH_PROXY names an asset fetch.py does not download")

ASSETS: Final[tuple[str, ...]] = tuple(fetch.US_TICKERS + fetch.IN_TICKERS)
US_CALENDAR_SERIES: Final = ("SPY", fetch.FRENCH_MARKET)
IN_CALENDAR_SERIES: Final = "^BSESN"


def market_of(asset: str) -> Market:
    if asset in fetch.US_TICKERS:
        return Market.US
    if asset in fetch.IN_TICKERS:
        return Market.IN
    raise ValueError(f"unknown asset {asset!r}")


# ---- events and episodes --------------------------------------------------------------------


@dataclass(frozen=True)
class RowProblem:
    line: int  # 1-based line in the CSV, header is line 1
    event_id: str | None
    field: str
    message: str


REQUIRED_FIELDS: Final = ("id", "date", "tz", "region", "type", "cause", "headline", "source_url")
CSV_COLUMNS: Final = (
    "id", "date", "time_known", "tz", "region", "type", "cause", "headline", "source_url", "notes",
)  # fmt: skip
_HHMM: Final = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_ISO_DATE: Final = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_row(line: int, row: Mapping[str, str]) -> tuple[Event | None, list[RowProblem]]:
    rid = (row.get("id") or "").strip() or None
    problems: list[RowProblem] = []

    def bad(field_name: str, message: str) -> None:
        problems.append(RowProblem(line, rid, field_name, message))

    for name in REQUIRED_FIELDS:
        if not (row.get(name) or "").strip():
            bad(name, "required field is empty")
    raw_date, hhmm = (row.get("date") or "").strip(), (row.get("time_known") or "").strip()
    day = tz = None
    if raw_date:
        try:
            if not _ISO_DATE.match(raw_date):
                raise ValueError
            day = dt.date.fromisoformat(raw_date)
        except ValueError:
            bad("date", f"{raw_date!r} is not an ISO date (YYYY-MM-DD)")
    if hhmm and not _HHMM.match(hhmm):
        bad("time_known", f"{hhmm!r} is not HH:MM")
    if raw_tz := (row.get("tz") or "").strip():
        try:
            tz = ZoneInfo(raw_tz)
        except (ZoneInfoNotFoundError, ValueError):
            bad("tz", f"{raw_tz!r} is not an IANA time zone")
    region, type_ = (row.get("region") or "").strip(), (row.get("type") or "").strip()
    if region and region not in Region.__members__.values():
        bad("region", f"{region!r} is not one of {[r.value for r in Region]}")
    if type_ and type_ not in EventType.__members__.values():
        bad("type", f"{type_!r} is not one of {[t.value for t in EventType]}")
    url = (row.get("source_url") or "").strip()
    if url and not url.startswith(("http://", "https://")):
        bad("source_url", f"{url!r} is not an http(s) URL")
    if problems or day is None or tz is None:
        return None, problems
    when = (
        KnownTime(dt.datetime.combine(day, dt.time.fromisoformat(hhmm), tz))
        if hhmm
        else UnknownTime(day)
    )
    event = Event(
        id=rid or "",
        date=day,
        time=when,
        tz=raw_tz,
        region=Region(region),
        type=EventType(type_),
        cause=row["cause"].strip(),
        headline=row["headline"].strip(),
        sources=(url,),
        notes=(row.get("notes") or "").strip(),
    )
    return event, []


def parse_events(path: Path = EVENTS_CSV) -> tuple[list[Event], list[RowProblem]]:
    """Parse every row, collecting every problem instead of stopping at the first. Rows with
    problems are left out. check_events reports them; build() refuses to run on any."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            return [], [RowProblem(1, None, c, "column missing from header") for c in missing]
        rows = list(reader)
    events: list[Event] = []
    problems: list[RowProblem] = []
    seen: dict[str, int] = {}
    for line, row in enumerate(rows, start=2):
        event, row_problems = _parse_row(line, row)
        problems += row_problems
        rid = (row.get("id") or "").strip()
        if rid and rid in seen:
            problems.append(RowProblem(line, rid, "id", f"duplicate of line {seen[rid]}"))
            continue
        if rid:
            seen[rid] = line
        if event is not None:
            events.append(event)
    return events, problems


@dataclass(frozen=True)
class EpisodeCalendars:
    """Trading days for counting episode gaps: US sessions, and Indian sessions for pairs of
    events that are both region `in`. An India pair the Indian calendar does not cover (before
    the Sensex data starts) is counted on the US calendar."""

    us: pd.DatetimeIndex
    india: pd.DatetimeIndex

    def sessions_between(self, a: Event, b: Event) -> int:
        """Trading days in (a.date, b.date]."""
        cal = self.us
        if a.region is Region.IN and b.region is Region.IN and len(self.india):
            if self.india[0].date() <= a.date and b.date <= self.india[-1].date():
                cal = self.india
        lo = cal.searchsorted(pd.Timestamp(a.date), side="right")
        hi = cal.searchsorted(pd.Timestamp(b.date), side="right")
        return int(hi - lo)


def merge_episodes(events: Iterable[Event], calendars: EpisodeCalendars) -> list[Episode]:
    """Chain same-type events at most EPISODE_GAP_SESSIONS trading days after the previous
    event in the chain (single linkage). The id comes from the onset, so it is stable."""
    by_type: dict[EventType, list[Event]] = {}
    for e in sorted(events, key=lambda e: (e.date, e.id)):
        by_type.setdefault(e.type, []).append(e)
    episodes: list[Episode] = []
    for type_, evs in by_type.items():
        chain = [evs[0]]
        for ev in evs[1:]:
            if calendars.sessions_between(chain[-1], ev) <= EPISODE_GAP_SESSIONS:
                chain.append(ev)
                continue
            episodes.append(Episode(f"{type_.value}:{chain[0].id}", type_, tuple(chain)))
            chain = [ev]
        episodes.append(Episode(f"{type_.value}:{chain[0].id}", type_, tuple(chain)))
    return sorted(episodes, key=lambda ep: (ep.onset.date, ep.id))


# ---- prices ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Panel:
    """Aligned closes for one (asset, era): sessions where both the measured series and the
    benchmark have a close, within [era.start, as_of]. close_utc[i] is the market close
    instant of sessions[i] (DST-correct) as int64 ns."""

    asset: str
    era: EraName
    market: Market
    series: str
    benchmark: str
    measure: Measure
    sessions: pd.DatetimeIndex
    close_utc: np.ndarray
    series_close: np.ndarray
    bench_close: np.ndarray

    def hit(self, raw: np.ndarray | float, bench: np.ndarray | float) -> np.ndarray | bool:
        return (raw if self.measure == "raw" else raw - bench) > 0


def close_instants(sessions: pd.DatetimeIndex, market: Market) -> np.ndarray:
    close, zone = MARKET_CLOSE[market]
    local = sessions + pd.Timedelta(hours=close.hour, minutes=close.minute)
    return local.tz_localize(zone).tz_convert("UTC").as_unit("ns").asi8.copy()


def make_panel(
    asset: str, era: EraName, market: Market, series: pd.Series, bench: pd.Series,
    bench_label: str, measure: Measure,
) -> Panel:  # fmt: skip
    joined = pd.concat([series, bench], axis=1, join="inner").dropna()
    sessions = pd.DatetimeIndex(joined.index)
    return Panel(
        asset=asset,
        era=era,
        market=market,
        series=str(series.name),
        benchmark=bench_label,
        measure=measure,
        sessions=sessions,
        close_utc=close_instants(sessions, market),
        series_close=joined.iloc[:, 0].to_numpy(dtype=float),
        bench_close=joined.iloc[:, 1].to_numpy(dtype=float),
    )


def splice(components: Sequence[pd.Series]) -> pd.Series:
    """One level series from per-day returns: the first component's return where it has
    closes on both the previous and the current union day, else the next component's."""
    union = components[0].index
    for s in components[1:]:
        union = union.union(s.index)
    returns = pd.Series(np.nan, index=union)
    for s in components:
        r = s.reindex(union).pct_change(fill_method=None)
        returns = returns.fillna(r)
    first_day = max(min(s.index[0] for s in components), union[0])
    returns = returns[returns.index > first_day].dropna()
    level = (1.0 + returns).cumprod()
    return pd.concat([pd.Series([1.0], index=[first_day]), level])


@dataclass
class PriceBook:
    """Every stored series, already cut at as_of. The cut is the vault's only enforcement."""

    closes: Mapping[str, pd.Series]
    as_of: dt.date | None
    _bench_cache: dict[str, pd.Series] = field(default_factory=dict)

    @classmethod
    def load(cls, prices_dir: Path | None = None, as_of: dt.date | None = None) -> PriceBook:
        directory = prices_dir or fetch.PRICES_DIR
        closes = {}
        for path in sorted(directory.glob("*.csv")):
            name = path.stem.replace("__", ":")
            s = fetch.load_series(name, directory)
            if as_of is not None:
                s = s[s.index <= pd.Timestamp(as_of)]
            if len(s):
                closes[name] = s
        return cls(closes, as_of)

    def benchmark(self, bench: Benchmark) -> pd.Series | None:
        if bench.label not in self._bench_cache:
            parts = [self.closes[c] for c in bench.components if c in self.closes]
            if len(parts) != len(bench.components):
                return None
            self._bench_cache[bench.label] = parts[0] if len(parts) == 1 else splice(parts)
        return self._bench_cache[bench.label]

    def calendars(self) -> EpisodeCalendars:
        us = pd.DatetimeIndex([])
        for name in US_CALENDAR_SERIES:
            if name in self.closes:
                us = us.union(self.closes[name].index)
        india = self.closes.get(IN_CALENDAR_SERIES)
        return EpisodeCalendars(us, pd.DatetimeIndex(india.index if india is not None else []))

    def panel(self, asset: str, era: Era) -> Panel | None:
        """None when the era does not apply to the asset or the data is missing."""
        market = market_of(asset)
        if era.market != market:
            return None
        series_name = FRENCH_PROXY.get(asset) if era.proxied else asset
        if series_name is None or series_name not in self.closes:
            return None
        newest = next(e for e in ERAS if e.market == market)
        own = self.closes.get(asset)
        if not era.proxied and era is not newest:
            if own is None or own.index[0].date() >= newest.start:
                return None
        bench = self.benchmark(era.benchmark)
        if bench is None:
            return None
        series = self.closes[series_name]
        series = series[series.index >= pd.Timestamp(era.start)]
        measure: Measure = "raw" if series_name in era.benchmark.components else "excess"
        panel = make_panel(
            asset, era.name, market, series, bench, era.benchmark.label, measure
        )  # fmt: skip
        return panel if len(panel.sessions) else None


# ---- the no-peeking rule: the only code that turns an event time into a price index ---------


def entry_index(event: Event, panel: Panel) -> int | None:
    """Index of the event's first usable session.

    Known time: the first session whose close is strictly after the instant (an event at
    exactly 16:00 New York counts from the next session). Unknown time: the first session
    dated strictly after the event's local date, in every market.

    None when that session is the panel's first (the true one may predate the data) or lies
    more than MAX_ENTRY_GAP_DAYS after the event date (a data hole).
    """
    match event.time:
        case KnownTime(at):
            instant = pd.Timestamp(at).tz_convert("UTC").value
            i = int(np.searchsorted(panel.close_utc, instant, side="right"))
        case UnknownTime(local_date):
            i = int(panel.sessions.searchsorted(pd.Timestamp(local_date), side="right"))
    if i == 0 or i == len(panel.sessions):
        return None
    if (panel.sessions[i].date() - event.date).days > MAX_ENTRY_GAP_DAYS:
        return None
    return i


def reaction_between(event: Event, panel: Panel, i: int, j: int) -> Reaction:
    """The Reaction for entry session i and exit session j. Reads closes i-1 (day 0 only),
    i and j."""
    s, b = panel.series_close, panel.bench_close
    raw, bench = s[j] / s[i] - 1.0, b[j] / b[i] - 1.0
    day0_raw = s[i] / s[i - 1] - 1.0
    day0_bench = b[i] / b[i - 1] - 1.0
    return Reaction(
        event_id=event.id,
        asset=panel.asset,
        era=panel.era,
        horizon_days=j - i,
        series=panel.series,
        benchmark=panel.benchmark,
        entry_date=panel.sessions[i].date(),
        exit_date=panel.sessions[j].date(),
        raw_return=float(raw),
        bench_return=float(bench),
        day0_raw=float(day0_raw),
        day0_excess=float(day0_raw - day0_bench),
    )


def react(event: Event, panel: Panel, horizon: int) -> Reaction | None:
    """close(entry) -> close(entry + horizon), for the series and the benchmark. None when an
    end is outside the panel, which is also how a pre-vault build drops windows ending in 2022."""
    i = entry_index(event, panel)
    if i is None or i + horizon >= len(panel.sessions):
        return None
    return reaction_between(event, panel, i, i + horizon)


# ---- baseline and rows ----------------------------------------------------------------------


def baseline_seed(panel: Panel, horizon: int) -> int:
    """crc32 of (BASELINE_SEED, series, benchmark, era, horizon): any row reproduces on its own,
    whatever the build order."""
    key = f"{BASELINE_SEED}|{panel.series}|{panel.benchmark}|{panel.era.value}|{horizon}"
    return zlib.crc32(key.encode())


def baseline_hit_rate(
    panel: Panel, horizon: int, *, n: int = BASELINE_WINDOWS, seed: int | None = None
) -> float:
    """Hit rate over n windows of `horizon` sessions, entries drawn with replacement from every
    valid entry session of the panel (index 1 on, as for events)."""
    last_entry = len(panel.sessions) - horizon
    if last_entry <= 1:
        raise ValueError(f"{panel.asset}/{panel.era}: panel too short for horizon {horizon}")
    rng = np.random.default_rng(baseline_seed(panel, horizon) if seed is None else seed)
    starts = rng.integers(1, last_entry, size=n)
    s, b = panel.series_close, panel.bench_close
    raw = s[starts + horizon] / s[starts] - 1.0
    bench = b[starts + horizon] / b[starts] - 1.0
    return float(np.mean(panel.hit(raw, bench)))


def base_rate_row(
    type_: EventType,
    cause: str | None,
    panel: Panel,
    scored: Sequence[tuple[Episode, Reaction]],
    baseline: float,
) -> BaseRate:
    measured = [r.raw_return if panel.measure == "raw" else r.excess_return for _, r in scored]
    hits = [is_hit(panel.measure, r.raw_return, r.excess_return) for _, r in scored]
    stats = summarize(measured, hits)
    raw = summarize([r.raw_return for _, r in scored], hits)
    return BaseRate(
        type=type_,
        cause=cause,
        asset=panel.asset,
        market=panel.market,
        horizon_days=HORIZONS[type_],
        era=panel.era,
        n_events=sum(len(ep.events) for ep, _ in scored),
        n_episodes=stats.n,
        n_hits=stats.n_hits,
        hit_rate=stats.hit_rate,
        baseline_hit_rate=baseline,
        median=stats.median,
        p10=stats.p10,
        p90=stats.p90,
        episode_ids=tuple(ep.id for ep, _ in scored),
        includes_vault=any(ep.in_vault for ep, _ in scored),
        measure=panel.measure,
        series=panel.series,
        benchmark=panel.benchmark,
        data_start=panel.sessions[0].date(),
        data_end=panel.sessions[-1].date(),
        raw_median=raw.median,
        raw_p10=raw.p10,
        raw_p90=raw.p90,
    )


EpisodeRegimes = Mapping[str, Mapping[str, macro.RegimeValue]]


def regime_rows(
    type_: EventType,
    cause: str | None,
    panel: Panel,
    scored: Sequence[tuple[Episode, Reaction]],
    baseline: float,
    regimes: EpisodeRegimes,
) -> list[RegimeRate]:
    """The same row restricted to each regime value. Only the episode set changes: same
    reactions, same baseline, same base_rate_row."""
    out = []
    for rule in macro.REGIMES.values():
        if type_ not in rule.types:
            continue
        for value in macro.REGIME_VALUES:
            sub = [(ep, r) for ep, r in scored if regimes.get(ep.id, {}).get(rule.name) == value]
            if sub:
                row = base_rate_row(type_, cause, panel, sub, baseline)
                out.append(RegimeRate(macro.regime_label(rule.name, value), rule.hindsight, row))
    return out


def rows_for_panel(
    panel: Panel,
    events: Sequence[Event],
    episodes: Sequence[Episode],
    regimes: EpisodeRegimes = MappingProxyType({}),
) -> tuple[list[Reaction], list[BaseRate], list[RegimeRate]]:
    reactions = {e.id: r for e in events if (r := react(e, panel, HORIZONS[e.type]))}
    baselines: dict[int, float] = {}
    rows: list[BaseRate] = []
    by_regime: list[RegimeRate] = []
    for type_ in EventType:
        eps = [ep for ep in episodes if ep.type == type_]
        for cause in (None, *sorted({ep.cause for ep in eps})):
            scored = [
                (ep, reactions[ep.onset.id])
                for ep in eps
                if (cause is None or ep.cause == cause) and ep.onset.id in reactions
            ]
            if not scored:
                continue
            h = HORIZONS[type_]
            if h not in baselines:
                baselines[h] = baseline_hit_rate(panel, h)
            rows.append(base_rate_row(type_, cause, panel, scored, baselines[h]))
            by_regime += regime_rows(type_, cause, panel, scored, baselines[h], regimes)
    return list(reactions.values()), rows, by_regime


# ---- the build ------------------------------------------------------------------------------


def build(
    events_csv: Path = EVENTS_CSV,
    prices_dir: Path | None = None,
    *,
    exclude_vault: bool = False,
    macro_dir: Path | None = None,
) -> Build:
    """events + prices (+ cached macro series) -> Build. Raises ValueError listing every
    RowProblem. Missing macro series only drop the regime rows that need them."""
    as_of = VAULT_START - dt.timedelta(days=1) if exclude_vault else None
    events, problems = parse_events(events_csv)
    if problems:
        listing = "\n".join(f"  line {p.line} {p.field}: {p.message}" for p in problems)
        raise ValueError(f"{events_csv} has {len(problems)} problems:\n{listing}")
    events = [e for e in events if as_of is None or e.date <= as_of]
    book = PriceBook.load(prices_dir, as_of)
    episodes = merge_episodes(events, book.calendars())
    macro_data = macro.Macro.load(macro_dir, as_of)
    regimes = {ep.id: macro.episode_regimes(ep, macro_data) for ep in episodes}
    all_reactions: list[Reaction] = []
    all_rows: list[BaseRate] = []
    all_regime_rows: list[RegimeRate] = []
    for asset in ASSETS:
        for era in ERAS:
            panel = book.panel(asset, era)
            if panel is None or len(panel.sessions) <= max(HORIZONS.values()) + 1:
                continue
            reactions, rows, by_regime = rows_for_panel(panel, events, episodes, regimes)
            all_reactions += reactions
            all_rows += rows
            all_regime_rows += by_regime
    meta = BuildMeta(
        as_of=as_of,
        baseline_seed=BASELINE_SEED,
        baseline_windows=BASELINE_WINDOWS,
        horizons=dict(HORIZONS),
        events_sha256=hashlib.sha256(events_csv.read_bytes()).hexdigest(),
        skipped_series=tuple(a for a in ASSETS if a not in book.closes),
        built_at=dt.datetime.now(dt.UTC),
        macro_gaps=dict(macro_data.gaps),
    )
    return Build(
        meta, tuple(events), tuple(episodes), tuple(all_reactions), tuple(all_rows),
        tuple(all_regime_rows),
    )  # fmt: skip


def summary(result: Build, out: Path) -> str:
    rows = result.base_rates
    lines = [
        f"wrote {out}",
        f"as_of {result.meta.as_of or 'all data'}: {len(result.events)} events, "
        f"{len(result.episodes)} episodes, {len(result.reactions)} reactions, "
        f"{len(rows)} base-rate rows",
        "",
        f"{'type':<18} {'episodes':>8} {'rows':>6}",
    ]
    eps = Counter(ep.type for ep in result.episodes)
    per_type = Counter(r.type for r in rows)
    lines += [f"{t.value:<18} {eps[t]:>8} {per_type[t]:>6}" for t in EventType]
    eras: dict[str, list[str]] = {}
    for r in rows:
        if r.cause is None and r.type is EventType.OIL_SUPPLY:
            eras.setdefault(r.asset, []).append(r.era.value)
    lines += ["", "eras per asset (oil_supply rows):"]
    lines += [f"  {a:<14} {', '.join(e)}" for a, e in eras.items()]
    skipped = result.meta.skipped_series
    lines += ["", f"skipped series (no price file): {', '.join(skipped) or 'none'}"]
    labels = Counter(r.regime for r in result.regime_rates)
    lines += ["", f"regime rows: {len(result.regime_rates)}"]
    lines += [f"  {label:<26} {n:>6}" for label, n in sorted(labels.items())]
    gaps = result.meta.macro_gaps
    lines += [f"macro gaps: {'; '.join(f'{k}: {v}' for k, v in gaps.items()) or 'none'}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exclude-vault", action="store_true", help="drop 2022+ events and prices")
    parser.add_argument("--out", type=Path, default=None, help="default depends on --exclude-vault")
    args = parser.parse_args(argv)
    out = args.out or (PRE_VAULT_DB if args.exclude_vault else DEFAULT_DB)
    result = build(exclude_vault=args.exclude_vault)
    write_db(out, result)
    print(summary(result, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
