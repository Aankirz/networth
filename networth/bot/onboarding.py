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
from networth.bot.holdings_words import BUCKET_WORDS
from networth.bot.message import Message, plain, say
from networth.bot.telegram import Button, Keyboard
from networth.money import money

CALLBACK_PREFIX: Final = "ob"


@dataclass(frozen=True)
class Reply:
    """A message and its buttons. A plain string is a message with one body block."""

    message: Message | str
    buttons: Keyboard = ()

    def __post_init__(self) -> None:
        if isinstance(self.message, str):
            object.__setattr__(self, "message", Message(body=(self.message,)))

    @property
    def text(self) -> str:
        return plain(self.message)  # type: ignore[arg-type]


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
# Every label the user sees has an English, Hindi and Hinglish version. A tapped button sends
# its value, never its label, and each parse also reads the labels in every language.

GOALS: Final = {
    "house": ("A house", ("house", "home", "flat", "ghar", "घर")),
    "retirement": ("Retirement", ("retire", "रिटायर")),
    "education": ("Education", ("education", "college", "school", "kids", "padhai", "पढ़ाई")),
    "growth": ("Just growing it", ("grow", "wealth", "badha", "बढ़ा")),
}
GOAL_LABELS: Final = {
    "hi": {"house": "घर", "retirement": "रिटायरमेंट", "education": "पढ़ाई",
           "growth": "बस पैसा बढ़ाना"},
    "hinglish": {"house": "Ghar", "retirement": "Retirement", "education": "Padhai",
                 "growth": "Bas paisa badhana"},
}  # fmt: skip
HORIZONS: Final = {2: "within 3 years", 4: "in about 4 years", 7: "in about 7 years",
                   15: "in 10+ years"}  # fmt: skip
HORIZON_WORDS: Final = {
    "hi": ({2: "3 साल के अंदर", 15: "10+ साल में"}, "लगभग {n} साल में"),
    "hinglish": ({2: "3 saal ke andar", 15: "10+ saal mein"}, "lagbhag {n} saal mein"),
}
HORIZON_BUTTONS: Final = (("Within 3 years", 2), ("3 to 5 years", 4), ("5 to 10 years", 7),
                          ("10+ years", 15))  # fmt: skip
HORIZON_LABELS: Final = {
    "hi": ("3 साल के अंदर", "3 से 5 साल", "5 से 10 साल", "10+ साल"),
    "hinglish": ("3 saal ke andar", "3 se 5 saal", "5 se 10 saal", "10+ saal"),
}
DROPS: Final = (10, 20, 30, 40)
DROP_WORDS: Final = {
    "en": ("40% or more", "up to {pct}%"),
    "hi": ("40% या उससे ज़्यादा", "{pct}% तक"),
    "hinglish": ("40% ya usse zyada", "{pct}% tak"),
}
DAYS: Final = (1, 5, 10, 15, 20, 25)
MAX_DAY: Final = 28
MAX_YEARS: Final = 60
EXCLUSIONS: Final = {
    "us_stocks": "US stocks",
    "crypto": "Crypto",
    "sin": "Tobacco, alcohol, gambling",
    "defence": "Defence",
}
EXCLUSION_LABELS: Final = {
    "hi": {"us_stocks": "US स्टॉक्स", "crypto": "क्रिप्टो", "sin": "तंबाकू, शराब, जुआ",
           "defence": "डिफ़ेंस"},
    "hinglish": {"us_stocks": "US stocks", "crypto": "Crypto",
                 "sin": "Tobacco, sharaab, jua", "defence": "Defence"},
}  # fmt: skip
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
OWN_PLAN_NAMES: Final = {"en": OWN_PLAN_NAME, "hi": "आपका अपना बँटवारा",
                         "hinglish": "Aapka apna split"}  # fmt: skip
BUCKETS: Final = ("safety", "core", "growth")
BUCKET_NAMES: Final = {lang: {b.value: words[lang] for b, words in BUCKET_WORDS.items()}
                       for lang in ("en", "hi", "hinglish")}  # fmt: skip
ORDER: Final = (Step.LANG, Step.GOAL, Step.HORIZON, Step.AMOUNT, Step.DAY, Step.DROP,
                Step.EXCLUDE, Step.PLAN)  # fmt: skip
