"""SnapTrade: signing, the read-only portal link, and positions mapped to Holdings. No network:
httpx2's MockTransport stands in for SnapTrade and serves the recorded fixtures."""

from __future__ import annotations

import base64
import dataclasses
import datetime as dt
import hashlib
import hmac
import json
import logging
from pathlib import Path

import httpx2
import pytest

from networth.app.store import Status, Store, new_profile, now_iso
from networth.holdings import model, snaptrade
from networth.holdings.model import Bucket, Kind, PriceFrom, Source
from networth.holdings.snaptrade import Keys, SnapTrade, SnapTradeError

FIXTURES = Path(__file__).parent / "fixtures" / "holdings"
KEYS = Keys("client-FAKE-id", "consumer-FAKE-key")
SECRET = "user-FAKE-secret"
PORTAL = "https://app.snaptrade.com/snapTrade/redeemToken?token=FAKE-token&clientId=client-FAKE-id"
NOW = 1_760_000_000
USER = "tg:42"
INVESTMENT_ID = "0b7c8f2e-0000-4000-8000-00000000fa11"
DEPOSIT_ID = "9d4e5f6a-0000-4000-8000-0000000dep05"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeSnapTrade:
    def __init__(self, status: int = 200) -> None:
        self.requests: list[httpx2.Request] = []
        self.status = status

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx2.Response(self.status, json={"detail": "Unable to verify signature"})
        path = request.url.path
        if path == "/snapTrade/registerUser":
            body = json.loads(request.content)
            return httpx2.Response(200, json={"userId": body["userId"], "userSecret": SECRET})
        if path == "/snapTrade/login":
            return httpx2.Response(200, json={"redirectURI": PORTAL, "sessionId": "s-1"})
        if path == "/accounts/all":
            return httpx2.Response(200, json=fixture("snaptrade_accounts.json"))
        if path == f"/accounts/{INVESTMENT_ID}/positions/all":
            return httpx2.Response(200, json=fixture("snaptrade_positions.json"))
        if path == "/snapTrade/deleteUser":
            return httpx2.Response(200, json={"status": "deleted", "detail": "queued"})
        return httpx2.Response(404, json={"detail": "not found"})

    def api(self) -> SnapTrade:
        client = httpx2.Client(transport=httpx2.MockTransport(self.handler))
        return SnapTrade(KEYS, client=client, clock=lambda: NOW)

    def to(self, path: str) -> list[httpx2.Request]:
        return [r for r in self.requests if r.url.path == path]


@pytest.fixture
def fake() -> FakeSnapTrade:
    return FakeSnapTrade()


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path)


def signed_content(request: httpx2.Request) -> tuple[str, str, object]:
    raw_path, _, query = request.url.raw_path.decode().partition("?")
    return raw_path, query, json.loads(request.content) if request.content else None


def test_sign_matches_a_hand_computed_hmac() -> None:
    content = (
        '{"content":{"userId":"u1"},"path":"/snapTrade/registerUser",'
        '"query":"clientId=c&timestamp=1"}'
    )
    expected = base64.b64encode(
        hmac.new(b"secret-key", content.encode(), hashlib.sha256).digest()
    ).decode()

    assert snaptrade.sign("secret-key", "/snapTrade/registerUser", "clientId=c&timestamp=1",
                          {"userId": "u1"}) == expected  # fmt: skip


def test_sign_treats_no_body_as_null_content() -> None:
    content = '{"content":null,"path":"/accounts/all","query":"clientId=c&timestamp=1"}'
    expected = base64.b64encode(hmac.new(b"k", content.encode(), hashlib.sha256).digest()).decode()

    assert snaptrade.sign("k", "/accounts/all", "clientId=c&timestamp=1", None) == expected
    assert snaptrade.sign("k", "/accounts/all", "clientId=c&timestamp=1", {}) == expected


def test_every_request_carries_a_signature_over_what_was_sent(
    fake: FakeSnapTrade, store: Store
) -> None:
    snaptrade.snaptrade_link(USER, store, client=fake.api())
    snaptrade.holdings_from_snaptrade(USER, store, client=fake.api())

    assert len(fake.requests) == 4
    for request in fake.requests:
        path, query, body = signed_content(request)
        assert f"clientId={KEYS.client_id}&timestamp={NOW}" in query
        assert request.headers["Signature"] == snaptrade.sign(KEYS.consumer_key, path, query, body)


