"""Watch this for me: parsing, refusals, /watch /watches /unwatch, and the sender that stays
quiet until the watcher confirms a matching story. Fake Telegram, a tmp watcher database."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from networth import config, guard, watch
from networth.app.services import Services
from networth.app.store import Status
from networth.bot.watches import run_watches
from networth.chat import Intent
from networth.engine.model import EventType, Region
from networth.llm import Classified
from networth.watch import Refusal, WatchRequest, parse_watch
from networth.watcher.store import Article, Confirmed, Insight, NewStory, Rejected
from networth.watcher.store import Store as WatcherStore
from tests.test_alerts import insight
from tests.test_chat import FakeChatModels
from tests.test_onboarding import NOW, Chat, onboard
from tests.watcher_fakes import FAKE_ENV

SET_AT = dt.datetime.fromisoformat(NOW)
LATER = SET_AT + dt.timedelta(hours=1)
RUN = SET_AT + dt.timedelta(hours=2)


@pytest.mark.parametrize("text", ["watch RBI rate changes", "tell me if RBI changes rates"])
def test_rbi_rate_changes_map_to_both_rbi_event_types(text: str) -> None:
    assert parse_watch(text) == WatchRequest("type", "rbi_hike,rbi_cut", "RBI rate changes")


def test_a_topic_maps_to_its_event_type_and_a_name_to_an_entity() -> None:
    assert parse_watch("watch bank stress news") == WatchRequest("type", "bank_stress",
                                                                 "bank stress")  # fmt: skip
    assert parse_watch("watch Paras Defence") == WatchRequest("entity", "Paras Defence",
                                                              "Paras Defence")  # fmt: skip
    assert parse_watch("keep an eye on Orbit Solar shares") == WatchRequest(
        "entity", "Orbit Solar", "Orbit Solar")  # fmt: skip


def test_a_price_target_or_a_trade_trigger_is_refused() -> None:
    refused = parse_watch("tell me when HDFC hits 1800 so I can buy")
    assert refused == Refusal("HDFC")
    assert refused.text("en") == (
        "I don't watch prices or tell anyone when to trade. I can tell you when a confirmed "
        "story about HDFC appears: watch HDFC."
    )
    assert refused.text("hinglish").startswith("Main prices")
    assert isinstance(parse_watch("alert me if Nifty crosses 25,000"), Refusal)
    assert isinstance(parse_watch("watch Reliance target price"), Refusal)


def test_nothing_to_watch_or_a_long_sentence_parses_to_none() -> None:
    assert parse_watch("watch") is None
    assert parse_watch("let me know when anything at all big happens anywhere") is None


@pytest.mark.parametrize("lang", ["en", "hi", "hinglish"])
def test_every_reply_passes_the_guards_word_rules(lang: str) -> None:
    tables = (watch.USAGE, watch.NO_WATCHES, watch.UNWATCH_USAGE, watch.WATCH_STOPPED)
    replies = [*(t[lang] for t in tables), watch.at_cap(5, lang), Refusal("HDFC").text(lang),
               Refusal(None).text(lang), watch.watching("it", lang),
               *(watch.watching(t.label, lang) for t in watch.TOPICS)]  # fmt: skip
    assert [r for r in replies if not guard.check(r, r).ok] == []


@pytest.mark.parametrize("lang", ["en", "hi", "hinglish"])
def test_a_reply_quoting_words_the_guard_rejects_falls_back_to_fixed_words(lang: str) -> None:
    fallback = watch.WATCHING[lang].format(label=watch.IT[lang])
    assert watch.watching("sure shot picks", lang) == fallback


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    chat = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", cfg=cfg))
    onboard(chat)
    return chat


def test_watch_then_watches_lists_it_with_a_stop_button(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    assert chat.bot.last.startswith("Watching RBI rate changes.")
    chat.say("/watches")
    assert chat.bot.last.startswith("Your watches:\n1. RBI rate changes")
    assert [b.label for row in chat.bot.sent[-1][2] for b in row] == ["Stop 1"]


def test_tapping_stop_stops_that_watch(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    chat.say("/watches")
    chat.tap(chat.bot.sent[-1][2][0][0].data)
    assert chat.bot.last == "Stopped watching RBI rate changes."
    assert chat.store.active_watches(chat.profile.user_id) == []


def test_unwatch_stops_the_nth_watch(chat: Chat) -> None:
    chat.say("/watch HDFC Bank")
    chat.say("/watch Paras Defence")
    chat.say("/unwatch 1")
    assert chat.bot.last == "Stopped watching HDFC Bank."
    assert [w.label for w in chat.store.active_watches(chat.profile.user_id)] == ["Paras Defence"]


def test_a_user_holds_at_most_five_watches(chat: Chat) -> None:
    for name in ("Alpha", "Beta", "Gamma", "Delta", "Epsilon"):
        chat.say(f"/watch {name}")
    chat.say("/watch Zeta")
    assert chat.bot.last.startswith("You already have 5 watches")
    assert len(chat.store.active_watches(chat.profile.user_id)) == 5


def test_asking_in_chat_sets_a_watch_or_refuses_a_trade_trigger(tmp_path: Path) -> None:
    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    chat = Chat(tmp_path, Services(tmp_path / "data", None, FakeChatModels(Intent.WATCH.value),
                                   cfg=cfg))  # fmt: skip
    onboard(chat)
    chat.say("tell me when HDFC hits 1800 so I can buy")
    assert chat.bot.last.startswith("I don't watch prices or tell anyone when to trade.")
    chat.say("tell me if RBI changes rates")
    assert chat.bot.last.startswith("Watching RBI rate changes.")


def story(chat: Chat, sid: str, title: str, *, type: str | None = None, first_seen=LATER,
          confirmed: bool = True, articles: tuple[str, ...] = ()) -> None:  # fmt: skip
    db = WatcherStore.open(chat.services.watcher_db)
    urls = {f"https://pub{i}.example/{sid}": t for i, t in enumerate((title, *articles))}
    db.add_articles([Article(u, f"pub{i}.example", f"pub{i}.example", t, "", first_seen, "q",
                             first_seen) for i, (u, t) in enumerate(urls.items())])  # fmt: skip
    db.assign([NewStory(sid, title, first_seen)], {sid: list(urls)})
    if type:
        db.set_classification(sid, Classified(EventType(type), "inflation", first_seen.date(),
                                              Region.IN, "judged"), first_seen)  # fmt: skip
    publishers = ("rbi.org.in",)
    verdict = Confirmed(publishers, "rbi.org.in") if confirmed else Rejected("one", publishers)
    db.put_decisions({sid: verdict}, first_seen)
    db.close()


def watches(chat: Chat, now: dt.datetime = RUN) -> int:
    return run_watches(chat.store, chat.bot, chat.services, now)


def test_a_watch_is_quiet_until_a_matching_story_is_confirmed(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    sent = len(chat.bot.sent)
    assert watches(chat) == 0, "no watcher data at all"
    story(chat, "s1", "RBI raises repo rate", type="rbi_hike", confirmed=False)
    story(chat, "s2", "Fed holds rates", type="fed_hike")
    assert watches(chat) == 0
    assert len(chat.bot.sent) == sent


def test_a_confirmed_match_is_sent_once_and_not_on_the_next_run(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    story(chat, "s1", "RBI raises repo rate to 5.50%", type="rbi_hike")
    assert watches(chat) == 1
    assert chat.bot.messages[-1].title == "Something you're watching: RBI rate changes."
    assert ("The watcher confirmed it: RBI raises repo rate to 5.50%.\nSource: rbi.org.in"
            in chat.bot.last)  # fmt: skip
    assert chat.bot.last.endswith("Research, not advice.")
    assert watches(chat) == 0


def test_a_story_from_before_the_watch_was_set_is_not_sent(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    story(chat, "s1", "RBI raises repo rate", type="rbi_hike", first_seen=SET_AT - dt.timedelta(1))
    assert watches(chat) == 0


def test_an_entity_watch_matches_an_article_title(chat: Chat) -> None:
    chat.say("/watch Paras Defence")
    story(chat, "s1", "Defence orders rise", articles=("Paras Defence wins ₹200 crore order",))
    story(chat, "s2", "Paras Defenceless is not a match")
    assert watches(chat) == 1
    assert "The watcher confirmed it: Defence orders rise." in chat.bot.last


def test_a_match_with_history_carries_the_engine_line_and_the_why_link(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    story(chat, "s1", "RBI raises repo rate", type="rbi_hike")
    db = WatcherStore.open(chat.services.watcher_db)
    i = insight(25)
    db.put_insights([Insight("s1", "news", i.asset, i.type, i.cause, LATER.date(), i.odds)], LATER)
    db.close()
    assert watches(chat) == 1
    assert "in 10 of 12 past RBI rate hikes" in chat.bot.last
    assert "Why these counts?: https://nw.example/why/rbi_hike/%5ENSEBANK" in chat.bot.last
    assert chat.bot.messages[-1].preview == "https://nw.example/why/rbi_hike/%5ENSEBANK"


def test_no_more_than_four_watch_messages_a_month(chat: Chat) -> None:
    names = ("Alpha", "Beta", "Gamma", "Delta", "Epsilon")
    for name in names:
        chat.say(f"/watch {name}")
    for n, name in enumerate(names):
        story(chat, f"s{n}", f"{name} posts results")
    assert watches(chat) == 4
    assert watches(chat, RUN + dt.timedelta(days=30)) == 1, "a new month frees the cap"


def test_pull_only_users_get_their_watch_but_paused_users_do_not(chat: Chat) -> None:
    chat.say("/watch RBI rate changes")
    story(chat, "s1", "RBI raises repo rate", type="rbi_hike")
    chat.store.save_profile(replace(chat.profile, status=Status.PAUSED))
    assert watches(chat) == 0
    chat.store.save_profile(replace(chat.profile, status=Status.ACTIVE, alerts_on=False))
    assert watches(chat) == 1


def test_watch_commands_work_by_email_without_buttons(tmp_path: Path) -> None:
    from tests.test_keiki_turn import Keiki, set_up

    cfg = config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)
    keiki = Keiki(tmp_path, Services(tmp_path / "data", cfg=cfg))
    set_up(keiki)
    keiki.say("/watch RBI rate changes")
    keiki.say("/watches")
    assert keiki.last == (
        "Your watches:\n1. RBI rate changes\n\nTo stop one, type /unwatch and its number."
    )
    keiki.say("/unwatch 1")
    assert keiki.last == "Stopped watching RBI rate changes."
