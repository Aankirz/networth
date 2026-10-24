"""The web pages, rendered from a fixture sqlite and, when it exists, the real one. Every number
checked here is read back from odds(), compare() or position_range()."""

from __future__ import annotations

import datetime as dt
import html
import re
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from networth.engine import backtest, odds
from networth.engine.model import DEFAULT_DB, EventType, RatesDB, write_db
from networth.web import fmt, names
from networth.web.routes import rates_db, router
from tests.conftest import (
    BOOK_EVENTS,
    book_series,
    random_walk,
    row,
    sessions,
    write_events,
    write_prices,
)

BANNED = re.compile(
    r"\b(buy|sell|guaranteed|sure shot|can't lose|multibagger|target price)\b", re.IGNORECASE
)
DISCLAIMER = "Research, not advice"

# Enough RBI hikes, each its own episode, for a row that is not a weak signal.
MORE_RBI = [
    row(f"rbi_{y}{s}", f"{y}-{md}", "rbi_hike", "in")
    for y, md, s in (
        ("2008", "06-11", "a"),
        ("2012", "02-15", "b"),
        ("2015", "09-10", "a"),
        ("2016", "04-20", "b"),
        ("2019", "10-09", "a"),
        ("2021", "08-18", "b"),
    )
]


def extra_series() -> dict:
    us = sessions(dt.date(1997, 1, 1), dt.date(2023, 6, 30))
    nse = us[us >= "2007-09-17"]
    return {
        "^CNXIT": random_walk(nse, 21),
        "XLF": random_walk(us, 22),
        "XLK": random_walk(us, 23),
    }


@pytest.fixture
def web_db(tmp_path: Path) -> Path:
    events = write_events(tmp_path / "events.csv", BOOK_EVENTS + MORE_RBI)
    prices = write_prices(tmp_path / "prices", {**book_series(), **extra_series()})
    path = tmp_path / "rates.sqlite"
    write_db(path, backtest.build(events, prices))
    return path


