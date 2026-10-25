"""The site's / commands, @ mentions and track record: each command is the Telegram command's
own message for the same profile, the web never changes a plan, every mention text routes to
its documented intent, and the track record is the pages' own words. Fake models, no network."""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from networth.app import links
from networth.app.store import Step
from networth.bot.commands import PAGE_NOTE
from networth.bot.message import Link, Message, plain
from networth.chat import Intent, _by_phrase
from networth.holdings.model import to_json
from networth.web import api, routes
from tests.test_chat import FakeChatModels
from tests.test_holdings import fixture_holdings
from tests.test_links import SECRET
from tests.test_onboarding import NOW, USER, handle_update
from tests.test_onboarding import text_update as say
from tests.test_web import SUMMARY, web_db  # noqa: F401 - the rates fixture
from tests.test_web_api import World, cfg, origins  # noqa: F401 - fixtures
from tests.test_web_api_contract import TYPES

NEW_CHAT = 6161
NEW_USER = f"tg:{NEW_CHAT}"
COMMANDS = ("brief", "range", "plan", "holdings", "help")


@pytest.fixture
def world(tmp_path: Path, cfg) -> World:  # noqa: F811
    w = World(tmp_path, cfg, FakeChatModels(Intent.OTHER.value))
    handle_update(say("/start", NEW_CHAT), w.store, w.a.bot, NOW, w.services)
    return w


def run(w: World, user_id: str, name: str, **extra: object):
    return w.client.post(f"/api/u/{w.token(user_id)}/command", json={"name": name, **extra})


def telegram(w: World, chat_id: int, name: str, services=None) -> list[Message]:
    """What the bot sent for /name, read from the fake bot, on the web route's clock: the brief
    greets by the hour."""
    before = len(w.a.bot.messages)
    now = dt.datetime.now(dt.UTC).isoformat()
    handle_update(say(f"/{name}", chat_id), w.store, w.a.bot, now, services or w.services)
    return w.a.bot.messages[before:]


def without_page(m: Message) -> Message:
    return replace(m, body=tuple(b for b in m.body
                                 if not isinstance(b, Link) and b != PAGE_NOTE["en"]))  # fmt: skip


@pytest.mark.parametrize("name", [n for n in COMMANDS if n != "plan"])
def test_a_command_is_the_telegram_message(world: World, name: str) -> None:
    web = run(world, USER, name).json()
    sent = telegram(world, 4242, name)
    assert web["command"] == name and len(sent) == 1
    assert web["text"] == plain(sent[0])


def test_holdings_is_the_telegram_report_with_its_card(world: World) -> None:
    world.store.save_holdings(USER, to_json(fixture_holdings()))
    web = run(world, USER, "holdings").json()
    assert web["text"] == plain(telegram(world, 4242, "holdings")[0])
    assert web["card"]["type"] == "holdings"


@pytest.mark.parametrize("name", COMMANDS)
def test_before_setup_a_command_says_what_telegram_says(world: World, name: str) -> None:
    web = run(world, NEW_USER, name).json()
    sent = telegram(world, NEW_CHAT, name)
    assert web["text"] == plain(sent[0])
    assert web["card"] == {"type": "text"}


def test_plan_is_telegrams_first_message_without_the_page_link(world: World) -> None:
    web = run(world, USER, "plan").json()
    sent = telegram(world, 4242, "plan", replace(world.services, link_secret=SECRET))
    assert any(isinstance(b, Link) for b in sent[0].body), "Telegram sent its page link"
    assert web["text"] == plain(without_page(sent[0]))
    assert web["text"].startswith("Your plan\n\nBalanced.")


def test_plan_on_the_web_never_changes_the_plan_or_the_step(world: World) -> None:
    before = (world.store.get_profile(USER), world.store.get_plan(USER))
    for _ in range(2):
        assert run(world, USER, "plan").status_code == 200
    after = (world.store.get_profile(USER), world.store.get_plan(USER))
    assert after == before and after[0].step is Step.DONE


