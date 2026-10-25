"""One outgoing message as data: a title, short body blocks, an expandable detail and a
footer, empty since the owner dropped every disclaimer (2026-10-25).

    m = Message(title="Morning.", body=("This month's news: RBI rate hike on Oct 20.",))
    plain(m)                     # the one plain-text render: Keiki email, logs, the guard
    from_stored(to_json(m))      # a sent brief, stored and read back

Pure, no IO. Telegram's HTML render lives in networth.bot.telegram, the only module that knows
the wire format and the only place that escapes. Nothing here escapes anything.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Link:
    label: str
    url: str


Block = str | Link


@dataclass(frozen=True)
class Message:
    title: str = ""  # one warm first line, rendered bold
    body: tuple[Block, ...] = ()  # short paragraphs, a blank line between them
    detail: tuple[str, ...] = ()  # lines inside one expandable blockquote
    footer: str = ""  # one quiet line, rendered italic
    preview: str | None = None  # the one URL whose link preview stays on


LANGS: Final = ("en", "hi", "hinglish")
# ponytail: blank, not deleted, while networth/bot/holdings.py (Phase 12) still imports it.
# Owner order 2026-10-25: no footer or disclaimer in any language. Delete with its last user.
FOOTER: Final = {"en": "", "hi": "", "hinglish": ""}
DISCLAIMER: Final = re.compile(
    r"[^.!?\n]*(?:not (?:financial |investment )?advice|your call|won'?t say yes or no|"
    r"whether to put money|रिसर्च, सलाह नहीं|advice nahin?)[^.!?\n]*[.!?।]?",
    re.I,
)


def say(table: Mapping[str, str], lang: str | None) -> str:
    """The table's line in the reader's language, else its English line."""
    return table.get(lang or "en") or table["en"]


def block_text(block: Block) -> str:
    return block if isinstance(block, str) else f"{block.label}: {block.url}"


def plain(m: Message) -> str:
    parts = [m.title, *(block_text(b) for b in m.body), "\n".join(m.detail), m.footer]
    return "\n\n".join(p for p in parts if p)


def to_json(m: Message) -> str:
    body = [b if isinstance(b, str) else {"label": b.label, "url": b.url} for b in m.body]
    return json.dumps({"title": m.title, "body": body, "detail": list(m.detail),
                       "footer": m.footer, "preview": m.preview}, ensure_ascii=False)  # fmt: skip


def from_stored(text: str) -> Message:
    """A stored message; a row written before messages were data is plain text."""
    try:
        raw = json.loads(text)
    except ValueError:
        return Message(body=(text,))
    if not isinstance(raw, dict) or "body" not in raw:
        return Message(body=(text,))
    body = tuple(b if isinstance(b, str) else Link(b["label"], b["url"]) for b in raw["body"])
    return Message(raw.get("title", ""), body, tuple(raw.get("detail", ())),
                   raw.get("footer", ""), raw.get("preview"))  # fmt: skip
