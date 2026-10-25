"""The investing-day brief, written by code in English, Hindi and Hinglish: short enough to read
in ten seconds, leading with the user's own plan in an event month, counts in the detail."""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from networth import brief, guard, sim
from networth.app.store import Plan, Profile, Step
from networth.bot.message import FOOTER, plain
from networth.bot.telegram import html
from networth.brief.lines import Line
from networth.engine import odds as engine
from tests.test_sim import varying
from tests.test_web import web_db  # noqa: F401, F811 - the engine fixture

LANGS = ("en", "hi", "hinglish")
TELEGRAM_MAX = 4096
MAX_VISIBLE = 8
KOLKATA = ZoneInfo("Asia/Kolkata")
MORNING = dt.datetime(2026, 11, 1, 8, 0, tzinfo=KOLKATA)
USER = Profile(
    "tg:1", "telegram", 1, Step.DONE, "tok", "2026-10-01", "2026-10-01", lang="en",
    invest_day=1, goal="house", horizon_years=7, drop_comfort=20, monthly_amount=100_000,
    currency="INR", exclude=("us_stocks",),
)  # fmt: skip
PLAN = Plan("tg:1", "balanced", {"safety": 20, "core": 70, "growth": 10}, 20, "2026-10-01")
RBI = brief.Event("rbi_hike", dt.date(2026, 10, 20), "RBI raises repo rate by 25 bps", ())
BANKS = brief.Event("bank_stress", dt.date(2026, 10, 14), "A big lender is in trouble", ())


def line(asset: str = "^NSEBANK", hits: int = 14, base: float = 0.56, n: int = 22,
         measure: str = "excess", hit_rate: float | None = None) -> Line:  # fmt: skip
    rate = hits / n if hit_rate is None else hit_rate
    return Line("rbi_hike", asset, measure, "^NSEI (^BSESN before 2007-09-17)", n, hits, rate,
                base, n < 8)  # fmt: skip


FOUR = (line(), line("^NSEI", 12, 0.58, measure="raw"), line("^CNXIT", 9, 0.5),
        line("^CNXPSUBANK", 4, 0.49, n=6))  # fmt: skip


def event_brief(**changes) -> brief.Brief:
    rng = sim.plan_range(PLAN, USER, table=varying(), paths=200, seed=1)
    base = brief.Brief(USER, PLAN, MORNING, (RBI,), FOUR, rng)
    return replace(base, **changes)


def visible(text: str, detail: tuple[str, ...]) -> list[str]:
    """Non-empty lines of the plain render before the detail block."""
    head = text.split("\n".join(detail))[0] if detail else text
    return [x for x in head.splitlines() if x.strip()]


@pytest.mark.parametrize("lang", LANGS)
def test_an_event_month_brief_is_eight_visible_lines_at_most(lang: str) -> None:
    m = event_brief().message(lang)
    assert len(visible(plain(m), m.detail)) <= MAX_VISIBLE
    assert len(html(m)) < TELEGRAM_MAX
    assert len(m.detail) == len(FOUR)


@pytest.mark.parametrize("lang", LANGS)
def test_an_empty_month_says_nothing_needs_attention(lang: str) -> None:
    m = replace(event_brief(), events=(), lines=(), range=None).message(lang)
    assert len(visible(plain(m), m.detail)) <= MAX_VISIBLE and m.detail == ()
    assert len(m.body) == 2, "the news line and the plan line"
    assert m.footer == FOOTER[lang]


def test_an_event_month_leads_with_the_plan_range_before_any_count() -> None:
    m = event_brief().message("en")
    assert m.title == "Morning. It's your investing day, and ₹1,00,000 is ready."
    assert m.body[0] == "This month's news: RBI rate hike on Oct 20."
    built = m.body[1].splitlines()
    assert built[0] == ("Months like this are why you have a plan. Yours is built to sit "
                        "through a fall of up to 20%.")  # fmt: skip
    r = event_brief().range
    assert built[1] == (f"In replays of past markets, a fall that big came in "
                        f"{r.hit_limit_pct}% of paths. Bad case {sim.rupees(r.nominal_p10)}, "
                        f"middle {sim.rupees(r.nominal_median)}.")  # fmt: skip
    assert m.body[2:] == ("Your plan: Balanced, the one you chose.", "What history counted:")
    assert not any("14 of 22" in b for b in m.body), "counts stay inside the detail"


