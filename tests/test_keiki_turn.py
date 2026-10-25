"""Keiki turns end to end: the signed endpoint, replay safety, and a turn running the same
pipeline as Telegram (setup, commands, chat through the guard). Fake Keiki, fake models."""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from networth import config
from networth.app.main import create_app
from networth.app.services import Services
from networth.app.store import Channel, Profile, Step, Store, new_email_profile, now_iso
from networth.bot.onboarding import Reply
from networth.chat import Intent, explain
from networth.keiki.mail import NOTICE, Mail
from networth.keiki.turn import Harness, run_turn
from networth.keiki.wire import parse
from networth.net import CallRecord, append_record
from tests.keiki_fakes import (
    ADDRESS,
    AGENT,
    GMAIL_QUOTE,
    MAILTRACK_FOOTER,
    FakeApi,
    FakeTurnClient,
    body,
    ed25519_headers,
    fake_keys,
    slack_payload,
    turn_payload,
)
from tests.test_chat import GOOD_EXPLANATION, IPO_TEXT, FakeChatModels, weekend_watcher
from tests.test_onboarding import FakeBot
from tests.watcher_fakes import FAKE_ENV


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


class Keiki:
    """One email contact talking to Networth through Keiki."""

    def __init__(self, tmp_path: Path, services: Services | None = None) -> None:
        self.store = Store(tmp_path / "data")
        self.services = services or Services(tmp_path / "data")
        self.client = FakeTurnClient()
        self._turns = 0

    def say(self, *texts: str, address: str = ADDRESS, now: str | None = None) -> str:
        self._turns += 1
        turn = parse(turn_payload(*texts, turn_id=f"t{self._turns}", address=address))
        assert turn is not None
        return run_turn(turn, self.store, self.services, self.client, now or now_iso())

    @property
    def last(self) -> str:
        return self.client.texts[-1]

    def profile(self, address: str = ADDRESS) -> Profile:
        user_id = self.store.contact_user(address)
        profile = self.store.get_profile(user_id) if user_id else None
        assert profile is not None, "the contact has a profile"
        return profile


def set_up(keiki: Keiki) -> Profile:
    profile = replace(new_email_profile(ADDRESS, now_iso()), step=Step.DONE, goal="growth",
                      monthly_amount=50_000, currency="INR", invest_day=1, lang="en")  # fmt: skip
    keiki.store.save_profile(profile)
    keiki.store.bind_contact(ADDRESS, profile.user_id)
    return profile


