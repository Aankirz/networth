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
from networth.bot.message import Block, Link, Message, plain, say
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Bot, Button
from networth.config import ProductConfig
from networth.engine.backtest import market_of
from networth.llm import Classified
from networth.watcher.store import Confirmed, Insight, Story
from networth.watcher.store import Store as WatcherStore
from networth.web import names

log = logging.getLogger("networth.bot")

STOP_PREFIX: Final = "wt:stop:"
UNAVAILABLE: Final = {
    "en": "Watches aren't working on my side right now. You can try again in a little while.",
    "hi": "वॉच अभी मेरी तरफ़ से नहीं चल रहीं। थोड़ी देर बाद फिर कोशिश कर सकते हैं।",
    "hinglish": "Watches abhi meri taraf se nahin chal rahi. Thodi der baad phir try kar sakte "
    "hain.",
}
YOUR_WATCHES: Final = {"en": "Your watches:", "hi": "आपकी वॉच:", "hinglish": "Aapki watches:"}
HOW_TO_STOP: Final = {
    "en": "To stop one, type /unwatch and its number.",
    "hi": "किसी को बंद करने के लिए /unwatch और उसका नंबर लिख सकते हैं।",
    "hinglish": "Kisi ko band karne ke liye /unwatch aur uska number likh sakte hain.",
}
HOW_MANY: Final = {
    "en": "You have {n} watches. /unwatch and a number stops one.",
    "hi": "आपकी {n} वॉच हैं। /unwatch और नंबर लिखने पर कोई एक बंद होती है।",
    "hinglish": "Aapki {n} watches hain. /unwatch aur number likhne par koi ek band hoti hai.",
}
STOP_BUTTON: Final = {"en": "Stop {n}", "hi": "बंद {n}", "hinglish": "Band {n}"}
WATCHED: Final = {
    "en": "Something you're watching: {label}.",
    "hi": "जिस पर आपकी नज़र है: {label}।",
    "hinglish": "Jis par aapki nazar hai: {label}.",
}
TOLD: Final = {
    "en": "The watcher confirmed it: {headline}.",
    "hi": "वॉचर ने इसकी पुष्टि की: {headline}।",
    "hinglish": "Watcher ne ise confirm kiya: {headline}.",
}
TOLD_PLAIN: Final = {
    "en": "The watcher confirmed a story about it.",
    "hi": "वॉचर ने इसके बारे में एक ख़बर की पुष्टि की।",
    "hinglish": "Watcher ne iske baare mein ek story confirm ki.",
}
SOURCE: Final = {"en": "Source: {source}", "hi": "स्रोत: {source}",
                 "hinglish": "Source: {source}"}  # fmt: skip
REPORTED: Final = {
    "en": "Reported by {n} publishers: {named}.",
    "hi": "{n} पब्लिशरों ने रिपोर्ट किया: {named}।",
    "hinglish": "{n} publishers ne report kiya: {named}.",
}
CONTEXT: Final = {
    "en": "History's counts are context, not a forecast.",
    "hi": "इतिहास की गिनती सिर्फ़ संदर्भ है, कोई अनुमान नहीं।",
    "hinglish": "History ki ginti sirf context hai, forecast nahin.",
}
WHY_COUNTS: Final = {"en": "Why these counts?", "hi": "ये गिनती क्यों?",
                     "hinglish": "Yeh counts kyun?"}  # fmt: skip
MAX_PUBLISHERS_NAMED: Final = 3


def set_watch(store: Store, profile: Profile, text: str, now: str,
              rules: ProductConfig | None, lang: str | None = None) -> str:  # fmt: skip
    lang = lang or profile.lang
    if rules is None:
        return say(UNAVAILABLE, lang)
    parsed = watch.parse_watch(text)
    if parsed is None:
        return say(watch.USAGE, lang)
    if isinstance(parsed, watch.Refusal):
        return parsed.text(lang)
    saved = store.add_watch(profile.user_id, parsed.kind, parsed.target, parsed.label, now,
                            rules.watch_max_active)  # fmt: skip
    if saved is None:
        return watch.at_cap(rules.watch_max_active, lang)
    return watch.watching(saved.label, lang)


