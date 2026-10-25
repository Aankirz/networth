"""Maritime-woken jobs: the schedule list, the /chat entry point, and that a repeated or forged
wake never sends anything twice."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from networth import config
from networth.app import schedule
from networth.app.main import create_app
from networth.app.services import Services
from networth.watcher.store import Cycle
from networth.watcher.store import Store as WatcherStore
from tests.test_alerts import insight
from tests.test_onboarding import Chat, onboard
from tests.watcher_fakes import FAKE_ENV

NOW = dt.datetime(2026, 10, 25, 2, 30, tzinfo=dt.UTC)  # Sunday 08:00 in Kolkata
OPEN = dt.datetime(2026, 10, 26, 4, 30, tzinfo=dt.UTC)  # Monday 10:00 in Kolkata


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    chat = Chat(tmp_path, Services(tmp_path / "data", cfg=cfg))
    onboard(chat)
    chat.store.save_profile(replace(chat.profile, invest_day=25))
    return chat


def job(chat: Chat, prompt: str, cycle=lambda services, now: [], now=NOW) -> str | None:
    return schedule.run_job(prompt, chat.store, chat.bot, chat.services, now, cycle)


def test_schedules_list_the_watcher_and_the_daily_brief_in_kolkata_time() -> None:
    client = TestClient(create_app(None, None, None))
    entries = {e["id"]: e for e in client.get("/schedules").json()}
    assert entries["watcher"]["cron"] == "*/30 9-15 * * 1-5"
    assert entries["brief"]["cron"] == "0 8 * * *"
    assert {e["tz"] for e in entries.values()} == {"Asia/Kolkata"}
    assert all(e["enabled"] and e["prompt"] for e in entries.values())


def test_a_non_scheduled_chat_call_runs_nothing(chat: Chat, monkeypatch) -> None:
    started: list[str] = []
    monkeypatch.setattr(schedule, "start_job", lambda prompt, *a: started.append(prompt))
    client = TestClient(create_app(chat.store, chat.bot, "s", None, chat.services))
    reply = client.post("/chat", json={"message": "RUN_BRIEF", "source": "user"}).json()
    assert reply["response"].startswith("Networth talks on Telegram")
    client.post("/chat", json={"message": "RUN_BRIEF", "source": "scheduled"})
    assert started == ["RUN_BRIEF"]


def test_the_daily_brief_never_goes_out_twice_on_the_same_day(chat: Chat) -> None:
    before = len(chat.bot.sent)
    assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 1 sent"
    assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 0 sent"
    assert len(chat.bot.sent) == before + 1
    assert chat.bot.last.startswith("Morning. It's your investing day, and ₹1 lakh is ready.")


def test_a_brief_that_failed_to_send_goes_out_on_the_next_run(chat: Chat, monkeypatch) -> None:
    def down(*args: object) -> dict:
        raise ConnectionError("telegram is down")

    with monkeypatch.context() as m:
        m.setattr(chat.bot, "send_message", down)
        assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 0 sent"
    assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 1 sent"
    assert chat.bot.last.startswith("Morning. It's your investing day, and ₹1 lakh is ready.")


def test_no_brief_on_other_days(chat: Chat) -> None:
    chat.store.save_profile(replace(chat.profile, invest_day=3))
    assert job(chat, schedule.BRIEF_PROMPT) == "brief ran: 0 sent"


def add_cycle(chat: Chat, finished: dt.datetime) -> None:
    store = WatcherStore.open(chat.services.watcher_db)
    store.add_cycle(Cycle(finished - dt.timedelta(minutes=2), finished, {}, 0.0, ()))
    store.close()


def test_a_watcher_wake_right_after_a_cycle_is_skipped(chat: Chat) -> None:
    ran: list[dt.datetime] = []
    add_cycle(chat, OPEN - dt.timedelta(minutes=10))
    outcome = job(chat, schedule.WATCHER_PROMPT, lambda s, now: ran.append(now) or [], OPEN)
    assert outcome.startswith("watcher skipped") and ran == []


def test_a_watcher_run_sends_rare_alerts_once(chat: Chat) -> None:
    add_cycle(chat, OPEN - dt.timedelta(minutes=40))
    rare = lambda s, now: [insight(9)]  # noqa: E731
    assert (
        job(chat, schedule.WATCHER_PROMPT, rare, OPEN)
        == "watcher ran: 1 insights, 1 alerts sent, 0 watch messages sent, 0 news alerts sent"
    )
    assert (
        job(chat, schedule.WATCHER_PROMPT, rare, OPEN)
        == "watcher ran: 1 insights, 0 alerts sent, 0 watch messages sent, 0 news alerts sent"
    )


def test_alerts_lost_when_the_vm_stopped_after_a_cycle_go_out_on_the_next_run(
    chat: Chat, monkeypatch
) -> None:
    from tests.test_chat import weekend_watcher

    weekend_watcher(chat.services.watcher_db, OPEN - dt.timedelta(hours=2))
    store = WatcherStore.open(chat.services.watcher_db)
    store.put_insights([insight(9)], OPEN - dt.timedelta(hours=2))
    store.close()
    monkeypatch.setattr(schedule.run, "run_cycle", lambda *args: None)
    outcome = schedule.run_job(schedule.WATCHER_PROMPT, chat.store, chat.bot, chat.services, OPEN)
    assert (
        outcome
        == "watcher ran: 1 insights, 1 alerts sent, 0 watch messages sent, 0 news alerts sent"
    )


def test_unknown_prompts_and_overlapping_runs_do_nothing(chat: Chat) -> None:
    assert job(chat, "DROP TABLE") is None
    with schedule.JOB_LOCK:
        assert job(chat, schedule.BRIEF_PROMPT) is None


def test_a_forged_watcher_call_outside_market_hours_spends_nothing(chat: Chat) -> None:
    ran: list[dt.datetime] = []
    count = lambda s, now: ran.append(now) or []  # noqa: E731
    friday_evening = dt.datetime(2026, 10, 23, 10, 30, tzinfo=dt.UTC)  # 16:00 in Kolkata
    for when in (NOW, friday_evening):
        assert job(chat, schedule.WATCHER_PROMPT, count, when) == (
            "watcher skipped: outside market hours"
        )
    assert ran == []
    assert job(chat, schedule.WATCHER_PROMPT, count, OPEN).startswith("watcher ran")


def test_the_market_hours_match_the_watcher_cron() -> None:
    watcher = next(s for s in schedule.SCHEDULES if s.id == "watcher")
    first, last = watcher.cron.split()[1].split("-")
    assert schedule.MARKET_HOURS == range(int(first), int(last) + 1)
    assert watcher.cron.split()[4] == "1-5"
