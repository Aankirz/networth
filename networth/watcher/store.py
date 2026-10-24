"""The watcher's data model and data/watcher.sqlite, the only module that knows its schema.

    store = Store.open(DATA_DIR / "watcher.sqlite")

Tables:
    articles  (url key, normalized)        one row per article ever pulled; INSERT OR IGNORE
    stories   (id = hash of first url)     the model's grouping, plus the judge's answer once
    decisions (story_id key)               the latest verdict per story, rewritten every cycle
    insights  (type + event date + asset + trigger)  engine numbers only, the exact odds() dict;
              one event reported as several stories writes one set, under the first story
    cycles                                 one row per run, for the report

Every write step runs in one transaction. Every write is keyed, so a step repeated on the same
inputs converges to the same rows.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
import urllib.parse
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from networth.engine.model import EventType, Region
from networth.llm import Classification, Classified, NotAnEvent

UTM_PREFIX: Final = "utm_"
NONE_TYPE: Final = "none"
STORY_ID_CHARS: Final = 12
# Second-level labels under which a registrable name has three labels (bbc.co.uk, rbi.org.in).
SECOND_LEVEL: Final = frozenset({"co", "com", "org", "net", "gov", "ac", "edu", "nic", "res"})

SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS articles (
  url TEXT PRIMARY KEY, publisher TEXT NOT NULL, origin TEXT NOT NULL, title TEXT NOT NULL,
  summary TEXT NOT NULL, published_at TEXT NOT NULL, query TEXT NOT NULL,
  pulled_at TEXT NOT NULL, story_id TEXT);
CREATE TABLE IF NOT EXISTS stories (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, first_seen TEXT NOT NULL,
  type TEXT, cause TEXT, classify_reason TEXT, classified_at TEXT, event_date TEXT,
  region TEXT);
CREATE TABLE IF NOT EXISTS decisions (
  story_id TEXT PRIMARY KEY, verdict TEXT NOT NULL CHECK (verdict IN ('confirmed', 'rejected')),
  reason TEXT NOT NULL, publishers TEXT NOT NULL, primary_source TEXT, decided_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS insights (
  id TEXT PRIMARY KEY, story_id TEXT NOT NULL,
  trigger TEXT NOT NULL CHECK (trigger IN ('news', 'price')), asset TEXT NOT NULL,
  type TEXT NOT NULL, cause TEXT NOT NULL, odds_json TEXT NOT NULL, created_at TEXT NOT NULL,
  event_date TEXT);
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
  counts TEXT NOT NULL, cost_usd REAL NOT NULL, errors TEXT NOT NULL);
"""

# A file from before the judge answered with a date and a region. Its answers lack both, and
# its "old news" verdicts were tied to the hour they were asked, so every story is judged once
# more. Insights are rebuilt from the answers every cycle. One transaction: all or nothing.
MIGRATE_REGION: Final = """
BEGIN;
ALTER TABLE stories ADD COLUMN event_date TEXT;
ALTER TABLE stories ADD COLUMN region TEXT;
UPDATE stories SET type = NULL, cause = NULL, classify_reason = NULL, classified_at = NULL;
DELETE FROM insights;
COMMIT;
"""
# Insights keyed by story, from before they were keyed by event. Rebuilt next cycle.
MIGRATE_EVENT_INSIGHTS: Final = """
BEGIN;
ALTER TABLE insights ADD COLUMN event_date TEXT;
DELETE FROM insights;
COMMIT;
"""


def normalize_url(url: str) -> str:
    """Lowercase scheme and host, no fragment, no utm_ parameters."""
    parts = urllib.parse.urlsplit(url.strip())
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith(UTM_PREFIX)]  # fmt: skip
    return urllib.parse.urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path,
         urllib.parse.urlencode(query), "")
    )  # fmt: skip


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def registrable(host: str) -> str:
    """The name a publisher registered: m.viralnews.xyz -> viralnews.xyz, x.rbi.org.in ->
    rbi.org.in. A heuristic, not the public suffix list."""
    labels = host.removeprefix("www.").split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in SECOND_LEVEL and len(labels[-1]) == 2 else 2
    return ".".join(labels[-keep:])


def story_id_for(first_url: str) -> str:
    return "s_" + hashlib.sha256(first_url.encode()).hexdigest()[:STORY_ID_CHARS]


@dataclass(frozen=True)
class Article:
    url: str  # normalized
    publisher: str
    origin: str  # the wire agency whose copy this is, else the publisher
    title: str
    summary: str
    published_at: dt.datetime
    query: str
    pulled_at: dt.datetime
    story_id: str | None = None


