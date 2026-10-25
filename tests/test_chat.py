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
from networth.bot.message import FOOTER
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
from tests.keiki_fakes import MAILTRACK_FOOTER, OPT_OUT
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
    Intent.TIP_CHECK: "Not confirmed. I searched the last 7 days of news",
    Intent.EXPLAIN_THIS: "I couldn't write a plain-words version",
    Intent.PLAN_QUESTION: "I can't tell you whether a plan is right for you.",
    Intent.PLAN_RANGE: "This is your own plan:",
    Intent.WATCH: "Watching something.",
    Intent.OTHER: "I can tell you what happened today",
}


@pytest.mark.parametrize("intent", list(Intent))
def test_each_intent_routes_to_its_own_answer(tmp_path: Path, cfg, sim_table,
                                              intent: Intent) -> None:  # fmt: skip
    models = FakeChatModels(intent.value)
    chat = talk(tmp_path, replace(cfg, product=replace(cfg.product, use_jev_for_intent=False)),
                models, FakeSearch([]))  # fmt: skip
    chat.say("something")
    assert chat.bot.last.startswith(ROUTED[intent])


def test_a_plan_question_never_restates_the_split_or_invites_a_change(tmp_path, cfg) -> None:
    """Finding 3: the judge read the saved split and "Type /plan" as an allocation and a nudge."""
    chat = talk(tmp_path, cfg, FakeChatModels(Intent.PLAN_QUESTION.value))
    chat.say("what is my plan?")
    assert "Looks right?" not in chat.bot.last
    assert "%" not in chat.bot.last and "/plan" not in chat.bot.last
    assert chat.bot.last.endswith("Research, not advice.")


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
    assert chat.bot.last.endswith(
        'also uses hype: "buy now". Real news rarely needs it.\n\nResearch, not advice.'
    )


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
    assert chat.bot.last == f"{GOOD_EXPLANATION}\n\nResearch, not advice."
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
    assert chat.bot.last == f"{GOOD_EXPLANATION}\n\nResearch, not advice."


def test_a_sticker_gets_told_what_can_be_read(tmp_path: Path, cfg) -> None:
    chat, _ = explain_chat(tmp_path, cfg, [])
    chat.send_photo(None)
    assert chat.bot.last == "I can read photos and text. A screenshot or some pasted text works."


def test_a_mail_footer_link_is_never_fetched_and_the_text_is_explained(
    tmp_path, cfg, monkeypatch
) -> None:
    fetched: list[str] = []
    monkeypatch.setattr(explain, "page_text", lambda url, client=None: fetched.append(url) or "")
    chat, _ = explain_chat(tmp_path, cfg, [GOOD_EXPLANATION])
    chat.say(IPO_TEXT + MAILTRACK_FOOTER)
    assert fetched == []
    assert chat.bot.last == f"{GOOD_EXPLANATION}\n\nResearch, not advice."


@pytest.mark.parametrize("url", [
    OPT_OUT, "https://news.example.com/unsubscribe?id=1", "https://example.com/email/click/9",
    "https://example.com/r?url=https%3A%2F%2Fexample.org", "https://track.example.com/a.png",
    "https://us1.list-manage.com/profile?u=1",
])  # fmt: skip
def test_unsubscribe_tracking_and_redirect_links_are_never_fetched(url: str) -> None:
    assert not explain.fetchable(url)
    with pytest.raises(explain.Blocked):
        explain.page_text(url)


def test_a_link_the_user_pasted_is_still_the_one_explained() -> None:
    article = "https://economictimes.indiatimes.com/markets/ipos/orbit-solar/articleshow/1.cms"
    assert explain.user_link(f"what is this? {article}{MAILTRACK_FOOTER}") == article
    assert explain.user_link(f"<{article}>") == article


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


def written(monkeypatch) -> list[str]:
    """Each time a brief is composed afresh, its user id; a resend from storage adds nothing."""
    from networth.bot import briefs

    calls: list[str] = []
    real = briefs.compose_reply

    def counted(profile, *args):
        calls.append(profile.user_id)
        return real(profile, *args)

    monkeypatch.setattr(briefs, "compose_reply", counted)
    return calls


