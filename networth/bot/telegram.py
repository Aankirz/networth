"""The Telegram Bot API, the only module that knows its wire format.

    bot = TelegramClient(token)
    bot.send_message(chat_id, Message(body=("Hi",)), ((Button("Yes", "ob:confirm:ok"),),))

Messages go out as HTML (parse_mode "HTML"), rendered here by html() and nowhere else: this is
the one place any text is escaped, so call sites never escape. Telegram rejects bad markup
with a 400 "can't parse entities"; the same message is then resent once as plain text with no
parse_mode, and a warning names the method and Telegram's description, never the text. Link
previews are off unless the message names its one preview link.

Every call goes over IPv4 under a wall-clock deadline, because this network resolves IPv6 and
then hangs. A 429 is retried once after its retry_after.
The token sits in every request URL, so no error, log line or exception here ever carries
the URL: httpx2's own request log is silenced and transport errors are re-raised by name only.
"""

from __future__ import annotations

import html as markup_escape
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol

import httpx2

from networth.bot.message import Link, Message, plain
from networth.net import call_with_deadline, ipv4_client

API_BASE: Final = "https://api.telegram.org"
HTTP_TIMEOUT_S: Final = 10.0
CONNECT_TIMEOUT_S: Final = 5.0
DEADLINE_SLACK_S: Final = 5.0
LONG_POLL_SLACK_S: Final = 10.0
MAX_RETRY_AFTER_S: Final = 30.0
TOO_MANY_REQUESTS: Final = 429
ALLOWED_UPDATES: Final = ["message", "callback_query"]
PARSE_ERROR: Final = "Bad Request: can't parse entities"

log = logging.getLogger("networth.bot")
logging.getLogger("httpx2").setLevel(logging.WARNING)


@dataclass(frozen=True)
class Button:
    label: str
    data: str  # callback data, at most 64 bytes; ignored when url is set
    url: str | None = None  # a link button that opens this page instead of calling back


Keyboard = tuple[tuple[Button, ...], ...]
HTTP_OK: Final = 200


class TelegramError(Exception):
    """A Bot API call failed. The message names the method, never the token or URL."""

    def __init__(self, method: str, description: str) -> None:
        super().__init__(f"telegram {method}: {description}")
        self.method = method
        self.description = description


class Bot(Protocol):
    def send_message(self, chat_id: int, message: Message, buttons: Keyboard = ()) -> dict: ...

    def answer_callback(self, callback_id: str, text: str | None = None) -> None: ...

    def edit_buttons(self, chat_id: int, message_id: int, buttons: Keyboard) -> None: ...

    def set_webhook(self, url: str, secret_token: str) -> None: ...

    def delete_webhook(self) -> None: ...

    def get_updates(self, offset: int | None, timeout_s: int) -> list[dict]: ...

    def download_file(self, file_id: str) -> bytes: ...


def _button(b: Button) -> dict:
    return {"text": b.label, "url": b.url} if b.url else {"text": b.label, "callback_data": b.data}


def markup(buttons: Keyboard) -> dict:
    return {"inline_keyboard": [[_button(b) for b in row] for row in buttons]}


def _text(s: str) -> str:
    return markup_escape.escape(s, quote=False)


def _block(block: str | Link) -> str:
    if isinstance(block, str):
        return _text(block)
    return f'<a href="{markup_escape.escape(block.url, quote=True)}">{_text(block.label)}</a>'


def html(m: Message) -> str:
    """The message as Telegram HTML: a bold title, the body, one expandable blockquote of
    detail, an italic footer. Every piece of text is escaped here."""
    detail = "\n".join(m.detail)
    parts = [
        f"<b>{_text(m.title)}</b>" if m.title else "",
        *(_block(b) for b in m.body),
        f"<blockquote expandable>{_text(detail)}</blockquote>" if detail else "",
        f"<i>{_text(m.footer)}</i>" if m.footer else "",
    ]
    return "\n\n".join(p for p in parts if p)


def preview_options(m: Message) -> dict:
    return {"url": m.preview} if m.preview else {"is_disabled": True}


