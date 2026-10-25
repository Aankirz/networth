"""Memory callbacks: a term asked in chat comes back once in a brief, and only when this
month's confirmed news uses it. Fake Telegram, fake models, a tmp watcher database."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from networth import config
from networth.app.services import Services
from networth.chat import Intent
from networth.memory import asked_terms, split_concept
from networth.watcher.store import Article, Confirmed, NewStory, Rejected
from networth.watcher.store import Store as WatcherStore
from tests.test_chat import FakeChatModels
from tests.test_onboarding import NOW, USER, Chat, onboard
from tests.watcher_fakes import FAKE_ENV

ORBIT = "Orbit Solar IPO has an OFS of ₹400 crore"
LINE = f"Earlier you asked what OFS means. It comes up in this month's news: {ORBIT}."


def test_glossary_concepts_split_into_the_terms_people_ask_about() -> None:
    assert split_concept("Offer for sale (OFS)") == ["Offer for sale", "OFS"]
    assert split_concept("Subscription (e.g. 3x)") == ["Subscription"]
    assert split_concept("P/E ratio") == ["P/E ratio"]
    assert asked_terms("what is OFS?") == ["OFS"]
    assert asked_terms("what is an index fund?") == ["Index fund"]


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    models = FakeChatModels(Intent.EXPLAIN_THIS.value)
    chat = Chat(tmp_path, Services(tmp_path / "data", None, models, None, cfg))
    onboard(chat)
    return chat


def news(chat: Chat, title: str, *, days_ago: int = 3, confirmed: bool = True) -> None:
    seen = dt.datetime.fromisoformat(NOW) - dt.timedelta(days=days_ago)
    slug = re.sub(r"\W+", "-", title.lower())
    url = f"https://www.livemint.com/{slug}"
    db = WatcherStore.open(chat.services.watcher_db)
    db.add_articles([Article(url, "livemint.com", "livemint.com", title, "", seen, "q", seen)])
    sid = f"s-{slug}"
    db.assign([NewStory(sid, title, seen)], {sid: [url]})
    verdict = Confirmed(("livemint.com",), None) if confirmed else Rejected("one", ())
    db.put_decisions({sid: verdict}, seen)
    db.close()


def test_a_term_in_this_months_news_comes_back_in_the_brief(chat: Chat) -> None:
    chat.say("what is OFS?")
    news(chat, ORBIT)
    chat.say("/brief")
    assert chat.bot.last.endswith(LINE)


def test_the_line_comes_back_once(chat: Chat) -> None:
    chat.say("what is OFS?")
    news(chat, ORBIT)
    chat.say("/brief")
    assert chat.bot.last.endswith(LINE)
    chat.store.release_brief(USER, "2026-10-25")
    chat.say("/brief")
    assert LINE not in chat.bot.last


def test_no_line_when_this_months_news_does_not_use_the_term(chat: Chat) -> None:
    chat.say("what is OFS?")
    news(chat, "RBI raises repo rate to 5.50%")
    news(chat, ORBIT, days_ago=45)
    news(chat, "Acme IPO has an OFS too", confirmed=False)
    chat.say("/brief")
    assert "Earlier you asked" not in chat.bot.last


def test_a_pasted_document_or_a_link_is_not_remembered_as_a_question(chat: Chat) -> None:
    chat.say("what is OFS? https://example.com/ipo")
    chat.say("Read this: " + "the OFS portion is large. " * 10)
    assert chat.store.recent_asked_terms(USER, "2000-01-01") == []


def test_the_line_quotes_a_title_that_holds_the_term(chat: Chat) -> None:
    chat.say("what is OFS?")
    seen = dt.datetime.fromisoformat(NOW) - dt.timedelta(days=3)
    url = "https://www.livemint.com/orbit-solar-ofs"
    db = WatcherStore.open(chat.services.watcher_db)
    db.add_articles([Article(url, "livemint.com", "livemint.com", "Orbit Solar IPO has an OFS", "",
                             seen, "q", seen)])  # fmt: skip
    db.assign([NewStory("s-orbit", "Orbit Solar opens its issue", seen)], {"s-orbit": [url]})
    db.put_decisions({"s-orbit": Confirmed(("livemint.com",), None)}, seen)
    db.close()
    chat.say("/brief")
    assert "It comes up in this month's news: Orbit Solar IPO has an OFS." in chat.bot.last
