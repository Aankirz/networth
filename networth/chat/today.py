"""What happened today, why the brief said what it said, the user's plan, and the scope line.
Each returns an Answer built only from stored facts."""

from __future__ import annotations

import datetime as dt
from typing import Final

from networth import brief
from networth.app.services import Services
from networth.app.store import Profile, Store
from networth.bot.onboarding import summary
from networth.chat.answer import Answer
from networth.watcher.store import Confirmed
from networth.watcher.store import Store as WatcherStore
from networth.web import names

DAY: Final = dt.timedelta(hours=24)
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


def what_happened(services: Services, now: dt.datetime) -> Answer:
    db = services.watcher_db
    if not db.exists():
        return Answer("I haven't read today's news yet. Ask me again in a little while.", "")
    store = WatcherStore.open(db)
    try:
        fresh = {s.id for s in store.stories_pulled_since(now - DAY)}
        decided = [d for d in store.decisions() if d.story.id in fresh]
    finally:
        store.close()
    confirmed = [d for d in decided if isinstance(d.verdict, Confirmed)]
    unconfirmed = len(decided) - len(confirmed)
    lines = [f"• {d.story.title}. Reported by {', '.join(d.verdict.publishers)}."
             for d in confirmed[:MAX_STORIES]]  # fmt: skip
    rest = (f"\n\nI also saw {unconfirmed} report{'s' if unconfirmed != 1 else ''} I could not "
            "confirm, so they are left out.") if unconfirmed else ""  # fmt: skip
    if not lines:
        text = f"Nothing was confirmed in the last 24 hours.{rest}"
    else:
        text = "Confirmed in the last 24 hours:\n" + "\n".join(lines) + rest
    return Answer(text, text, TODAY_TASK, kind="today")


def why(store: Store, profile: Profile, services: Services, today: dt.date) -> Answer:
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


def plan(store: Store, profile: Profile) -> Answer:
    saved = store.get_plan(profile.user_id)
    if saved is None:
        return Answer(NO_PLAN, NO_PLAN)
    text = summary(profile, saved).removesuffix("Looks right?") + "Type /plan to change it."
    return Answer(text, text)


def scope() -> Answer:
    return Answer(SCOPE, SCOPE)
