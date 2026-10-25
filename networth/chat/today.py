"""What happened today, why the brief said what it said, the user's plan and its range, and the
scope line.
Each returns an Answer built only from stored facts."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Final
from zoneinfo import ZoneInfo

from networth import brief, sim
from networth.app.services import Services
from networth.app.store import INDIA_TZ, Profile, Store
from networth.bot.onboarding import summary
from networth.chat.answer import Answer
from networth.sim.data import MissingSeries
from networth.watcher.store import Confirmed
from networth.watcher.store import Store as WatcherStore
from networth.web import names

log = logging.getLogger("networth.chat")

DAY: Final = dt.timedelta(hours=24)
STALE_CHECK: Final = dt.timedelta(hours=1)
NOT_READ: Final = "I haven't read today's news yet. Ask me again in a little while."
MAX_STORIES: Final = 5
TODAY_TASK: Final = "Tell a beginner, in a short chat message, what news was confirmed today."
WHY_TASK: Final = (
    "Explain to a beginner, in a short chat message, where the brief's line came from."
)
SCOPE: Final = (
    "I can tell you what happened today, why a brief said what it said, and whether a tip "
    "you were sent is reported anywhere. You can also send me an IPO page, an article or a "
    "screenshot and I'll explain it in plain words. Research, not advice."
)
NO_LEAD: Final = (
    "Nothing in this month's news matched an event we have history for, so the brief had "
    'nothing to explain. Ask me "what happened today?" for the latest.'
)
NO_PLAN: Final = "You haven't picked a plan yet. Type /start to finish setting up."
NOT_A_JUDGE: Final = {
    "en": "I can't tell you whether a plan is right for you. Here's what you saved.",
    "hi": "मैं नहीं बता सकता कि कोई प्लान आपके लिए सही है या नहीं। आपने यह सेव किया है।",
    "hinglish": "Main nahin bata sakta ki koi plan aapke liye sahi hai ya nahin. Aapne yeh "
    "save kiya hai.",
}
RANGE_NOT_READY: Final = {
    "en": "The range isn't available right now. Please try again later.",
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


def what_happened(services: Services, now: dt.datetime, tz: str = INDIA_TZ) -> Answer:
    """Confirmed stories pulled in the 24 hours before the last news check. With no check in
    the last hour (nights, weekends), the reply says when that check was."""
    db = services.watcher_db
    if not db.exists():
        return Answer(NOT_READ, NOT_READ)
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
    lines = [f"• {d.story.title}. Reported by {', '.join(d.verdict.publishers)}."
             for d in confirmed[:MAX_STORIES]]  # fmt: skip
    rest = (f"\n\nI also saw {unconfirmed} report{'s' if unconfirmed != 1 else ''} I could not "
            "confirm, so they are left out.") if unconfirmed else ""  # fmt: skip
    when = "the last 24 hours"
    if now - anchor > STALE_CHECK:
        local = anchor.astimezone(ZoneInfo(tz))
        when = f"the 24 hours before my last news check ({local:%b} {local.day}, {local:%H:%M})"
    if not lines:
        text = f"Nothing was confirmed in {when}.{rest}"
    else:
        text = f"Confirmed in {when}:\n" + "\n".join(lines) + rest
    return Answer(text, text, TODAY_TASK, kind="today")


TYPE_QUESTION: Final = "Which market event type, if any, does this question name?"
NO_TYPE: Final = "none"
MIN_WORDS_FOR_TYPE: Final = 3  # "why?" and "why that?" ask about the brief, not a type
TYPE_TASK: Final = "Explain to a beginner, in a short chat message, what history shows here."


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


def type_history(type: str, profile: Profile, services: Services) -> Answer | None:
    """Where history leans after an event type, from odds(), with or without news this month."""
    assets = services.cfg.triggers.assets_by_type.get(type, ()) if services.cfg else ()
    line = brief.history(type, profile, assets, services.rates_db)
    if line is None:
        return None
    link = (f"\nEvery past episode: {services.public_url}/why/{line.type}/{line.asset}"
            if services.public_url else "")  # fmt: skip
    text = (
        f"What history shows after {names.TYPES[type].plural.removeprefix('past ')}:\n"
        f"{line.mark} {line.text}\nThat is a count of what happened, not a forecast.{link}"
    )
    return Answer(text, text, TYPE_TASK, kind="why")


def why(store: Store, profile: Profile, services: Services, today: dt.date,
        text: str = "") -> Answer:  # fmt: skip
    type = named_type(text, services)
    answer = type_history(type, profile, services) if type else None
    if answer is not None:
        return answer
    events = brief.month_events(services.watcher_db, today)
    draft = brief.compose(events, profile, store.get_plan(profile.user_id), services.rates_db,
                          today)  # fmt: skip
    lead = draft.lead
    if lead is None:
        return Answer(NO_LEAD, NO_LEAD)
    event = next(e for e in events if e.type == lead.type)
    cfg = services.cfg.confirm if services.cfg else None
    rule = ""
    if cfg:
        rule = (
            f"We only count news that at least {cfg.min_publishers} publishers report within "
            f"{cfg.window_hours} hours, or that an official source posts. "
        )
    link = f" Every past episode is listed here: {services.public_url}/why/{lead.type}/{lead.asset}"
    text = (f"The brief starts from this news: {event.title} ({event.event_date:%b} "
            f"{event.event_date.day}). {rule}The line \"{lead.text}\" counts what happened after "
            f"every {names.TYPES[lead.type].plural.removeprefix('past ')} in our records."
            f"{link if services.public_url else ''}")  # fmt: skip
    return Answer(text, text, WHY_TASK, kind="why")


def plan(store: Store, profile: Profile, text: str, services: Services, today: dt.date) -> Answer:
    """The saved plan after the fixed line saying a plan is not judged here. A question naming
    an event type confirmed this month also gets that type's history line."""
    saved = store.get_plan(profile.user_id)
    if saved is None:
        return Answer(NO_PLAN, NO_PLAN)
    saved_text = summary(profile, saved).removeprefix("Here's what I have.\n\n")
    text_out = saved_text.removesuffix("Looks right?") + "Type /plan to change it."
    month = {e.type for e in brief.month_events(services.watcher_db, today)}
    type = named_type(text, services) if month else None
    if type in month:
        history = type_history(type, profile, services)
        text_out = f"{text_out}\n\n{history.template}" if history else text_out
    return Answer(text_out, text_out, lead=NOT_A_JUDGE)


def plan_range(store: Store, profile: Profile, lang: str) -> Answer:
    """The user's own plan replayed over past months, in fixed sentences: no model rewords it."""
    lang = lang if lang in NO_RANGE else "en"
    try:
        text = sim.plan_range_message(profile.user_id, store, lang) or NO_RANGE[lang]
    except MissingSeries:
        log.exception("no plan range table")
        text = RANGE_NOT_READY[lang]
    return Answer(text, text, written=True, kind="range")


def scope() -> Answer:
    return Answer(SCOPE, SCOPE)
