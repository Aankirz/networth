"""The one way a message leaves the bot.

    send(store, bot, profile, reply, proactive=True)

It sends nothing to a stopped user, and nothing proactive (briefs, alerts) to a paused one.
Every sent text is logged as an outgoing message.
"""

from __future__ import annotations

from networth.app.store import Profile, Status, Store
from networth.bot.onboarding import Reply
from networth.bot.telegram import Bot


def send(
    store: Store, bot: Bot, profile: Profile, reply: Reply, *, proactive: bool = False
) -> bool:
    """False, and nothing sent, when the user said no."""
    if profile.status is Status.STOPPED or (proactive and profile.status is Status.PAUSED):
        return False
    bot.send_message(profile.chat_id, reply.text, reply.buttons)
    store.log_message(profile.user_id, "out", reply.text)
    return True
