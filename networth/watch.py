""" "Watch this for me", parsed: a watcher event type, a named company or topic, or a refusal.

    parsed = parse_watch("tell me if RBI changes rates")   # WatchRequest("type", ...)
    parsed = parse_watch("tell me when HDFC hits 1800")    # Refusal("HDFC")

A watch never maps to a price target or a trade trigger: any trade word, or a number right
after hits/crosses/falls to and the like, is a Refusal. A topic in TOPICS maps to its event
types. Anything else, once the asking words are stripped, is a name of 1 to 5 words matched
against confirmed story titles. Pure: no IO. Every reply here passes guard.check, and a reply
that quotes the user's own words falls back to a fixed one if those words would not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from networth import guard
from networth.app.store import WatchKind
from networth.bot.message import say
from networth.engine.model import EventType

MAX_ENTITY_WORDS: Final = 5


@dataclass(frozen=True)
class Topic:
    words: re.Pattern[str]
    types: tuple[EventType, ...]
    label: str


def _words(*alternatives: str) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{'|'.join(alternatives)})\b", re.IGNORECASE)


# Order matters where words overlap: "trade war" is a tariff story before it is a war.
TOPICS: Final = (
    Topic(_words("rbi", "repo rate", "reserve bank"), (EventType.RBI_HIKE, EventType.RBI_CUT),
          "RBI rate changes"),
    Topic(_words("fed", "fomc", "federal reserve"), (EventType.FED_HIKE, EventType.FED_CUT),
          "US Fed rate changes"),
    Topic(_words("bank stress", "bank failures?", "bank collapse", "banking crisis", "bank runs?"),
          (EventType.BANK_STRESS,), "bank stress"),
    Topic(_words("tariffs?", "trade war", "trade deal"), (EventType.TARIFF,), "tariffs"),
    Topic(_words("oil", "crude", "opec"), (EventType.OIL_SUPPLY,), "oil supply shocks"),
    Topic(_words("budget"), (EventType.UNION_BUDGET,), "the Union Budget"),
    Topic(_words("rupee", "inr"), (EventType.INR_SHOCK,), "big rupee moves"),
    Topic(_words("wars?", "conflicts?", "military", "invasion"), (EventType.MILITARY_CONFLICT,),
          "wars and military conflicts"),
    Topic(_words("pandemics?", "outbreaks?", "epidemics?"), (EventType.PANDEMIC,), "pandemics"),
    Topic(_words("elections?", "polls?"), (EventType.ELECTION,), "elections"),
)  # fmt: skip
TRADE_WORDS: Final = _words("buy", "sell", "target", "stop ?loss", "entry", "exit(?! polls?)",
                            "short(?:ing)?(?![- ]term)", "price")  # fmt: skip
PRICE_TRIGGER: Final = re.compile(
    r"\b(?:hits?|reach(?:es)?|cross(?:es)?|above|below|falls? to|goes to|touch(?:es)?)"
    r"\s*(?:rs\.?|₹|\$|inr)?\s*\d",
    re.IGNORECASE,
)
LEAD: Final = re.compile(
    r"^(?:(?:please|pls|can you|could you)\s+)*"
    r"(?:tell me (?:if|when|about)|let me know (?:if|when|about)?|alert me (?:if|when|about|on)?"
    r"|notify me (?:if|when|about)?|keep (?:me posted|an eye) on|update me on|watch(?: out for)?"
    r"|track|follow)\s*",
    re.IGNORECASE,
)
TAIL: Final = re.compile(r"(?:\s+(?:news|stocks?|shares|updates|for me|please))+$", re.IGNORECASE)
EDGES: Final = " \t\n.,!?;:'\"“”"

USAGE: Final = {
    "en": "Tell me what to watch, like: watch RBI rate changes, or watch HDFC Bank. I'll message "
    "you only when a confirmed story appears.",
    "hi": "किसी चीज़ पर नज़र रखने के लिए ऐसे लिख सकते हैं: watch RBI rate changes, या watch HDFC "
    "Bank। पुष्ट ख़बर आने पर ही मैं आपको मैसेज करूँगा।",
    "hinglish": "Kisi cheez par nazar rakhne ke liye aise likh sakte hain: watch RBI rate "
    "changes, ya watch HDFC Bank. Confirmed story aane par hi main aapko message karoonga.",
}
REFUSE_LEAD: Final = {
    "en": "I don't watch prices or tell anyone when to trade.",
    "hi": "मैं कीमतों पर नज़र नहीं रखता, और न ही किसी को बताता हूँ कि कब ट्रेड करना है।",
    "hinglish": "Main prices par nazar nahin rakhta, aur na hi kisi ko batata hoon ki kab trade "
    "karna hai.",
}
REFUSE_OFFER: Final = {
    "en": "I can tell you when a confirmed story about a company or an event appears. For "
    "example: watch RBI rate changes.",
    "hi": "किसी कंपनी या घटना के बारे में पुष्ट ख़बर आने पर मैं बता सकता हूँ। जैसे: watch RBI rate changes।",
    "hinglish": "Kisi company ya event ke baare mein confirmed story aane par main bata sakta "
    "hoon. Jaise: watch RBI rate changes.",
}
REFUSE_ENTITY: Final = {
    "en": "I can tell you when a confirmed story about {entity} appears: watch {entity}.",
    "hi": "{entity} के बारे में पुष्ट ख़बर आने पर मैं बता सकता हूँ: watch {entity}।",
    "hinglish": "{entity} ke baare mein confirmed story aane par main bata sakta hoon: watch "
    "{entity}.",
}
WATCHING: Final = {
    "en": "Watching {label}. I'll stay quiet until the watcher confirms a story about it. "
    "/watches shows your watches and stops them.",
    "hi": "{label} पर नज़र है। जब तक वॉचर इसके बारे में किसी ख़बर की पुष्टि नहीं करता, मैं चुप "
    "रहूँगा। /watches में आपकी सारी वॉच दिखती हैं, और वहीं से बंद होती हैं।",
    "hinglish": "{label} par nazar hai. Jab tak watcher iske baare mein koi story confirm nahin "
    "karta, main chup rahoonga. /watches mein aapki saari watches dikhti hain, aur wahin se band "
    "hoti hain.",
}
IT: Final = {"en": "it", "hi": "इस", "hinglish": "is"}
NO_WATCHES: Final = {
    "en": "You aren't watching anything yet. For example: watch RBI rate changes.",
    "hi": "अभी आप किसी चीज़ पर नज़र नहीं रख रहे। जैसे: watch RBI rate changes।",
    "hinglish": "Abhi aap kisi cheez par nazar nahin rakh rahe. Jaise: watch RBI rate changes.",
}
UNWATCH_USAGE: Final = {
    "en": "/unwatch and a number from /watches stops one, like /unwatch 1.",
    "hi": "/watches में दिए नंबर के साथ /unwatch लिखने पर वॉच बंद होती है, जैसे /unwatch 1।",
    "hinglish": "/watches wale number ke saath /unwatch likhne par watch band hoti hai, jaise "
    "/unwatch 1.",
}
WATCH_STOPPED: Final = {
    "en": "Stopped. That watch is off.",
    "hi": "बंद कर दिया। वह वॉच अब बंद है।",
    "hinglish": "Band kar diya. Woh watch ab band hai.",
}
AT_CAP: Final = {
    "en": "You already have {cap} watches, the most I keep. /watches lets you stop one first.",
    "hi": "आपकी पहले से {cap} वॉच हैं, जितनी मैं रखता हूँ। नई के लिए /watches से पहले कोई एक बंद कर सकते हैं।",
    "hinglish": "Aapki pehle se {cap} watches hain, jitni main rakhta hoon. Nayi ke liye "
    "/watches se pehle koi ek band kar sakte hain.",
}
STOPPED_LABEL: Final = {
    "en": "Stopped watching {label}.",
    "hi": "{label} पर नज़र रखना बंद किया।",
    "hinglish": "{label} par nazar rakhna band kiya.",
}


@dataclass(frozen=True)
class WatchRequest:
    kind: WatchKind
    target: str
    label: str


@dataclass(frozen=True)
class Refusal:
    entity: str | None  # the name the user meant, offered back as a watch they can set

    def text(self, lang: str | None = "en") -> str:
        generic = f"{say(REFUSE_LEAD, lang)} {say(REFUSE_OFFER, lang)}"
        if self.entity is None:
            return generic
        offer = say(REFUSE_ENTITY, lang).format(entity=self.entity)
        return safe(f"{say(REFUSE_LEAD, lang)} {offer}", generic)


def safe(text: str, fallback: str) -> str:
    """text when it passes the guard's word rules, else the fixed fallback."""
    return text if guard.check(text, text).ok else fallback


