"""A US broker link through SnapTrade, read-only, and the holdings it returns.

    url = snaptrade_link("tg:42", store)             # a portal link with read access only
    holdings = holdings_from_snaptrade("tg:42", store)
    forget_snaptrade("tg:42", store)

The only module that knows SnapTrade's endpoints (https://docs.snaptrade.com/openapi.yaml).
Every call carries clientId and timestamp in the query and an HMAC Signature header over the
path, the exact query string and the JSON body. The portal is always asked for
connectionType "read"; nothing here can ask for trade access. Keys and the user secret travel
only in the query and the signature, and no error or log line carries either, or the URL.

    uv run python -m networth.holdings.snaptrade     # checks the keys in .env, or says how
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import logging
import math
import os
import secrets
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol
from urllib.parse import quote, urlencode, urlsplit

import httpx2

from networth.app.settings import ENV_FILE, read_dotenv
from networth.holdings import model
from networth.holdings.model import Holding, Holdings, Kind, PriceFrom, Source, placed
from networth.net import call_with_deadline, ipv4_client

log = logging.getLogger(__name__)
# httpx2 logs every request URL at INFO, and ours carry the keys and the user secret.
logging.getLogger("httpx2").setLevel(logging.WARNING)

API_BASE: Final = "https://api.snaptrade.com"
CLIENT_ID_VAR: Final = "SNAPTRADE_CLIENT_ID"
CONSUMER_KEY_VAR: Final = "SNAPTRADE_CONSUMER_KEY"
HTTP_TIMEOUT_S: Final = 15.0
CONNECT_TIMEOUT_S: Final = 5.0
DEADLINE_S: Final = 25.0
READ_ONLY: Final = "read"
INVESTMENT: Final = "investment"
USD: Final = "USD"
USER_ID_PREFIX: Final = "networth-"
USER_ID_BYTES: Final = 16

KINDS: Final[Mapping[str, Kind]] = {
    "stock": Kind.STOCK, "adr": Kind.STOCK, "etf": Kind.ETF,
    "mutualfund": Kind.MUTUAL_FUND, "bond": Kind.BOND,
}  # fmt: skip
LEFT_OUT: Final[Mapping[str, str]] = {
    "option": "options are left out",
    "future": "futures are left out",
    "future_option": "options on futures are left out",
    "cfd": "CFDs are left out",
}

OWNER_NEEDED: Final = (
    "OWNER NEEDED: create a SnapTrade developer account (free tier) and add its keys to .env - "
    "1) sign up at https://dashboard.snaptrade.com/signup, "
    "2) verify your email and turn on 2FA, "
    "3) stay on the free Build plan (up to 5 connections; do not add a payment method), "
    "4) on the API Key page create a Commercial test key, "
    f"5) add {CLIENT_ID_VAR}=... and {CONSUMER_KEY_VAR}=... to .env (never commit it), "
    "6) run `uv run python -m networth.holdings.snaptrade`"
)


class SnapTradeError(Exception):
    """A SnapTrade call failed. The message names the call and the status, never a key, the
    user secret or the URL."""

    def __init__(self, call: str, detail: str) -> None:
        super().__init__(f"snaptrade {call}: {detail}")
        self.call = call


@dataclass(frozen=True)
class Keys:
    client_id: str = field(repr=False)
    consumer_key: str = field(repr=False)


@dataclass(frozen=True)
class SnapUser:
    user_id: str  # ours to choose, random, never an email or our own user id
    secret: str = field(repr=False)


@dataclass(frozen=True)
class Account:
    id: str
    kind: str
    name: str


class HoldingsStore(Protocol):
    def snaptrade_user(self, user_id: str) -> tuple[str, str] | None: ...
    def save_snaptrade_user(self, user_id: str, snaptrade_user_id: str, secret: str) -> None: ...
    def delete_snaptrade_user(self, user_id: str) -> None: ...
    def save_holdings(self, user_id: str, data: str) -> None: ...


def keys_from_env(environ: Mapping[str, str] = os.environ, dotenv: Path = ENV_FILE) -> Keys | None:
    env = {**read_dotenv(dotenv), **environ}
    client_id, consumer_key = env.get(CLIENT_ID_VAR), env.get(CONSUMER_KEY_VAR)
    return Keys(client_id, consumer_key) if client_id and consumer_key else None


def sign(consumer_key: str, path: str, query: str, body: object | None) -> str:
    """base64 HMAC-SHA256 of {"content", "path", "query"} as compact, key-sorted JSON."""
    content = json.dumps({"content": body or None, "path": path, "query": query},
                         separators=(",", ":"), sort_keys=True)  # fmt: skip
    digest = hmac.new(consumer_key.encode(), content.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def new_snaptrade_user_id() -> str:
    """Random rather than a hash of our user id, so a user who stops and links again never
    collides with a SnapTrade user that outlived the local row."""
    return USER_ID_PREFIX + secrets.token_hex(USER_ID_BYTES)


def _field(call: str, body: object, key: str) -> object:
    if not isinstance(body, dict) or body.get(key) is None:
        raise SnapTradeError(call, f"the answer has no {key}")
    return body[key]


def _rows(call: str, body: object) -> list[dict]:
    rows = _field(call, body, "results")
    if not isinstance(rows, list):
        raise SnapTradeError(call, "results is not a list")
    return [row for row in rows if isinstance(row, dict)]


class SnapTrade:
    def __init__(self, keys: Keys, *, client: httpx2.Client | None = None,
                 clock: Callable[[], float] = time.time) -> None:  # fmt: skip
        self._keys = keys
        self._client = client or ipv4_client(HTTP_TIMEOUT_S, CONNECT_TIMEOUT_S)
        self._clock = clock

    def __repr__(self) -> str:
        return "SnapTrade(keys=<hidden>)"

    def register_user(self, snaptrade_user_id: str) -> SnapUser:
        body = self._call("register", "POST", "/snapTrade/registerUser",
                          body={"userId": snaptrade_user_id})  # fmt: skip
        return SnapUser(snaptrade_user_id, str(_field("register", body, "userSecret")))

    def login_link(self, user: SnapUser, redirect: str | None = None) -> str:
        """A connection-portal URL with read access only. It lasts 5 minutes."""
        payload = {
            "connectionType": READ_ONLY,
            **({"customRedirect": redirect} if redirect else {}),
        }
        body = self._call("login", "POST", "/snapTrade/login", user=user, body=payload)
        return str(_field("login", body, "redirectURI"))

    def accounts(self, user: SnapUser) -> list[Account]:
        rows = _rows("accounts", self._call("accounts", "GET", "/accounts/all", user=user))
        return [Account(str(r["id"]), str(r.get("kind") or ""), str(r.get("display_name") or ""))
                for r in rows if r.get("id")]  # fmt: skip

    def positions(self, user: SnapUser, account_id: str) -> list[dict]:
        path = f"/accounts/{quote(account_id, safe='')}/positions/all"
        return _rows("positions", self._call("positions", "GET", path, user=user))

    def delete_user(self, snaptrade_user_id: str) -> None:
        """SnapTrade queues the deletion and answers at once."""
        self._call("delete", "DELETE", "/snapTrade/deleteUser",
                   extra=(("userId", snaptrade_user_id),))  # fmt: skip

    def _call(
        self, call: str, method: str, path: str, *, user: SnapUser | None = None,
        extra: Iterable[tuple[str, str]] = (), body: dict | None = None,
    ) -> object:  # fmt: skip
        params = [("clientId", self._keys.client_id), ("timestamp", str(int(self._clock())))]
        if user is not None:
            params += [("userId", user.user_id), ("userSecret", user.secret)]
        query = urlencode([*params, *extra])
        headers = {"Accept": "application/json",
                   "Signature": sign(self._keys.consumer_key, path, query, body)}  # fmt: skip
        content = None
        if body is not None:
            content = json.dumps(body, separators=(",", ":"))
            headers["Content-Type"] = "application/json"

        def send() -> httpx2.Response:
            try:
                return self._client.request(method, f"{API_BASE}{path}?{query}",
                                            content=content, headers=headers)  # fmt: skip
            except httpx2.HTTPError as exc:
                raise SnapTradeError(call, type(exc).__name__) from None

        response = call_with_deadline(send, DEADLINE_S, f"snaptrade {call}")
        if not response.is_success:
            log.warning("snaptrade %s failed: HTTP %s", call, response.status_code)
            raise SnapTradeError(call, f"HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            raise SnapTradeError(call, "the answer is not JSON") from None


def _number(value: object) -> float | None:
    """SnapTrade sends amounts as decimal strings, any of which may be null."""
    if value is None:
        return None
    try:
        number = float(str(value))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _holding(position: Mapping) -> Holding | str:
    """The Holding, or what the report should say about a position it leaves out."""
    instrument = position.get("instrument") or {}
    symbol = str(instrument.get("symbol") or "a position")
    kind = str(instrument.get("kind") or "other")
    if kind in LEFT_OUT:
        return f"{symbol}: {LEFT_OUT[kind]}"
    currency = position.get("currency") or instrument.get("currency")
    if currency != USD:
        priced_in = currency or "an unknown currency"
        return f"{symbol}: priced in {priced_in}, left out (one report, one currency)"
    units, avg_cost = _number(position.get("units")), _number(position.get("cost_basis"))
    if units is None:
        return f"{symbol}: the broker did not say how many units"
    if units <= 0:
        return f"{symbol}: short or empty positions are left out"
    if avg_cost is None:
        return f"{symbol}: the broker did not say what it cost"
    price = _number(position.get("price"))
    return Holding(
        name=str(instrument.get("description") or symbol), units=units, avg_cost=avg_cost,
        currency=USD, kind=KINDS.get(kind, Kind.OTHER), identifier=symbol, price=price,
        price_from=PriceFrom.BROKER if price is not None else PriceFrom.NONE,
    )  # fmt: skip


def to_holdings(user_id: str, positions_by_account: Mapping[str, Sequence[Mapping]],
                as_of: dt.datetime) -> Holdings:  # fmt: skip
    """Confirmed already: the broker is the source, there is no reading to check."""
    read = [_holding(p) for positions in positions_by_account.values() for p in positions]
    items = tuple(placed(r) for r in read if isinstance(r, Holding))
    unread = tuple(r for r in read if isinstance(r, str))
    if not positions_by_account:
        unread = ("no investment account is linked yet",)
    return Holdings(user_id, Source.SNAPTRADE, as_of, items, confirmed=True, unread=unread)


def _api(client: SnapTrade | None) -> SnapTrade | None:
    if client is not None:
        return client
    keys = keys_from_env()
    return SnapTrade(keys) if keys else None


def _stored(user_id: str, store: HoldingsStore) -> SnapUser | None:
    row = store.snaptrade_user(user_id)
    return SnapUser(*row) if row else None


def snaptrade_link(user_id: str, store: HoldingsStore, *, client: SnapTrade | None = None,
                   redirect: str | None = None) -> str | None:  # fmt: skip
    """A read-only portal link, registering the user with SnapTrade the first time. None
    when the SnapTrade keys are not set."""
    api = _api(client)
    if api is None:
        return None
    user = _stored(user_id, store)
    if user is None:
        user = api.register_user(new_snaptrade_user_id())
        store.save_snaptrade_user(user_id, user.user_id, user.secret)
    return api.login_link(user, redirect)


def holdings_from_snaptrade(user_id: str, store: HoldingsStore, *,
                            client: SnapTrade | None = None) -> Holdings | None:  # fmt: skip
    """The user's positions in every linked investment account, saved and returned. None when
    the keys are not set or the user never asked for a link."""
    api, user = _api(client), _stored(user_id, store)
    if api is None or user is None:
        return None
    accounts = [a for a in api.accounts(user) if a.kind == INVESTMENT]
    positions = {a.id: api.positions(user, a.id) for a in accounts}
    holdings = to_holdings(user_id, positions, dt.datetime.now(dt.UTC))
    store.save_holdings(user_id, model.to_json(holdings))
    return holdings


def forget_snaptrade(user_id: str, store: HoldingsStore, *,
                     client: SnapTrade | None = None) -> None:  # fmt: skip
    user = _stored(user_id, store)
    if user is None:
        return
    api = _api(client)
    if api is not None:
        api.delete_user(user.user_id)
    # Only after the remote delete, so a failed one leaves the row to retry from.
    store.delete_snaptrade_user(user_id)


def main(*, environ: Mapping[str, str] = os.environ, dotenv: Path = ENV_FILE,
         client: SnapTrade | None = None) -> None:  # fmt: skip
    """Check the keys end to end with a throwaway user, deleted again at the end."""
    keys = keys_from_env(environ, dotenv)
    if client is None and keys is None:
        print(OWNER_NEEDED)
        return
    api = client or SnapTrade(keys)  # type: ignore[arg-type]
    user = api.register_user(new_snaptrade_user_id())
    try:
        host = urlsplit(api.login_link(user)).hostname
        print(f"read-only link generated on {host}")
        print(f"accounts linked: {len(api.accounts(user))}")
    finally:
        api.delete_user(user.user_id)


if __name__ == "__main__":
    main()
