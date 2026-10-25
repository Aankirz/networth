"""The user data model and $DATA_DIR/networth.sqlite, the only module that knows its schema.

    store = Store(data_dir)
    profile = store.get_profile("tg:42")

Tables: profiles (one per chat), plans (one per user, rewritten on change), messages (every
text in and out), briefs (one per user per investing day) and alerts (one per user per event).
contacts maps a Keiki conversation to our user; outbox holds email waiting for a Keiki turn;
keiki_turns holds every turn id answered; link_codes holds the single-use codes that tie an
email contact to a Telegram user; watches are standing per-user requests, and watch_hits holds
one row per watch per confirmed story it matched, claimed before the message goes out;
asked_terms holds glossary terms a user asked about, until a brief brings one back.
holdings holds one user's holdings list as networth.holdings writes it (never an image), and
snaptrade_users the SnapTrade user secret behind a broker link; both go when the user stops.
A brief or an alert row is claimed before the message goes out, so a retried trigger never
sends it twice. Each operation opens its own short connection,
because webhook handlers run on a threadpool. The schema is created on first use and migrated
additively: a column missing from an older file is added, so opening twice is a no-op.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

DB_NAME: Final = "networth.sqlite"
INDIA_TZ: Final = "Asia/Kolkata"
US_TZ: Final = "America/New_York"
LINK_TOKEN_BYTES: Final = 16
LINK_CODE_DIGITS: Final = 6
LINK_CODE_TRIES: Final = 5
US_STOCKS: Final = "us_stocks"
ALL_MARKETS: Final = ("in", "us")


class Channel(StrEnum):
    TELEGRAM = "telegram"
    EMAIL = "email"  # Keiki's AgentMail inbox


CHANNEL: Final = Channel.TELEGRAM
EMAIL_USER_PREFIX: Final = "kk:"
SLACK_CONTACT_PREFIX: Final = "slack:"  # a Slack author's contact; every other one is an email
EMAIL_USER_CHARS: Final = 16


class Status(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class Step(StrEnum):
    GOAL = "goal"
    HORIZON = "horizon"
    AMOUNT = "amount"
    DAY = "day"
    DROP = "drop"
    EXCLUDE = "exclude"
    LANG = "lang"
    PLAN = "plan"
    OWN_SPLIT = "own_split"
    CONFIRM = "confirm"
    DONE = "done"


@dataclass(frozen=True)
class Profile:
    user_id: str  # "tg:<chat_id>", or "kk:<hash of the Keiki conversation>" for email users
    channel: str
    chat_id: int  # 0 for a profile that began by email and has no Telegram chat
    step: Step
    link_token: str
    created_at: str
    updated_at: str
    status: Status = Status.ACTIVE
    tz: str = INDIA_TZ
    lang: str | None = None
    invest_day: int | None = None
    alerts_on: bool = True
    goal: str | None = None
    horizon_years: int | None = None
    drop_comfort: int | None = None
    monthly_amount: int | None = None
    currency: str | None = None
    exclude: tuple[str, ...] = ()
    deliver_to: Channel = Channel.TELEGRAM  # where proactive messages (briefs, alerts) go

    @property
    def markets(self) -> tuple[str, ...]:
        return tuple(m for m in ALL_MARKETS if not (m == "us" and US_STOCKS in self.exclude))


@dataclass(frozen=True)
class Plan:
    user_id: str
    name: str  # "steady" | "balanced" | "ambitious" | "own"
    targets_pct: Mapping[str, int]  # {"safety", "core", "growth"} summing to 100
    max_drop_ok: int
    written_at: str


WatchKind = Literal["type", "entity"]


@dataclass(frozen=True)
class Watch:
    id: int
    user_id: str
    kind: WatchKind
    target: str  # comma-joined event types for "type", the name as typed for "entity"
    label: str  # what the user is told they are watching
    created_at: str
    stopped_at: str | None = None

    @property
    def types(self) -> tuple[str, ...]:
        return tuple(self.target.split(",")) if self.kind == "type" else ()


@dataclass(frozen=True)
class OutMail:
    id: int
    user_id: str
    address: str
    text: str
    created_at: str


@dataclass(frozen=True)
class Message:
    id: int
    user_id: str
    direction: Literal["in", "out"]
    text: str
    insight_id: str | None
    numbers_used: tuple[str, ...]
    sent_at: str


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def user_id_for(chat_id: int) -> str:
    return f"tg:{chat_id}"


def new_profile(chat_id: int, now: str) -> Profile:
    return Profile(
        user_id=user_id_for(chat_id), channel=CHANNEL, chat_id=chat_id, step=Step.GOAL,
        link_token=secrets.token_urlsafe(LINK_TOKEN_BYTES), created_at=now, updated_at=now,
    )  # fmt: skip


def email_user_id(address: str) -> str:
    """A hash, so log lines that name the user never carry an email address."""
    digest = hashlib.sha256(address.encode()).hexdigest()[:EMAIL_USER_CHARS]
    return f"{EMAIL_USER_PREFIX}{digest}"


def new_email_profile(address: str, now: str) -> Profile:
    return Profile(
        user_id=email_user_id(address), channel=Channel.EMAIL, chat_id=0, step=Step.GOAL,
        link_token=secrets.token_urlsafe(LINK_TOKEN_BYTES), created_at=now, updated_at=now,
        deliver_to=Channel.EMAIL,
    )  # fmt: skip


COLUMNS: Final[dict[str, dict[str, str]]] = {
    "profiles": {
        "user_id": "TEXT PRIMARY KEY", "channel": "TEXT NOT NULL", "chat_id": "INTEGER NOT NULL",
        "step": "TEXT NOT NULL", "status": "TEXT NOT NULL", "tz": "TEXT NOT NULL", "lang": "TEXT",
        "link_token": "TEXT NOT NULL", "invest_day": "INTEGER",
        "alerts_on": "INTEGER NOT NULL DEFAULT 1", "goal": "TEXT", "horizon_years": "INTEGER",
        "drop_comfort": "INTEGER", "monthly_amount": "INTEGER", "currency": "TEXT",
        "markets": "TEXT NOT NULL DEFAULT '[]'", "exclude": "TEXT NOT NULL DEFAULT '[]'",
        "deliver_to": "TEXT NOT NULL DEFAULT 'telegram'",
        "created_at": "TEXT NOT NULL", "updated_at": "TEXT NOT NULL",
    },
    "plans": {
        "user_id": "TEXT PRIMARY KEY", "name": "TEXT NOT NULL", "targets_pct": "TEXT NOT NULL",
        "max_drop_ok": "INTEGER NOT NULL", "written_at": "TEXT NOT NULL",
    },
    "messages": {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT", "user_id": "TEXT NOT NULL",
        "direction": "TEXT NOT NULL CHECK (direction IN ('in', 'out'))", "text": "TEXT NOT NULL",
        "insight_id": "TEXT", "numbers_used": "TEXT NOT NULL DEFAULT '[]'",
        "sent_at": "TEXT NOT NULL",
    },
    "updates": {"update_id": "INTEGER PRIMARY KEY", "seen_at": "TEXT NOT NULL"},
    "briefs": {
        "user_id": "TEXT NOT NULL", "day": "TEXT NOT NULL", "text": "TEXT NOT NULL DEFAULT ''",
        "used": "TEXT NOT NULL DEFAULT ''", "sent_at": "TEXT NOT NULL",
        "inputs": "TEXT NOT NULL DEFAULT ''",
    },
    "answers": {"user_id": "TEXT NOT NULL", "at": "TEXT NOT NULL"},
    "alerts": {
        "user_id": "TEXT NOT NULL", "event_key": "TEXT NOT NULL", "month": "TEXT NOT NULL",
        "text": "TEXT NOT NULL", "sent_at": "TEXT NOT NULL",
    },
    "contacts": {
        "address": "TEXT PRIMARY KEY", "user_id": "TEXT NOT NULL", "linked_at": "TEXT NOT NULL",
    },
    "keiki_turns": {"turn_id": "TEXT PRIMARY KEY", "seen_at": "TEXT NOT NULL"},
    "link_codes": {
        "code": "TEXT PRIMARY KEY", "user_id": "TEXT NOT NULL", "expires_at": "TEXT NOT NULL",
        "used_at": "TEXT",
    },
    "watches": {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT", "user_id": "TEXT NOT NULL",
        "kind": "TEXT NOT NULL CHECK (kind IN ('type', 'entity'))", "target": "TEXT NOT NULL",
        "label": "TEXT NOT NULL", "created_at": "TEXT NOT NULL", "stopped_at": "TEXT",
    },
    "watch_hits": {
        "user_id": "TEXT NOT NULL", "watch_id": "INTEGER NOT NULL", "match_key": "TEXT NOT NULL",
        "month": "TEXT NOT NULL", "sent_at": "TEXT NOT NULL",
    },
    "asked_terms": {
        "user_id": "TEXT NOT NULL", "term": "TEXT NOT NULL", "asked_at": "TEXT NOT NULL",
        "used_at": "TEXT",
    },
    "holdings": {
        "user_id": "TEXT PRIMARY KEY", "data": "TEXT NOT NULL", "updated_at": "TEXT NOT NULL",
    },
    "snaptrade_users": {
        "user_id": "TEXT PRIMARY KEY", "snaptrade_user_id": "TEXT NOT NULL",
        "user_secret": "TEXT NOT NULL", "created_at": "TEXT NOT NULL",
    },
    "outbox": {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT", "user_id": "TEXT NOT NULL",
        "address": "TEXT NOT NULL", "text": "TEXT NOT NULL", "created_at": "TEXT NOT NULL",
        "sent_at": "TEXT",
    },
}  # fmt: skip


def migrate(conn: sqlite3.Connection) -> None:
    for table, columns in COLUMNS.items():
        body = ", ".join(f'"{name}" {decl}' for name, decl in columns.items())
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({body})")
        present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in present:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN "{name}" {decl}')
    conn.execute("CREATE INDEX IF NOT EXISTS messages_user ON messages (user_id, id)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS briefs_user_day ON briefs (user_id, day)")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS alerts_user_event ON alerts (user_id, event_key)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS watch_hits_key ON watch_hits (watch_id, match_key)"
    )


KEPT_ON_SAVE: Final = ("user_id", "link_token")
FORGOTTEN_ON_STOP: Final = ("holdings", "snaptrade_users")


def _profile_row(p: Profile) -> dict[str, object]:
    row: dict[str, object] = {f.name: getattr(p, f.name) for f in fields(p)}
    row["alerts_on"] = int(p.alerts_on)
    row["exclude"] = json.dumps(list(p.exclude))
    row["markets"] = json.dumps(list(p.markets))
    return row


def _profile_from(row: sqlite3.Row) -> Profile:
    values = {f.name: row[f.name] for f in fields(Profile)}
    values["step"] = Step(row["step"])
    values["status"] = Status(row["status"])
    values["alerts_on"] = bool(row["alerts_on"])
    values["exclude"] = tuple(json.loads(row["exclude"]))
    values["deliver_to"] = Channel(row["deliver_to"])
    return Profile(**values)


def _watches(conn: sqlite3.Connection, where: str, args: tuple) -> list[Watch]:
    rows = conn.execute(f"SELECT * FROM watches WHERE {where} ORDER BY id", args).fetchall()
    return [Watch(r["id"], r["user_id"], r["kind"], r["target"], r["label"], r["created_at"],
                  r["stopped_at"]) for r in rows]  # fmt: skip


class Store:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / DB_NAME
        self._migrated = False
        self._lock = threading.Lock()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self._migrated:
            with self._lock:
                if not self._migrated:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self._open() as conn:
                        conn.execute("PRAGMA journal_mode=WAL")
                        migrate(conn)
                    self._migrated = True
        with self._open() as conn:
            yield conn

    @contextmanager
    def _open(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def get_profile(self, user_id: str) -> Profile | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
        return _profile_from(row) if row else None

    def save_profile(self, profile: Profile) -> None:
        """Insert, or update every column but link_token, which only new_link_token changes,
        so a turn holding an older copy of the profile never revives a retired link. Saving a
        stopped profile deletes the user's holdings and broker link in the same transaction."""
        row = _profile_row(profile)
        names = ", ".join(f'"{n}"' for n in row)
        marks = ", ".join("?" for _ in row)
        updates = ", ".join(f'"{n}" = excluded."{n}"' for n in row if n not in KEPT_ON_SAVE)
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO profiles ({names}) VALUES ({marks}) "
                f"ON CONFLICT(user_id) DO UPDATE SET {updates}",
                tuple(row.values()),
            )
            if profile.status is Status.STOPPED:
                for table in FORGOTTEN_ON_STOP:
                    conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (profile.user_id,))

    def get_plan(self, user_id: str) -> Plan | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM plans WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return Plan(row["user_id"], row["name"], json.loads(row["targets_pct"]),
                    row["max_drop_ok"], row["written_at"])  # fmt: skip

    def save_plan(self, plan: Plan) -> None:
        row = {f.name: getattr(plan, f.name) for f in fields(plan)}
        row["targets_pct"] = json.dumps(dict(plan.targets_pct))
        self._upsert("plans", row)

    def log_message(self, user_id: str, direction: Literal["in", "out"], text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (user_id, direction, text, sent_at) VALUES (?, ?, ?, ?)",
                (user_id, direction, text, now_iso()),
            )

    def claim_update(self, update_id: int) -> bool:
        """True the first time an update id is seen. Telegram delivers at least once."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO updates (update_id, seen_at) VALUES (?, ?)",
                (update_id, now_iso()),
            )
        return cursor.rowcount == 1

    def claim_turn(self, turn_id: str) -> bool:
        """True the first time a Keiki turn id is seen, so a replayed turn is answered once."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO keiki_turns (turn_id, seen_at) VALUES (?, ?)",
                (turn_id, now_iso()),
            )
        return cursor.rowcount == 1

    def profiles(self) -> list[Profile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM profiles ORDER BY user_id").fetchall()
        return [_profile_from(r) for r in rows]

    def new_link_token(self, user_id: str) -> str:
        """A fresh page token for this user. Every link signed with the old one stops working."""
        token = secrets.token_urlsafe(LINK_TOKEN_BYTES)
        with self._connect() as conn:
            conn.execute("UPDATE profiles SET link_token = ? WHERE user_id = ?", (token, user_id))
        return token

    def profile_by_token(self, link_token: str) -> Profile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE link_token = ?", (link_token,)
            ).fetchone()
        return _profile_from(row) if row else None

    def claim_brief(self, user_id: str, day: str) -> bool:
        """True the first time this user's brief for this day is claimed."""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO briefs (user_id, day, sent_at) VALUES (?, ?, ?)",
                (user_id, day, now_iso()),
            )
        return cursor.rowcount == 1

    def release_brief(self, user_id: str, day: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM briefs WHERE user_id = ? AND day = ?", (user_id, day))

    def save_brief(self, user_id: str, day: str, text: str, used: str, inputs: str = "") -> None:
        """inputs keys the profile and plan the brief was written from."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE briefs SET text = ?, used = ?, sent_at = ?, inputs = ? "
                "WHERE user_id = ? AND day = ?",
                (text, used, now_iso(), inputs, user_id, day),
            )

    def brief_inputs(self, user_id: str, day: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT inputs FROM briefs WHERE user_id = ? AND day = ?", (user_id, day)
            ).fetchone()
        return row["inputs"] if row else None

    def last_brief(self, user_id: str) -> tuple[str, str, str] | None:
        """(day, text, sent_at) of the newest brief that was written, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT day, text, sent_at FROM briefs WHERE user_id = ? AND text != '' "
                "ORDER BY day DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return (row["day"], row["text"], row["sent_at"]) if row else None

    def claim_alert(self, user_id: str, event_key: str, month: str, cap: int, text: str) -> bool:
        """True when this user has not had this event's alert and is under the month's cap.
        The check and the claim are one transaction."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            sent = conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE user_id = ? AND month = ?", (user_id, month)
            ).fetchone()[0]
            if sent >= cap:
                return False
            cursor = conn.execute(
                "INSERT OR IGNORE INTO alerts (user_id, event_key, month, text, sent_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, event_key, month, text, now_iso()),
            )
        return cursor.rowcount == 1

    def claim_answer(self, user_id: str, now: dt.datetime, cap: int) -> bool:
        """True when this user has had fewer than cap paid answers in the hour before now.
        The check and the claim are one transaction."""
        since = (now - dt.timedelta(hours=1)).isoformat()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM answers WHERE at < ?", (since,))
            used = conn.execute(
                "SELECT COUNT(*) FROM answers WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            if used >= cap:
                return False
            conn.execute("INSERT INTO answers (user_id, at) VALUES (?, ?)",
                         (user_id, now.isoformat()))  # fmt: skip
        return True

    def release_alert(self, user_id: str, event_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM alerts WHERE user_id = ? AND event_key = ?", (user_id, event_key)
            )

    def messages(self, user_id: str) -> list[Message]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE user_id = ? ORDER BY id", (user_id,)
            ).fetchall()
        return [
            Message(r["id"], r["user_id"], r["direction"], r["text"], r["insight_id"],
                    tuple(json.loads(r["numbers_used"])), r["sent_at"])
            for r in rows
        ]  # fmt: skip

    def new_link_code(self, user_id: str, now: dt.datetime, ttl: dt.timedelta) -> str:
        """A fresh 6-digit code for this user. Their older unused codes stop working, and every
        expired code is cleared so the space stays free."""
        now_utc = now.astimezone(dt.UTC)
        expires = (now_utc + ttl).isoformat()
        for _ in range(LINK_CODE_TRIES):
            code = f"{secrets.randbelow(10**LINK_CODE_DIGITS):0{LINK_CODE_DIGITS}d}"
            with self._connect() as conn:
                conn.execute("DELETE FROM link_codes WHERE expires_at <= ? OR "
                             "(user_id = ? AND used_at IS NULL)",
                             (now_utc.isoformat(), user_id))  # fmt: skip
                cursor = conn.execute(
                    "INSERT OR IGNORE INTO link_codes (code, user_id, expires_at) VALUES (?, ?, ?)",
                    (code, user_id, expires),
                )
            if cursor.rowcount == 1:
                return code
        raise RuntimeError("no free link code")

    def redeem_link_code(self, code: str, now: dt.datetime) -> str | None:
        """The user id behind an unexpired, unused code, which is used up in the same
        transaction. None for any other code."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT user_id FROM link_codes WHERE code = ? AND used_at IS NULL "
                "AND expires_at > ?",
                (code, now.astimezone(dt.UTC).isoformat()),
            ).fetchone()
            if row is None:
                return None
            conn.execute("UPDATE link_codes SET used_at = ? WHERE code = ?", (now_iso(), code))
        return row["user_id"]

    def add_watch(self, user_id: str, kind: WatchKind, target: str, label: str, now: str,
                  cap: int) -> Watch | None:  # fmt: skip
        """The new watch, or the same active one if the user already has it. None when the
        user is at the cap. The check and the insert are one transaction."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = _watches(conn, "user_id = ? AND stopped_at IS NULL", (user_id,))
            same = next((w for w in active if (w.kind, w.target) == (kind, target)), None)
            if same is not None:
                return same
            if len(active) >= cap:
                return None
            cursor = conn.execute(
                "INSERT INTO watches (user_id, kind, target, label, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, kind, target, label, now),
            )
        return Watch(int(cursor.lastrowid or 0), user_id, kind, target, label, now)

    def active_watches(self, user_id: str) -> list[Watch]:
        with self._connect() as conn:
            return _watches(conn, "user_id = ? AND stopped_at IS NULL", (user_id,))

    def all_active_watches(self) -> list[Watch]:
        with self._connect() as conn:
            return _watches(conn, "stopped_at IS NULL", ())

    def stop_watch(self, user_id: str, watch_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE watches SET stopped_at = ? WHERE id = ? AND user_id = ? "
                "AND stopped_at IS NULL",
                (now_iso(), watch_id, user_id),
            )
        return cursor.rowcount == 1

    def claim_watch_hit(self, user_id: str, watch_id: int, match_key: str, month: str,
                        cap: int) -> bool:  # fmt: skip
        """True when this user has had no message for this story and is under the month's
        cap. The check and the claim are one transaction."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            told = conn.execute(
                "SELECT COUNT(*) FROM watch_hits WHERE user_id = ? AND match_key = ?",
                (user_id, match_key),
            ).fetchone()[0]
            sent = conn.execute(
                "SELECT COUNT(*) FROM watch_hits WHERE user_id = ? AND month = ?", (user_id, month)
            ).fetchone()[0]
            if told or sent >= cap:
                return False
            cursor = conn.execute(
                "INSERT OR IGNORE INTO watch_hits (user_id, watch_id, match_key, month, sent_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, watch_id, match_key, month, now_iso()),
            )
        return cursor.rowcount == 1

    def release_watch_hit(self, watch_id: int, match_key: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM watch_hits WHERE watch_id = ? AND match_key = ?", (watch_id, match_key)
            )

    def add_asked_terms(self, user_id: str, terms: Sequence[str], now: str) -> None:
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO asked_terms (user_id, term, asked_at) VALUES (?, ?, ?)",
                [(user_id, term, now) for term in terms],
            )

    def recent_asked_terms(self, user_id: str, since: str) -> list[str]:
        """Terms asked at or after since and not yet brought back, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT term FROM asked_terms WHERE user_id = ? AND used_at IS NULL "
                "AND asked_at >= ? GROUP BY term ORDER BY MAX(asked_at) DESC, MAX(rowid) DESC",
                (user_id, since),
            ).fetchall()
        return [r["term"] for r in rows]

    def mark_terms_used(self, user_id: str, terms: Sequence[str]) -> None:
        with self._connect() as conn:
            conn.executemany(
                "UPDATE asked_terms SET used_at = ? WHERE user_id = ? AND term = ? "
                "AND used_at IS NULL",
                [(now_iso(), user_id, term) for term in terms],
            )

    def contact_user(self, address: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id FROM contacts WHERE address = ?", (address,)
            ).fetchone()
        return row["user_id"] if row else None

    def bind_contact(self, address: str, user_id: str) -> None:
        """Point a Keiki conversation at a user, replacing whoever it pointed at before."""
        self._upsert("contacts", {"address": address, "user_id": user_id, "linked_at": now_iso()})

    def contact_for(self, user_id: str) -> str | None:
        """The user's newest bound email address, if any. A Slack contact is never one."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT address FROM contacts WHERE user_id = ? AND address NOT LIKE ? "
                "ORDER BY linked_at DESC, rowid DESC LIMIT 1",
                (user_id, f"{SLACK_CONTACT_PREFIX}%"),
            ).fetchone()
        return row["address"] if row else None

    def queue_mail(self, user_id: str, address: str, text: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO outbox (user_id, address, text, created_at) VALUES (?, ?, ?, ?)",
                (user_id, address, text, now_iso()),
            )
        return int(cursor.lastrowid or 0)

    def pending_mail(self, address: str) -> list[OutMail]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM outbox WHERE address = ? AND sent_at IS NULL ORDER BY id",
                (address,),
            ).fetchall()
        return [OutMail(r["id"], r["user_id"], r["address"], r["text"], r["created_at"])
                for r in rows]  # fmt: skip

    def mark_mail_sent(self, mail_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE outbox SET sent_at = ? WHERE id = ?", (now_iso(), mail_id))

    def save_holdings(self, user_id: str, data: str) -> None:
        self._upsert("holdings", {"user_id": user_id, "data": data, "updated_at": now_iso()})

    def holdings_data(self, user_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM holdings WHERE user_id = ?", (user_id,)).fetchone()
        return row["data"] if row else None

    def delete_holdings(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM holdings WHERE user_id = ?", (user_id,))

    def save_snaptrade_user(self, user_id: str, snaptrade_user_id: str, secret: str) -> None:
        row = {"user_id": user_id, "snaptrade_user_id": snaptrade_user_id,
               "user_secret": secret, "created_at": now_iso()}  # fmt: skip
        self._upsert("snaptrade_users", row)

    def snaptrade_user(self, user_id: str) -> tuple[str, str] | None:
        """(snaptrade_user_id, user_secret) for a user who has registered, else None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT snaptrade_user_id, user_secret FROM snaptrade_users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return (row["snaptrade_user_id"], row["user_secret"]) if row else None

    def delete_snaptrade_user(self, user_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM snaptrade_users WHERE user_id = ?", (user_id,))

    def _upsert(self, table: str, row: Mapping[str, object]) -> None:
        names = ", ".join(f'"{n}"' for n in row)
        marks = ", ".join("?" for _ in row)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({names}) VALUES ({marks})", tuple(row.values())
            )
