"""Walk-forward calibration and the vault score: what "history leans" said at a cutoff, against
the episodes that came after it.

    statements = state_at(cutoff, universe)            # the engine rebuilt on data before cutoff
    scored = score(statements, outcomes_after(...))    # each later episode against its statement

A statement is the engine's own odds() answer on a table built only from events and prices
before the cutoff. build_before() composes the engine's public build steps (parse_events,
PriceBook.load(as_of), merge_episodes, rows_for_panel, write_db) the way backtest.build() does,
because build() takes only the vault cut, not any cutoff. Regime rows are skipped. Outcomes are
episodes in a later table, on the statement's own era, so a later table that adds an older
proxy era never changes the series being scored. The lean rule below is the one the pages used
until phase 5 showed it did not hold out of sample; it stays here only so the stored results can
be rescored and read.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import tomllib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from networth.config import CONFIG_TOML
from networth.engine import backtest, odds
from networth.engine.backtest import BASELINE_SEED, BASELINE_WINDOWS
from networth.engine.model import WEAK_SIGNAL_MIN_EPISODES, Build, BuildMeta, EventType, write_db
from networth.web import names

# Fixed before any result was computed (docs/phases/phase-5-plan.md).
CUTOFFS: Final = tuple(dt.date(y, 1, 1) for y in (2010, 2013, 2016, 2019))
WALK_END: Final = dt.date(2022, 1, 1)  # the vault starts here; walk-forward never reads it
BUCKETS: Final = ((0.5, 0.6, "50-60%"), (0.6, 0.7, "60-70%"), (0.7, 1.01, "70%+"))
LEAN_GAP: Final = 0.10
LEAN_UP: Final = "leans-up"
LEAN_DOWN: Final = "leans-down"
NO_PATTERN: Final = "no-pattern"


def lean_kind(hit_rate: float, baseline: float, weak: bool) -> str:
    """The stated lean: a gap of LEAN_GAP or more from the baseline, unless the signal is weak."""
    if weak:
        return NO_PATTERN
    gap = hit_rate - baseline
    if gap >= LEAN_GAP:
        return LEAN_UP
    if gap <= -LEAN_GAP:
        return LEAN_DOWN
    return NO_PATTERN


@dataclass(frozen=True)
class Statement:
    """What the engine would have said about one (type, asset) at a cutoff."""

    type: str
    asset: str
    era: str
    cutoff: str
    n: int
    hits: int
    hit_rate: float
    baseline: float
    weak: bool
    lean: str  # a lean_kind() value


@dataclass(frozen=True)
class Outcome:
    episode_id: str
    date: str
    hit: bool


@dataclass(frozen=True)
class Scored:
    statement: Statement
    outcomes: tuple[Outcome, ...]

    @property
    def n(self) -> int:
        return len(self.outcomes)

    @property
    def hits(self) -> int:
        return sum(o.hit for o in self.outcomes)


def universe(config_toml: Path = CONFIG_TOML) -> list[tuple[str, str]]:
    """Every (type, asset) a user can be shown: the watcher's assets for the type, then every
    scoreboard sector. Fixed in config.toml and names.py, not chosen here."""
    by_type = tomllib.loads(config_toml.read_text())["triggers"]["assets_by_type"]
    sectors = [a for groups in names.SCOREBOARD_GROUPS.values() for g in groups for a in g]
    return [(t.value, a) for t in EventType
            for a in dict.fromkeys([*by_type.get(t.value, []), *sectors])]  # fmt: skip


def build_before(cutoff: dt.date, out: Path, prices_dir: Path | None = None) -> Path:
    """The engine's table as it would have been on the day before cutoff."""
    as_of = cutoff - dt.timedelta(days=1)
    events, problems = backtest.parse_events()
    if problems:
        raise ValueError(f"events.csv has {len(problems)} problems; run check_events")
    events = [e for e in events if e.date <= as_of]
    book = backtest.PriceBook.load(prices_dir, as_of)
    episodes = backtest.merge_episodes(events, book.calendars())
    reactions, rows = [], []
    for asset in backtest.ASSETS:
        for era in backtest.ERAS:
            panel = book.panel(asset, era)
            if panel is None or len(panel.sessions) <= max(backtest.HORIZONS.values()) + 1:
                continue
            r, b, _ = backtest.rows_for_panel(panel, events, episodes)
            reactions += r
            rows += b
    meta = BuildMeta(as_of, BASELINE_SEED, BASELINE_WINDOWS, dict(backtest.HORIZONS),
                     hashlib.sha256(backtest.EVENTS_CSV.read_bytes()).hexdigest(),
                     tuple(a for a in backtest.ASSETS if a not in book.closes),
                     dt.datetime.now(dt.UTC))  # fmt: skip
    write_db(out, Build(meta, tuple(events), tuple(episodes), tuple(reactions), tuple(rows)))
    return out


