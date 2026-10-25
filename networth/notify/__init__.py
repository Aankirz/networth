"""The news notifier: one Telegram message when a confirmed story moves something the user
owns, or its sector, or the index their plan follows.

    sent = run_notify(store, bot, services, now)     # after each watcher cycle, in run_watcher

It rides the watcher's own schedule and the outbox; there is no scheduler here. Per user: at
most MAX_PER_DAY a day (IST), nothing in quiet hours (22:00 to 08:00 IST; the story waits for
the next cycle), nothing once they type /alerts off, nothing when paused or stopped. A story
reaches a user once, claimed before sending and released if the send fails.

The message says what happened (the confirmed story and who reported it), the price move with
its source and date, what that move means in the user's own money, and our rating when it moved
since we last told them. Watches are left to networth.bot.watches, so nobody hears twice.
"""

from __future__ import annotations

import datetime as dt
import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from networth.app.services import Services
from networth.app.store import Profile, Status, Step, Store
from networth.bot.message import Link, Message
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Bot
from networth.holdings.model import from_json
from networth.holdings.prices import symbols
from networth.ratings.model import Rating, money
from networth.ratings.sources import LiveSources, Seen, Sources, mentions, stories_from
from networth.sectors import BY_KEY, Sector, stories_for

log = logging.getLogger("networth.notify")

IST: Final = ZoneInfo("Asia/Kolkata")
MAX_PER_DAY: Final = 3
QUIET_FROM, QUIET_TO = 22, 8  # IST hours
FRESH: Final = dt.timedelta(hours=24)
NOTIFY_DB: Final = "notify.sqlite"
NIFTY: Final = Sector("nifty", "Nifty 50", "^NSEI", ("Nifty", "Sensex", "Dalal Street"), ())
SCHEMA: Final = """
CREATE TABLE IF NOT EXISTS sent (user_id TEXT NOT NULL, story TEXT NOT NULL, day TEXT NOT NULL,
  text TEXT NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY (user_id, story));
CREATE TABLE IF NOT EXISTS views (user_id TEXT NOT NULL, symbol TEXT NOT NULL,
  view TEXT NOT NULL, PRIMARY KEY (user_id, symbol));
"""

Rater = Callable[[str], Rating | None]


@dataclass(frozen=True)
class Target:
    kind: str  # "holding" | "sector" | "index", most specific first
    label: str  # "HDFC Bank", "the Bank sector", "the Nifty 50"
    ticker: str  # Yahoo symbol whose move is quoted
    value: float  # the user's money in it, in currency; 0 when we don't know
    currency: str
    words: tuple[str, ...] = ()
    sector: Sector | None = None
    symbol: str | None = None  # what rate() takes, for a holding


