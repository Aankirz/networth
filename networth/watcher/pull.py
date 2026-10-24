"""Pull the last lookback_hours of news from Exa, one search per configured query.

Each Exa result is parsed here, at the boundary, into a store.Article: normalized url, the
publisher (an alias or the registrable host) and the origin (the wire agency whose copy it is,
else the publisher). Results without a url or a parseable date are skipped and counted. A
failed query is recorded and the rest still run.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import httpx2

from networth import net
from networth.config import Config, ConfirmConfig, Query
from networth.watcher.store import Article, Store, host_of, normalize_url, registrable

EXA_URL: Final = "https://api.exa.ai/search"
TEXT_CHARS: Final = 1000
BYLINE_CHARS: Final = 300

RawResult = Mapping[str, object]


class NewsSearch(Protocol):
    def search(self, query: Query, since: dt.datetime) -> list[RawResult]: ...


class ExaSearch:
    """Exa /search over an IPv4-only client, under the configured deadline, logged with its
    reported cost as role "exa"."""

    def __init__(self, cfg: Config, log_path: Path, client: httpx2.Client | None = None) -> None:
        self._cfg = cfg
        self._log_path = log_path
        self._client = client or net.ipv4_client(
            cfg.http.exa_deadline_s, cfg.http.connect_timeout_s
        )

    def _body(self, query: Query, since: dt.datetime) -> dict[str, object]:
        body: dict[str, object] = {
            "query": query.text,
            "numResults": self._cfg.pull.results_per_query,
            "startPublishedDate": since.astimezone(dt.UTC).isoformat(timespec="seconds"),
            "contents": {"text": {"maxCharacters": TEXT_CHARS}},
        }
        if query.category:
            body["category"] = query.category
        if query.include_domains:
            body["includeDomains"] = list(query.include_domains)
        return body

    def search(self, query: Query, since: dt.datetime) -> list[RawResult]:
        def request() -> tuple[list[RawResult], net.Usage]:
            resp = self._client.post(
                EXA_URL,
                json=self._body(query, since),
                headers={"x-api-key": self._cfg.secrets.exa_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") if isinstance(data, dict) else None
            if not isinstance(results, list):
                raise ValueError("Exa answer has no results list")
            cost = data.get("costDollars", {}).get("total", 0.0)
            usd = float(cost) if isinstance(cost, int | float) else 0.0
            return [r for r in results if isinstance(r, dict)], net.Usage(cost_usd=usd)

        return net.metered(
            request,
            call=f"exa_search: {query.text[:60]}",
            role="exa",
            model="exa",
            deadline_s=self._cfg.http.exa_deadline_s,
            log_path=self._log_path,
        )


def publisher_of(host: str, aliases: Mapping[str, str]) -> str:
    name = registrable(host)
    return aliases.get(name, name)


def origin_of(publisher: str, byline: str, wires: Mapping[str, Sequence[str]]) -> str:
    """The wire agency whose marker appears in the byline text, else the publisher."""
    for agency, markers in wires.items():
        if any(re.search(rf"(?<!\w){re.escape(m)}(?!\w)", byline) for m in markers):
            return agency
    return publisher


def _published(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _text(raw: RawResult, key: str) -> str:
    value = raw.get(key)
    return value.strip() if isinstance(value, str) else ""


def parse_result(
    raw: RawResult, query: Query, pulled_at: dt.datetime, cfg: ConfirmConfig
) -> Article | None:
    url, published = _text(raw, "url"), _published(raw.get("publishedDate"))
    if not url or published is None:
        return None
    url = normalize_url(url)
    title, text = _text(raw, "title"), _text(raw, "text") or _text(raw, "summary")
    publisher = publisher_of(host_of(url), cfg.publisher_aliases)
    byline = " ".join((title, _text(raw, "author"), text[:BYLINE_CHARS]))
    return Article(
        url=url,
        publisher=publisher,
        origin=origin_of(publisher, byline, cfg.wire_agencies),
        title=title or url,
        summary=text,
        published_at=published.astimezone(dt.UTC),
        query=query.text,
        pulled_at=pulled_at,
    )


@dataclass(frozen=True)
class PullResult:
    queries_run: int
    results: int
    new_articles: int
    skipped: int
    errors: tuple[str, ...]


def pull(cfg: Config, search: NewsSearch, store: Store, now: dt.datetime) -> PullResult:
    since = now - dt.timedelta(hours=cfg.pull.lookback_hours)
    articles: dict[str, Article] = {}
    results = skipped = 0
    errors: list[str] = []
    for query in cfg.pull.queries:
        try:
            raws = search.search(query, since)
        except net.CallFailed as exc:
            errors.append(str(exc))
            continue
        results += len(raws)
        for raw in raws:
            article = parse_result(raw, query, now, cfg.confirm)
            if article is None:
                skipped += 1
                continue
            articles.setdefault(article.url, article)
    new = store.add_articles(articles.values())
    return PullResult(len(cfg.pull.queries), results, new, skipped, tuple(errors))