class TelegramClient:
    def __init__(
        self,
        token: str,
        *,
        client: httpx2.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._token = token
        self._client = client or ipv4_client(HTTP_TIMEOUT_S, CONNECT_TIMEOUT_S)
        self._sleep = sleep

    def __repr__(self) -> str:
        return "TelegramClient(token=<hidden>)"

    def send_message(self, chat_id: int, message: Message, buttons: Keyboard = ()) -> dict:
        params: dict[str, Any] = {"chat_id": chat_id, "text": html(message),
                                  "parse_mode": "HTML",
                                  "link_preview_options": preview_options(message)}  # fmt: skip
        if buttons:
            params["reply_markup"] = markup(buttons)
        try:
            return self._call("sendMessage", params)
        except TelegramError as exc:
            if not exc.description.startswith(PARSE_ERROR):
                raise
            log.warning("telegram %s: %s; resent as plain text", exc.method, exc.description)
        params.pop("parse_mode")
        return self._call("sendMessage", {**params, "text": plain(message)})

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        params: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            params["text"] = text
        self._call("answerCallbackQuery", params)

    def edit_buttons(self, chat_id: int, message_id: int, buttons: Keyboard) -> None:
        params = {"chat_id": chat_id, "message_id": message_id, "reply_markup": markup(buttons)}
        self._call("editMessageReplyMarkup", params)

    def set_webhook(self, url: str, secret_token: str) -> None:
        params = {"url": url, "secret_token": secret_token, "allowed_updates": ALLOWED_UPDATES}
        self._call("setWebhook", params)

    def delete_webhook(self) -> None:
        self._call("deleteWebhook", {})

    def get_updates(self, offset: int | None, timeout_s: int) -> list[dict]:
        params: dict[str, Any] = {"timeout": timeout_s, "allowed_updates": ALLOWED_UPDATES}
        if offset is not None:
            params["offset"] = offset
        return self._call("getUpdates", params, read_timeout_s=timeout_s + LONG_POLL_SLACK_S)

    def download_file(self, file_id: str) -> bytes:
        """getFile, then the file itself. Telegram serves bot downloads up to 20 MB."""
        path = self._call("getFile", {"file_id": file_id}).get("file_path")
        if not path:
            raise TelegramError("getFile", "no file_path")
        url = f"{API_BASE}/file/bot{self._token}/{path}"

        def get() -> bytes:
            try:
                response = self._client.get(url, timeout=HTTP_TIMEOUT_S)
            except httpx2.HTTPError as exc:
                raise TelegramError("file download", type(exc).__name__) from None
            if response.status_code != HTTP_OK:
                raise TelegramError("file download", f"HTTP {response.status_code}")
            return response.content

        return call_with_deadline(get, HTTP_TIMEOUT_S + DEADLINE_SLACK_S, "telegram file")

    def _call(self, method: str, params: dict, *, read_timeout_s: float = HTTP_TIMEOUT_S) -> Any:
        body = self._post(method, params, read_timeout_s)
        if not body.get("ok") and body.get("error_code") == TOO_MANY_REQUESTS:
            retry_after = body.get("parameters", {}).get("retry_after", 1)
            self._sleep(min(float(retry_after), MAX_RETRY_AFTER_S))
            body = self._post(method, params, read_timeout_s)
        if not body.get("ok"):
            raise TelegramError(method, str(body.get("description", "no description")))
        return body.get("result")

    def _post(self, method: str, params: dict, read_timeout_s: float) -> dict:
        url = f"{API_BASE}/bot{self._token}/{method}"
        timeout = httpx2.Timeout(read_timeout_s, connect=CONNECT_TIMEOUT_S)

        def post() -> dict:
            try:
                response = self._client.post(url, json=params, timeout=timeout)
            except httpx2.HTTPError as exc:
                raise TelegramError(method, type(exc).__name__) from None
            try:
                return response.json()
            except ValueError:
                raise TelegramError(method, f"HTTP {response.status_code}") from None

        return call_with_deadline(post, read_timeout_s + DEADLINE_SLACK_S, f"telegram {method}")
