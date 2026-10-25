"""Investing-day briefs: compose, word, guard, send, once per user per day.

    send_brief(store, bot, profile, services, today)   # /brief, or one user's scheduled brief
    run_daily(store, bot, services, now)               # every user whose investing day is today

The brief row is claimed before anything is sent, so a schedule that fires twice never sends
a second brief the same day. A compose or send that fails releases the claim, so the next try
sends it. Asking /brief again that day resends
the stored text without another model call.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Final
from zoneinfo import ZoneInfo

from networth import brief, guard
from networth.app import links
from networth.app.services import Services
from networth.app.store import Profile, Status, Step, Store
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Bot

log = logging.getLogger("networth.bot")

LANGUAGES: Final = {
    "en": "English",
    "hi": "Hindi in Devanagari script",
    "hinglish": "Hinglish: Hindi in Roman script, with English for money terms",
}
BRIEF_TASK: Final = """Reword this investing-day brief for a beginner, in {language}. Keep
every line, every number exactly as written, each emoji mark and the line order. Keep "Weak
signal" where it appears, translated. You may smooth the wording; add no number, opinion,
prediction or suggestion of what to do. Return only the message text."""
NOT_SET_UP: Final = "Let's finish setting up first. Type /start."


def language(profile: Profile) -> str:
    return LANGUAGES.get(profile.lang or "en", LANGUAGES["en"])


def compose_reply(profile: Profile, store: Store, services: Services, today: dt.date) -> tuple:
    """(reply, used): the guarded brief and which version went out."""
    events = brief.month_events(services.watcher_db, today)
    draft = brief.compose(events, profile, store.get_plan(profile.user_id), services.rates_db,
                          today)  # fmt: skip
    template = draft.text()
    models = services.models
    if models is None:
        out = guard.Guarded(template, "template", ())
    else:
        task = BRIEF_TASK.format(language=language(profile))
        out = guard.guarded(lambda fb: models.write(task, template, fb), draft.source(),
                            template, services.guard_log, "brief")  # fmt: skip
    page = None
    if services.public_url and services.link_secret:
        page = links.page_url(services.public_url, store.new_link_token(profile.user_id),
                              services.link_secret, dt.datetime.now(dt.UTC))  # fmt: skip
    return Reply(out.text, brief.buttons(draft, services.public_url, page)), out.used


def local_today(profile: Profile, now: dt.datetime) -> dt.date:
    return now.astimezone(ZoneInfo(profile.tz)).date()


def send_brief(
    store: Store, bot: Bot, profile: Profile, services: Services, today: dt.date,
    *, proactive: bool = False,
) -> bool:  # fmt: skip
    if profile.step is not Step.DONE:
        return send(store, bot, profile, Reply(NOT_SET_UP))
    day = today.isoformat()
    if not store.claim_brief(profile.user_id, day):
        if proactive:
            return False
        last = store.last_brief(profile.user_id)
        if last and last[0] == day:
            return send(store, bot, profile, Reply(last[1]))
    try:
        reply, used = compose_reply(profile, store, services, today)
        sent = send(store, bot, profile, reply, proactive=proactive)
    except Exception:
        store.release_brief(profile.user_id, day)
        raise
    store.save_brief(profile.user_id, day, reply.text, used)
    return sent


def run_daily(store: Store, bot: Bot, services: Services, now: dt.datetime) -> int:
    """Send today's brief to each active, set-up user whose investing day is today in their
    own time zone. Returns how many went out."""
    sent = 0
    for p in store.profiles():
        today = local_today(p, now)
        if p.step is not Step.DONE or p.status is not Status.ACTIVE or p.invest_day != today.day:
            continue
        try:
            sent += send_brief(store, bot, p, services, today, proactive=True)
        except Exception:
            log.exception("brief for %s failed", p.user_id)
    return sent
