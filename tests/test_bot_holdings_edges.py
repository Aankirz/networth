"""The holdings flow's edges on Telegram: /link_broker, /stop forgetting the broker link, group
chats, an image sent as a document, the image never stored or logged, and the voice of every
new message. No network: SnapTrade is a fake and its keys are patched away."""

from __future__ import annotations

import base64
import dataclasses
import logging
from pathlib import Path

import pytest

from networth import guard
from networth.app.store import Status, user_id_for
from networth.bot import commands
from networth.bot import holdings as flow
from networth.bot.message import FOOTER, LANGS, Message, plain
from networth.holdings import snaptrade
from networth.holdings.snaptrade import SnapTradeError, SnapUser
from tests.test_bot_holdings import (
    PNG,
    buttons,
    confirm,
    last,
    photo,
    stored,
    talk,
)
from tests.test_onboarding import USER, Chat, tap_update, text_update
from tests.test_voice import FOOTERS, check_language

PORTAL = "https://app.snaptrade.com/portal?read"


class FakeSnapTrade:
    def __init__(self, *, fail_delete: bool = False) -> None:
        self.calls: list[str] = []
        self.fail_delete = fail_delete

    def register_user(self, snaptrade_user_id: str) -> SnapUser:
        self.calls.append("register_user")
        return SnapUser(snaptrade_user_id, "user-secret")

    def login_link(self, user: SnapUser, redirect: str | None = None) -> str:
        self.calls.append("login_link")
        return PORTAL

    def delete_user(self, snaptrade_user_id: str) -> None:
        self.calls.append("delete_user")
        if self.fail_delete:
            raise SnapTradeError("delete user", "HTTP 500")


@pytest.fixture(autouse=True)
def no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(snaptrade, "keys_from_env", lambda *a, **k: None)


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    return talk(tmp_path)


def in_currency(chat: Chat, currency: str) -> Chat:
    chat.store.save_profile(dataclasses.replace(chat.profile, currency=currency))
    return chat


def test_link_broker_for_a_us_account_sends_the_read_only_link(tmp_path: Path) -> None:
    fake = FakeSnapTrade()
    chat = in_currency(talk(tmp_path, snaptrade=fake), "USD")
    chat.say("/link_broker")
    assert chat.bot.last == flow.LINK_LEAD["en"]
    assert buttons(chat) == [(flow.LINK_BUTTON["en"], "", PORTAL)]
    assert fake.calls == ["register_user", "login_link"]
    assert chat.store.snaptrade_user(USER) is not None


def test_link_broker_for_an_indian_account_is_a_kind_line(tmp_path: Path) -> None:
    fake = FakeSnapTrade()
    chat = in_currency(talk(tmp_path, snaptrade=fake), "INR")
    chat.say("/link_broker")
    assert chat.bot.last == flow.US_ONLY["en"] and fake.calls == []


def test_link_broker_without_keys_says_not_yet(tmp_path: Path) -> None:
    chat = in_currency(talk(tmp_path), "USD")
    chat.say("/link_broker")
    assert chat.bot.last == flow.NOT_YET["en"]


def test_a_snaptrade_error_says_try_again(tmp_path: Path) -> None:
    class Down(FakeSnapTrade):
        def register_user(self, snaptrade_user_id: str) -> SnapUser:
            raise SnapTradeError("register user", "HTTP 503")

    chat = in_currency(talk(tmp_path, snaptrade=Down()), "USD")
    chat.say("/link_broker")
    assert chat.bot.last == commands.TRY_AGAIN["en"]


def test_stop_forgets_the_broker_deletes_holdings_and_retires_the_link(tmp_path) -> None:
    fake = FakeSnapTrade()
    chat = talk(tmp_path, snaptrade=fake)
    confirm(chat)
    chat.store.save_snaptrade_user(USER, "networth-abc", "user-secret")
    old_token = chat.profile.link_token
    chat.say("/stop")
    assert fake.calls == ["delete_user"]
    assert chat.store.snaptrade_user(USER) is None and stored(chat) is None
    assert chat.store.profile_by_token(old_token) is None
    assert chat.profile.status is Status.STOPPED


def test_stop_still_stops_when_the_snaptrade_delete_fails(tmp_path, caplog) -> None:
    chat = talk(tmp_path, snaptrade=FakeSnapTrade(fail_delete=True))
    confirm(chat)
    chat.store.save_snaptrade_user(USER, "networth-abc", "user-secret")
    chat.say("/stop")
    assert chat.profile.status is Status.STOPPED and stored(chat) is None
    assert chat.bot.last == commands.STOPPED["en"]
    assert "user-secret" not in caplog.text and USER in caplog.text


