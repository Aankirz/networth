"""Validate networth/engine/events.csv. Prints a report, exits non-zero on any failure.

Run: uv run python -m networth.engine.check_events [--offline]

Structure comes from backtest.parse_events, the one parser the build also uses, so a row this
check accepts is a row the build accepts. This module adds link liveness and the library
targets from the brief.
"""

from __future__ import annotations

import argparse
import http.client
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Final

from networth.engine.backtest import EVENTS_CSV, RowProblem, parse_events
from networth.engine.model import Event, EventType, Region

MIN_ROWS: Final = 80
MIN_INDIA_ROWS: Final = 20
MIN_PER_TYPE: Final = 5
URL_TIMEOUT_S: Final = 15.0  # per socket operation
CONNECT_TIMEOUT_S: Final = 5.0  # per resolved address, so a dead IPv6 route fails fast
URL_DEADLINE_S: Final = 20.0  # wall clock per URL, across every address and redirect
URL_WORKERS: Final = 8
TRANSPORT_ATTEMPTS: Final = 2
PER_HOST_LIMIT: Final = 2
HOST_LIMITS: Final = {"web.archive.org": 1}  # answers 429 to parallel requests from one client
TOO_MANY_REQUESTS: Final = 429
MAX_BACKOFF_S: Final = 5.0  # keeps one 429 retry inside URL_DEADLINE_S
DEFAULT_BACKOFF_S: Final = 2.0
USER_AGENT: Final = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

UrlStatus = Callable[[str], int | str]  # HTTP status after redirects, or an error string


@dataclass(frozen=True)
class DeadLink:
    event_id: str
    url: str
    result: int | str


@dataclass(frozen=True)
class Report:
    events: tuple[Event, ...]
    problems: tuple[RowProblem, ...]
    dead_links: tuple[DeadLink, ...]
    target_failures: tuple[str, ...]
    links_checked: int | None  # None = offline

    @property
    def ok(self) -> bool:
        return not (self.problems or self.dead_links or self.target_failures)

    def render(self) -> str:
        types = Counter(e.type for e in self.events)
        regions = Counter(e.region for e in self.events)
        lines = [f"{len(self.events)} valid rows", "", "by type:"]
        lines += [f"  {t.value:<18} {types[t]:>4}" for t in EventType]
        lines += ["by region:"] + [f"  {r.value:<18} {regions[r]:>4}" for r in Region]
        lines += [""]
        lines += [f"PROBLEM line {p.line} ({p.event_id}) {p.field}: {p.message}"
                  for p in self.problems]  # fmt: skip
        lines += [f"FAILED LINK {d.event_id}: {d.url} -> {d.result}" for d in self.dead_links]
        lines += [f"TARGET {t}" for t in self.target_failures]
        links = (
            "links not checked (--offline)"
            if self.links_checked is None
            else f"{self.links_checked} distinct URLs checked, "
            f"{len({d.url for d in self.dead_links})} FAILED"
        )
        lines += [links, "OK" if self.ok else "FAILED"]
        return "\n".join(lines)


def _connect_ipv4_first(
    address: tuple[str, int], timeout: float | None = None, source_address=None, **_: object
) -> socket.socket:
    """socket.create_connection, but IPv4 addresses first and a short timeout per address.
    Some networks resolve IPv6 for a host and then never complete the handshake."""
    host, port = address
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    infos.sort(key=lambda info: info[0] != socket.AF_INET)
    last: OSError = OSError(f"no address for {host}")
    for family, type_, proto, _, sockaddr in infos:
        sock = socket.socket(family, type_, proto)
        try:
            sock.settimeout(min(CONNECT_TIMEOUT_S, timeout or CONNECT_TIMEOUT_S))
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            sock.settimeout(timeout)
            return sock
        except OSError as exc:
            sock.close()
            last = exc
    raise last


class _HTTPConnection(http.client.HTTPConnection):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_ipv4_first


class _HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_ipv4_first


class _HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HTTPConnection, req)


class _HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HTTPSConnection, req, context=self._context)


_OPENER: Final = urllib.request.build_opener(_HTTPHandler, _HTTPSHandler)