def test_login_asks_for_read_access_only(fake: FakeSnapTrade, store: Store) -> None:
    url = snaptrade.snaptrade_link(USER, store, client=fake.api(), redirect="https://example.test/")
    snaptrade.holdings_from_snaptrade(USER, store, client=fake.api())
    snaptrade.forget_snaptrade(USER, store, client=fake.api())

    assert url == PORTAL
    (login,) = fake.to("/snapTrade/login")
    assert json.loads(login.content) == {"connectionType": "read",
                                         "customRedirect": "https://example.test/"}  # fmt: skip
    for request in fake.requests:
        assert "trade" not in request.url.query.decode().lower()
        assert "trade" not in request.content.decode().lower()


def test_a_user_registers_once_across_links(fake: FakeSnapTrade, store: Store) -> None:
    first = snaptrade.snaptrade_link(USER, store, client=fake.api())
    second = snaptrade.snaptrade_link(USER, store, client=fake.api())

    assert first == second == PORTAL
    (register,) = fake.to("/snapTrade/registerUser")
    snap_id = json.loads(register.content)["userId"]
    assert USER not in snap_id
    assert store.snaptrade_user(USER) == (snap_id, SECRET)
    for login in fake.to("/snapTrade/login"):
        assert login.url.params["userId"] == snap_id
        assert login.url.params["userSecret"] == SECRET


def test_no_keys_means_no_link(monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                               store: Store) -> None:  # fmt: skip
    monkeypatch.setattr(snaptrade, "keys_from_env", lambda: None)

    assert snaptrade.snaptrade_link(USER, store) is None
    assert snaptrade.holdings_from_snaptrade(USER, store) is None
    assert store.snaptrade_user(USER) is None


