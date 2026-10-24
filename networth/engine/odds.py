"""Read-only answers over data/base_rates.sqlite, in the spec's JSON shapes.

    odds("oil_supply", "JETS")
    position_range(2000, "JETS", "oil_supply")
    compare("oil_supply", ["JETS", "XLE", "SPY"])
    odds("fed_cut", "XLF", regime="recession_followed=no")
    split("fed_cut", "XLF", "recession_followed")

Run: uv run python -m networth.engine.odds odds oil_supply JETS
     uv run python -m networth.engine.odds range 2000 JETS oil_supply
     uv run python -m networth.engine.odds compare oil_supply JETS XLE SPY
     uv run python -m networth.engine.odds split fed_cut XLF recession_followed

Reads only through model.RatesDB. Every value is a JSON scalar, floats rounded to 4 places, so
later phases can record exactly which numbers a message quoted. Nothing here ranks assets or
says what to do: compare() keeps the caller's order.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal, TypedDict

from networth.engine import macro
from networth.engine.model import (
    CURRENCY,
    DEFAULT_DB,
    WEAK_SIGNAL_MIN_EPISODES,
    BaseRate,
    EpisodeDetail,
    EraName,
    EventType,
    Measure,
    RatesDB,
    is_hit,
    summarize,
)

DECIMALS: Final = 4
COMPARE_MIN, COMPARE_MAX = 2, 3


class NoBaseRate(LookupError):
    """No row for this question. The message lists the rows that do exist."""


class NoRegimeData(LookupError):
    """The macro series a regime needs was missing when the file was built."""


class EpisodeJSON(TypedDict):
    episode_id: str
    date: str
    cause: str
    headline: str
    sources: list[str]
    event_ids: list[str]
    entry_date: str
    exit_date: str
    raw_return: float
    excess_return: float
    hit: bool
    day0_raw: float  # informational: the entry session's own move, not in any base rate
    day0_excess: float


class EraJSON(TypedDict):
    era: str
    series: str
    benchmark: str
    measure: Measure
    n_events: int
    n_episodes: int
    n_hits: int
    hit_rate: float
    baseline: float
    median: float
    p10: float
    p90: float
    weak_signal: bool
    includes_vault: bool
    data_start: str
    data_end: str
    n_shared_with_primary: int  # how many of this era's episodes the primary era also scores


class OddsJSON(TypedDict):
    type: str
    cause: str | None
    asset: str
    era: str
    horizon_days: int
    n_events: int
    n_episodes: int
    n_hits: int
    hit_rate: float
    baseline: float
    median: float
    p10: float
    p90: float
    measure: Measure
    series: str
    benchmark: str
    data_start: str
    data_end: str
    weak_signal: bool
    includes_vault: bool
    episodes: list[EpisodeJSON]
    other_eras: list[EraJSON]
    eras_disagree: bool  # two eras put hit_rate on opposite sides of their baselines


class RegimeOddsJSON(OddsJSON):
    regime: str  # e.g. "recession_followed=no"
    hindsight: bool  # True: what happened in each case, never a live signal


class SideJSON(TypedDict):
    value: macro.RegimeValue
    regime: str
    n_episodes: int
    n_hits: int
    hit_rate: float | None  # None when the side has no episodes
    baseline: float
    median: float | None
    p10: float | None
    p90: float | None
    weak_signal: bool
    hindsight: bool
    episode_ids: list[str]


class SplitJSON(TypedDict):
    type: str
    asset: str
    cause: str | None
    era: str
    horizon_days: int
    regime: str  # the rule name, e.g. "recession_followed"
    hindsight: bool
    baseline: float
    measure: Measure
    n_episodes_all: int  # the row without a regime
    n_unclassified: int  # episodes the rule could not decide: in neither side
    sides: list[SideJSON]  # "yes" then "no"


class PositionRangeJSON(TypedDict):
    value: float
    currency: str
    asset: str
    type: str
    cause: str | None
    era: str
    horizon_days: int
    basis: Literal["raw"]  # money moves with the raw return, not the excess
    p10: int
    median: int
    p90: int
    n_episodes: int
    weak_signal: bool


class CompareAssetJSON(TypedDict):
    asset: str
    era: str
    series: str
    benchmark: str
    measure: Measure
    n_episodes_all: int  # the asset's own row, before restricting to shared episodes
    n_hits: int
    hit_rate: float
    baseline: float
    median: float
    p10: float
    p90: float


class CompareJSON(TypedDict):
    type: str
    cause: str | None
    horizon_days: int
    episode_ids: list[str]
    n_episodes: int
    weak_signal: bool
    assets: list[CompareAssetJSON]


def _r(x: float) -> float:
    return round(float(x), DECIMALS)


def _parse_type(type: str) -> EventType:
    try:
        return EventType(type)
    except ValueError:
        raise ValueError(f"unknown type {type!r}; one of {[t.value for t in EventType]}") from None


def _parse_era(era: str | None) -> EraName | None:
    if era is None:
        return None
    try:
        return EraName(era)
    except ValueError:
        raise ValueError(f"unknown era {era!r}; one of {[e.value for e in EraName]}") from None


def _rows(
    db: RatesDB, type: EventType, asset: str, cause: str | None, era: EraName | None
) -> tuple[BaseRate, list[BaseRate]]:
    """(primary row, every row for the asset's eras). Primary = the requested era, else the
    first era in EraName order, which is the asset measured on itself."""
    if asset not in db.assets():
        raise ValueError(f"unknown asset {asset!r}")
    rows = db.base_rates(type, asset, cause)
    primary = next((r for r in rows if era is None or r.era == era), None)
    if primary is None:
        existing = ", ".join(f"{e}/{c or 'all causes'}" for e, c in db.rows_for(type, asset))
        wanted = f"{era or 'any era'}/{cause or 'all causes'}"
        raise NoBaseRate(
            f"no {type.value} row for {asset} at {wanted}; rows that exist: {existing or 'none'}"
        )
    return primary, rows


def _era_json(rate: BaseRate, primary: BaseRate) -> EraJSON:
    return EraJSON(
        era=rate.era.value,
        series=rate.series,
        benchmark=rate.benchmark,
        measure=rate.measure,
        n_events=rate.n_events,
        n_episodes=rate.n_episodes,
        n_hits=rate.n_hits,
        hit_rate=_r(rate.hit_rate),
        baseline=_r(rate.baseline_hit_rate),
        median=_r(rate.median),
        p10=_r(rate.p10),
        p90=_r(rate.p90),
        weak_signal=rate.weak_signal,
        includes_vault=rate.includes_vault,
        data_start=rate.data_start.isoformat(),
        data_end=rate.data_end.isoformat(),
        n_shared_with_primary=len(set(rate.episode_ids) & set(primary.episode_ids)),
    )


def _episode_json(d: EpisodeDetail, measure: Measure) -> EpisodeJSON:
    r, onset = d.reaction, d.events[0]
    return EpisodeJSON(
        episode_id=d.episode_id,
        date=onset.date.isoformat(),
        cause=d.cause,
        headline=onset.headline,
        sources=list(onset.sources),
        event_ids=[e.id for e in d.events],
        entry_date=r.entry_date.isoformat(),
        exit_date=r.exit_date.isoformat(),
        raw_return=_r(r.raw_return),
        excess_return=_r(r.excess_return),
        hit=is_hit(measure, r.raw_return, r.excess_return),
        day0_raw=_r(r.day0_raw),
        day0_excess=_r(r.day0_excess),
    )


def _beats_baseline(r: BaseRate) -> bool:
    return r.hit_rate > r.baseline_hit_rate


def _rule_for(t: EventType, name: str) -> macro.RegimeRule:
    rule = macro.REGIMES.get(name)
    if rule is None:
        raise ValueError(f"unknown regime {name!r}; one of {sorted(macro.REGIMES)}")
    if t not in rule.types:
        allowed = sorted(x.value for x in rule.types)
        raise ValueError(f"{name} does not apply to {t.value}; it applies to {allowed}")
    return rule


def _check_regime_data(rates: RatesDB, t: EventType, rule: macro.RegimeRule) -> None:
    series = rule.series_by_type[t]
    if reason := rates.macro_gaps().get(series):
        raise NoRegimeData(f"no {macro.SERIES_TITLE[series]} for {rule.name}: {reason}")


def _regime_rows(
    rates: RatesDB, t: EventType, asset: str, cause: str | None, era: EraName | None, label: str
) -> tuple[BaseRate, list[BaseRate]]:
    base, _ = _rows(rates, t, asset, cause, era)
    rows = [r.rate for r in rates.regime_rates(t, asset, cause, label)]
    primary = next((r for r in rows if r.era == base.era), None)
    if primary is None:
        existing = ", ".join(
            f"{e}/{c or 'all causes'}/{g}" for e, c, g in rates.regime_rows_for(t, asset)
        )
        raise NoBaseRate(
            f"no {t.value} row for {asset} at {base.era}/{cause or 'all causes'} with {label}; "
            f"regime rows that exist: {existing or 'none'}"
        )
    return primary, rows


def odds(
    type: str,
    asset: str,
    cause: str | None = None,
    era: str | None = None,
    *,
    db: Path = DEFAULT_DB,
    regime: str | None = None,
) -> OddsJSON | RegimeOddsJSON:
    """The odds for one (type, asset), on the requested era or the asset's own series. Every
    other era with a row goes in other_eras. With regime="<rule>=<yes|no>", the same answer
    over only the episodes with that regime value, plus `regime` and `hindsight`. Raises
    ValueError on an unknown type, asset, era or regime, NoBaseRate when no row exists,
    NoRegimeData when the regime's macro series was missing at build time."""
    t, e = _parse_type(type), _parse_era(era)
    rule = None if regime is None else _rule_for(t, macro.parse_label(regime)[0].name)
    rates = RatesDB.open(db)
    try:
        if rule is None:
            primary, rows = _rows(rates, t, asset, cause, e)
        else:
            _check_regime_data(rates, t, rule)
            primary, rows = _regime_rows(rates, t, asset, cause, e, regime)
        details = rates.episodes(primary)
    finally:
        rates.close()
    out = _odds_json(t, asset, cause, primary, rows, details)
    if rule is None:
        return out
    return RegimeOddsJSON(**out, regime=regime, hindsight=rule.hindsight)


def _odds_json(
    t: EventType,
    asset: str,
    cause: str | None,
    primary: BaseRate,
    rows: list[BaseRate],
    details: list[EpisodeDetail],
) -> OddsJSON:
    era_view = _era_json(primary, primary)
    return OddsJSON(
        type=t.value,
        cause=cause,
        asset=asset,
        era=era_view["era"],
        horizon_days=primary.horizon_days,
        n_events=era_view["n_events"],
        n_episodes=era_view["n_episodes"],
        n_hits=era_view["n_hits"],
        hit_rate=era_view["hit_rate"],
        baseline=era_view["baseline"],
        median=era_view["median"],
        p10=era_view["p10"],
        p90=era_view["p90"],
        measure=primary.measure,
        series=primary.series,
        benchmark=primary.benchmark,
        data_start=era_view["data_start"],
        data_end=era_view["data_end"],
        weak_signal=primary.weak_signal,
        includes_vault=primary.includes_vault,
        episodes=[_episode_json(d, primary.measure) for d in details],
        other_eras=[_era_json(r, primary) for r in rows if r is not primary],
        eras_disagree=len({_beats_baseline(r) for r in rows}) > 1,
    )


def _side_json(
    rule: macro.RegimeRule, value: macro.RegimeValue, rate: BaseRate | None, baseline: float
) -> SideJSON:
    return SideJSON(
        value=value,
        regime=macro.regime_label(rule.name, value),
        n_episodes=rate.n_episodes if rate else 0,
        n_hits=rate.n_hits if rate else 0,
        hit_rate=_r(rate.hit_rate) if rate else None,
        baseline=_r(baseline),
        median=_r(rate.median) if rate else None,
        p10=_r(rate.p10) if rate else None,
        p90=_r(rate.p90) if rate else None,
        weak_signal=rate.weak_signal if rate else True,
        hindsight=rule.hindsight,
        episode_ids=list(rate.episode_ids) if rate else [],
    )


def _side_rate(
    rates: RatesDB, t: EventType, asset: str, cause: str | None, label: str, era: EraName
) -> BaseRate | None:
    return next(
        (r.rate for r in rates.regime_rates(t, asset, cause, label) if r.rate.era == era), None
    )


def split(
    type: str,
    asset: str,
    regime_name: str,
    cause: str | None = None,
    era: str | None = None,
    *,
    db: Path = DEFAULT_DB,
) -> SplitJSON:
    """Both sides of one regime for (type, asset), on the era odds() would answer on. A side
    with no episodes is still returned, with n_episodes 0. Raises ValueError on an unknown
    regime or one that does not apply to the type, NoRegimeData when its macro series was
    missing at build time, NoBaseRate when the plain row does not exist."""
    t, e = _parse_type(type), _parse_era(era)
    rule = _rule_for(t, regime_name)
    rates = RatesDB.open(db)
    try:
        _check_regime_data(rates, t, rule)
        base, _ = _rows(rates, t, asset, cause, e)
        sides = {
            v: _side_rate(rates, t, asset, cause, macro.regime_label(rule.name, v), base.era)
            for v in macro.REGIME_VALUES
        }
    finally:
        rates.close()
    classified = sum(r.n_episodes for r in sides.values() if r)
    return SplitJSON(
        type=t.value,
        asset=asset,
        cause=cause,
        era=base.era.value,
        horizon_days=base.horizon_days,
        regime=rule.name,
        hindsight=rule.hindsight,
        baseline=_r(base.baseline_hit_rate),
        measure=base.measure,
        n_episodes_all=base.n_episodes,
        n_unclassified=base.n_episodes - classified,
        sides=[_side_json(rule, v, sides[v], base.baseline_hit_rate) for v in macro.REGIME_VALUES],
    )


def position_range(
    value: float,
    asset: str,
    type: str,
    cause: str | None = None,
    era: str | None = None,
    *,
    db: Path = DEFAULT_DB,
) -> PositionRangeJSON:
    """What past episodes would have meant for a position of `value`, in the asset's currency:
    value times the row's raw-return quantiles, rounded to whole units. An illustration of
    history, never a forecast. Raises ValueError if value <= 0."""
    if value <= 0:
        raise ValueError("value must be positive")
    t, e = _parse_type(type), _parse_era(era)
    rates = RatesDB.open(db)
    try:
        primary, _ = _rows(rates, t, asset, cause, e)
    finally:
        rates.close()
    return PositionRangeJSON(
        value=value,
        currency=CURRENCY[primary.market],
        asset=asset,
        type=t.value,
        cause=cause,
        era=primary.era.value,
        horizon_days=primary.horizon_days,
        basis="raw",
        p10=round(value * primary.raw_p10),
        median=round(value * primary.raw_median),
        p90=round(value * primary.raw_p90),
        n_episodes=primary.n_episodes,
        weak_signal=primary.weak_signal,
    )


def compare(
    type: str,
    assets: Sequence[str],
    cause: str | None = None,
    era: str | None = None,
    *,
    db: Path = DEFAULT_DB,
) -> CompareJSON:
    """2 or 3 assets after the same event type, each re-summarised on the episodes they all
    share, so no asset is scored on years another did not exist. Baselines are the rows' own.
    Assets keep the caller's order; nothing is ranked."""
    if not COMPARE_MIN <= len(set(assets)) == len(assets) <= COMPARE_MAX:
        raise ValueError(f"compare takes {COMPARE_MIN} to {COMPARE_MAX} distinct assets")
    t, e = _parse_type(type), _parse_era(era)
    rates = RatesDB.open(db)
    try:
        primaries = [_rows(rates, t, a, cause, e)[0] for a in assets]
        shared = set.intersection(*(set(r.episode_ids) for r in primaries))
        order = [ep for ep in primaries[0].episode_ids if ep in shared]
        details = [
            {d.episode_id: d for d in rates.episodes(r) if d.episode_id in shared}
            for r in primaries
        ]
    finally:
        rates.close()
    rows: list[CompareAssetJSON] = []
    for rate, by_id in zip(primaries, details, strict=True):
        reactions = [by_id[ep].reaction for ep in order]
        measured = [r.raw_return if rate.measure == "raw" else r.excess_return for r in reactions]
        hits = [is_hit(rate.measure, r.raw_return, r.excess_return) for r in reactions]
        stats = summarize(measured, hits) if order else None
        rows.append(
            CompareAssetJSON(
                asset=rate.asset,
                era=rate.era.value,
                series=rate.series,
                benchmark=rate.benchmark,
                measure=rate.measure,
                n_episodes_all=rate.n_episodes,
                n_hits=stats.n_hits if stats else 0,
                hit_rate=_r(stats.hit_rate) if stats else 0.0,
                baseline=_r(rate.baseline_hit_rate),
                median=_r(stats.median) if stats else 0.0,
                p10=_r(stats.p10) if stats else 0.0,
                p90=_r(stats.p90) if stats else 0.0,
            )
        )
    return CompareJSON(
        type=t.value,
        cause=cause,
        horizon_days=primaries[0].horizon_days,
        episode_ids=order,
        n_episodes=len(order),
        weak_signal=len(order) < WEAK_SIGNAL_MIN_EPISODES,
        assets=rows,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    usage = (
        "usage: odds TYPE ASSET [REGIME] | range VALUE ASSET TYPE | "
        "compare TYPE ASSET ASSET [ASSET] | split TYPE ASSET REGIME_NAME"
    )
    if not args:
        print(usage, file=sys.stderr)
        return 2
    command, rest = args[0], args[1:]
    if command == "odds" and len(rest) in (2, 3):
        out: object = odds(rest[0], rest[1], regime=rest[2] if len(rest) == 3 else None)
    elif command == "split" and len(rest) == 3:
        out = split(rest[0], rest[1], rest[2])
    elif command == "range" and len(rest) == 3:
        out = position_range(float(rest[0]), rest[1], rest[2])
    elif command == "compare" and len(rest) >= 3:
        out = compare(rest[0], rest[1:])
    else:
        print(usage, file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