def test_brief_never_claims_the_days_brief(world: World) -> None:
    run(world, USER, "brief")
    assert world.store.last_brief(USER) is None
    card = run(world, USER, "brief").json()["card"]
    board = world.client.get(f"/api/u/{world.token(USER)}/dashboard").json()
    assert card == board["history"]


def test_a_users_command_is_logged_like_telegrams(world: World) -> None:
    web = run(world, USER, "range").json()
    assert [m.text for m in world.store.messages(USER)][-2:] == ["/range", web["text"]]


def test_a_language_choice_changes_only_this_command(world: World) -> None:
    web = run(world, USER, "help", lang="hi").json()
    assert web["message"]["footer"] == "रिसर्च, सलाह नहीं।"
    profile = world.store.get_profile(USER)
    assert profile is not None and profile.lang == "en"


def test_an_unknown_command_name_is_refused(world: World) -> None:
    assert run(world, USER, "stop").status_code == 422
    assert world.client.post("/api/demo/command", json={"name": "link_broker"}).status_code == 422


@pytest.mark.parametrize("token", ["nope", "abc.123.def"])
def test_an_unknown_token_is_the_same_404(world: World, token: str) -> None:
    response = world.client.post(f"/api/u/{token}/command", json={"name": "help"})
    assert response.status_code == 404 and response.json()["error"] == "not_found"


def test_a_demo_token_never_opens_the_user_command_route(world: World) -> None:
    api.reset_demo(world.store)
    world.store.new_link_token(api.DEMO_USER)
    demo = world.store.get_profile(api.DEMO_USER)
    assert demo is not None
    token = links.sign(demo.link_token, SECRET, dt.datetime.now(dt.UTC))
    assert world.client.post(f"/api/u/{token}/command", json={"name": "help"}).status_code == 404


def test_the_demo_command_shares_the_demo_cap_and_logs_no_messages(world: World) -> None:
    head = {api.VISITOR_HEADER: "1.1.1.1"}
    codes = [world.client.post("/api/demo/command", json={"name": "help"}, headers=head)
             .status_code for _ in range(api.DEMO_PER_IP_HOUR + 1)]  # fmt: skip
    assert codes.count(200) == api.DEMO_PER_IP_HOUR and codes[-1] == 429
    assert world.store.messages(api.DEMO_USER) == []


def test_a_users_commands_claim_no_hourly_answer(tmp_path: Path, cfg) -> None:  # noqa: F811
    product = replace(cfg.product, chat_max_per_hour=1)
    w = World(tmp_path, replace(cfg, product=product), FakeChatModels(Intent.OTHER.value))
    assert [run(w, USER, "help").status_code for _ in range(3)] == [200, 200, 200]
    assert w.ask(USER, "hi").status_code == 200


def test_the_turn_log_has_the_command_never_the_text_or_token(world: World) -> None:
    token = world.token(USER)
    web = world.client.post(f"/api/u/{token}/command", json={"name": "plan"}).json()
    raw = (world.services.data_dir / api.TURN_LOG).read_text()
    row = json.loads(raw)
    assert token not in raw and USER not in raw and web["text"] not in raw
    assert "Balanced" not in raw
    assert set(row) == {"ts", "trace_id", "user_id", "channel", "intent", "guard", "cost_usd",
                        "outcome"}  # fmt: skip
    assert (row["intent"], row["channel"], row["outcome"]) == ("/plan", "web", "completed")


def test_a_failing_command_says_try_again(world: World, monkeypatch) -> None:
    def boom(f):
        raise RuntimeError("boom")

    monkeypatch.setitem(api.COMMANDS, "help", boom)  # type: ignore[arg-type]
    response = run(world, USER, "help")
    assert response.status_code == 500 and response.json()["error"] == "failed"


# @ mentions -----------------------------------------------------------------------------------

