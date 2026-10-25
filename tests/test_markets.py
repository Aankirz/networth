"""Market answers end to end with a fake Yahoo: each question in the brief's table routes to
its answer, leads with the number asked for, says its source and date, and carries its card."""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from networth import guard, market
from networth.app.services import Services
from networth.chat import markets, today
from tests.test_chat import FakeChatModels, cfg, weekend_watcher  # noqa: F401 - cfg is the config fixture
from tests.test_market import SWIGGY, TESLA, FakeSource
from tests.test_onboarding import NOW, Chat, onboard

DAYS = pd.bdate_range(end="2026-10-23", periods=5 * 261)
SWIGGY_CLOSES = pd.Series([430.0] * (len(DAYS) - 2) + [211.4, 176.0], index=DAYS)
TESLA_CLOSES = pd.Series([200.0 + i / 10 for i in range(len(DAYS))], index=DAYS)
NIFTY = pd.Series([15000.0 * (1 + i / len(DAYS) / 4) for i in range(len(DAYS))], index=DAYS)
INFO = {
    "SWIGGY.NS": {"currency": "INR", "exchange": "NSI", "low_52w": 174.95, "high_52w": 434.0},
    "TSLA": {"currency": "USD", "exchange": "NMS", "low_52w": 200.0, "high_52w": 340.0},
    "^NSEI": {"currency": "INR", "exchange": "NSI"},
    "^BSESN": {"currency": "INR", "exchange": "BSE"},
}
CLOSES = {
    "SWIGGY.NS": SWIGGY_CLOSES,
    "TSLA": TESLA_CLOSES,
    "^NSEI": NIFTY,
    "^BSESN": NIFTY * 3,
    "^GSPC": NIFTY / 3,
    "^IXIC": NIFTY,
    "^DJI": NIFTY * 3,
}


class Yahoo(FakeSource):
    def __init__(self) -> None:
        super().__init__(CLOSES, INFO, {"swiggy": [SWIGGY], "tesla": [TESLA]})


@pytest.fixture
def chat(tmp_path: Path, cfg, monkeypatch) -> Chat:  # noqa: F811
    monkeypatch.setattr(market, "Yahoo", Yahoo)
    markets._found.cache_clear()
    user = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", None, None, cfg))
    onboard(user)
    return user


@pytest.mark.parametrize(("text", "intent"), [
    ("I hold 390 Swiggy shares at 230", "position"),
    ("I hold 390 Swiggy shares at 230, should I sell?", "stock_view"),
    ("Should I invest in Swiggy shares now?", "stock_view"),
    ("How has Nifty 50 done over the last 5 years?", "price_history"),
    ("what is tesla's current price", "price"),
    ("nifty vs sensex over 5 years", "compare"),
])  # fmt: skip
def test_the_brief_table_questions_route_to_market_answers(text: str, intent: str,
                                                           monkeypatch) -> None:  # fmt: skip
    monkeypatch.setattr(market, "Yahoo", Yahoo)
    routed = markets.route(text, "INR")
    assert routed is not None and routed[0] == intent


@pytest.mark.parametrize("text", [
    "kya bechna chahiye", "what happened today", "should I sell my holdings?", "hello",
])  # fmt: skip
def test_questions_naming_no_stock_are_not_market_answers(text: str, monkeypatch) -> None:
    monkeypatch.setattr(market, "Yahoo", Yahoo)
    assert markets.route(text, "INR") is None


def test_a_price_leads_with_the_close_and_says_its_source(chat: Chat) -> None:
    chat.say("what is tesla's current price")
    first, *_, last = chat.bot.last.split("\n\n")
    assert first.startswith("Tesla, Inc. closed at $")
    assert "23 Oct 2026" in first or "Oct 23" in first or "23 October" in first
    assert last.startswith("Source: Yahoo Finance")


