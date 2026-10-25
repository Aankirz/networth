"""A Telegram reply turned into plain email text.

    text = plain(reply.text, reply.buttons)

Email has no buttons. A link button becomes a "Label: url" line. Onboarding's answer buttons
become one "Reply with one of: a, b, c" line, because their labels are what the onboarding
parse reads when typed. Every other callback button (brief taps, watch Stop buttons) is
dropped: the message text already says the typed way to do the same thing.
"""

from __future__ import annotations

from typing import Final

from networth.bot.onboarding import CALLBACK_PREFIX
from networth.bot.telegram import Keyboard

ANSWER_PREFIX: Final = f"{CALLBACK_PREFIX}:"


def plain(text: str, buttons: Keyboard = ()) -> str:
    flat = [b for row in buttons for b in row]
    links = [f"{b.label}: {b.url}" for b in flat if b.url]
    answers = [b.label for b in flat if not b.url and b.data.startswith(ANSWER_PREFIX)]
    extra = links + ([f"Reply with one of: {', '.join(answers)}"] if answers else [])
    return "\n\n".join([text, "\n".join(extra)]) if extra else text
