"""The site's JSON API: per-user isolation, the same answer as Telegram with the guard on it,
rate limits, CORS, the length cap and a turn log with no text. Fake models, no network."""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from networth import config, sim
from networth.app import links
from networth.app.services import Services
from networth.app.settings import Settings
from networth.app.store import Status, Store
from networth.bot.commands import TOO_MANY
from networth.chat import Intent
from networth.web import api
from networth.web.routes import router, settings, sim_table
from tests.test_chat import GOOD_EXPLANATION, IPO_TEXT, FakeChatModels
from tests.test_links import SECRET
from tests.test_onboarding import TAPS_TO_CONFIRM, USER, Chat, handle_update, onboard
from tests.test_onboarding import tap_update as tap
from tests.test_onboarding import text_update as say
from tests.test_sim_web import TABLE
from tests.watcher_fakes import FAKE_ENV

OTHER_CHAT = 5151
OTHER_USER = f"tg:{OTHER_CHAT}"
PREVIEW = "https://networth-*-aankirzs-projects.vercel.app"
PROD = "https://networth-aankirz.vercel.app"
NOW = "2026-10-25T06:00:00+00:00"


@pytest.fixture
def cfg() -> config.Config:
    return config.load_config(env_path=Path("/nonexistent"), environ=FAKE_ENV)


class World:
    """User A (the Balanced one) and user B (Steady), both set up on Telegram, plus the API."""

    def __init__(self, tmp_path: Path, cfg: config.Config | None, models: FakeChatModels) -> None:
        self.models = models
        self.services = Services(tmp_path / "data", "https://nw.example", models, None, cfg)
        self.a = Chat(tmp_path, self.services)
        onboard(self.a)
        store = self.a.store
        for update in (say("/start", OTHER_CHAT),
                       *(tap(d.replace("plan:balanced", "plan:steady"), OTHER_CHAT)
                         for d in TAPS_TO_CONFIRM), tap("ob:confirm:ok", OTHER_CHAT)):  # fmt: skip
            handle_update(update, store, self.a.bot, NOW, self.services)
        app = FastAPI()
        app.include_router(router)
        data = tmp_path / "data"
        app.dependency_overrides[settings] = lambda: Settings(data, None, None, None, SECRET)
        app.dependency_overrides[api.api_services] = lambda: self.services
        app.dependency_overrides[sim_table] = lambda: TABLE
        self.client = TestClient(app)

    @property
    def store(self) -> Store:
        return self.a.store

    def token(self, user_id: str) -> str:
        profile = self.store.get_profile(user_id)
        assert profile is not None, "user is set up"
        return links.sign(profile.link_token, SECRET, dt.datetime.now(dt.UTC))

    def ask(self, user_id: str, text: str, **extra: object):
        return self.client.post(f"/api/u/{self.token(user_id)}/chat", json={"text": text, **extra})

    def turns(self) -> list[dict]:
        path = self.services.data_dir / api.TURN_LOG
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.fixture
def world(tmp_path: Path, cfg) -> World:
    return World(tmp_path, cfg, FakeChatModels(Intent.OTHER.value))


@pytest.fixture(autouse=True)
def origins(monkeypatch) -> None:
    monkeypatch.setenv(api.ORIGINS_ENV, f"{PROD},{PREVIEW}")
    monkeypatch.setattr(api, "DEMO_WINDOW", api.Window(api.DEMO_PER_IP_HOUR))


def test_the_dashboard_is_the_token_owners_own(world: World) -> None:
    a = world.client.get(f"/api/u/{world.token(USER)}/dashboard").json()
    b = world.client.get(f"/api/u/{world.token(OTHER_USER)}/dashboard").json()
    assert a["profile"]["plan"] == "Balanced. 20% safety, 70% core, 10% growth"
    assert b["profile"]["plan"].startswith("Steady.")
    assert "Steady" not in json.dumps(a) and "Balanced" not in json.dumps(b)
    assert a["sample"] is False and a["footer"] == "Research, not advice."
    assert (a["profile"]["money"], a["profile"]["day"]) == ("₹1,00,000", "1st")


