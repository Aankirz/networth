"""The investing-day brief: the month's confirmed events, the user's own plan range, and what
history counted after events like these, written by code in English, Hindi or Hinglish.

    events = month_events(watcher_db, today)
    b = compose(events, profile, plan, rates_db, local_now, plan_range_for(plan, profile))
    b.message("hinglish")    # the Message: title, news, plan, history in the detail, footer

No model rewords it. In a month with a confirmed event the brief leads with the user's plan:
the fall it is built to sit through and, for rupee plans, how often a fall that big came in
replays of past markets, with the bad and middle case. The counts follow inside the
expandable detail, one engine row per line (networth.brief.lines). Nothing here ranks rows or
says what to do: rows keep a fixed order and the plan line names the user's own plan.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from networth import sim
from networth.app.store import Plan, Profile
from networth.bot.message import FOOTER, Message, say
from networth.bot.onboarding import STARTER_PLANS, format_money
from networth.bot.telegram import Button, Keyboard
from networth.brief.lines import Line, day_words, lang_of, odds_line, type_words
from networth.engine import odds as engine
from networth.engine.backtest import market_of
from networth.engine.model import EventType
from networth.memory import Callback
from networth.sim.data import MissingSeries
from networth.watcher.store import Store
from networth.web import names

MONTH_DAYS: Final = 31
MAX_LINES: Final = 4
MAX_NEWS_EVENTS: Final = 3
CALLBACK_PREFIX: Final = "br"
HOME_MARKET: Final = {"INR": "in", "USD": "us"}  # the market whose event leads the brief
NOON: Final = 12
EVENING: Final = 17
# News that tends to frighten people gets a line that names the feeling, not just the event.
STRESS_TYPES: Final = frozenset({
    EventType.BANK_STRESS, EventType.MILITARY_CONFLICT, EventType.PANDEMIC,
    EventType.OIL_SUPPLY, EventType.INR_SHOCK, EventType.TARIFF,
})  # fmt: skip

GREETING: Final = {
    "en": ("Morning.", "Afternoon.", "Evening."),
    "hi": ("सुप्रभात।", "नमस्ते।", "शुभ संध्या।"),
    "hinglish": ("Good morning.", "Good afternoon.", "Good evening."),
}
INVESTING_DAY: Final = {
    "en": "{greet} It's your investing day, and {amount} is ready.",
    "hi": "{greet} आज आपके निवेश का दिन है, और {amount} तैयार हैं।",
    "hinglish": "{greet} Aaj aapka investing day hai, aur {amount} ready hai.",
}
OTHER_DAY: Final = {
    "en": "{greet} Here's your brief for this month.",
    "hi": "{greet} इस महीने का आपका ब्रीफ़ यह रहा।",
    "hinglish": "{greet} Yeh raha is mahine ka aapka brief.",
}
NEWS: Final = {
    "en": "This month's news: {events}.",
    "hi": "इस महीने की ख़बर: {events}।",
    "hinglish": "Is mahine ki news: {events}.",
}
EVENT_ON: Final = {"en": "{title} on {day}", "hi": "{day} को {title}",
                   "hinglish": "{day} ko {title}"}  # fmt: skip
ROUGH: Final = {
    "en": "A rough stretch in the news: {events}. Shocks like this have happened before.",
    "hi": "ख़बरों में एक मुश्किल दौर: {events}। ऐसे झटके पहले भी आए हैं।",
    "hinglish": "News mein ek mushkil daur: {events}. Aise jhatke pehle bhi aaye hain.",
}
NOTHING_NEW: Final = {
    "en": "No confirmed news this month matched anything in our history. Nothing needs your "
    "attention.",
    "hi": "इस महीने की कोई पुष्ट ख़बर हमारे इतिहास की किसी घटना से मेल नहीं खाई। अभी किसी बात पर "
    "ध्यान देने की ज़रूरत नहीं है।",
    "hinglish": "Is mahine ki koi confirmed news hamari history ki kisi ghatna se match nahin "
    "hui. Abhi kisi baat par dhyaan dene ki zaroorat nahin hai.",
}
BUILT_FOR: Final = {
    "en": "Months like this are why you have a plan. Yours is built to sit through a fall of up "
    "to {limit}%.",
    "hi": "ऐसे ही महीनों के लिए आपका प्लान है। यह {limit}% तक की गिरावट सहने के लिए बना है।",
    "hinglish": "Aise mahine ke liye hi aapka plan hai. Yeh {limit}% tak ki giravat sehne ke "
    "liye bana hai.",
}
REPLAYS: Final = {
    "en": "In replays of past markets, a fall that big came in {hit}% of paths. Bad case "
    "{p10}, middle {median}.",
    "hi": "पुराने बाज़ारों को दोहराने पर इतनी बड़ी गिरावट {hit}% रास्तों में आई। बुरे हाल में {p10}, "
    "बीच में {median}।",
    "hinglish": "Purane markets ko dohraane par itni badi giravat {hit}% raaston mein aayi. Bure "
    "haal mein {p10}, beech mein {median}.",
}
YOUR_PLAN: Final = {
    "en": "Your plan: {name}, the one you chose.",
    "hi": "आपका प्लान: {name}, जो आपने चुना।",
    "hinglish": "Aapka plan: {name}, jo aapne chuna.",
}
NO_PLAN: Final = {
    "en": "You haven't picked a plan yet.",
    "hi": "आपने अभी कोई प्लान नहीं चुना है।",
    "hinglish": "Aapne abhi koi plan nahin chuna hai.",
}
OWN_PLAN_WORDS: Final = {"en": "your own split", "hi": "आपका अपना बँटवारा",
                         "hinglish": "aapka apna split"}  # fmt: skip
HISTORY_LEAD: Final = {
    "en": "What history counted:",
    "hi": "इतिहास ने क्या गिना:",
    "hinglish": "History ne kya gina:",
}
BUTTONS: Final = {
    "ok": {"en": "Got it", "hi": "ठीक है", "hinglish": "Theek hai"},
    "plan": {"en": "See my plan", "hi": "मेरा प्लान", "hinglish": "Mera plan"},
    "why": {"en": "Why these counts?", "hi": "ये गिनती क्यों?", "hinglish": "Yeh counts kyun?"},
    "board": {"en": "Every sector", "hi": "हर सेक्टर", "hinglish": "Har sector"},
    "page": {"en": "My page", "hi": "मेरा पेज", "hinglish": "Mera page"},
    "range": {"en": "My range", "hi": "मेरी रेंज", "hinglish": "Meri range"},
}


@dataclass(frozen=True)
class Event:
    """One confirmed event of the month, with the engine rows the watcher wrote for it."""

    type: str
    event_date: dt.date
    title: str
    odds: tuple[engine.OddsJSON, ...]  # the exact odds() dicts from its news-first Insights


def mid_sentence(title: str, lang: str) -> str:
    """A type title as it reads after a colon: "oil supply shock", but "RBI rate hike" keeps its
    capitals, and Devanagari has no case."""
    if lang == "hi" or len(title) < 2 or not title[1].islower():
        return title
    return title[0].lower() + title[1:]


@dataclass(frozen=True)
class Brief:
    """Everything the brief says, as data; message() words it in one language."""

    profile: Profile
    plan: Plan | None
    local: dt.datetime  # the user's own clock, for the greeting
    events: tuple[Event, ...]  # the month's events in the user's markets, lead first
    lines: tuple[Line, ...]
    range: sim.PlanRange | None = None
    memory: Callback | None = None

    @property
    def lead(self) -> Line | None:
        """The row the Why button opens."""
        return self.lines[0] if self.lines else None

    def message(self, lang: str | None) -> Message:
        lang = lang_of(lang)
        body = [self._news(lang)]
        if self.memory:
            body.append(self.memory.line(lang))
        if self.events and self.plan:
            body.append(self._built_for(lang))
        body.append(self._plan_line(lang))
        if self.lines:
            body.append(say(HISTORY_LEAD, lang))
        detail = tuple(line.words(lang) for line in self.lines)
        return Message(self._title(lang), tuple(body), detail, say(FOOTER, lang))

    def _title(self, lang: str) -> str:
        hour = self.local.hour
        greet = GREETING[lang][0 if hour < NOON else 1 if hour < EVENING else 2]
        if self.local.day != self.profile.invest_day:
            return say(OTHER_DAY, lang).format(greet=greet)
        amount = format_money(self.profile.monthly_amount or 0, self.profile.currency or "INR")
        return say(INVESTING_DAY, lang).format(greet=greet, amount=amount)

    def _news(self, lang: str) -> str:
        if not self.events:
            return say(NOTHING_NEW, lang)
        named = "; ".join(
            say(EVENT_ON, lang).format(title=mid_sentence(type_words(e.type, lang).title, lang),
                                       day=day_words(e.event_date, lang))
            for e in self.events[:MAX_NEWS_EVENTS])  # fmt: skip
        if any(e.type in STRESS_TYPES for e in self.events[:MAX_NEWS_EVENTS]):
            return say(ROUGH, lang).format(events=named)
        return say(NEWS, lang).format(events=named)

    def _built_for(self, lang: str) -> str:
        built = say(BUILT_FOR, lang).format(limit=self.plan.max_drop_ok)  # type: ignore[union-attr]
        if self.range is None:
            return built
        r = self.range
        replays = say(REPLAYS, lang).format(hit=r.hit_limit_pct, p10=sim.rupees(r.nominal_p10),
                                            median=sim.rupees(r.nominal_median))  # fmt: skip
        return f"{built}\n{replays}"

    def _plan_line(self, lang: str) -> str:
        if self.plan is None:
            return say(NO_PLAN, lang)
        name = (STARTER_PLANS[self.plan.name][0] if self.plan.name in STARTER_PLANS
                else say(OWN_PLAN_WORDS, lang))  # fmt: skip
        return say(YOUR_PLAN, lang).format(name=name)


def month_events(watcher_db: Path, today: dt.date) -> list[Event]:
    """Events with a news-first Insight dated in the last MONTH_DAYS, newest first."""
    if not watcher_db.exists():
        return []
    store = Store.open(watcher_db)
    try:
        titles = {s.id: s.title for s in store.stories()}
        insights = [i for i in store.insights() if i.trigger == "news"
                    and (today - i.event_date).days <= MONTH_DAYS]  # fmt: skip
    finally:
        store.close()
    events: dict[tuple[str, dt.date], list] = {}
    for i in insights:
        events.setdefault((i.type, i.event_date), []).append(i)
    out = [Event(t, d, titles.get(rows[0].story_id, t), tuple(r.odds for r in rows))
           for (t, d), rows in events.items()]  # fmt: skip
    return sorted(out, key=lambda e: e.event_date, reverse=True)


def _in_markets(asset: str, markets: Sequence[str]) -> bool:
    return market_of(asset).value in markets


def history(type: str, profile: Profile, assets: Sequence[str], rates_db: Path) -> Line | None:
    """The odds() line for the first asset with history in the user's markets, home market
    first, or None."""
    home = HOME_MARKET.get(profile.currency or "INR", "in")
    mine = sorted((a for a in assets if _in_markets(a, profile.markets)),
                  key=lambda a: not _in_markets(a, [home]))  # fmt: skip
    for asset in mine:
        try:
            row = engine.odds(type, asset, db=rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        return odds_line(type, row, row["n_episodes"], row["weak_signal"])
    return None


def scoreboard(event: Event, markets: Sequence[str], rates_db: Path) -> list[Line]:
    """The event's own Insight rows in the user's markets, then the first sector group of each
    of those markets, in names.SCOREBOARD_GROUPS order, up to MAX_LINES. No ranking."""
    lines = [odds_line(o["type"], o, o["n_episodes"], o["weak_signal"])
             for o in event.odds if _in_markets(o["asset"], markets)]  # fmt: skip
    for market in (m for m in names.SCOREBOARD_GROUPS if m in markets):
        group = names.SCOREBOARD_GROUPS[market][0]
        try:
            c = engine.compare(event.type, group, db=rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        shown = {line.asset for line in lines}
        lines += [odds_line(c["type"], a, c["n_episodes"], c["weak_signal"])
                  for a in c["assets"] if a["asset"] not in shown]  # fmt: skip
    return lines[:MAX_LINES]


def plan_range_for(plan: Plan | None, profile: Profile) -> sim.PlanRange | None:
    """The user's plan range, or None for a dollar plan, no plan or no table."""
    if plan is None:
        return None
    try:
        return sim.plan_range(plan, profile)
    except (sim.NotRupees, MissingSeries, ValueError):
        return None


