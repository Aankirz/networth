"""Explain this: a forwarded text, a link or a screenshot, in plain words, from its own text.

    answer = explain_text(text)
    answer = explain_link(url)
    answer = explain_image(image, services)

The text the user sent (a page's visible text, or the image transcription) is the guard's
source, so every number in the explanation must be on the page. The writer gets the glossary
through voice(). A link is fetched only from a public address, redirects included, because the
server fetches whatever URL a user sends.
"""

from __future__ import annotations

import html
import ipaddress
import re
import socket
from typing import Final
from urllib.parse import urljoin, urlsplit

import httpx2

from networth import net
from networth.app.services import Services
from networth.chat.answer import Answer
from networth.llm import NoAnswer

SOURCE_CHARS: Final = 8000
MAX_REDIRECTS: Final = 3
FETCH_DEADLINE_S: Final = 8.0
CONNECT_TIMEOUT_S: Final = 3.0
MAX_PAGE_BYTES: Final = 2_000_000
IMAGE_MIME: Final = "image/jpeg"  # Telegram re-encodes every photo as JPEG
EXPLAIN_TASK: Final = """Explain the text below to a first-time investor, in a short chat
message under 180 words. Say what it is, then the few numbers that matter and what each one
means in plain words (use the glossary), then any risk or condition the text itself states.
Give no opinion on whether it is good, and say nothing about what the reader should do."""
NOT_EXPLAINED: Final = (
    "I couldn't write a plain-words version I could check against what you sent, so I'm not "
    "sending one. Try again in a few minutes."
)
CANT_FETCH: Final = (
    "I couldn't open that link. Paste the text, or send a screenshot, and I'll explain it."
)
CANT_READ: Final = (
    "I couldn't read the text in that image. Send a clearer screenshot, or paste the text."
)
TAGS: Final = re.compile(r"<(script|style|noscript)\b.*?</\1>|<[^>]+>", re.IGNORECASE | re.DOTALL)
SPACE: Final = re.compile(r"\s+")


class Blocked(Exception):
    """The link is not a public http(s) address."""


# ponytail: resolves, then httpx resolves again, so DNS rebinding between the two is not
# covered. Pin the checked address in the transport if this ever fetches for untrusted users at
# scale.
def _public(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise Blocked(url)
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise Blocked(url) from exc
    if not all(ipaddress.ip_address(info[4][0]).is_global for info in infos):
        raise Blocked(url)


def _capped(response: httpx2.Response) -> bytes:
    """At most MAX_PAGE_BYTES of the body; the rest is never downloaded."""
    chunks, size = [], 0
    for chunk in response.iter_bytes():
        chunks.append(chunk)
        size += len(chunk)
        if size >= MAX_PAGE_BYTES:
            break
    return b"".join(chunks)[:MAX_PAGE_BYTES]


def page_text(url: str, client: httpx2.Client | None = None) -> str:
    """The visible text of a public page. Raises Blocked or httpx2.HTTPError."""
    http = client or net.ipv4_client(FETCH_DEADLINE_S, CONNECT_TIMEOUT_S)
    for _ in range(MAX_REDIRECTS + 1):
        _public(url)
        with http.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            raw = _capped(response)
            body = raw.decode(response.encoding or "utf-8", "replace")
        return SPACE.sub(" ", html.unescape(TAGS.sub(" ", body))).strip()
    raise Blocked(url)


def explain_text(text: str) -> Answer:
    return Answer(NOT_EXPLAINED, text[:SOURCE_CHARS], EXPLAIN_TASK, kind="explain", draft=False)


def explain_link(url: str) -> Answer:
    try:
        text = page_text(url)
    except (Blocked, httpx2.HTTPError, UnicodeError):
        return Answer(CANT_FETCH, CANT_FETCH)
    if not text:
        return Answer(CANT_FETCH, CANT_FETCH)
    return explain_text(text)


def explain_image(image: bytes, services: Services) -> Answer:
    if services.models is None:
        return Answer(CANT_READ, CANT_READ)
    try:
        text = services.models.read_image(image, IMAGE_MIME)
    except (net.CallFailed, NoAnswer):
        return Answer(CANT_READ, CANT_READ)
    return explain_text(text)
