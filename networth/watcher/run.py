"""One watcher cycle: pull, group, confirm, classify, trigger, log.

Run: uv run python -m networth.watcher.run --once

Every step reads the state the store already holds and adds only what is missing, so a
second run on the same news adds no articles, makes no grouping call and asks the judge
nothing new. A failed Exa or OpenAI call is logged and recorded in the cycle's errors; the
cycle still finishes. A missing key exits 2 with a one-line message.
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from networth import net
from networth.config import CONFIG_TOML, DATA_DIR, ENV_FILE, Config, ConfigError, load_config
from networth.engine import fetch, odds
from networth.llm import Models, OpenAIModels
from networth.watcher import classify, group, log, triggers
from networth.watcher.pull import ExaSearch, NewsSearch, pull
from networth.watcher.store import Confirmed, Cycle, Rejected, Store


@dataclass(frozen=True)
class Paths:
    data_dir: Path

    @property
    def watcher_db(self) -> Path:
        return self.data_dir / "watcher.sqlite"

    @property
    def call_log(self) -> Path:
        return self.data_dir / "llm_calls.jsonl"

    @property
    def prices_dir(self) -> Path:
        return self.data_dir / "prices"

    @property
    def rates_db(self) -> Path:
        return self.data_dir / "base_rates.sqlite"


@dataclass(frozen=True)
class CycleOutcome:
    cycle: Cycle
    rejected_by_reason: Mapping[str, int]
    notes: tuple[str, ...]


def run_cycle(
    cfg: Config, paths: Paths, search: NewsSearch, models: Models, now: dt.datetime
) -> CycleOutcome:
    since = now - dt.timedelta(hours=cfg.pull.lookback_hours)
    calls_before = len(net.read_records(paths.call_log))
    store = Store.open(paths.watcher_db)
    try:
        pulled = pull(cfg, search, store, now)
        grouped = group.assign_stories(store, models, cfg.group_batch_size, since)
        verdicts = group.decide(store, cfg.confirm, now)
        judged = classify.classify_confirmed(
            store,
            models,
            verdicts,
            classify.allowed_causes(),
            cfg.max_judge_calls_per_cycle,
            now,
        )
        repairs = [f"grouping repaired: {r}" for r in grouped.repairs]
        errors = [*pulled.errors, *grouped.errors, *repairs, *judged.errors]
        if paths.rates_db.exists():
            fired = triggers.write_insights(
                store, verdicts, cfg.triggers,
                functools.partial(odds.odds, db=paths.rates_db),
                functools.partial(fetch.load_series, prices_dir=paths.prices_dir),
                since, now, triggers.oldest_event(now, cfg.event_max_age_days),
            )  # fmt: skip
            insights, jumps, notes = fired.insights, len(fired.jumps), fired.notes
        else:
            errors.append(f"{paths.rates_db} is missing; build it with the engine first")
            insights, jumps, notes = 0, 0, ()
        confirmed = sum(isinstance(v, Confirmed) for v in verdicts.values())
        counts = {
            "exa_results": pulled.results,
            "articles_new": pulled.new_articles,
            "articles_skipped": pulled.skipped,
            **store.counts(),
            "group_calls": grouped.calls,
            "stories_new": grouped.new_stories,
            "confirmed": confirmed,
            "rejected": len(verdicts) - confirmed,
            "classified": judged.classified,
            "classify_over_cap": judged.over_cap,
            "insights": insights,
            "price_jumps": jumps,
        }
        spent = log.spend(net.read_records(paths.call_log)[calls_before:])
        cycle = Cycle(now, dt.datetime.now(dt.UTC), counts, spent.cost_usd, tuple(errors))
        store.add_cycle(cycle)
    finally:
        store.close()
    reasons = Counter(v.reason for v in verdicts.values() if isinstance(v, Rejected))
    return CycleOutcome(cycle, reasons, notes)


def render_outcome(outcome: CycleOutcome) -> list[str]:
    c = outcome.cycle
    seconds = (c.finished_at - c.started_at).total_seconds()
    lines = [f"cycle {c.started_at:%Y-%m-%d %H:%M:%S} UTC, {seconds:.0f}s, "
             f"cost ${c.cost_usd:.4f}"]  # fmt: skip
    lines += [f"  {k:<18} {v}" for k, v in c.counts.items()]
    lines += ["rejected by reason:"]
    lines += [f"  {n:>4}  {r}" for r, n in sorted(outcome.rejected_by_reason.items())] or ["  none"]
    lines += [f"note: {n}" for n in outcome.notes]
    lines += [f"ERROR: {e}" for e in c.errors]
    return lines


def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", required=True, help="run one cycle")
    parser.add_argument("--config", type=Path, default=CONFIG_TOML)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config, args.env_file, environ)
    except ConfigError as exc:
        print(f"networth.watcher.run: {exc}", file=sys.stderr)
        return 2
    paths = Paths(args.data_dir)
    outcome = run_cycle(
        cfg,
        paths,
        ExaSearch(cfg, paths.call_log),
        OpenAIModels(cfg, paths.call_log),
        dt.datetime.now(dt.UTC),
    )
    print("\n".join(render_outcome(outcome)))
    print("\nfull decision log: uv run python -m networth.watcher.report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
