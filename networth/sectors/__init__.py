"""The sector board: the day, week and month change of the main NSE sectors, each beside the
confirmed stories behind it.

    card = board(sources, now)           # the contract's SectorsCard
    msg = board_message(card, public_url)  # what /sectors sends on Telegram

Prices are Yahoo's daily closes of the NSE indices. Stories are the watcher's confirmed ones
from the last STORY_DAYS days whose titles name the sector's words or whose event type is one
the sector moves on; up to three, newest first. A sector whose prices can't be read is left out
and named in the note. Nothing is estimated.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Final

from networth.bot.message import Link, Message
from networth.ratings.sources import Closes, Seen, Sources

STORY_DAYS: Final = 7
MAX_STORIES: Final = 3
WEEK, MONTH = 5, 21  # sessions
FLAT: Final = 0.001  # under 0.1% either way reads as flat


@dataclass(frozen=True)
class Sector:
    key: str
    name: str
    ticker: str  # Yahoo's symbol for the NSE index, checked live 2026-10-25
    words: tuple[str, ...]  # matched as whole words; short all-caps words match case
    types: tuple[str, ...] = ()  # watcher event types this sector moves on


SECTORS: Final = (
    Sector("bank", "Bank", "^NSEBANK", ("bank", "banks", "banking", "lender", "lenders", "RBI",
           "repo", "NPA", "deposit"), ("bank_stress", "rbi_hike", "rbi_cut")),
    Sector("it", "IT", "^CNXIT", ("IT", "software", "Infosys", "TCS", "Wipro", "HCLTech",
           "outsourcing", "H-1B"), ()),
    Sector("pharma", "Pharma", "^CNXPHARMA", ("pharma", "drug", "drugmaker", "USFDA", "FDA",
           "pharmaceutical"), ("pandemic",)),
    Sector("auto", "Auto", "^CNXAUTO", ("auto", "automaker", "car", "cars", "vehicle", "EV",
           "Maruti", "Mahindra", "Tata Motors"), ()),
    Sector("fmcg", "FMCG", "^CNXFMCG", ("FMCG", "consumer goods", "rural demand", "Hindustan "
           "Unilever", "Nestle", "ITC"), ()),
    Sector("metal", "Metal", "^CNXMETAL", ("metal", "metals", "steel", "aluminium", "copper",
           "iron ore", "Hindalco", "JSW"), ("tariff",)),
    Sector("energy", "Energy", "^CNXENERGY", ("oil", "crude", "OPEC", "gas", "Reliance", "ONGC",
           "power", "fuel"), ("oil_supply",)),
    Sector("realty", "Realty", "^CNXREALTY", ("real estate", "realty", "housing", "property",
           "DLF", "home loan"), ("rbi_hike", "rbi_cut")),
    Sector("psu", "PSU", "^CNXPSE", ("PSU", "PSUs", "public sector", "state-run", "disinvestment"),
           ("union_budget",)),
    Sector("midcap", "Midcap", "^NSEMDCP50", ("midcap", "midcaps", "mid-cap"), ()),
    Sector("smallcap", "Smallcap", "NIFTYSMLCAP250.NS", ("smallcap", "smallcaps", "small-cap"),
           ()),
)  # fmt: skip
BY_KEY: Final = {s.key: s for s in SECTORS}


def _pattern(word: str) -> re.Pattern[str]:
    flags = 0 if word.isupper() and len(word) <= 4 else re.IGNORECASE
    return re.compile(rf"(?<![\w-]){re.escape(word)}(?![\w-])", flags)


def stories_for(sector: Sector, stories: Sequence[Seen]) -> list[Seen]:
    pats = [_pattern(w) for w in sector.words]
    hit = [s for s in stories if (s.type in sector.types)
           or any(p.search(t) for t in s.titles for p in pats)]  # fmt: skip
    return sorted(hit, key=lambda s: s.day, reverse=True)[:MAX_STORIES]


def change(c: Closes, sessions: int) -> float | None:
    s = c.series
    return float(s.iloc[-1] / s.iloc[-1 - sessions] - 1) if len(s) > sessions else None


def signed(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:+.1f}%"


def direction(x: float | None) -> str:
    return "flat" if x is None or abs(x) < FLAT else "up" if x > 0 else "down"


def row(sector: Sector, c: Closes, stories: Sequence[Seen], public_url: str | None) -> dict:
    day = change(c, 1)
    told = [{"title": s.title, "day": s.day.isoformat(), "publishers": list(s.publishers)}
            for s in stories_for(sector, stories)]  # fmt: skip
    return {"key": sector.key, "name": sector.name, "day": signed(day),
            "week": signed(change(c, WEEK)), "month": signed(change(c, MONTH)),
            "direction": direction(day), "stories": told, "source": asdict(c.source),
            "url": f"{public_url or ''}/r/sector-{sector.key}"}  # fmt: skip


def board(src: Sources, now: dt.datetime, public_url: str | None = None) -> dict:
    """The contract's SectorsCard. NSE sectors, so the currency is INR."""
    told = src.stories(now - dt.timedelta(days=STORY_DAYS))
    stories = told.items if told else ()
    rows, unread = [], []
    for sector in SECTORS:
        try:
            c = src.closes(sector.ticker, "3mo")
        except Exception:  # noqa: BLE001 - one index failing leaves the rest of the board
            c = None
        if c is None or len(c.series) < 2:
            unread.append(sector.name)
            continue
        rows.append(row(sector, c, stories, public_url))
    notes = []
    if unread:
        notes.append(f"No prices for {', '.join(unread)} right now.")
    if told is None:
        notes.append("The watcher's stories aren't available, so moves show without news.")
    as_of = max((r["source"]["as_of"] for r in rows), default=now.date().isoformat())
    return {"type": "sectors", "as_of": as_of, "rows": rows,
            "note": " ".join(notes) or None, "currency": "INR"}  # fmt: skip


DOTS: Final = {"up": "🟢", "down": "🔴", "flat": "⚪"}


def board_message(card: dict, public_url: str | None = None) -> Message:
    if not card["rows"]:
        return Message("Sector moves", (card["note"] or "No sector prices right now.",))
    lines = []
    for r in sorted(card["rows"], key=lambda r: r["day"].startswith("-")):
        line = (f"{DOTS[r['direction']]} {r['name']} {r['day']} today, {r['week']} this week, "
                f"{r['month']} this month")  # fmt: skip
        for s in r["stories"]:
            line += f"\n   · {s['title']} ({', '.join(s['publishers'][:2])})"
        lines.append(line)
    body: list = ["\n".join(lines)]
    if card["note"]:
        body.append(card["note"])
    body.append(f"Prices: Yahoo Finance, NSE index closes to {card['as_of']}. News: confirmed by "
                "the Networth watcher.")  # fmt: skip
    if public_url:
        body.append(Link("Open the sector board", f"{public_url}/r/sectors"))
    return Message(f"Sector moves to {card['as_of']}", tuple(body))
