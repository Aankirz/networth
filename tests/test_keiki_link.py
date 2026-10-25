"""One person on two channels: /link codes, /sendto, and one brief a day across Telegram and
email. Fake Telegram, fake Keiki, a tmp store shared by both."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import replace
from pathlib import Path

import pytest

from networth import config
from networth.app.services import Services
from networth.app.store import LINK_MISSES_PER_HOUR, Channel, Store
from networth.bot.briefs import run_daily
from networth.keiki.mail import Mail
from networth.keiki.turn import LINKED
from tests.keiki_fakes import ADDRESS, IPHONE, LIVE_BRIEF, MAILTRACK_FOOTER, FakeApi
from tests.test_keiki_turn import Keiki, turn_log
from tests.test_onboarding import NOW, USER, Chat, onboard
from tests.watcher_fakes import FAKE_ENV

CLOCK = dt.datetime.fromisoformat(NOW)
TEN_MINUTES = dt.timedelta(minutes=10)


@pytest.fixture
def services(tmp_path: Path) -> Services:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    store = Store(tmp_path / "data")
    return Services(tmp_path / "data", cfg=cfg, mail=Mail(store, FakeApi()),
                    keiki_email="networth@agentmail.to")  # fmt: skip


@pytest.fixture
def chat(tmp_path: Path, services: Services) -> Chat:
    chat = Chat(tmp_path, services)
    onboard(chat)
    return chat


def link_code(chat: Chat) -> str:
    chat.say("/link")
    found = re.search(r"Your code is (\d{6})\.", chat.bot.last)
    assert found, chat.bot.last
    return found.group(1)


def test_brief_by_email_in_a_new_thread_is_a_command_for_the_linked_user(tmp_path, chat) -> None:
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(link_code(chat), now=NOW)
    keiki.say("/brief\n\nSent from my iPhone", now=NOW)
    linked, brief = turn_log(keiki)
    assert (linked["kind"], linked["user_id"]) == ("link", USER)
    assert (brief["kind"], brief["user_id"], brief["intent"]) == ("command", USER, None)


def test_brief_by_email_in_the_live_shape_sends_the_brief_not_a_chat_answer(tmp_path, chat):
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(link_code(chat), now=NOW)
    keiki.say(LIVE_BRIEF, now=NOW)
    _, brief = turn_log(keiki)
    assert (brief["kind"], brief["user_id"], brief["intent"]) == ("command", USER, None)
    chat.say("/brief")
    assert keiki.last == chat.bot.last, "the same brief Telegram sends that day"


@pytest.mark.parametrize("tail", [MAILTRACK_FOOTER, IPHONE, MAILTRACK_FOOTER + IPHONE])
def test_a_code_with_a_mail_footer_still_links(tmp_path, chat, tail: str) -> None:
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(link_code(chat) + tail, now=NOW)
    assert keiki.last == LINKED["en"]


def test_link_gives_a_code_the_inbox_and_how_long_it_lasts(chat: Chat) -> None:
    link_code(chat)
    assert "Email it to networth@agentmail.to within 10 minutes. It works once." in chat.bot.last


def test_a_code_sent_by_email_links_that_contact_to_the_telegram_user(tmp_path, chat) -> None:
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(f"my code is {link_code(chat)}", now=NOW)
    assert keiki.last == LINKED["en"]
    assert keiki.profile().user_id == USER
    keiki.say("/plan", now=NOW)
    assert any(t.startswith("Your plan\n\nBalanced.") for t in keiki.client.texts)


def test_a_code_works_only_once(tmp_path: Path, chat: Chat) -> None:
    code = link_code(chat)
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(code, now=NOW)
    keiki.say(code, address="someone@example.com", now=NOW)
    assert keiki.last.startswith("Hi, I'm Networth."), "a stranger gets the email setup instead"
    assert keiki.profile("someone@example.com").user_id != USER


def test_a_code_expires_after_the_configured_minutes(tmp_path: Path) -> None:
    store = Store(tmp_path)
    code = store.new_link_code("tg:1", CLOCK, TEN_MINUTES)
    assert store.redeem_link_code(code, CLOCK + dt.timedelta(minutes=11), ADDRESS) is None
    fresh = store.new_link_code("tg:1", CLOCK, TEN_MINUTES)
    assert store.redeem_link_code(fresh, CLOCK + dt.timedelta(minutes=9), ADDRESS) == "tg:1"


def test_a_code_belongs_to_the_user_who_made_it(tmp_path: Path) -> None:
    store = Store(tmp_path)
    mine, theirs = (store.new_link_code(u, CLOCK, TEN_MINUTES) for u in ("tg:1", "tg:2"))
    assert store.redeem_link_code(theirs, CLOCK, ADDRESS) == "tg:2"
    assert store.redeem_link_code(mine, CLOCK, ADDRESS) == "tg:1"


def test_a_new_code_retires_the_users_older_unused_one(tmp_path: Path, monkeypatch) -> None:
    from networth.app import store as store_module

    draws = iter([111111, 222222])
    monkeypatch.setattr(store_module.secrets, "randbelow", lambda n: next(draws))
    store = Store(tmp_path)
    assert store.new_link_code("tg:1", CLOCK, TEN_MINUTES) == "111111"
    assert store.new_link_code("tg:1", CLOCK, TEN_MINUTES) == "222222"
    assert store.redeem_link_code("111111", CLOCK, ADDRESS) is None
    assert store.redeem_link_code("222222", CLOCK, ADDRESS) == "tg:1"


def test_an_email_profile_can_be_relinked_to_telegram(tmp_path: Path, chat: Chat) -> None:
    keiki = Keiki(tmp_path, chat.services)
    keiki.say("Hello", now=NOW)
    assert keiki.profile().channel == "email"
    keiki.say(link_code(chat), now=NOW)
    assert keiki.profile().user_id == USER


def test_sendto_email_needs_a_linked_email(tmp_path: Path, chat: Chat) -> None:
    chat.say("/sendto email")
    assert chat.bot.last.startswith("Your email isn't linked yet")
    assert chat.profile.deliver_to == Channel.TELEGRAM
    Keiki(tmp_path, chat.services).say(link_code(chat), now=NOW)
    chat.say("/sendto email")
    assert chat.bot.last == "Done. Briefs and alerts now go to your email."
    assert chat.profile.deliver_to == Channel.EMAIL


def test_sendto_telegram_needs_a_telegram_chat(tmp_path: Path, services: Services) -> None:
    keiki = Keiki(tmp_path, services)
    keiki.say("Hello")
    keiki.say("/sendto telegram")
    assert keiki.last.startswith("You haven't used Networth on Telegram yet")


def test_a_linked_user_on_email_gets_one_brief_a_day_and_none_on_telegram(tmp_path, chat) -> None:
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(link_code(chat), now=NOW)
    chat.say("/sendto email")
    chat.store.save_profile(replace(chat.profile, invest_day=25))
    telegram = len(chat.bot.sent)
    morning = dt.datetime(2026, 10, 25, 2, 30, tzinfo=dt.UTC)
    assert run_daily(chat.store, chat.bot, chat.services, morning) == 1
    assert run_daily(chat.store, chat.bot, chat.services, morning) == 0, "a rerun sends nothing"
    assert len(chat.bot.sent) == telegram, "nothing proactive went to Telegram"
    queued = chat.store.pending_mail(ADDRESS)
    assert len(queued) == 1 and queued[0].text.startswith(
        "Morning. It's your investing day, and ₹1,00,000 is ready."
    )
    keiki.say("", now=NOW)
    assert keiki.last.startswith("Morning. It's your investing day, and ₹1,00,000 is ready."), (
        "the notice turn delivers it"
    )


def test_link_waits_until_setup_is_done(tmp_path: Path, services: Services) -> None:
    chat = Chat(tmp_path, services)
    onboard(chat, confirm=False)
    chat.say("/link")
    assert chat.bot.last == "Let's finish setting up first."


def test_a_code_inside_a_longer_message_does_not_link(tmp_path: Path, chat: Chat) -> None:
    code = chat.store.new_link_code(USER, dt.datetime.now(dt.UTC), TEN_MINUTES)
    keiki = Keiki(tmp_path, chat.services)
    keiki.say(f"Did the Nifty really close at {code} points yesterday, or was that a typo?")
    assert keiki.store.contact_user(ADDRESS) != USER


def guess_wrong(keiki: Keiki, code: str, times: int) -> None:
    for wrong in [c for c in (f"{n:06d}" for n in range(times + 1)) if c != code][:times]:
        keiki.say(wrong, now=NOW)


def test_five_wrong_codes_in_an_hour_stop_codes_from_that_contact(tmp_path, chat) -> None:
    code = link_code(chat)
    keiki = Keiki(tmp_path, chat.services)
    guess_wrong(keiki, code, LINK_MISSES_PER_HOUR)
    keiki.say(code, now=NOW)
    assert keiki.last != LINKED["en"], "the right code is answered as a normal message"
    assert keiki.store.contact_user(ADDRESS) != USER
    keiki.say(code, address="someone@example.com", now=NOW)
    assert keiki.store.contact_user("someone@example.com") == USER, "other contacts still link"


def test_codes_from_a_contact_work_again_an_hour_after_the_misses(tmp_path, chat) -> None:
    keiki = Keiki(tmp_path, chat.services)
    guess_wrong(keiki, link_code(chat), LINK_MISSES_PER_HOUR)
    later = CLOCK + dt.timedelta(hours=1, minutes=1)
    keiki.say(chat.store.new_link_code(USER, later, TEN_MINUTES), now=later.isoformat())
    assert keiki.last == LINKED["en"]
