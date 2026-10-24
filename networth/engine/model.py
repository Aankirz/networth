"""The spec's data model (tech.html section 03) and the sqlite file that stores it.

This is the only module that knows the sqlite schema. backtest.py computes these shapes and
hands a `Build` to `write_db`. odds.py reads them back through `RatesDB`.

Spec mapping:
    Event    -> table events     (+ tz, time_known, notes, in_vault; sources[] stored as JSON)
    Reaction -> table reactions  (+ era, series, benchmark, entry/exit dates, bench_return,
                                    day0_raw/day0_excess, informational only)
    BaseRate -> table base_rates (+ weak_signal, includes_vault, measure, market, series,
                                    benchmark, data_start, data_end, raw_p10/raw_median/raw_p90)
    (new)    -> table episodes   (the spec's episode_id needs somewhere to point)
    (new)    -> table meta       (as_of, seed, horizons, macro_gaps: how this file was built)
    (new)    -> table regime_rates (a base_rates row restricted to one regime value, + regime,
                                    hindsight; its own table so base_rates readers never see it)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Final, Literal
from zoneinfo import ZoneInfo

import numpy as np

DATA_DIR: Final = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DB: Final = DATA_DIR / "base_rates.sqlite"
PRE_VAULT_DB: Final = DATA_DIR / "base_rates_pre2022.sqlite"

VAULT_START: Final = dt.date(2022, 1, 1)
WEAK_SIGNAL_MIN_EPISODES: Final = 8
ALL_CAUSES: Final = "*"  # base_rates.cause for the all-causes row; never leaves this module


class EventType(StrEnum):
    OIL_SUPPLY = "oil_supply"
    FED_HIKE = "fed_hike"
    FED_CUT = "fed_cut"
    RBI_HIKE = "rbi_hike"
    RBI_CUT = "rbi_cut"
    UNION_BUDGET = "union_budget"
    INR_SHOCK = "inr_shock"
    MILITARY_CONFLICT = "military_conflict"
    TARIFF = "tariff"
    BANK_STRESS = "bank_stress"
    PANDEMIC = "pandemic"
    ELECTION = "election"


class Region(StrEnum):
    US = "us"
    IN = "in"
    GLOBAL = "global"


class Market(StrEnum):
    """Where an asset trades. Decides the close-time rule, the eras and the currency."""

    US = "us"
    IN = "in"


CURRENCY: Final[Mapping[Market, str]] = {Market.US: "USD", Market.IN: "INR"}


class EraName(StrEnum):
    """Declaration order is display order: within a market, the asset's own series first."""

    SINCE_1998 = "since_1998"  # US, the ETFs themselves vs SPY
    SINCE_1926 = "since_1926"  # US, French industry portfolios vs the French market
    SINCE_2007 = "since_2007"  # India, vs the Nifty 50
    SINCE_1997 = "since_1997"  # India, vs the Sensex-Nifty splice


Measure = Literal["excess", "raw"]  # raw only when the measured series is the market itself


@dataclass(frozen=True)
class KnownTime:
    """The event became public at this aware instant."""

    at: dt.datetime


@dataclass(frozen=True)
class UnknownTime:
    """Only the local date is known. In every market the first usable session is the first
    session dated strictly after local_date (the brief: unknown means after the close). Its own
    type so no code can read it as midnight or as the end of the day in some other zone."""

    local_date: dt.date


EventTime = KnownTime | UnknownTime


@dataclass(frozen=True)
class Event:
    """One row of events.csv, parsed. date is local to tz."""

    id: str
    date: dt.date
    time: EventTime
    tz: str
    region: Region
    type: EventType
    cause: str
    headline: str
    sources: tuple[str, ...]  # spec: sources[]; events.csv has one source_url today
    notes: str = ""

    @property
    def in_vault(self) -> bool:
        return self.date >= VAULT_START

    @property
    def time_known(self) -> str | None:
        """HH:MM local, as in the CSV, or None."""
        if isinstance(self.time, UnknownTime):
            return None
        return self.time.at.astimezone(ZoneInfo(self.tz)).strftime("%H:%M")


