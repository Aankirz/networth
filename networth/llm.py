"""The model layer: one function per call shape, keyed by role, over the OpenAI Responses API.

    models = OpenAIModels(cfg, log_path=DATA_DIR / "llm_calls.jsonl")
    grouping = models.group_articles(articles, open_stories)   # role cheap
    verdict = models.classify_story(story, allowed_causes)     # role judge
    related = models.match_related(events, rejected_stories)   # role cheap

Model output is parsed into pydantic wire types, then validated here against the inputs and
the allowed table. The watcher only sees the dataclasses below. Watcher code takes a `Models`
object, so tests pass a fake and never touch the network.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import openai
from pydantic import BaseModel

from networth import net
from networth.config import Config, Role
from networth.engine.model import EventType, Region

SNIPPET_CHARS: Final = 300
STORY_ARTICLES_FOR_JUDGE: Final = 8
OPENAI_MAX_RETRIES: Final = 1
NONE_TYPE: Final = "none"
INVALID_OUTPUT: Final = "invalid model output"

AllowedCauses = Mapping[EventType, tuple[str, ...]]


@dataclass(frozen=True)
class ArticleBrief:
    id: str
    publisher: str
    title: str
    snippet: str
    published: str = ""  # ISO date as the search reported it, which can be a recrawl date


@dataclass(frozen=True)
class StoryBrief:
    id: str
    title: str


@dataclass(frozen=True)
class Group:
    """Articles about one real-world event. existing_story_id None means a new story."""

    existing_story_id: str | None
    title: str
    article_ids: tuple[str, ...]


@dataclass(frozen=True)
class Grouping:
    groups: tuple[Group, ...]
    repairs: tuple[str, ...] = ()  # how a rule-breaking model answer was fixed up


@dataclass(frozen=True)
class StoryForJudge:
    id: str
    title: str
    articles: tuple[ArticleBrief, ...]
    today: dt.date


@dataclass(frozen=True)
class Classified:
    """The judge's answer, a fact about the event that never changes. Whether the event is
    recent enough to act on is decided each cycle against the clock, not stored here."""

    type: EventType
    cause: str
    event_date: dt.date
    region: Region
    reason: str


@dataclass(frozen=True)
class NotAnEvent:
    reason: str
    region: Region | None = None  # None when the model gave no usable answer


Classification = Classified | NotAnEvent


@dataclass(frozen=True)
class EventBrief:
    """A confirmed event, keyed "type:event_date", that rejected stories may be about."""

    key: str
    title: str


class Models(Protocol):
    def group_articles(
        self, articles: Sequence[ArticleBrief], open_stories: Sequence[StoryBrief]
    ) -> Grouping: ...

    def classify_story(self, story: StoryForJudge, allowed: AllowedCauses) -> Classification: ...

    def match_related(
        self, events: Sequence[EventBrief], stories: Sequence[StoryForJudge]
    ) -> Mapping[str, str | None]: ...


class _WireGroup(BaseModel):
    existing_story_id: str  # "" for a new story
    title: str
    article_ids: list[str]


class _WireGrouping(BaseModel):
    groups: list[_WireGroup]


class _WireMatch(BaseModel):
    story_id: str
    event_id: str  # "" when the story is about none of the events


class _WireMatches(BaseModel):
    matches: list[_WireMatch]


class _WireClassification(BaseModel):
    type: str
    cause: str
    event_date: str  # YYYY-MM-DD the event itself happened, "" for none
    region: str
    reason: str


GROUP_INSTRUCTIONS: Final = """You group news articles into stories. A story is one real-world
event (one rate decision, one attack, one tariff announcement). Articles that report the same
event belong together even when worded differently; articles about different events never do.
Put each article id in exactly one group. If an article reports the same event as one of the
open stories, use that story's id as existing_story_id; otherwise leave existing_story_id
empty and write a short neutral title for the new story."""

CLASSIFY_INSTRUCTIONS: Final = """You map one confirmed news story to a market event type from
a fixed table, or to "none". Pick a type only when the story reports that event itself
happening (a decision announced, a war started, a tariff imposed), not commentary, previews,
expectations or anniversaries. The cause must be one of the causes listed for that type.
If nothing fits, answer type "none" and cause "". Give event_date, the day the event itself
happened (YYYY-MM-DD), read from the article text, not from the published dates, which can be
recrawl dates. Articles often mention older events; date the event, not the article. Give
region for every answer, "none" included: "in" when the event happens in India or is about
India's market, "us" when it happens in the US or is about the US market, "global" when it
moves markets everywhere (a war, an OPEC decision, a pandemic). Give a one-sentence reason."""

RELATED_INSTRUCTIONS: Final = """You match unconfirmed news stories to confirmed market events.
A story matches an event when it is about the same subject: the same central bank's policy
rate, the same tariff action, the same bank, the same outbreak, the same conflict. Older,
earlier or conflicting reports on that subject match too (a report that the RBI held its rate
matches an RBI rate hike event). A story about anything else matches nothing. Answer one entry
per story: its id and the matching event id, or "" for none."""


def fallback_grouping(articles: Sequence[ArticleBrief], reason: str) -> Grouping:
    """One new story per article, so no article is dropped when the model gave no answer."""
    groups = tuple(Group(None, a.title, (a.id,)) for a in articles)
    return Grouping(groups, (reason,))


def validate_grouping(
    wire: _WireGrouping | None,
    articles: Sequence[ArticleBrief],
    open_stories: Sequence[StoryBrief],
    short_ids: Mapping[str, str],
) -> Grouping:
    """short_ids maps the prompt's short ids back to article ids. A rule-breaking answer is
    repaired, not discarded: unknown ids are dropped, an article placed twice stays in its first
    group, an unknown story id becomes a new story, and an article left out becomes its own
    story. Discarding the whole answer for one slip split every story into single-publisher
    rejections on the first live run."""
    if wire is None:
        return fallback_grouping(articles, "no parsed output")
    known_stories = {s.id for s in open_stories}
    seen: set[str] = set()
    repairs: list[str] = []
    groups: list[Group] = []
    for g in wire.groups:
        unknown = [i for i in g.article_ids if i not in short_ids]
        twice = [i for i in g.article_ids if i in seen]
        ids = list(dict.fromkeys(i for i in g.article_ids if i in short_ids and i not in seen))
        if unknown:
            repairs.append(f"unknown article ids {unknown}")
        if twice:
            repairs.append(f"articles placed twice {twice}")
        existing = g.existing_story_id or None
        if existing is not None and existing not in known_stories:
            repairs.append(f"unknown story id {existing!r}, made a new story")
            existing = None
        if not ids:
            continue
        seen.update(ids)
        groups.append(Group(existing, g.title.strip(), tuple(short_ids[i] for i in ids)))
    missing = [short for short in short_ids if short not in seen]
    if missing:
        repairs.append(f"{len(missing)} articles left out, each made its own story")
        by_id = {a.id: a for a in articles}
        groups += [Group(None, by_id[short_ids[m]].title, (short_ids[m],)) for m in missing]
    return Grouping(tuple(groups), tuple(repairs))


def validate_classification(
    wire: _WireClassification | None, allowed: AllowedCauses
) -> Classification:
    """The model names the event, its date and its region. Whether that date is recent enough
    is decided each cycle in triggers, so a verdict never depends on when it was asked."""
    if wire is None:
        return NotAnEvent(INVALID_OUTPUT)
    try:
        region = Region(wire.region)
    except ValueError:
        return NotAnEvent(f"{INVALID_OUTPUT}: region {wire.region!r}")
    if wire.type == NONE_TYPE:
        return NotAnEvent(wire.reason, region)
    try:
        event_type = EventType(wire.type)
    except ValueError:
        return NotAnEvent(INVALID_OUTPUT)
    if event_type not in allowed or wire.cause not in allowed[event_type]:
        return NotAnEvent(INVALID_OUTPUT)
    try:
        event_date = dt.date.fromisoformat(wire.event_date)
    except ValueError:
        return NotAnEvent(f"{INVALID_OUTPUT}: no event date")
    return Classified(event_type, wire.cause, event_date, region, wire.reason)


def validate_matches(
    wire: _WireMatches | None, events: Mapping[str, str], stories: Mapping[str, str]
) -> dict[str, str | None]:
    """events and stories map the prompt's short ids back to event keys and story ids. Every
    story gets an answer; an unknown event id, or no answer at all, means no match."""
    answers = {m.story_id: events.get(m.event_id) for m in (wire.matches if wire else [])}
    return {story_id: answers.get(short) for short, story_id in stories.items()}


def _related_prompt(
    events: Sequence[EventBrief], stories: Sequence[StoryForJudge]
) -> tuple[str, dict[str, str], dict[str, str]]:
    event_ids = {f"e{i}": e.key for i, e in enumerate(events, start=1)}
    story_ids = {f"s{i}": s.id for i, s in enumerate(stories, start=1)}
    payload = {
        "events": [{"id": short, "type_and_date": e.key, "title": e.title}
                   for short, e in zip(event_ids, events, strict=True)],
        "stories": [{"id": short, "title": s.title,
                     "snippet": s.articles[0].snippet[:SNIPPET_CHARS] if s.articles else ""}
                    for short, s in zip(story_ids, stories, strict=True)],
    }  # fmt: skip
    return json.dumps(payload, ensure_ascii=False), event_ids, story_ids


def _group_prompt(
    articles: Sequence[ArticleBrief], open_stories: Sequence[StoryBrief]
) -> tuple[str, dict[str, str]]:
    short_ids = {f"a{i}": a.id for i, a in enumerate(articles, start=1)}
    payload = {
        "open_stories": [{"id": s.id, "title": s.title} for s in open_stories],
        "articles": [
            {"id": short, "publisher": a.publisher, "title": a.title,
             "snippet": a.snippet[:SNIPPET_CHARS]}
            for short, a in zip(short_ids, articles, strict=True)
        ],
    }  # fmt: skip
    return json.dumps(payload, ensure_ascii=False), short_ids


def _classify_prompt(story: StoryForJudge, allowed: AllowedCauses) -> str:
    payload = {
        "today": story.today.isoformat(),
        "allowed": {t.value: list(causes) for t, causes in allowed.items()},
        "story": {
            "title": story.title,
            "articles": [
                {"publisher": a.publisher, "published": a.published, "title": a.title,
                 "snippet": a.snippet[:SNIPPET_CHARS]}
                for a in story.articles[:STORY_ARTICLES_FOR_JUDGE]
            ],
        },
    }  # fmt: skip
    return json.dumps(payload, ensure_ascii=False)


class OpenAIModels:
    """Models over the OpenAI SDK. A failed or timed-out call raises net.CallFailed, already
    logged; an answer that parses but breaks the rules is handled by the validators."""

    def __init__(self, cfg: Config, log_path: Path, client: openai.OpenAI | None = None) -> None:
        self._cfg = cfg
        self._log_path = log_path
        self._client = client or openai.OpenAI(
            api_key=cfg.secrets.openai_api_key,
            http_client=net.ipv4_client(cfg.http.openai_deadline_s, cfg.http.connect_timeout_s),
            max_retries=OPENAI_MAX_RETRIES,
            timeout=cfg.http.openai_deadline_s,
        )

    def _parse[W: BaseModel](
        self, role: Role, call: str, instructions: str, prompt: str, wire: type[W]
    ) -> W | None:
        rc = self._cfg.roles[role]
        price = self._cfg.price_of(role)

        def request() -> tuple[W | None, net.Usage]:
            resp = self._client.responses.parse(
                model=rc.model,
                instructions=instructions,
                input=prompt,
                text_format=wire,
                reasoning={"effort": rc.reasoning_effort},
                max_output_tokens=rc.max_output_tokens,
                store=False,
            )
            u = resp.usage
            if u is None:
                return resp.output_parsed, net.Usage()
            cached = u.input_tokens_details.cached_tokens
            cost = price.cost(u.input_tokens, cached, u.output_tokens)
            return resp.output_parsed, net.Usage(u.input_tokens, cached, u.output_tokens, cost)

        return net.metered(
            request,
            call=call,
            role=role.value,
            model=rc.model,
            deadline_s=self._cfg.http.openai_deadline_s,
            log_path=self._log_path,
        )

    def group_articles(
        self, articles: Sequence[ArticleBrief], open_stories: Sequence[StoryBrief]
    ) -> Grouping:
        prompt, short_ids = _group_prompt(articles, open_stories)
        wire = self._parse(Role.CHEAP, "group_articles", GROUP_INSTRUCTIONS, prompt, _WireGrouping)
        return validate_grouping(wire, articles, open_stories, short_ids)

    def classify_story(self, story: StoryForJudge, allowed: AllowedCauses) -> Classification:
        prompt = _classify_prompt(story, allowed)
        wire = self._parse(
            Role.JUDGE, "classify_story", CLASSIFY_INSTRUCTIONS, prompt, _WireClassification
        )
        return validate_classification(wire, allowed)

    def match_related(
        self, events: Sequence[EventBrief], stories: Sequence[StoryForJudge]
    ) -> dict[str, str | None]:
        prompt, event_ids, story_ids = _related_prompt(events, stories)
        wire = self._parse(Role.CHEAP, "match_related", RELATED_INSTRUCTIONS, prompt, _WireMatches)
        return validate_matches(wire, event_ids, story_ids)