class Claims:
    """data/notify.sqlite: what each user was told, and the last rating view they saw."""

    def __init__(self, path: Path) -> None:
        self.path = path
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, isolation_level=None)

    def claim(self, user_id: str, story: str, day: str, text: str) -> bool:
        """True when under today's cap and this story is new to this user; one transaction."""
        with self._conn() as c:
            c.execute("BEGIN IMMEDIATE")
            n = c.execute("SELECT COUNT(*) FROM sent WHERE user_id = ? AND day = ?",
                          (user_id, day)).fetchone()[0]  # fmt: skip
            if n >= MAX_PER_DAY:
                c.execute("COMMIT")
                return False
            cur = c.execute(
                "INSERT OR IGNORE INTO sent VALUES (?, ?, ?, ?, ?)",
                (user_id, story, day, text, dt.datetime.now(dt.UTC).isoformat()),
            )
            c.execute("COMMIT")
            return cur.rowcount == 1

    def release(self, user_id: str, story: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM sent WHERE user_id = ? AND story = ?", (user_id, story))

    def swap_view(self, user_id: str, symbol: str, view: str) -> str | None:
        """Store this view; return the one before it, if any."""
        with self._conn() as c:
            row = c.execute("SELECT view FROM views WHERE user_id = ? AND symbol = ?",
                            (user_id, symbol)).fetchone()  # fmt: skip
            c.execute("INSERT OR REPLACE INTO views VALUES (?, ?, ?)", (user_id, symbol, view))
        return row[0] if row else None


def quiet(now: dt.datetime) -> bool:
    h = now.astimezone(IST).hour
    return h >= QUIET_FROM or h < QUIET_TO


def wants(p: Profile) -> bool:
    return p.step is Step.DONE and p.status is Status.ACTIVE and p.alerts_on


def targets(store: Store, p: Profile, src: Sources) -> list[Target]:
    """What the user owns, the sectors of what they own, and the index their plan follows."""
    out: list[Target] = []
    raw = store.holdings_data(p.user_id)
    held = from_json(raw).items if raw else ()
    for h in held:
        value = h.units * (h.price or h.avg_cost)
        tickers = symbols(h)
        if not tickers:
            continue
        info = src.stock(tickers[0])
        name = info.name if info else h.name
        sector = sector_for(info.sector, info.industry) if info else None
        out.append(Target("holding", short(name), tickers[0], value, h.currency,
                          (short(name), tickers[0].split(".")[0]), sector,
                          tickers[0].split(".")[0]))  # fmt: skip
    for t in [t for t in out if t.sector is not None]:
        in_it = sum(x.value for x in out if x.sector == t.sector and x.currency == t.currency)
        out.append(Target("sector", f"the {t.sector.name} sector", t.sector.ticker, in_it,
                          t.currency, sector=t.sector))  # fmt: skip
    if store.get_plan(p.user_id) is not None:
        inr = sum(x.value for x in out if x.kind == "holding" and x.currency == "INR")
        out.append(Target("index", "the Nifty 50", NIFTY.ticker, inr, "INR", sector=NIFTY))
    return out


def short(name: str) -> str:
    from networth.ratings.kinds import short_name

    return short_name(name)


def sector_for(sector: str | None, industry: str | None) -> Sector | None:
    from networth.ratings.kinds import IN_INDUSTRY, IN_SECTOR

    hit = IN_INDUSTRY.get(industry or "") or IN_SECTOR.get(sector or "")
    return next((s for s in BY_KEY.values() if hit and s.ticker == hit[0]), None)


def matched(t: Target, stories: Sequence[Seen]) -> list[Seen]:
    if t.kind == "holding":
        return mentions(stories, t.words)
    return stories_for(t.sector, stories) if t.sector else []


def move_line(t: Target, src: Sources) -> tuple[str, float] | None:
    c = src.closes(t.ticker, "1mo")
    if c is None or len(c.series) < 2:
        return None
    move = float(c.series.iloc[-1] / c.series.iloc[-2] - 1)
    return (f"{t.label[0].upper()}{t.label[1:]} moved {move * 100:+.1f}% on the last close "
            f"({c.source.name}, {c.source.as_of}).", move)  # fmt: skip


def money_line(t: Target, move: float, p: Profile) -> str | None:
    if t.value > 0:
        return (f"On your {money(t.value, t.currency)} in it, that is about "
                f"{signed_money(t.value * move, t.currency)}.")  # fmt: skip
    if p.monthly_amount and p.currency:
        return (f"On your monthly {money(p.monthly_amount, p.currency)}, a move like that is "
                f"{signed_money(p.monthly_amount * move, p.currency)}.")  # fmt: skip
    return None


def signed_money(n: float, currency: str) -> str:
    body = money(abs(n), currency)
    return f"−{body}" if round(n) < 0 else f"+{body}" if round(n) > 0 else body


def rating_line(t: Target, p: Profile, rater: Rater, claims: Claims,
                public_url: str | None) -> list:  # fmt: skip
    if t.kind != "holding" or t.symbol is None:
        return []
    try:
        r = rater(t.symbol)
    except Exception:  # noqa: BLE001 - an alert without its rating line still goes out
        log.warning("rating for an alert failed")
        return []
    if r is None:
        return []
    before = claims.swap_view(p.user_id, r.symbol, r.view.value)
    if before is None or before == r.view.value:
        return []
    line: list = [f"Our rating moved from {before} to {r.view.value} ({r.score}/100)."]
    if public_url:
        line.append(Link("See the rating and its sources", f"{public_url}/r/{r.slug}"))
    return line


def message(t: Target, s: Seen, p: Profile, src: Sources, rater: Rater, claims: Claims,
            public_url: str | None) -> Message:  # fmt: skip
    named = ", ".join(s.publishers[:3])
    body: list = [f"{s.title.rstrip('.')}.\nConfirmed by {len(s.publishers)} publishers: {named}."]
    moved = move_line(t, src)
    if moved:
        worth = money_line(t, moved[1], p)
        body.append(moved[0] + (f"\n{worth}" if worth else ""))
    body += rating_line(t, p, rater, claims, public_url)
    return Message(f"News on {t.label}", tuple(body))


def story_key(s: Seen) -> str:
    return f"{s.day.isoformat()}:{s.title}"


def notify_user(store: Store, bot: Bot, services: Services, p: Profile, stories: Sequence[Seen],
                src: Sources, rater: Rater, claims: Claims, day: str) -> int:  # fmt: skip
    sent, told = 0, set()
    for t in targets(store, p, src):
        for s in matched(t, stories):
            if story_key(s) in told:
                continue
            told.add(story_key(s))
            if not claims.claim(p.user_id, story_key(s), day, s.title):
                continue
            try:
                m = message(t, s, p, src, rater, claims, services.public_url)
                if send(store, bot, p, Reply(m), proactive=True, mail=services.mail):
                    sent += 1
                    continue
            except Exception:
                log.exception("news alert for %s failed", p.user_id)
            claims.release(p.user_id, story_key(s))
    return sent


def run_notify(store: Store, bot: Bot, services: Services, now: dt.datetime, *,
               sources: Sources | None = None, rater: Rater | None = None) -> int:  # fmt: skip
    """How many news alerts went out."""
    if quiet(now) or not services.watcher_db.exists():
        return 0
    stories = stories_from(services.watcher_db, now - FRESH).items
    if not stories:
        return 0
    src = sources or LiveSources(services.watcher_db)
    if rater is None:
        from networth.ratings import rate

        def rater(symbol: str) -> Rating | None:
            return rate(symbol, now=now, sources=src)

    claims = Claims(services.data_dir / NOTIFY_DB)
    day = now.astimezone(IST).date().isoformat()
    return sum(notify_user(store, bot, services, p, stories, src, rater, claims, day)
               for p in store.profiles() if wants(p))  # fmt: skip