@dataclass(frozen=True)
class Episode:
    """Same-type events chained with gaps of at most 21 trading days.

    The onset (first event) is the one whose Reaction scores the episode.
    id = f"{type}:{onset.id}", so it survives a vault cut and a price refresh.
    """

    id: str
    type: EventType
    events: tuple[Event, ...]

    @property
    def onset(self) -> Event:
        return self.events[0]

    @property
    def cause(self) -> str:
        return self.onset.cause

    @property
    def in_vault(self) -> bool:
        return any(e.in_vault for e in self.events)


@dataclass(frozen=True)
class Reaction:
    """What one asset did after one event, over the type's fixed horizon.

    raw_return and bench_return read exactly close(entry) and close(exit). day0_raw and
    day0_excess are the entry session's own move, close(entry-1) -> close(entry): what the
    investable convention leaves out. No base rate uses them.
    """

    event_id: str
    asset: str
    era: EraName
    horizon_days: int
    series: str
    benchmark: str
    entry_date: dt.date
    exit_date: dt.date
    raw_return: float
    bench_return: float
    day0_raw: float
    day0_excess: float

    @property
    def excess_return(self) -> float:
        return self.raw_return - self.bench_return


def is_hit(measure: Measure, raw: float, excess: float) -> bool:
    """Beat the market, or rose when the series is the market."""
    return (raw if measure == "raw" else excess) > 0


@dataclass(frozen=True)
class Stats:
    n: int
    n_hits: int
    hit_rate: float
    median: float
    p10: float
    p90: float


def summarize(values: Sequence[float], hits: Sequence[bool]) -> Stats:
    """One implementation for backtest rows and odds.compare subsets, so they never disagree."""
    if not values or len(values) != len(hits):
        raise ValueError("summarize needs a non-empty sample with one hit flag per value")
    p10, median, p90 = np.quantile(np.asarray(values, dtype=float), [0.1, 0.5, 0.9])
    n_hits = int(sum(hits))
    return Stats(len(values), n_hits, n_hits / len(values), float(median), float(p10), float(p90))


@dataclass(frozen=True)
class BaseRate:
    """One row of base_rates. weak_signal is derived from n_episodes, never set on its own.

    hit_rate / median / p10 / p90 are on `measure`. raw_* are the same quantiles on the raw
    return, for position_range, since money moves with the raw return.
    """

    type: EventType
    cause: str | None  # None = all causes
    asset: str
    market: Market
    horizon_days: int
    era: EraName
    n_events: int
    n_episodes: int
    n_hits: int
    hit_rate: float
    baseline_hit_rate: float
    median: float
    p10: float
    p90: float
    episode_ids: tuple[str, ...]
    includes_vault: bool
    measure: Measure
    series: str
    benchmark: str
    data_start: dt.date
    data_end: dt.date
    raw_median: float
    raw_p10: float
    raw_p90: float

    @property
    def weak_signal(self) -> bool:
        return self.n_episodes < WEAK_SIGNAL_MIN_EPISODES


@dataclass(frozen=True)
class RegimeRate:
    """A BaseRate over only the episodes whose onset had one regime value.

    regime is the label, e.g. "recession_followed=no". hindsight=True means the value was only
    knowable after the fact: "what happened in each case", never a live signal.
    """

    regime: str
    hindsight: bool
    rate: BaseRate


@dataclass(frozen=True)
class BuildMeta:
    as_of: dt.date | None  # None = everything
    baseline_seed: int
    baseline_windows: int
    horizons: Mapping[EventType, int]
    events_sha256: str
    skipped_series: tuple[str, ...]
    built_at: dt.datetime
    macro_gaps: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class Build:
    meta: BuildMeta
    events: tuple[Event, ...]
    episodes: tuple[Episode, ...]
    reactions: tuple[Reaction, ...]
    base_rates: tuple[BaseRate, ...]
    regime_rates: tuple[RegimeRate, ...] = field(default=())


SCHEMA: Final = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE episodes (
  id TEXT PRIMARY KEY, type TEXT NOT NULL, cause TEXT NOT NULL,
  onset_event_id TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
  n_events INTEGER NOT NULL, in_vault INTEGER NOT NULL);
CREATE TABLE events (
  id TEXT PRIMARY KEY, date TEXT NOT NULL, time_known TEXT, tz TEXT NOT NULL,
  region TEXT NOT NULL, type TEXT NOT NULL, cause TEXT NOT NULL, headline TEXT NOT NULL,
  sources TEXT NOT NULL, notes TEXT NOT NULL,
  episode_id TEXT NOT NULL REFERENCES episodes(id), in_vault INTEGER NOT NULL);