def test_the_dashboard_range_is_the_users_own_simulation(world: World) -> None:
    plan = world.store.get_plan(USER)
    profile = world.store.get_profile(USER)
    assert plan is not None and profile is not None
    r = sim.plan_range(plan, profile, table=TABLE)
    card = world.client.get(f"/api/u/{world.token(USER)}/dashboard").json()["plan_range"]
    assert card["range"]["nominal"]["median"] == sim.rupees(r.nominal_median)
    assert card["range"]["invested"] == sim.rupees(r.invested)


@pytest.mark.parametrize("token", ["nope", "abc.123.def", "x" * 40])
def test_an_unknown_token_is_the_same_404_as_the_page(world: World, token: str) -> None:
    for response in (world.client.get(f"/api/u/{token}/dashboard"),
                     world.client.post(f"/api/u/{token}/chat", json={"text": "hi"})):  # fmt: skip
        assert response.status_code == 404
        assert response.json()["error"] == "not_found"
    assert world.models.picks == []


def test_a_chat_turn_reads_and_writes_only_the_askers_rows(tmp_path: Path, cfg) -> None:
    w = World(tmp_path, cfg, FakeChatModels(Intent.PLAN_RANGE.value))
    before = w.store.messages(OTHER_USER)
    turn = w.ask(USER, "what could my plan become").json()
    assert turn["card"]["type"] == "plan_range"
    assert turn["card"]["range"]["plan"].startswith("Balanced.")
    assert w.store.messages(OTHER_USER) == before
    mine = [m.text for m in w.store.messages(USER)]
    assert mine[-2:] == ["what could my plan become", turn["text"]]


def test_the_web_answer_is_the_telegram_answer(tmp_path: Path, cfg) -> None:
    w = World(
        tmp_path,
        cfg,
        FakeChatModels(Intent.EXPLAIN_THIS.value, writes=[GOOD_EXPLANATION, GOOD_EXPLANATION]),
    )
    w.a.say(IPO_TEXT)
    telegram = w.a.bot.last
    web = w.ask(USER, IPO_TEXT).json()
    assert web["text"] == telegram == f"{GOOD_EXPLANATION}\n\nResearch, not advice."
    assert web["message"]["footer"] == "Research, not advice."
    assert web["intent"] == "explain_this" and w.turns()[-1]["guard"] == "model"


def test_a_fixed_answer_matches_telegram_in_every_language(world: World) -> None:
    for text in ("hello there", "kya hai yeh batao", "नमस्ते क्या हाल है"):
        world.a.say(text)
        assert world.ask(USER, text).json()["text"] == world.a.bot.last


def test_the_guard_blocks_a_planted_number(tmp_path: Path, cfg) -> None:
    invented = GOOD_EXPLANATION.replace("60%", "70%")
    w = World(tmp_path, cfg, FakeChatModels(Intent.EXPLAIN_THIS.value, writes=[invented, invented]))
    turn = w.ask(USER, IPO_TEXT).json()
    assert "70%" not in turn["text"]
    assert turn["text"].startswith("I couldn't write a plain-words version")
    assert w.turns()[-1]["guard"] == "template"


def test_the_users_hourly_cap_is_the_telegram_one(tmp_path: Path, cfg) -> None:
    product = replace(cfg.product, chat_max_per_hour=2)
    w = World(tmp_path, replace(cfg, product=product), FakeChatModels(Intent.OTHER.value))
    assert [w.ask(USER, "hi").status_code for _ in range(2)] == [200, 200]
    over = w.ask(USER, "hi")
    assert over.status_code == 429
    assert over.json()["message"]["body"] == [{"kind": "text", "text": TOO_MANY["en"]}]
    assert w.ask(OTHER_USER, "hi").status_code == 200


