"""/sectors: today's moves of the main NSE sectors, each with the confirmed stories behind it.

    COMMANDS["/sectors"] = cmd_sectors

Prices and stories are read after the update lock, like /range. A sector whose prices can't be
read is named as having no data; nothing is filled in. The board has no amounts, so no money
is written; the moves are percentages of the index.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from typing import Final

from networth.app.services import Services
from networth.app.store import Profile
from networth.bot.onboarding import Reply
from networth.ratings.sources import LiveSources, Sources
from networth.sectors import board, board_message

log = logging.getLogger("networth.bot")

TRY_AGAIN: Final = "I couldn't read the sector prices just now. Try /sectors again in a minute."


def live_sources(services: Services) -> Sources:
    return LiveSources(services.watcher_db)


SOURCES: Callable[[Services], Sources] = live_sources  # tests swap in fakes


def sectors_reply(services: Services, now: dt.datetime) -> Reply:
    # ponytail: no link to /r/sectors until that page ships
    return Reply(board_message(board(SOURCES(services), now)))


def cmd_sectors(turn, profile: Profile, args: str) -> None:  # noqa: ANN001 - commands.Turn
    def job() -> None:
        try:
            reply = sectors_reply(turn.services, turn.clock)
        except Exception as exc:  # noqa: BLE001 - the user still hears something went wrong
            log.warning("sectors for %s failed: %s", profile.user_id, type(exc).__name__)
            reply = Reply(TRY_AGAIN)
        turn.send(profile, reply)

    turn.later.append(job)
