"""Outbound HTTP for paid APIs: IPv4 only, a wall-clock deadline, one log line per call.

This network resolves IPv6 for most hosts and then never completes the handshake, so every
client binds an IPv4 local address. Socket timeouts alone do not bound a call that keeps
trickling bytes or retries inside a library, so each call also runs under a thread deadline,
like engine/check_events.with_deadline.

Every call through `metered` appends one JSON line to the call log (data/llm_calls.jsonl):
ts, call, role, model, input_tokens, cached_tokens, output_tokens, cost_usd, ok, error.
The report sums cost_usd from that one file.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import httpx2

IPV4_ANY: Final = "0.0.0.0"

log = logging.getLogger("networth.net")


class DeadlineExceeded(TimeoutError):
    def __init__(self, what: str, deadline_s: float) -> None:
        super().__init__(f"{what}: no answer within {deadline_s:g}s")
        self.what = what
        self.deadline_s = deadline_s


class CallFailed(Exception):
    """A metered call failed or timed out. Already logged with ok=false."""

    def __init__(self, call: str, error: str) -> None:
        super().__init__(f"{call} failed: {error}")
        self.call = call
        self.error = error


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class CallRecord:
    ts: str
    call: str
    role: str
    model: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    cost_usd: float
    ok: bool
    error: str


def ipv4_client(timeout_s: float, connect_timeout_s: float) -> httpx2.Client:
    transport = httpx2.HTTPTransport(local_address=IPV4_ANY, retries=0)
    timeout = httpx2.Timeout(timeout_s, connect=connect_timeout_s)
    return httpx2.Client(transport=transport, timeout=timeout)


def call_with_deadline[T](fn: Callable[[], T], deadline_s: float, what: str) -> T:
    """fn() in a daemon thread. Its exception is re-raised here; past the deadline the thread
    is abandoned and DeadlineExceeded is raised."""
    box: list[tuple[bool, object]] = []

    def run() -> None:
        try:
            box.append((True, fn()))
        except BaseException as exc:
            box.append((False, exc))

    worker = threading.Thread(target=run, daemon=True, name=what)
    worker.start()
    worker.join(deadline_s)
    if not box:
        raise DeadlineExceeded(what, deadline_s)
    ok, value = box[0]
    if not ok:
        raise value  # type: ignore[misc]
    return value  # type: ignore[return-value]


def append_record(log_path: Path, record: CallRecord) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")


def read_records(log_path: Path) -> list[CallRecord]:
    """Every whole record. A VM stopped mid-append leaves NUL padding or a torn line; one bad
    line must not take down every reader, so NULs are stripped and a line that still fails to
    parse is skipped and counted in the log."""
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    records, torn = [], 0
    for line in (x.replace("\0", "").strip() for x in lines):
        if not line:
            continue
        try:
            records.append(CallRecord(**json.loads(line)))
        except (ValueError, TypeError):
            torn += 1
    if torn:
        log.warning("%s: skipped %d unreadable line(s)", log_path.name, torn)
    return records


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def metered[T](
    fn: Callable[[], tuple[T, Usage]],
    *,
    call: str,
    role: str,
    model: str,
    deadline_s: float,
    log_path: Path,
) -> T:
    """Run fn under the deadline and log it. Any failure is logged and raised as CallFailed."""
    try:
        result, usage = call_with_deadline(fn, deadline_s, call)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        append_record(log_path, CallRecord(_now(), call, role, model, 0, 0, 0, 0.0, False, error))
        raise CallFailed(call, error) from exc
    append_record(
        log_path,
        CallRecord(_now(), call, role, model, usage.input_tokens, usage.cached_tokens,
                   usage.output_tokens, usage.cost_usd, True, ""),
    )  # fmt: skip
    return result