def compose(
    events: Sequence[Event],
    profile: Profile,
    plan: Plan | None,
    rates_db: Path,
    local: dt.datetime,
    range: sim.PlanRange | None = None,
    memory: Callback | None = None,
) -> Brief:
    markets = profile.markets
    home = HOME_MARKET.get(profile.currency or "INR", "in")
    mine = [e for e in events if any(_in_markets(o["asset"], markets) for o in e.odds)]
    lead = sorted(mine, key=lambda e: not any(_in_markets(o["asset"], [home]) for o in e.odds))
    lines = tuple(scoreboard(lead[0], markets, rates_db)) if lead else ()
    return Brief(profile, plan, local, tuple(lead), lines, range, memory)


def buttons(b: Brief, lang: str | None, public_url: str | None,
            page_url: str | None = None) -> Keyboard:  # fmt: skip
    """Got it, See my plan and My range call back; every sector, the counts' trail and the
    user's own page open pages."""
    lang = lang_of(lang)
    first = (Button(say(BUTTONS["ok"], lang), f"{CALLBACK_PREFIX}:ok"),
             Button(say(BUTTONS["plan"], lang), f"{CALLBACK_PREFIX}:plan"))  # fmt: skip
    rows: list[tuple[Button, ...]] = [first]
    if b.lead is not None and public_url:
        lead = b.lead
        rows.append((Button(say(BUTTONS["why"], lang), "",
                            public_url + names.why_path(lead.type, lead.asset)),
                     Button(say(BUTTONS["board"], lang), "",
                            f"{public_url}/scoreboard/{lead.type}")))  # fmt: skip
    mine = (Button(say(BUTTONS["page"], lang), "", page_url),) if page_url else ()
    rows.append((*mine, Button(say(BUTTONS["range"], lang), f"{CALLBACK_PREFIX}:range")))
    return tuple(rows)
