"""Talk.DASHBOARD: "my dashboard", "mera dashboard", "open my page" and /dashboard get one button
to the user's own signed page.

    if asks(text, is_forward): answer = dashboard(profile, services, now, lang)
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Final

from networth.app.services import Services
from networth.app.store import Profile
from networth.bot.message import say
from networth.bot.onboarding import brief_now_buttons
from networth.bot.telegram import Button
from networth.brief import BUTTONS
from networth.chat.answer import Answer
from networth.chat.talk import SHORT_CHARS, Talk

RULE: Final = re.compile(
    r"\b(?:my|mera|meri) (?:dashboard|page)\b|\bopen (?:my )?(?:dashboard|page)\b"
    r"|\bdashboard (?:link|kholo|khol|dikhao)\b|मेरा डैशबोर्ड|मेरा पेज",
    re.IGNORECASE,
)
DASHBOARD_READY: Final = {
    "en": "Your dashboard has your plan, your latest brief and what history counted for it. The "
    "button below opens it.",
    "hi": "आपके डैशबोर्ड पर आपका प्लान, ताज़ा ब्रीफ़ और उसके लिए इतिहास की गिनती है। नीचे का बटन उसे खोलता है।",
    "hinglish": "Aapke dashboard par aapka plan, latest brief aur uske liye history ki ginti hai. "
    "Neeche ka button use kholta hai.",
}
DASHBOARD_ON_TELEGRAM: Final = {
    "en": "Your dashboard link comes from Telegram: /dashboard there sends it.",
    "hi": "आपके डैशबोर्ड का लिंक Telegram पर मिलता है: वहाँ /dashboard भेजने पर आ जाता है।",
    "hinglish": "Aapke dashboard ka link Telegram par milta hai: wahan /dashboard bhejne par aa "
    "jaata hai.",
}


def asks(text: str, is_forward: bool) -> bool:
    return not is_forward and len(text) <= SHORT_CHARS and bool(RULE.search(text))


def dashboard(profile: Profile, services: Services, now: dt.datetime, lang: str) -> Answer:
    """One button to the user's signed page; a line pointing at /dashboard where no page link
    can be built (the web chat has no signing secret)."""
    url = services.page_url(profile.link_token, now)
    if url is None:
        return Answer.fixed(DASHBOARD_ON_TELEGRAM, kind=Talk.DASHBOARD.value)
    button = Button(say(BUTTONS["page"], lang), "", url)
    buttons = ((button,), *brief_now_buttons(lang))
    return Answer.fixed(DASHBOARD_READY, kind=Talk.DASHBOARD.value, buttons=buttons)