def test_a_typed_holding_gets_its_value_and_gain_from_the_close(chat: Chat) -> None:
    chat.say("I hold 390 Swiggy shares at 230")
    first = chat.bot.last.split("\n\n")[0]
    assert first.startswith("Your 390 Swiggy Limited shares at ₹230")
    assert "₹89,700" in first and "₹68,640" in first and "down ₹21,060" in first


def test_should_i_gets_networths_read_in_the_first_line(chat: Chat) -> None:
    chat.say("Should I invest in Swiggy shares now?")
    assert chat.bot.last.startswith("Networth's read: I would not add to Swiggy Limited")


def test_a_rating_from_13c_leads_when_it_answers(chat: Chat, monkeypatch) -> None:
    class Rating:
        class view:  # noqa: N801 - stands in for networth.ratings.View
            value = "Positive"

        score, confidence, outlook, drivers = 68, "medium", "Earnings are turning.", ()

        class track:  # noqa: N801
            text = "Past Positive calls beat the index 6 times in 10."

    monkeypatch.setattr(markets, "rated", lambda symbol: Rating)
    chat.say("Should I invest in Swiggy shares now?")
    assert chat.bot.last.startswith("Networth's read: I would hold Swiggy Limited and add on dips")
    assert "Score 68/100" in chat.bot.last


def test_history_gives_the_total_the_yearly_rate_and_the_worst_fall(chat: Chat) -> None:
    chat.say("How has Swiggy done over the last 5 years?")
    first, fall, source = chat.bot.last.split("\n\n")
    assert first.startswith("Swiggy Limited is down ")
    assert fall.startswith("The worst fall in that time was ")
    assert source.startswith("Source: Yahoo Finance, daily closes to ")


def test_no_data_says_so_and_gives_no_number(chat: Chat, monkeypatch) -> None:
    class Empty(Yahoo):
        def closes(self, symbol: str, years: float) -> pd.Series:
            return pd.Series(dtype=float)

    monkeypatch.setattr(market, "Yahoo", Empty)
    chat.say("what is tesla's current price")
    assert chat.bot.last.startswith("I couldn't get prices for Tesla, Inc. from Yahoo Finance")


PRICE_KEYS = {"type", "symbol", "name", "exchange", "currency", "price", "change", "change_pct",
              "direction", "low_52w", "high_52w", "series", "source"}  # fmt: skip


def test_cards_carry_a_source_with_name_url_and_date(monkeypatch) -> None:
    monkeypatch.setattr(market, "Yahoo", Yahoo)
    q = market.quote("TSLA", name="Tesla, Inc.")
    assert q is not None
    card = markets.price_card(q)
    assert card["type"] == "price"
    assert set(card["source"]) == {"name", "url", "as_of"}
    assert card["source"]["url"].startswith("https://finance.yahoo.com/")
    assert len(card["series"]["points"]) <= markets.MAX_POINTS


def test_a_slow_name_search_answers_in_time_without_a_number(chat: Chat, monkeypatch) -> None:
    class Slow(Yahoo):
        def search(self, text: str) -> list[dict]:
            time.sleep(0.5)
            return super().search(text)

    monkeypatch.setattr(market, "Yahoo", Slow)
    monkeypatch.setattr(markets, "SEARCH_DEADLINE_S", 0.05)
    chat.say("what is tesla's current price")
    assert chat.bot.last.startswith("Yahoo Finance didn't answer in time")
    assert not any(c.isdigit() for c in chat.bot.last)


def test_a_slow_search_never_takes_a_question_that_names_nothing(monkeypatch) -> None:
    monkeypatch.setattr(markets, "found_in_time", lambda text, currency: None)
    assert markets.route("should i buy now?", "INR") is None


def test_today_leads_with_the_home_indices_then_confirmed_news(chat: Chat) -> None:
    weekend_watcher(chat.services.watcher_db, dt.datetime.fromisoformat(NOW))
    chat.say("what happened today?")
    tiles, news, source = chat.bot.last.split("\n\n")
    assert tiles.startswith("Markets at the close on 23 Oct 2026:\n• Nifty 50 ")
    assert "• Sensex " in tiles and "S&P 500" not in tiles
    assert news.startswith("Confirmed in the last 24 hours:")
    assert source == "Index levels: Yahoo Finance, close of 23 Oct 2026."