FIX_LABELS: Final = {
    "en": ("Language", "Goal", "Time", "Amount", "Day", "Fall", "Left out", "Plan"),
    "hi": ("भाषा", "लक्ष्य", "समय", "रक़म", "तारीख़", "गिरावट", "बाहर रखा", "प्लान"),
    "hinglish": ("Language", "Goal", "Samay", "Amount", "Din", "Giravat", "Bahar rakha", "Plan"),
}
FIX_TARGETS: Final = tuple(zip(FIX_LABELS["en"], ORDER, strict=True))
DONE_WORDS: Final = ("done", "none", "nothing", "no", "हो गया", "कुछ नहीं", "ho gaya",
                     "kuch nahin", "kuch nahi")  # fmt: skip
BUTTON: Final = {
    "done": {"en": "Done", "hi": "हो गया", "hinglish": "Ho gaya"},
    "own": {"en": "My own split", "hi": "मेरा अपना बँटवारा", "hinglish": "Mera apna split"},
    "ok": {"en": "Looks right", "hi": "सही है", "hinglish": "Sahi hai"},
    "fix": {"en": "Fix something", "hi": "कुछ बदलना है", "hinglish": "Kuch badalna hai"},
}


# --- formatting ----------------------------------------------------------------------------


def ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def day_label(n: int, lang: str | None) -> str:
    return ordinal(n) if lang in (None, "en") else str(n)


def goal_label(goal: str, lang: str | None) -> str:
    return GOAL_LABELS.get(lang or "en", {}).get(goal) or GOALS[goal][0]


def horizon_label(years: int, lang: str | None = "en") -> str:
    if lang in HORIZON_WORDS:
        fixed, about = HORIZON_WORDS[lang]
        return fixed.get(years) or about.format(n=years)
    return HORIZONS.get(years) or f"in about {years} year{'' if years == 1 else 's'}"


def drop_label(pct: int, lang: str | None = "en") -> str:
    most, upto = say(DROP_WORDS, lang)  # type: ignore[arg-type]
    return most if pct >= DROPS[-1] else upto.format(pct=pct)


def exclusion_label(key: str, lang: str | None) -> str:
    return EXCLUSION_LABELS.get(lang or "en", {}).get(key) or EXCLUSIONS[key]


def plan_name(plan: Plan, lang: str | None = "en") -> str:
    if plan.name in STARTER_PLANS:
        return STARTER_PLANS[plan.name][0]
    return say(OWN_PLAN_NAMES, lang)


def plan_line(plan: Plan, lang: str | None = "en") -> str:
    names = BUCKET_NAMES.get(lang or "en", {})
    split = ", ".join(f"{plan.targets_pct[b]}% {names.get(b, b)}" for b in BUCKETS)
    return f"{plan_name(plan, lang)}. {split}"


SUMMARY: Final = {
    "en": "Here's what I have.\n\nGoal: {goal}, {horizon}\nEach month: {money} on the {day}\n"
    "A fall you can sit through: {drop}\nLeft out: {left_out}\nLanguage: {lang}\n"
    "Plan: {plan}\n\nLooks right?",
    "hi": "मेरे पास यह है।\n\nलक्ष्य: {goal}, {horizon}\nहर महीने: {money}, {day} तारीख़ को\n"
    "कितनी गिरावट झेल सकते हैं: {drop}\nबाहर रखा: {left_out}\nभाषा: {lang}\n"
    "प्लान: {plan}\n\nसब सही है?",
    "hinglish": "Mere paas yeh hai.\n\nGoal: {goal}, {horizon}\nHar mahine: {money}, {day} "
    "tareekh ko\nKitni giravat jhel sakte hain: {drop}\nBahar rakha: {left_out}\n"
    "Language: {lang}\nPlan: {plan}\n\nSab sahi hai?",
}
NOTHING: Final = {"en": "Nothing", "hi": "कुछ नहीं", "hinglish": "Kuch nahin"}


def summary(p: Profile, plan: Plan) -> str:
    lang = p.lang
    left_out = ", ".join(exclusion_label(k, lang) for k in p.exclude) or say(NOTHING, lang)
    return say(SUMMARY, lang).format(
        goal=goal_label(p.goal, lang), horizon=horizon_label(p.horizon_years, lang),
        money=money(p.monthly_amount or 0, p.currency, lang),
        day=day_label(p.invest_day, lang), drop=drop_label(p.drop_comfort, lang),
        left_out=left_out, lang=LANGS[p.lang][0], plan=plan_line(plan, lang))  # fmt: skip