CREATE TABLE reactions (
  event_id TEXT NOT NULL REFERENCES events(id), asset TEXT NOT NULL, era TEXT NOT NULL,
  horizon_days INTEGER NOT NULL, series TEXT NOT NULL, benchmark TEXT NOT NULL,
  entry_date TEXT NOT NULL, exit_date TEXT NOT NULL,
  raw_return REAL NOT NULL, bench_return REAL NOT NULL, excess_return REAL NOT NULL,
  day0_raw REAL NOT NULL, day0_excess REAL NOT NULL,
  PRIMARY KEY (event_id, asset, era));
CREATE TABLE base_rates (
  type TEXT NOT NULL, cause TEXT NOT NULL, asset TEXT NOT NULL, market TEXT NOT NULL,
  horizon_days INTEGER NOT NULL, era TEXT NOT NULL,
  n_events INTEGER NOT NULL, n_episodes INTEGER NOT NULL, n_hits INTEGER NOT NULL,
  hit_rate REAL NOT NULL, baseline_hit_rate REAL NOT NULL,
  median REAL NOT NULL, p10 REAL NOT NULL, p90 REAL NOT NULL,
  episode_ids TEXT NOT NULL, weak_signal INTEGER NOT NULL, includes_vault INTEGER NOT NULL,
  measure TEXT NOT NULL, series TEXT NOT NULL, benchmark TEXT NOT NULL,
  data_start TEXT NOT NULL, data_end TEXT NOT NULL,
  raw_median REAL NOT NULL, raw_p10 REAL NOT NULL, raw_p90 REAL NOT NULL,
  PRIMARY KEY (type, cause, asset, era));
CREATE TABLE regime_rates (
  type TEXT NOT NULL, cause TEXT NOT NULL, asset TEXT NOT NULL, market TEXT NOT NULL,
  horizon_days INTEGER NOT NULL, era TEXT NOT NULL,
  n_events INTEGER NOT NULL, n_episodes INTEGER NOT NULL, n_hits INTEGER NOT NULL,
  hit_rate REAL NOT NULL, baseline_hit_rate REAL NOT NULL,
  median REAL NOT NULL, p10 REAL NOT NULL, p90 REAL NOT NULL,
  episode_ids TEXT NOT NULL, weak_signal INTEGER NOT NULL, includes_vault INTEGER NOT NULL,
  measure TEXT NOT NULL, series TEXT NOT NULL, benchmark TEXT NOT NULL,
  data_start TEXT NOT NULL, data_end TEXT NOT NULL,
  raw_median REAL NOT NULL, raw_p10 REAL NOT NULL, raw_p90 REAL NOT NULL,
  regime TEXT NOT NULL, hindsight INTEGER NOT NULL,
  PRIMARY KEY (type, cause, asset, era, regime));
