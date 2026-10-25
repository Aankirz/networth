"""Onboarding as a pure state machine: (profile, plan, answer) in, new state and replies out.

    outcome = advance(profile, plan, "25k", now)

Each question step is one QUESTIONS entry holding its prompt, its parse and its apply. A tapped
button carries a value that the same parse reads, so taps and typed answers share one path.
Bad input never raises: it gets a short retry line and the same question again.

After an answer the next step is CONFIRM when every question is answered and a plan exists,
otherwise the step's successor. That one rule makes "Fix something" work with no extra state:
the user answers the field they picked and lands back on the summary.

No IO here. The caller stores the outcome and sends the replies.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Final, Literal

from networth.app.store import INDIA_TZ, US_TZ, Plan, Profile, Step
from networth.bot.telegram import Button, Keyboard

CALLBACK_PREFIX: Final = "ob"


@dataclass(frozen=True)
class Reply:
    text: str
    buttons: Keyboard = ()


@dataclass(frozen=True)
class Outcome:
    profile: Profile
    plan: Plan | None
    replies: tuple[Reply, ...] = ()
    toast: str | None = None
    edit_buttons: Keyboard | None = None


@dataclass(frozen=True)
class Money:
    amount: int
    currency: Literal["INR", "USD"]


def callback(step: Step, value: str) -> str:
    return f"{CALLBACK_PREFIX}:{step}:{value}"


def keyboard(step: Step, rows: tuple[tuple[tuple[str, str], ...], ...]) -> Keyboard:
    return tuple(tuple(Button(label, callback(step, value)) for label, value in row)
                 for row in rows)  # fmt: skip


# --- parsing typed and tapped answers ------------------------------------------------------

FIRST_INT: Final = re.compile(r"(?<![\d.-])\d+")
AMOUNT: Final = re.compile(
    r"(?<![\d.])(-?)(\d[\d,]*(?:\.\d+)?)\s*"
    r"(k|thousand|lakhs?|lacs?|l|crores?|cr|million|mn|m)?(?![a-z])"
)
MULTIPLIERS: Final = {
    "k": 1_000, "thousand": 1_000, "l": 100_000, "lakh": 100_000, "lakhs": 100_000,
    "lac": 100_000, "lacs": 100_000, "cr": 10_000_000, "crore": 10_000_000,
    "crores": 10_000_000, "m": 1_000_000, "mn": 1_000_000, "million": 1_000_000,
}  # fmt: skip
USD_MARKERS: Final = re.compile(r"\$|\busd\b|\bdollars?\b")
# A monthly amount below these is a misread answer ("5 years" at the amount step), not a plan.
MIN_AMOUNT: Final = {"INR": 100, "USD": 10}


def first_int(text: str) -> int | None:
    match = FIRST_INT.search(text)
    return int(match.group()) if match else None


def int_in(low: int, high: int) -> Callable[[str], int | None]:
    def parse(text: str) -> int | None:
        n = first_int(text)
        return n if n is not None and low <= n <= high else None

    return parse


def parse_amount(text: str) -> Money | None:
    """'1 lakh', '1.5L', '₹50,000', '50k', '$500', '500 dollars', '10,00,000' -> Money."""
    lowered = text.strip().lower()
    match = AMOUNT.search(lowered)
    if not match or match.group(1):
        return None
    number = float(match.group(2).replace(",", ""))
    amount = round(number * MULTIPLIERS.get(match.group(3) or "", 1))
    currency = "USD" if USD_MARKERS.search(lowered) else "INR"
    return Money(amount, currency) if amount >= MIN_AMOUNT[currency] else None


def match_words(table: Mapping[str, tuple[str, ...]]) -> Callable[[str], str | None]:
    """The first key whose words appear in the text, as a substring."""

    def parse(text: str) -> str | None:
        lowered = text.strip().lower()
        return next((key for key, words in table.items()
                     if any(w in lowered for w in words)), None)  # fmt: skip

    return parse


def exact_words(table: Mapping[str, tuple[str, ...]]) -> Callable[[str], str | None]:
    """The key one of whose words equals the whole answer."""

    def parse(text: str) -> str | None:
        lowered = text.strip().lower()
        return next((key for key, words in table.items() if lowered in words), None)

    return parse


# --- the domain tables ---------------------------------------------------------------------

GOALS: Final = {
    "house": ("A house", ("house", "home", "flat")),
    "retirement": ("Retirement", ("retire",)),
    "education": ("Education", ("education", "college", "school", "kids")),
    "growth": ("Just growing it", ("grow", "wealth")),
}
HORIZONS: Final = {2: "within 3 years", 4: "in about 4 years", 7: "in about 7 years",
                   15: "in 10+ years"}  # fmt: skip
HORIZON_BUTTONS: Final = (("Within 3 years", 2), ("3 to 5 years", 4), ("5 to 10 years", 7),
                          ("10+ years", 15))  # fmt: skip
DROPS: Final = (10, 20, 30, 40)
DAYS: Final = (1, 5, 10, 15, 20, 25)
MAX_DAY: Final = 28
MAX_YEARS: Final = 60
EXCLUSIONS: Final = {
    "us_stocks": "US stocks",
    "crypto": "Crypto",
    "sin": "Tobacco, alcohol, gambling",
    "defence": "Defence",
}
LANGS: Final = {
    "en": ("English", ("en", "english")),
    "hi": ("हिंदी", ("hi", "hindi", "हिंदी", "हिन्दी")),
    "hinglish": ("Hinglish", ("hinglish",)),
}
STARTER_PLANS: Final = {
    "steady": ("Steady", (60, 40, 0)),
    "balanced": ("Balanced", (20, 70, 10)),
    "ambitious": ("Ambitious", (10, 60, 30)),
}
OWN_PLAN: Final = "own"
OWN_PLAN_NAME: Final = "Your own split"
BUCKETS: Final = ("safety", "core", "growth")
FIX_TARGETS: Final = (
    ("Goal", Step.GOAL), ("Time", Step.HORIZON), ("Amount", Step.AMOUNT), ("Day", Step.DAY),
    ("Fall", Step.DROP), ("Left out", Step.EXCLUDE), ("Language", Step.LANG),
    ("Plan", Step.PLAN),
)  # fmt: skip
ORDER: Final = (Step.GOAL, Step.HORIZON, Step.AMOUNT, Step.DAY, Step.DROP, Step.EXCLUDE,
                Step.LANG, Step.PLAN)  # fmt: skip
DONE_WORDS: Final = ("done", "none", "nothing", "no")


# --- formatting ----------------------------------------------------------------------------


def ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def indian_grouping(n: int) -> str:
    digits = str(n)
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    pairs = [head[max(0, i - 2) : i] for i in range(len(head), 0, -2)]
    return ",".join(reversed(pairs)) + "," + tail


def format_money(amount: int, currency: str) -> str:
    return f"${amount:,}" if currency == "USD" else f"₹{indian_grouping(amount)}"


def horizon_label(years: int) -> str:
    return HORIZONS.get(years) or f"in about {years} year{'' if years == 1 else 's'}"


def drop_label(pct: int) -> str:
    return "40% or more" if pct >= DROPS[-1] else f"up to {pct}%"


def plan_line(plan: Plan) -> str:
    name = STARTER_PLANS[plan.name][0] if plan.name in STARTER_PLANS else OWN_PLAN_NAME
    split = ", ".join(f"{plan.targets_pct[b]}% {b}" for b in BUCKETS)
    return f"{name}. {split}"


def summary(p: Profile, plan: Plan) -> str:
    left_out = ", ".join(EXCLUSIONS[k] for k in p.exclude) or "Nothing"
    money = format_money(p.monthly_amount or 0, p.currency or "INR")
    return (
        "Here's what I have.\n\n"
        f"Goal: {GOALS[p.goal][0]}, {horizon_label(p.horizon_years)}\n"
        f"Each month: {money} on the {ordinal(p.invest_day)}\n"
        f"A fall you can sit through: {drop_label(p.drop_comfort)}\n"
        f"Left out: {left_out}\n"
        f"Language: {LANGS[p.lang][0]}\n"
        f"Plan: {plan_line(plan)}\n\n"
        "Looks right?"
    )


def done_text(p: Profile) -> str:
    return (
        f"You're all set. I'll message you on the {ordinal(p.invest_day)} of each month, the "
        "morning you invest, with what history says about months like this one.\n\n"
        "Meanwhile, type /help to see what I can do.\n\n"
        "Research, not advice."
    )


# --- prompts -------------------------------------------------------------------------------

GOAL_TEXT: Final = (
    "Hi. I read the market news every day so you don't have to, and I'll check in on the day "
    "you invest. A few quick taps to set you up.\n\nWhat's this money for?"
)
PLAN_TEXT: Final = (
    "Pick a starting plan, or make your own. These are common mixes, shown for "
    "education. The plan is always your choice.\n\n"
    "Safety is money you'll need soon: FDs, liquid funds.\n"
    "Core is broad index funds you hold for years.\n"
    "Growth is single stocks and sectors.\n\n"
    "Steady: 60% safety, 40% core, 0% growth\n"
    "Balanced: 20% safety, 70% core, 10% growth\n"
    "Ambitious: 10% safety, 60% core, 30% growth"
)
FIX_TEXT: Final = "What would you like to change?"


def exclude_keyboard(p: Profile) -> Keyboard:
    rows = tuple(((("✓ " if key in p.exclude else "") + label, key),)
                 for key, label in EXCLUSIONS.items())  # fmt: skip
    return keyboard(Step.EXCLUDE, (*rows, (("Done", "done"),)))


def fix_keyboard() -> Keyboard:
    pairs = tuple((label, str(step)) for label, step in FIX_TARGETS)
    return keyboard(Step.CONFIRM, (pairs[:3], pairs[3:6], pairs[6:]))


PROMPTS: Final[dict[Step, Callable[[Profile, Plan | None], Reply]]] = {
    Step.GOAL: lambda p, plan: Reply(GOAL_TEXT, keyboard(Step.GOAL, (
        (("A house", "house"), ("Retirement", "retirement")),
        (("Education", "education"), ("Just growing it", "growth"))))),
    Step.HORIZON: lambda p, plan: Reply("When will you need it?", keyboard(Step.HORIZON, (
        tuple((label, str(y)) for label, y in HORIZON_BUTTONS[:2]),
        tuple((label, str(y)) for label, y in HORIZON_BUTTONS[2:])))),
    Step.AMOUNT: lambda p, plan: Reply(
        "About how much do you invest each month? Tap one, or type it like 25k, 1 lakh or $500.",
        keyboard(Step.AMOUNT, (
            (("₹10,000", "10000"), ("₹25,000", "25000"), ("₹50,000", "50000")),
            (("₹1,00,000", "100000"), ("$500", "$500"), ("$1,000", "$1000"))))),
    Step.DAY: lambda p, plan: Reply(
        "Which day of the month do you usually invest? I'll check in that morning.",
        keyboard(Step.DAY, (tuple((ordinal(d), str(d)) for d in DAYS[:3]),
                            tuple((ordinal(d), str(d)) for d in DAYS[3:])))),
    Step.DROP: lambda p, plan: Reply(
        "Markets fall sometimes. In a bad year, how big a fall could you sit through without "
        "losing sleep?",
        keyboard(Step.DROP, ((("10%", "10"), ("20%", "20")), (("30%", "30"),
                                                              ("40% or more", "40"))))),
    Step.EXCLUDE: lambda p, plan: Reply(
        "Anything you want left out? Tap to toggle, then Done.", exclude_keyboard(p)),
    Step.LANG: lambda p, plan: Reply("Which language do you want me to use?", keyboard(
        Step.LANG, (tuple((label, key) for key, (label, _) in LANGS.items()),))),
    Step.PLAN: lambda p, plan: Reply(PLAN_TEXT, keyboard(Step.PLAN, (
        tuple((label, key) for key, (label, _) in STARTER_PLANS.items()),
        (("My own split", OWN_PLAN),)))),
    Step.OWN_SPLIT: lambda p, plan: Reply(
        "Type your split as three numbers that add up to 100: safety, core, growth. "
        "For example: 20 70 10"),
    Step.CONFIRM: lambda p, plan: Reply(summary(p, plan), keyboard(
        Step.CONFIRM, ((("Looks right", "ok"), ("Fix something", "fix")),))),
    Step.DONE: lambda p, plan: Reply(done_text(p)),
}  # fmt: skip


def prompt(profile: Profile, plan: Plan | None) -> Reply:
    return PROMPTS[profile.step](profile, plan)


# --- transitions ---------------------------------------------------------------------------


def is_complete(p: Profile) -> bool:
    return None not in (p.goal, p.horizon_years, p.monthly_amount, p.invest_day,
                        p.drop_comfort, p.lang)  # fmt: skip


def move_on(profile: Profile, plan: Plan | None, answered: Step) -> Outcome:
    if plan is not None and plan.max_drop_ok != profile.drop_comfort:
        plan = replace(plan, max_drop_ok=profile.drop_comfort)
    if is_complete(profile) and plan is not None:
        step = Step.CONFIRM
    else:
        step = ORDER[ORDER.index(answered) + 1]
    profile = replace(profile, step=step)
    return Outcome(profile, plan, (prompt(profile, plan),))


def setting(field: str, step: Step) -> Apply:
    def apply(p: Profile, plan: Plan | None, value: object, now: str) -> Outcome:
        return move_on(replace(p, **{field: value}), plan, step)

    return apply


def with_money(p: Profile, money: Money) -> Profile:
    """The amount, its currency, and the time zone that currency implies."""
    tz = US_TZ if money.currency == "USD" else INDIA_TZ
    return replace(p, monthly_amount=money.amount, currency=money.currency, tz=tz)


def apply_amount(p: Profile, plan: Plan | None, money: Money, now: str) -> Outcome:
    return move_on(with_money(p, money), plan, Step.AMOUNT)


def parse_drop(text: str) -> int | None:
    n = first_int(text)
    if n is None or not 0 < n <= 100:
        return None
    return min(DROPS, key=lambda d: abs(d - n))


def parse_exclude(text: str) -> str | None:
    lowered = text.strip().lower()
    if lowered in DONE_WORDS:
        return "done"
    return next((key for key, label in EXCLUSIONS.items()
                 if lowered in (key, label.lower())), None)  # fmt: skip


def apply_exclude(p: Profile, plan: Plan | None, key: str, now: str) -> Outcome:
    if key == "done":
        return move_on(p, plan, Step.EXCLUDE)
    leaving = key not in p.exclude
    exclude = (*p.exclude, key) if leaving else tuple(k for k in p.exclude if k != key)
    p = replace(p, exclude=exclude)
    toast = f"{EXCLUSIONS[key]} {'left out' if leaving else 'back in'}"
    return Outcome(p, plan, toast=toast, edit_buttons=exclude_keyboard(p))


def make_plan(p: Profile, name: str, split: tuple[int, int, int], now: str) -> Plan:
    return Plan(p.user_id, name, dict(zip(BUCKETS, split, strict=True)), p.drop_comfort or 0, now)


def apply_plan(p: Profile, plan: Plan | None, name: str, now: str) -> Outcome:
    if name == OWN_PLAN:
        p = replace(p, step=Step.OWN_SPLIT)
        return Outcome(p, plan, (prompt(p, plan),))
    return move_on(p, make_plan(p, name, STARTER_PLANS[name][1], now), Step.PLAN)


def parse_split(text: str) -> tuple[int, int, int] | None:
    numbers = tuple(int(n) for n in re.findall(r"\d+", text))
    if len(numbers) != len(BUCKETS) or sum(numbers) != 100 or max(numbers) > 100:
        return None
    return numbers  # type: ignore[return-value]


def apply_split(p: Profile, plan: Plan | None, split: tuple[int, int, int], now: str) -> Outcome:
    return move_on(p, make_plan(p, OWN_PLAN, split, now), Step.PLAN)


CONFIRM_WORDS: Final = {
    "ok": ("ok", "okay", "yes", "looks right", "right", "correct"),
    "fix": ("fix", "fix something", "change", "no"),
    **{str(step): (str(step), label.lower()) for label, step in FIX_TARGETS},
}


def apply_confirm(p: Profile, plan: Plan | None, choice: str, now: str) -> Outcome:
    if choice == "ok":
        p = replace(p, step=Step.DONE)
        return Outcome(p, plan, (Reply(done_text(p)),))
    if choice == "fix":
        return Outcome(p, plan, (Reply(FIX_TEXT, fix_keyboard()),))
    p = replace(p, step=Step(choice))
    return Outcome(p, plan, (prompt(p, plan),))


Apply = Callable[[Profile, "Plan | None", object, str], Outcome]


@dataclass(frozen=True)
class Question:
    parse: Callable[[str], object | None]
    apply: Apply
    retry: str


AMOUNT_RETRY: Final = "I didn't catch that amount. Try something like 25k, 1 lakh or $500."
DAY_RETRY: Final = "I didn't catch that day. Type a number from 1 to 28."
LATE_DAY_RETRY: Final = "Pick a day from 1 to 28, so every month has it."

QUESTIONS: Final[dict[Step, Question]] = {
    Step.GOAL: Question(
        match_words({k: words for k, (_, words) in GOALS.items()}), setting("goal", Step.GOAL),
        "I didn't catch that. Tap one, or type house, retirement, education or growth."),
    Step.HORIZON: Question(
        int_in(1, MAX_YEARS), setting("horizon_years", Step.HORIZON),
        "I didn't catch that. Type the number of years, like 5."),
    Step.AMOUNT: Question(parse_amount, apply_amount, AMOUNT_RETRY),
    Step.DAY: Question(int_in(1, MAX_DAY), setting("invest_day", Step.DAY), DAY_RETRY),
    Step.DROP: Question(parse_drop, setting("drop_comfort", Step.DROP),
                        "I didn't catch that. Type a percent, like 20."),
    Step.EXCLUDE: Question(parse_exclude, apply_exclude,
                           "I didn't catch that. Tap what to leave out, then Done."),
    Step.LANG: Question(exact_words({k: words for k, (_, words) in LANGS.items()}),
                        setting("lang", Step.LANG), "I didn't catch that. Tap a language."),
    Step.PLAN: Question(
        exact_words({**{k: (k, label.lower()) for k, (label, _) in STARTER_PLANS.items()},
                     OWN_PLAN: (OWN_PLAN, "my own", "my own split", "custom")}),
        apply_plan, "I didn't catch that. Tap a plan, or My own split."),
    Step.OWN_SPLIT: Question(
        parse_split, apply_split,
        "Those need to be three numbers that add up to 100, like 20 70 10."),
    Step.CONFIRM: Question(exact_words(CONFIRM_WORDS), apply_confirm,
                           "Tap Looks right, or Fix something to change an answer."),
}  # fmt: skip


def retry_line(step: Step, answer: str) -> str:
    n = first_int(answer)
    if step is Step.DAY and n is not None and MAX_DAY < n <= 31:
        return LATE_DAY_RETRY
    return QUESTIONS[step].retry


def advance(profile: Profile, plan: Plan | None, answer: str, now: str) -> Outcome:
    """One answer, typed or tapped, applied to the profile's current step."""
    question = QUESTIONS.get(profile.step)
    if question is None:
        return Outcome(profile, plan)
    value = question.parse(answer)
    if value is None:
        ask = prompt(profile, plan)
        return Outcome(profile, plan, (Reply(f"{retry_line(profile.step, answer)}\n\n{ask.text}",
                                             ask.buttons),))  # fmt: skip
    return question.apply(profile, plan, value, now)
