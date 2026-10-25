"""Get my brief now: offered wherever we say the brief comes on the investing day, built as
/brief builds it, and never using up or skipping the month's scheduled brief."""

from __future__ import annotations

from dataclasses import replace

import pytest

from networth.app import schedule
from networth.app.store import Step
from networth.bot.onboarding import BRIEF_NOW
from tests.test_dashboard_link import chat_on
from tests.test_onboarding import Chat, onboard
from tests.test_schedule import chat, job  # noqa: F401 - the chat fixture: invest day is today

BRIEF_TITLE = "Morning. It's your investing day, and ₹1 lakh is ready."


def taps(user: Chat) -> list[str]:
    return [b.data for row in user.bot.sent[-1][2] for b in row]


def test_setup_done_asks_want_it_now_with_the_button(tmp_path) -> None:
    user = Chat(tmp_path)
    onboard(user)
    done = next(i for i, t in enumerate(user.bot.texts) if t.startswith("You're all set."))
    assert "Want it now?" in user.bot.texts[done]
    assert BRIEF_NOW in [b.data for row in user.bot.sent[done][2] for b in row]


def test_the_plan_command_offers_it_and_says_the_day(tmp_path) -> None:
    user = Chat(tmp_path)
    onboard(user)
    user.say("/plan")
    i = len(user.bot.sent) - 2  # the plan message, before the change prompt
    assert (
        "I'll also send your brief on the 1st of every month. Want it now?" in (user.bot.texts[i])
    )
    assert BRIEF_NOW in [b.data for row in user.bot.sent[i][2] for b in row]


def test_the_dashboard_reply_carries_the_button(tmp_path) -> None:
    user = chat_on(tmp_path)
    user.say("/dashboard")
    assert BRIEF_NOW in taps(user)


def test_the_tap_sends_the_full_brief(chat: Chat) -> None:  # noqa: F811
    chat.tap(BRIEF_NOW)
    assert chat.bot.last.startswith(BRIEF_TITLE)


@pytest.mark.parametrize("ask", ["tap", "/brief now"])
def test_getting_it_now_never_uses_up_the_scheduled_brief(chat: Chat, ask: str) -> None:  # noqa: F811
    chat.tap(BRIEF_NOW) if ask == "tap" else chat.say(ask)
    assert chat.bot.last.startswith(BRIEF_TITLE)
    assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 1 sent"
    assert chat.bot.last.startswith(BRIEF_TITLE)


def test_plain_brief_still_claims_the_day_as_before(chat: Chat) -> None:  # noqa: F811
    chat.say("/brief")
    assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 0 sent"


def test_before_setup_the_tap_says_finish_setup(chat: Chat) -> None:  # noqa: F811
    chat.store.save_profile(replace(chat.profile, step=Step.GOAL))
    chat.tap(BRIEF_NOW)
    assert not chat.bot.last.startswith(BRIEF_TITLE)
