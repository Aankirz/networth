"""The short setup for someone who first writes by email: goal, amount, investing day, language.

    outcome = advance_email(profile, "1 lakh")

A pure state machine over EMAIL_STEPS that reuses onboarding's parses and retry lines, so a
typed answer means the same thing on both channels. No plan is saved: the brief already says
"You haven't picked a plan" when there is none. The caller stores the outcome and sends it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Final

from networth.app.store import Profile, Step
from networth.bot.onboarding import (
    QUESTIONS,
    Outcome,
    Reply,
    ordinal,
    retry_line,
    with_money,
)
from networth.bot.onboarding import prompt as telegram_prompt

EMAIL_STEPS: Final = (Step.GOAL, Step.AMOUNT, Step.DAY, Step.LANG)
GREETING: Final = (
    "Hi, I'm Networth. I read the market news every day so you don't have to, and I can write "
    "to you on the day you invest. Four short questions to set you up."
)
EMAIL_TEXT: Final = {
    Step.GOAL: f"{GREETING}\n\nWhat's this money for?",
    Step.AMOUNT: "About how much do you invest each month? Write it like 25k, 1 lakh or $500.",
    Step.DAY: "Which day of the month do you usually invest? Write a number from 1 to 28.",
    Step.LANG: "Which language do you want me to use?",
}
APPLY: Final[dict[Step, Callable[[Profile, object], Profile]]] = {
    Step.GOAL: lambda p, goal: replace(p, goal=goal),
    Step.AMOUNT: with_money,
    Step.DAY: lambda p, day: replace(p, invest_day=day),
    Step.LANG: lambda p, lang: replace(p, lang=lang),
}


def done_text(p: Profile) -> str:
    return (
        f"You're set. I'll write on the {ordinal(p.invest_day or 1)} of each month, the morning "
        "you invest, with what history says about months like this one.\n\n"
        "Reply /help to see what I can do.\n\nResearch, not advice."
    )


def prompt(profile: Profile) -> Reply:
    """The email question for the profile's step, with onboarding's answer buttons, which
    render.plain turns into a "Reply with one of" line."""
    return Reply(EMAIL_TEXT[profile.step], telegram_prompt(profile, None).buttons)


def start(profile: Profile) -> Outcome:
    profile = replace(profile, step=EMAIL_STEPS[0])
    return Outcome(profile, None, (prompt(profile),))


def advance_email(profile: Profile, text: str) -> Outcome:
    if profile.step not in EMAIL_STEPS:
        return start(profile)
    value = QUESTIONS[profile.step].parse(text)
    if value is None:
        ask = prompt(profile)
        retry = Reply(f"{retry_line(profile.step, text)}\n\n{ask.text}", ask.buttons)
        return Outcome(profile, None, (retry,))
    profile = APPLY[profile.step](profile, value)
    i = EMAIL_STEPS.index(profile.step) + 1
    if i == len(EMAIL_STEPS):
        profile = replace(profile, step=Step.DONE)
        return Outcome(profile, None, (Reply(done_text(profile)),))
    profile = replace(profile, step=EMAIL_STEPS[i])
    return Outcome(profile, None, (prompt(profile),))