def test_a_dollar_plan_keeps_the_fall_line_and_drops_the_replay_numbers() -> None:
    m = event_brief(range=None).message("en")
    assert m.body[1] == ("Months like this are why you have a plan. Yours is built to sit "
                         "through a fall of up to 20%.")  # fmt: skip


def test_history_lines_state_counts_with_the_normal_rate_and_no_direction() -> None:
    near, far, weak = line(hits=13, base=0.56), line(hits=20, base=0.56), FOUR[3]
    assert near.words("en") == (
        "Indian banks (Nifty Bank) beat the Nifty 50 in 13 of 22 past RBI rate hikes. "
        "Normal is 56%, so this is within normal ups and downs."
    )
    assert far.words("en").endswith("in 20 of 22 past RBI rate hikes. Normal is 56%.")
    assert weak.words("en").endswith("Only 6 past cases, too few to call a pattern.")
    assert line("^NSEI", 12, 0.58, measure="raw").words("hi") == (
        "पिछली 22 RBI दर बढ़ोतरियों में से 12 के बाद Nifty 50 में तेज़ी रही। सामान्य समय में "
        "यह 58% होता है, तो यह आम उतार-चढ़ाव के भीतर है।"
    )
    assert near.words("hinglish").startswith(
        "Pichhle 22 RBI rate hikes mein se 13 ke baad Indian banks (Nifty Bank) ne Nifty 50 se "
        "behtar kiya."
    )


@pytest.mark.parametrize("lang", LANGS)
def test_no_lean_words_or_colour_marks_and_the_guard_passes(lang: str) -> None:
    text = plain(event_brief().message(lang))
    assert not any(mark in text for mark in ("🟢", "🔴", "⚪", "lean", "Weak signal"))
    assert guard.check(text, text).ok, guard.check(text, text).problems
    assert text.count(FOOTER[lang]) == 1 and text.endswith(FOOTER[lang])


def test_stress_news_names_the_feeling_and_never_promises() -> None:
    m = event_brief(events=(BANKS,)).message("en")
    assert m.body[0] == ("A rough stretch in the news: Bank stress on Oct 14. Shocks like this "
                         "have happened before, and you planned for one.")  # fmt: skip
    assert "Aise jhatke pehle bhi aaye hain" in event_brief(events=(BANKS,)).message(
        "hinglish").body[0]  # fmt: skip


@pytest.mark.parametrize(("hour", "greeting"), [(8, "Morning."), (13, "Afternoon."),
                                                (19, "Evening.")])  # fmt: skip
def test_the_greeting_follows_the_users_own_clock(hour: int, greeting: str) -> None:
    m = event_brief(local=MORNING.replace(hour=hour)).message("en")
    assert m.title.startswith(greeting)


def test_a_brief_asked_for_on_another_day_does_not_claim_it_is_investing_day() -> None:
    m = event_brief(local=MORNING.replace(day=9)).message("hi")
    assert m.title == "सुप्रभात। इस महीने का आपका ब्रीफ़ यह रहा।"


def test_compose_reads_the_engine_and_keeps_the_plan_line_name_only(web_db: Path) -> None:  # noqa: F811
    row = engine.odds("rbi_hike", "^NSEBANK", db=web_db)
    event = replace(RBI, odds=(row,))
    b = brief.compose([event], USER, PLAN, web_db, MORNING)
    assert b.lead is not None and b.lead.asset == "^NSEBANK"
    m = b.message("en")
    counted = f"{row['n_hits']} of {row['n_episodes']} past RBI rate hikes."
    assert m.detail[0].startswith(f"Indian banks (Nifty Bank) beat the Nifty 50 in {counted}")
    assert not any("%" in block for block in m.body if "plan:" in block)


def test_buttons_are_friendlier_and_keep_their_callback_data() -> None:
    keyboard = brief.buttons(event_brief(), "hinglish", "https://nw.example", "https://p")
    labels = [(b.label, b.data or b.url) for row in keyboard for b in row]
    assert labels == [
        ("Theek hai", "br:ok"), ("Mera plan", "br:plan"),
        ("Yeh counts kyun?", "https://nw.example/why/rbi_hike/^NSEBANK"),
        ("Har sector", "https://nw.example/scoreboard/rbi_hike"),
        ("Mera page", "https://p"), ("Meri range", "br:range"),
    ]  # fmt: skip