def client_for(db: Path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[rates_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def client(web_db: Path) -> TestClient:
    return client_for(web_db)


def text(page: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


PAGES = (
    "/",
    "/why/rbi_hike/^NSEBANK",
    "/why/oil_supply/JETS",
    "/what-if/rbi_hike/^NSEBANK",
    "/what-if/oil_supply/JETS?amount=2000&currency=USD",
    "/scoreboard/rbi_hike",
    "/track-record",
    "/stats",
)


@pytest.mark.parametrize("path", [*PAGES, "/static/networth.css"])
def test_every_route_returns_200(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


ERROR_PAGES = ("/why/nope/X", "/what-if/rbi_hike/^NSEBANK?amount=-5")  # the 404 and the 400


@pytest.mark.parametrize("path", [*PAGES, *ERROR_PAGES])
def test_pages_carry_the_disclaimer_and_no_banned_words(client: TestClient, path: str) -> None:
    page = client.get(path).text
    assert DISCLAIMER in page
    assert not BANNED.search(page)


def test_why_shows_the_engine_counts_and_every_episode(client, web_db) -> None:
    o = odds.odds("rbi_hike", "^NSEBANK", db=web_db)
    page = client.get("/why/rbi_hike/^NSEBANK").text
    words = text(page)
    assert f"in {o['n_hits']} of {o['n_episodes']} past RBI rate hikes" in words
    assert fmt.percent(o["baseline"]) in words
    for e in o["episodes"]:
        assert e["date"] in words
        for url in e["sources"]:
            assert f'href="{url}" rel="noopener" target="_blank"' in page


@pytest.mark.parametrize(("type", "asset"), [("rbi_hike", "^NSEBANK"), ("oil_supply", "JETS")])
def test_weak_signal_label_appears_iff_the_engine_says_so(client, web_db, type, asset) -> None:
    o = odds.odds(type, asset, db=web_db)
    words = text(client.get(f"/why/{type}/{asset}").text)
    assert ("Weak signal, only" in words) == o["weak_signal"]


def test_fixture_has_both_weak_and_strong_rows(web_db) -> None:
    flags = {odds.odds(t, a, db=web_db)["weak_signal"] for t, a in (
        ("rbi_hike", "^NSEBANK"), ("oil_supply", "JETS"))}  # fmt: skip
    assert flags == {True, False}


def test_what_if_shows_the_position_range(client, web_db) -> None:
    rng = odds.position_range(2000, "JETS", "oil_supply", db=web_db)
    words = text(client.get("/what-if/oil_supply/JETS?amount=2000&currency=USD").text)
    for key in ("p10", "median", "p90"):
        assert fmt.money(rng[key], "USD") in words
    assert "History, not a forecast" in words


def test_what_if_defaults_to_one_lakh_in_the_asset_currency(client, web_db) -> None:
    rng = odds.position_range(100_000, "^NSEBANK", "rbi_hike", db=web_db)
    words = text(client.get("/what-if/rbi_hike/^NSEBANK").text)
    assert "On ₹1,00,000" in words
    assert fmt.money(rng["median"], "INR") in words


def test_what_if_in_another_currency_says_fx_is_left_out(client) -> None:
    words = text(client.get("/what-if/rbi_hike/^NSEBANK?currency=USD").text)
    assert "Exchange-rate moves are left out" in words


@pytest.mark.parametrize(
    ("n", "expected"),
    [(100000, "1,00,000"), (12345678, "1,23,45,678"), (999, "999"), (-4000, "−4,000")],
)
def test_indian_grouping(n: int, expected: str) -> None:
    assert fmt.indian_grouping(n) == expected


def test_money_signs_use_a_true_minus() -> None:
    assert (fmt.money(-258, "USD"), fmt.money(211, "USD")) == ("−$258", "+$211")
    assert fmt.money(-400000, "INR") == "−₹4,00,000"


def test_scoreboard_shows_compare_counts_in_caller_order(client, web_db) -> None:
    words = text(client.get("/scoreboard/rbi_hike").text)
    for group in (("^NSEBANK", "^CNXIT"), ("XLF", "XLK")):
        c = odds.compare("rbi_hike", list(group), db=web_db)
        positions = []
        for a in c["assets"]:
            name = names.asset_name(a["asset"])
            assert f"in {a['n_hits']} of {c['n_episodes']} shared" in words
            positions.append(words.index(name))
        assert positions == sorted(positions)


def test_scoreboard_never_ranks(client) -> None:
    words = text(client.get("/scoreboard/rbi_hike").text).lower()
    assert not re.search(r"\b(best|worst|top pick|#1|rank(ed)? \d)\b", words)


@pytest.mark.parametrize(
    "path", ["/why/nope/^NSEBANK", "/why/rbi_hike/NOPE", "/what-if/nope/JETS", "/scoreboard/nope"]
)
def test_unknown_type_or_asset_is_a_friendly_404(client, path) -> None:
    r = client.get(path)
    assert r.status_code == 404
    assert "That page isn't here" in r.text and DISCLAIMER in r.text


@pytest.mark.parametrize(
    "query", ["amount=abc", "amount=0", "amount=-5", "amount=1e13", "amount=nan", "currency=EUR"]
)
def test_bad_what_if_input_is_a_friendly_400(client, query) -> None:
    r = client.get(f"/what-if/rbi_hike/^NSEBANK?{query}")
    assert r.status_code == 400
    assert "Check the amount" in r.text


def test_track_record_empty_state(client) -> None:
    assert "We start counting from our first message." in text(client.get("/track-record").text)


def test_track_record_renders_its_table(web_db, tmp_path) -> None:
    copy = tmp_path / "with_record.sqlite"
    shutil.copy(web_db, copy)
    conn = sqlite3.connect(copy)
    with conn:
        conn.execute("CREATE TABLE track_record (said TEXT, what_happened TEXT)")
        conn.execute("INSERT INTO track_record VALUES ('Banks 6 of 9', 'Banks beat it')")
    conn.close()
    words = text(client_for(copy).get("/track-record").text)
    assert "what happened" in words and "Banks 6 of 9" in words
    assert "1 line, as recorded." in words
    assert "We start counting" not in words


def test_stats_counts_match_sqlite(client, web_db) -> None:
    conn = sqlite3.connect(web_db)
    n_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    conn.close()
    assert f"Past news events {fmt.western_grouping(n_events)}" in " ".join(
        text(client.get("/stats").text).split()
    )


def test_every_event_type_has_words() -> None:
    assert set(names.TYPES) == set(EventType)


real_db = pytest.mark.skipif(not DEFAULT_DB.exists(), reason="data/base_rates.sqlite missing")


@real_db
def test_real_db_why_and_what_if_match_the_engine() -> None:
    c = client_for(DEFAULT_DB)
    why = text(c.get("/why/rbi_hike/^NSEBANK").text)
    assert "in 14 of 22 past RBI rate hikes" in why
    assert "Weak signal, only" not in why
    what_if = text(c.get("/what-if/oil_supply/JETS?amount=2000&currency=USD").text)
    assert all(v in what_if for v in ("−$258", "−$1", "+$211"))


@real_db
def test_real_db_why_pages_never_use_banned_words() -> None:
    c = client_for(DEFAULT_DB)
    rates = RatesDB.open(DEFAULT_DB)
    assets = sorted(rates.assets())
    rates.close()
    for t in EventType:
        for a in assets:
            page = c.get(f"/why/{t.value}/{a}").text
            assert not BANNED.search(page), (t, a)
            assert DISCLAIMER in page


def test_the_one_real_headline_with_a_banned_word_is_reworded() -> None:
    reworded = names.reword_headline("UBS agrees to buy Credit Suisse for CHF 3B")
    assert reworded == "UBS agrees to take over Credit Suisse for CHF 3B"
