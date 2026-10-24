"""The one Networth server: health check, Telegram webhook, and the web pages when present.

    uv run uvicorn networth.app.main:app --port 8080

The webhook trusts a request only when its X-Telegram-Bot-Api-Secret-Token header matches the
secret we gave setWebhook. A handled update always answers 200, even when handling failed,
because Telegram redelivers anything else until it gets one. The web pages (networth.web) are
another builder's; the server runs with or without them.
"""

from __future__ import annotations

import hmac
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from networth.app.settings import Settings
from networth.app.store import Store
from networth.bot.commands import handle_update
from networth.bot.telegram import Bot, TelegramClient

log = logging.getLogger("networth.app")

SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"
WEBHOOK_PATH = "/telegram/webhook"
OK = {"ok": True}


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
    store: Store | None, bot: Bot | None, secret: str | None, public_url: str | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if public_url and bot is not None and secret:
            try:
                await run_in_threadpool(bot.set_webhook, f"{public_url}{WEBHOOK_PATH}", secret)
                log.info("webhook set to %s%s", public_url, WEBHOOK_PATH)
            except Exception as exc:
                log.warning("setWebhook failed, continuing: %s", exc)
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
            await run_in_threadpool(handle_update, update, store, bot)
        except Exception:
            log.exception("update %s failed", update.get("update_id"))
        return JSONResponse(OK)

    mount_web(app)
    return app


def app_from_env(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    bot = TelegramClient(settings.bot_token) if settings.bot_token else None
    if bot is None:
        log.warning("TELEGRAM_BOT_TOKEN not set; the webhook will answer 503")
    store = Store(settings.data_dir)
    return create_app(store, bot, settings.webhook_secret, settings.public_url)


app = app_from_env()