def statement(type: str, asset: str, cutoff: dt.date, db: Path, era: str | None = None) -> (
    Statement | None
):  # fmt: skip
    try:
        o = odds.odds(type, asset, era=era, db=db)
    except (odds.NoBaseRate, ValueError):
        return None
    weak = o["n_episodes"] < WEAK_SIGNAL_MIN_EPISODES
    lean = lean_kind(o["hit_rate"], o["baseline"], weak)
    return Statement(type, asset, o["era"], cutoff.isoformat(), o["n_episodes"], o["n_hits"],
                     o["hit_rate"], o["baseline"], weak, lean)  # fmt: skip


def outcomes(s: Statement, db: Path, start: dt.date, end: dt.date) -> tuple[Outcome, ...]:
    """Episodes with onset in [start, end) on the statement's era, from a later table."""
    try:
        o = odds.odds(s.type, s.asset, era=s.era, db=db)
    except (odds.NoBaseRate, ValueError):
        return ()
    return tuple(Outcome(e["episode_id"], e["date"], e["hit"]) for e in o["episodes"]
                 if start <= dt.date.fromisoformat(e["date"]) < end)  # fmt: skip


def walk(rows: Sequence[tuple[str, str]], cutoff_dbs: Sequence[tuple[dt.date, Path]],
         later_db: Path) -> list[Scored]:  # fmt: skip
    """Each cutoff's statement scored on the episodes up to the next cutoff (or WALK_END), so
    no episode is scored twice for the same row."""
    ends = [c for c, _ in cutoff_dbs[1:]] + [WALK_END]
    out = []
    for (cutoff, db), end in zip(cutoff_dbs, ends, strict=True):
        for type, asset in rows:
            final = statement(type, asset, cutoff, later_db)
            s = final and statement(type, asset, cutoff, db, era=final.era)
            if s:
                out.append(Scored(s, outcomes(s, later_db, cutoff, end)))
    return out


def lean_side(s: Statement) -> bool:
    """The outcome the stated hit rate puts above even: a hit at 50% or more, else a miss."""
    return s.hit_rate >= 0.5


def calibration(scored: Iterable[Scored]) -> list[dict]:
    """Strong statements bucketed by the stated chance of their likelier outcome, against how
    often that outcome happened next. Baseline is the normal-period chance of the same side."""
    rows = []
    for lo, hi, label in BUCKETS:
        stated, base, happened, n = [], [], 0, 0
        for sc in scored:
            s = sc.statement
            side = lean_side(s)
            p = s.hit_rate if side else 1 - s.hit_rate
            if s.weak or not lo <= p < hi or not sc.n:
                continue
            stated += [p] * sc.n
            base += [s.baseline if side else 1 - s.baseline] * sc.n
            happened += sum(o.hit == side for o in sc.outcomes)
            n += sc.n
        rows.append({"bucket": label, "episodes": n, "happened": happened,
                     "happened_rate": round(happened / n, 4) if n else None,
                     "stated_mean": round(sum(stated) / n, 4) if n else None,
                     "baseline_mean": round(sum(base) / n, 4) if n else None})  # fmt: skip
    return rows


