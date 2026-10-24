"""Ask the judge model, once per confirmed story, which engine event type and cause it is.

The allowed table is every (type, cause) in events.csv, read through backtest.parse_events.
A story with an answer (including "none") is never asked again. Stories past the per-cycle cap
wait for the next cycle, and the count says so.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from networth import net
from networth.engine.backtest import EVENTS_CSV, parse_events
from networth.llm import AllowedCauses, ArticleBrief, Models, StoryForJudge
from networth.watcher.store import Confirmed, Store, Verdict


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
        briefs = tuple(ArticleBrief(a.url, a.publisher, a.title, a.summary)
                       for a in articles.get(story.id, []))  # fmt: skip
        try:
            answer = models.classify_story(StoryForJudge(story.id, story.title, briefs), allowed)
        except net.CallFailed as exc:
            errors.append(str(exc))
            continue
        store.set_classification(story.id, answer, now)
        classified += 1
    return ClassifyResult(classified, max(0, len(pending) - cap), tuple(errors))
