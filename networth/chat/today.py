"""What happened today, why the brief said what it said, the user's plan and its range, and the
scope line. Each returns an Answer built only from stored facts, its words written in English,
Hindi and Hinglish, so a reader whose model draft fails the guard still gets their language."""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Callable, Mapping
from typing import Final
from zoneinfo import ZoneInfo

from networth import brief, sim
from networth.app.services import Services
from networth.app.store import INDIA_TZ, Plan, Profile, Store
from networth.bot.message import LANGS, Link, say
from networth.bot.onboarding import plan_line
from networth.brief.lines import Line, day_words
from networth.chat import talk
from networth.chat.answer import Answer
from networth.sim.data import MissingSeries
from networth.watcher.store import Confirmed
from networth.watcher.store import Store as WatcherStore
from networth.web import names

log = logging.getLogger("networth.chat")

DAY: Final = dt.timedelta(hours=24)
STALE_CHECK: Final = dt.timedelta(hours=1)
MAX_STORIES: Final = 5
TODAY_TASK: Final = "Tell a beginner, in a short chat message, what news was confirmed today."
WHY_TASK: Final = (
    "Explain to a beginner, in a short chat message, where the brief's line came from."
)
TYPE_TASK: Final = "Explain to a beginner, in a short chat message, what history shows here."

NOT_READ: Final = {
    "en": "I haven't read today's news yet. I check a few times a day, so it won't be long.",
    "hi": "मैंने आज की ख़बरें अभी नहीं पढ़ीं। मैं दिन में कुछ बार देखता हूँ, ज़्यादा देर नहीं लगेगी।",
    "hinglish": "Maine aaj ki news abhi nahin padhi. Main din mein kuch baar check karta hoon, "
    "zyada der nahin lagegi.",
}
LAST_DAY: Final = {"en": "the last 24 hours", "hi": "पिछले 24 घंटों",
                   "hinglish": "pichhle 24 ghante"}  # fmt: skip
BEFORE_CHECK: Final = {
    "en": "the 24 hours before my last news check ({when})",
    "hi": "मेरी पिछली जाँच ({when}) से पहले के 24 घंटों",
    "hinglish": "meri pichhli news check ({when}) se pehle ke 24 ghante",
}
NOTHING_CONFIRMED: Final = {
    "en": "Nothing was confirmed in {when}.",
    "hi": "{when} में किसी ख़बर की पुष्टि नहीं हुई।",
    "hinglish": "{when} mein koi news confirm nahin hui.",
}
CONFIRMED_IN: Final = {
    "en": "Confirmed in {when}:",
    "hi": "{when} में इनकी पुष्टि हुई:",
    "hinglish": "{when} mein yeh confirm hua:",
}
STORY: Final = {
    "en": "• {title}. Reported by {who}.",
    "hi": "• {title}। रिपोर्ट करने वाले: {who}।",
    "hinglish": "• {title}. Report karne wale: {who}.",
}
LEFT_OUT_ONE: Final = {
    "en": "I also saw 1 other report I could not confirm, so it is left out.",
    "hi": "1 और रिपोर्ट दिखी जिसकी पुष्टि नहीं हो सकी, इसलिए वह यहाँ नहीं है।",
    "hinglish": "1 aur report dikhi jo confirm nahin ho saki, isliye woh yahan nahin hai.",
}
LEFT_OUT: Final = {
    "en": "I also saw {n} other reports I could not confirm, so they are left out.",
    "hi": "{n} और रिपोर्टें दिखीं जिनकी पुष्टि नहीं हो सकी, इसलिए वे यहाँ नहीं हैं।",
    "hinglish": "{n} aur reports dikhi jo confirm nahin ho saki, isliye woh yahan nahin hain.",
}
HISTORY_HEAD: Final = {
    "en": "Here's what history counted after news like this:",
    "hi": "ऐसी ख़बरों के बाद इतिहास ने यह गिना:",
    "hinglish": "Aisi news ke baad history ne yeh gina:",
}
NOT_A_FORECAST: Final = {
    "en": "That is a count of what happened, not a forecast.",
    "hi": "यह बीते समय की गिनती है, कोई अनुमान नहीं।",
    "hinglish": "Yeh beete waqt ki ginti hai, koi forecast nahin.",
}
EVERY_CASE: Final = {"en": "Every past case", "hi": "हर पुराना मामला",
                     "hinglish": "Har purana case"}  # fmt: skip
