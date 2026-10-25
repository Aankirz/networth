"""Onboarding and commands end to end through handle_update, a fake Telegram, a tmp store."""

from __future__ import annotations

import itertools
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from networth.app.services import Services
from networth.app.store import Plan, Profile, Status, Step, Store
from networth.bot.commands import handle_update
from networth.bot.message import Message, plain
from networth.bot.onboarding import Reply
from networth.bot.outbox import send
from networth.bot.telegram import Keyboard

CHAT = 4242
USER = f"tg:{CHAT}"
NOW = "2026-10-25T06:00:00+00:00"

SUMMARY = (
    "Here's what I have.\n\n"
    "Goal: A house, in about 4 years\n"
    "Each month: ₹1,00,000 on the 1st\n"
    "A fall you can sit through: up to 20%\n"
    "Left out: Crypto, US stocks\n"
    "Language: English\n"
    "Plan: Balanced. 20% safety, 70% core, 10% growth\n\n"
    "Looks right?"
)
TAPS_TO_CONFIRM = (
    "ob:lang:en", "ob:goal:house", "ob:horizon:4", "ob:amount:100000", "ob:day:1",
    "ob:drop:20", "ob:exclude:crypto", "ob:exclude:us_stocks", "ob:exclude:done",
    "ob:plan:balanced",
)  # fmt: skip


@dataclass
class FakeBot:
    sent: list[tuple[int, str, Keyboard]] = field(default_factory=list)  # the plain render
    messages: list[Message] = field(default_factory=list)
    answers: list[tuple[str, str | None]] = field(default_factory=list)
    edits: list[tuple[int, int, Keyboard]] = field(default_factory=list)
    webhooks: list[tuple[str, str]] = field(default_factory=list)
    downloads: list[str] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(100))

    def send_message(self, chat_id: int, message: Message, buttons: Keyboard = ()) -> dict:
        self.sent.append((chat_id, plain(message), buttons))
        self.messages.append(message)
        return {"message_id": next(self._ids)}

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        self.answers.append((callback_id, text))

    def edit_buttons(self, chat_id: int, message_id: int, buttons: Keyboard) -> None:
        self.edits.append((chat_id, message_id, buttons))

    def set_webhook(self, url: str, secret_token: str) -> None:
        self.webhooks.append((url, secret_token))

    def delete_webhook(self) -> None:
        pass

    def get_updates(self, offset: int | None, timeout_s: int) -> list[dict]:
        return []

    def download_file(self, file_id: str) -> bytes:
        self.downloads.append(file_id)
        return b"\xff\xd8 fake jpeg"

    @property
    def texts(self) -> list[str]:
        return [text for _, text, _ in self.sent]

    @property
    def last(self) -> str:
        return self.sent[-1][1]

    def labels(self) -> list[str]:
        return [b.label for _, _, kb in self.sent for row in kb for b in row]


_update_ids = itertools.count(1)


def text_update(text: str, chat: int = CHAT, **extra: object) -> dict:
    message = {"message_id": 1, "chat": {"id": chat, "type": "private"}, "text": text, **extra}
    return {"update_id": next(_update_ids), "message": message}


def tap_update(data: str, chat: int = CHAT, message_id: int = 7) -> dict:
    n = next(_update_ids)
    message = {"message_id": message_id, "chat": {"id": chat, "type": "private"}}
    return {"update_id": n, "callback_query": {"id": f"cb{n}", "data": data, "message": message}}