@dataclass(frozen=True)
class Story:
    id: str
    title: str
    first_seen: dt.datetime
    classification: Classification | None  # None until the judge has answered
    classified_at: dt.datetime | None


@dataclass(frozen=True)
class NewStory:
    id: str
    title: str
    first_seen: dt.datetime


@dataclass(frozen=True)
class Confirmed:
    publishers: tuple[str, ...]
    primary_source: str | None  # the primary domain that confirmed it, if any


@dataclass(frozen=True)
class Rejected:
    reason: str
    publishers: tuple[str, ...]


Verdict = Confirmed | Rejected
Trigger = Literal["news", "price"]


@dataclass(frozen=True)
class Insight:
    story_id: str  # the first story that reported the event
    trigger: Trigger
    asset: str
    type: str
    cause: str
    event_date: dt.date
    odds: Mapping[str, object]  # the exact odds() dict

    @property
    def id(self) -> str:
        return f"{self.type}:{self.event_date}:{self.asset}:{self.trigger}"


@dataclass(frozen=True)
class Decision:
    story: Story
    verdict: Verdict
    decided_at: dt.datetime


@dataclass(frozen=True)
class Cycle:
    started_at: dt.datetime
    finished_at: dt.datetime
    counts: Mapping[str, int]
    cost_usd: float
    errors: tuple[str, ...]


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).isoformat(timespec="seconds")


def _time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


def _article(r: sqlite3.Row) -> Article:
    return Article(r["url"], r["publisher"], r["origin"], r["title"], r["summary"],
                   _time(r["published_at"]), r["query"], _time(r["pulled_at"]),
                   r["story_id"])  # fmt: skip


def _classification(r: sqlite3.Row) -> Classification | None:
    if r["classified_at"] is None:
        return None
    if r["type"] == NONE_TYPE:
        return NotAnEvent(r["classify_reason"], Region(r["region"]) if r["region"] else None)
    return Classified(EventType(r["type"]), r["cause"], dt.date.fromisoformat(r["event_date"]),
                      Region(r["region"]), r["classify_reason"])  # fmt: skip


def _story(r: sqlite3.Row) -> Story:
    at = r["classified_at"]
    return Story(r["id"], r["title"], _time(r["first_seen"]), _classification(r),
                 _time(at) if at else None)  # fmt: skip


def _verdict(r: sqlite3.Row) -> Verdict:
    publishers = tuple(json.loads(r["publishers"]))
    if r["verdict"] == "confirmed":
        return Confirmed(publishers, r["primary_source"])
    return Rejected(r["reason"], publishers)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


