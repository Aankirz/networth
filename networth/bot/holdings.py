"""Holdings on Telegram: a screenshot in, a list to check, then the factual report.

    reply = photo_reply(store, profile, image, services)    # the confirm prompt, or Explain this
    reply = tapped(store, profile, "hd:ok", services, now)   # Looks right, Fix a line, Cancel
    reply = typed_fix(store, profile, "2 units 15")          # None when it isn't a fix
    reply = report_reply(store, profile, services, now)      # /holdings

The flow keeps no state of its own. What is pending is the stored list itself: none stored is
nothing pending, an unconfirmed list waits for a confirm, a fix or a cancel, and only a
confirmed list gives a report. The image is a local here and is never logged or written.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Callable
from typing import Final

from networth import chat, holdings
from networth.app.services import Services
from networth.app.store import Profile, Store
from networth.bot.message import FOOTER, Message, say
from networth.bot.onboarding import Reply
from networth.bot.telegram import Button
from networth.chat.answer import Answer
from networth.holdings import lines as hl
from networth.holdings.lines import holdings_lines, lang_of, unit_money, units
from networth.holdings.model import BUCKETS, Holdings, from_json

log = logging.getLogger("networth.bot")

TAP_PREFIX: Final = "hd"
TITLE: Final = {"en": "Here is what I read.", "hi": "मैंने यह पढ़ा।", "hinglish": "Maine yeh padha."}
ROW: Final = {
    "en": "{n}. {name}: {units} units, average cost {cost}",
    "hi": "{n}. {name}: {units} यूनिट, औसत लागत {cost}",
    "hinglish": "{n}. {name}: {units} units, average cost {cost}",
}
NOT_READ: Final = {"en": "Not read: {what}.", "hi": "नहीं पढ़ पाया: {what}।",
                   "hinglish": "Padh nahin paaya: {what}."}  # fmt: skip
WHICH_BUCKET: Final = {
    "en": "Is line {n} safety, core or growth? Reply like: {n} growth",
    "hi": "लाइन {n} सेफ़्टी, कोर या ग्रोथ में है? जवाब ऐसे दे सकते हैं: {n} growth",
    "hinglish": "Line {n} safety, core ya growth mein hai? Jawab aise de sakte hain: {n} growth",
}
HOW_TO_FIX: Final = {
    "en": "To fix a line, type its number and the change: 2 units 15, 2 cost 450, 2 growth or "
    "2 drop.",
    "hi": "कोई लाइन ठीक करने के लिए उसका नंबर और बदलाव लिख सकते हैं: 2 units 15, 2 cost 450, "
    "2 growth या 2 drop।",
    "hinglish": "Koi line theek karne ke liye uska number aur badlav likh sakte hain: 2 units 15, "
    "2 cost 450, 2 growth ya 2 drop.",
}
LOOKS_RIGHT: Final = {"en": "Looks right", "hi": "सही है", "hinglish": "Sahi hai"}
FIX_A_LINE: Final = {"en": "Fix a line", "hi": "एक लाइन ठीक करनी है",
                     "hinglish": "Ek line theek karni hai"}  # fmt: skip
CANCEL: Final = {"en": "Cancel", "hi": "रद्द", "hinglish": "Cancel"}
CANCELLED: Final = {"en": "Cancelled, nothing saved.", "hi": "रद्द कर दिया, कुछ सेव नहीं हुआ।",
                    "hinglish": "Cancel kar diya, kuch save nahin hua."}  # fmt: skip
NO_HOLDINGS: Final = {
    "en": "Send me a screenshot of your holdings and I'll read it.",
    "hi": "अपनी होल्डिंग्स का स्क्रीनशॉट भेजने पर मैं उसे पढ़ लूँगा।",
    "hinglish": "Apni holdings ka screenshot bhejne par main use padh loonga.",
}
PAGE_BUTTON: Final = {"en": "My holdings page", "hi": "मेरी होल्डिंग्स का पेज",
                      "hinglish": "Meri holdings ka page"}  # fmt: skip
US_ONLY: Final = {
    "en": "Linking a broker works for US accounts only for now. A screenshot of your holdings "
    "works here.",
    "hi": "ब्रोकर लिंक करना अभी सिर्फ़ US खातों के लिए है। यहाँ आपकी होल्डिंग्स का स्क्रीनशॉट काम करता है।",
    "hinglish": "Broker link karna abhi sirf US accounts ke liye hai. Yahan aapki holdings ka "
    "screenshot kaam karta hai.",
}
NOT_YET: Final = {
    "en": "Broker linking isn't available yet. A screenshot of your holdings works for now.",
    "hi": "ब्रोकर लिंक करना अभी उपलब्ध नहीं है। अभी के लिए आपकी होल्डिंग्स का स्क्रीनशॉट काम करता है।",
    "hinglish": "Broker linking abhi available nahin hai. Abhi ke liye aapki holdings ka "
    "screenshot kaam karta hai.",
}
LINK_LEAD: Final = {
    "en": "This opens SnapTrade with read-only access, so it can read your holdings and never "
    "place a trade.",
    "hi": "इससे SnapTrade सिर्फ़ पढ़ने की पहुँच के साथ खुलता है, यानी यह आपकी होल्डिंग्स पढ़ सकता है "
    "और कभी कोई ट्रेड नहीं कर सकता।",
    "hinglish": "Isse SnapTrade sirf read-only access ke saath khulta hai, yaani yeh aapki "
    "holdings padh sakta hai aur kabhi koi trade nahin kar sakta.",
}
LINK_BUTTON: Final = {"en": "Link my broker (read-only)",
                      "hi": "मेरा ब्रोकर लिंक करना (सिर्फ़ पढ़ने के लिए)",
                      "hinglish": "Mera broker link karna (read-only)"}  # fmt: skip
SENTENCE_END: Final = re.compile(r"(?<=[.।])\s+")
USD: Final = "USD"


def _pending(store: Store, profile: Profile) -> Holdings | None:
    """The stored list while it waits for the user's confirm, else None."""
    data = store.holdings_data(profile.user_id)
    h = from_json(data) if data else None
    return h if h is not None and not h.confirmed else None


