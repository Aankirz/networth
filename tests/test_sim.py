"""The plan range over small hand-made tables. No network, never data/."""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
from pathlib import Path

import numpy as np
import pytest

import networth.sim as sim
from networth import guard
from networth.app.store import Plan, Store, new_profile
from networth.bot.message import DISCLAIMER
from networth.sim import (
    NotRupees,
    horizon_years,
    plan_range,
    plan_range_lines,
    plan_range_message,
    rupees,
    simulate,
    worst_falls,
)
from networth.sim.data import Table

NOW = "2026-10-25T00:00:00+00:00"
LANGS = ("en", "hi", "hinglish")


def table(rows: list[tuple[float, float, float, float]]) -> Table:
    months = tuple(dt.date(2012 + i // 12, i % 12 + 1, 1) for i in range(len(rows)))
    return Table(months, np.array(rows, dtype=float))


def varying(n: int = 24) -> Table:
    """Safety alternates 0.3% and 0.5%; core and growth swing hard; CPI 0.4% a month."""
    return table([(0.003, 0.2, 0.3, 0.004) if i % 2 else (0.005, -0.15, -0.2, 0.004)
                  for i in range(n)])  # fmt: skip


def constant(r: float, cpi: float = 0.0, n: int = 24) -> Table:
    return table([(r, r, r, cpi)] * n)


def annuity_due(amount: float, r: float, months: int) -> float:
    return amount * (1 + r) * ((1 + r) ** months - 1) / r


def to_3_sig(x: float) -> int:
    digits = math.floor(math.log10(abs(x))) + 1
    return round(x, 3 - digits)


def test_the_same_seed_gives_the_same_range() -> None:
    args = ((20, 70, 10), 10_000, 3, 20, varying())
    assert simulate(*args, seed=7) == simulate(*args, seed=7)


def test_all_safety_ends_close_to_the_safety_rate_compounded() -> None:
    r = simulate((100, 0, 0), 10_000, 3, 20, varying(), paths=2_000)
    expected = annuity_due(10_000, 0.004, 36)
    assert r.nominal_p10 == pytest.approx(expected, rel=0.01)
    assert r.nominal_p90 == pytest.approx(expected, rel=0.01)


def test_a_constant_table_gives_the_closed_form_and_real_equals_nominal() -> None:
    r = simulate((20, 70, 10), 10_000, 3, 20, constant(0.01), paths=500)
    expected = to_3_sig(annuity_due(10_000, 0.01, 36))
    assert (r.nominal_p10, r.nominal_median, r.nominal_p90) == (expected,) * 3
    assert (r.real_p10, r.real_median, r.real_p90) == (expected,) * 3


def test_worst_fall_on_a_hand_built_path() -> None:
    falls = worst_falls(np.array([[1.0, 1.2, 0.9, 1.0, 1.2, 1.3]]))
    assert falls.fall[0] == pytest.approx(0.25)
    assert (falls.peak[0], falls.recovery_months[0]) == (1, 2)


def test_a_path_that_never_gets_back_recovers_never() -> None:
    falls = worst_falls(np.array([[1.0, 2.0, 1.0, 1.5]]))
    assert falls.fall[0] == pytest.approx(0.5)
    assert falls.recovery_months[0] == np.inf


def test_a_path_that_only_rises_has_no_fall_to_recover_from() -> None:
    falls = worst_falls(np.array([[1.0, 1.1, 1.2]]))
    assert (falls.fall[0], falls.recovery_months[0]) == (0.0, 0.0)


def test_hitting_the_limit_counts_a_fall_at_or_beyond_it() -> None:
    fall_pct = 100 * (1 - 0.95**36)
    at = simulate((20, 70, 10), 10_000, 3, math.floor(fall_pct), constant(-0.05), paths=200)
    beyond = simulate((20, 70, 10), 10_000, 3, math.ceil(fall_pct), constant(-0.05), paths=200)
    assert (at.hit_limit_pct, beyond.hit_limit_pct) == (100, 0)
    assert at.worst_fall_pct == round(fall_pct)
    assert at.recovery_months is None


def test_the_invested_total_is_the_amount_times_the_months() -> None:
    assert simulate((20, 70, 10), 12_500, 5, 20, varying(), paths=100).invested == 750_000


@pytest.mark.parametrize(("stored", "years"), [(2, 3), (4, 5), (7, 10), (15, 15)])
def test_onboarding_horizons_map_to_simulated_years(stored: int, years: int) -> None:
    assert horizon_years(stored) == years


@pytest.mark.parametrize(
    ("n", "text"),
    [(5_000, "₹5,000"), (1_00_000, "₹1,00,000"), (27_00_000, "₹27,00,000"),
     (99_90_000, "₹99,90,000"), (1_00_00_000, "₹1 Cr"), (1_20_00_000, "₹1.2 Cr"),
     (1_23_00_000, "₹1.23 Cr"), (12_30_00_000, "₹12.3 Cr"), (1_23_45_678, "₹1,23,45,678")],
)  # fmt: skip
def test_rupees_in_indian_format(n: int, text: str) -> None:
    assert rupees(n) == text


def ranges() -> list[sim.PlanRange]:
    back = simulate((20, 70, 10), 1_50_000, 3, 20, varying())
    big = dataclasses.replace(back, invested=2_70_00_000, nominal_median=6_85_00_000,
                              nominal_p90=12_30_00_000)  # fmt: skip
    never = simulate((60, 40, 0), 25_000, 3, 10, constant(-0.05), paths=200)
    return [back, big, never]


@pytest.mark.parametrize("lang", LANGS)
def test_every_line_passes_the_guard_against_its_range(lang: str) -> None:
    for r in ranges():
        for line in plan_range_lines(r, lang):
            assert guard.check(line, repr(r)).problems == (), line


@pytest.mark.parametrize("lang", LANGS)
def test_the_lines_end_with_the_plain_label_and_leave_the_footer_to_the_message(lang: str) -> None:
    labels = {
        "en": "It is not a forecast.",
        "hi": "यह कोई अनुमान नहीं है।",
        "hinglish": "Yeh koi forecast nahin hai.",
    }
    lines = plan_range_lines(ranges()[0], lang)
    assert lines[-1].endswith(labels[lang])
    assert not any(DISCLAIMER.search(line) for line in lines)


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Store:
    monkeypatch.setattr(sim, "load_table", varying)
    return Store(tmp_path)


def save_user(store: Store, currency: str, *, with_plan: bool = True) -> str:
    profile = dataclasses.replace(new_profile(4242, NOW), currency=currency,
                                  monthly_amount=1_50_000, horizon_years=2, lang="en")  # fmt: skip
    store.save_profile(profile)
    if with_plan:
        store.save_plan(Plan(profile.user_id, "balanced",
                             {"safety": 20, "core": 70, "growth": 10}, 20, NOW))  # fmt: skip
    return profile.user_id


def test_a_rupee_user_gets_their_range(store: Store) -> None:
    text = plan_range_message(save_user(store, "INR"), store)
    assert text is not None
    assert (
        "20% safe money, 70% broad index funds, "
        "10% single shares or themes, ₹1,50,000 a month for 3 years" in text
    )
    assert text.endswith("It is not a forecast.")


def test_a_dollar_user_gets_none(store: Store) -> None:
    user_id = save_user(store, "USD")
    assert plan_range_message(user_id, store) is None
    with pytest.raises(NotRupees):
        plan_range(store.get_plan(user_id), store.get_profile(user_id))


def test_a_user_without_a_plan_gets_none(store: Store) -> None:
    assert plan_range_message(save_user(store, "INR", with_plan=False), store) is None