def test_the_demo_has_a_stricter_per_visitor_cap(world: World) -> None:
    ask = world.client.post
    first = [ask("/api/demo/chat", json={"text": "hi"}, headers={api.VISITOR_HEADER: "1.1.1.1"})
             for _ in range(api.DEMO_PER_IP_HOUR + 1)]  # fmt: skip
    assert [r.status_code for r in first].count(200) == api.DEMO_PER_IP_HOUR
    assert first[-1].status_code == 429
    other = ask("/api/demo/chat", json={"text": "hi"}, headers={api.VISITOR_HEADER: "2.2.2.2"})
    assert other.status_code == 200


def test_the_demo_is_its_own_paused_user_and_never_touches_real_history(world: World) -> None:
    before = (world.store.messages(USER), world.store.messages(OTHER_USER))
    board = world.client.get("/api/demo/dashboard").json()
    assert board["sample"] is True and board["profile"]["money"] == "₹1,50,000"
    assert board["profile"]["plan"].startswith("Balanced.") and board["lang"] == "en"
    assert world.client.post("/api/demo/chat", json={"text": "hi"}).status_code == 200
    assert (world.store.messages(USER), world.store.messages(OTHER_USER)) == before
    assert world.store.messages(api.DEMO_USER) == []
    demo = world.store.get_profile(api.DEMO_USER)
    assert demo is not None and demo.status is Status.PAUSED and not demo.alerts_on


def test_a_demo_token_never_opens_the_user_routes(world: World) -> None:
    api.reset_demo(world.store)
    demo = world.store.get_profile(api.DEMO_USER)
    assert demo is not None
    world.store.new_link_token(api.DEMO_USER)
    demo = world.store.get_profile(api.DEMO_USER)
    assert demo is not None
    token = links.sign(demo.link_token, SECRET, dt.datetime.now(dt.UTC))
    assert world.client.get(f"/api/u/{token}/dashboard").status_code == 404


def test_reset_demo_is_idempotent_and_stops_its_watches(world: World) -> None:
    api.reset_demo(world.store)
    world.store.add_watch(api.DEMO_USER, "type", "rbi_hike", "RBI rate hike", NOW, 5)
    world.store.save_profile(replace(world.store.get_profile(api.DEMO_USER), lang="hi"))
    api.reset_demo(world.store)
    api.reset_demo(world.store)
    profile = world.store.get_profile(api.DEMO_USER)
    assert profile is not None and profile.lang == "en"
    assert world.store.active_watches(api.DEMO_USER) == []


@pytest.mark.parametrize("origin", [PROD, "https://networth-git-p8-aankirzs-projects.vercel.app"])
def test_our_origins_get_cors_headers(world: World, origin: str) -> None:
    response = world.client.get("/api/demo/dashboard", headers={"origin": origin})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    pre = world.client.options("/api/demo/chat", headers={
        "origin": origin, "access-control-request-method": "POST"})  # fmt: skip
    assert pre.status_code == 204 and pre.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://networth-aankirz.vercel.app",
        "https://networth-x-aankirzs-projects.vercel.app.evil.example",
    ],
)
def test_other_origins_are_refused(world: World, origin: str) -> None:
    for response in (
        world.client.get("/api/demo/dashboard", headers={"origin": origin}),
        world.client.post("/api/demo/chat", json={"text": "hi"}, headers={"origin": origin}),
        world.client.options("/api/demo/chat", headers={"origin": origin}),
    ):
        assert response.status_code == 403
        assert "access-control-allow-origin" not in response.headers


def test_a_bare_star_never_allows_every_origin(world: World, monkeypatch) -> None:
    monkeypatch.setenv(api.ORIGINS_ENV, "*")
    response = world.client.get("/api/demo/dashboard", headers={"origin": "https://a.example"})
    assert response.status_code == 403


