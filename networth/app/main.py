"""The one Networth server: health check, Telegram webhook, Keiki turns, and the web pages.

    uv run uvicorn networth.app.main:app --port 8080

The webhook trusts a request only when its X-Telegram-Bot-Api-Secret-Token header matches the
secret we gave setWebhook. A handled update always answers 200, even when handling failed,
because Telegram redelivers anything else until it gets one. The web pages (networth.web) are
another builder's; the server runs with or without them.

/keiki/turn trusts a push only when its signature verifies (networth.keiki.verify) and it names
our agent. A new turn id is claimed, answered 202 at once and run in the background; a replay
of a claimed id answers 200 and runs nothing, so a turn is never answered twice.
"""

from __future__ import annotations

import functools
import hmac
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from networth.app import schedule
from networth.app.services import Services
from networth.app.settings import Settings
from networth.app.store import Store, now_iso
from networth.bot.commands import COMMAND_LIST, handle_update
from networth.bot.telegram import Bot, MenuBot, TelegramClient
from networth.keiki import wire
from networth.keiki.turn import Harness, run_turn
from networth.keiki.verify import TOKEN_HEADER, Keys, verify

log = logging.getLogger("networth.app")

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
WEBHOOK_PATH = "/telegram/webhook"
KEIKI_PATH = "/keiki/turn"
OK = {"ok": True}
DATA_DIR_MODE = 0o700


def mount_web(app: FastAPI) -> None:
    try:
        from networth.web.routes import router
    except ImportError:
        log.info("networth.web not available; serving without web pages")
        return
    except Exception:
        log.exception("networth.web failed to import; serving without web pages")
        return
    app.include_router(router)


def create_app(
    store: Store | None, bot: Bot | None, secret: str | None, public_url: str | None = None,
    services: Services | None = None, keiki: Harness | None = None,
) -> FastAPI:  # fmt: skip
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if public_url and bot is not None and secret:
            try:
                await run_in_threadpool(bot.set_webhook, f"{public_url}{WEBHOOK_PATH}", secret)
                log.info("webhook set to %s%s", public_url, WEBHOOK_PATH)
            except Exception as exc:
                log.warning("setWebhook failed, continuing: %s", exc)
        if isinstance(bot, MenuBot):
            try:
                await run_in_threadpool(bot.set_my_commands, COMMAND_LIST)
            except Exception as exc:
                log.warning("setMyCommands failed, continuing: %s", exc)
        yield

    app = FastAPI(title="Networth", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        return OK

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(request: Request) -> JSONResponse:
        if not secret or store is None or bot is None:
            return JSONResponse({"ok": False, "error": "webhook not configured"}, status_code=503)
        given = request.headers.get(SECRET_HEADER, "")
        if not hmac.compare_digest(given.encode(), secret.encode()):
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
        try:
            update = json.loads(await request.body())
        except ValueError:
            return JSONResponse({"ok": False, "error": "bad json"}, status_code=400)
        if not isinstance(update, dict):
            return JSONResponse({"ok": False, "error": "bad update"}, status_code=400)
        try:
            await run_in_threadpool(handle_update, update, store, bot, None, services)
        except Exception:
            log.exception("update %s failed", update.get("update_id"))
        return JSONResponse(OK)

    @app.post(KEIKI_PATH)
    async def keiki_turn(request: Request) -> JSONResponse:
        if keiki is None or store is None:
            return JSONResponse({"ok": False, "error": "keiki not configured"}, status_code=503)
        raw = await request.body()
        reason = await run_in_threadpool(verify, request.headers, raw, time.time(), keiki.keys,
                                         keiki.hmac_secret)  # fmt: skip
        if reason is not None:
            return JSONResponse({"error": reason}, status_code=401)
        try:
            event = wire.parse(json.loads(raw))
        except ValueError:
            event = None
        if event is None:
            return JSONResponse({"error": "bad payload"}, status_code=400)
        if event.agent_id != keiki.agent_id:
            return JSONResponse({"error": "unknown_agent"}, status_code=401)
        if not isinstance(event, wire.KeikiTurn):
            return JSONResponse(OK, status_code=202)
        if not store.claim_turn(event.turn_id):
            return JSONResponse({"ok": True, "duplicate": True})
        client = keiki.client(event.turn_url, request.headers.get(TOKEN_HEADER, ""))
        turn_services = services or Services(store.path.parent)
        keiki.start(functools.partial(run_turn, event, store, turn_services, client, now_iso()))
        return JSONResponse(OK, status_code=202)

    @app.get("/schedules")
    def schedules() -> list[dict]:
        return schedule.schedules()

    @app.post("/chat")
    async def chat(request: Request) -> JSONResponse:
        """Maritime's scheduled prompts. Anything else is pointed at Telegram."""
        try:
            body = json.loads(await request.body())
        except ValueError:
            body = {}
        body = body if isinstance(body, dict) else {}
        prompt = next((str(body[k]) for k in ("prompt", "message", "text") if body.get(k)), "")
        if body.get("source") != "scheduled" or store is None or bot is None:
            return JSONResponse({"response": schedule.CHAT_REPLY})
        if prompt.strip() not in (schedule.WATCHER_PROMPT, schedule.BRIEF_PROMPT):
            return JSONResponse({"response": f"unknown job {prompt[:40]!r}"})
        schedule.start_job(prompt.strip(), store, bot, services or Services(store.path.parent))
        return JSONResponse({"response": f"started {prompt.strip()}"})

    mount_web(app)
    return app


def secure_data_dir(path: Path) -> None:
    """Only the server's own user may read the data dir: it holds every profile, message,
    holding and broker secret."""
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(DATA_DIR_MODE)


def app_from_env(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    secure_data_dir(settings.data_dir)
    bot = TelegramClient(settings.bot_token) if settings.bot_token else None
    if bot is None:
        log.warning("TELEGRAM_BOT_TOKEN not set; the webhook will answer 503")
    store = Store(settings.data_dir)
    services = Services.from_settings(settings)
    keiki = None
    if settings.keiki_agent_id:
        keiki = Harness(settings.keiki_agent_id, Keys(), settings.keiki_signing_secret)
    else:
        log.warning("KEIKI_AGENT_ID not set; /keiki/turn will answer 503")
    return create_app(store, bot, settings.webhook_secret, settings.public_url, services, keiki)


app = app_from_env()
