"""Fake Keiki: a signing key of our own, a JWKS that publishes it, signed turn requests, a
turn client that records what it was asked to send, and a notice API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from networth.keiki.verify import Keys

KID = "test-kid"
NOW = 1_800_000_000
TOKEN = "turn-token-not-real"
HMAC_SECRET = "whsec_test_not_real"
PRIVATE = Ed25519PrivateKey.generate()


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def jwks(kid: str = KID) -> dict:
    x = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return {"keys": [{"kty": "OKP", "crv": "Ed25519", "kid": kid, "alg": "EdDSA", "x": b64url(x)}]}


def fake_keys(kid: str = KID) -> Keys:
    return Keys(lambda: jwks(kid))


def ed25519_headers(body: bytes, *, t: int = NOW, kid: str = KID, token: str = TOKEN,
                    key: Ed25519PrivateKey = PRIVATE) -> dict[str, str]:  # fmt: skip
    sig = key.sign(f"{t}.{token}.".encode() + body)
    return {"Keiki-Signature-Ed25519": f"t={t},kid={kid},v1={b64url(sig)}",
            "Keiki-Turn-Token": token}  # fmt: skip


def hmac_headers(body: bytes, *, t: int = NOW, secret: str = HMAC_SECRET) -> dict[str, str]:
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return {"Keiki-Signature": f"t={t},v1={mac}"}


def body(payload: dict) -> bytes:
    return json.dumps(payload).encode()


AGENT = "agent-test"
SLACK_TEAM, SLACK_USER = "T_ACME", "U_ASHA"
ADDRESS = "asha@example.com"
TURN_URL = "https://onkeiki.example/api/v1/harness/turns/t1"


def turn_payload(*texts: str, turn_id: str = "t1", address: str = ADDRESS,
                 **extra: object) -> dict:  # fmt: skip
    return {
        "type": "keiki.turn", "turnId": turn_id, "agentId": AGENT, "conversationId": address,
        "channel": {"channel": "agentmail", "inboxId": address, "inboundText": "\n".join(texts)},
        "messages": [{"text": t, "messageId": f"m{i}"} for i, t in enumerate(texts)],
        "heldBack": False, "quietLoop": False,
        "keiki": {"apiBase": "https://onkeiki.example/api/v1", "turnUrl": TURN_URL},
        **extra,
    }  # fmt: skip


def slack_payload(text: str, thread: str, turn_id: str = "s1") -> dict:
    """A Slack DM as Keiki pushes it: the conversation is the thread, the author is userId."""
    channel = {"channel": "slack", "teamId": SLACK_TEAM, "channelId": "D1", "threadTs": thread,
               "userId": SLACK_USER, "inboundText": text}  # fmt: skip
    return turn_payload(text, turn_id=turn_id, address=f"slack:{SLACK_TEAM}:D1:{thread}",
                        channel=channel)  # fmt: skip


@dataclass
class FakeTurnClient:
    sent: list[tuple[str, str]] = field(default_factory=list)  # (text, idempotency key)
    completed: list[tuple[str, str | None]] = field(default_factory=list)
    fail_send: bool = False

    def send(self, text: str, idempotency_key: str) -> None:
        if self.fail_send:
            raise ConnectionError("keiki is down")
        self.sent.append((text, idempotency_key))

    def complete(self, status: str, error: str | None = None) -> None:
        self.completed.append((status, error))

    @property
    def texts(self) -> list[str]:
        return [text for text, _ in self.sent]


@dataclass
class FakeApi:
    notices: list[tuple[str, str]] = field(default_factory=list)

    def notice(self, phone: str, text: str) -> str:
        self.notices.append((phone, text))
        return "queued"