def test_a_new_contact_is_set_up_by_email_in_four_answers(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    keiki.say("Hello")
    assert keiki.last.startswith("Hi, I'm Networth.")
    assert keiki.last.endswith("Reply with one of: A house, Retirement, Education, Just growing it")
    for answer in ("retirement", "1 lakh", "5", "English"):
        keiki.say(answer)
    p = keiki.profile()
    assert (p.channel, p.chat_id, p.deliver_to, p.step) == ("email", 0, Channel.EMAIL, Step.DONE)
    assert (p.goal, p.monthly_amount, p.invest_day, p.lang) == ("retirement", 100_000, 5, "en")
    assert keiki.last.startswith("You're set. I'll write on the 5th of each month")
    assert ADDRESS not in p.user_id, "the address never becomes a user id in logs"


def test_a_bad_answer_by_email_gets_a_retry_and_the_same_question(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    keiki.say("Hello")
    keiki.say("house")
    keiki.say("lots")
    assert keiki.profile().step is Step.AMOUNT
    assert keiki.last.startswith("I didn't catch that amount.")


def test_start_by_email_restarts_the_short_setup(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    set_up(keiki)
    keiki.say("/start")
    assert keiki.profile().step is Step.GOAL
    assert keiki.last.startswith("Hi, I'm Networth.")


def test_a_command_by_email_runs_like_on_telegram(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    set_up(keiki)
    keiki.say("/help")
    assert keiki.last.startswith("Here's what I can do.")
    assert keiki.client.completed == [("completed", None)]


def test_a_chat_turn_runs_the_guard_and_blocks_a_planted_number(tmp_path: Path, cfg) -> None:
    planted = "The RBI raised its repo rate to 6.25%, reported by rbi.org.in."
    models = FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value, writes=[planted, planted])
    keiki = Keiki(tmp_path, Services(tmp_path / "data", None, models, None, cfg))
    set_up(keiki)
    weekend_watcher(keiki.services.watcher_db, dt.datetime.now(dt.UTC) - dt.timedelta(hours=1))
    keiki.say("What happened today?")
    assert keiki.last.startswith("Confirmed in the last 24 hours:")
    assert "RBI raises repo rate to 5.50%" in keiki.last
    assert not any("6.25" in text for text in keiki.client.texts)
    assert len(models.tasks) == 2, "one draft and one rewrite, both blocked"


def test_quoted_mail_is_not_read_as_part_of_the_question(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    set_up(keiki)
    keiki.say("/help\n\nOn Fri, Oct 24, Networth wrote:\n> Investing day")
    assert keiki.last.startswith("Here's what I can do.")


def test_a_notice_turn_sends_queued_mail_and_nothing_else(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    profile = set_up(keiki)
    mail = Mail(keiki.store, FakeApi())
    keiki.services = replace(keiki.services, mail=mail)
    mail.queue(profile, Reply("Investing day, Nov 1."))
    keiki.say(NOTICE)
    assert keiki.client.sent == [("Investing day, Nov 1.", "outbox:1")]
    assert keiki.client.completed == [("completed", None)]


def test_a_failed_turn_is_reported_to_keiki_as_failed(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    set_up(keiki)
    keiki.client.fail_send = True
    assert keiki.say("/help") == "failed"
    assert keiki.client.completed == [("failed", "ConnectionError")]


def endpoint(tmp_path: Path, client: FakeTurnClient, agent: str = AGENT) -> TestClient:
    store = Store(tmp_path / "data")
    keiki = Harness(agent, fake_keys(), None, client=lambda url, token: client,
                    start=lambda work: work())  # fmt: skip
    return TestClient(create_app(store, FakeBot(), "s", None, Services(tmp_path / "data"), keiki))


def push(app: TestClient, payload: dict, *, t: int | None = None, signed: bool = True):
    raw = body(payload)
    headers = ed25519_headers(raw, t=t or int(time.time())) if signed else {}
    return app.post("/keiki/turn", content=raw, headers=headers)


def test_an_unsigned_or_stale_turn_gets_401_and_runs_nothing(tmp_path: Path) -> None:
    client = FakeTurnClient()
    app = endpoint(tmp_path, client)
    unsigned = push(app, turn_payload("/help"), signed=False)
    stale = push(app, turn_payload("/help"), t=int(time.time()) - 600)
    assert (unsigned.status_code, unsigned.json()) == (401, {"error": "unsigned"})
    assert (stale.status_code, stale.json()) == (401, {"error": "stale"})
    assert client.sent == [] and client.completed == []


def test_a_turn_for_another_agent_gets_401(tmp_path: Path) -> None:
    response = push(endpoint(tmp_path, FakeTurnClient(), agent="our-agent"), turn_payload("hi"))
    assert (response.status_code, response.json()) == (401, {"error": "unknown_agent"})


def test_a_replayed_turn_is_answered_once(tmp_path: Path) -> None:
    client = FakeTurnClient()
    app = endpoint(tmp_path, client)
    first, again = push(app, turn_payload("Hello")), push(app, turn_payload("Hello"))
    assert first.status_code == 202
    assert (again.status_code, again.json()) == (200, {"ok": True, "duplicate": True})
    assert client.completed == [("completed", None)]
    assert len(client.sent) == 1


def test_an_arrival_is_acknowledged_and_runs_nothing(tmp_path: Path) -> None:
    client = FakeTurnClient()
    response = push(endpoint(tmp_path, client), {"type": "keiki.turn.arrival", "agentId": AGENT})
    assert response.status_code == 202
    assert client.completed == []


def test_without_keiki_configured_the_endpoint_answers_503(tmp_path: Path) -> None:
    app = TestClient(create_app(Store(tmp_path), FakeBot(), "s"))
    assert push(app, turn_payload("hi")).status_code == 503


class CostedModels(FakeChatModels):
    """Logs each write to the call log as a paid call, like the real models do."""

    def __init__(self, call_log: Path, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.call_log = call_log

    def write(self, task: str, facts: str, feedback: str | None = None) -> str:
        stamp = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        append_record(self.call_log, CallRecord(stamp, "write", "writer", "m", 1, 0, 1, 0.002,
                                                True, ""))  # fmt: skip
        return super().write(task, facts, feedback)


def turn_log(keiki: Keiki) -> list[dict]:
    lines = keiki.services.turn_log.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_each_turn_logs_its_ids_intent_guard_and_cost_but_no_text(tmp_path: Path, cfg) -> None:
    data = tmp_path / "data"
    planted = "The RBI raised its repo rate to 6.25%, reported by rbi.org.in."
    models = CostedModels(data / "llm_calls.jsonl", intent=Intent.WHAT_HAPPENED_TODAY.value,
                          writes=[planted, planted])  # fmt: skip
    keiki = Keiki(tmp_path, Services(data, None, models, None, cfg))
    profile = set_up(keiki)
    weekend_watcher(keiki.services.watcher_db, dt.datetime.now(dt.UTC) - dt.timedelta(hours=1))
    hour_ago = (dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)).isoformat(timespec="seconds")
    append_record(data / "llm_calls.jsonl", CallRecord(hour_ago, "write", "writer", "m", 1, 0,
                                                       1, 5.0, True, ""))  # fmt: skip
    turn = parse(turn_payload("What happened today?", traceId="tr_9", heldBack=True))
    assert turn is not None
    run_turn(turn, keiki.store, keiki.services, keiki.client, now_iso())
    (row,) = turn_log(keiki)
    assert {k: v for k, v in row.items() if k != "ts"} == {
        "turn_id": "t1", "trace_id": "tr_9", "user_id": profile.user_id, "channel": "agentmail",
        "kind": "chat", "intent": "what_happened_today", "guard": "template",
        "cost_usd": 0.004, "held_back": True, "outcome": "completed",
    }  # fmt: skip
    raw = keiki.services.turn_log.read_text(encoding="utf-8")
    assert ADDRESS not in raw and "What happened" not in raw


def test_a_command_turn_logs_no_intent_and_a_failed_turn_logs_its_outcome(tmp_path) -> None:
    keiki = Keiki(tmp_path)
    set_up(keiki)
    keiki.say("/help")
    keiki.client.fail_send = True
    keiki.say("/help")
    first, second = turn_log(keiki)
    assert (first["kind"], first["intent"], first["outcome"]) == ("command", None, "completed")
    assert second["outcome"] == "failed"


def test_a_first_email_that_asks_something_is_answered_then_set_up(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    keiki.say("What happened today?")
    assert len(keiki.client.texts) == 2, "an answer, then the first setup question"
    assert not keiki.client.texts[0].startswith("Hi, I'm Networth.")
    assert keiki.last.startswith("Hi, I'm Networth.")
    (row,) = turn_log(keiki)
    assert (row["kind"], row["intent"]) == ("welcome", "what_happened_today")


def test_a_slack_dm_runs_the_same_pipeline_and_threads_share_one_profile(tmp_path) -> None:
    keiki = Keiki(tmp_path)
    for i, thread in enumerate(("1.1", "2.2"), start=1):
        turn = parse(slack_payload("/help", thread, f"s{i}"))
        assert turn is not None
        run_turn(turn, keiki.store, keiki.services, keiki.client, now_iso())
    first, second = turn_log(keiki)
    assert (first["channel"], first["kind"]) == ("slack", "welcome")
    assert (second["kind"], second["user_id"]) == ("command", first["user_id"])
    assert "*" not in keiki.last and "<" not in keiki.last, "plain text, as for email"


def test_an_email_with_a_mailtrack_footer_is_explained_without_fetching(
    tmp_path, cfg, monkeypatch
) -> None:
    fetched: list[str] = []
    monkeypatch.setattr(explain, "page_text", lambda url, client=None: fetched.append(url) or "")
    data = tmp_path / "data"
    models = CostedModels(data / "llm_calls.jsonl", intent=Intent.EXPLAIN_THIS.value,
                          writes=[GOOD_EXPLANATION])  # fmt: skip
    keiki = Keiki(tmp_path, Services(data, None, models, None, cfg))
    set_up(keiki)
    keiki.say(IPO_TEXT + MAILTRACK_FOOTER + GMAIL_QUOTE)
    assert fetched == []
    assert keiki.last == GOOD_EXPLANATION


def test_two_email_threads_from_one_sender_are_one_user(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    keiki.say("Hello")
    keiki.say("Saving for a house")
    first, second = turn_log(keiki)
    assert first["user_id"] == second["user_id"]
    assert (first["kind"], second["kind"]) == ("welcome", "onboarding")


def test_a_first_email_that_is_a_command_gets_the_setup_not_a_chat_answer(tmp_path) -> None:
    keiki = Keiki(tmp_path)
    keiki.say("/brief")
    assert keiki.client.texts == [keiki.last] and keiki.last.startswith("Hi, I'm Networth.")
    (row,) = turn_log(keiki)
    assert (row["kind"], row["intent"]) == ("welcome", None)


def test_a_first_email_that_only_greets_gets_just_the_setup(tmp_path: Path) -> None:
    keiki = Keiki(tmp_path)
    keiki.say("Hello")
    assert keiki.client.texts == [keiki.last]