DONE_TITLE: Final = {"en": "You're all set.", "hi": "सब तैयार है।",
                     "hinglish": "Sab taiyaar hai."}  # fmt: skip
DONE_BODY: Final = {
    "en": "I'll message you on the {day} of each month, the morning you invest, with what "
    "history says about months like this one.",
    "hi": "हर महीने {day} तारीख़ की सुबह, जिस दिन आप निवेश करते हैं, मैं बताऊँगा कि ऐसे महीनों के "
    "बारे में इतिहास क्या कहता है।",
    "hinglish": "Har mahine {day} tareekh ki subah, jis din aap invest karte hain, main "
    "bataoonga ki aise mahinon ke baare mein history kya kehti hai.",
}
DONE_HELP: Final = {
    "en": "Meanwhile, /help shows what I can do.",
    "hi": "तब तक, /help में मेरे सारे काम दिखते हैं।",
    "hinglish": "Tab tak, /help mein mere saare kaam dikhte hain.",
}


# "Get my brief now": networth.brief's tap prefix ("br"), answered by commands.on_brief_tap
# with briefs.brief_now, which never claims the day's brief, so the scheduled one still goes out.
BRIEF_NOW: Final = "br:now"
NOW_BUTTON: Final = {"en": "Get my brief now", "hi": "मेरी ब्रीफ़ अभी",
                     "hinglish": "Meri brief abhi"}  # fmt: skip
WANT_IT_NOW: Final = {"en": "Want it now?", "hi": "अभी भेज दूँ?", "hinglish": "Abhi bhej doon?"}
BRIEF_OFFER: Final = {
    "en": "I'll also send your brief on the {day} of every month. Want it now?",
    "hi": "आपकी ब्रीफ़ हर महीने {day} तारीख़ को भी आएगी। अभी भेज दूँ?",
    "hinglish": "Aapki brief har mahine {day} tareekh ko bhi aayegi. Abhi bhej doon?",
}


def brief_now_buttons(lang: str | None) -> Keyboard:
    return ((Button(say(NOW_BUTTON, lang), BRIEF_NOW),),)


def brief_offer(p: Profile) -> str:
    return say(BRIEF_OFFER, p.lang).format(day=day_label(p.invest_day or 1, p.lang))


def done_message(p: Profile) -> Message:
    lang = p.lang
    day = say(DONE_BODY, lang).format(day=day_label(p.invest_day or 1, lang))
    return Message(say(DONE_TITLE, lang), (day, say(WANT_IT_NOW, lang), say(DONE_HELP, lang)))


def done_reply(p: Profile) -> Reply:
    return Reply(done_message(p), brief_now_buttons(p.lang))


def with_lead(lead: str, ask: Reply) -> Reply:
    """The question with one line in front of it, its buttons kept."""
    m = ask.message
    assert isinstance(m, Message)
    return Reply(replace(m, body=(lead, *m.body)), ask.buttons)


# --- prompts -------------------------------------------------------------------------------

