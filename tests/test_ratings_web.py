"""The public /r pages and the ratings API: open without sign-in, every driver's source shown,
the track record on the page, and JSON shaped as the contract says."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from networth.app.settings import Settings
from networth.web import ratings_web
from networth.web.routes import router, settings
from tests.ratings_fakes import FakeSources, seen
from tests.test_web_api_contract import CONTRACT

BLOCK = re.findall(r"```ts\n(.*?)```", CONTRACT.read_text(encoding="utf-8"), re.S)
FIELDS = {
    name: set(re.findall(r"^  (\w+)\??: ", body, re.M))
    for block in BLOCK
    for name, body in re.findall(r"export interface (\w+) \{\n(.*?)\n\}", block, re.S)
}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    stories = (seen("Banks rally as RBI holds repo rate"),)
    monkeypatch.setattr(ratings_web, "SOURCES", lambda data_dir: FakeSources(stories=stories))
    monkeypatch.setattr(ratings_web, "_cache", {})
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[settings] = lambda: Settings(tmp_path, None, None, "https://nw.test")
    return TestClient(app)


def test_a_rating_page_opens_without_sign_in_and_shows_its_sources_and_record(
    client: TestClient,
) -> None:
    page = client.get("/r/hdfcbank")
    assert page.status_code == 200
    html = page.text
    assert "HDFC Bank Limited: " in html and "/100" in html
    assert "https://example.test/Yahoo" in html, "each driver links its source"
    assert "Ratings like this beat the Nifty" in html
    assert "advice" not in html.lower()


@pytest.mark.parametrize("slug", ["mf120716", "sfctech", "aapl"])
def test_funds_ipos_and_us_shares_have_pages_too(client: TestClient, slug: str) -> None:
    assert client.get(f"/r/{slug}").status_code == 200


def test_the_sector_pages_show_the_moves_and_the_news(client: TestClient) -> None:
    board = client.get("/r/sectors").text
    assert "Banks rally as RBI holds repo rate" in board and "Smallcap" in board
    one = client.get("/r/sector-bank").text
    assert "Bank sector" in one and "Smallcap" not in one
    assert client.get("/r/sector-nope").status_code == 404


def test_an_unknown_name_is_a_friendly_404(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(ratings_web, "SOURCES", lambda d: FakeSources(stocks={}))
    monkeypatch.setattr(FakeSources, "fund_search", lambda self, q: [])
    monkeypatch.setattr(FakeSources, "ipos", lambda self: [])
    page = client.get("/r/nosuchco")
    assert page.status_code == 404 and "couldn't find" in page.text
    api = client.get("/api/rating/nosuchco")
    assert api.status_code == 404 and api.json()["error"] == "not_found"


def test_the_api_cards_have_the_contracts_fields(client: TestClient) -> None:
    card = client.get("/api/rating/HDFCBANK").json()
    assert set(card) == FIELDS["RatingCard"] and card["currency"] == "INR"
    assert card["url"] == "https://nw.test/r/hdfcbank"
    for d in card["drivers"]:
        assert set(d) == FIELDS["Driver"] and set(d["source"]) == FIELDS["Source"]
    assert set(card["track"]) == FIELDS["Track"]
    board = client.get("/api/sectors").json()
    assert set(board) == FIELDS["SectorsCard"]
    for row in board["rows"]:
        assert set(row) == FIELDS["SectorRow"]
    table = client.get("/api/ratings/backtest").json()
    assert set(table) == FIELDS["RatingsBacktest"]
    for g in table["groups"]:
        assert set(g) == FIELDS["BacktestGroup"]
        for r in g["rows"]:
            assert set(r) == FIELDS["BacktestRow"]


def test_a_foreign_browser_origin_is_refused(client: TestClient) -> None:
    got = client.get("/api/sectors", headers={"Origin": "https://evil.example"})
    assert got.status_code == 403
