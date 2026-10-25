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
from networth.chat.today import TYPE_QUESTION
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
from tests.test_web import web_db  # noqa: F401, F811 - the engine fixture
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
        self.event_type = "none"
        self.writes = list(writes)
        self.same = same or set()
        self.image_text = image_text
        self.picks: list[str] = []
        self.tasks: list[str] = []
        self.images: list[bytes] = []

    def pick(self, question: str, choices: Mapping[str, str], text: str) -> str | None:
        if question == TYPE_QUESTION:
            return self.event_type
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
    Intent.TIP_CHECK: "Not confirmed. I searched the news from the last 7 days",
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


def jev_on(cfg: config.Config) -> config.Config:
    return replace(cfg, product=replace(cfg.product, use_jev_for_intent=True))


def test_confident_jev_pick_wins_and_the_model_is_not_asked(tmp_path, cfg, monkeypatch) -> None:
    monkeypatch.setattr(jev, "choose", lambda *a, **k: jev.Pick("other", 0.9, 800))
    models = FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value)
    chat = talk(tmp_path, jev_on(cfg), models)
    chat.say("hi there")
    assert chat.bot.last.startswith(ROUTED[Intent.OTHER])
    assert models.picks == []


def test_unsure_jev_pick_falls_back_to_the_model(tmp_path, cfg, monkeypatch) -> None:
    monkeypatch.setattr(jev, "choose", lambda *a, **k: jev.Pick("other", 0.4, 800))
    models = FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value)
    chat = talk(tmp_path, jev_on(cfg), models)
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
    assert chat.bot.last.startswith(
        "Not confirmed. Only livemint.com reported this in the last 7 days."
    )
    assert chat.bot.last.endswith('also uses hype: "buy now". Real news rarely needs it.')


def test_a_tip_reported_by_enough_publishers_in_the_window_is_reported(tmp_path, cfg) -> None:
    found = [result("https://www.livemint.com/a"), result("https://www.thehindu.com/b", 3),
             result("https://www.moneycontrol.com/c", 5)]  # fmt: skip
    chat = tip_chat(tmp_path, cfg, found, {"a0", "a1", "a2"})
    chat.say("Bank X merging with Bank Y", forward_date=1)
    assert chat.bot.last.startswith(
        "Confirmed. livemint.com, moneycontrol.com, thehindu.com reported it."
    )


def test_articles_that_do_not_report_the_claim_do_not_count(tmp_path: Path, cfg) -> None:
    found = [result("https://www.livemint.com/a"), result("https://www.thehindu.com/b", 3),
             result("https://www.moneycontrol.com/c", 5)]  # fmt: skip
    chat = tip_chat(tmp_path, cfg, found, set())
    chat.say("Bank X merging with Bank Y", forward_date=1)
    assert chat.bot.last.startswith("Not confirmed.")
    assert "no publisher is reporting this" in chat.bot.last


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


def test_a_huge_page_is_read_only_up_to_the_byte_cap(monkeypatch) -> None:
    import httpx2

    served: list[int] = []

    def endless():
        while True:
            served.append(1)
            yield b"<p>IPO " + b"x" * 65_530 + b"</p>"

    monkeypatch.setattr(explain, "_public", lambda url: None)
    client = httpx2.Client(transport=httpx2.MockTransport(
        lambda request: httpx2.Response(200, content=endless())))  # fmt: skip
    text = explain.page_text("https://example.com/huge", client)
    assert text.startswith("IPO x")
    assert len(served) * 65_536 < explain.MAX_PAGE_BYTES + 2 * 65_536


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


