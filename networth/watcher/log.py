"""The decision log: every story with its publishers, verdict and reason, its classification
and the engine numbers it triggered, rendered as plain text. run.py and report.py print it.

Nothing here says what anyone should do with a story; it reports what the watcher decided
and what history's numbers are.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from networth import net
from networth.llm import Classified
from networth.watcher.store import Confirmed, Decision, Insight, Rejected, Store


@dataclass(frozen=True)
class LogEntry:
    decision: Decision
    insights: tuple[Insight, ...]


@dataclass(frozen=True)
class Spend:
    cost_usd: float
    calls: int
    failed: int


def decision_log(store: Store, since: dt.datetime) -> list[LogEntry]:
    by_story: dict[str, list[Insight]] = {}
    for i in store.insights(since):
        by_story.setdefault(i.story_id, []).append(i)
    return [LogEntry(d, tuple(by_story.get(d.story.id, ()))) for d in store.decisions(since)]


def spend(records: Sequence[net.CallRecord]) -> Spend:
    return Spend(sum(r.cost_usd for r in records), len(records), sum(not r.ok for r in records))


def spend_since(log_path: Path, since: dt.datetime) -> Spend:
    return spend([r for r in net.read_records(log_path)
                  if dt.datetime.fromisoformat(r.ts) >= since])  # fmt: skip


def _classification_line(entry: LogEntry) -> str:
    story = entry.decision.story
    c = story.classification
    if c is None:
        return "classification: not yet"
    if isinstance(c, Classified):
        return f"classification: {c.type.value} / {c.cause} ({c.reason})"
    return f"classification: none ({c.reason})"


def _insight_line(i: Insight) -> str:
    o = i.odds
    weak = ", weak signal" if o.get("weak_signal") else ""
    return (f"{i.trigger}-first {i.asset}: hit rate {o.get('hit_rate')} vs baseline "
            f"{o.get('baseline')} over {o.get('n_episodes')} episodes, "
            f"{o.get('horizon_days')}d, {o.get('era')}{weak}")  # fmt: skip


def render_entry(entry: LogEntry) -> list[str]:
    d = entry.decision
    lines = [f"  {d.story.title}  [{d.story.first_seen:%Y-%m-%d %H:%M} UTC]"]
    publishers = ", ".join(d.verdict.publishers)
    if isinstance(d.verdict, Confirmed):
        via = (f"primary source {d.verdict.primary_source}" if d.verdict.primary_source
               else f"{len(d.verdict.publishers)} publishers")  # fmt: skip
        lines += [f"    confirmed via {via}; publishers: {publishers}",
                  f"    {_classification_line(entry)}"]  # fmt: skip
        lines += [f"    {_insight_line(i)}" for i in entry.insights]
    else:
        lines.append(f"    {d.verdict.reason}; publishers: {publishers}")
    return lines


def render_log(entries: Sequence[LogEntry]) -> list[str]:
    confirmed = [e for e in entries if isinstance(e.decision.verdict, Confirmed)]
    rejected = [e for e in entries if isinstance(e.decision.verdict, Rejected)]
    lines = [f"CONFIRMED ({len(confirmed)})"]
    lines += [line for e in confirmed for line in render_entry(e)] or ["  none"]
    lines += ["", f"REJECTED ({len(rejected)})"]
    lines += [line for e in rejected for line in render_entry(e)] or ["  none"]
    return lines