class Store:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    @classmethod
    def open(cls, path: Path) -> Store:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        if "region" not in _columns(conn, "stories"):
            conn.executescript(MIGRATE_REGION)
        if "event_date" not in _columns(conn, "insights"):
            conn.executescript(MIGRATE_EVENT_INSIGHTS)
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def add_articles(self, articles: Iterable[Article]) -> int:
        """Insert new articles; known urls are left as they are. Returns how many were new."""
        with self._conn:
            cur = self._conn.executemany(
                "INSERT OR IGNORE INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                [(a.url, a.publisher, a.origin, a.title, a.summary, _iso(a.published_at),
                  a.query, _iso(a.pulled_at)) for a in articles],
            )  # fmt: skip
            return cur.rowcount

    def counts(self) -> dict[str, int]:
        one = self._conn.execute
        return {
            "articles_total": one("SELECT count(*) FROM articles").fetchone()[0],
            "stories_total": one("SELECT count(*) FROM stories").fetchone()[0],
        }

    def unassigned_articles(self) -> list[Article]:
        rows = self._conn.execute(
            "SELECT * FROM articles WHERE story_id IS NULL ORDER BY published_at, url"
        )
        return [_article(r) for r in rows]

    def stories(self) -> list[Story]:
        return [
            _story(r) for r in self._conn.execute("SELECT * FROM stories ORDER BY first_seen, id")
        ]

    def stories_pulled_since(self, since: dt.datetime) -> list[Story]:
        """Stories with an article pulled since then. first_seen is a publish date, which
        search reports late or stale, so it cannot say which stories are still open."""
        rows = self._conn.execute(
            "SELECT * FROM stories WHERE id IN "
            "(SELECT story_id FROM articles WHERE pulled_at >= ?) ORDER BY first_seen, id",
            (_iso(since),),
        )
        return [_story(r) for r in rows]

    def assign(self, new_stories: Sequence[NewStory], urls_by_story: Mapping[str, list[str]]):
        """Create the new stories and attach articles that have no story yet."""
        with self._conn:
            self._conn.executemany(
                "INSERT OR IGNORE INTO stories (id, title, first_seen) VALUES (?, ?, ?)",
                [(s.id, s.title, _iso(s.first_seen)) for s in new_stories],
            )
            self._conn.executemany(
                "UPDATE articles SET story_id = ? WHERE url = ? AND story_id IS NULL",
                [(sid, url) for sid, urls in urls_by_story.items() for url in urls],
            )

    def articles_by_story(self) -> dict[str, list[Article]]:
        out: dict[str, list[Article]] = defaultdict(list)
        rows = self._conn.execute(
            "SELECT * FROM articles WHERE story_id IS NOT NULL ORDER BY published_at, url"
        )
        for r in rows:
            out[r["story_id"]].append(_article(r))
        return dict(out)

    def put_decisions(self, verdicts: Mapping[str, Verdict], now: dt.datetime) -> None:
        def row(story_id: str, v: Verdict) -> tuple:
            if isinstance(v, Confirmed):
                return (story_id, "confirmed", "", json.dumps(v.publishers), v.primary_source)
            return (story_id, "rejected", v.reason, json.dumps(v.publishers), None)

        with self._conn:
            self._conn.executemany(
                "INSERT OR REPLACE INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
                [(*row(sid, v), _iso(now)) for sid, v in verdicts.items()],
            )

    def decisions(self, since: dt.datetime | None = None) -> list[Decision]:
        rows = self._conn.execute(
            "SELECT s.*, d.verdict, d.reason, d.publishers, d.primary_source, d.decided_at "
            "FROM decisions d JOIN stories s ON s.id = d.story_id "
            "WHERE d.decided_at >= ? ORDER BY s.first_seen, s.id",
            (_iso(since) if since else "",),
        )
        return [Decision(_story(r), _verdict(r), _time(r["decided_at"])) for r in rows]

    def set_classification(self, story_id: str, c: Classification, now: dt.datetime) -> None:
        if isinstance(c, Classified):
            type_, cause, event_date = c.type.value, c.cause, c.event_date.isoformat()
        else:
            type_, cause, event_date = NONE_TYPE, "", None
        region = c.region.value if c.region else None
        with self._conn:
            self._conn.execute(
                "UPDATE stories SET type = ?, cause = ?, classify_reason = ?, classified_at = ?, "
                "event_date = ?, region = ? WHERE id = ? AND classified_at IS NULL",
                (type_, cause, c.reason, _iso(now), event_date, region, story_id),
            )

    def put_insights(self, insights: Iterable[Insight], now: dt.datetime) -> None:
        """Upsert by id. created_at stays the first time the insight was written."""
        with self._conn:
            self._conn.executemany(
                "INSERT INTO insights (id, story_id, trigger, asset, type, cause, odds_json, "
                "created_at, event_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) "
                "DO UPDATE SET cause = excluded.cause, odds_json = excluded.odds_json",
                [(i.id, i.story_id, i.trigger, i.asset, i.type, i.cause, json.dumps(i.odds),
                  _iso(now), i.event_date.isoformat()) for i in insights],
            )  # fmt: skip

    def insights(self, since: dt.datetime | None = None) -> list[Insight]:
        rows = self._conn.execute(
            "SELECT i.* FROM insights i JOIN stories s ON s.id = i.story_id "
            "JOIN decisions d ON d.story_id = i.story_id "
            "WHERE d.decided_at >= ? ORDER BY s.first_seen, i.id",
            (_iso(since) if since else "",),
        )
        return [Insight(r["story_id"], r["trigger"], r["asset"], r["type"], r["cause"],
                        dt.date.fromisoformat(r["event_date"]), json.loads(r["odds_json"]))
                for r in rows]  # fmt: skip

    def add_cycle(self, cycle: Cycle) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO cycles (started_at, finished_at, counts, cost_usd, errors) "
                "VALUES (?, ?, ?, ?, ?)",
                (_iso(cycle.started_at), _iso(cycle.finished_at), json.dumps(dict(cycle.counts)),
                 cycle.cost_usd, json.dumps(list(cycle.errors))),
            )  # fmt: skip

    def latest_cycle(self) -> Cycle | None:
        r = self._conn.execute("SELECT * FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
        if r is None:
            return None
        return Cycle(_time(r["started_at"]), _time(r["finished_at"]), json.loads(r["counts"]),
                     r["cost_usd"], tuple(json.loads(r["errors"])))  # fmt: skip
