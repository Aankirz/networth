"""Holdings on Telegram: a screenshot in, the answer first, then the list checked in plain words.

    reply = photo_reply(store, profile, image, services)    # worth today, up or down, each share
    reply = tapped(store, profile, "hd:ok", services, now)   # That's everything, Send more, ...
    reply = typed_fix(store, profile, "15 shares")           # None when it isn't a fix
    reply = report_reply(store, profile, services, now)      # /holdings

The flow keeps no state of its own. What is pending is the stored list itself: none stored is
nothing pending, an unconfirmed list waits for more screenshots, a fix or "That's everything",
and the line being fixed is saved on it. Only a confirmed list is compared with the plan. The
image is a local here and is never logged or written. Every reply goes through the guard.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Final

from networth import chat, guard, holdings
from networth.app.services import Services
from networth.app.store import Profile, Store
from networth.bot import holdings_plan, message
from networth.bot.holdings_words import (
    ADDED,
    ALL_SHARES,
    BOTH_SHARES,
    CHANGED,
    DOWN,
    EVEN,
    EVERYTHING,
    GOT_IT,
    GOT_ONE,
    KIND_BUTTONS,
    NO_PRICE,
    NOT_CAUGHT,
    ONE_SHARE,
    PUT_IN,
    REMOVE_BUTTON,
    REMOVED,
    ROW,
    ROW_FIRST,
    ROW_NO_PRICE,
    SAVED,
    SEE_CUT,
    SEE_OF,
    SEND_MORE,
    SEND_NEXT,
    SOME_SHARES,
    START_OVER,
    STARTED_OVER,
    THATS_ALL,
    TOP,
    UNDER_ONE,
    UP,
    WHAT_KIND,
    WHAT_SHOULD,
    WHICH,
    WRONG,
)
from networth.bot.message import Message, say
from networth.bot.onboarding import Reply
from networth.bot.telegram import Button, Keyboard
from networth.chat.answer import Answer
from networth.holdings import lines as hl
from networth.holdings.lines import holdings_lines, lang_of
from networth.holdings.model import BUCKETS, Bucket, Holdings
from networth.holdings.summary import Summary, short_money, summarize

log = logging.getLogger("networth.bot")

TAP_PREFIX: Final = "hd"
NOT_READ: Final = {"en": "Not read: {what}.", "hi": "नहीं पढ़ पाया: {what}।",
                   "hinglish": "Padh nahin paaya: {what}."}  # fmt: skip
MOST: Final = 50  # a holding at least this share of the money gets its own line
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
USD: Final = "USD"


def _say(table: dict, lang: str, **values: object) -> str:
    return say(table, lang).format(**values)


def _guarded(reply: Reply, services: Services | None) -> Reply:
    """Fixed words, so the guard checks the wording; a failure is logged, never sent silently."""
    text = message.plain(reply.message) if isinstance(reply.message, Message) else reply.message
    verdict = guard.check(text, text)
    if services is not None:
        guard.log_verdict(services.guard_log, "holdings", "template", verdict)
    if not verdict.ok:
        log.warning("holdings reply failed the guard: %s", verdict.problems)
    return reply


def _pending(store: Store, profile: Profile) -> Holdings | None:
    return holdings.pending(profile.user_id, store)


def _title(s: Summary, lang: str) -> str:
    value = short_money(s.value, s.currency, lang)
    if s.count == 1:
        return _say(GOT_ONE, lang, value=value)
    return _say(GOT_IT, lang, count=s.count, value=value)


def _gain(s: Summary, lang: str) -> str:
    invested = short_money(s.invested, s.currency, lang)
    if s.gain is None:
        names = ", ".join(i.name for i in s.items if i.value is None)
        return "\n".join((_say(PUT_IN, lang, invested=invested), _say(NO_PRICE, lang, names=names)))
    if not s.gain_pct:
        return _say(EVEN, lang, invested=invested)
    words = UP if s.gain > 0 else DOWN
    return _say(words, lang, invested=invested, gain=short_money(s.gain, s.currency, lang),
                pct=abs(s.gain_pct))  # fmt: skip


def _rows(s: Summary, lang: str) -> str:
    rows = []
    for i, x in enumerate(s.items):
        if x.value is None:
            rows.append(_say(ROW_NO_PRICE, lang, name=x.name))
            continue
        share = say(UNDER_ONE, lang) if x.share == 0 else f"{x.share}%"
        rows.append(_say(ROW_FIRST if i == 0 else ROW, lang, name=x.name,
                         value=short_money(x.value, s.currency, lang), share=share))  # fmt: skip
    return "\n".join(rows)


def _takeaway(s: Summary, lang: str) -> str:
    if s.shares == s.count:
        kinds = {1: say(ONE_SHARE, lang), 2: say(BOTH_SHARES, lang)}.get(
            s.count, _say(ALL_SHARES, lang, count=s.count)
        )
    else:
        kinds = _say(SOME_SHARES, lang, shares=s.shares, count=s.count) if s.shares else ""
    top = s.items[0]
    big = s.count > 1 and top.share is not None and top.share >= MOST
    alone = _say(TOP, lang, name=top.name, share=top.share) if big else ""
    return " ".join(w for w in (kinds, alone) if w)


def _ask(s: Summary, lang: str) -> str:
    if s.listed > s.count:
        return _say(SEE_OF, lang, count=s.count, listed=s.listed)
    if s.more_below:
        return _say(SEE_CUT, lang, count=s.count)
    return say(EVERYTHING, lang)


def _buttons(lang: str) -> Keyboard:
    return ((Button(say(THATS_ALL, lang), f"{TAP_PREFIX}:ok"),
             Button(say(SEND_MORE, lang), f"{TAP_PREFIX}:more")),
            (Button(say(WRONG, lang), f"{TAP_PREFIX}:fix"),))  # fmt: skip


def summary_reply(h: Holdings, lang: str | None, lead: str = "") -> Reply:
    """The answer first: what it's worth, what went in, each holding's share, one takeaway,
    then whether this is everything. A question, so no footer."""
    lang, s = lang or "en", summarize(h)
    unread = _say(NOT_READ, lang, what="; ".join(h.unread)) if h.unread else ""
    body = (lead, _gain(s, lang), _rows(s, lang), _takeaway(s, lang), unread, _ask(s, lang))
    return Reply(Message(_title(s, lang), tuple(b for b in body if b)), _buttons(lang))


def photo_reply(store: Store, profile: Profile, image: bytes, services: Services) -> Reply:
    """The summary when the reader found holdings, added to any list still waiting; otherwise
    Explain this, with what was stored left as it was."""
    if services.models is None:
        return chat.respond_image(profile, image, services)
    read = holdings.holdings_from_photo(profile.user_id, image, store, reader=services.models,
                                        prices=services.prices)  # fmt: skip
    if not read.added and not read.same:
        return chat.respond_image(profile, image, services)
    lead = (
        _say(ADDED, profile.lang, added=read.added, same=read.same)
        if read.added and read.same
        else ""
    )
    return _guarded(summary_reply(read.holdings, profile.lang, lead), services)


def _changed(before: Holdings, after: Holdings, lang: str | None) -> str:
    gone = {x.name for x in before.items} - {x.name for x in after.items}
    if gone:
        return _say(REMOVED, lang, name=", ".join(sorted(gone)))
    n = before.fixing
    return _say(CHANGED, lang, name=before.items[n - 1].name) if n else ""


def typed_fix(store: Store, profile: Profile, text: str,
              services: Services | None = None) -> Reply | None:  # fmt: skip
    """Plain words for the line being fixed ("15 shares", "remove it"), or the old "2 units 15"
    syntax as a fallback. None when no list waits or the words aren't a fix."""
    before = _pending(store, profile)
    if before is None:
        return None
    after = holdings.correct(profile.user_id, store, text)
    if after is None and before.fixing:
        after = holdings.fix_line(profile.user_id, store, text)
        if after is None:
            return _guarded(Reply(say(NOT_CAUGHT, profile.lang)), services)
    elif after is None:
        after = holdings.fix_line(profile.user_id, store, text)
    if after is None:
        return None
    lead = _changed(before, after, profile.lang)
    return _guarded(summary_reply(after, profile.lang, lead), services)


