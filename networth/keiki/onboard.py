"""The short setup for someone who first writes by email: language, goal, amount, investing day.

    outcome = advance_email(profile, "1 lakh")

A pure state machine over EMAIL_STEPS that reuses onboarding's parses and retry lines, so a
typed answer means the same thing on both channels. No plan is saved: the brief already says
"You haven't picked a plan" when there is none. The caller stores the outcome and sends it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Final

from networth.app.store import Profile, Step
from networth.bot.message import Message, say
from networth.bot.onboarding import (
    QUESTIONS,
    Outcome,
    Reply,
    day_label,
    retry_line,
    with_lead,
    with_money,
)
from networth.bot.onboarding import prompt as telegram_prompt

EMAIL_STEPS: Final = (Step.LANG, Step.GOAL, Step.AMOUNT, Step.DAY)
LANG_TEXT: Final = (
    "Hi, I'm Networth. I read the market news every day, and I can write to you on the day you "
    "invest. Four short questions to set you up.\nनमस्ते, मैं Networth हूँ।\n\n"
    "Which language do you want? / आप किस भाषा में बात करना चाहेंगे?"
)
EMAIL_TEXT: Final[Mapping[Step, Mapping[str, str]]] = {
    Step.GOAL: {
        "en": "What's this money for?",
        "hi": "यह पैसा किसलिए है?",
        "hinglish": "Yeh paisa kis liye hai?",
    },
    Step.AMOUNT: {
        "en": "About how much do you invest each month? Write it like 25k, 1 lakh or $500.",
        "hi": "आप हर महीने लगभग कितना निवेश करते हैं? 25k, 1 lakh या $500 जैसा लिख सकते हैं।",
        "hinglish": "Aap har mahine lagbhag kitna invest karte hain? 25k, 1 lakh ya $500 jaisa "
        "likh sakte hain.",
    },
    Step.DAY: {
        "en": "Which day of the month do you usually invest? Write a number from 1 to 28.",
        "hi": "आप आमतौर पर महीने की किस तारीख़ को निवेश करते हैं? 1 से 28 तक का नंबर लिख सकते हैं।",
        "hinglish": "Aap aam taur par mahine ki kis tareekh ko invest karte hain? 1 se 28 tak ka "
        "number likh sakte hain.",
    },
}
DONE_TITLE: Final = {"en": "You're set.", "hi": "सब तैयार है।", "hinglish": "Sab taiyaar hai."}
DONE_BODY: Final = {
    "en": "I'll write on the {day} of each month, the morning you invest, with what history "
    "says about months like this one.",
    "hi": "हर महीने {day} तारीख़ की सुबह, जिस दिन आप निवेश करते हैं, मैं लिखूँगा कि ऐसे महीनों के "
    "बारे में इतिहास क्या कहता है।",
    "hinglish": "Har mahine {day} tareekh ki subah, jis din aap invest karte hain, main "
    "likhoonga ki aise mahinon ke baare mein history kya kehti hai.",
}
WANT_IT_NOW: Final = {
    "en": "Want it now? Reply /brief now.",
    "hi": "/brief now लिखने पर यह अभी आ जाएगी।",
    "hinglish": "/brief now likhne par yeh abhi aa jayegi.",
}
DONE_HELP: Final = {
    "en": "Reply /help to see what I can do.",
    "hi": "/help भेजने पर मेरे सारे काम दिखेंगे।",
    "hinglish": "/help bhejne par mere saare kaam dikhenge.",
}
APPLY: Final[dict[Step, Callable[[Profile, object], Profile]]] = {
    Step.GOAL: lambda p, goal: replace(p, goal=goal),
    Step.AMOUNT: with_money,
    Step.DAY: lambda p, day: replace(p, invest_day=day),
    Step.LANG: lambda p, lang: replace(p, lang=lang),
}


def done_message(p: Profile) -> Message:
    lang = p.lang
    day = say(DONE_BODY, lang).format(day=day_label(p.invest_day or 1, lang))
    return Message(say(DONE_TITLE, lang), (day, say(WANT_IT_NOW, lang), say(DONE_HELP, lang)))


def prompt(profile: Profile) -> Reply:
    """The email question for the profile's step, with onboarding's answer buttons, which
    render.plain turns into a "Reply with one of" line."""
    text = LANG_TEXT if profile.step is Step.LANG else say(EMAIL_TEXT[profile.step], profile.lang)
    return Reply(text, telegram_prompt(profile, None).buttons)


def start(profile: Profile) -> Outcome:
    profile = replace(profile, step=EMAIL_STEPS[0])
    return Outcome(profile, None, (prompt(profile),))


def advance_email(profile: Profile, text: str) -> Outcome:
    if profile.step not in EMAIL_STEPS:
        return start(profile)
    value = QUESTIONS[profile.step].parse(text)
    if value is None:
        retry = with_lead(retry_line(profile.step, text, profile.lang), prompt(profile))
        return Outcome(profile, None, (retry,))
    profile = APPLY[profile.step](profile, value)
    i = EMAIL_STEPS.index(profile.step) + 1
    if i == len(EMAIL_STEPS):
        profile = replace(profile, step=Step.DONE)
        return Outcome(profile, None, (Reply(done_message(profile)),))
    profile = replace(profile, step=EMAIL_STEPS[i])
    return Outcome(profile, None, (prompt(profile),))