def held(sc: Scored) -> bool | None:
    """Did the later episodes land on the stated side of the baseline? None when no lean was
    stated or nothing happened later."""
    s = sc.statement
    if s.lean == NO_PATTERN or not sc.n:
        return None
    rate = sc.hits / sc.n
    return rate > s.baseline if s.lean == LEAN_UP else rate < s.baseline


LEAN_GROUPS: Final = ((LEAN_UP, "History leans toward"), (LEAN_DOWN, "History leans against"),
                      (NO_PATTERN, "No clear pattern"), ("weak", "Weak signal"))  # fmt: skip


def _in_group(s: Statement, kind: str) -> bool:
    return s.weak if kind == "weak" else not s.weak and s.lean == kind


def _weighted(group: Sequence[Scored], value: Callable[[Statement], float]) -> float | None:
    n = sum(sc.n for sc in group)
    return round(sum(value(sc.statement) * sc.n for sc in group) / n, 4) if n else None


def by_lean(scored: Sequence[Scored]) -> list[dict]:
    """Per stated lean: statements, later episodes, the later hit rate against the stated rate
    and the baseline, and how many leaning statements held."""
    out = []
    for kind, label in LEAN_GROUPS:
        group = [sc for sc in scored if _in_group(sc.statement, kind)]
        n, hits = sum(sc.n for sc in group), sum(sc.hits for sc in group)
        verdicts = [h for sc in group if (h := held(sc)) is not None]
        leaning = kind in (LEAN_UP, LEAN_DOWN)
        out.append({"lean": label, "statements": len(group), "episodes": n, "later_hits": hits,
                    "later_rate": round(hits / n, 4) if n else None,
                    "stated_rate": _weighted(group, lambda s: s.hit_rate),
                    "baseline": _weighted(group, lambda s: s.baseline),
                    "held": sum(verdicts) if leaning else None,
                    "judged": len(verdicts) if leaning else None})  # fmt: skip
    return out


def per_row(scored: Sequence[Scored], in_sample_db: Path) -> list[dict]:
    """One line per (type, asset) with at least WEAK_SIGNAL_MIN_EPISODES episodes in the
    in-sample table: its in-sample rate, and every later episode pooled across cutoffs."""
    rows: dict[tuple[str, str], list[Scored]] = {}
    for sc in scored:
        rows.setdefault((sc.statement.type, sc.statement.asset), []).append(sc)
    out = []
    for (type, asset), group in rows.items():
        full = statement(type, asset, WALK_END, in_sample_db, era=group[0].statement.era)
        if full is None or full.weak:
            continue
        n = sum(sc.n for sc in group)
        hits = sum(sc.hits for sc in group)
        base = sum(sc.statement.baseline * sc.n for sc in group) / n if n else full.baseline
        out.append({"type": type, "asset": asset, "era": full.era,
                    "in_n": full.n, "in_hits": full.hits, "in_rate": full.hit_rate,
                    "in_baseline": full.baseline, "in_gap": round(full.hit_rate - full.baseline, 4),
                    "lean": full.lean, "out_n": n, "out_hits": hits,
                    "out_rate": round(hits / n, 4) if n else None,
                    "out_baseline": round(base, 4),
                    "out_gap": round(hits / n - base, 4) if n else None})  # fmt: skip
    return out


def scored_json(scored: Iterable[Scored]) -> list[dict]:
    return [{**asdict(sc.statement), "outcomes": [asdict(o) for o in sc.outcomes]}
            for sc in scored]  # fmt: skip


def scored_from_json(rows: Iterable[dict]) -> list[Scored]:
    return [Scored(Statement(**{k: v for k, v in r.items() if k != "outcomes"}),
                   tuple(Outcome(**o) for o in r["outcomes"])) for r in rows]  # fmt: skip
