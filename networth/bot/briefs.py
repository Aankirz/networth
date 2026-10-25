"""Investing-day briefs: compose, check, send, once per user per day.

    send_brief(store, bot, profile, services, local)   # /brief, or one user's scheduled brief
    run_daily(store, bot, services, now)               # every user whose investing day is today

The brief is written by code in the user's language (networth.brief); no model rewords it.
The plain render still passes guard.check before it goes, logged as "template". The brief row
is claimed before anything is sent, so a schedule that fires twice never sends a second brief
the same day. The claim is per user, not per channel, so a person who gets briefs by email
gets one a day across Telegram and email. A compose or send that fails releases the claim, so
the next try sends it. Asking /brief again that day resends the stored message, unless a news
check has finished since it was written, the profile changed, or a deploy changed the code that
writes briefs (FORMAT_KEY, stored inside each brief's inputs key); then it is written afresh.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from dataclasses import replace
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from networth import brief, guard, memory
from networth.app import links
from networth.app.services import Services
from networth.app.store import Profile, Status, Step, Store
from networth.bot import message
from networth.bot.message import say
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Bot

log = logging.getLogger("networth.bot")

NOT_SET_UP: Final = {
    "en": "Let's finish setting you up first. Type /start and it takes a minute.",
    "hi": "पहले आपका सेटअप पूरा कर लेते हैं। /start लिखने पर बस एक मिनट लगेगा।",
    "hinglish": "Pehle aapka setup poora kar lete hain. /start likhne par bas ek minute lagega.",
}
BRIEF_INPUTS: Final = ("lang", "goal", "horizon_years", "drop_comfort", "monthly_amount",
                       "currency", "invest_day", "markets", "exclude", "tz")  # fmt: skip
INPUTS_KEY_CHARS: Final = 16
# The code a stored brief's words come from: any deploy that edits it rewrites that day's brief.
FORMAT_KEY: Final = hashlib.sha256(b"".join(
    f.read_bytes() for f in sorted(Path(brief.__file__).parent.glob("*.py"))
) + Path(message.__file__).read_bytes()).hexdigest()  # fmt: skip


def callback(profile: Profile, store: Store, services: Services,
             today: dt.date) -> memory.Callback | None:  # fmt: skip
    if services.cfg is None:
        return None
    return memory.callback_line(store, profile, services.watcher_db, today,
                                services.cfg.product.memory_days)  # fmt: skip


def compose_reply(profile: Profile, store: Store, services: Services,
                  local: dt.datetime) -> tuple[Reply, memory.Callback | None]:  # fmt: skip
    """(reply, back): the brief in the user's language, and the memory line it brought back,
    if it has one."""
    today = local.date()
    events = brief.month_events(services.watcher_db, today)
    plan = store.get_plan(profile.user_id)
    back = callback(profile, store, services, today)
    draft = brief.compose(events, profile, plan, services.rates_db, local, memory=back)
    if draft.events:
        draft = replace(draft, range=brief.plan_range_for(plan, profile))
    lang = profile.lang or "en"
    out = draft.message(lang)
    text = message.plain(out)
    guard.log_verdict(services.guard_log, "brief", "template", guard.check(text, text))
    page = None
    if services.public_url and services.link_secret:
        page = links.page_url(services.public_url, store.new_link_token(profile.user_id),
                              services.link_secret, dt.datetime.now(dt.UTC))  # fmt: skip
    return Reply(out, brief.buttons(draft, lang, services.public_url, page)), back


def inputs_key(profile: Profile, store: Store) -> str:
    """What a brief is written from, its code included, so an edit to any of it makes the next
    /brief fresh."""
    plan = store.get_plan(profile.user_id)
    used = [FORMAT_KEY, *(getattr(profile, f) for f in BRIEF_INPUTS)]
    used += [plan.name, sorted(plan.targets_pct.items()), plan.max_drop_ok] if plan else [None]
    return hashlib.sha256(repr(used).encode()).hexdigest()[:INPUTS_KEY_CHARS]


def local_now(profile: Profile, now: dt.datetime) -> dt.datetime:
    return now.astimezone(ZoneInfo(profile.tz))


def send_brief(
    store: Store, bot: Bot, profile: Profile, services: Services, local: dt.datetime,
    *, proactive: bool = False,
) -> bool:  # fmt: skip
    if profile.step is not Step.DONE:
        return send(store, bot, profile, Reply(say(NOT_SET_UP, profile.lang)))
    day = local.date().isoformat()
    if not store.claim_brief(profile.user_id, day):
        if proactive:
            return False
        last = store.last_brief(profile.user_id)
        checked = services.last_news_check()
        if (
            last
            and last[0] == day
            and store.brief_inputs(profile.user_id, day) == inputs_key(profile, store)
            and not (checked and checked > dt.datetime.fromisoformat(last[2]))
        ):
            return send(store, bot, profile, Reply(message.from_stored(last[1])))
    try:
        reply, back = compose_reply(profile, store, services, local)
        sent = send(store, bot, profile, reply, proactive=proactive, mail=services.mail)
    except Exception:
        store.release_brief(profile.user_id, day)
        raise
    store.save_brief(profile.user_id, day, message.to_json(reply.message), "template",
                     inputs_key(profile, store))  # fmt: skip
    if back:
        store.mark_terms_used(profile.user_id, [back.term])
    return sent


def run_daily(store: Store, bot: Bot, services: Services, now: dt.datetime) -> int:
    """Send today's brief to each active, set-up user whose investing day is today in their
    own time zone. Returns how many went out."""
    sent = 0
    for p in store.profiles():
        local = local_now(p, now)
        if p.step is not Step.DONE or p.status is not Status.ACTIVE or p.invest_day != local.day:
            continue
        try:
            sent += send_brief(store, bot, p, services, local, proactive=True)
        except Exception:
            log.exception("brief for %s failed", p.user_id)
    return sent