STARTS_FROM: Final = {
    "en": "This month's brief starts from one confirmed story: {title} ({day}).",
    "hi": "इस महीने का ब्रीफ़ एक पुष्ट ख़बर से शुरू होता है: {title} ({day})।",
    "hinglish": "Is mahine ka brief ek confirmed story se shuru hota hai: {title} ({day}).",
}
CONFIRM_RULE: Final = {
    "en": "We count news only when at least {k} publishers report it within {h} hours, or an "
    "official source posts it.",
    "hi": "हम किसी ख़बर को तभी गिनते हैं जब कम से कम {k} पब्लिशर उसे {h} घंटों के अंदर रिपोर्ट "
    "करते हैं, या कोई आधिकारिक स्रोत उसे जारी करता है।",
    "hinglish": "Hum kisi news ko tabhi ginte hain jab kam se kam {k} publishers {h} ghante ke "
    "andar use report karte hain, ya koi official source use post karta hai.",
}
NO_LEAD: Final = {
    "en": "Nothing in this month's news matched an event in our history, so the brief had "
    "nothing to explain. You can ask what happened today for the latest.",
    "hi": "इस महीने की किसी ख़बर का हमारे इतिहास की किसी घटना से मेल नहीं हुआ, इसलिए ब्रीफ़ में "
    "समझाने को कुछ नहीं था। ताज़ा ख़बरों के लिए आप पूछ सकते हैं कि आज क्या हुआ।",
    "hinglish": "Is mahine ki kisi news ka hamari history se match nahin hua, isliye brief mein "
    "samjhaane ko kuch nahin tha. Taaza news ke liye aap pooch sakte hain ki aaj kya hua.",
}
NO_PLAN: Final = {
    "en": "You haven't picked a plan yet. /start finishes setting up, and it takes a minute.",
    "hi": "आपने अभी कोई प्लान नहीं चुना है। /start से सेटअप एक मिनट में पूरा हो जाता है।",
    "hinglish": "Aapne abhi koi plan nahin chuna hai. /start se setup ek minute mein poora ho "
    "jaata hai.",
}
NOT_A_JUDGE: Final = {
    "en": "I can't tell you whether a plan is right for you. The plan stays your choice.",
    "hi": "मैं नहीं बता सकता कि कोई प्लान आपके लिए सही है या नहीं। प्लान हमेशा आपकी अपनी पसंद है।",
    "hinglish": "Main nahin bata sakta ki koi plan aapke liye sahi hai ya nahin. Plan hamesha "
    "aapki apni pasand hai.",
}
SAVED_PLAN: Final = {
    "en": "This is the plan you saved: {plan}.",
    "hi": "आपने यह प्लान सेव किया है: {plan}।",
    "hinglish": "Aapne yeh plan save kiya hai: {plan}.",
}
# A plain ask to see the saved plan, with nothing asking whether it is right. P10's @plan
# mention sends exactly "What is my plan?".
SHOW_PLAN: Final = re.compile(
    r"^(?:what(?:'s| is) my (?:current |saved )?plan|(?:show|tell) me my plan|(?:see|view) my "
    r"plan|my plan|mera plan(?: kya hai| dikhao| batao)?|मेरा प्लान(?: क्या है| दिखाओ| बताओ)?)$"
)
YOUR_PAGE: Final = {"en": "Your page", "hi": "आपका पेज", "hinglish": "Aapka page"}
RANGE_NOT_READY: Final = {
    "en": "The range isn't available right now. You can ask again in a little while.",
    "hi": "रेंज अभी उपलब्ध नहीं है। थोड़ी देर बाद फिर से पूछ सकते हैं।",
    "hinglish": "Range abhi available nahin hai. Thodi der baad phir se pooch sakte hain.",
}
NO_RANGE: Final = {
    "en": "The range covers rupee plans only for now, and it needs your saved plan, monthly "
    "amount and time horizon. What you saved is in /plan.",
    "hi": "रेंज अभी सिर्फ़ रुपये वाले प्लान के लिए है, और इसके लिए आपका सेव किया प्लान, हर महीने "
    "की रकम और समय ज़रूरी हैं। आपने जो सेव किया है वह /plan में है।",
    "hinglish": "Range abhi sirf rupee plans ke liye hai, aur iske liye aapka saved plan, har "
    "mahine ki rakam aur time horizon zaroori hain. Aapne jo save kiya hai woh /plan mein hai.",
}
SCOPE: Final = {
    "en": "I can tell you what happened today, why a brief said what it said, and whether a tip "
    "you were sent is reported anywhere. You can also send me an IPO page, an article or a "
    "screenshot, and I'll explain it in plain words.",
    "hi": "मैं बता सकता हूँ कि आज क्या हुआ, ब्रीफ़ ने जो कहा वह क्यों कहा, और आपको मिली कोई टिप "
    "कहीं रिपोर्ट हुई है या नहीं। आप मुझे IPO पेज, कोई लेख या स्क्रीनशॉट भी भेज सकते हैं, मैं "
    "उसे आसान शब्दों में समझा दूँगा।",
    "hinglish": "Main bata sakta hoon ki aaj kya hua, brief ne jo kaha woh kyun kaha, aur aapko "
    "mili koi tip kahin report hui hai ya nahin. Aap mujhe IPO page, koi article ya screenshot "
    "bhi bhej sakte hain, main use aasaan shabdon mein samjha doonga.",
}


