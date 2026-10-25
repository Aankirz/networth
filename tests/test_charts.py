"""The two SVG charts: every mark is reachable by keyboard and says what its tooltip shows,
the shapes sit where the numbers put them, and every colour comes from a token."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

from networth.web import plan_view, views
from networth.web.routes import HERE
from tests.test_sim_web import TABLE, _range_with, app_with
from tests.test_web import client_for, text, web_db  # noqa: F401  (web_db is a fixture)

MARK = re.compile(
    r'<g class="chart-mark s-(\w+)" tabindex="0" role="img" aria-label="([^"]+)">(.*?)</g>', re.S
)
TIP_TEXT = re.compile(r'<p class="chart-tip__(?:label|row)">(.*?)</p>', re.S)
LEGEND = re.compile(r'<li class="s-(\w+)">')
PLAN_PAGE = "/plan-range?plan=balanced&amount=150000&years=15&fall=20"
WHAT_IF_PAGE = "/what-if/rbi_hike/^NSEBANK"


@pytest.fixture
def what_if(web_db: Path) -> str:  # noqa: F811
    return client_for(web_db).get(WHAT_IF_PAGE).text


@pytest.fixture
def plan_range() -> str:
    return app_with(TABLE).get(PLAN_PAGE).text


def _marks(page: str) -> list[tuple[str, str, str]]:
    marks = [(s, html.unescape(label), body) for s, label, body in MARK.findall(page)]
    assert marks, "the chart has focusable marks"
    return marks


def _tip_words(body: str) -> list[str]:
    return [" ".join(text(p).split()) for p in TIP_TEXT.findall(body)]


@pytest.mark.parametrize("page", ["what_if", "plan_range"])
def test_every_tooltip_says_what_its_aria_label_says(page: str, request) -> None:
    for _, label, body in _marks(request.getfixturevalue(page)):
        for words in _tip_words(body):
            for part in words.split():
                assert part in label, (part, label)


@pytest.mark.parametrize("page", ["what_if", "plan_range"])
def test_the_legend_names_every_series_the_marks_use(page: str, request) -> None:
    source = request.getfixturevalue(page)
    assert {s for s, _, _ in _marks(source)} <= set(LEGEND.findall(source))


def test_plan_bars_carry_the_same_rupees_as_the_range_above(plan_range: str) -> None:
    figures = re.findall(r'<dd class="num">([^<]+)</dd>', plan_range)
    before, after = (label for s, label, _ in _marks(plan_range) if s in ("before", "after"))
    assert all(f in before for f in figures[:3])
    assert all(f in after for f in figures[3:6])


def test_the_what_if_band_carries_the_engine_range(what_if: str) -> None:
    figures = [html.unescape(f) for f in re.findall(r'<dd class="num">([^<]+)</dd>', what_if)]
    band = next(label for s, label, _ in _marks(what_if) if s == "band")
    assert all(f in band for f in figures)


def test_bars_and_the_invested_line_share_one_scale_from_zero() -> None:
    bar = plan_view.bar_geometry(_range_with(invested=500, p10=250, p90=1000))
    assert [(r["x"], r["w"]) for r in bar["rows"]] == [(25, 75), (25, 75)]
    assert bar["invested_x"] == 50


def test_close_dots_stack_so_they_never_touch_on_the_narrowest_phone() -> None:
    episodes = [{"raw_return": 0.00005 * i, "date": f"2020-01-{i:02}"} for i in range(40)]
    strip = views.strip_geometry(1000, episodes, {"p10": 0, "median": 1, "p90": 2})
    phone_px, diameter = 288, 2 * strip["r"]
    dots = strip["dots"]
    for i, a in enumerate(dots):
        for b in dots[i + 1 :]:
            apart_x = abs(a["cx"] - b["cx"]) / 100 * phone_px
            apart_y = abs(a["cy"] - b["cy"])
            assert apart_x >= diameter or apart_y >= diameter, (a, b)


def test_the_chart_stylesheet_is_served(web_db: Path) -> None:  # noqa: F811
    response = client_for(web_db).get("/static/charts.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


def test_every_chart_colour_reads_a_token() -> None:
    css = (HERE / "static" / "charts.css").read_text()
    colours = re.findall(
        r"^\s*(fill|stroke|color|background|border(?:-top)?|box-shadow):\s*([^;]+);", css, re.M
    )
    assert colours
    for prop, value in colours:
        assert "var(--" in value or value in ("none", "transparent"), (prop, value)


def test_chart_templates_keep_the_copy_rules() -> None:
    for name in ("_chart.html", "_plan_range.html", "what_if.html"):
        source = (HERE / "templates" / name).read_text()
        assert "!" not in text(source), name
        assert "leans" not in source, name
