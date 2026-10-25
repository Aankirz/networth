"""Is a pushed Keiki request really from Keiki? One answer: None when trusted, else a reason.

    reason = verify(request.headers, raw_body, time.time(), keys, hmac_secret)

Two signatures count, and either one is enough (docs/phases/phase-3c-spike.md, Q3):

    Keiki-Signature-Ed25519: t=<unix s>,kid=<key id>,v1=<base64url Ed25519 over
                             "<t>.<Keiki-Turn-Token>.<raw body>">   (empty token when absent)
    Keiki-Signature:         t=<unix s>,v1=<hex HMAC-SHA256(secret, "<t>.<raw body>")>

The Ed25519 key comes from Keiki's published JWKS, so it needs no secret of ours. The HMAC form
is checked only when KEIKI_SIGNING_SECRET is set. A signature older or newer than max_age_s is
stale: the docs set no window for turns, so we use the five minutes their identity webhook
page asks for.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import threading
import time
from collections.abc import Callable, Mapping
from typing import Final

import httpx2
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from networth.net import call_with_deadline, ipv4_client

log = logging.getLogger("networth.keiki")

JWKS_URL: Final = "https://onkeiki.com/.well-known/keiki-turn-keys.json"
ED25519_HEADER: Final = "keiki-signature-ed25519"
HMAC_HEADER: Final = "keiki-signature"
TOKEN_HEADER: Final = "keiki-turn-token"
MAX_AGE_S: Final = 300
REFRESH_GAP_S: Final = 60.0
HTTP_TIMEOUT_S: Final = 5.0
DEADLINE_S: Final = 10.0
HTTP_OK: Final = 200

Jwks = Mapping[str, object]


def fetch_jwks(client: httpx2.Client | None = None) -> Jwks:
    http = client or ipv4_client(HTTP_TIMEOUT_S, HTTP_TIMEOUT_S)

    def get() -> Jwks:
        response = http.get(JWKS_URL)
        if response.status_code != HTTP_OK:
            raise RuntimeError(f"keiki jwks: HTTP {response.status_code}")
        return response.json()

    return call_with_deadline(get, DEADLINE_S, "keiki jwks")


def b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def parse_jwks(jwks: Jwks) -> dict[str, Ed25519PublicKey]:
    """{kid: key} for every OKP/Ed25519 entry; anything else in the set is skipped."""
    keys: dict[str, Ed25519PublicKey] = {}
    entries = jwks.get("keys")
    for k in entries if isinstance(entries, list) else []:
        if isinstance(k, dict) and k.get("kty") == "OKP" and k.get("crv") == "Ed25519":
            try:
                keys[str(k["kid"])] = Ed25519PublicKey.from_public_bytes(b64url(str(k["x"])))
            except (KeyError, ValueError, binascii.Error):
                continue
    return keys


class Keys:
    """Keiki's turn-signing keys, fetched on first use and again on an unknown kid, at most
    once per REFRESH_GAP_S so a flood of made-up kids cannot hammer Keiki."""

    def __init__(self, fetch: Callable[[], Jwks] = fetch_jwks,
                 clock: Callable[[], float] = time.monotonic) -> None:  # fmt: skip
        self._fetch = fetch
        self._clock = clock
        self._keys: dict[str, Ed25519PublicKey] = {}
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    def get(self, kid: str) -> Ed25519PublicKey | None:
        with self._lock:
            if kid not in self._keys and self._may_refresh():
                self._fetched_at = self._clock()
                try:
                    self._keys = parse_jwks(self._fetch())
                except Exception as exc:  # noqa: BLE001 - a failed fetch means untrusted, not a crash
                    log.warning("keiki jwks fetch failed: %s", type(exc).__name__)
            return self._keys.get(kid)

    def _may_refresh(self) -> bool:
        return self._fetched_at is None or self._clock() - self._fetched_at >= REFRESH_GAP_S


def fields_of(header: str) -> dict[str, str]:
    """'t=1,kid=a,v1=b' -> {"t": "1", "kid": "a", "v1": "b"}."""
    pairs = (part.strip().split("=", 1) for part in header.split(","))
    return {p[0]: p[1] for p in pairs if len(p) == 2}


def _stamp(fields: Mapping[str, str], now: float, max_age_s: int) -> str | int:
    """The signed unix time, or why it cannot be used."""
    t = fields.get("t", "")
    if not t.isascii() or not t.isdigit():
        return "malformed"
    return int(t) if abs(now - int(t)) <= max_age_s else "stale"


def check_ed25519(header: str, token: str, body: bytes, now: float, keys: Keys,
                  max_age_s: int) -> str | None:  # fmt: skip
    fields = fields_of(header)
    t = _stamp(fields, now, max_age_s)
    if isinstance(t, str):
        return t
    key = keys.get(fields.get("kid", ""))
    if key is None:
        return "unknown_kid"
    try:
        key.verify(b64url(fields.get("v1", "")), f"{t}.{token}.".encode() + body)
    except (InvalidSignature, ValueError, binascii.Error):
        return "bad_signature"
    return None


def check_hmac(header: str, body: bytes, now: float, secret: str, max_age_s: int) -> str | None:
    fields = fields_of(header)
    t = _stamp(fields, now, max_age_s)
    if isinstance(t, str):
        return t
    want = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return None if hmac.compare_digest(want, fields.get("v1", "")) else "bad_signature"


def verify(headers: Mapping[str, str], raw_body: bytes, now: float, keys: Keys,
           hmac_secret: str | None, max_age_s: int = MAX_AGE_S) -> str | None:  # fmt: skip
    """None when either signature checks out, else the first signature's reason."""
    h = {k.lower(): v for k, v in headers.items()}
    reasons: list[str] = []
    if ed := h.get(ED25519_HEADER):
        reason = check_ed25519(ed, h.get(TOKEN_HEADER, ""), raw_body, now, keys, max_age_s)
        if reason is None:
            return None
        reasons.append(reason)
    if hmac_secret and (mac := h.get(HMAC_HEADER)):
        reason = check_hmac(mac, raw_body, now, hmac_secret, max_age_s)
        if reason is None:
            return None
        reasons.append(reason)
    return reasons[0] if reasons else "unsigned"