NEWS = [{"title": "RBI raises repo rate to 5.50%", "day": "on 3 October", "publishers": []}]
HISTORY = [{"type": "rbi_hike", "asset": "^NSEBANK", "asset_name": "Indian banks (Nifty Bank)"}]
HOLDINGS = {"rows": [{"name": "Parag Parikh Flexi Cap"}, {"name": "Nifty 50 ETF"}]}
DOCUMENTED = {
    "news": ("news", "What happened today?", Intent.WHAT_HAPPENED_TODAY),
    "story:0": ("RBI raises repo rate to 5.50%",
                "Why does this story matter: RBI raises repo rate to 5.50%?", Intent.WHY),
    "history:rbi_hike:^NSEBANK": (
        "RBI rate hike, Indian banks (Nifty Bank)",
        "Why? What history counted for RBI rate hike and Indian banks (Nifty Bank)", Intent.WHY),
    "plan": ("plan", "What is my plan?", Intent.PLAN_QUESTION),
    "range": ("range", "What could my plan become?", Intent.PLAN_RANGE),
    "holdings": ("holdings", "How are my holdings doing?", Intent.HOLDINGS),
    "holding:0": ("Parag Parikh Flexi Cap",
                  "How are my holdings doing? About Parag Parikh Flexi Cap", Intent.HOLDINGS),
    "holding:1": ("Nifty 50 ETF", "How are my holdings doing? About Nifty 50 ETF",
                  Intent.HOLDINGS),
}  # fmt: skip


def test_each_mention_is_the_documented_text_and_routes_to_its_intent() -> None:
    got = api.mentions(NEWS, HISTORY, HOLDINGS)
    assert [m["id"] for m in got] == list(DOCUMENTED)
    for m in got:
        label, text, intent = DOCUMENTED[m["id"]]
        assert (m["label"], m["text"]) == (label, text)
        assert _by_phrase(m["text"], False) is intent, m["id"]
        assert set(m) == TYPES["Mention"]


def test_without_holdings_the_holdings_mention_stays() -> None:
    kinds = [m["kind"] for m in api.mentions([], [], None)]
    assert kinds == ["news", "plan", "range", "holdings"]


def test_the_dashboard_mentions_are_its_own_pieces(world: World) -> None:
    world.store.save_holdings(USER, to_json(fixture_holdings()))
    board = world.client.get(f"/api/u/{world.token(USER)}/dashboard").json()
    expected = api.mentions(board["news"]["items"], board["history"]["rows"], board["holdings"])
    assert board["mentions"] == expected
    ids = [m["id"] for m in board["mentions"]]
    assert len(ids) == len(set(ids)) and "holding:0" in ids


# Track record ---------------------------------------------------------------------------------


def text(page: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


@pytest.fixture
def pages(web_db: Path, tmp_path: Path, monkeypatch) -> TestClient:  # noqa: F811
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps(SUMMARY))
    monkeypatch.setattr(routes, "EVAL_SUMMARY", summary)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[routes.rates_db] = lambda: web_db
    return TestClient(app)


def test_the_track_record_is_what_the_pages_show(pages: TestClient) -> None:
    record = pages.get("/api/track-record").json()
    assert set(record) == TYPES["TrackRecord"]
    page = pages.get("/track-record").text
    section = page[page.index('id="tested"') : page.index("</section>", page.index('id="tested"'))]
    shown = [text(p) for p in re.findall(r'<p class="normal">(.*?)</p>', section, re.S)]
    assert record["tested"] == shown and len(shown) == 2
    stats = text(pages.get("/stats").text)
    assert len(record["stats"]) == len(routes.STATS_QUERIES)
    for stat in record["stats"]:
        assert set(stat) == TYPES["Stat"]
        assert f"{stat['label']} {stat['value']}" in stats


def test_without_a_database_or_summary_the_track_record_is_empty(tmp_path: Path,
                                                                 monkeypatch) -> None:  # fmt: skip
    monkeypatch.setattr(routes, "EVAL_SUMMARY", tmp_path / "missing.json")
    assert api.track_record(tmp_path / "none.sqlite") == {"tested": None, "stats": []}
