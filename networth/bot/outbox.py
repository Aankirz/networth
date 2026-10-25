"""The one way a message leaves the bot.

    send(store, bot, profile, reply, proactive=True, mail=services.mail)

It sends nothing to a stopped user, and nothing proactive (briefs, alerts, watches) to a paused
one. A proactive message for a user who chose email is queued for Keiki instead of sent on the
bot; replies always go back on the bot that carried the question (Telegram, or a Keiki turn).
Every sent text is logged as an outgoing message.
"""

from __future__ import annotations

from networth.app.store import Channel, Profile, Status, Store
from networth.bot.onboarding import Reply
from networth.bot.telegram import Bot
from networth.keiki.mail import Mail


def send(
    store: Store, bot: Bot, profile: Profile, reply: Reply, *, proactive: bool = False,
    mail: Mail | None = None,
) -> bool:  # fmt: skip
    """False, and nothing sent, when the user said no or their email cannot be reached."""
    if profile.status is Status.STOPPED or (proactive and profile.status is Status.PAUSED):
        return False
    if proactive and profile.deliver_to == Channel.EMAIL:
        if mail is None or not mail.queue(profile, reply):
            return False
    else:
        bot.send_message(profile.chat_id, reply.text, reply.buttons)
    store.log_message(profile.user_id, "out", reply.text)
    return True