class Chat:
    """One user talking to the bot."""

    def __init__(self, tmp_path: Path, services: Services | None = None) -> None:
        self.store = Store(tmp_path / "data")
        self.bot = FakeBot()
        self.services = services or Services(tmp_path / "data")

    def say(self, text: str, **extra: object) -> None:
        handle_update(text_update(text, **extra), self.store, self.bot, NOW, self.services)

    def tap(self, data: str) -> None:
        handle_update(tap_update(data), self.store, self.bot, NOW, self.services)

    def send_photo(self, file_id: str | None) -> None:
        sizes = [{"file_id": "small"}, {"file_id": file_id}] if file_id else []
        message = {"message_id": 1, "chat": {"id": CHAT}, "photo": sizes} if file_id else {
            "message_id": 1, "chat": {"id": CHAT}, "sticker": {}}  # fmt: skip
        handle_update({"update_id": next(_update_ids), "message": message}, self.store,
                      self.bot, NOW, self.services)  # fmt: skip

    @property
    def profile(self) -> Profile:
        profile = self.store.get_profile(USER)
        assert profile is not None, "profile exists"
        return profile

    @property
    def plan(self) -> Plan | None:
        return self.store.get_plan(USER)


def onboard(chat: Chat, *, confirm: bool = True) -> None:
    chat.say("/start")
    for data in TAPS_TO_CONFIRM:
        chat.tap(data)
    if confirm:
        chat.tap("ob:confirm:ok")


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    return Chat(tmp_path)


def test_button_taps_take_start_to_done_and_store_every_field(chat: Chat) -> None:
    onboard(chat, confirm=False)
    assert chat.bot.last == SUMMARY
    chat.tap("ob:confirm:ok")

    p = chat.profile
    assert (p.user_id, p.channel, p.chat_id) == (USER, "telegram", CHAT)
    assert p.step is Step.DONE and p.status is Status.ACTIVE
    assert (p.tz, p.lang, p.invest_day, p.alerts_on) == ("Asia/Kolkata", "en", 1, True)
    assert (p.goal, p.horizon_years, p.drop_comfort) == ("house", 4, 20)
    assert (p.monthly_amount, p.currency) == (100_000, "INR")
    assert p.exclude == ("crypto", "us_stocks")
    assert p.markets == ("in",)
    assert len(p.link_token) >= 16
    assert p.created_at == p.updated_at == NOW
    assert chat.plan == Plan(USER, "balanced", {"safety": 20, "core": 70, "growth": 10}, 20, NOW)
    assert chat.bot.messages[-1].title == "You're all set."
    assert "I'll message you on the 1st of each month" in chat.bot.last
    assert chat.bot.last.endswith("Research, not advice.")


def test_every_tap_is_answered_so_the_spinner_stops(chat: Chat) -> None:
    onboard(chat)
    assert len(chat.bot.answers) == len(TAPS_TO_CONFIRM) + 1


def test_messages_are_logged_both_ways(chat: Chat) -> None:
    onboard(chat)
    log = chat.store.messages(USER)
    assert [m.text for m in log if m.direction == "in"][:2] == ["/start", "ob:lang:en"]
    assert [m.text for m in log if m.direction == "out"] == chat.bot.texts


def test_typed_answers_work_like_taps(chat: Chat) -> None:
    chat.say("/start")
    for answer in ("English", "saving for a flat", "in 4 yrs", "1 lakh", "on the 1st", "25",
                   "crypto", "US stocks", "done", "balanced"):  # fmt: skip
        chat.say(answer)
    assert chat.bot.last == SUMMARY
    chat.say("looks right")
    assert chat.profile.step is Step.DONE


def test_bad_amount_gets_a_retry_and_stays_on_amount(chat: Chat) -> None:
    chat.say("/start")
    chat.tap("ob:lang:en")
    chat.tap("ob:goal:house")
    chat.tap("ob:horizon:4")
    chat.say("lots")
    assert chat.profile.step is Step.AMOUNT
    assert chat.bot.last.startswith("I didn't catch that amount. Try something like 25k")
    assert "About how much do you invest each month?" in chat.bot.last
    assert chat.bot.sent[-1][2], "the retry keeps the buttons"