def test_brief_is_sent_once_a_day_and_a_repeat_resends_it(tmp_path: Path, cfg,
                                                          monkeypatch) -> None:  # fmt: skip
    models = FakeChatModels()
    chat = talk(tmp_path, cfg, models)
    composed = written(monkeypatch)
    chat.say("/brief")
    first = chat.bot.sent[-1]
    chat.say("/brief")
    assert chat.bot.sent[-1][1] == first[1]
    assert chat.bot.messages[-1] == chat.bot.messages[-2], "the stored message, title and all"
    assert first[1].startswith("Morning. Here's your brief for this month.")
    assert len(composed) == 1, "the second /brief is the stored message"
    assert models.tasks == [], "code writes the brief; no model rewords it"


def test_a_repeat_brief_is_written_afresh_after_a_newer_news_check(
    tmp_path: Path, cfg, monkeypatch
) -> None:
    chat = talk(tmp_path, cfg, FakeChatModels())
    composed = written(monkeypatch)
    chat.say("/brief")
    chat.say("/brief")
    assert len(composed) == 1, "no news check since, so the stored brief is resent"
    weekend_watcher(chat.services.watcher_db, dt.datetime.now(dt.UTC) + dt.timedelta(minutes=1))
    chat.say("/brief")
    assert len(composed) == 2, "a newer news check, so the brief is written again"


def test_brief_buttons_keep_or_change_the_plan(tmp_path: Path, cfg) -> None:
    chat = talk(tmp_path, cfg)
    chat.tap("br:ok")
    assert chat.bot.last == "Got it. Your plan stays just as it is."
    chat.tap("br:plan")
    assert any(text.startswith("Your plan\n\nBalanced.") for text in chat.bot.texts)


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
    off = replace(cfg, product=replace(cfg.product, use_jev_for_intent=False))
    chat = talk(tmp_path, off, FakeChatModels(Intent.OTHER.value))
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
    assert chat.bot.last.startswith("Here's what history counted after news like this:")
    assert f"in {o['n_hits']} of {o['n_episodes']} past RBI rate hikes" in chat.bot.last
    assert "Every past case: https://nw.example/why/rbi_hike/^NSEBANK" in chat.bot.last
    assert chat.bot.messages[-1].preview == "https://nw.example/why/rbi_hike/^NSEBANK"


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
    assert chat.bot.last == TOO_MANY["en"]


def test_the_hourly_cap_frees_up_after_an_hour(tmp_path) -> None:
    from networth.app.store import Store

    store, start = Store(tmp_path), dt.datetime(2026, 10, 26, 4, 0, tzinfo=dt.UTC)
    assert store.claim_answer("u", start, 1)
    assert not store.claim_answer("u", start + dt.timedelta(minutes=59), 1)
    assert store.claim_answer("u", start + dt.timedelta(minutes=61), 1)


# --- phase 3D: fixes from the phase 5 evals, Jev back on, /range ---------------------------


def test_a_hinglish_plan_question_gets_hinglish_words_and_no_translation(tmp_path, cfg) -> None:
    models = FakeChatModels(Intent.PLAN_QUESTION.value)
    chat = talk(tmp_path, cfg, models)
    chat.say("Mera plan 70% index hai, theek hai ya change karu?")
    assert chat.bot.last.startswith("Main nahin bata sakta")
    assert chat.bot.last.endswith("Research hai, advice nahin.")
    assert models.tasks == [], "code wrote the Hinglish, so no model translates it"


def test_a_reworded_reply_tells_the_writer_to_use_statements(tmp_path, cfg) -> None:
    models = FakeChatModels(Intent.TIP_CHECK.value)
    chat = talk(tmp_path, cfg, models, FakeSearch([]))
    chat.say("IPO mein paisa lagau kya? GMP accha chal raha hai", forward_date=1)
    assert models.tasks, "a non-hyped Hinglish tip verdict is reworded"
    assert "never as a command, polite forms included" in " ".join(models.tasks[0].split())


def test_a_hinglish_hyped_tip_skips_the_writer_it_could_never_pass(tmp_path, cfg) -> None:
    models = FakeChatModels(Intent.TIP_CHECK.value)
    chat = talk(tmp_path, cfg, models, FakeSearch([]))
    chat.say("Bhai Tata Steel 900 tak jayega is mahine, pakka khabar hai, abhi kharid lo.",
             forward_date=1)  # fmt: skip
    assert chat.bot.last.startswith("Confirm nahin hua.")
    assert models.tasks == [], "the template already fails the guard, so no model is asked"