def test_keys_come_from_env_over_dotenv(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("SNAPTRADE_CLIENT_ID=from-file\nSNAPTRADE_CONSUMER_KEY=key-file\n")

    assert snaptrade.keys_from_env({}, dotenv) == Keys("from-file", "key-file")
    assert snaptrade.keys_from_env({"SNAPTRADE_CLIENT_ID": "from-env"}, dotenv) == Keys(
        "from-env", "key-file"
    )
    assert snaptrade.keys_from_env({}, tmp_path / "missing") is None
    assert "key-file" not in repr(Keys("from-file", "key-file"))


def test_main_without_keys_prints_owner_needed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    snaptrade.main(environ={}, dotenv=tmp_path / "missing")

    out = capsys.readouterr().out
    assert out.startswith("OWNER NEEDED: create a SnapTrade developer account (free tier)")
    assert "https://dashboard.snaptrade.com/signup" in out
    assert "SNAPTRADE_CLIENT_ID=" in out and "SNAPTRADE_CONSUMER_KEY=" in out


def test_main_with_keys_prints_the_host_only_and_cleans_up(
    fake: FakeSnapTrade, capsys: pytest.CaptureFixture[str]
) -> None:
    snaptrade.main(client=fake.api())

    out = capsys.readouterr().out
    assert "read-only link generated on app.snaptrade.com" in out
    assert "accounts linked: 2" in out
    assert "FAKE-token" not in out and SECRET not in out
    assert len(fake.to("/snapTrade/deleteUser")) == 1


def test_positions_map_to_placed_usd_holdings() -> None:
    as_of = dt.datetime(2026, 10, 25, tzinfo=dt.UTC)
    positions = fixture("snaptrade_positions.json")["results"]

    h = snaptrade.to_holdings(USER, {INVESTMENT_ID: positions}, as_of)

    assert (h.user_id, h.source, h.as_of, h.confirmed, h.currency) == (
        USER, Source.SNAPTRADE, as_of, True, "USD")  # fmt: skip
    rows = {i.identifier: (i.name, i.units, i.avg_cost, i.price, i.kind, i.bucket) for i in h.items}
    assert rows == {
        "AAPL": ("Apple Inc.", 10.5, 150.25, 190.0, Kind.STOCK, Bucket.GROWTH),
        "VOO": ("Vanguard S&P 500 ETF", 4.0, 420.0, 500.1, Kind.ETF, Bucket.CORE),
        "SPAXX": ("Fidelity Government Money Market Fund", 1200.0, 1.0, 1.0, Kind.MUTUAL_FUND,
                  Bucket.SAFETY),
    }  # fmt: skip
    assert all(i.price_from is PriceFrom.BROKER for i in h.items)


def test_options_and_other_currencies_land_in_unread() -> None:
    positions = fixture("snaptrade_positions.json")["results"]

    h = snaptrade.to_holdings(USER, {INVESTMENT_ID: positions}, dt.datetime.now(dt.UTC))

    assert len(h.unread) == 2
    assert any("AAPL  261218C00200000" in u and "options are left out" in u for u in h.unread)
    assert any("SHOP.TO" in u and "CAD" in u for u in h.unread)


def test_positions_without_units_or_cost_are_not_guessed() -> None:
    stock = {"kind": "stock", "symbol": "MSFT", "description": "Microsoft", "currency": "USD"}
    positions = [
        {"instrument": stock, "units": None, "cost_basis": "300", "currency": "USD"},
        {"instrument": {**stock, "symbol": "NVDA"}, "units": "2", "cost_basis": None,
         "currency": "USD"},
        {"instrument": {**stock, "symbol": "TSLA"}, "units": "-5", "cost_basis": "200",
         "currency": "USD"},
    ]  # fmt: skip

    h = snaptrade.to_holdings(USER, {INVESTMENT_ID: positions}, dt.datetime.now(dt.UTC))

    assert h.items == ()
    assert [u.split(":")[0] for u in h.unread] == ["MSFT", "NVDA", "TSLA"]


def test_holdings_come_from_investment_accounts_and_are_saved(
    fake: FakeSnapTrade, store: Store
) -> None:
    snaptrade.snaptrade_link(USER, store, client=fake.api())

    h = snaptrade.holdings_from_snaptrade(USER, store, client=fake.api())

    assert h is not None
    assert {i.identifier for i in h.items} == {"AAPL", "VOO", "SPAXX"}
    assert fake.to(f"/accounts/{DEPOSIT_ID}/positions/all") == []
    saved = store.holdings_data(USER)
    assert saved is not None and model.from_json(saved) == h


def test_a_user_who_never_linked_gets_none(fake: FakeSnapTrade, store: Store) -> None:
    assert snaptrade.holdings_from_snaptrade(USER, store, client=fake.api()) is None
    assert fake.requests == []


def test_errors_never_carry_keys_or_the_secret(
    store: Store, caplog: pytest.LogCaptureFixture
) -> None:
    store.save_snaptrade_user(USER, "networth-abc", SECRET)
    failing = FakeSnapTrade(status=401)

    with caplog.at_level(logging.INFO), pytest.raises(SnapTradeError) as caught:
        snaptrade.holdings_from_snaptrade(USER, store, client=failing.api())

    text = str(caught.value) + caplog.text
    assert "HTTP 401" in str(caught.value)
    assert "snaptrade accounts failed: HTTP 401" in caplog.text
    for secret in (KEYS.client_id, KEYS.consumer_key, SECRET, "api.snaptrade.com"):
        assert secret not in text


def test_transport_errors_never_carry_the_url(store: Store) -> None:
    def boom(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(f"cannot reach {request.url}", request=request)

    api = SnapTrade(KEYS, client=httpx2.Client(transport=httpx2.MockTransport(boom)))
    store.save_snaptrade_user(USER, "networth-abc", SECRET)

    with pytest.raises(SnapTradeError) as caught:
        snaptrade.holdings_from_snaptrade(USER, store, client=api)

    assert str(caught.value) == "snaptrade accounts: ConnectError"
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_forget_deletes_the_snaptrade_user(fake: FakeSnapTrade, store: Store) -> None:
    snaptrade.snaptrade_link(USER, store, client=fake.api())
    (snap_id, _) = store.snaptrade_user(USER) or ("", "")

    snaptrade.forget_snaptrade(USER, store, client=fake.api())

    assert store.snaptrade_user(USER) is None
    (delete,) = fake.to("/snapTrade/deleteUser")
    assert delete.method == "DELETE" and delete.url.params["userId"] == snap_id


def test_stop_deletes_the_snaptrade_user_and_holdings(store: Store) -> None:
    profile = new_profile(42, now_iso())
    store.save_profile(profile)
    store.save_snaptrade_user(profile.user_id, "networth-abc", SECRET)
    store.save_holdings(profile.user_id, "{}")

    store.save_profile(dataclasses.replace(profile, status=Status.STOPPED))

    assert store.snaptrade_user(profile.user_id) is None
    assert store.holdings_data(profile.user_id) is None