def _row(n: int, h: Holdings, lang: str) -> str:
    x = h.items[n - 1]
    row = say(ROW, lang).format(n=n, name=x.name, units=units(x.units),
                                cost=unit_money(x.avg_cost, x.currency))  # fmt: skip
    return f"{row} ({hl.LINES[lang_of(lang)][x.bucket.value]})" if x.bucket else row


def confirm_reply(h: Holdings, lang: str | None) -> Reply:
    """The list as read, the lines still needing a bucket, and how to fix one. A question, so
    no footer."""
    rows = "\n".join(_row(n, h, lang or "en") for n in range(1, len(h.items) + 1))
    not_read = (say(NOT_READ, lang).format(what="; ".join(h.unread)),) if h.unread else ()
    ask = "\n".join(say(WHICH_BUCKET, lang).format(n=n) for n in h.unplaced)
    body = tuple(b for b in (rows, *not_read, ask, say(HOW_TO_FIX, lang)) if b)
    buttons = ((Button(say(LOOKS_RIGHT, lang), f"{TAP_PREFIX}:ok"),
                Button(say(FIX_A_LINE, lang), f"{TAP_PREFIX}:fix"),
                Button(say(CANCEL, lang), f"{TAP_PREFIX}:cancel")),)  # fmt: skip
    return Reply(Message(say(TITLE, lang), body), buttons)


def photo_reply(store: Store, profile: Profile, image: bytes, services: Services) -> Reply:
    """The confirm prompt when the reader found holdings; otherwise Explain this, with any
    earlier list left as it was."""
    if services.models is None:
        return chat.respond_image(profile, image, services)
    before = store.holdings_data(profile.user_id)
    prompt = holdings.holdings_from_photo(profile.user_id, image, store, reader=services.models,
                                          prices=services.prices)  # fmt: skip
    if prompt.holdings.items:
        return confirm_reply(prompt.holdings, profile.lang)
    if before is None:
        store.delete_holdings(profile.user_id)
    else:
        store.save_holdings(profile.user_id, before)
    return chat.respond_image(profile, image, services)


def typed_fix(store: Store, profile: Profile, text: str) -> Reply | None:
    """A typed "2 units 15" while a list waits for its confirm; None for anything else."""
    if _pending(store, profile) is None:
        return None
    prompt = holdings.fix_line(profile.user_id, store, text)
    return confirm_reply(prompt.holdings, profile.lang) if prompt else None


