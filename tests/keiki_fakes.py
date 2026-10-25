"""Fake Keiki: a signing key of our own, a JWKS that publishes it, and signed turn requests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

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