LANG_TEXT: Final = (
    "Hi. I'm Networth. I read the market news every day, and I'll check in on the day you "
    "invest.\nनमस्ते। मैं Networth हूँ।\n\nWhich language do you want? / आप किस भाषा में बात "
    "करना चाहेंगे?"
)
TEXT: Final[Mapping[Step, Mapping[str, str]]] = {
    Step.GOAL: {
        "en": "A few quick taps to set you up.\n\nWhat's this money for?",
        "hi": "सेटअप के लिए कुछ छोटे सवाल।\n\nयह पैसा किसलिए है?",
        "hinglish": "Setup ke liye kuch chhote sawaal.\n\nYeh paisa kis liye hai?",
    },
    Step.HORIZON: {
        "en": "When will you need it?",
        "hi": "यह पैसा कब काम आएगा?",
        "hinglish": "Yeh paisa kab tak kaam aayega?",
    },
    Step.AMOUNT: {
        "en": "About how much do you invest each month? Tap one, or type it like 25k, 1 lakh "
        "or $500.",
        "hi": "आप हर महीने लगभग कितना निवेश करते हैं? एक बटन दबा सकते हैं, या लिख सकते हैं, "
        "जैसे 25k, 1 lakh या $500।",
        "hinglish": "Aap har mahine lagbhag kitna invest karte hain? Ek button daba sakte hain, "
        "ya likh sakte hain, jaise 25k, 1 lakh ya $500.",
    },
    Step.DAY: {
        "en": "Which day of the month do you usually invest? I'll check in that morning.",
        "hi": "आप आमतौर पर महीने की किस तारीख़ को निवेश करते हैं? मैं उसी सुबह मैसेज करूँगा।",
        "hinglish": "Aap aam taur par mahine ki kis tareekh ko invest karte hain? Main usi "
        "subah message karoonga.",
    },
    Step.DROP: {
        "en": "Markets fall sometimes. In a bad year, how big a fall could you sit through "
        "without losing sleep?",
        "hi": "बाज़ार कभी-कभी गिरते हैं। किसी बुरे साल में, कितनी गिरावट आप बिना नींद खोए झेल "
        "सकते हैं?",
        "hinglish": "Market kabhi-kabhi girta hai. Kisi bure saal mein, kitni giravat aap bina "
        "neend khoye jhel sakte hain?",
    },
    Step.EXCLUDE: {
        "en": "Anything you want left out? Tap to toggle, then Done.",
        "hi": "कुछ बाहर रखना है? हर बटन दबाने पर वह बाहर या वापस होता है, फिर हो गया।",
        "hinglish": "Kuch bahar rakhna hai? Har button dabane par woh bahar ya wapas hota hai, "
        "phir Ho gaya.",
    },
    Step.PLAN: {
        "en": "Pick a starting plan, or make your own.\n\n"
        "Safe money (liquid, gilt, FD) is money you'll need soon.\n"
        "Broad index funds hold the whole market and are kept for years.\n"
        "Single shares or themes are single company shares and sector funds.\n\n"
        "Steady: 60% safe money, 40% broad index funds, 0% single shares or themes\n"
        "Balanced: 20% safe money, 70% broad index funds, 10% single shares or themes\n"
        "Ambitious: 10% safe money, 60% broad index funds, 30% single shares or themes",
        "hi": "शुरुआती प्लान चुन सकते हैं, या अपना बना सकते हैं।\n\n"
        "सुरक्षित पैसा (लिक्विड, गिल्ट, FD) वह पैसा है जो जल्दी काम आएगा।\n"
        "ब्रॉड इंडेक्स फ़ंड पूरे बाज़ार वाले फ़ंड हैं, जो सालों तक रखे जाते हैं।\n"
        "अलग शेयर या थीम का मतलब है एक-एक कंपनी के शेयर और सेक्टर फ़ंड।\n\n"
        "Steady: 60% सुरक्षित पैसा, 40% ब्रॉड इंडेक्स फ़ंड, 0% अलग शेयर या थीम\n"
        "Balanced: 20% सुरक्षित पैसा, 70% ब्रॉड इंडेक्स फ़ंड, 10% अलग शेयर या थीम\n"
        "Ambitious: 10% सुरक्षित पैसा, 60% ब्रॉड इंडेक्स फ़ंड, 30% अलग शेयर या थीम",
        "hinglish": "Ek starting plan chun sakte hain, ya apna bana sakte hain.\n\n"
        "Safe paisa (liquid, gilt, FD) woh paisa hai jo jaldi kaam aayega.\n"
        "Broad index funds poore bazaar wale funds hain, jo saalon tak rakhe jaate hain.\n"
        "Alag shares ya theme matlab ek-ek company ke shares aur sector funds.\n\n"
        "Steady: 60% safe paisa, 40% broad index funds, 0% alag shares ya theme\n"
        "Balanced: 20% safe paisa, 70% broad index funds, 10% alag shares ya theme\n"
        "Ambitious: 10% safe paisa, 60% broad index funds, 30% alag shares ya theme",
    },
    Step.OWN_SPLIT: {
        "en": "Type your split as three numbers that add up to 100: safe money, broad index funds, "
        "single shares or themes. For example: 20 70 10",
        "hi": "अपना बँटवारा तीन नंबरों में लिख सकते हैं, जिनका जोड़ 100 हो: सुरक्षित पैसा, ब्रॉड इंडेक्स फ़ंड, "
        "अलग शेयर या थीम। "
        "जैसे: 20 70 10",
        "hinglish": "Apna split teen numbers mein likh sakte hain, jinka jod 100 ho: safe paisa, "
        "broad index funds, alag shares ya theme. Jaise: 20 70 10",
    },
}  # fmt: skip
FIX_TEXT: Final = {
    "en": "What would you like to change?",
    "hi": "क्या बदलना है?",
    "hinglish": "Kya badalna hai?",
}


