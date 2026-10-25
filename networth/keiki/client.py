"""Keiki's HTTP API, the only module that knows its endpoints.

    client = TurnClient(turn.turn_url, turn_token)
    client.send("text", idempotency_key="t1:1")
    client.complete("completed")

    KeikiApi(api_key, agent_id).notice(conversation_id, text)

A turn is answered on its own turnUrl with the per-turn token; Keiki never sends twice under
one idempotency key, and a repeated /complete or a 409 turn_closed means the work is already
done, so both count as success. A notice asks Keiki to start a turn for a contact; with our
external harness that turn comes back to /keiki/turn. Tokens and keys sit in headers only;
no error or log line here carries one.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import httpx2

from networth.net import call_with_deadline, ipv4_client

API_BASE: Final = "https://onkeiki.com/api/v1"
HTTP_TIMEOUT_S: Final = 10.0
CONNECT_TIMEOUT_S: Final = 5.0
DEADLINE_S: Final = 15.0
CONFLICT: Final = 409
NOT_FOUND: Final = 404
TURN_CLOSED: Final = "turn_closed"
NO_CONVERSATION: Final = "no_conversation"
UNAVAILABLE: Final = "unavailable"


class KeikiError(Exception):
    """A Keiki call failed. The message names the call and the status, never a token."""

    def __init__(self, call: str, detail: str) -> None:
        super().__init__(f"keiki {call}: {detail}")
        self.call = call


def _error_code(response: httpx2.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    return str(body.get("error", "")) if isinstance(body, dict) else ""


def _post(client: httpx2.Client, call: str, url: str, token: str,
          payload: dict) -> httpx2.Response:  # fmt: skip
    def post() -> httpx2.Response:
        try:
            return client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
        except httpx2.HTTPError as exc:
            raise KeikiError(call, type(exc).__name__) from None

    return call_with_deadline(post, DEADLINE_S, f"keiki {call}")


def _default_client() -> httpx2.Client:
    return ipv4_client(HTTP_TIMEOUT_S, CONNECT_TIMEOUT_S)


class TurnClient:
    def __init__(self, turn_url: str, token: str, *, client: httpx2.Client | None = None) -> None:
        if not turn_url.startswith("https://"):
            raise KeikiError("turn", "turnUrl is not https")
        self._url = turn_url.rstrip("/")
        self._token = token
        self._client = client or _default_client()

    def __repr__(self) -> str:
        return "TurnClient(token=<hidden>)"

    def send(self, text: str, idempotency_key: str) -> None:
        self._call("messages", {"text": text, "idempotencyKey": idempotency_key})

    def complete(self, status: str, error: str | None = None) -> None:
        payload = {"status": status, **({"error": error} if error else {})}
        self._call("complete", payload)

    def _call(self, path: str, payload: dict) -> None:
        response = _post(self._client, path, f"{self._url}/{path}", self._token, payload)
        if response.is_success:
            return
        if response.status_code == CONFLICT and _error_code(response) == TURN_CLOSED:
            return
        raise KeikiError(path, f"HTTP {response.status_code}")


ClientFactory = Callable[[str, str], TurnClient]


class KeikiApi:
    def __init__(self, api_key: str, agent_id: str, *,
                 client: httpx2.Client | None = None) -> None:  # fmt: skip
        self._key = api_key
        self._agent = agent_id
        self._client = client or _default_client()

    def __repr__(self) -> str:
        return f"KeikiApi(agent_id={self._agent!r}, api_key=<hidden>)"

    def notice(self, phone: str, text: str) -> str:
        """Keiki's outcome for the notice, or why it could not be delivered."""
        url = f"{API_BASE}/developer/agents/{self._agent}/notice"
        response = _post(self._client, "notice", url, self._key, {"text": text, "phone": phone})
        if response.status_code == NOT_FOUND:
            code = _error_code(response)
            return code if code in (NO_CONVERSATION, UNAVAILABLE) else UNAVAILABLE
        if not response.is_success:
            raise KeikiError("notice", f"HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return "sent"
        return str(body.get("outcome") or body.get("status") or "sent")