def test_a_dollar_reader_gets_the_s_and_p_nasdaq_and_dow(chat: Chat) -> None:
    chat.store.save_profile(replace(chat.profile, currency="USD"))
    chat.say("what happened today?")
    names = [line.split(" ")[1] for line in chat.bot.last.splitlines() if line.startswith("•")]
    assert names[:3] == ["S&P", "Nasdaq", "Dow"]


def test_reports_that_were_not_confirmed_are_never_mentioned(chat: Chat) -> None:
    from networth.watcher.store import NewStory, Rejected
    from networth.watcher.store import Store as WatcherStore

    now = dt.datetime.fromisoformat(NOW)
    weekend_watcher(chat.services.watcher_db, now)
    store = WatcherStore.open(chat.services.watcher_db)
    store.assign([NewStory("s2", "Bank X to merge with Bank Y", now)], {"s2": []})
    store.put_decisions({"s2": Rejected("one blog", ("blog.example",))}, now)
    store.close()
    chat.say("what happened today?")
    assert "Bank X" not in chat.bot.last
    assert "could not confirm" not in chat.bot.last and "other report" not in chat.bot.last


def test_today_carries_a_market_today_card_with_a_source(chat: Chat) -> None:
    answer = today.what_happened(chat.services, dt.datetime.fromisoformat(NOW), currency="INR")
    assert answer.card is not None and answer.card["type"] == "market_today"
    assert [t["name"] for t in answer.card["tiles"]] == ["Nifty 50", "Sensex"]
    assert set(answer.card["tiles"][0]) == {"symbol", "name", "level", "change", "change_pct",
                                            "direction"}  # fmt: skip
    assert answer.card["source"]["as_of"] == "close of 23 Oct 2026"


def test_with_no_index_data_today_is_the_news_alone(chat: Chat, monkeypatch) -> None:
    monkeypatch.setattr(markets, "index_quotes", lambda currency: [])
    weekend_watcher(chat.services.watcher_db, dt.datetime.fromisoformat(NOW))
    chat.say("what happened today?")
    assert chat.bot.last.startswith("Confirmed in the last 24 hours:")


SOURCE = "Networth's read: I would not add to Swiggy Limited right now. It closed at ₹176.00."


@pytest.mark.parametrize("draft", [
    "Networth's read: abhi Swiggy mein aur kharidna theek nahin. ₹176.00 par band hua.",
    "Networth's read: I would not buy more of it now. It closed at ₹176.00.",
])  # fmt: skip
def test_a_view_may_say_what_networth_would_do(draft: str) -> None:
    assert guard.check(draft, SOURCE, view=True).ok
    assert not guard.check(draft, SOURCE).ok, "outside a view the old word rules hold"


@pytest.mark.parametrize("draft", [
    "Networth's read: I would buy Swiggy, it will reach ₹250.",
    "Networth's read: Swiggy is a sure-shot multibagger at ₹176.00.",
])  # fmt: skip
def test_a_view_still_never_invents_a_number_or_promises_one(draft: str) -> None:
    assert not guard.check(draft, SOURCE, view=True).ok


def test_a_hinglish_view_keeps_the_writers_words_and_blocks_a_planted_number(
    tmp_path: Path, cfg, monkeypatch  # noqa: F811
) -> None:  # fmt: skip
    monkeypatch.setattr(market, "Yahoo", Yahoo)
    planted = "Networth's read: Swiggy ₹300 tak jayega, kharid lo."
    honest = "Networth's read: abhi Swiggy mein aur kharidna theek nahin."
    models = FakeChatModels(writes=[planted, honest])
    user = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", models, None, cfg))
    onboard(user)
    user.say("Swiggy kharidna chahiye kya?")
    assert user.bot.last.startswith(honest)
    assert "VIEW" not in models.tasks[0] and "Keep Networth's read" in models.tasks[0]
