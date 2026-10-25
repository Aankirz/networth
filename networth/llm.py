"""The model layer: one function per call shape, keyed by role, over the OpenAI Responses API.

    models = OpenAIModels(cfg, log_path=DATA_DIR / "llm_calls.jsonl")
    grouping = models.group_articles(articles, open_stories)   # role cheap
    verdict = models.classify_story(story, allowed_causes)     # role judge
    related = models.match_related(events, rejected_stories)   # role cheap
    text = models.write(task, facts, feedback)                # role writer, PRODUCT.md voice
    seen = models.read_image(jpeg_bytes, "image/jpeg")        # role vision, the image's text
    rows = models.read_holdings(png_bytes, "image/png", "en") # role vision, a holdings table
    intent = models.pick(question, choices, text)             # role cheap, one closed choice

Model output is parsed into pydantic wire types, then validated here against the inputs and
the allowed table. The watcher only sees the dataclasses below. Watcher code takes a `Models`
object, so tests pass a fake and never touch the network.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import openai
from pydantic import BaseModel

from networth import net
from networth.config import REPO, Config, Role
from networth.engine.model import EventType, Region

SNIPPET_CHARS: Final = 300
STORY_ARTICLES_FOR_JUDGE: Final = 8
OPENAI_MAX_RETRIES: Final = 1
NONE_TYPE: Final = "none"
INVALID_OUTPUT: Final = "invalid model output"
VOICE_FILES: Final = (REPO / "knowledge" / "PRODUCT.md", REPO / "knowledge" / "glossary.md")

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


class ChatModels(Protocol):
    """The calls behind what a user reads. write and read_image raise net.CallFailed or
    NoAnswer; pick answers None when the model names no listed choice."""

    def write(self, task: str, facts: str, feedback: str | None = None) -> str: ...

    def read_image(self, image: bytes, mime: str) -> str: ...

    def read_holdings(self, image: bytes, mime: str, lang: str) -> WireHoldings | None: ...

    def pick(self, question: str, choices: Mapping[str, str], text: str) -> str | None: ...

    def same_claim(self, claim: str, articles: Sequence[ArticleBrief]) -> set[str]: ...

    def classify_story(self, story: StoryForJudge, allowed: AllowedCauses) -> Classification: ...


class NoAnswer(Exception):
    """The model replied but gave no usable text."""


class _WireGroup(BaseModel):
    existing_story_id: str  # "" for a new story
    title: str
    article_ids: list[str]


class _WireGrouping(BaseModel):
    groups: list[_WireGroup]


class _WireText(BaseModel):
    text: str


class _WirePick(BaseModel):
    choice: str


class _WireIds(BaseModel):
    ids: list[str]


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


class WireHolding(BaseModel):
    """One row of a holdings screenshot, as written. 0 or "" means the image doesn't show it."""

    name: str
    kind: str  # stock | mutual_fund | etf | fd | bond | other
    identifier: str  # a ticker or ISIN only when the image prints one
    currency: str  # INR | USD
    units: float
    avg_cost: float  # per unit
    invested: float  # the row's total cost
    current_price: float  # per unit
    current_value: float  # the row's total value now
    bought_on: str  # YYYY-MM-DD


class WireHoldings(BaseModel):
    rows: list[WireHolding]
    unread: list[str]  # each part of the table that could not be read, in a few words


GROUP_INSTRUCTIONS: Final = """You group news articles into stories. A story is one real-world
event (one rate decision, one attack, one tariff announcement). Articles that report the same
event belong together even when worded differently; articles about different events never do.
Put each article id in exactly one group. If an article reports the same event as one of the
open stories, use that story's id as existing_story_id; otherwise leave existing_story_id
empty and write a short neutral title for the new story."""

CLASSIFY_INSTRUCTIONS: Final = """You map one confirmed news story to a market event type from a
fixed table, or to "none". Pick a type only when the story reports that event itself happening
(a decision announced, a war started, a tariff imposed), not commentary, previews,
expectations, anniversaries, or a pause, delay, suspension or rollback of the action. The cause
must be one of the causes listed for that type. If nothing fits, answer type "none" and cause
"". Give event_date, the day the event itself happened (YYYY-MM-DD), read from the article
text, not from the published dates, which can be recrawl dates. Articles often mention older
events; date the event, not the article. Give region for every answer, "none" included: "in"
when the event happens in India or is about India's market, "us" when it happens in the US or
is about the US market, "global" when it moves markets everywhere (a war, an OPEC decision, a
pandemic). Give a one-sentence reason."""

RELATED_INSTRUCTIONS: Final = """You match unconfirmed news stories to confirmed market events.
A story matches an event when it is about the same subject: the same central bank's policy
rate, the same tariff action, the same bank, the same outbreak, the same conflict. Older,
earlier or conflicting reports on that subject match too (a report that the RBI held its rate
matches an RBI rate hike event). A story about anything else matches nothing. Answer one entry
per story: its id and the matching event id, or "" for none."""

