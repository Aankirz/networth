"""The plan range on the web: /plan-range and the /u/{token} section, over a small fixture
table. No network, and never the real data/sim table."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from networth import sim
from networth.app.services import Services
from networth.app.settings import Settings
from networth.sim.data import Table
from networth.web import plan_view
from networth.web.routes import router, settings, sim_table
from tests.test_links import SECRET, page_path
from tests.test_onboarding import Chat, onboard
from tests.test_web import BANNED, DISCLAIMER, text

LABEL = "This replays real past months. It is not a forecast. Your plan is your choice."
STARTERS = {"steady": "Steady", "balanced": "Balanced", "ambitious": "Ambitious"}


def fixture_table() -> Table:
    months = tuple(dt.date(2015 + i // 12, i % 12 + 1, 1) for i in range(48))
    wave = np.sin(np.arange(48) / 3.0)
    returns = np.column_stack([
        np.full(48, 0.005),  # safety
        0.01 + 0.06 * wave,  # core
        0.012 + 0.1 * wave,  # growth
        np.full(48, 0.004),  # cpi
    ])  # fmt: skip
    return Table(months, returns)


TABLE = fixture_table()


def app_with(table: Table | None, data_dir: Path | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[sim_table] = lambda: table
    if data_dir is not None:
        app.dependency_overrides[settings] = lambda: Settings(
            data_dir, None, None, "https://nw.example", SECRET
        )
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return app_with(TABLE)


DEMO_PAGES = (
    *(f"/plan-range?plan={k}&amount=150000&years=15&fall=20" for k in STARTERS),
    "/plan-range?plan=own&safety=30&core=50&growth=20&amount=50000&years=4&fall=30",
    "/plan-range",
)


@pytest.mark.parametrize("path", DEMO_PAGES)
def test_the_demo_page_renders_with_the_label_and_no_banned_words(client, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert DISCLAIMER in response.text
    assert LABEL in text(response.text)
    assert "<svg" in response.text
    assert not BANNED.search(response.text)


def test_the_demo_page_prints_the_simulated_range(client) -> None:
    r = sim.simulate((20, 70, 10), 150_000, 15, 20, TABLE)
    words = text(client.get("/plan-range?plan=balanced&amount=150000&years=15&fall=20").text)
    for n in (r.invested, r.nominal_p10, r.nominal_median, r.nominal_p90, r.real_median):
        assert sim.rupees(n) in words
    assert f"In {r.hit_limit_pct}% of the paths" in words


def test_a_custom_split_is_the_one_simulated(client) -> None:
    words = text(client.get("/plan-range?plan=own&safety=30&core=50&growth=20").text)
    assert (
        "Your own split. 30% safe money (liquid, gilt, FD), 50% broad index funds, "
        "20% single shares or themes." in words
    )


@pytest.mark.parametrize("query", [
    "plan=own&safety=30&core=50&growth=30",
    "plan=own&safety=30&core=70",
    "plan=yolo",
    "amount=-5",
    "amount=1.5",
    "years=0",
    "fall=101",
])  # fmt: skip
def test_bad_input_gets_the_friendly_400(client, query: str) -> None:
    response = client.get(f"/plan-range?{query}")
    assert response.status_code == 400
    assert DISCLAIMER in response.text
    assert not BANNED.search(response.text)


def test_a_dollar_plan_gets_the_rupee_only_line(client) -> None:
    response = client.get("/plan-range?plan=balanced&amount=2000&currency=USD")
    assert response.status_code == 200
    assert "Rupee plans only for now." in response.text
    assert "<svg" not in response.text


def test_a_missing_table_gets_a_page_saying_how_to_build_it() -> None:
    response = app_with(None).get("/plan-range")
    assert response.status_code == 503
    assert "uv run python -m networth.sim.data" in response.text
    assert DISCLAIMER in response.text


@pytest.fixture
def chat(tmp_path: Path) -> Chat:
    chat = Chat(tmp_path, Services(tmp_path / "data", "https://nw.example", link_secret=SECRET))
    onboard(chat)  # Balanced, ₹1,00,000 a month, INR
    return chat


def test_the_user_page_shows_only_the_users_own_range(chat: Chat) -> None:
    plan = chat.store.get_plan(chat.profile.user_id)
    assert plan is not None
    r = sim.plan_range(plan, chat.profile, table=TABLE)
    page = app_with(TABLE, chat.store.path.parent).get(page_path(chat.store)).text
    words = text(page)
    assert "What history says about this plan" in words
    assert LABEL in words and DISCLAIMER in page
    assert sim.rupees(r.nominal_median) in words
    assert (
        "Balanced. 20% safe money (liquid, gilt, FD), 70% broad index funds, "
        "10% single shares or themes" in words
    )
    assert "Steady" not in words and "Ambitious" not in words
    assert not BANNED.search(page)


def test_a_dollar_user_gets_the_rupee_only_line(chat: Chat) -> None:
    chat.store.save_profile(replace(chat.profile, currency="USD"))
    page = app_with(TABLE, chat.store.path.parent).get(page_path(chat.store)).text
    assert "Rupee plans only for now." in page
    assert "<svg" not in page


def test_the_user_page_still_works_without_the_table(chat: Chat) -> None:
    response = app_with(None, chat.store.path.parent).get(page_path(chat.store))
    assert response.status_code == 200
    assert "What history says about this plan" not in response.text


def _range_with(invested: int, p10: int, p90: int) -> sim.PlanRange:
    return sim.PlanRange(
        targets_pct=(20, 70, 10), monthly_amount=1, years=1, fall_limit_pct=20, paths=1,
        mean_block_months=12, invested=invested, nominal_p10=p10, nominal_median=p10,
        nominal_p90=p90, real_p10=p10, real_median=p10, real_p90=p90, hit_limit_pct=0,
        worst_fall_pct=0, worst_fall_rupees=0, recovery_months=0,
        window_start=dt.date(2007, 10, 1), window_end=dt.date(2026, 9, 1), method_version="t",
    )  # fmt: skip


@pytest.mark.parametrize(("invested", "p10", "p90"), [(100, 300, 900), (800, 100, 900)])
def test_bar_row_names_sit_away_from_the_invested_line(invested, p10, p90) -> None:
    bar = plan_view.bar_geometry(_range_with(invested, p10, p90))
    names_on_right = bar["name_anchor"] == "end"
    assert names_on_right == (bar["invested_x"] < 50)