def _kind_buttons(n: int, verb: str, lang: str) -> Keyboard:
    return tuple((Button(say(KIND_BUTTONS[b], lang), f"{TAP_PREFIX}:{verb}:{n}:{b.value}"),)
                 for b in BUCKETS)  # fmt: skip


def _everything(store: Store, profile: Profile, h: Holdings, services: Services) -> Reply:
    """Ask the kind of the first line with none; once every line has one, confirm and compare."""
    if h.unplaced:
        n = h.unplaced[0]
        ask = _say(WHAT_KIND, profile.lang, name=h.items[n - 1].name)
        return Reply(ask, _kind_buttons(n, "place", profile.lang or "en"))
    holdings.confirm_holdings(profile.user_id, store)
    return holdings_plan.plan_reply(store, profile, services, "overview") or Reply(
        say(SAVED, profile.lang)
    )


def _which(h: Holdings, lang: str) -> Reply:
    rows = tuple((Button(x.name, f"{TAP_PREFIX}:pick:{n}"),)
                 for n, x in enumerate(h.items, start=1))  # fmt: skip
    return Reply(
        say(WHICH, lang), (*rows, (Button(say(START_OVER, lang), f"{TAP_PREFIX}:cancel"),))
    )


def _picked(store: Store, profile: Profile, n: int) -> Reply | None:
    h = holdings.start_fix(profile.user_id, store, n)
    if h is None:
        return None
    lang = profile.lang or "en"
    remove = (Button(say(REMOVE_BUTTON, lang), f"{TAP_PREFIX}:drop:{n}"),)
    ask = _say(WHAT_SHOULD, lang, name=h.items[n - 1].name)
    return Reply(ask, (*_kind_buttons(n, "kind", lang), remove))


