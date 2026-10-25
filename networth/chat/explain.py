"""Explain this: a forwarded text, a link or a screenshot, in plain words, from its own text.

    answer = explain_text(text)
    answer = explain_link(url)
    answer = explain_image(image, services)

The text the user sent (a page's visible text, or the image transcription) is the guard's
source, so every number in the explanation must be on the page. The writer gets the glossary
through voice(). A link is fetched only from a public address, redirects included, because the
server fetches whatever URL a user sends. An unsubscribe, opt-out, tracking or redirect link is
never fetched, at any hop: a GET on one acts for the user (live, a Mailtrack opt-out link in an
email footer unsubscribed the sender).

    url = user_link(text)   # the first link in the text that is safe to fetch, or None
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
URL: Final = re.compile(r"https?://[^\s<>\"'()\[\]]+")
# ponytail: a word and host list, not a classifier. Add a host when a new mail tracker shows up.
SKIP_HOSTS: Final = (
    "mailtrack", "mailsuite", "list-manage", "mailchimp", "sendgrid", "mandrillapp",
    "doubleclick", "hubspotlinks", "mlsend", "mailgun",
)  # fmt: skip
SKIP_WORDS: Final = frozenset({
    "unsubscribe", "unsub", "optout", "opt", "resubscribe", "subscription", "preferences",
    "track", "tracking", "trk", "pixel", "redirect", "click", "clicks",
})  # fmt: skip
TAGS: Final = re.compile(r"<(script|style|noscript)\b.*?</\1>|<[^>]+>", re.IGNORECASE | re.DOTALL)
SPACE: Final = re.compile(r"\s+")


class Blocked(Exception):
    """The link is not a public http(s) address, or not one to fetch (see fetchable)."""


def fetchable(url: str) -> bool:
    """False for a link whose GET may act for the user or only bounces elsewhere: a known mail
    tracker, a path or query word like unsubscribe or click, or a URL inside the query."""
    parts = urlsplit(url)
    host, query = (parts.hostname or "").lower(), parts.query.lower()
    words = set(re.split(r"[^a-z0-9]+", f"{host} {parts.path.lower()} {query}"))
    return not (any(h in host for h in SKIP_HOSTS) or words & SKIP_WORDS or "http" in query)


def user_link(text: str) -> str | None:
    return next((url for url in URL.findall(text) if fetchable(url)), None)


# ponytail: resolves, then httpx resolves again, so DNS rebinding between the two is not
# covered. Pin the checked address in the transport if this ever fetches for untrusted users at
# scale.
def _public(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or not fetchable(url):
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


def explain_message(text: str) -> Answer:
    """The one link in the text that is safe to fetch, or else the text itself."""
    url = user_link(text)
    return explain_link(url) if url else explain_text(text)


def explain_image(image: bytes, services: Services) -> Answer:
    if services.models is None:
        return Answer(CANT_READ, CANT_READ)
    try:
        text = services.models.read_image(image, IMAGE_MIME)
    except (net.CallFailed, NoAnswer):
        return Answer(CANT_READ, CANT_READ)
    return explain_text(text)
