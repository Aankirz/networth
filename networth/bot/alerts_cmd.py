"""/alerts on and /alerts off: the one switch for every message Networth starts on its own
about news (rare alerts and the news notifier). Briefs and watches the user asked for stay."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from networth.app.store import Profile
from networth.bot.onboarding import Reply

OFF: Final = "News alerts are off. Type /alerts on to turn them back on."
ON: Final = ("News alerts are on: up to 3 a day, never between 10 pm and 8 am, only when a "
             "confirmed story touches what you own or follow.")  # fmt: skip
USAGE: Final = "Type /alerts off to stop news alerts, or /alerts on to turn them back on."
SWITCH: Final = {"off": False, "on": True}


def cmd_alerts(turn, profile: Profile, args: str) -> None:  # noqa: ANN001 - commands.Turn
    on = SWITCH.get(args.strip().lower())
    if on is None:
        turn.send(profile, Reply(USAGE))
        return
    profile = turn.save(replace(profile, alerts_on=on))
    turn.send(profile, Reply(ON if on else OFF))
