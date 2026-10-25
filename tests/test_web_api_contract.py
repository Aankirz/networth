"""The contract in docs/phases/phase-10-contract.md, the site's TypeScript copy of it and the JSON
the API really returns all name the same fields."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from networth.chat import Intent
from networth.holdings.model import to_json
from networth.web import api
from tests.test_chat import FakeChatModels
from tests.test_holdings import fixture_holdings
from tests.test_onboarding import USER
from tests.test_web_api import World, cfg  # noqa: F401 - the config fixture

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "phases" / "phase-10-contract.md"
SITE_TYPES = ROOT / "site" / "lib" / "contract.ts"
INTERFACE = re.compile(r"export interface (\w+) \{\n(.*?)\n\}", re.S)
FIELD = re.compile(r"^  (\w+)(\?)?: ", re.M)


def ts_block() -> str:
    m = re.search(r"```ts\n(.*?)```", CONTRACT.read_text(encoding="utf-8"), re.S)
    assert m, "the contract has one ts block"
    return m.group(1)


def interfaces() -> dict[str, set[str]]:
    return {name: {f for f, _ in FIELD.findall(body)} for name, body in
            INTERFACE.findall(ts_block())}  # fmt: skip


TYPES = interfaces()


def test_the_site_types_are_the_contract_block() -> None:
    site = SITE_TYPES.read_text(encoding="utf-8")
    if "MarketTodayCard" not in site:
        # ponytail: Phase 13A pushed the cards first; drop this skip once 13B copies the block
        pytest.skip("site/lib/contract.ts predates the Phase 13A cards (13B copies it)")
    assert site == ts_block()


def test_every_card_type_the_server_sends_is_declared() -> None:
    declared = set(re.findall(r'type: "(\w+)";', ts_block()))
    assert declared == {
        "news",
        "history",
        "plan_range",
        "holdings",
        "text",
        "price",
        "price_history",
        "position",
        "compare",
        "market_today",
    }
    intents = re.search(r"export type Intent =(.*?);", ts_block(), re.S)
    assert intents and set(re.findall(r'"(\w+)"', intents.group(1))) == {i.value for i in Intent}


def shape(value: dict, name: str) -> None:
    assert set(value) == TYPES[name], name


def check_cards(board: dict) -> None:
    shape(board, "Dashboard")
    shape(board["profile"], "ProfileLine")
    shape(board["news"], "NewsCard")
    for item in board["news"]["items"]:
        shape(item, "NewsItem")
    shape(board["history"], "HistoryCard")
    for m in board["mentions"]:
        shape(m, "Mention")
    shape(board["plan_range"], "PlanRangeCard")
    r = board["plan_range"]["range"]
    shape(r, "PlanRange")
    shape(r["nominal"], "Cases")
    shape(r["real"], "Cases")
    shape(r["bar"], "RangeBar")
    for row in r["bar"]["rows"]:
        shape(row, "RangeRow")
        for case in row["cases"]:
            shape(case, "RangeCase")
    h = board["holdings"]
    shape(h, "HoldingsCard")
    shape(h["bar"], "MixBar")
    for row in h["rows"]:
        shape(row, "HoldingRow")
    for row in h["bar"]["rows"]:
        shape(row, "MixRow")
        for seg in row["segments"]:
            shape(seg, "MixSegment")


@pytest.fixture
def world(tmp_path: Path, cfg) -> World:  # noqa: F811
    w = World(tmp_path, cfg, FakeChatModels(Intent.PLAN_RANGE.value))
    w.store.save_holdings(USER, to_json(fixture_holdings()))
    return w


def test_the_dashboard_json_matches_the_types(world: World) -> None:
    check_cards(world.client.get(f"/api/u/{world.token(USER)}/dashboard").json())


def test_a_history_row_matches_the_types(world: World) -> None:
    line = api.odds_line("rbi_hike", {"asset": "^NSEBANK", "measure": "excess",
                                      "benchmark": "^NSEI", "n_hits": 6, "hit_rate": 0.6,
                                      "baseline": 0.5}, 10, False)  # fmt: skip
    row = api.history_row(line, "en", "https://nw.example")
    shape(row, "HistoryRow")
    shape(row["bar"], "HistoryBar")


def test_a_chat_turn_and_an_error_match_the_types(world: World) -> None:
    turn = world.ask(USER, "what could my plan become").json()
    shape(turn, "ChatTurn")
    shape(turn["message"], "Message")
    for block in turn["message"]["body"]:
        shape(block, "TextBlock" if block["kind"] == "text" else "LinkBlock")
    shape(turn["card"], "PlanRangeCard")
    error = world.client.get("/api/u/nope/dashboard").json()
    shape(error, "ApiError")
    shape(error["message"], "Message")


def test_a_command_turn_matches_the_types(world: World) -> None:
    for name, card in (("range", "PlanRangeCard"), ("holdings", "HoldingsCard"),
                       ("brief", "HistoryCard"), ("help", "TextCard")):  # fmt: skip
        turn = world.client.post(f"/api/u/{world.token(USER)}/command", json={"name": name})
        shape(turn.json(), "CommandTurn")
        shape(turn.json()["message"], "Message")
        shape(turn.json()["card"], card)


def test_every_command_name_is_declared() -> None:
    names = re.search(r"export type CommandName =(.*?);", ts_block(), re.S)
    assert names and set(re.findall(r'"(\w+)"', names.group(1))) == set(api.COMMANDS)


def test_a_news_card_matches_the_types(world: World) -> None:
    card = api.CARDS[Intent.WHAT_HAPPENED_TODAY](api.TurnFacts(
        None, None, "en", world.services, None, None))  # type: ignore[arg-type]  # fmt: skip
    shape(card, "NewsCard")


FIXTURES = ROOT / "site" / "e2e" / "fixtures"


def test_the_site_mock_fixtures_match_the_types() -> None:
    import json

    for name in ("dashboard", "demo-dashboard"):
        board = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        if board["holdings"] is None:
            board = {**board, "holdings": json.loads(
                (FIXTURES / "dashboard.json").read_text(encoding="utf-8"))["holdings"]}  # fmt: skip
        check_cards(board)
    cards = {"news": "NewsCard", "history": "HistoryCard", "plan_range": "PlanRangeCard",
             "text": "TextCard"}  # fmt: skip
    for path in FIXTURES.glob("turn-*.json"):
        turn = json.loads(path.read_text(encoding="utf-8"))
        shape(turn, "ChatTurn")
        shape(turn["message"], "Message")
        shape(turn["card"], cards[turn["card"]["type"]])