def by_lang(write: Callable[[str], str]) -> dict[str, str]:
    return {lang: write(lang) for lang in LANGS}


def what_happened(services: Services, now: dt.datetime, tz: str = INDIA_TZ) -> Answer:
    """Confirmed stories pulled in the 24 hours before the last news check. With no check in
    the last hour (nights, weekends), the reply says when that check was."""
    db = services.watcher_db
    if not db.exists():
        return Answer.fixed(NOT_READ)
    store = WatcherStore.open(db)
    try:
        cycle = store.latest_cycle()
        anchor = min(now, cycle.finished_at) if cycle else now
        fresh = {s.id for s in store.stories_pulled_since(anchor - DAY)}
        decided = [d for d in store.decisions() if d.story.id in fresh]
    finally:
        store.close()
    confirmed = [d for d in decided if isinstance(d.verdict, Confirmed)]
    unconfirmed = len(decided) - len(confirmed)
    local = anchor.astimezone(ZoneInfo(tz))
    stale = now - anchor > STALE_CHECK

    def write(lang: str) -> str:
        when = say(LAST_DAY, lang)
        if stale:
            when = say(BEFORE_CHECK, lang).format(
                when=f"{day_words(local.date(), lang)}, {local:%H:%M}")  # fmt: skip
        left = say(LEFT_OUT_ONE if unconfirmed == 1 else LEFT_OUT, lang).format(n=unconfirmed)
        rest = f"\n\n{left}" if unconfirmed else ""
        if not confirmed:
            return say(NOTHING_CONFIRMED, lang).format(when=when) + rest
        lines = [say(STORY, lang).format(title=d.story.title.rstrip("."),
                                         who=", ".join(d.verdict.publishers))
                 for d in confirmed[:MAX_STORIES]]  # fmt: skip
        head = say(CONFIRMED_IN, lang).format(when=when)
        return "\n".join([head, *lines]) + rest

    words = by_lang(write)
    return Answer(words["en"], words["en"], TODAY_TASK, kind="today", words=words)


TYPE_QUESTION: Final = "Which market event type, if any, does this question name?"
NO_TYPE: Final = "none"
MIN_WORDS_FOR_TYPE: Final = 3  # "why?" and "why that?" ask about the brief, not a type


def named_type(text: str, services: Services) -> str | None:
    models = services.models
    if models is None or len(text.split()) < MIN_WORDS_FOR_TYPE:
        return None
    choices = {t: f"{n.title} ({n.plural})" for t, n in names.TYPES.items()}
    try:
        picked = models.pick(TYPE_QUESTION, {**choices, NO_TYPE: "no event type"}, text)
    except Exception:  # noqa: BLE001 - no pick means the brief answers instead
        return None
    return picked if picked in names.TYPES else None


def why_link(line: Line, services: Services, label: Mapping[str, str], lang: str) -> Link | None:
    if not services.public_url:
        return None
    return Link(say(label, lang), f"{services.public_url}{names.why_path(line.type, line.asset)}")


def history_words(line: Line) -> dict[str, str]:
    """The line between its lead-in and the reminder that it counts the past."""
    return by_lang(lambda lang: f"{say(HISTORY_HEAD, lang)}\n{line.words(lang)}\n"
                                f"{say(NOT_A_FORECAST, lang)}")  # fmt: skip