def http_status(url: str, timeout: float = URL_TIMEOUT_S) -> int | str:
    """GET with a browser User-Agent, following redirects, IPv4 first. Never raises. Some
    sites refuse HEAD, so this reads the first byte of a GET instead. A transport error (DNS,
    refused, reset) or a 429 gets one more attempt, because a resolver blip and archive.org
    rate limiting each failed a live run; a 429 first waits for its Retry-After. Any other
    HTTP status is final. The caller's deadline still bounds every attempt."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    result: int | str = "not attempted"
    for attempt in range(TRANSPORT_ATTEMPTS):
        try:
            with _OPENER.open(req, timeout=timeout) as resp:
                resp.read(1)
                return int(resp.status)
        except urllib.error.HTTPError as exc:
            if exc.code != TOO_MANY_REQUESTS:
                return int(exc.code)
            result = int(exc.code)
            if attempt + 1 < TRANSPORT_ATTEMPTS:
                time.sleep(retry_after_s(exc.headers.get("Retry-After")))
        except Exception as exc:  # every failure is reported as a dead link, never raised
            result = f"{type(exc).__name__}: {exc}"
    return result


def retry_after_s(header: str | None) -> float:
    """Seconds to wait from a Retry-After header (delta-seconds or an HTTP date), clamped to
    [0, MAX_BACKOFF_S]. A missing or unreadable header waits DEFAULT_BACKOFF_S."""
    if not header:
        return DEFAULT_BACKOFF_S
    try:
        wait = float(header)
    except ValueError:
        try:
            when = parsedate_to_datetime(header)
        except (TypeError, ValueError):
            return DEFAULT_BACKOFF_S
        wait = when.timestamp() - time.time()
    return min(max(wait, 0.0), MAX_BACKOFF_S)


def with_deadline(url_status: UrlStatus, url: str, deadline: float) -> int | str:
    """Run url_status(url) in a daemon thread and give up after `deadline` seconds, so a stuck
    connection can neither pass nor hold up the pool or interpreter exit."""
    box: list[int | str] = []

    def run() -> None:
        try:
            box.append(url_status(url))
        except Exception as exc:
            box.append(f"{type(exc).__name__}: {exc}")

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(deadline)
    return box[0] if box else f"timeout after {deadline:g}s (stuck connecting)"


def check_targets(events: Sequence[Event]) -> list[str]:
    failures = []
    if len(events) < MIN_ROWS:
        failures.append(f"{len(events)} rows, need {MIN_ROWS}")
    india = sum(e.region is Region.IN for e in events)
    if india < MIN_INDIA_ROWS:
        failures.append(f"{india} region-in rows, need {MIN_INDIA_ROWS}")
    types = Counter(e.type for e in events)
    failures += [f"{t.value} has {types[t]} rows, need {MIN_PER_TYPE}"
                 for t in EventType if types[t] < MIN_PER_TYPE]  # fmt: skip
    return failures


def _alive(result: int | str) -> bool:
    return isinstance(result, int) and 200 <= result < 400


def check_links(
    events: Sequence[Event],
    url_status: UrlStatus = http_status,
    workers: int = URL_WORKERS,
    deadline: float = URL_DEADLINE_S,
) -> tuple[list[DeadLink], int]:
    """Each distinct URL fetched once, at most `workers` at a time and at most the host's
    limit per host, each within `deadline` seconds once it starts. Dead = not 2xx/3xx, an
    error, or past the deadline."""
    urls = interleave_by_host(sorted({u for e in events for u in e.sources}))
    slots = {host: threading.BoundedSemaphore(HOST_LIMITS.get(host, PER_HOST_LIMIT))
             for host in {host_of(u) for u in urls}}  # fmt: skip

    def fetch(url: str) -> int | str:
        with slots[host_of(url)]:
            return with_deadline(url_status, url, deadline)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = dict(zip(urls, pool.map(fetch, urls), strict=True))
    dead = [DeadLink(e.id, u, results[u]) for e in events for u in e.sources
            if not _alive(results[u])]  # fmt: skip
    return dead, len(urls)


def host_of(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def interleave_by_host(urls: Sequence[str]) -> list[str]:
    """Round-robin across hosts, so workers waiting on one busy host's limit don't idle the
    pool while other hosts have work."""
    by_host: dict[str, list[str]] = defaultdict(list)
    for url in urls:
        by_host[host_of(url)].append(url)
    queues = sorted(by_host.values(), key=len, reverse=True)
    return [q[i] for i in range(len(queues[0]) if queues else 0) for q in queues if i < len(q)]


def check(path: Path = EVENTS_CSV, *, url_status: UrlStatus | None = http_status) -> Report:
    """url_status None skips the network. Tests pass a fake."""
    events, problems = parse_events(path)
    dead, checked = check_links(events, url_status) if url_status else ([], None)
    return Report(tuple(events), tuple(problems), tuple(dead), tuple(check_targets(events)),
                  checked)  # fmt: skip


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip the link check")
    parser.add_argument("--csv", type=Path, default=EVENTS_CSV)
    args = parser.parse_args(argv)
    report = check(args.csv, url_status=None if args.offline else http_status)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