def test_day_past_28_explains_why(chat: Chat) -> None:
    chat.say("/start")
    for data in ("ob:lang:en", "ob:goal:house", "ob:horizon:4", "ob:amount:25000"):
        chat.tap(data)
    chat.say("31st")
    assert chat.bot.last.startswith("Pick a day from 1 to 28, so every month has it.")
    assert chat.profile.step is Step.DAY


def test_fix_amount_returns_to_confirm_with_the_new_value(chat: Chat) -> None:
    onboard(chat, confirm=False)
    chat.tap("ob:confirm:fix")
    assert chat.bot.last == "What would you like to change?"
    chat.tap("ob:confirm:amount")
    assert chat.profile.step is Step.AMOUNT
    chat.say("$500")
    assert chat.profile.step is Step.CONFIRM
    assert "Each month: $500 on the 1st" in chat.bot.last
    assert chat.profile.tz == "America/New_York"


def test_fixing_the_fall_keeps_the_plan_in_step(chat: Chat) -> None:
    onboard(chat, confirm=False)
    chat.tap("ob:confirm:fix")
    chat.tap("ob:confirm:drop")
    chat.tap("ob:drop:40")
    assert "A fall you can sit through: 40% or more" in chat.bot.last
    assert chat.plan is not None and chat.plan.max_drop_ok == 40


def test_own_split_typed(chat: Chat) -> None:
    onboard(chat, confirm=False)
    chat.tap("ob:confirm:fix")
    chat.tap("ob:confirm:plan")
    chat.tap("ob:plan:own")
    chat.say("20 50")
    assert chat.bot.last.startswith("Those need to be three numbers that add up to 100")
    chat.say("25 50 25")
    assert chat.plan is not None
    assert (chat.plan.name, dict(chat.plan.targets_pct)) == (
        "own", {"safety": 25, "core": 50, "growth": 25})  # fmt: skip
    assert "Plan: Your own split. 25% safety, 50% core, 25% growth" in chat.bot.last


def test_exclusion_toggled_twice_comes_back(chat: Chat) -> None:
    chat.say("/start")
    for data in ("ob:lang:en", "ob:goal:growth", "ob:horizon:15", "ob:amount:10000", "ob:day:5",
                 "ob:drop:30"):  # fmt: skip
        chat.tap(data)
    chat.tap("ob:exclude:crypto")
    assert chat.bot.answers[-1][1] == "Crypto left out"
    assert "✓ Crypto" in [b.label for row in chat.bot.edits[-1][2] for b in row]
    chat.tap("ob:exclude:crypto")
    assert chat.bot.answers[-1][1] == "Crypto back in"
    assert chat.profile.exclude == ()
    assert chat.profile.step is Step.EXCLUDE


def test_stale_tap_is_told_and_gets_the_current_question(chat: Chat) -> None:
    chat.say("/start")
    chat.tap("ob:lang:en")
    chat.tap("ob:goal:house")
    chat.tap("ob:goal:retirement")
    assert chat.bot.answers[-1][1] == "That question has moved on."
    assert chat.bot.last == "When will you need it?"
    assert chat.profile.goal == "house"


def test_stop_silences_everything_until_start(chat: Chat) -> None:
    onboard(chat)
    chat.say("/stop")
    assert chat.bot.last.startswith("Stopped. I won't message you again.")
    assert chat.profile.status is Status.STOPPED
    before = len(chat.bot.sent)

    assert send(chat.store, chat.bot, chat.profile, Reply("hello")) is False
    chat.say("what happened today?")
    chat.say("/help")
    chat.tap("ob:confirm:ok")
    assert len(chat.bot.sent) == before, "nothing reaches a stopped user"

    chat.say("/start")
    assert chat.profile.status is Status.ACTIVE
    assert chat.bot.last == f"Welcome back.\n\n{SUMMARY}"


def test_pause_blocks_proactive_sends_but_not_replies(chat: Chat) -> None:
    onboard(chat)
    chat.say("/pause")
    assert chat.profile.status is Status.PAUSED
    assert send(chat.store, chat.bot, chat.profile, Reply("brief"), proactive=True) is False
    assert send(chat.store, chat.bot, chat.profile, Reply("answer")) is True
    chat.say("/resume")
    assert chat.bot.last == "Back on. I'll check in on the 1st."


