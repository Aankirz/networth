"""Keiki's pushed payloads, parsed once at the boundary into frozen types.

    event = parse(json.loads(raw_body))   # KeikiTurn, Other, or None for an unknown shape

Only a `keiki.turn` carries work. An arrival, a cancellation or a reaction is an Other: it is
acknowledged and nothing runs. Messages marked silent are skipped. The first payload of the
process logs its top-level keys (never values), so the first live turn shows what Keiki sends.

https://onkeiki.com/docs/external-harness.md
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

log = logging.getLogger("networth.keiki")

TURN: Final = "keiki.turn"
OTHER_TYPES: Final = frozenset({"keiki.turn.arrival", "keiki.turn.cancelled", "keiki.reaction"})
QUOTE_HEADER: Final = re.compile(r"^(On\b.*\bwrote:|-----\s*Original Message\s*-----)\s*$", re.I)
_first_payload = threading.Event()


@dataclass(frozen=True)
class KeikiTurn:
    turn_id: str
    agent_id: str
    conversation_id: str  # the contact's identity on its channel; for email, the sender
    channel: str
    texts: tuple[str, ...]
    held_back: bool  # playground and steered turns: captured by Keiki, never delivered
    quiet_loop: bool
    turn_url: str
    trace_id: str | None


@dataclass(frozen=True)
class Other:
    type: str
    agent_id: str


def _texts(messages: object) -> tuple[str, ...]:
    rows = messages if isinstance(messages, list) else []
    return tuple(m["text"] for m in rows if isinstance(m, dict) and not m.get("silent")
                 and isinstance(m.get("text"), str))  # fmt: skip


def _log_keys_once(payload: Mapping[str, object]) -> None:
    if not _first_payload.is_set():
        _first_payload.set()
        log.info("first keiki payload keys: %s", sorted(payload))


def parse(payload: object) -> KeikiTurn | Other | None:
    if not isinstance(payload, dict):
        return None
    _log_keys_once(payload)
    kind, agent = payload.get("type"), payload.get("agentId")
    if not isinstance(agent, str):
        return None
    if kind in OTHER_TYPES:
        return Other(kind, agent)
    keiki = payload.get("keiki")
    turn_url = keiki.get("turnUrl") if isinstance(keiki, dict) else None
    ids = (payload.get("turnId"), payload.get("conversationId"), turn_url)
    if kind != TURN or not all(isinstance(v, str) and v for v in ids):
        return None
    trace = payload.get("traceId")
    return KeikiTurn(
        payload["turnId"], agent, payload["conversationId"], str(payload.get("channel") or ""),
        _texts(payload.get("messages")), bool(payload.get("heldBack")),
        bool(payload.get("quietLoop")), turn_url, trace if isinstance(trace, str) else None,
    )  # fmt: skip


def strip_quoted(text: str) -> str:
    """An email reply without the mail it quotes: '>' lines go, and so does everything from an
    'On ... wrote:' or '-----Original Message-----' line on."""
    kept: list[str] = []
    for line in text.splitlines():
        if QUOTE_HEADER.match(line.strip()):
            break
        if not line.lstrip().startswith(">"):
            kept.append(line)
    return "\n".join(kept).strip()