def watching(label: str, lang: str | None = "en") -> str:
    return safe(say(WATCHING, lang).format(label=label),
                say(WATCHING, lang).format(label=say(IT, lang)))  # fmt: skip


def at_cap(cap: int, lang: str | None = "en") -> str:
    return say(AT_CAP, lang).format(cap=cap)


def stopped(label: str, lang: str | None = "en") -> str:
    return safe(say(STOPPED_LABEL, lang).format(label=label), say(WATCH_STOPPED, lang))


def entity_of(text: str) -> str | None:
    """The name left once the asking words, the trade part and the tail words are gone."""
    rest = LEAD.sub("", text.strip(EDGES), count=1)
    cut = min((m.start() for p in (TRADE_WORDS, PRICE_TRIGGER) if (m := p.search(rest))),
              default=len(rest))  # fmt: skip
    name = TAIL.sub("", rest[:cut].strip(EDGES)).strip(EDGES)
    name = re.sub(r"^the\s+", "", name, flags=re.IGNORECASE)
    words = name.split()
    return " ".join(words) if 1 <= len(words) <= MAX_ENTITY_WORDS else None


def parse_watch(text: str) -> WatchRequest | Refusal | None:
    if TRADE_WORDS.search(text) or PRICE_TRIGGER.search(text):
        return Refusal(entity_of(text))
    topic = next((t for t in TOPICS if t.words.search(text)), None)
    if topic is not None:
        return WatchRequest("type", ",".join(topic.types), topic.label)
    name = entity_of(text)
    return WatchRequest("entity", name, name) if name else None