def test_jev_is_not_asked_when_config_turns_it_off(tmp_path, cfg, monkeypatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(jev, "choose", lambda *a, **k: asked.append("jev"))
    chat = talk(tmp_path, cfg, FakeChatModels(Intent.OTHER.value))
    chat.say("hi there")
    assert asked == [] and chat.bot.last.startswith(ROUTED[Intent.OTHER])


def weekend_watcher(db: Path, checked: dt.datetime) -> None:
    from networth.watcher.store import Article, Confirmed, Cycle, NewStory
    from networth.watcher.store import Store as WatcherStore

    store = WatcherStore.open(db)
    url = "https://www.rbi.org.in/press/1"
    store.add_articles([Article(url, "rbi.org.in", "rbi.org.in", "RBI raises repo rate to 5.50%",
                                "", checked, "q", checked)])  # fmt: skip
    store.assign([NewStory("s1", "RBI raises repo rate to 5.50%", checked)], {"s1": [url]})
    store.put_decisions({"s1": Confirmed(("rbi.org.in",), "rbi.org.in")}, checked)
    store.add_cycle(Cycle(checked, checked, {}, 0.0, ()))
    store.close()


def test_today_falls_back_to_the_last_news_check_and_says_when(tmp_path: Path, cfg) -> None:
    chat = talk(tmp_path, cfg, FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value))
    checked = dt.datetime.fromisoformat(NOW) - dt.timedelta(hours=30)
    weekend_watcher(chat.services.watcher_db, checked)
    chat.say("what happened today?")
    assert chat.bot.last.startswith(
        "Confirmed in the 24 hours before my last news check (Oct 24, 05:30):"
    )
    assert "RBI raises repo rate to 5.50%. Reported by rbi.org.in." in chat.bot.last


def test_a_why_question_naming_an_event_type_answers_from_the_engine(
    tmp_path: Path,
    cfg,
    web_db: Path,  # noqa: F811
) -> None:
    from networth.engine import odds

    models = FakeChatModels(Intent.WHY.value)
    models.event_type = "rbi_hike"
    chat = talk(tmp_path, cfg, models)
    (chat.services.data_dir / "base_rates.sqlite").write_bytes(web_db.read_bytes())
    chat.say("Why do banks move after an RBI rate hike?")
    o = odds.odds("rbi_hike", "^NSEBANK", db=web_db)
    assert chat.bot.last.startswith("What history shows after RBI rate hikes:")
    assert f"in {o['n_hits']} of {o['n_episodes']} past RBI rate hikes" in chat.bot.last
    assert chat.bot.last.endswith("https://nw.example/why/rbi_hike/^NSEBANK")


def test_a_hyped_fake_tip_leads_with_the_verdict_and_quotes_the_hype(tmp_path, cfg) -> None:
    from networth.chat.tip import hype

    tip = "200 bps cut tomorrow, banks will double, buy HDFC Bank now, sure shot"
    assert hype(tip) == ["will double", "buy HDFC Bank now", "sure shot"]
    models = FakeChatModels(Intent.TIP_CHECK.value)
    chat = talk(tmp_path, cfg, models, FakeSearch([]))
    chat.say(tip, forward_date=1)
    assert chat.bot.last.startswith("Not confirmed.")
    assert '"will double", "buy HDFC Bank now", "sure shot"' in chat.bot.last
    assert models.tasks == [], "quoted hype goes out as code wrote it"


def test_past_the_hourly_cap_a_user_gets_a_polite_note_and_no_paid_call(tmp_path, cfg) -> None:
    from networth.bot.commands import TOO_MANY

    capped = replace(cfg, product=replace(cfg.product, chat_max_per_hour=2))
    models = FakeChatModels(Intent.OTHER.value)
    chat = talk(tmp_path, capped, models)
    for _ in range(3):
        chat.say("hi there")
    assert len(models.picks) == 2
    assert chat.bot.last == TOO_MANY


def test_the_hourly_cap_frees_up_after_an_hour(tmp_path) -> None:
    from networth.app.store import Store

    store, start = Store(tmp_path), dt.datetime(2026, 10, 26, 4, 0, tzinfo=dt.UTC)
    assert store.claim_answer("u", start, 1)
    assert not store.claim_answer("u", start + dt.timedelta(minutes=59), 1)
    assert store.claim_answer("u", start + dt.timedelta(minutes=61), 1)
