"""/erase end to end through handle_update: a confirm button first, then every row about the user
gone from every table, the broker link forgotten at SnapTrade before anything local, and one kind
line in the user's language. Fake Telegram, fake SnapTrade; no network."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from networth.app.services import Services
from networth.app.store import COLUMNS, USER_TABLES
from networth.bot.commands import (
    COMMAND_LIST,
    ERASE_ASK,
    ERASE_KEPT,
    ERASED,
    TRY_AGAIN,
    help_message,
)
from networth.bot.message import plain
from networth.holdings import snaptrade
from tests.test_bot_holdings_edges import FakeSnapTrade
from tests.test_onboarding import USER, Chat, onboard

OTHER = "tg:9191"
OTHER_CONTACT = "other@example.com"
MY_CONTACT = "me@example.com"


@pytest.fixture(autouse=True)
def no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snaptrade, "keys_from_env", lambda *a, **k: None)


def value(column: str, decl: str, user_id: str) -> object:
    """A value each column's declaration accepts, the user id where it names one."""
    if column == "user_id":
        return user_id
    if column == "address":
        return MY_CONTACT if user_id == USER else OTHER_CONTACT
    checked = {"direction": "in", "kind": "type", "role": "user"}
    if column in checked:
        return checked[column]
    return 1 if decl.startswith("INTEGER") else f"{column}-{user_id}"


def seed(db: Path, user_id: str) -> None:
    """One row for this user in every table that has a user_id, and one link-code miss from
    their bound email contact."""
    with sqlite3.connect(db) as conn:
        for table in USER_TABLES:
            row = {c: value(c, d, user_id) for c, d in COLUMNS[table].items()
                   if "AUTOINCREMENT" not in d}  # fmt: skip
            names = ", ".join(f'"{c}"' for c in row)
            marks = ", ".join("?" for _ in row)
            conn.execute(f"INSERT OR IGNORE INTO {table} ({names}) VALUES ({marks})",
                         tuple(row.values()))  # fmt: skip
        address = MY_CONTACT if user_id == USER else OTHER_CONTACT
        conn.execute("INSERT INTO link_misses (address, at) VALUES (?, ?)", (address, "t"))


def rows(db: Path, table: str, user_id: str) -> int:
    with sqlite3.connect(db) as conn:
        if table == "link_misses":
            address = MY_CONTACT if user_id == USER else OTHER_CONTACT
            return conn.execute("SELECT COUNT(*) FROM link_misses WHERE address = ?",
                                (address,)).fetchone()[0]  # fmt: skip
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?",
                            (user_id,)).fetchone()[0]  # fmt: skip


@pytest.fixture
def fake_snap() -> FakeSnapTrade:
    return FakeSnapTrade()


@pytest.fixture
def chat(tmp_path: Path, fake_snap: FakeSnapTrade) -> Chat:
    chat = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", link_secret="s",
                                   snaptrade=fake_snap))  # fmt: skip
    onboard(chat)
    seed(chat.store.path, USER)
    seed(chat.store.path, OTHER)
    return chat


def test_the_tables_cover_everything_about_a_user() -> None:
    expected = {"profiles", "plans", "messages", "briefs", "answers", "alerts", "contacts",
                "link_codes", "watches", "watch_hits", "asked_terms", "holdings",
                "snaptrade_users", "outbox", "turns"}  # fmt: skip
    assert expected <= set(USER_TABLES)


@pytest.mark.parametrize("table", [*USER_TABLES, "link_misses"])
def test_erase_deletes_this_users_rows_and_no_one_elses(chat: Chat, table: str) -> None:
    assert rows(chat.store.path, table, USER) >= 1
    chat.say("/erase")
    chat.tap("er:yes")
    assert rows(chat.store.path, table, USER) == 0
    assert rows(chat.store.path, table, OTHER) >= 1, "another user's rows stay"


def test_erase_asks_first_and_deletes_nothing_until_confirmed(chat: Chat) -> None:
    chat.say("/erase")
    _, text, buttons = chat.bot.sent[-1]
    assert text == ERASE_ASK["en"]
    assert [b.data for row in buttons for b in row] == ["er:yes", "er:no"]
    assert chat.store.get_profile(USER) is not None
    chat.tap("er:no")
    assert chat.bot.last == ERASE_KEPT["en"]
    assert chat.store.get_profile(USER) is not None
    assert rows(chat.store.path, "holdings", USER) == 1


def test_erase_forgets_snaptrade_first_then_says_one_kind_line(chat: Chat, fake_snap) -> None:
    chat.say("/erase")
    chat.tap("er:yes")
    assert fake_snap.calls == ["delete_user"]
    assert chat.bot.last == ERASED["en"]
    assert chat.store.get_profile(USER) is None
    assert chat.bot.menus[-1][2] is None, "the menu button no longer opens a page"


def test_a_failed_snaptrade_delete_erases_nothing(tmp_path: Path) -> None:
    failing = FakeSnapTrade(fail_delete=True)
    chat = Chat(tmp_path, Services(tmp_path / "data", snaptrade=failing))
    onboard(chat)
    seed(chat.store.path, USER)
    chat.say("/erase yes")
    assert failing.calls == ["delete_user"]
    assert chat.bot.last == TRY_AGAIN["en"]
    assert all(rows(chat.store.path, t, USER) >= 1 for t in USER_TABLES), "nothing was deleted"


def test_a_stopped_user_can_still_erase(chat: Chat) -> None:
    chat.say("/stop")
    chat.say("/erase")
    assert chat.bot.last == ERASE_ASK["en"]
    chat.tap("er:yes")
    assert chat.bot.last == ERASED["en"]
    assert chat.store.get_profile(USER) is None


@pytest.mark.parametrize("lang", ["en", "hi", "hinglish"])
def test_erase_speaks_the_users_language(tmp_path: Path, lang: str) -> None:
    chat = Chat(tmp_path, Services(tmp_path / "data", snaptrade=FakeSnapTrade()))
    onboard(chat)
    chat.store.save_profile(chat.profile.__class__(**{**vars(chat.profile), "lang": lang}))
    chat.say("/erase")
    assert chat.bot.last == ERASE_ASK[lang]
    chat.tap("er:yes")
    assert chat.bot.last == ERASED[lang]


def test_erase_is_in_help_and_the_command_list() -> None:
    assert "erase" in dict(COMMAND_LIST)
    for lang in ("en", "hi", "hinglish"):
        assert "/erase" in plain(help_message(lang))


@pytest.mark.parametrize("lang", ["en", "hi", "hinglish"])
def test_the_erase_ask_no_longer_mentions_a_broker(lang: str) -> None:
    assert "broker" not in ERASE_ASK[lang].lower() and "ब्रोकर" not in ERASE_ASK[lang]
