"""Free text from a set-up user: pick one closed intent, then that intent's handler answers.

    intent = classify(text, is_forward, services)
    reply = respond(store, profile, text, is_forward, services, now)

The pick is a typed Jev Choice when config says Jev measured at least as accurate as the cheap
model (evals/intent_accuracy.py), and Jev answered above its confidence floor in time. In every
other case the cheap model picks. With no models at all, simple phrase rules pick.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from enum import StrEnum
from typing import Final
from zoneinfo import ZoneInfo

from networth.app.services import Services
from networth.app.store import Profile, Store
from networth.bot.onboarding import Reply
from networth.chat import explain, jev, tip, today
from networth.chat.answer import Answer, deliver


class Intent(StrEnum):
    WHAT_HAPPENED_TODAY = "what_happened_today"
    WHY = "why"
    TIP_CHECK = "tip_check"
    EXPLAIN_THIS = "explain_this"
    PLAN_QUESTION = "plan_question"
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
        "or other settings"
    ),
    Intent.OTHER: "anything else: greetings, thanks, unrelated questions",
}
QUESTION: Final = "Which of these does the user's message to a market-news assistant want?"
STATE: Final = "{kind} to a market-news assistant: {text!r}"
URL: Final = re.compile(r"https?://\S+")
LONG_TEXT: Final = 400
DEVANAGARI: Final = re.compile(r"[ऀ-ॿ]")
HINGLISH_WORDS: Final = frozenset(
    "kya hai hain hua aaj mein ka ki ko kaise kyun kyon batao samjhao yeh ye nahi kuch "
    "karna chahiye paisa matlab bhai yaar accha theek".split()
)
HINGLISH_MIN_WORDS: Final = 2
PHRASES: Final = (
    (("what happened", "aaj market", "news today", "kya hua"), Intent.WHAT_HAPPENED_TODAY),
    (("why",), Intent.WHY),
    (("my plan", "my amount", "investing day"), Intent.PLAN_QUESTION),
)


def reply_lang(text: str, profile: Profile) -> str:
    """Hindi when they write in Devanagari, Hinglish when they write Hindi in Roman letters,
    otherwise the language they chose at setup."""
    if DEVANAGARI.search(text):
        return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & HINGLISH_WORDS) >= HINGLISH_MIN_WORDS:
        return "hinglish"
    return profile.lang or "en"


def _by_phrase(text: str, is_forward: bool) -> Intent:
    lowered = text.lower()
    if URL.search(text) or len(text) > LONG_TEXT:
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


Handler = Callable[[Store, Profile, str, Services, dt.datetime], Answer]
HANDLERS: Final[dict[Intent, Handler]] = {
    Intent.WHAT_HAPPENED_TODAY: lambda store, p, text, s, now: today.what_happened(s, now, p.tz),
    Intent.WHY: lambda store, p, text, s, now: today.why(
        store, p, s, now.astimezone(ZoneInfo(p.tz)).date(), text
    ),
    Intent.TIP_CHECK: lambda store, p, text, s, now: tip.check_tip(text, p, s, now),
    Intent.EXPLAIN_THIS: lambda store, p, text, s, now: (
        explain.explain_link(m.group(0)) if (m := URL.search(text)) else explain.explain_text(text)
    ),
    Intent.PLAN_QUESTION: lambda store, p, text, s, now: today.plan(store, p),
    Intent.OTHER: lambda store, p, text, s, now: today.scope(),
}


def respond(
    store: Store, profile: Profile, text: str, is_forward: bool, services: Services,
    now: dt.datetime,
) -> Reply:  # fmt: skip
    intent = classify(text, is_forward, services)
    answer = HANDLERS[intent](store, profile, text, services, now)
    return deliver(answer, reply_lang(text, profile), services)


def respond_image(profile: Profile, image: bytes, services: Services) -> Reply:
    return deliver(explain.explain_image(image, services), profile.lang or "en", services)
