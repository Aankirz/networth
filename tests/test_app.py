"""The server and the Telegram client, with no network.

fastapi.testclient needs httpx, which this project does not install, so requests go straight
to the ASGI app through a few lines of asyncio.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import sys
import types
from pathlib import Path

import httpx2
import pytest
from fastapi import APIRouter, FastAPI

from networth.app.main import SECRET_HEADER, create_app
from networth.app.settings import Settings
from networth.app.store import Status, Step, Store
from networth.bot.telegram import Button, TelegramClient, TelegramError
from tests.test_onboarding import FakeBot, text_update

SECRET = "s3cret-for-tests"
TOKEN = "123456:TEST-TOKEN-not-real"


def call(app: FastAPI, method: str, path: str, *, headers: dict | None = None,
         body: bytes = b"") -> tuple[int, dict]:  # fmt: skip
    async def run() -> tuple[int, dict]:
        inbox = [{"type": "http.request", "body": body, "more_body": False}]
        sent: list[dict] = []

        async def receive() -> dict:
            return inbox.pop(0) if inbox else {"type": "http.disconnect"}

        async def send(message: dict) -> None:
            sent.append(message)

        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "root_path": "", "client": ("test", 1), "server": ("test", 80),
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        }  # fmt: skip
        await app(scope, receive, send)
        status = next(m["status"] for m in sent if m["type"] == "http.response.start")
        payload = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        return status, json.loads(payload)

    return asyncio.run(run())


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path)


@pytest.fixture
def app(store: Store) -> FastAPI:
    return create_app(store, FakeBot(), SECRET)


def post_update(app: FastAPI, update: dict, secret: str | None) -> tuple[int, dict]:
    headers = {"content-type": "application/json"}
    if secret is not None:
        headers[SECRET_HEADER] = secret
    return call(app, "POST", "/telegram/webhook", headers=headers,
                body=json.dumps(update).encode())  # fmt: skip


def test_health(app: FastAPI) -> None:
    assert call(app, "GET", "/health") == (200, {"ok": True})


def test_webhook_without_the_secret_is_rejected(app: FastAPI, store: Store) -> None:
    assert post_update(app, text_update("/start"), None)[0] == 401
    assert post_update(app, text_update("/start"), "wrong")[0] == 401
    assert store.get_profile("tg:4242") is None


def test_webhook_with_the_secret_stores_a_profile_at_the_first_step(
    app: FastAPI, store: Store
) -> None:
    assert post_update(app, text_update("/start"), SECRET) == (200, {"ok": True})
    profile = store.get_profile("tg:4242")
    assert profile is not None
    assert (profile.step, profile.status) == (Step.GOAL, Status.ACTIVE)


def test_webhook_answers_200_even_when_handling_fails(store: Store) -> None:
    class BrokenBot(FakeBot):
        def send_message(self, chat_id: int, text: str, buttons=()) -> dict:
            raise TelegramError("sendMessage", "Forbidden: bot was blocked by the user")

    app = create_app(store, BrokenBot(), SECRET)
    assert post_update(app, text_update("/start"), SECRET) == (200, {"ok": True})


def test_webhook_unconfigured_answers_503(store: Store) -> None:
    app = create_app(store, None, None)
    assert post_update(app, text_update("/start"), "anything")[0] == 503
    assert call(app, "GET", "/health")[0] == 200


def test_app_runs_without_networth_web(monkeypatch: pytest.MonkeyPatch, store: Store) -> None:
    monkeypatch.setitem(sys.modules, "networth.web.routes", None)
    app = create_app(store, FakeBot(), SECRET)
    assert call(app, "GET", "/health") == (200, {"ok": True})


def test_app_mounts_networth_web_when_present(
    monkeypatch: pytest.MonkeyPatch, store: Store
) -> None:
    router = APIRouter()
    router.add_api_route("/hello", lambda: {"hello": "web"})
    module = types.ModuleType("networth.web.routes")
    module.router = router  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "networth.web.routes", module)
    app = create_app(store, FakeBot(), SECRET)
    assert call(app, "GET", "/hello") == (200, {"hello": "web"})


def test_app_survives_a_broken_networth_web(monkeypatch: pytest.MonkeyPatch, store: Store) -> None:
    def explode(name: str, *args: object, **kwargs: object) -> object:
        if name == "networth.web.routes":
            raise RuntimeError("web module broke at import")
        return real_import(name, *args, **kwargs)

    real_import = builtins.__import__
    monkeypatch.delitem(sys.modules, "networth.web.routes", raising=False)
    monkeypatch.setattr(builtins, "__import__", explode)
    app = create_app(store, FakeBot(), SECRET)
    assert call(app, "GET", "/health") == (200, {"ok": True})


def test_settings_prefer_real_env_and_never_touch_os_environ(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "# local\nTELEGRAM_BOT_TOKEN='from-file'\nDATA_DIR=/x\nPUBLIC_URL=https://a/\n"
    )
    settings = Settings.from_env({"DATA_DIR": "/real"}, dotenv)
    assert settings.bot_token == "from-file"
    assert settings.data_dir == Path("/real")
    assert settings.public_url == "https://a"
    assert "from-file" not in repr(settings)


def telegram(handler) -> tuple[TelegramClient, list[float]]:
    slept: list[float] = []
    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return TelegramClient(TOKEN, client=client, sleep=slept.append), slept


def test_telegram_sends_plain_text_with_an_inline_keyboard() -> None:
    seen: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return httpx2.Response(200, json={"ok": True, "result": {"message_id": 9}})

    bot, _ = telegram(handler)
    result = bot.send_message(1, "Hi", ((Button("Yes", "ob:confirm:ok"),),))
    assert result == {"message_id": 9}
    assert seen == [{"chat_id": 1, "text": "Hi", "reply_markup": {
        "inline_keyboard": [[{"text": "Yes", "callback_data": "ob:confirm:ok"}]]}}]  # fmt: skip


def test_telegram_retries_once_after_429() -> None:
    replies = iter([
        httpx2.Response(429, json={"ok": False, "error_code": 429, "description": "Too Many",
                                   "parameters": {"retry_after": 99}}),
        httpx2.Response(200, json={"ok": True, "result": True}),
    ])  # fmt: skip
    bot, slept = telegram(lambda request: next(replies))
    bot.answer_callback("cb1")
    assert slept == [30.0], "retry_after is honoured, capped at 30s"


def test_telegram_errors_never_carry_the_token() -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(f"cannot reach {request.url}", request=request)

    bot, _ = telegram(refuse)
    with pytest.raises(TelegramError) as caught:
        bot.delete_webhook()
    assert TOKEN not in str(caught.value) and TOKEN not in repr(bot)

    bot, _ = telegram(lambda r: httpx2.Response(400, json={"ok": False, "description": "Bad"}))
    with pytest.raises(TelegramError, match="sendMessage: Bad") as caught:
        bot.send_message(1, "x")
    assert TOKEN not in str(caught.value)


def test_poll_skips_a_bad_update_and_advances_the_offset(store: Store) -> None:
    from networth.bot.poll import poll_once

    class OneBatch(FakeBot):
        def get_updates(self, offset: int | None, timeout_s: int) -> list[dict]:
            return [{"update_id": 10, "message": {"chat": {"id": "not-a-number"}, "text": "x"}},
                    {**text_update("/start"), "update_id": 11}]  # fmt: skip

    bot = OneBatch()
    assert poll_once(store, bot, None) == 12
    assert bot.texts and bot.texts[0].startswith("Hi.")