def exclude_keyboard(p: Profile) -> Keyboard:
    rows = tuple(((("✓ " if key in p.exclude else "") + exclusion_label(key, p.lang), key),)
                 for key in EXCLUSIONS)  # fmt: skip
    return keyboard(Step.EXCLUDE, (*rows, ((say(BUTTON["done"], p.lang), "done"),)))


def fix_keyboard(lang: str | None) -> Keyboard:
    labels = say(FIX_LABELS, lang)  # type: ignore[arg-type]
    pairs = tuple((label, str(step)) for label, step in zip(labels, ORDER, strict=True))
    return keyboard(Step.CONFIRM, (pairs[:3], pairs[3:6], pairs[6:]))


def ask(step: Step) -> Callable[[Profile, Plan | None], str]:
    return lambda p, plan: say(TEXT[step], p.lang)


def lang_reply(p: Profile, plan: Plan | None) -> Reply:
    return Reply(LANG_TEXT, keyboard(Step.LANG, (
        tuple((label, key) for key, (label, _) in LANGS.items()),)))  # fmt: skip


def goal_reply(p: Profile, plan: Plan | None) -> Reply:
    pairs = tuple((goal_label(g, p.lang), g) for g in GOALS)
    return Reply(ask(Step.GOAL)(p, plan), keyboard(Step.GOAL, (pairs[:2], pairs[2:])))


def horizon_reply(p: Profile, plan: Plan | None) -> Reply:
    labels = HORIZON_LABELS.get(p.lang or "en") or tuple(lb for lb, _ in HORIZON_BUTTONS)
    pairs = tuple((label, str(y)) for label, (_, y) in zip(labels, HORIZON_BUTTONS, strict=True))
    return Reply(ask(Step.HORIZON)(p, plan), keyboard(Step.HORIZON, (pairs[:2], pairs[2:])))


def amount_reply(p: Profile, plan: Plan | None) -> Reply:
    return Reply(ask(Step.AMOUNT)(p, plan), keyboard(Step.AMOUNT, (
        (("₹10,000", "10000"), ("₹25,000", "25000"), ("₹50,000", "50000")),
        (("₹1,00,000", "100000"), ("$500", "$500"), ("$1,000", "$1000")))))  # fmt: skip


def day_reply(p: Profile, plan: Plan | None) -> Reply:
    pairs = tuple((day_label(d, p.lang), str(d)) for d in DAYS)
    return Reply(ask(Step.DAY)(p, plan), keyboard(Step.DAY, (pairs[:3], pairs[3:])))


def drop_reply(p: Profile, plan: Plan | None) -> Reply:
    pairs = tuple((f"{d}%" if d < DROPS[-1] else say(DROP_WORDS, p.lang)[0], str(d))
                  for d in DROPS)  # fmt: skip
    return Reply(ask(Step.DROP)(p, plan), keyboard(Step.DROP, (pairs[:2], pairs[2:])))


def plan_reply(p: Profile, plan: Plan | None) -> Reply:
    return Reply(ask(Step.PLAN)(p, plan), keyboard(Step.PLAN, (
        tuple((label, key) for key, (label, _) in STARTER_PLANS.items()),
        ((say(BUTTON["own"], p.lang), OWN_PLAN),))))  # fmt: skip


def confirm_reply(p: Profile, plan: Plan | None) -> Reply:
    assert plan is not None
    return Reply(summary(p, plan), keyboard(Step.CONFIRM, (
        ((say(BUTTON["ok"], p.lang), "ok"), (say(BUTTON["fix"], p.lang), "fix")),)))  # fmt: skip


PROMPTS: Final[dict[Step, Callable[[Profile, Plan | None], Reply]]] = {
    Step.LANG: lang_reply,
    Step.GOAL: goal_reply,
    Step.HORIZON: horizon_reply,
    Step.AMOUNT: amount_reply,
    Step.DAY: day_reply,
    Step.DROP: drop_reply,
    Step.EXCLUDE: lambda p, plan: Reply(ask(Step.EXCLUDE)(p, plan), exclude_keyboard(p)),
    Step.PLAN: plan_reply,
    Step.OWN_SPLIT: lambda p, plan: Reply(ask(Step.OWN_SPLIT)(p, plan)),
    Step.CONFIRM: confirm_reply,
    Step.DONE: lambda p, plan: done_reply(p),
}


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