"""

_BASE_RATE_COLUMNS: Final = (
    "type", "cause", "asset", "market", "horizon_days", "era", "n_events", "n_episodes",
    "n_hits", "hit_rate", "baseline_hit_rate", "median", "p10", "p90", "episode_ids",
    "weak_signal", "includes_vault", "measure", "series", "benchmark", "data_start",
    "data_end", "raw_median", "raw_p10", "raw_p90",
)  # fmt: skip


def _base_rate_values(r: BaseRate) -> tuple:
    return (
        r.type.value, r.cause or ALL_CAUSES, r.asset, r.market.value, r.horizon_days,
        r.era.value, r.n_events, r.n_episodes, r.n_hits, r.hit_rate, r.baseline_hit_rate,
        r.median, r.p10, r.p90, json.dumps(list(r.episode_ids)), int(r.weak_signal),
        int(r.includes_vault), r.measure, r.series, r.benchmark, r.data_start.isoformat(),
        r.data_end.isoformat(), r.raw_median, r.raw_p10, r.raw_p90,
    )  # fmt: skip


def _meta_rows(meta: BuildMeta) -> list[tuple[str, str]]:
    return [
        ("as_of", meta.as_of.isoformat() if meta.as_of else ""),
        ("baseline_seed", str(meta.baseline_seed)),
        ("baseline_windows", str(meta.baseline_windows)),
        ("horizons", json.dumps({t.value: h for t, h in meta.horizons.items()})),
        ("events_sha256", meta.events_sha256),
        ("skipped_series", json.dumps(list(meta.skipped_series))),
        ("built_at", meta.built_at.isoformat()),
        ("macro_gaps", json.dumps(dict(meta.macro_gaps))),
    ]


def write_db(path: Path, build: Build) -> None:
    """Write a whole build into <path>.tmp, then os.replace it onto path. A crash halfway
    leaves the previous file untouched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    episode_of = {e.id: ep.id for ep in build.episodes for e in ep.events}
    conn = sqlite3.connect(tmp)
    try:
        with conn:
            conn.executescript(SCHEMA)
            conn.executemany("INSERT INTO meta VALUES (?, ?)", _meta_rows(build.meta))
            conn.executemany(
                "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (ep.id, ep.type.value, ep.cause, ep.onset.id, ep.events[0].date.isoformat(),
                     ep.events[-1].date.isoformat(), len(ep.events), int(ep.in_vault))
                    for ep in build.episodes
                ],
            )  # fmt: skip
            conn.executemany(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (e.id, e.date.isoformat(), e.time_known, e.tz, e.region.value, e.type.value,
                     e.cause, e.headline, json.dumps(list(e.sources)), e.notes, episode_of[e.id],
                     int(e.in_vault))
                    for e in build.events
                ],
            )  # fmt: skip
            conn.executemany(
                "INSERT INTO reactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (r.event_id, r.asset, r.era.value, r.horizon_days, r.series, r.benchmark,
                     r.entry_date.isoformat(), r.exit_date.isoformat(), r.raw_return,
                     r.bench_return, r.excess_return, r.day0_raw, r.day0_excess)
                    for r in build.reactions
                ],
            )  # fmt: skip
            marks = ", ".join("?" * len(_BASE_RATE_COLUMNS))
            conn.executemany(
                f"INSERT INTO base_rates ({', '.join(_BASE_RATE_COLUMNS)}) VALUES ({marks})",
                [_base_rate_values(r) for r in build.base_rates],
            )
            regime_columns = ", ".join((*_BASE_RATE_COLUMNS, "regime", "hindsight"))
            conn.executemany(
                f"INSERT INTO regime_rates ({regime_columns}) VALUES ({marks}, ?, ?)",
                [
                    (*_base_rate_values(r.rate), r.regime, int(r.hindsight))
                    for r in build.regime_rates
                ],
            )
    finally:
        conn.close()
    os.replace(tmp, path)


@dataclass(frozen=True)
class EpisodeDetail:
    """An episode as odds() shows it: its members and the onset's scored reaction."""

    episode_id: str
    cause: str
    events: tuple[EpisodeEvent, ...]
    reaction: Reaction


@dataclass(frozen=True)
class EpisodeEvent:
    id: str
    date: dt.date
    headline: str
    sources: tuple[str, ...]


_ERA_RANK: Final = {e: i for i, e in enumerate(EraName)}