def test_text_over_the_cap_is_refused_before_any_model_runs(world: World) -> None:
    response = world.ask(USER, "a" * (api.MAX_TEXT + 1))
    assert response.status_code == 413 and response.json()["error"] == "too_long"
    assert world.models.picks == [] and world.turns() == []
    assert world.ask(USER, "a" * api.MAX_TEXT).status_code == 200


def test_the_turn_log_never_holds_the_text_or_the_token(world: World) -> None:
    secret_words = "my pan is ABCDE1234F and my number is 98765"
    token = world.token(USER)
    world.client.post(f"/api/u/{token}/chat", json={"text": secret_words})
    raw = (world.services.data_dir / api.TURN_LOG).read_text()
    row = json.loads(raw)
    assert secret_words not in raw and "ABCDE1234F" not in raw and token not in raw
    assert USER not in raw and row["user_id"] == api.hashed(USER)
    assert set(row) == {"ts", "trace_id", "user_id", "channel", "intent", "guard", "cost_usd",
                        "outcome"}  # fmt: skip
    assert (row["intent"], row["guard"], row["channel"]) == ("other", "fixed", "web")


def test_access_logs_drop_the_token() -> None:
    args = ("1.2.3.4", "GET", "/api/u/abc.123.sig/dashboard")
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s"', args, None)
    api.RedactTokens().filter(record)
    assert record.getMessage() == '1.2.3.4 - "GET /api/u/…/dashboard"'


def test_a_language_choice_changes_only_this_turn(world: World) -> None:
    turn = world.ask(USER, "hello there", lang="hi").json()
    assert turn["message"]["footer"] == "रिसर्च, सलाह नहीं।"
    profile = world.store.get_profile(USER)
    assert profile is not None and profile.lang == "en"


def test_a_tip_marked_forwarded_goes_to_the_tip_check(tmp_path: Path, cfg) -> None:
    w = World(tmp_path, cfg, FakeChatModels(None))
    turn = w.ask(USER, "SBI to merge with HDFC tomorrow, pakka news", forwarded=True).json()
    assert turn["intent"] == "tip_check" and turn["card"] == {"type": "text"}


def test_a_holdings_question_carries_the_askers_own_holdings(tmp_path: Path, cfg) -> None:
    from networth.holdings.model import to_json
    from tests.test_holdings import fixture_holdings

    w = World(tmp_path, cfg, FakeChatModels(Intent.HOLDINGS.value))
    assert w.ask(OTHER_USER, "how are my holdings doing").json()["card"] == {"type": "text"}
    w.store.save_holdings(USER, to_json(fixture_holdings()))
    turn = w.ask(USER, "how are my holdings doing").json()
    assert turn["intent"] == "holdings" and turn["card"]["type"] == "holdings"
    assert turn["card"]["count"] == len(fixture_holdings().items)


def torn_call_log(path: Path) -> None:
    """The live 500: the VM stopped mid-append and left a line of NUL bytes in the call log."""
    good = json.dumps({"ts": "2026-10-25T10:00:00+00:00", "call": "write", "role": "writer",
                       "model": "m", "input_tokens": 1, "cached_tokens": 0, "output_tokens": 1,
                       "cost_usd": 0.001, "ok": True, "error": ""})  # fmt: skip
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{good}\n{chr(0) * 403}\n{chr(0) * 8}{good}\nnot json\n", encoding="utf-8")


def test_the_demo_chat_answers_what_happened_today_with_a_torn_call_log(world: World) -> None:
    torn_call_log(world.services.call_log)
    reply = world.client.post("/api/demo/chat", json={"text": "What happened today?"})
    assert reply.status_code == 200, reply.text
    assert reply.json()["text"]


def test_a_torn_call_log_keeps_every_whole_record(tmp_path: Path) -> None:
    from networth import net

    path = tmp_path / "llm_calls.jsonl"
    torn_call_log(path)
    assert [r.cost_usd for r in net.read_records(path)] == [0.001, 0.001]