SAME_CLAIM_INSTRUCTIONS: Final = """You check which news articles report the claim a user was
sent. An article matches only when it reports that same thing happening: the same company,
policy, person or event, and the same direction. Articles on a related subject that do not
report the claim do not match, and neither do articles that deny it. Answer the ids of the
matching articles, or an empty list."""

READ_IMAGE_TASK: Final = """Transcribe every piece of text in this image, in reading order,
exactly as written: names, numbers, dates, labels and their values. Keep each label next to its
value ("Price band: ₹95 to ₹100"). Do not explain, summarise or add anything that is not
written in the image."""


READ_HOLDINGS_TASK: Final = """This image is a screenshot of someone's investment holdings
from a broker or fund app (Groww, Zerodha, Kuvera, a CAS statement, Fidelity, Schwab and the
like). Read every holding row into rows, copying numbers exactly as printed. Never compute,
estimate or fill in a number the image does not print: use 0 for a number and "" for text it
doesn't show. kind is one of stock, mutual_fund, etf, fd, bond, other, from what the row says.
identifier is a ticker or ISIN only when one is printed. currency is INR for ₹ or Rs and USD
for $. bought_on is YYYY-MM-DD only when a buy or start date is printed. Totals, headers and
summary lines are not rows. List in unread anything that looks like a holding but is cut off,
blurred or unreadable, in a few words each. If the image is not a holdings screen, answer no
rows and say so in unread."""


NO_DASHES: Final = "Never use long dashes (— or –). Write short sentences instead."
LONG_DASH: Final = re.compile(r"\s*(—|(?<!\d)–|–(?!\d))\s*")


def undash(text: str) -> str:
    """Long dashes the writer used anyway become a comma; a range like ₹410–432 stays."""
    return LONG_DASH.sub(", ", text)


def voice() -> str:
    """PRODUCT.md and the glossary, read once per call so an edit needs no restart."""
    return "\n\n".join(path.read_text(encoding="utf-8") for path in VOICE_FILES)


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
        self, role: Role, call: str, instructions: str, prompt: str | list, wire: type[W]
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

    def write(self, task: str, facts: str, feedback: str | None = None) -> str:
        """The writer words `facts` for a user. PRODUCT.md and the glossary are its system
        prompt, as PRODUCT.md requires of every agent; `task` says what to write."""
        prompt = facts if feedback is None else (
            f"{facts}\n\nYour last draft was blocked: {feedback}. Write it again without that."
        )  # fmt: skip
        instructions = f"{voice()}\n\n{task}\n\n{NO_DASHES}"
        wire = self._parse(Role.WRITER, "write", instructions, prompt, _WireText)
        if wire is None or not wire.text.strip():
            raise NoAnswer("writer gave no text")
        return undash(wire.text.strip())

    def read_image(self, image: bytes, mime: str) -> str:
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        content = [{"type": "input_text", "text": READ_IMAGE_TASK},
                   {"type": "input_image", "image_url": url}]  # fmt: skip
        wire = self._parse(
            Role.VISION, "read_image", READ_IMAGE_TASK, [{"role": "user", "content": content}],
            _WireText,
        )  # fmt: skip
        if wire is None or not wire.text.strip():
            raise NoAnswer("no text read from the image")
        return wire.text.strip()

    def read_holdings(self, image: bytes, mime: str, lang: str) -> WireHoldings | None:
        """The holdings table in the image, or None when the model gave no parsed answer. The
        image goes only into the request; the call log records tokens, never the input."""
        url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        hint = f"The app's language may be {lang}; write names exactly as printed."
        content = [{"type": "input_text", "text": hint},
                   {"type": "input_image", "image_url": url}]  # fmt: skip
        return self._parse(
            Role.VISION, "read_holdings", READ_HOLDINGS_TASK,
            [{"role": "user", "content": content}], WireHoldings,
        )  # fmt: skip

    def pick(self, question: str, choices: Mapping[str, str], text: str) -> str | None:
        listed = "\n".join(f"- {name}: {meaning}" for name, meaning in choices.items())
        instructions = f"{question}\nAnswer with exactly one choice name.\n{listed}"
        wire = self._parse(Role.CHEAP, "pick", instructions, text, _WirePick)
        return wire.choice if wire and wire.choice in choices else None

    def same_claim(self, claim: str, articles: Sequence[ArticleBrief]) -> set[str]:
        """The ids of the articles that report `claim`. Unknown ids are dropped."""
        listed = [{"id": a.id, "publisher": a.publisher, "title": a.title,
                   "snippet": a.snippet[:SNIPPET_CHARS]} for a in articles]  # fmt: skip
        prompt = json.dumps({"claim": claim, "articles": listed}, ensure_ascii=False)
        wire = self._parse(Role.CHEAP, "same_claim", SAME_CLAIM_INSTRUCTIONS, prompt, _WireIds)
        return {i for i in wire.ids if i in {a.id for a in articles}} if wire else set()
