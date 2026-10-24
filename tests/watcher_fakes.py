"""Fakes at the two paid boundaries: the news search and the models. No network."""

from __future__ import annotations

import datetime as dt
import json
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

import httpx2
import pandas as pd

from networth.config import Query
from networth.engine.model import EventType, Region
from networth.llm import (
    AllowedCauses,
    ArticleBrief,
    Classification,
    Classified,
    EventBrief,
    Group,
    Grouping,
    NotAnEvent,
    StoryBrief,
    StoryForJudge,
)
from networth.watcher.prices import RecentCloses
from networth.watcher.store import normalize_url

FIXTURES = Path(__file__).with_name("fixtures")
NOW = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.UTC)
EVENT_DAY = dt.date(2026, 10, 24)
FAKE_ENV = {"OPENAI_API_KEY": "sk-test-not-real", "EXA_API_KEY": "exa-test-not-real"}


def fixture_results() -> list[dict]:
    return json.loads((FIXTURES / "articles.json").read_text(encoding="utf-8"))


def story_labels() -> dict[str, str]:
    """normalized url -> the story the fixture says it belongs to."""
    return {normalize_url(r["url"]): r["_story"] for r in fixture_results() if r.get("url")}


class FakeSearch:
    """Every fixture result for the first query, nothing for the rest."""

    def __init__(self, results: list[dict] | None = None) -> None:
        self.results = fixture_results() if results is None else results
        self.calls = 0

    def search(self, query: Query, since: dt.datetime) -> list[Mapping[str, object]]:
        self.calls += 1
        return self.results if self.calls == 1 else []


class FakeModels:
    """Groups by the fixture's story label, titles each new story with its label, and
    classifies by a label -> answer table."""

    def __init__(
        self,
        answers: Mapping[str, Classification] | None = None,
        related: Mapping[str, str] | None = None,
    ) -> None:
        self.labels = story_labels()
        self.related = related or {}  # rejected story title -> event key it is about
        self.related_asked: list[list[str]] = []
        self.answers = (
            answers
            if answers is not None
            else {
                "rbi_hike": Classified(
                    EventType.RBI_HIKE, "inflation", EVENT_DAY, Region.IN, "repo rate raised"
                ),
                "opec_cut": Classified(
                    EventType.OIL_SUPPLY, "opec_cut", EVENT_DAY, Region.GLOBAL, "OPEC+ cut output"
                ),
            }
        )
        self.group_calls: list[int] = []
        self.classified: list[str] = []

    def group_articles(
        self, articles: Sequence[ArticleBrief], open_stories: Sequence[StoryBrief]
    ) -> Grouping:
        self.group_calls.append(len(articles))
        existing = {s.title: s.id for s in open_stories}
        by_label: dict[str, list[str]] = {}
        for a in articles:
            by_label.setdefault(self.labels[a.id], []).append(a.id)
        return Grouping(
            tuple(Group(existing.get(label), label, tuple(ids)) for label, ids in by_label.items())
        )

    def classify_story(self, story: StoryForJudge, allowed: AllowedCauses) -> Classification:
        self.classified.append(story.title)
        return self.answers.get(story.title, NotAnEvent("not a market event"))

    def match_related(
        self, events: Sequence[EventBrief], stories: Sequence[StoryForJudge]
    ) -> dict[str, str | None]:
        self.related_asked.append([s.title for s in stories])
        keys = {e.key for e in events}
        return {s.id: k if (k := self.related.get(s.title)) in keys else None for s in stories}


class NeverConnects(httpx2.BaseTransport):
    """A transport whose connect never completes, like an IPv6 SYN with no answer."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        self.release.wait(60)
        raise httpx2.ConnectError("never connected", request=request)


class FakeCloses:
    """Fresh closes for every asset asked for: a flat line, so nothing jumps."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def __call__(self, assets: Sequence[str]) -> RecentCloses:
        self.asked += assets
        days = pd.bdate_range(end=NOW.date(), periods=80)
        return RecentCloses({a: pd.Series(100.0, index=days) for a in assets}, {})
