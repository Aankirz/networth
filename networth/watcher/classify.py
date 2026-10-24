"""Ask the judge model, once per confirmed story, which engine event type and cause it is.

The allowed table is every (type, cause) in events.csv, read through backtest.parse_events.
A story with an answer (including "none") is never asked again. Stories past the per-cycle cap
wait for the next cycle, and the count says so.

Rejected stories are never judged. Instead the cheap model says which confirmed event, if any,
each one is about, so the decision log can show "RBI holds repo rate" under the RBI hike it
contradicts instead of as an unrelated rejection. A story is asked again only when an event
was judged after its last answer.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from networth import net
from networth.engine.backtest import EVENTS_CSV, parse_events
from networth.llm import AllowedCauses, ArticleBrief, EventBrief, Models, StoryForJudge
from networth.watcher.store import Article, Confirmed, Rejected, Store, Story, Verdict


def allowed_causes(path: Path = EVENTS_CSV) -> AllowedCauses:
    events, _ = parse_events(path)
    causes: dict = defaultdict(set)
    for e in events:
        causes[e.type].add(e.cause)
    return {t: tuple(sorted(c)) for t, c in causes.items()}


@dataclass(frozen=True)
class ClassifyResult:
    classified: int
    over_cap: int
    errors: tuple[str, ...]


def _for_judge(story: Story, articles: list[Article], today: dt.date) -> StoryForJudge:
    briefs = tuple(ArticleBrief(a.url, a.publisher, a.title, a.summary,
                                a.published_at.date().isoformat())
                   for a in articles)  # fmt: skip
    return StoryForJudge(story.id, story.title, briefs, today)


def classify_confirmed(
    store: Store,
    models: Models,
    verdicts: Mapping[str, Verdict],
    allowed: AllowedCauses,
    cap: int,
    now: dt.datetime,
) -> ClassifyResult:
    pending = [s for s in store.stories() if s.classified_at is None
               and isinstance(verdicts.get(s.id), Confirmed)]  # fmt: skip
    articles = store.articles_by_story()
    classified = 0
    errors: list[str] = []
    for story in pending[:cap]:
        judged = _for_judge(story, articles.get(story.id, []), now.date())
        try:
            answer = models.classify_story(judged, allowed)
        except net.CallFailed as exc:
            errors.append(str(exc))
            continue
        store.set_classification(story.id, answer, now)
        classified += 1
    return ClassifyResult(classified, max(0, len(pending) - cap), tuple(errors))


@dataclass(frozen=True)
class RelateResult:
    asked: int
    matched: int
    errors: tuple[str, ...]


def relate_rejected(
    store: Store, models: Models, verdicts: Mapping[str, Verdict], cap: int, now: dt.datetime
) -> RelateResult:
    """One cheap call: which confirmed event is each newly rejected story about?"""
    stories = store.stories()
    judged = [s for s in stories if s.event_key and isinstance(verdicts.get(s.id), Confirmed)]
    if not judged:
        return RelateResult(0, 0, ())
    events = {s.event_key: EventBrief(s.event_key, s.title) for s in reversed(judged)}
    newest_event = max(s.classified_at for s in judged if s.classified_at)
    pending = [s for s in stories if isinstance(verdicts.get(s.id), Rejected)
               and (s.related_at is None or s.related_at < newest_event)][:cap]  # fmt: skip
    if not pending:
        return RelateResult(0, 0, ())
    articles = store.articles_by_story()
    asked = [_for_judge(s, articles.get(s.id, []), now.date()) for s in pending]
    try:
        related = models.match_related(tuple(events.values()), asked)
    except net.CallFailed as exc:
        return RelateResult(0, 0, (str(exc),))
    store.set_related(related, now)
    return RelateResult(len(pending), sum(v is not None for v in related.values()), ())
