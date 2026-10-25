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

USAGE: Final = (
    "Tell me what to watch, for example: watch RBI rate changes, or watch HDFC Bank. I'll "
    "message you only when a confirmed story appears."
)
REFUSE_LEAD: Final = "I don't watch prices or tell anyone when to trade."
REFUSAL_GENERIC: Final = (
    f"{REFUSE_LEAD} I can tell you when a confirmed story about a company or an event "
    "appears. Try: watch RBI rate changes."
)
WATCHING_GENERIC: Final = (
    "Watching it. I'll stay quiet until the watcher confirms a story about it. "
    "Type /watches to see or stop your watches."
)
NO_WATCHES: Final = "You have no watches. Try: watch RBI rate changes."
UNWATCH_USAGE: Final = "Type /unwatch and a number from /watches, like /unwatch 1."
WATCH_STOPPED: Final = "Stopped. That watch is off."


@dataclass(frozen=True)
class WatchRequest:
    kind: WatchKind
    target: str
    label: str


@dataclass(frozen=True)
class Refusal:
    entity: str | None  # the name the user meant, offered back as a watch they can set

    @property
    def text(self) -> str:
        if self.entity is None:
            return REFUSAL_GENERIC
        return safe(f"{REFUSE_LEAD} I can tell you when a confirmed story about {self.entity} "
                    f"appears. Try: watch {self.entity}.", REFUSAL_GENERIC)  # fmt: skip


def safe(text: str, fallback: str) -> str:
    """text when it passes the guard's word rules, else the fixed fallback."""
    return text if guard.check(text, text).ok else fallback


def watching(label: str) -> str:
    return safe(f"Watching {label}. I'll stay quiet until the watcher confirms a story about "
                "it. Type /watches to see or stop your watches.", WATCHING_GENERIC)  # fmt: skip


def at_cap(cap: int) -> str:
    return f"You already have {cap} watches, the most I keep. Type /watches to stop one first."


def stopped(label: str) -> str:
    return safe(f"Stopped watching {label}.", WATCH_STOPPED)


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
