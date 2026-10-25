"""Signed, expiring links to a user's own page, so no login is needed.

    token = sign(profile.link_token, secret, now)      # "<link_token>.<expires>.<signature>"
    link_token = verify(token, secret, now)            # None when tampered or expired

The signature is an HMAC-SHA256 over the link token and the expiry, keyed by
LINK_SIGNING_SECRET. Changing the secret revokes every link at once.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
from typing import Final

LINK_DAYS: Final = 30
SIGNATURE_CHARS: Final = 32


def _signature(link_token: str, expires: int, secret: str) -> str:
    message = f"{link_token}.{expires}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()[:SIGNATURE_CHARS]


def sign(link_token: str, secret: str, now: dt.datetime) -> str:
    expires = int((now + dt.timedelta(days=LINK_DAYS)).timestamp())
    return f"{link_token}.{expires}.{_signature(link_token, expires, secret)}"


def verify(token: str, secret: str, now: dt.datetime) -> str | None:
    if not token.isascii():  # str.isdigit takes "²" and compare_digest raises on non-ASCII
        return None
    link_token, _, rest = token.partition(".")
    expires, _, signature = rest.partition(".")
    if not (link_token and expires.isdigit() and signature):
        return None
    if not hmac.compare_digest(signature, _signature(link_token, int(expires), secret)):
        return None
    return link_token if int(expires) > now.timestamp() else None


def page_url(public_url: str | None, link_token: str, secret: str | None,
             now: dt.datetime) -> str | None:  # fmt: skip
    if not (public_url and secret):
        return None
    return f"{public_url}/u/{sign(link_token, secret, now)}"