def type_history(type: str, profile: Profile, services: Services,
                 lang: str = "en") -> Answer | None:  # fmt: skip
    """What history counted after an event type, from odds(), with or without news this
    month."""
    assets = services.cfg.triggers.assets_by_type.get(type, ()) if services.cfg else ()
    line = brief.history(type, profile, assets, services.rates_db)
    if line is None:
        return None
    words = history_words(line)
    return Answer(words["en"], words["en"], TYPE_TASK, kind="why", words=words,
                  link=why_link(line, services, EVERY_CASE, lang))  # fmt: skip


def why(store: Store, profile: Profile, services: Services, today: dt.date, text: str = "",
        lang: str = "en") -> Answer:  # fmt: skip
    type = named_type(text, services)
    answer = type_history(type, profile, services, lang) if type else None
    if answer is not None:
        return answer
    events = brief.month_events(services.watcher_db, today)
    draft = brief.compose(events, profile, store.get_plan(profile.user_id), services.rates_db,
                          dt.datetime.combine(today, dt.time()))  # fmt: skip
    lead = draft.lead
    if lead is None:
        return Answer.fixed(NO_LEAD)
    event = next(e for e in events if e.type == lead.type)
    rule = services.cfg.confirm if services.cfg else None

    def write(lang: str) -> str:
        start = say(STARTS_FROM, lang).format(title=event.title.rstrip("."),
                                              day=day_words(event.event_date, lang))  # fmt: skip
        told = say(CONFIRM_RULE, lang).format(k=rule.min_publishers, h=rule.window_hours)
        return "\n\n".join([f"{start} {told}" if rule else start, lead.words(lang)])

    words = by_lang(write)
    return Answer(words["en"], words["en"], WHY_TASK, kind="why", words=words,
                  link=why_link(lead, services, EVERY_CASE, lang))  # fmt: skip


def page_link(profile: Profile, services: Services, lang: str) -> Link | None:
    """A signed link to the user's own page, as /plan builds it, when the server has one."""
    url = services.page_url(profile.link_token, dt.datetime.now(dt.UTC))
    return Link(say(YOUR_PAGE, lang), url) if url else None


def plan(store: Store, profile: Profile, text: str, services: Services, today: dt.date,
         lang: str = "en") -> Answer:  # fmt: skip
    """A plain ask to see the plan gets the saved plan. Anything else gets the fixed line saying
    a plan is not judged here, then the history line of an event type named in the question and
    confirmed this month, then a link to the user's own page. Neither invites a change."""
    saved = store.get_plan(profile.user_id)
    if saved is None:
        return Answer.fixed(NO_PLAN)
    if SHOW_PLAN.match(talk.bare(text)):
        return saved_plan(saved, profile, services, lang)
    month = {e.type for e in brief.month_events(services.watcher_db, today)}
    type = named_type(text, services) if month else None
    assets = services.cfg.triggers.assets_by_type.get(type, ()) if services.cfg and type else ()
    line = brief.history(type, profile, assets, services.rates_db) if type in month else None
    extra = history_words(line) if line else {}
    words = by_lang(lambda lang: "\n\n".join(x for x in (say(NOT_A_JUDGE, lang),
                                                         extra.get(lang)) if x))  # fmt: skip
    return Answer.fixed(words, kind="plan", link=page_link(profile, services, lang))


def saved_plan(saved: Plan, profile: Profile, services: Services, lang: str) -> Answer:
    """The user's own saved plan read back as a fact, never with "Looks right?" or /plan."""
    words = by_lang(lambda lang: say(SAVED_PLAN, lang).format(plan=plan_line(saved, lang)))
    return Answer.fixed(words, kind="plan", link=page_link(profile, services, lang))


def plan_range(store: Store, profile: Profile, lang: str) -> Answer:
    """The user's own plan replayed over past months, in fixed sentences: no model rewords it."""
    lang = lang if lang in NO_RANGE else "en"
    try:
        text = sim.plan_range_message(profile.user_id, store, lang) or NO_RANGE[lang]
    except MissingSeries:
        log.exception("no plan range table")
        text = RANGE_NOT_READY[lang]
    return Answer(text, text, kind="range", words={lang: text})


def scope() -> Answer:
    return Answer.fixed(SCOPE)