PLAN_LEADS = {
    "Is 70% equity too much for me?": "I can't tell you whether a plan is right for you. "
    "The plan stays your choice.",
    "मेरा प्लान 70% इंडेक्स है, क्या ये ठीक है?": "मैं नहीं बता सकता कि कोई प्लान आपके लिए सही है "
    "या नहीं। प्लान हमेशा आपकी अपनी पसंद है।",
    "Mera plan 70% index hai, theek hai ya change karu?": "Main nahin bata sakta ki koi plan "
    "aapke liye sahi hai ya nahin. Plan hamesha aapki apni pasand hai.",
}


@pytest.mark.parametrize("question", PLAN_LEADS)
def test_a_plan_question_leads_with_the_fixed_line(tmp_path, cfg, question: str) -> None:
    from networth import guard

    lead = PLAN_LEADS[question]
    assert guard.check(lead, "").ok
    chat = talk(tmp_path, cfg, FakeChatModels(Intent.PLAN_QUESTION.value))
    chat.say(question)
    assert chat.bot.last.startswith(lead)
    assert "Here's what I have." not in chat.bot.last, "one opening line, not two"


def test_a_plan_question_about_this_months_event_adds_its_history_line(
    tmp_path: Path,
    cfg,
    monkeypatch,
    web_db: Path,  # noqa: F811
) -> None:
    from networth import brief

    month = [brief.Event("rbi_hike", dt.date(2026, 10, 9), "RBI raises repo rate", ())]
    monkeypatch.setattr(brief, "month_events", lambda db, today: month)
    models = FakeChatModels(Intent.PLAN_QUESTION.value)
    models.event_type = "rbi_hike"
    chat = talk(tmp_path, cfg, models)
    (chat.services.data_dir / "base_rates.sqlite").write_bytes(web_db.read_bytes())
    chat.say("RBI hiked, what do I do with my SIP?")
    assert chat.bot.last.startswith(PLAN_LEADS["Is 70% equity too much for me?"])
    assert "past RBI rate hikes" in chat.bot.last
    monkeypatch.setattr(brief, "month_events", lambda db, today: [])
    chat.say("RBI hiked, what do I do with my SIP?")
    assert "past RBI rate hikes" not in chat.bot.last, "no history line without the event"


def test_jev_is_on_in_the_shipped_config(cfg) -> None:
    assert cfg.product.use_jev_for_intent


def test_jev_down_falls_back_to_the_model(tmp_path, cfg, monkeypatch) -> None:
    monkeypatch.setattr(jev, "choose", lambda *a, **k: None)
    models = FakeChatModels(Intent.WHAT_HAPPENED_TODAY.value)
    chat = talk(tmp_path, cfg, models)
    chat.say("hi there")
    assert chat.bot.last.startswith(ROUTED[Intent.WHAT_HAPPENED_TODAY])
    assert len(models.picks) == 1


@pytest.fixture
def sim_table(monkeypatch):
    from networth import sim
    from tests.test_sim import varying

    monkeypatch.setattr(sim, "load_table", varying)


RANGE_STARTS = {"en": "This is your own plan:", "hi": "यह आपका अपना प्लान है:",
                "hinglish": "Yeh aapka apna plan hai:"}  # fmt: skip


def set_lang(chat: Chat, lang: str) -> None:
    chat.store.save_profile(replace(chat.profile, lang=lang))


@pytest.mark.parametrize("lang", list(RANGE_STARTS))
def test_range_command_sends_the_plan_range_in_the_users_language(
    tmp_path, cfg, sim_table, lang: str
) -> None:
    from networth import guard, sim

    models = FakeChatModels()
    chat = talk(tmp_path, cfg, models)
    set_lang(chat, lang)
    chat.say("/range")
    r = sim.plan_range(chat.plan, chat.profile)
    assert chat.bot.last.startswith(RANGE_STARTS[lang])
    body = sim.plan_range_message(chat.profile.user_id, chat.store)
    assert chat.bot.last == f"{body}\n\n{FOOTER[lang]}"
    assert guard.check(chat.bot.last, repr(r)).ok
    assert models.tasks == [], "the range is fixed sentences, no model writes it"


RANGE_QUESTIONS = {"en": "What could my plan become?", "hi": "मेरा प्लान कितना गिर सकता है?",
                   "hinglish": "Mera plan kitna gir sakta hai, kya hoga?"}  # fmt: skip


