"""Standing watches: set, list and stop them, and tell a user once when one comes true.

    reply = set_watch(store, profile, "watch RBI rate changes", now, rules)
    sent = run_watches(store, bot, services, now)   # after each watcher cycle

Quiet by default. A watch speaks only when the watcher confirms a story first seen after the
watch was set: a type watch matches the story's event type, an entity watch matches the name
in the story's title or any of its articles' titles. Each user hears about a story at most
once, at most watch_max_per_month times a month, claimed before sending; a failed or refused
send releases the claim so the next run retries it. Pull-only users get watches too, because
a watch is something they asked for. Stopped and paused users get nothing.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Final

from networth import brief, guard, watch
from networth.app.services import Services
from networth.app.store import Profile, Status, Step, Store, Watch
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Bot, Button
from networth.chat.answer import Answer, deliver
from networth.config import ProductConfig
from networth.engine.backtest import market_of
from networth.llm import Classified
from networth.watcher.store import Confirmed, Insight, Story
from networth.watcher.store import Store as WatcherStore

log = logging.getLogger("networth.bot")

STOP_PREFIX: Final = "wt:stop:"
UNAVAILABLE: Final = "Watches aren't available right now. Please try again later."
MAX_PUBLISHERS_NAMED: Final = 3


def set_watch(store: Store, profile: Profile, text: str, now: str,
              rules: ProductConfig | None) -> str:  # fmt: skip
    if rules is None:
        return UNAVAILABLE
    parsed = watch.parse_watch(text)
    if parsed is None:
        return watch.USAGE
    if isinstance(parsed, watch.Refusal):
        return parsed.text
    saved = store.add_watch(profile.user_id, parsed.kind, parsed.target, parsed.label, now,
                            rules.watch_max_active)  # fmt: skip
    return watch.at_cap(rules.watch_max_active) if saved is None else watch.watching(saved.label)


def list_reply(store: Store, profile: Profile) -> Reply:
    active = store.active_watches(profile.user_id)
    if not active:
        return Reply(watch.NO_WATCHES)
    lines = "\n".join(f"{n}. {w.label}" for n, w in enumerate(active, 1))
    text = watch.safe(
        f"Your watches:\n{lines}\n\nTo stop one, type /unwatch and its number.",
        f"You have {len(active)} watches. Type /unwatch and a number to stop one.",
    )
    buttons = tuple((Button(f"Stop {n}", f"{STOP_PREFIX}{w.id}"),)
                    for n, w in enumerate(active, 1))  # fmt: skip
    return Reply(text, buttons)


def stop_nth(store: Store, profile: Profile, args: str) -> str:
    active = store.active_watches(profile.user_id)
    n = int(args) if args.strip().isdigit() else 0
    if not 1 <= n <= len(active):
        return watch.UNWATCH_USAGE
    store.stop_watch(profile.user_id, active[n - 1].id)
    return watch.stopped(active[n - 1].label)


def stop_tapped(store: Store, profile: Profile, data: str) -> str:
    """A Stop button's callback data, wt:stop:<watch id>. Only the user's own watch stops."""
    raw = data.removeprefix(STOP_PREFIX)
    active = {w.id: w for w in store.active_watches(profile.user_id)}
    stopped = active.get(int(raw)) if raw.isdigit() else None
    if stopped is None or not store.stop_watch(profile.user_id, stopped.id):
        return watch.WATCH_STOPPED
    return watch.stopped(stopped.label)


# --- the sender ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Seen:
    """A confirmed story as a watch sees it."""

    story: Story
    verdict: Confirmed
    titles: tuple[str, ...]  # the story's title, then its articles' titles

    @property
    def key(self) -> str:
        return self.story.event_key or self.story.id


def type_matches(w: Watch, seen: Seen) -> bool:
    c = seen.story.classification
    return isinstance(c, Classified) and c.type.value in w.types


def entity_matches(w: Watch, seen: Seen) -> bool:
    name = re.compile(rf"(?<!\w){re.escape(w.target.casefold())}(?!\w)")
    return any(name.search(t.casefold()) for t in seen.titles)


MATCHERS: Final[dict[str, Callable[[Watch, Seen], bool]]] = {
    "type": type_matches,
    "entity": entity_matches,
}


def matches(w: Watch, seen: Seen) -> bool:
    set_at = dt.datetime.fromisoformat(w.created_at)
    return seen.story.first_seen >= set_at and MATCHERS[w.kind](w, seen)


def confirmed(db: WatcherStore) -> list[Seen]:
    articles = db.articles_by_story()
    return [Seen(d.story, d.verdict,
                 (d.story.title, *(a.title for a in articles.get(d.story.id, ()))))
            for d in db.decisions() if isinstance(d.verdict, Confirmed)]  # fmt: skip


def history_for(seen: Seen, profile: Profile, insights: Sequence[Insight]) -> Insight | None:
    """The first news-first Insight for the story's event in one of the user's markets."""
    c = seen.story.classification
    if not isinstance(c, Classified):
        return None
    return next((i for i in insights if i.trigger == "news" and i.type == c.type.value
                 and i.event_date == c.event_date
                 and market_of(i.asset).value in profile.markets), None)  # fmt: skip


def source_line(v: Confirmed) -> str:
    if v.primary_source:
        return f"Source: {v.primary_source}"
    named = ", ".join(v.publishers[:MAX_PUBLISHERS_NAMED])
    return f"Reported by {len(v.publishers)} publishers: {named}"


def watch_text(w: Watch, seen: Seen, insight: Insight | None, public_url: str | None,
               headline: bool = True) -> str:  # fmt: skip
    told = (f"The watcher confirmed it: {seen.story.title.rstrip('.')}." if headline
            else "The watcher confirmed a story about it.")  # fmt: skip
    parts = [f"You asked me to watch {w.label}. {told}\n{source_line(seen.verdict)}"]
    if insight is not None:
        o = insight.odds
        line = brief.odds_line(insight.type, o, int(o["n_episodes"]), bool(o["weak_signal"]))
        why = f"\nWhy: {public_url}/why/{insight.type}/{insight.asset}" if public_url else ""
        parts.append(f"{line.mark} {line.text}\nHistory's counts are context, not a forecast."
                     f"{why}")  # fmt: skip
    return "\n\n".join(parts)


def checked_text(w: Watch, seen: Seen, insight: Insight | None, services: Services) -> str | None:
    """The message, without the headline if the headline trips the guard's word rules, or None
    when even that version does not pass."""
    for headline in (True, False):
        text = watch_text(w, seen, insight, services.public_url, headline)
        verdict = guard.check(text, text)
        guard.log_verdict(services.guard_log, "watch", "template", verdict)
        if verdict.ok:
            return text
    return None


def wants_watches(p: Profile | None) -> bool:
    return p is not None and p.step is Step.DONE and p.status is Status.ACTIVE


def tell(store: Store, bot: Bot, services: Services, p: Profile, w: Watch, seen: Seen,
         insights: Sequence[Insight], month: str, cap: int) -> bool:  # fmt: skip
    if not store.claim_watch_hit(p.user_id, w.id, seen.key, month, cap):
        return False
    try:
        text = checked_text(w, seen, history_for(seen, p, insights), services)
        if text is None:
            log.warning("watch %s: no version of the message passed the guard", w.id)
            return False
        reply = deliver(Answer(text, text, None, kind="watch"), p.lang or "en", services)
        if send(store, bot, p, reply, proactive=True, mail=services.mail):
            return True
    except Exception:
        log.exception("watch %s for %s failed", w.id, p.user_id)
    store.release_watch_hit(w.id, seen.key)
    return False


def run_watches(store: Store, bot: Bot, services: Services, now: dt.datetime) -> int:
    """How many watch messages went out."""
    if services.cfg is None or not services.watcher_db.exists():
        return 0
    watches = store.all_active_watches()
    if not watches:
        return 0
    db = WatcherStore.open(services.watcher_db)
    try:
        stories, insights = confirmed(db), db.insights()
    finally:
        db.close()
    cap, month, sent = services.cfg.product.watch_max_per_month, now.strftime("%Y-%m"), 0
    for w in watches:
        p = store.get_profile(w.user_id)
        if not wants_watches(p):
            continue
        for seen in (s for s in stories if matches(w, s)):
            sent += tell(store, bot, services, p, w, seen, insights, month, cap)
    return sent