class RatesDB:
    """Read-only handle over one base_rates sqlite file (uri mode=ro)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: Path = DEFAULT_DB) -> RatesDB:
        if not path.exists():
            raise FileNotFoundError(f"{path} missing: run python -m networth.engine.backtest")
        return cls(sqlite3.connect(f"file:{path}?mode=ro", uri=True))

    def close(self) -> None:
        self._conn.close()

    def meta(self) -> dict[str, str]:
        return {row["key"]: row["value"] for row in self._conn.execute("SELECT * FROM meta")}

    def assets(self) -> set[str]:
        return {row[0] for row in self._conn.execute("SELECT DISTINCT asset FROM base_rates")}

    def base_rates(self, type: EventType, asset: str, cause: str | None) -> list[BaseRate]:
        """Every era's row for (type, cause, asset), in EraName order."""
        rows = self._conn.execute(
            "SELECT * FROM base_rates WHERE type = ? AND asset = ? AND cause = ?",
            (type.value, asset, cause or ALL_CAUSES),
        ).fetchall()
        rates = [_base_rate_from_row(r) for r in rows]
        return sorted(rates, key=lambda r: _ERA_RANK[r.era])

    def rows_for(self, type: EventType, asset: str) -> list[tuple[str, str | None]]:
        """(era, cause) of every row that exists for this type and asset."""
        rows = self._conn.execute(
            "SELECT era, cause FROM base_rates WHERE type = ? AND asset = ? ORDER BY era, cause",
            (type.value, asset),
        ).fetchall()
        return [(r["era"], None if r["cause"] == ALL_CAUSES else r["cause"]) for r in rows]

    def macro_gaps(self) -> dict[str, str]:
        return json.loads(self.meta().get("macro_gaps", "{}"))

    def regime_rates(
        self, type: EventType, asset: str, cause: str | None, regime: str
    ) -> list[RegimeRate]:
        """Every era's row for (type, cause, asset, regime label), in EraName order."""
        rows = self._conn.execute(
            "SELECT * FROM regime_rates WHERE type = ? AND asset = ? AND cause = ? AND regime = ?",
            (type.value, asset, cause or ALL_CAUSES, regime),
        ).fetchall()
        rates = [
            RegimeRate(r["regime"], bool(r["hindsight"]), _base_rate_from_row(r)) for r in rows
        ]
        return sorted(rates, key=lambda r: _ERA_RANK[r.rate.era])

    def regime_rows_for(self, type: EventType, asset: str) -> list[tuple[str, str | None, str]]:
        """(era, cause, regime) of every regime row that exists for this type and asset."""
        rows = self._conn.execute(
            "SELECT era, cause, regime FROM regime_rates WHERE type = ? AND asset = ? "
            "ORDER BY era, cause, regime",
            (type.value, asset),
        ).fetchall()
        return [
            (r["era"], None if r["cause"] == ALL_CAUSES else r["cause"], r["regime"]) for r in rows
        ]

    def episodes(self, rate: BaseRate) -> list[EpisodeDetail]:
        """The scored episodes behind one row, chronological, with the onset's Reaction."""
        details = []
        for episode_id in rate.episode_ids:
            ep = self._conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
            members = self._conn.execute(
                "SELECT id, date, headline, sources FROM events WHERE episode_id = ? "
                "ORDER BY date, id",
                (episode_id,),
            ).fetchall()
            reaction = self._conn.execute(
                "SELECT * FROM reactions WHERE event_id = ? AND asset = ? AND era = ?",
                (ep["onset_event_id"], rate.asset, rate.era.value),
            ).fetchone()
            details.append(
                EpisodeDetail(
                    episode_id=episode_id,
                    cause=ep["cause"],
                    events=tuple(
                        EpisodeEvent(
                            m["id"],
                            dt.date.fromisoformat(m["date"]),
                            m["headline"],
                            tuple(json.loads(m["sources"])),
                        )
                        for m in members
                    ),  # fmt: skip
                    reaction=_reaction_from_row(reaction),
                )
            )
        return details


def _base_rate_from_row(r: sqlite3.Row) -> BaseRate:
    return BaseRate(
        type=EventType(r["type"]),
        cause=None if r["cause"] == ALL_CAUSES else r["cause"],
        asset=r["asset"],
        market=Market(r["market"]),
        horizon_days=r["horizon_days"],
        era=EraName(r["era"]),
        n_events=r["n_events"],
        n_episodes=r["n_episodes"],
        n_hits=r["n_hits"],
        hit_rate=r["hit_rate"],
        baseline_hit_rate=r["baseline_hit_rate"],
        median=r["median"],
        p10=r["p10"],
        p90=r["p90"],
        episode_ids=tuple(json.loads(r["episode_ids"])),
        includes_vault=bool(r["includes_vault"]),
        measure=r["measure"],
        series=r["series"],
        benchmark=r["benchmark"],
        data_start=dt.date.fromisoformat(r["data_start"]),
        data_end=dt.date.fromisoformat(r["data_end"]),
        raw_median=r["raw_median"],
        raw_p10=r["raw_p10"],
        raw_p90=r["raw_p90"],
    )


def _reaction_from_row(r: sqlite3.Row) -> Reaction:
    return Reaction(
        event_id=r["event_id"],
        asset=r["asset"],
        era=EraName(r["era"]),
        horizon_days=r["horizon_days"],
        series=r["series"],
        benchmark=r["benchmark"],
        entry_date=dt.date.fromisoformat(r["entry_date"]),
        exit_date=dt.date.fromisoformat(r["exit_date"]),
        raw_return=r["raw_return"],
        bench_return=r["bench_return"],
        day0_raw=r["day0_raw"],
        day0_excess=r["day0_excess"],
    )
