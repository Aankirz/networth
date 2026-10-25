"""Free text from a set-up user: pick one closed intent, then that intent's handler answers.

    intent = classify(text, is_forward, services)
    reply = respond(store, profile, text, is_forward, services, now)
    reply, intent, used = respond_traced(store, profile, text, is_forward, services, now)
    built = build(store, profile, text, is_forward, services, now)   # the Answer, not yet sent

respond_traced is build, deliver_traced, then remember: the exchange joins the user's window
(networth.chat.talk). build reads the window first: a follow-up to the last answer, then
classify; an OTHER pick (and a short "should I" read as EXPLAIN_THIS) is refined into a Talk
kind, which still reports Intent.OTHER, because the site's contract pins Intent.
A dashboard ask (networth.chat.dashboard) is answered before any of that.

The pick is a typed Jev Choice when config says Jev measured at least as accurate as the cheap
model (evals/intent_accuracy.py), and Jev answered above its confidence floor in time. In every
other case the cheap model picks. With no models at all, simple phrase rules pick.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

from networth import memory
from networth.app.services import Services
from networth.app.store import Profile, Store
from networth.bot import holdings, watches
from networth.bot.message import Message
from networth.bot.onboarding import Reply
from networth.chat import dashboard, explain, jev, talk, tip, today
from networth.chat.answer import Answer, Used, deliver, deliver_traced
from networth.chat.talk import Said, Talk


class Intent(StrEnum):
    WHAT_HAPPENED_TODAY = "what_happened_today"
    WHY = "why"
    TIP_CHECK = "tip_check"
    EXPLAIN_THIS = "explain_this"
    PLAN_QUESTION = "plan_question"
    PLAN_RANGE = "plan_range"
    WATCH = "watch"
    HOLDINGS = "holdings"
    PRICE = "price"
    PRICE_HISTORY = "price_history"
    POSITION = "position"
    COMPARE = "compare"
    STOCK_VIEW = "stock_view"
    OTHER = "other"


CRITERIA: Final[dict[str, str]] = {
    Intent.WHAT_HAPPENED_TODAY: "asks what happened in the market or the news today or lately",
    Intent.WHY: "asks why: the reason, source or history behind the last message or brief",
    Intent.TIP_CHECK: (
        "a tip, rumour or claim about markets, a stock, a policy or an event to verify, often "
        "forwarded from a group chat; not a factual document such as an IPO page"
    ),
    Intent.EXPLAIN_THIS: (
        "wants something explained in plain words: an IPO page, a news article, a broker "
        "alert, a link, a long pasted text (forwarded or not), or a finance term such as "
        "DRHP, PAT or SIP"
    ),
    Intent.PLAN_QUESTION: (
        "asks about their own saved plan, split, amount, investing day, what they left out, "
        "or other settings; not what the plan could grow to or how far it could fall"
    ),
    Intent.PLAN_RANGE: (
        "asks what their own plan could grow to or end up as, or how far or how badly it "
        'could fall, such as "what could my plan become" or "how bad can a fall get"'
    ),
    Intent.WATCH: (
        "asks to be told when something happens, or to watch or track a topic, event or company"
    ),
    Intent.HOLDINGS: (
        "asks about their own holdings, investments or portfolio: how they are doing, what "
        "they own, or what to do with them"
    ),
    Intent.OTHER: (
        "anything else: greetings, thanks, general questions about how money, investing or "
        "markets work, whether to put money into something, unrelated questions"
    ),
}
QUESTION: Final = "Which of these does the user's message to a market-news assistant want?"
STATE: Final = "{kind} to a market-news assistant: {text!r}"
LONG_TEXT: Final = 400
MAX_TERM_QUESTION: Final = 200  # a longer explain-this is a pasted document, not a question
DEVANAGARI: Final = re.compile(r"[ऀ-ॿ]")
HINGLISH_WORDS: Final = frozenset(
    "kya hai hain hua aaj mein ka ki ko kaise kyun kyon batao samjhao yeh ye nahi kuch "
    "karna chahiye paisa matlab bhai yaar accha theek".split()
)
HINGLISH_MIN_WORDS: Final = 2
PHRASES: Final = (
    (("watch", "tell me if", "tell me when", "let me know when", "alert me"), Intent.WATCH),
    (("what happened", "aaj market", "news today", "kya hua"), Intent.WHAT_HAPPENED_TODAY),
    (("why",), Intent.WHY),
    (
        (
            "portfolio",
            "my investments",
            "my holdings",
            "investments doing",
            "what should i sell",
            "should i sell",
        ),
        Intent.HOLDINGS,
    ),
    (
        ("could my plan", "plan become", "how bad can a fall", "how far can my plan", "my range"),
        Intent.PLAN_RANGE,
    ),
    (("my plan", "my amount", "investing day"), Intent.PLAN_QUESTION),
)


def reply_lang(text: str, profile: Profile) -> str:
    """The language they ask for outright, else Hindi when they write in Devanagari, Hinglish
    when they write Hindi in Roman letters, otherwise the language they chose at setup."""
    if asked := talk.asked_lang(text):
        return asked
    if DEVANAGARI.search(text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & HINGLISH_WORDS) >= HINGLISH_MIN_WORDS:
        return "hinglish"
    return profile.lang or "en"


def _by_phrase(text: str, is_forward: bool) -> Intent:
    lowered = text.lower()
    if explain.user_link(text) or len(text) > LONG_TEXT:
        return Intent.EXPLAIN_THIS
    if is_forward:
        return Intent.TIP_CHECK
    return next((i for words, i in PHRASES if any(w in lowered for w in words)), Intent.OTHER)


def classify(text: str, is_forward: bool, services: Services) -> Intent:
    kind = "A message the user forwarded" if is_forward else "The user wrote"
    state = STATE.format(kind=kind, text=text[:2000])
    cfg = services.cfg
    if cfg is not None and cfg.product.use_jev_for_intent:
        product = cfg.product
        pick = jev.choose(
            state, QUESTION, CRITERIA, services.env,
            deadline_s=product.jev_deadline_s, log_path=services.call_log,
        )  # fmt: skip
        if pick is not None and pick.confidence >= product.jev_min_confidence:
            return Intent(pick.name)
    if services.models is not None:
        try:
            picked = services.models.pick(QUESTION, CRITERIA, state)
        except Exception:  # noqa: BLE001 - a failed pick falls back to phrase rules
            picked = None
        if picked is not None:
            return Intent(picked)
    return _by_phrase(text, is_forward)


def watch_answer(store: Store, profile: Profile, text: str, services: Services,
                 now: dt.datetime, lang: str) -> Answer:  # fmt: skip
    """Sets the watch the text asks for; fixed words, so no model writes the reply."""
    rules = services.cfg.product if services.cfg else None
    reply = watches.set_watch(store, profile, text, now.isoformat(), rules, lang)
    return Answer(reply, reply, kind="watch", words={lang: reply}, footer=False)


def local_date(p: Profile, now: dt.datetime) -> dt.date:
    return now.astimezone(ZoneInfo(p.tz)).date()


Handler = Callable[[Store, Profile, str, Services, dt.datetime, str], Answer]
HANDLERS: Final[dict[Intent, Handler]] = {
    Intent.WHAT_HAPPENED_TODAY: lambda store, p, text, s, now, lang: today.what_happened(
        s, now, p.tz
    ),
    Intent.WHY: lambda store, p, text, s, now, lang: today.why(
        store, p, s, local_date(p, now), text, lang
    ),
    Intent.TIP_CHECK: lambda store, p, text, s, now, lang: tip.check_tip(text, p, s, now, lang),
    Intent.EXPLAIN_THIS: lambda store, p, text, s, now, lang: explain.explain_message(text),
    Intent.PLAN_QUESTION: lambda store, p, text, s, now, lang: today.plan(
        store, p, text, s, local_date(p, now), lang
    ),
    Intent.PLAN_RANGE: lambda store, p, text, s, now, lang: today.plan_range(store, p, lang),
    Intent.WATCH: watch_answer,
    Intent.HOLDINGS: lambda store, p, text, s, now, lang: holdings.chat_answer(
        store, p, text, s, lang
    ),
    Intent.OTHER: lambda store, p, text, s, now, lang: today.scope(),
}


def respond(
    store: Store, profile: Profile, text: str, is_forward: bool, services: Services,
    now: dt.datetime,
) -> Reply:  # fmt: skip
    return respond_traced(store, profile, text, is_forward, services, now)[0]


@dataclass(frozen=True)
class Built:
    answer: Answer
    intent: Intent  # what the site sees: every Talk kind is Intent.OTHER
    lang: str
    label: str  # the Intent or Talk value the turn is stored under


def build(
    store: Store, profile: Profile, text: str, is_forward: bool, services: Services,
    now: dt.datetime,
) -> Built:  # fmt: skip
    """The answer and how it was picked. Reads the window; writes only asked terms."""
    window = talk.window(store, profile.user_id, now)

    def said(lang: str) -> Said:
        return Said(profile, text, window, services, now, lang)

    if dashboard.asks(text, is_forward):
        lang = reply_lang(text, profile)
        answer = dashboard.dashboard(profile, services, now, lang)
        return Built(answer, Intent.OTHER, lang, Talk.DASHBOARD)
    if talk.follows_up(text, is_forward, window, now, services.models):
        last = talk.last_exchange(window)
        before = reply_lang(last.asked.text, profile) if last else profile.lang
        lang = reply_lang(text, replace(profile, lang=before))
        return Built(talk.follow_up(said(lang)), Intent.OTHER, lang, Talk.FOLLOW_UP)
    intent = classify(text, is_forward, services)
    short = len(text) <= MAX_TERM_QUESTION
    if intent is Intent.EXPLAIN_THIS and short and not explain.URL.search(text):
        store.add_asked_terms(profile.user_id, memory.asked_terms(text), now.isoformat())
    lang = reply_lang(text, profile)
    kind = None
    if intent is Intent.OTHER:
        kind = talk.kind_of(text, services.models)
    elif intent is Intent.EXPLAIN_THIS and short and not is_forward and talk.is_should_i(text):
        kind = Talk.SHOULD_I
    if kind is not None:
        return Built(talk.TALK[kind](said(lang)), Intent.OTHER, lang, kind)
    asked = text
    shows_plan = intent is Intent.PLAN_QUESTION and today.SHOW_PLAN.match(talk.bare(text))
    if (
        intent is Intent.PLAN_QUESTION
        and not shows_plan
        and (last := talk.live_exchange(window, now))
    ):
        # "what about my plan then?" names its event type only through the last answer; a plain
        # "What is my plan?" must reach the plan handler as typed, or the show rule misses it
        asked = f"{text}\n\n{talk.clip(last.answered.text)}"
    answer = HANDLERS[intent](store, profile, asked, services, now, lang)
    return Built(answer, intent, lang, intent)


def sent_words(reply: Reply) -> str:
    """The body as the reader saw it, without the footer or any link."""
    m = reply.message
    assert isinstance(m, Message), "Reply wraps a plain string in a Message"
    return "\n\n".join(b for b in m.body if isinstance(b, str))


def remember(store: Store, profile: Profile, text: str, reply: Reply, label: str,
             now: dt.datetime) -> None:  # fmt: skip
    talk.remember(store, profile.user_id, text, sent_words(reply), label, now)


def respond_traced(
    store: Store, profile: Profile, text: str, is_forward: bool, services: Services,
    now: dt.datetime,
) -> tuple[Reply, Intent, Used]:  # fmt: skip
    """The reply, the intent that answered, and which words went out."""
    built = build(store, profile, text, is_forward, services, now)
    reply, used = deliver_traced(built.answer, built.lang, services)
    remember(store, profile, text, reply, built.label, now)
    return reply, built.intent, used


def respond_image(profile: Profile, image: bytes, services: Services) -> Reply:
    return deliver(explain.explain_image(image, services), profile.lang or "en", services)