@pytest.mark.parametrize("lang", list(RANGE_QUESTIONS))
def test_a_plan_range_question_answers_with_the_range(tmp_path, cfg, sim_table, lang) -> None:
    models = FakeChatModels(Intent.PLAN_RANGE.value)
    chat = talk(tmp_path, cfg, models)
    chat.say(RANGE_QUESTIONS[lang])
    assert chat.bot.last.startswith(RANGE_STARTS[lang])
    assert models.tasks == []


def test_a_plan_range_question_routes_by_phrase_without_models(tmp_path, cfg, sim_table) -> None:
    chat = talk(tmp_path, cfg, None)
    chat.say("how bad can a fall get?")
    assert chat.bot.last.startswith(RANGE_STARTS["en"])


def test_a_dollar_plan_gets_the_polite_range_line(tmp_path, cfg, sim_table) -> None:
    from networth.chat.today import NO_RANGE

    chat = talk(tmp_path, cfg, FakeChatModels(Intent.PLAN_RANGE.value))
    chat.store.save_profile(replace(chat.profile, currency="USD", monthly_amount=1000))
    chat.say("/range")
    assert chat.bot.last == f"{NO_RANGE['en']}\n\n{FOOTER['en']}"
    chat.say("how bad can a fall get?")
    assert chat.bot.last == f"{NO_RANGE['en']}\n\n{FOOTER['en']}"


@pytest.mark.parametrize("lang", list(RANGE_STARTS))
def test_the_polite_range_lines_pass_the_guard(lang: str) -> None:
    from networth import guard
    from networth.chat.today import NO_RANGE, RANGE_NOT_READY

    assert guard.check(NO_RANGE[lang], "").ok
    assert guard.check(RANGE_NOT_READY[lang], "").ok


def test_a_missing_range_table_says_the_range_is_not_ready(tmp_path, cfg, monkeypatch) -> None:
    from networth import sim
    from networth.chat.today import RANGE_NOT_READY
    from networth.sim.data import MissingSeries

    def missing() -> None:
        raise MissingSeries("no table")

    monkeypatch.setattr(sim, "load_table", missing)
    chat = talk(tmp_path, cfg, FakeChatModels())
    chat.say("/range")
    assert chat.bot.last == f"{RANGE_NOT_READY['en']}\n\n{FOOTER['en']}"


def test_a_reworded_reply_with_a_failing_template_still_asks_the_writer(tmp_path, cfg) -> None:
    from networth.chat.answer import Answer, deliver

    services = Services(tmp_path / "data", None, FakeChatModels(writes=["Banks rose."]), None, cfg)
    answer = Answer("buy banks now", "Banks rose.", "Say what happened.")
    assert deliver(answer, "en", services).text == "Banks rose.\n\nResearch, not advice."


def test_the_brief_has_a_my_range_button_next_to_my_page(tmp_path, cfg, sim_table) -> None:
    services = Services(tmp_path / "data", "https://nw.example", None, None, cfg,
                        link_secret="s" * 32)  # fmt: skip
    chat = Chat(tmp_path, services)
    onboard(chat)
    chat.say("/brief")
    rows = [[b.label for b in row] for row in chat.bot.sent[-1][2]]
    assert ["My page", "My range"] in rows
    chat.tap("br:range")
    assert chat.bot.last.startswith(RANGE_STARTS["en"])


def switch_lang(chat: Chat, lang: str) -> None:
    for data in ("ob:confirm:fix", "ob:confirm:lang", f"ob:lang:{lang}", "ob:confirm:ok"):
        chat.tap(data)


def test_a_language_change_reaches_the_same_day_brief(tmp_path, cfg, monkeypatch) -> None:
    from networth.bot import briefs

    chat = talk(tmp_path, cfg, FakeChatModels())
    composed = written(monkeypatch)
    chat.say("/start")
    switch_lang(chat, "hinglish")
    chat.say("/brief")
    assert chat.bot.last.startswith("Good morning. Yeh raha is mahine ka aapka brief.")
    chat.say("/start")
    switch_lang(chat, "en")
    chat.say("/brief")
    assert chat.bot.last.startswith("Morning.") and len(composed) == 2
    chat.say("/brief")
    assert len(composed) == 2, "unchanged since, so the stored brief is resent"
    sent = len(chat.bot.sent)
    local = briefs.local_now(chat.profile, dt.datetime.fromisoformat(NOW))
    assert not briefs.send_brief(chat.store, chat.bot, chat.profile, chat.services, local,
                                 proactive=True)  # fmt: skip
    assert len(chat.bot.sent) == sent, "the scheduled run still sends one brief a day"