def labels_of(key: str, english: str, local: Mapping[str, Mapping[str, str]]) -> set[str]:
    return {key, english.lower(), *(table[key].lower() for table in local.values())}


def parse_exclude(text: str) -> str | None:
    lowered = text.strip().lower()
    if lowered in DONE_WORDS:
        return "done"
    return next((key for key, label in EXCLUSIONS.items()
                 if lowered in labels_of(key, label, EXCLUSION_LABELS)), None)  # fmt: skip


TOAST: Final = {
    "en": ("{label} left out", "{label} back in"),
    "hi": ("{label} बाहर रखा", "{label} वापस शामिल"),
    "hinglish": ("{label} bahar rakha", "{label} wapas shaamil"),
}


def apply_exclude(p: Profile, plan: Plan | None, key: str, now: str) -> Outcome:
    if key == "done":
        return move_on(p, plan, Step.EXCLUDE)
    leaving = key not in p.exclude
    exclude = (*p.exclude, key) if leaving else tuple(k for k in p.exclude if k != key)
    p = replace(p, exclude=exclude)
    out, back = say(TOAST, p.lang)  # type: ignore[arg-type]
    toast = (out if leaving else back).format(label=exclusion_label(key, p.lang))
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


def button_words(key: str) -> tuple[str, ...]:
    return tuple(label.lower() for label in BUTTON[key].values())


CONFIRM_WORDS: Final = {
    "ok": ("ok", "okay", "yes", "right", "correct", "haan", "हाँ", *button_words("ok")),
    "fix": ("fix", "change", "no", *button_words("fix")),
    **{str(step): (str(step), *(labels[i].lower() for labels in FIX_LABELS.values()))
       for i, step in enumerate(ORDER)},
}  # fmt: skip


def apply_confirm(p: Profile, plan: Plan | None, choice: str, now: str) -> Outcome:
    if choice == "ok":
        p = replace(p, step=Step.DONE)
        return Outcome(p, plan, (done_reply(p),))
    if choice == "fix":
        return Outcome(p, plan, (Reply(say(FIX_TEXT, p.lang), fix_keyboard(p.lang)),))
    p = replace(p, step=Step(choice))
    return Outcome(p, plan, (prompt(p, plan),))


Apply = Callable[[Profile, "Plan | None", object, str], Outcome]


@dataclass(frozen=True)
class Question:
    parse: Callable[[str], object | None]
    apply: Apply
    retry: Mapping[str, str]


