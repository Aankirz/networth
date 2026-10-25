"""The news notifier: a confirmed story about what a user owns sends one message, at most 3 a
day, never in quiet hours (22:00 to 08:00 IST), never after /alerts off."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from networth import notify
from networth.holdings.model import Holding, Holdings, Source, to_json
from networth.ratings import rate
from networth.ratings.model import view_for
from networth.watcher.store import Article, Confirmed, NewStory
from networth.watcher.store import Store as WatcherStore
from tests.ratings_fakes import FakeSources
from tests.test_onboarding import USER, Chat, onboard
from tests.test_ratings import TABLE

IST = ZoneInfo("Asia/Kolkata")
DAY = dt.datetime(2026, 10, 26, 11, 0, tzinfo=IST)  # a Monday, 11:00 IST


@pytest.fixture
def owner(tmp_path: Path) -> Chat:
    c = Chat(tmp_path)
    onboard(c)
    held = Holding("HDFC Bank", 10, 1500.0, "INR", identifier="HDFCBANK", price=1600.0)
    c.store.save_holdings(USER, to_json(Holdings(USER, Source.SCREENSHOT, DAY, (held,), True)))
    return c


def story(c: Chat, sid: str, title: str, at: dt.datetime) -> None:
    db = WatcherStore.open(c.services.watcher_db)
    url = f"https://pub.example/{sid}"
    db.add_articles([Article(url, "pub.example", "pub.example", title, "", at, "q", at)])
    db.assign([NewStory(sid, title, at)], {sid: [url]})
    db.put_decisions({sid: Confirmed(("reuters.com", "mint.com"), None)}, at)
    db.close()


def run(c: Chat, now: dt.datetime) -> int:
    return notify.run_notify(c.store, c.bot, c.services, now, sources=FakeSources(),
                             rater=lambda symbol: None)  # fmt: skip


def test_a_story_about_a_holding_sends_one_alert_with_the_move_in_the_users_money(
    owner: Chat,
) -> None:
    story(owner, "s1", "HDFC Bank profit jumps 20%", DAY - dt.timedelta(hours=1))
    before = len(owner.bot.sent)
    assert run(owner, DAY) == 1
    m = owner.bot.messages[-1]
    assert m.title == "News on HDFC Bank"
    text = owner.bot.last
    assert "HDFC Bank profit jumps 20%.\nConfirmed by 2 publishers: reuters.com, mint.com." in text
    assert "moved" in text and "on the last close (Yahoo:HDFCBANK.NS, 2026-10-23)" in text
    assert "On your ₹16,000 in it, that is about" in text
    assert "advice" not in text.lower() and not m.footer
    assert run(owner, DAY + dt.timedelta(minutes=30)) == 0, "once per story"
    assert len(owner.bot.sent) == before + 1


def test_at_most_three_alerts_a_day(owner: Chat) -> None:
    for i in range(4):
        story(owner, f"s{i}", f"HDFC Bank story {i}", DAY - dt.timedelta(hours=1 + i))
    assert run(owner, DAY) == 3
    assert run(owner, DAY + dt.timedelta(hours=1)) == 0, "the fourth waits for tomorrow"
    tomorrow = DAY + dt.timedelta(days=1)
    story(owner, "s9", "HDFC Bank names a new chief", tomorrow - dt.timedelta(hours=1))
    assert run(owner, tomorrow) >= 1


@pytest.mark.parametrize("hour", [22, 23, 0, 7])
def test_nothing_goes_out_in_quiet_hours_and_the_story_waits(owner: Chat, hour: int) -> None:
    night = DAY.replace(hour=hour)
    story(owner, "s1", "HDFC Bank profit jumps", night - dt.timedelta(hours=1))
    assert run(owner, night) == 0
    morning = (night + dt.timedelta(days=1 if hour >= 22 else 0)).replace(hour=8)
    assert run(owner, morning) == 1


def test_alerts_off_stops_them_and_on_brings_them_back(owner: Chat) -> None:
    story(owner, "s1", "HDFC Bank profit jumps", DAY - dt.timedelta(hours=1))
    owner.say("/alerts off")
    assert owner.bot.last.startswith("News alerts are off.")
    assert not owner.profile.alerts_on
    assert run(owner, DAY) == 0
    owner.say("/alerts on")
    assert owner.profile.alerts_on
    assert run(owner, DAY) == 1


def test_a_story_about_nothing_they_own_or_follow_sends_nothing(owner: Chat) -> None:
    story(owner, "s1", "Fitness app launches in Pune", DAY - dt.timedelta(hours=1))
    assert run(owner, DAY) == 0


def test_a_failed_send_releases_the_claim_for_the_next_run(owner: Chat, monkeypatch) -> None:
    story(owner, "s1", "HDFC Bank profit jumps", DAY - dt.timedelta(hours=1))
    monkeypatch.setattr(notify, "send", lambda *a, **k: False)
    assert run(owner, DAY) == 0
    monkeypatch.undo()
    assert run(owner, DAY + dt.timedelta(minutes=30)) == 1


def test_the_rating_line_appears_only_when_the_view_moved(owner: Chat) -> None:
    base = rate("HDFCBANK", now=DAY, sources=FakeSources(), table=TABLE)

    def scored(score: int) -> notify.Rater:
        return lambda symbol: dataclasses.replace(base, view=view_for(score), score=score)

    sent = []
    for i, score in enumerate((50, 50, 70)):
        story(owner, f"s{i}", f"HDFC Bank story {i}", DAY - dt.timedelta(hours=1))
        notify.run_notify(owner.store, owner.bot, owner.services, DAY + dt.timedelta(minutes=i),
                          sources=FakeSources(), rater=scored(score))  # fmt: skip
        sent.append(owner.bot.last)
    assert "Our rating" not in sent[0], "the first view is only remembered"
    assert "Our rating" not in sent[1], "same view, no line"
    assert "Our rating moved from Neutral to Positive (70/100)." in sent[2]
