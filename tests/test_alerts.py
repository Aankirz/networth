"""Rare alerts: who gets one, when, and how often."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from networth import config
from networth.app.services import Services
from networth.app.store import Status
from networth.bot.alerts import run_alerts
from networth.watcher.store import Insight
from tests.test_onboarding import Chat, onboard
from tests.watcher_fakes import FAKE_ENV

MONTH = "2026-10"


def insight(
    day: int, n: int = 12, hits: int = 10, baseline: float = 0.55, asset: str = "^NSEBANK",
    weak: bool = False, type: str = "rbi_hike",
) -> Insight:  # fmt: skip
    odds = {"type": type, "asset": asset, "measure": "relative", "benchmark": "^NSEI",
            "hit_rate": hits / n, "baseline": baseline, "n_hits": hits, "n_episodes": n,
            "weak_signal": weak}  # fmt: skip
    return Insight("s1", "news", asset, type, "inflation", dt.date(2026, 10, day), odds)


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    chat = Chat(tmp_path, Services(tmp_path / "data", cfg=cfg))
    onboard(chat)
    return chat


def alerts(chat: Chat, *insights: Insight) -> int:
    return run_alerts(chat.store, chat.bot, chat.services, insights, MONTH)


def test_a_long_uneven_history_sends_one_alert(chat: Chat) -> None:
    assert alerts(chat, insight(9)) == 1
    assert chat.bot.last.startswith("A rare one: RBI rate hike on Oct 9, confirmed.")
    assert "in 10 of 12 past RBI rate hikes" in chat.bot.last


def test_fewer_than_8_episodes_sends_nothing(chat: Chat) -> None:
    assert alerts(chat, insight(9, n=7, hits=6)) == 0


def test_a_small_gap_or_a_weak_signal_sends_nothing(chat: Chat) -> None:
    assert alerts(chat, insight(9, hits=8, baseline=0.6), insight(10, weak=True)) == 0


@pytest.mark.parametrize("status", [Status.STOPPED, Status.PAUSED])
def test_stopped_and_paused_users_get_no_alert(chat: Chat, status: Status) -> None:
    chat.store.save_profile(replace(chat.profile, status=status))
    sent = len(chat.bot.sent)
    assert alerts(chat, insight(9)) == 0
    assert len(chat.bot.sent) == sent


def test_pull_only_users_get_no_alert(chat: Chat) -> None:
    chat.store.save_profile(replace(chat.profile, alerts_on=False))
    assert alerts(chat, insight(9)) == 0


def test_the_monthly_cap_holds_and_an_event_is_never_sent_twice(chat: Chat) -> None:
    assert alerts(chat, insight(9)) == 1
    assert alerts(chat, insight(9)) == 0, "a rerun of the same cycle sends nothing"
    assert alerts(chat, insight(10, type="bank_stress"), insight(11, type="tariff")) == 1
    assert alerts(chat, insight(12, type="inr_shock")) == 0, "two this month already"


def test_an_alert_that_failed_to_send_goes_out_on_the_next_run(chat: Chat, monkeypatch) -> None:
    def down(*args: object) -> dict:
        raise ConnectionError("telegram is down")

    with monkeypatch.context() as m:
        m.setattr(chat.bot, "send_message", down)
        assert alerts(chat, insight(9)) == 0
    assert alerts(chat, insight(9)) == 1


def test_an_event_outside_the_users_markets_sends_nothing(chat: Chat) -> None:
    assert alerts(chat, insight(9, asset="XLF", type="fed_hike")) == 0, "US stocks left out"
