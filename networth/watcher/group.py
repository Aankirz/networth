"""Group new articles into stories with the cheap model, then decide in plain code which
stories are confirmed.

Only articles with no story are sent to the model, so a cycle with nothing new makes no call.
A story is confirmed when one article comes from a primary source (a configured domain or its
subdomain, or an investor-relations host), or when at least min_publishers distinct origins
published inside one window_hours window. Wire reposts share an origin, so they count once.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from networth import net
from networth.config import ConfirmConfig
from networth.llm import ArticleBrief, Grouping, Models, StoryBrief
from networth.watcher.store import (
    Article,
    Confirmed,
    NewStory,
    Rejected,
    Store,
    Verdict,
    host_of,
    story_id_for,
)


@dataclass(frozen=True)
class GroupResult:
    calls: int
    new_stories: int
    assigned: int
    repairs: tuple[str, ...]
    errors: tuple[str, ...]


def _brief(a: Article) -> ArticleBrief:
    return ArticleBrief(a.url, a.publisher, a.title, a.summary)


def _apply(grouping: Grouping, batch: Sequence[Article], store: Store) -> tuple[int, int]:
    by_url = {a.url: a for a in batch}
    new: list[NewStory] = []
    urls_by_story: dict[str, list[str]] = {}
    for g in grouping.groups:
        members = sorted((by_url[u] for u in g.article_ids), key=lambda a: (a.published_at, a.url))
        story_id = g.existing_story_id
        if story_id is None:
            story_id = story_id_for(members[0].url)
            new.append(NewStory(story_id, g.title or members[0].title, members[0].published_at))
        urls_by_story.setdefault(story_id, []).extend(a.url for a in members)
    store.assign(new, urls_by_story)
    return len(new), sum(len(u) for u in urls_by_story.values())


def assign_stories(
    store: Store, models: Models, batch_size: int, open_since: dt.datetime
) -> GroupResult:
    """Group every unassigned article, batch by batch. A failed call stops grouping for this
    cycle; its articles stay unassigned and are grouped next cycle."""
    pending = store.unassigned_articles()
    calls = new_stories = assigned = 0
    repairs: list[str] = []
    errors: list[str] = []
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        open_stories = [StoryBrief(s.id, s.title) for s in store.stories(since=open_since)]
        calls += 1
        try:
            grouping = models.group_articles([_brief(a) for a in batch], open_stories)
        except net.CallFailed as exc:
            errors.append(str(exc))
            break
        repairs += grouping.repairs
        n_new, n_assigned = _apply(grouping, batch, store)
        new_stories += n_new
        assigned += n_assigned
    return GroupResult(calls, new_stories, assigned, tuple(repairs), tuple(errors))


def primary_source(url: str, cfg: ConfirmConfig) -> str | None:
    host = host_of(url)
    for domain in cfg.primary_domains:
        if host == domain or host.endswith("." + domain):
            return domain
    if any(host.startswith(p) for p in cfg.primary_host_prefixes):
        return host
    return None


def most_origins_in_window(articles: Sequence[Article], window: dt.timedelta) -> int:
    """The largest number of distinct origins among articles published inside any one window."""
    ordered = sorted(articles, key=lambda a: a.published_at)
    best = lo = 0
    for hi, a in enumerate(ordered):
        while a.published_at - ordered[lo].published_at > window:
            lo += 1
        best = max(best, len({x.origin for x in ordered[lo : hi + 1]}))
    return best


def confirm(articles: Sequence[Article], cfg: ConfirmConfig) -> Verdict:
    publishers = tuple(sorted({a.origin for a in articles}))
    for a in articles:
        source = primary_source(a.url, cfg)
        if source is not None:
            return Confirmed(publishers, source)
    n = most_origins_in_window(articles, dt.timedelta(hours=cfg.window_hours))
    if n >= cfg.min_publishers:
        return Confirmed(publishers, None)
    if len(publishers) == 1:
        return Rejected("rejected: 1 publisher, no primary source", publishers)
    reason = (
        f"rejected: {n} publisher{'s' if n != 1 else ''} in {cfg.window_hours}h "
        f"(need {cfg.min_publishers}), "
        "no primary source"
    )
    return Rejected(reason, publishers)


def decide(store: Store, cfg: ConfirmConfig, now: dt.datetime) -> Mapping[str, Verdict]:
    """Recompute every story's verdict from its current articles and store it."""
    verdicts = {sid: confirm(arts, cfg) for sid, arts in store.articles_by_story().items()}
    store.put_decisions(verdicts, now)
    return verdicts