def test_plan_command_shows_then_changes_the_plan(chat: Chat) -> None:
    onboard(chat)
    chat.say("/plan")
    assert chat.bot.texts[-2] == (
        "Your plan\n\nBalanced. 20% safety, 70% core, 10% growth.\n\nResearch, not advice."
    )
    assert chat.bot.messages[-2].title == "Your plan"
    chat.tap("ob:plan:steady")
    assert chat.profile.step is Step.CONFIRM
    assert "Plan: Steady. 60% safety, 40% core, 0% growth" in chat.bot.last


def test_plan_before_setup_asks_to_finish(chat: Chat) -> None:
    chat.say("/start")
    chat.say("/plan")
    assert chat.bot.last.startswith("Let's finish setting up first.\n\nHi. I'm Networth.")


def test_after_setup_free_text_gets_an_answer_even_without_models(chat: Chat) -> None:
    onboard(chat)
    chat.say("Aaj market kaisa tha?")
    assert chat.bot.last == ("I haven't read today's news yet. I check a few times a day, so "
                             "it won't be long.\n\nResearch, not advice.")  # fmt: skip
    chat.say("Stock X will double", forward_date=1_700_000_000)
    assert chat.bot.last.startswith("I can't search the news right now")
    chat.say("hello")
    assert chat.bot.last.startswith("Hi, I'm Networth.")
    chat.say("tell me about the moon landing")
    assert chat.bot.last.startswith("I can tell you what happened today")
    chat.say("/frobnicate@networth_professor_bot")
    assert chat.bot.last == "I don't know that one yet. /help shows everything I can do."


def test_photo_before_setup_is_ignored(chat: Chat) -> None:
    photo = {"message_id": 1, "chat": {"id": CHAT}, "photo": [{}]}
    handle_update({"update_id": 1, "message": photo}, chat.store, chat.bot, NOW)
    assert chat.bot.sent == []


def test_store_migrations_are_idempotent(tmp_path: Path) -> None:
    first = Store(tmp_path)
    first.log_message(USER, "in", "hi")
    again = Store(tmp_path)
    assert [m.text for m in again.messages(USER)] == ["hi"]


def test_a_redelivered_update_is_applied_once(chat: Chat) -> None:
    chat.say("/start")
    chat.tap("ob:lang:en")
    tap = tap_update("ob:goal:house")
    handle_update(tap, chat.store, chat.bot, NOW)
    handle_update(tap, chat.store, chat.bot, NOW)
    assert (chat.profile.goal, chat.profile.step) == ("house", Step.HORIZON)
    assert chat.bot.texts.count("When will you need it?") == 1, "next question sent once"
    assert len(chat.bot.answers) == 2, "the language tap and the goal tap; the replay is not"


class SlowStore(Store):
    """Widens the read-then-write window so two concurrent taps would both see the old step."""

    def get_plan(self, user_id: str) -> Plan | None:
        time.sleep(0.05)
        return super().get_plan(user_id)


def test_two_taps_on_one_question_at_once_apply_only_one(tmp_path: Path) -> None:
    chat = Chat(tmp_path)
    chat.store = SlowStore(tmp_path / "data")
    chat.say("/start")
    for data in TAPS_TO_CONFIRM[:5]:
        chat.tap(data)
    taps = [tap_update("ob:drop:20"), tap_update("ob:drop:10")]
    threads = [threading.Thread(target=handle_update, args=(t, chat.store, chat.bot, NOW))
               for t in taps]  # fmt: skip
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert chat.profile.step is Step.EXCLUDE
    assert chat.profile.drop_comfort in (10, 20)
    assert [text for _, text in chat.bot.answers].count("That question has moved on.") == 1