def list_reply(store: Store, profile: Profile) -> Reply:
    lang = profile.lang
    active = store.active_watches(profile.user_id)
    if not active:
        return Reply(say(watch.NO_WATCHES, lang))
    lines = "\n".join(f"{n}. {w.label}" for n, w in enumerate(active, 1))
    text = watch.safe(f"{say(YOUR_WATCHES, lang)}\n{lines}\n\n{say(HOW_TO_STOP, lang)}",
                      say(HOW_MANY, lang).format(n=len(active)))  # fmt: skip
    buttons = tuple((Button(say(STOP_BUTTON, lang).format(n=n), f"{STOP_PREFIX}{w.id}"),)
                    for n, w in enumerate(active, 1))  # fmt: skip
    return Reply(text, buttons)


def stop_nth(store: Store, profile: Profile, args: str) -> str:
    active = store.active_watches(profile.user_id)
    n = int(args) if args.strip().isdigit() else 0
    if not 1 <= n <= len(active):
        return say(watch.UNWATCH_USAGE, profile.lang)
    store.stop_watch(profile.user_id, active[n - 1].id)
    return watch.stopped(active[n - 1].label, profile.lang)


def stop_tapped(store: Store, profile: Profile, data: str) -> str:
    """A Stop button's callback data, wt:stop:<watch id>. Only the user's own watch stops."""
    raw = data.removeprefix(STOP_PREFIX)
    active = {w.id: w for w in store.active_watches(profile.user_id)}
    stopped = active.get(int(raw)) if raw.isdigit() else None
    if stopped is None or not store.stop_watch(profile.user_id, stopped.id):
        return say(watch.WATCH_STOPPED, profile.lang)
    return watch.stopped(stopped.label, profile.lang)


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


def source_line(v: Confirmed, lang: str | None) -> str:
    if v.primary_source:
        return say(SOURCE, lang).format(source=v.primary_source)
    named = ", ".join(v.publishers[:MAX_PUBLISHERS_NAMED])
    return say(REPORTED, lang).format(n=len(v.publishers), named=named)


def watch_message(w: Watch, seen: Seen, insight: Insight | None, public_url: str | None,
                  lang: str | None, headline: bool = True) -> Message:  # fmt: skip
    told = (say(TOLD, lang).format(headline=seen.story.title.rstrip(".")) if headline
            else say(TOLD_PLAIN, lang))  # fmt: skip
    body: list[Block] = [f"{told}\n{source_line(seen.verdict, lang)}"]
    link = None
    if insight is not None:
        o = insight.odds
        line = brief.odds_line(insight.type, o, int(o["n_episodes"]), bool(o["weak_signal"]))
        body.append(f"{line.words(lang)}\n{say(CONTEXT, lang)}")
        if public_url:
            link = Link(
                say(WHY_COUNTS, lang), public_url + names.why_path(insight.type, insight.asset)
            )
            body.append(link)
    return Message(
        say(WATCHED, lang).format(label=w.label), tuple(body), preview=link.url if link else None
    )


def checked_message(w: Watch, seen: Seen, insight: Insight | None, services: Services,
                    lang: str | None) -> Message | None:  # fmt: skip
    """The message, without the headline if the headline trips the guard's word rules, or None
    when even that version does not pass."""
    for headline in (True, False):
        m = watch_message(w, seen, insight, services.public_url, lang, headline)
        text = plain(m)
        verdict = guard.check(text, text)
        guard.log_verdict(services.guard_log, "watch", "template", verdict)
        if verdict.ok:
            return m
    return None


def wants_watches(p: Profile | None) -> bool:
    return p is not None and p.step is Step.DONE and p.status is Status.ACTIVE


def tell(store: Store, bot: Bot, services: Services, p: Profile, w: Watch, seen: Seen,
         insights: Sequence[Insight], month: str, cap: int) -> bool:  # fmt: skip
    if not store.claim_watch_hit(p.user_id, w.id, seen.key, month, cap):
        return False
    try:
        m = checked_message(w, seen, history_for(seen, p, insights), services, p.lang)
        if m is None:
            log.warning("watch %s: no version of the message passed the guard", w.id)
            return False
        if send(store, bot, p, Reply(m), proactive=True, mail=services.mail):
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