def _line(arg: str) -> int:
    return int(arg) if arg.isdigit() else 0


def _bucket_of(arg: str) -> Bucket | None:
    return next((b for b in BUCKETS if b.value == arg), None)


def _pending_tap(store: Store, profile: Profile, h: Holdings, services: Services,
                 parts: list[str]) -> Reply | None:  # fmt: skip
    """A tap on the list still waiting; None for one it doesn't know."""
    lang, user = profile.lang, profile.user_id
    action, n = parts[0], _line(parts[1]) if len(parts) > 1 else 0
    bucket = _bucket_of(parts[2]) if len(parts) > 2 else None
    if action == "ok":
        return _everything(store, profile, h, services)
    if action == "more":
        return Reply(_say(SEND_NEXT, lang, count=len(h.items)))
    if action == "fix":
        return _which(h, lang or "en")
    if action == "pick":
        return _picked(store, profile, n)
    if action == "cancel":
        store.delete_holdings(user)
        return Reply(say(STARTED_OVER, lang))
    if action == "drop" and (after := holdings.fix_line(user, store, f"{n} drop")):
        return summary_reply(after, lang, _say(REMOVED, lang, name=h.items[n - 1].name))
    if bucket is not None and (after := holdings.place(user, store, n, bucket)):
        if action == "place":
            return _everything(store, profile, after, services)
        return summary_reply(after, lang, _say(CHANGED, lang, name=h.items[n - 1].name))
    return None


def tapped(store: Store, profile: Profile, data: str, services: Services,
           now: dt.datetime) -> Reply:  # fmt: skip
    parts = data.split(":")[1:]
    if parts and parts[0] in holdings_plan.ACTIONS:
        reply = holdings_plan.plan_reply(store, profile, services, parts[0])
        return _guarded(reply or Reply(say(NO_HOLDINGS, profile.lang)), services)
    h = _pending(store, profile)
    reply = _pending_tap(store, profile, h, services, parts) if h is not None and parts else None
    return _guarded(reply or Reply(say(NO_HOLDINGS, profile.lang)), services)


def report_message(lines: list[str], rows: int, lang: str) -> Message:
    """holdings_lines as the 3E shape: the head as title; rows, total, mix and label as body;
    history and prices in the detail."""
    total, mix_end = 1 + rows, 1 + rows + 2 + len(BUCKETS)
    body = ("\n".join(lines[1:total]), lines[total], "\n".join(lines[total + 1 : mix_end]),
            lines[-1])  # fmt: skip
    return Message(lines[0], body, tuple(lines[mix_end:-1]))


def report_reply(store: Store, profile: Profile, services: Services, now: dt.datetime) -> Reply:
    lang = lang_of(profile.lang)
    report = holdings.report_for(profile.user_id, store, prices=services.prices)
    if report is None:
        return Reply(say(NO_HOLDINGS, lang))
    message_ = report_message(holdings_lines(report, lang), len(report.rows), lang)
    page = services.page_url(profile.link_token, now)
    # The site has one page per user; only this server's /u page has a /holdings subpage.
    url = page if services.site_url else f"{page}/holdings"
    buttons = ((Button(say(PAGE_BUTTON, lang), "", url),),) if page else ()
    return _guarded(Reply(message_, buttons), services)


def chat_answer(store: Store, profile: Profile, text: str, services: Services,
                lang: str) -> Answer:  # fmt: skip
    """A holdings question in chat: the guarded answer, or with no models the decline and the
    report. A buy or sell question gets the view on each holding and the plan gap."""
    chosen = lang_of(lang)
    report = holdings.report_for(profile.user_id, store)
    if report is None:
        return Answer.fixed(NO_HOLDINGS, footer=False)
    if guard.BANNED.search(text) or guard.ADVICE.search(text):  # asks what to sell or buy
        viewed = holdings_plan.view_answer(store, profile, services, chosen)
        if viewed is not None:
            words, keys = viewed
            return Answer.fixed({"en": words, chosen: words}, buttons=keys)
        words = "\n".join(holdings_lines(report, chosen))
    elif services.models is None:
        words = "\n".join([hl.LINES[chosen]["decline"], *holdings_lines(report, chosen)])
    else:
        words = holdings.holdings_answer(profile.user_id, text, store, services.models,
                                         log_path=services.guard_log, lang=chosen)  # fmt: skip
    return Answer.fixed({"en": words.strip(), chosen: words.strip()}, footer=False)


def link_broker_reply(store: Store, profile: Profile, services: Services) -> Reply:
    """A read-only SnapTrade link for a US account; a kind line otherwise."""
    lang = profile.lang
    if profile.currency != USD:
        return Reply(say(US_ONLY, lang))
    url = holdings.snaptrade_link(profile.user_id, store, client=services.snaptrade)
    if url is None:
        return Reply(say(NOT_YET, lang))
    return Reply(say(LINK_LEAD, lang), ((Button(say(LINK_BUTTON, lang), "", url),),))
