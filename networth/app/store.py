"""The user data model and $DATA_DIR/networth.sqlite, the only module that knows its schema.

    store = Store(data_dir)
    profile = store.get_profile("tg:42")

Tables: profiles (one per chat), plans (one per user, rewritten on change), messages (every
text in and out), briefs (one per user per investing day) and alerts (one per user per event).
A brief or an alert row is claimed before the message goes out, so a retried trigger never
sends it twice. Each operation opens its own short connection,
because webhook handlers run on a threadpool. The schema is created on first use and migrated
additively: a column missing from an older file is added, so opening twice is a no-op.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, fields
from enum import StrEnum
from pathlib import Path
from typing import Final, Literal

DB_NAME: Final = "networth.sqlite"
CHANNEL: Final = "telegram"
INDIA_TZ: Final = "Asia/Kolkata"
US_TZ: Final = "America/New_York"
LINK_TOKEN_BYTES: Final = 16
US_STOCKS: Final = "us_stocks"
ALL_MARKETS: Final = ("in", "us")


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
    user_id: str  # "tg:<chat_id>"
    channel: str
    chat_id: int
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


COLUMNS: Final[dict[str, dict[str, str]]] = {
    "profiles": {
        "user_id": "TEXT PRIMARY KEY", "channel": "TEXT NOT NULL", "chat_id": "INTEGER NOT NULL",
        "step": "TEXT NOT NULL", "status": "TEXT NOT NULL", "tz": "TEXT NOT NULL", "lang": "TEXT",
        "link_token": "TEXT NOT NULL", "invest_day": "INTEGER",
        "alerts_on": "INTEGER NOT NULL DEFAULT 1", "goal": "TEXT", "horizon_years": "INTEGER",
        "drop_comfort": "INTEGER", "monthly_amount": "INTEGER", "currency": "TEXT",
        "markets": "TEXT NOT NULL DEFAULT '[]'", "exclude": "TEXT NOT NULL DEFAULT '[]'",
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
    },
    "answers": {"user_id": "TEXT NOT NULL", "at": "TEXT NOT NULL"},
    "alerts": {
        "user_id": "TEXT NOT NULL", "event_key": "TEXT NOT NULL", "month": "TEXT NOT NULL",
        "text": "TEXT NOT NULL", "sent_at": "TEXT NOT NULL",
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
    return Profile(**values)


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
        self._upsert("profiles", _profile_row(profile))

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

    def profiles(self) -> list[Profile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM profiles ORDER BY user_id").fetchall()
        return [_profile_from(r) for r in rows]

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

    def save_brief(self, user_id: str, day: str, text: str, used: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE briefs SET text = ?, used = ?, sent_at = ? WHERE user_id = ? AND day = ?",
                (text, used, now_iso(), user_id, day),
            )

    def last_brief(self, user_id: str) -> tuple[str, str] | None:
        """(day, text) of the newest brief that was written, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT day, text FROM briefs WHERE user_id = ? AND text != '' "
                "ORDER BY day DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return (row["day"], row["text"]) if row else None

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

    def _upsert(self, table: str, row: Mapping[str, object]) -> None:
        names = ", ".join(f'"{n}"' for n in row)
        marks = ", ".join("?" for _ in row)
        with self._connect() as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({names}) VALUES ({marks})", tuple(row.values())
            )