def _without_label_phrase(text: str, lang: str) -> str:
    """The text without the holdings label's closing "Research, not advice" sentence, so the
    footer carries it once."""
    phrase = SENTENCE_END.split(hl.LINES[lang]["label"])[-1]
    return text.strip().removesuffix(phrase).rstrip()


def report_message(lines: list[str], rows: int, lang: str) -> Message:
    """holdings_lines as the 3E shape: the head as title; rows, total, mix and label as body;
    history and prices in the detail."""
    total, mix_end = 1 + rows, 1 + rows + 2 + len(BUCKETS)
    body = ("\n".join(lines[1:total]), lines[total], "\n".join(lines[total + 1 : mix_end]),
            _without_label_phrase(lines[-1], lang))  # fmt: skip
    return Message(lines[0], body, tuple(lines[mix_end:-1]), say(FOOTER, lang))


def report_reply(store: Store, profile: Profile, services: Services, now: dt.datetime) -> Reply:
    lang = lang_of(profile.lang)
    report = holdings.report_for(profile.user_id, store, prices=services.prices)
    if report is None:
        return Reply(say(NO_HOLDINGS, lang))
    message = report_message(holdings_lines(report, lang), len(report.rows), lang)
    page = services.page_url(profile.link_token, now)
    # The site has one page per user; only this server's /u page has a /holdings subpage.
    url = page if services.site_url else f"{page}/holdings"
    buttons = ((Button(say(PAGE_BUTTON, lang), "", url),),) if page else ()
    return Reply(message, buttons)


def _looks_right(store: Store, profile: Profile, h: Holdings, services: Services,
                 now: dt.datetime) -> Reply:  # fmt: skip
    if h.unplaced:
        return confirm_reply(h, profile.lang)
    holdings.confirm_holdings(profile.user_id, store)
    return report_reply(store, profile, services, now)


def _cancel(store: Store, profile: Profile, h: Holdings, services: Services,
            now: dt.datetime) -> Reply:  # fmt: skip
    store.delete_holdings(profile.user_id)
    return Reply(say(CANCELLED, profile.lang))


TapAction = Callable[[Store, Profile, Holdings, Services, dt.datetime], Reply]
TAP_ACTIONS: Final[dict[str, TapAction]] = {
    f"{TAP_PREFIX}:ok": _looks_right,
    f"{TAP_PREFIX}:fix": lambda store, profile, h, s, now: Reply(say(HOW_TO_FIX, profile.lang)),
    f"{TAP_PREFIX}:cancel": _cancel,
}


def tapped(store: Store, profile: Profile, data: str, services: Services,
           now: dt.datetime) -> Reply:  # fmt: skip
    h, action = _pending(store, profile), TAP_ACTIONS.get(data)
    if h is None or action is None:
        return Reply(say(NO_HOLDINGS, profile.lang))
    return action(store, profile, h, services, now)


def chat_answer(store: Store, profile: Profile, text: str, services: Services,
                lang: str) -> Answer:  # fmt: skip
    """A holdings question in chat: the guarded answer, or with no models the decline and the
    report. Fixed words, so deliver adds the footer once."""
    chosen = lang_of(lang)
    report = holdings.report_for(profile.user_id, store)
    if report is None:
        return Answer.fixed(NO_HOLDINGS, footer=False)
    if services.models is None:
        words = "\n".join([hl.LINES[chosen]["decline"], *holdings_lines(report, chosen)])
    else:
        words = holdings.holdings_answer(profile.user_id, text, store, services.models,
                                         log_path=services.guard_log, lang=chosen)  # fmt: skip
    words = _without_label_phrase(words, chosen)
    return Answer.fixed({"en": words, chosen: words})


def link_broker_reply(store: Store, profile: Profile, services: Services) -> Reply:
    """A read-only SnapTrade link for a US account; a kind line otherwise."""
    lang = profile.lang
    if profile.currency != USD:
        return Reply(say(US_ONLY, lang))
    url = holdings.snaptrade_link(profile.user_id, store, client=services.snaptrade)
    if url is None:
        return Reply(say(NOT_YET, lang))
    return Reply(say(LINK_LEAD, lang), ((Button(say(LINK_BUTTON, lang), "", url),),))