RETRY: Final[Mapping[str, Mapping[str, str]]] = {
    "goal": {
        "en": "I didn't catch that. Tap one, or type house, retirement, education or grow it.",
        "hi": "यह समझ नहीं आया। एक बटन दबा सकते हैं, या घर, रिटायरमेंट, पढ़ाई या बढ़ाना लिख सकते हैं।",
        "hinglish": "Yeh samajh nahin aaya. Ek button daba sakte hain, ya ghar, retirement, "
        "padhai ya badhana likh sakte hain.",
    },
    "horizon": {
        "en": "I didn't catch that. Type the number of years, like 5.",
        "hi": "यह समझ नहीं आया। सालों की गिनती लिख सकते हैं, जैसे 5।",
        "hinglish": "Yeh samajh nahin aaya. Saalon ki ginti likh sakte hain, jaise 5.",
    },
    "amount": {
        "en": "I didn't catch that amount. Try something like 25k, 1 lakh or $500.",
        "hi": "यह रक़म समझ नहीं आई। 25k, 1 lakh या $500 जैसा कुछ लिख सकते हैं।",
        "hinglish": "Yeh amount samajh nahin aaya. 25k, 1 lakh ya $500 jaisa kuch likh sakte "
        "hain.",
    },
    "day": {
        "en": "I didn't catch that day. Type a number from 1 to 28.",
        "hi": "यह तारीख़ समझ नहीं आई। 1 से 28 तक का कोई नंबर लिख सकते हैं।",
        "hinglish": "Yeh tareekh samajh nahin aayi. 1 se 28 tak ka koi number likh sakte hain.",
    },
    "late_day": {
        "en": "Pick a day from 1 to 28, so every month has it.",
        "hi": "1 से 28 तक की कोई तारीख़ चुन सकते हैं, ताकि वह हर महीने में हो।",
        "hinglish": "1 se 28 tak ki koi tareekh chun sakte hain, taaki woh har mahine mein ho.",
    },
    "drop": {
        "en": "I didn't catch that. Type a percent, like 20.",
        "hi": "यह समझ नहीं आया। प्रतिशत लिख सकते हैं, जैसे 20।",
        "hinglish": "Yeh samajh nahin aaya. Percent likh sakte hain, jaise 20.",
    },
    "exclude": {
        "en": "I didn't catch that. Tap what to leave out, then Done.",
        "hi": "यह समझ नहीं आया। जो बाहर रखना है उसका बटन दबा सकते हैं, फिर हो गया।",
        "hinglish": "Yeh samajh nahin aaya. Jo bahar rakhna hai uska button daba sakte hain, "
        "phir Ho gaya.",
    },
    "lang": {
        "en": "I didn't catch that. Tap a language. / यह समझ नहीं आया, एक भाषा चुन सकते हैं।",
    },
    "plan": {
        "en": "I didn't catch that. Tap a plan, or My own split.",
        "hi": "यह समझ नहीं आया। कोई प्लान चुन सकते हैं, या मेरा अपना बँटवारा।",
        "hinglish": "Yeh samajh nahin aaya. Koi plan chun sakte hain, ya Mera apna split.",
    },
    "own_split": {
        "en": "Those need to be three numbers that add up to 100, like 20 70 10.",
        "hi": "तीन नंबर होने ज़रूरी हैं, जिनका जोड़ 100 हो, जैसे 20 70 10।",
        "hinglish": "Teen numbers zaroori hain, jinka jod 100 ho, jaise 20 70 10.",
    },
    "confirm": {
        "en": "Tap Looks right, or Fix something to change an answer.",
        "hi": "सही है दबा सकते हैं, या कोई जवाब बदलने के लिए कुछ बदलना है।",
        "hinglish": "Sahi hai daba sakte hain, ya koi jawab badalne ke liye Kuch badalna hai.",
    },
}  # fmt: skip
PLAN_WORDS: Final = {
    **{k: (k, label.lower()) for k, (label, _) in STARTER_PLANS.items()},
    OWN_PLAN: (OWN_PLAN, "my own", "custom", *button_words("own")),
}

QUESTIONS: Final[dict[Step, Question]] = {
    Step.LANG: Question(exact_words({k: words for k, (_, words) in LANGS.items()}),
                        setting("lang", Step.LANG), RETRY["lang"]),
    Step.GOAL: Question(match_words({k: words for k, (_, words) in GOALS.items()}),
                        setting("goal", Step.GOAL), RETRY["goal"]),
    Step.HORIZON: Question(int_in(1, MAX_YEARS), setting("horizon_years", Step.HORIZON),
                           RETRY["horizon"]),
    Step.AMOUNT: Question(parse_amount, apply_amount, RETRY["amount"]),
    Step.DAY: Question(int_in(1, MAX_DAY), setting("invest_day", Step.DAY), RETRY["day"]),
    Step.DROP: Question(parse_drop, setting("drop_comfort", Step.DROP), RETRY["drop"]),
    Step.EXCLUDE: Question(parse_exclude, apply_exclude, RETRY["exclude"]),
    Step.PLAN: Question(exact_words(PLAN_WORDS), apply_plan, RETRY["plan"]),
    Step.OWN_SPLIT: Question(parse_split, apply_split, RETRY["own_split"]),
    Step.CONFIRM: Question(exact_words(CONFIRM_WORDS), apply_confirm, RETRY["confirm"]),
}  # fmt: skip


def retry_line(step: Step, answer: str, lang: str | None = None) -> str:
    n = first_int(answer)
    if step is Step.DAY and n is not None and MAX_DAY < n <= 31:
        return say(RETRY["late_day"], lang)
    return say(QUESTIONS[step].retry, lang)


def advance(profile: Profile, plan: Plan | None, answer: str, now: str) -> Outcome:
    """One answer, typed or tapped, applied to the profile's current step."""
    question = QUESTIONS.get(profile.step)
    if question is None:
        return Outcome(profile, plan)
    value = question.parse(answer)
    if value is None:
        retry = retry_line(profile.step, answer, profile.lang)
        return Outcome(profile, plan, (with_lead(retry, prompt(profile, plan)),))
    return question.apply(profile, plan, value, now)
