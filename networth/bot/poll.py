"""python -m networth.bot.poll: run the bot locally by long polling instead of the webhook.

Telegram delivers updates one way at a time, so this removes any webhook first. Production
sets it again on the next server start. One bad update or a dropped connection is logged and
skipped; only Ctrl-C ends the loop.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Final

from networth.app.settings import Settings
from networth.app.store import Store
from networth.bot.commands import handle_update
from networth.bot.telegram import Bot, TelegramClient

LONG_POLL_S: Final = 25
BACKOFF_S: Final = 2.0

log = logging.getLogger("networth.bot.poll")


def poll_once(store: Store, bot: Bot, offset: int | None) -> int | None:
    """Handle one batch of updates and return the next offset."""
    for update in bot.get_updates(offset, LONG_POLL_S):
        offset = int(update["update_id"]) + 1
        try:
            handle_update(update, store, bot)
        except Exception:
            log.exception("update %s failed", update.get("update_id"))
    return offset


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = Settings.from_env()
    if not settings.bot_token:
        print("TELEGRAM_BOT_TOKEN is not set (env or .env).", file=sys.stderr)
        return 2
    store = Store(settings.data_dir)
    bot = TelegramClient(settings.bot_token)
    bot.delete_webhook()
    print(f"Webhook removed. Polling Telegram, data in {store.path}. Ctrl-C to stop.")
    offset: int | None = None
    try:
        while True:
            try:
                offset = poll_once(store, bot, offset)
            except Exception as exc:
                log.warning("polling failed, retrying in %gs: %s", BACKOFF_S, exc)
                time.sleep(BACKOFF_S)
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
