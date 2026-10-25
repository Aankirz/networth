"""Who a signed-in web visitor is, as the site vouches for them.

    who = verify(request.headers["authorization"], cfg.web_secret, now)

The site checks the Auth.js session on its own server, then sends a token that lasts a minute:
`v1.<payload>.<mac>`, where payload is base64url JSON {"sub", "name", "exp"} and mac is
base64url HMAC-SHA256 over "v1.<payload>" with NETWORTH_WEB_SECRET. `sub` is the Google subject
id. Nothing the browser sends ever names a user; only this token does, and only the site can
sign it.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Final

VERSION: Final = "v1"
MAX_AGE_S: Final = 300  # a token claiming to live longer than this was not made by the site
MAX_SUBJECT: Final = 255
MAX_NAME: Final = 200
BEARER: Final = "Bearer "


@dataclass(frozen=True)
class WebVisitor:
    subject: str  # the Google subject id
    name: str


def _unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def mac(secret: str, signed: str) -> str:
    digest = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify(header: str | None, secret: str | None, now: dt.datetime) -> WebVisitor | None:
    """The visitor a valid, unexpired token names. None for anything else, including a server
    with no secret set, so a missing secret refuses everyone instead of trusting anyone."""
    if not secret or not header or not header.startswith(BEARER):
        return None
    parts = header[len(BEARER) :].strip().split(".")
    if len(parts) != 3 or parts[0] != VERSION:
        return None
    if not hmac.compare_digest(mac(secret, f"{VERSION}.{parts[1]}"), parts[2]):
        return None
    try:
        claims = json.loads(_unb64(parts[1]))
    except (binascii.Error, ValueError):
        return None
    if not isinstance(claims, dict):
        return None
    sub, name, exp = claims.get("sub"), claims.get("name", ""), claims.get("exp")
    if not isinstance(sub, str) or not 0 < len(sub) <= MAX_SUBJECT or not isinstance(name, str):
        return None
    if not isinstance(exp, int) or isinstance(exp, bool):
        return None
    left = exp - now.timestamp()
    if not 0 < left <= MAX_AGE_S:
        return None
    return WebVisitor(sub, name[:MAX_NAME])
