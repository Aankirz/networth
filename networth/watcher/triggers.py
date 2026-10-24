"""Turn confirmed, classified stories into Insight rows that hold only engine numbers.

News first: each confirmed story with an engine type and an event no older than the cycle's
cutoff looks up odds(type, asset) for every asset configured for that type in the story's
region: an India story only Indian assets, a US story only US assets, a global one all.

Price first: an asset whose latest daily return (excess over its benchmark, or raw for an
index) moves more than price_multiple times the standard deviation of the previous
vol_window_days returns is a jump. A jump inside the lookback looks for the confirmed story
behind it: a classified story whose type lists that asset. With one, it writes a price-trigger
Insight; without one, it says so in the notes.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pandas as pd

from networth.config import TriggerConfig
from networth.engine.backtest import market_of
from networth.engine.model import Market, Region
from networth.engine.odds import NoBaseRate
from networth.llm import Classified
from networth.watcher.store import Confirmed, Insight, Store, Story, Trigger, Verdict

OddsFn = Callable[[str, str], Mapping[str, object]]  # (type, asset) -> the odds() dict
LoadCloses = Callable[[str], pd.Series]


@dataclass(frozen=True)
class PriceJump:
    asset: str
    benchmark: str | None
    date: dt.date
    move: float  # the day's return, excess over the benchmark when there is one
    sigma: float  # std of the previous window's returns, same basis


@dataclass(frozen=True)
class TriggerResult:
    insights: int
    jumps: tuple[PriceJump, ...]
    notes: tuple[str, ...]


def price_jump(
    asset_closes: pd.Series,
    bench_closes: pd.Series | None,
    multiple: float,
    window: int,
    asset: str = "",
    benchmark: str | None = None,
) -> PriceJump | None:
    returns = asset_closes.pct_change()
    if bench_closes is not None:
        returns = returns - bench_closes.pct_change()  # aligned on dates both series have
    returns = returns.dropna()
    if len(returns) < window + 1:
        return None
    move, sigma = float(returns.iloc[-1]), float(returns.iloc[-window - 1 : -1].std())
    if abs(move) <= multiple * sigma:
        return None
    return PriceJump(asset, benchmark, returns.index[-1].date(), move, sigma)


def oldest_event(now: dt.datetime, max_age_days: int) -> dt.date:
    """The earliest event date that still counts as news on this cycle's date."""
    return now.date() - dt.timedelta(days=max_age_days)


def _fresh_confirmed(
    store: Store, verdicts: Mapping[str, Verdict], oldest: dt.date
) -> list[tuple[Story, Classified]]:
    return [(s, s.classification) for s in store.stories()
            if isinstance(s.classification, Classified)
            and s.classification.event_date >= oldest
            and isinstance(verdicts.get(s.id), Confirmed)]  # fmt: skip


def _assets_for(c: Classified, cfg: TriggerConfig, notes: list[str]) -> list[str]:
    assets = cfg.assets_by_type.get(c.type, ())
    if c.region is Region.GLOBAL:
        return list(assets)
    market = Market(c.region.value)
    kept: list[str] = []
    for asset in assets:
        try:
            if market_of(asset) == market:
                kept.append(asset)
        except ValueError as exc:
            notes.append(f"skipped {asset} for {c.type.value}: {exc}")
    return kept


def _insight(
    story: Story, c: Classified, asset: str, trigger: Trigger, odds_fn: OddsFn
) -> Insight | str:
    try:
        odds = odds_fn(c.type.value, asset)
    except (NoBaseRate, ValueError) as exc:
        return f"no odds for {c.type.value} on {asset}: {exc}"
    return Insight(story.id, trigger, asset, c.type.value, c.cause, c.event_date, odds)


def write_insights(
    store: Store,
    verdicts: Mapping[str, Verdict],
    cfg: TriggerConfig,
    odds_fn: OddsFn,
    load_closes: LoadCloses,
    since: dt.datetime,
    now: dt.datetime,
    oldest: dt.date,
) -> TriggerResult:
    """since bounds the price jumps, oldest the events behind any insight."""
    jumps, notes = _jumps(cfg, load_closes, since)
    stories = [(s, c, _assets_for(c, cfg, notes))
               for s, c in _fresh_confirmed(store, verdicts, oldest)]  # fmt: skip
    made: list[Insight | str] = [
        _insight(s, c, asset, "news", odds_fn) for s, c, assets in stories for asset in assets
    ]
    for jump in jumps:
        behind = [(s, c) for s, c, assets in stories if jump.asset in assets]
        if not behind:
            notes.append(f"price jump on {jump.asset} ({jump.move:+.2%} on {jump.date}, "
                         f"sigma {jump.sigma:.2%}), no confirmed story")  # fmt: skip
        made += [_insight(s, c, jump.asset, "price", odds_fn) for s, c in behind]
    by_event: dict[str, Insight] = {}
    for m in made:
        if isinstance(m, Insight):
            by_event.setdefault(m.id, m)
    insights = list(by_event.values())
    store.put_insights(insights, now)
    notes += [m for m in made if isinstance(m, str)]
    return TriggerResult(len(insights), tuple(jumps), tuple(notes))


def _jumps(
    cfg: TriggerConfig, load_closes: LoadCloses, since: dt.datetime
) -> tuple[list[PriceJump], list[str]]:
    jumps: list[PriceJump] = []
    notes: list[str] = []
    for watch in cfg.price_watch:
        try:
            closes = load_closes(watch.asset)
            bench = load_closes(watch.benchmark) if watch.benchmark else None
        except (OSError, ValueError, KeyError) as exc:
            notes.append(f"no prices for {watch.asset}: {type(exc).__name__}")
            continue
        jump = price_jump(closes, bench, cfg.price_multiple, cfg.vol_window_days,
                          watch.asset, watch.benchmark)  # fmt: skip
        if jump is not None and jump.date >= since.date():
            jumps.append(jump)
    return jumps, notes
