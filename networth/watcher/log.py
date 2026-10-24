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


def _events(confirmed: Sequence[LogEntry]) -> dict[str, list[LogEntry]]:
    """Confirmed stories the judge dated to the same event, keyed "type:event_date", in
    first-seen order. A story with no engine type is an event of its own, keyed by its id."""
    events: dict[str, list[LogEntry]] = {}
    for e in confirmed:
        story = e.decision.story
        events.setdefault(story.event_key or story.id, []).append(e)
    return events


def render_event(
    event: Sequence[LogEntry], age: Age, related: Sequence[LogEntry] = ()
) -> list[str]:
    """The event's confirmed stories, its classification and numbers, then the rejected
    stories about the same subject, each with its own reason."""
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
    lines += [f"{indent}  {line}" for line in tail]
    if related:
        lines.append(f"{indent}reports on the same subject we did not confirm ({len(related)}):")
        lines += [f"{indent}  {line}" for e in related for line in _story_lines(e.decision)]
    return lines


def india_line(entries: Sequence[LogEntry], age: Age) -> str:
    india = [e for e in entries if isinstance(e.decision.verdict, Confirmed)
             and e.decision.story.classification is not None
             and e.decision.story.classification.region is Region.IN]  # fmt: skip
    if not india:
        return "Newest confirmed India story: none in window"
    story = max(
        india, key=lambda e: (e.decision.story.first_seen, e.decision.story.id)
    ).decision.story
    c = story.classification
    kind = "not one of the event types we count"
    if isinstance(c, Classified):
        old = c.event_date < oldest_event(age.now, age.max_days)
        kind = f"{c.type.value} dated {c.event_date}{', old news' if old else ''}"
    return f"Newest confirmed India story: {story.title} ({story.first_seen:%Y-%m-%d}), {kind}"


def render_log(entries: Sequence[LogEntry], age: Age) -> list[str]:
    """Rejected stories about a confirmed event print under that event, so a rejected "RBI
    holds" never sits in a separate list from the RBI hike it contradicts."""
    confirmed = [e for e in entries if isinstance(e.decision.verdict, Confirmed)]
    rejected = [e for e in entries if isinstance(e.decision.verdict, Rejected)]
    events = _events(confirmed)
    related: dict[str, list[LogEntry]] = {}
    unrelated: list[LogEntry] = []
    for e in rejected:
        key = e.decision.story.related_event
        if key in events:
            related.setdefault(key, []).append(e)
        else:
            unrelated.append(e)
    lines = [india_line(entries, age), "", f"CONFIRMED ({len(confirmed)})"]
    lines += [line for key, ev in events.items()
              for line in render_event(ev, age, related.get(key, ()))] or ["  none"]  # fmt: skip
    lines += ["", f"REJECTED ({len(rejected)})"]
    if under_events := len(rejected) - len(unrelated):
        lines.append(f"  {under_events} listed above, under the confirmed event they are about")
    lines += [f"  {line}" for e in unrelated for line in _story_lines(e.decision)] or ["  none"]
    return lines
