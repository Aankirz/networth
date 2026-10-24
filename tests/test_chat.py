"""Chat after setup, end to end through handle_update: intent routing, tip checks, explain-this,
/brief and its buttons. Fake Telegram, fake models, fake search; no network."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from networth import config
from networth.app.services import Services
from networth.app.store import Profile
from networth.chat import Intent, explain, jev, reply_lang
from networth.config import Query
from networth.llm import (
    AllowedCauses,
    ArticleBrief,
    Classification,
    NoAnswer,
    NotAnEvent,
    StoryForJudge,
)
from tests.test_onboarding import CHAT, NOW, Chat, onboard
from tests.watcher_fakes import FAKE_ENV

IPO_TEXT = (
    "Acme Foods Ltd IPO. Price band: ₹95 to ₹100 per share. Lot size: 150 shares. "
    "Issue size: ₹1,200 crore, of which ₹800 crore is a fresh issue and ₹400 crore an offer "
    "for sale. Subscription opens Oct 28 and closes Oct 30. Retail quota: 35%. "
    "Risk factors: the company depends on three suppliers for 60% of raw materials."
)
GOOD_EXPLANATION = (
    "This is an IPO, a company offering shares to the public for the first time. Each share "
    "costs ₹95 to ₹100, sold in lots of 150. Of the ₹1,200 crore raised, ₹800 crore goes to "
    "the company. The page says it relies on three suppliers for 60% of its raw materials."
)


class FakeChatModels:
    def __init__(self, intent: str | None = None, writes: Sequence[str] = (),
                 same: set[str] | None = None, image_text: str = IPO_TEXT) -> None:  # fmt: skip
        self.intent = intent
        self.writes = list(writes)
        self.same = same or set()
        self.image_text = image_text
        self.picks: list[str] = []
        self.tasks: list[str] = []
        self.images: list[bytes] = []

    def pick(self, question: str, choices: Mapping[str, str], text: str) -> str | None:
        self.picks.append(text)
        return self.intent

    def write(self, task: str, facts: str, feedback: str | None = None) -> str:
        self.tasks.append(task)
        if not self.writes:
            raise NoAnswer("no scripted draft")
        return self.writes.pop(0)

    def read_image(self, image: bytes, mime: str) -> str:
        self.images.append(image)
        return self.image_text

    def same_claim(self, claim: str, articles: Sequence[ArticleBrief]) -> set[str]:
        return {a.id for a in articles if a.id in self.same}

    def classify_story(self, story: StoryForJudge, allowed: AllowedCauses) -> Classification:
        return NotAnEvent("not an event type")


class FakeSearch:
    def __init__(self, results: list[dict]) -> None:
        self.results = results
        self.queries: list[Query] = []

    def search(self, query: Query, since: dt.datetime) -> list[dict]:
        self.queries.append(query)
        return self.results


def result(url: str, hours_ago: int = 1, title: str = "Bank X to merge with Bank Y") -> dict:
    when = dt.datetime.fromisoformat(NOW) - dt.timedelta(hours=hours_ago)
    return {"url": url, "publishedDate": when.isoformat(), "title": title, "text": title}


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


def talk(tmp_path: Path, cfg: config.Config | None, models: FakeChatModels | None = None,
         search: FakeSearch | None = None) -> Chat:  # fmt: skip
    services = Services(tmp_path / "data", "https://nw.example", models, search, cfg)
    chat = Chat(tmp_path, services)
    onboard(chat)
    return chat


ROUTED = {
    Intent.WHAT_HAPPENED_TODAY: "I haven't read today's news yet.",
    Intent.WHY: "Nothing in this month's news matched an event",
    Intent.TIP_CHECK: "I searched the news from the last 7 days and found no publisher",
    Intent.EXPLAIN_THIS: "I couldn't write a plain-words version",
    Intent.PLAN_QUESTION: "Here's what I have.",
    Intent.OTHER: "I can tell you what happened today",
}


@pytest.mark.parametrize("intent", list(Intent))
def test_each_intent_routes_to_its_own_answer(tmp_path: Path, cfg, intent: Intent) -> None:
    models = FakeChatModels(intent.value)
    chat = talk(tmp_path, replace(cfg, product=replace(cfg.product, use_jev_for_intent=False)),
                models, FakeSearch([]))  # fmt: skip
    chat.say("something")
    assert chat.bot.last.startswith(ROUTED[intent])


def test_plan_question_ends_by_pointing_at_plan_command(tmp_path: Path, cfg) -> None:
    chat = talk(tmp_path, cfg, FakeChatModels(Intent.PLAN_QUESTION.value))
    chat.say("what is my plan?")
    assert "Looks right?" not in chat.bot.last
    assert chat.bot.last.endswith("Type /plan to change it.")


def test_confident_jev_pick_wins_and_the_model_is_not_asked(tmp_path, cfg, monkeypatch) -> None:
    monkeypatch.setattr(jev, "choose", lambda *a, **k: jev.Pick("other", 0.9, 800))
    models = FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value)
    chat = talk(tmp_path, cfg, models)
    chat.say("hi there")
    assert chat.bot.last.startswith(ROUTED[Intent.OTHER])
    assert models.picks == []


def test_unsure_jev_pick_falls_back_to_the_model(tmp_path, cfg, monkeypatch) -> None:
    monkeypatch.setattr(jev, "choose", lambda *a, **k: jev.Pick("other", 0.4, 800))
    models = FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value)
    chat = talk(tmp_path, cfg, models)
    chat.say("hi there")
    assert chat.bot.last.startswith(ROUTED[Intent.WHAT_HAPPENED_TODAY])
    assert len(models.picks) == 1


def profile(lang: str) -> Profile:
    return Profile("tg:1", "telegram", 1, "done", "t", NOW, NOW, lang=lang)  # type: ignore[arg-type]


def test_reply_language_follows_how_the_user_writes() -> None:
    assert reply_lang("आज बाजार में क्या हुआ?", profile("en")) == "hi"
    assert reply_lang("aaj market mein kya hua", profile("en")) == "hinglish"
    assert reply_lang("what happened today", profile("hi")) == "hi"
    assert reply_lang("what happened today", profile("en")) == "en"


def tip_chat(tmp_path: Path, cfg, results: list[dict], same: set[str]) -> Chat:
    models = FakeChatModels(Intent.TIP_CHECK.value, same=same)
    return talk(tmp_path, cfg, models, FakeSearch(results))


def test_a_tip_reported_by_one_publisher_is_not_confirmed(tmp_path: Path, cfg) -> None:
    chat = tip_chat(tmp_path, cfg, [result("https://www.livemint.com/a")], {"a0"})
    chat.say("Bank X merging with Bank Y, buy now", forward_date=1)
    assert chat.bot.last.startswith("Only livemint.com reported this in the last 7 days.")
    assert "not confirmed" in chat.bot.last


def test_a_tip_reported_by_enough_publishers_in_the_window_is_reported(tmp_path, cfg) -> None:
    found = [result("https://www.livemint.com/a"), result("https://www.thehindu.com/b", 3),
             result("https://www.moneycontrol.com/c", 5)]  # fmt: skip
    chat = tip_chat(tmp_path, cfg, found, {"a0", "a1", "a2"})
    chat.say("Bank X merging with Bank Y", forward_date=1)
    assert chat.bot.last.startswith(
        "This is reported. livemint.com, moneycontrol.com, thehindu.com reported it."
    )


def test_articles_that_do_not_report_the_claim_do_not_count(tmp_path: Path, cfg) -> None:
    found = [result("https://www.livemint.com/a"), result("https://www.thehindu.com/b", 3),
             result("https://www.moneycontrol.com/c", 5)]  # fmt: skip
    chat = tip_chat(tmp_path, cfg, found, set())
    chat.say("Bank X merging with Bank Y", forward_date=1)
    assert "found no publisher reporting this" in chat.bot.last


def explain_chat(tmp_path: Path, cfg, writes: Sequence[str]) -> tuple[Chat, FakeChatModels]:
    models = FakeChatModels(Intent.EXPLAIN_THIS.value, writes=writes)
    return talk(tmp_path, cfg, models), models


def test_explain_this_sends_a_checked_plain_explanation(tmp_path: Path, cfg) -> None:
    chat, models = explain_chat(tmp_path, cfg, [GOOD_EXPLANATION])
    chat.say(IPO_TEXT)
    assert chat.bot.last == GOOD_EXPLANATION
    assert "never say what the reader should do" in models.tasks[0]


def test_explain_this_never_sends_an_invented_number_or_advice(tmp_path: Path, cfg) -> None:
    invented = GOOD_EXPLANATION.replace("60%", "70%")
    advice = GOOD_EXPLANATION + " You should apply."
    chat, _ = explain_chat(tmp_path, cfg, [invented, advice])
    chat.say(IPO_TEXT)
    assert chat.bot.last.startswith("I couldn't write a plain-words version")


def test_a_screenshot_is_read_then_explained(tmp_path: Path, cfg) -> None:
    chat, models = explain_chat(tmp_path, cfg, [GOOD_EXPLANATION])
    chat.send_photo("big")
    assert chat.bot.downloads == ["big"]
    assert models.images == [b"\xff\xd8 fake jpeg"]
    assert chat.bot.last == GOOD_EXPLANATION


def test_a_sticker_gets_told_what_can_be_read(tmp_path: Path, cfg) -> None:
    chat, _ = explain_chat(tmp_path, cfg, [])
    chat.send_photo(None)
    assert chat.bot.last == "I can read photos and text. Send a screenshot, or paste the text."


@pytest.mark.parametrize("url", ["http://127.0.0.1/admin", "http://169.254.169.254/latest",
                                 "file:///etc/passwd", "http://localhost:8080/"])  # fmt: skip
def test_links_to_private_addresses_are_never_fetched(url: str) -> None:
    with pytest.raises(explain.Blocked):
        explain.page_text(url)


def test_brief_is_sent_once_a_day_and_a_repeat_resends_it(tmp_path: Path, cfg) -> None:
    models = FakeChatModels()
    chat = talk(tmp_path, cfg, models)
    chat.say("/brief")
    first = chat.bot.sent[-1]
    chat.say("/brief")
    assert chat.bot.sent[-1][1] == first[1]
    assert first[1].startswith("Investing day, Oct 25. ₹1,00,000 ready.")
    assert len(models.tasks) == 2, "one draft and one rewrite, then the stored text is reused"


def test_brief_buttons_keep_or_change_the_plan(tmp_path: Path, cfg) -> None:
    chat = talk(tmp_path, cfg)
    chat.tap("br:ok")
    assert chat.bot.last == "Noted. Your plan stays as it is."
    chat.tap("br:plan")
    assert any(text.startswith("Your plan: Balanced.") for text in chat.bot.texts)


def test_a_stopped_user_gets_no_chat_answer(tmp_path: Path, cfg) -> None:
    chat = talk(tmp_path, cfg, FakeChatModels(Intent.OTHER.value))
    chat.say("/stop")
    sent = len(chat.bot.sent)
    chat.say("what happened today?")
    chat.send_photo("big")
    assert len(chat.bot.sent) == sent
    assert CHAT == chat.profile.chat_id