GROUP = -100123


def test_a_group_message_gets_one_line_and_creates_no_profile(tmp_path: Path) -> None:
    chat = talk(tmp_path)
    update = text_update("/start")
    update["message"]["chat"] = {"id": GROUP, "type": "group"}
    commands.handle_update(update, chat.store, chat.bot, services=chat.services)
    assert chat.bot.sent[-1][:2] == (GROUP, commands.PRIVATE_ONLY)
    assert chat.store.get_profile(user_id_for(GROUP)) is None


def test_a_group_tap_is_answered_and_creates_no_profile(tmp_path: Path) -> None:
    chat = talk(tmp_path)
    sent = len(chat.bot.sent)
    update = tap_update("hd:ok", chat=GROUP)
    update["callback_query"]["message"]["chat"]["type"] = "supergroup"
    commands.handle_update(update, chat.store, chat.bot, services=chat.services)
    assert chat.bot.answers[-1][1] == commands.PRIVATE_ONLY
    assert len(chat.bot.sent) == sent
    assert chat.store.get_profile(user_id_for(GROUP)) is None


def test_an_image_sent_as_a_document_is_read_like_a_photo(chat: Chat) -> None:
    photo(chat, document={"file_id": "doc-1", "mime_type": "image/png"})
    assert chat.bot.downloads[-1] == "doc-1"
    assert last(chat).title == flow.TITLE["en"]


def test_a_pdf_document_is_not_an_image(chat: Chat) -> None:
    photo(chat, document={"file_id": "doc-2", "mime_type": "application/pdf"})
    assert chat.bot.last == commands.NOT_A_PHOTO["en"] and "doc-2" not in chat.bot.downloads


def _files(*roots: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for root in roots if root.exists()
            for p in root.rglob("*") if p.is_file()}  # fmt: skip


def test_the_image_is_never_written_or_logged(tmp_path: Path, caplog) -> None:
    chat = talk(tmp_path)
    repo_data = Path(__file__).parents[1] / "data"
    before = _files(tmp_path, repo_data, Path.cwd() / "data")
    caplog.set_level(logging.DEBUG)
    photo(chat)
    assert last(chat).title == flow.TITLE["en"], "the photo was read"
    after = _files(tmp_path, repo_data, Path.cwd() / "data")
    new = {p.name for p in set(after) - set(before)}
    assert all(name.startswith(chat.store.path.name) for name in new), new
    encoded = base64.b64encode(PNG)
    for path, content in after.items():
        if after[path] != before.get(path):
            assert PNG[:64] not in content and encoded[:64] not in content, path
    for record in caplog.records:
        logged = f"{record.getMessage()} {record.args!r}".encode()
        assert PNG[:64] not in logged and encoded[:64] not in logged


# --- the voice of every new message, in every language --------------------------------------


def report(chat: Chat) -> Message:
    confirm(chat)
    return last(chat)


def answer(chat: Chat) -> Message:
    confirm(chat)
    chat.services = dataclasses.replace(chat.services, models=None)
    chat.say("what should i sell")
    return last(chat)


def prompt(chat: Chat) -> Message:
    photo(chat)
    return last(chat)


WITH_FOOTER = {"report": report, "holdings answer": answer}
WITHOUT_FOOTER = {"confirm prompt": prompt, "no holdings": "NO_HOLDINGS", "cancelled": "CANCELLED",
                  "how to fix": "HOW_TO_FIX", "us only": "US_ONLY", "not yet": "NOT_YET",
                  "link lead": "LINK_LEAD"}  # fmt: skip


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("kind", list(WITH_FOOTER))
def test_the_report_and_answer_end_with_one_footer(tmp_path, kind: str, lang: str) -> None:
    m = WITH_FOOTER[kind](talk(tmp_path, lang=lang))
    text = plain(m)
    assert m.footer == FOOTER[lang] and text.endswith(FOOTER[lang])
    assert sum(text.count(f) for f in FOOTERS) == 1
    assert guard.check(text, text).ok, guard.check(text, text).problems
    check_language(m, lang)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("kind", list(WITHOUT_FOOTER))
def test_prompts_and_acks_carry_no_footer(tmp_path, kind: str, lang: str) -> None:
    build = WITHOUT_FOOTER[kind]
    chat = talk(tmp_path, lang=lang)
    m = build(chat) if callable(build) else Message(body=(getattr(flow, build)[lang],))
    assert m.footer == "" and not any(f in plain(m) for f in FOOTERS)
    check_language(m, lang)
