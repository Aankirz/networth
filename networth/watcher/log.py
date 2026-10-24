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
from networth.engine.model import Region
from networth.llm import Classified
from networth.watcher.store import Confirmed, Decision, Insight, Rejected, Store
from networth.watcher.triggers import oldest_event


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


@dataclass(frozen=True)
class Age:
    """How the report judges old news: against its own clock, like the cycle does."""

    now: dt.datetime
    max_days: int


def _classification_lines(entry: LogEntry, age: Age) -> list[str]:
    c = entry.decision.story.classification
    if c is None:
        return ["classification: not yet"]
    if not isinstance(c, Classified):
        region = f", region {c.region.value}" if c.region else ""
        return [f"classification: none{region} ({c.reason})"]
    lines = [f"classification: {c.type.value} / {c.cause}, dated {c.event_date}, "
             f"region {c.region.value} ({c.reason})"]  # fmt: skip
    if c.event_date < oldest_event(age.now, age.max_days):
        lines.append(f"old news: {c.type.value} dated {c.event_date}, "
                     f"older than {age.max_days} days")  # fmt: skip
    return lines


def _insight_line(i: Insight) -> str:
    o = i.odds
    weak = ", weak signal" if o.get("weak_signal") else ""
    return (f"{i.trigger}-first {i.asset}: hit rate {o.get('hit_rate')} vs baseline "
            f"{o.get('baseline')} over {o.get('n_episodes')} episodes, "
            f"{o.get('horizon_days')}d, {o.get('era')}{weak}")  # fmt: skip


def _story_lines(d: Decision) -> list[str]:
    lines = [f"{d.story.title}  [{d.story.first_seen:%Y-%m-%d %H:%M} UTC]"]
    publishers = ", ".join(d.verdict.publishers)
    if isinstance(d.verdict, Rejected):
        return [*lines, f"  {d.verdict.reason}; publishers: {publishers}"]
    via = (f"primary source {d.verdict.primary_source}" if d.verdict.primary_source
           else f"{len(d.verdict.publishers)} publishers")  # fmt: skip
    return [*lines, f"  confirmed via {via}; publishers: {publishers}"]


def _events(confirmed: Sequence[LogEntry]) -> list[list[LogEntry]]:
    """Confirmed stories the judge dated to the same event, in first-seen order. A story with
    no engine type is an event of its own."""
    events: dict[object, list[LogEntry]] = {}
    for e in confirmed:
        c = e.decision.story.classification
        key = (c.type, c.event_date) if isinstance(c, Classified) else e.decision.story.id
        events.setdefault(key, []).append(e)
    return list(events.values())


def render_event(event: Sequence[LogEntry], age: Age) -> list[str]:
    first = event[0]
    c = first.decision.story.classification
    lines: list[str] = []
    indent = "  "
    if isinstance(c, Classified):
        lines.append(f"  EVENT {c.type.value} on {c.event_date}")
        indent = "    "
    lines += [indent + line for e in event for line in _story_lines(e.decision)]
    insights = {i.id: i for e in event for i in e.insights}.values()
    tail = [*_classification_lines(first, age), *(_insight_line(i) for i in insights)]
    return lines + [f"{indent}  {line}" for line in tail]


def india_line(entries: Sequence[LogEntry]) -> str:
    india = [e for e in entries if isinstance(e.decision.verdict, Confirmed)
             and e.decision.story.classification is not None
             and e.decision.story.classification.region is Region.IN]  # fmt: skip
    if not india:
        return "Newest confirmed India story: none in window"
    story = max(
        india, key=lambda e: (e.decision.story.first_seen, e.decision.story.id)
    ).decision.story
    c = story.classification
    kind = c.type.value if isinstance(c, Classified) else "none"
    return f"Newest confirmed India story: {story.title} ({story.first_seen:%Y-%m-%d}), {kind}"


def render_log(entries: Sequence[LogEntry], age: Age) -> list[str]:
    confirmed = [e for e in entries if isinstance(e.decision.verdict, Confirmed)]
    rejected = [e for e in entries if isinstance(e.decision.verdict, Rejected)]
    lines = [india_line(entries), "", f"CONFIRMED ({len(confirmed)})"]
    lines += [line for ev in _events(confirmed) for line in render_event(ev, age)] or ["  none"]
    lines += ["", f"REJECTED ({len(rejected)})"]
    lines += [f"  {line}" for e in rejected for line in _story_lines(e.decision)] or ["  none"]
    return lines
