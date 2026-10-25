"""Plan range: the user's own plan replayed over real past months, as a range in rupees.

    r = plan_range(plan, profile)                # pure over data/sim/returns.csv
    lines = plan_range_lines(r, "en")            # fixed sentences, numbers filled in
    text = plan_range_message(user_id, store)    # the bot's /range reply, None for USD or no plan

docs/phases/phase-6-method.md fixes every rule. Only the user's own plan is ever simulated:
nothing here compares plans, ranks them or suggests a change.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np

from networth.app.store import Plan, Profile, Store
from networth.sim import config
from networth.sim.data import Table, load_table
from networth.web.fmt import indian_grouping

Lang = Literal["en", "hi", "hinglish"]


class NotRupees(ValueError):
    """The plan's amount is not in rupees. Phase 6 covers INR only."""


@dataclass(frozen=True)
class PlanRange:
    """Every number at the precision it is shown with: rupees to 3 significant figures,
    percentages and months whole. guard.check reads repr(r) as the source of every line."""

    targets_pct: tuple[int, int, int]  # safety, core, growth
    monthly_amount: int
    years: int
    fall_limit_pct: int
    paths: int
    mean_block_months: int
    invested: int
    nominal_p10: int
    nominal_median: int
    nominal_p90: int
    real_p10: int
    real_median: int
    real_p90: int
    hit_limit_pct: int  # share of paths whose worst fall reached fall_limit_pct
    worst_fall_pct: int  # median across paths
    worst_fall_rupees: int  # median across paths
    recovery_months: int | None  # median across paths; None = not back by the end
    window_start: dt.date
    window_end: dt.date
    method_version: str


@dataclass(frozen=True)
class Falls:
    """Each path's worst peak-to-trough fall in its time-weighted value. Indexes are points on
    the value path; recovery is in months, inf when the path never got back to its peak."""

    fall: np.ndarray
    peak: np.ndarray
    recovery_months: np.ndarray


def worst_falls(unit: np.ndarray) -> Falls:
    """unit: (paths, points), the value of one rupee held in the plan at each point."""
    rows = np.arange(unit.shape[0])
    peaks = np.maximum.accumulate(unit, axis=1)
    trough = (1.0 - unit / peaks).argmax(axis=1)
    peak_value = peaks[rows, trough]
    fall = 1.0 - unit[rows, trough] / peak_value
    at_peak = unit >= peak_value[:, None]
    peak = at_peak.argmax(axis=1)
    back = at_peak & (np.arange(unit.shape[1]) > trough[:, None])
    months = np.where(back.any(axis=1), back.argmax(axis=1) - trough, np.inf)
    return Falls(fall, peak, np.where(fall > 0, months, 0.0))


def sig3(x: float) -> int:
    return int(float(f"{x:.3g}"))


def resample(n_months: int, paths: int, months: int, rng: np.random.Generator) -> np.ndarray:
    """(paths, months) table rows: a stationary block bootstrap with circular blocks."""
    restart = rng.random((paths, months)) < 1.0 / config.MEAN_BLOCK_MONTHS
    fresh = rng.integers(n_months, size=(paths, months))
    idx = np.empty((paths, months), dtype=np.intp)
    idx[:, 0] = fresh[:, 0]
    for t in range(1, months):
        idx[:, t] = np.where(restart[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n_months)
    return idx


def grow(weights: np.ndarray, amount: int, growth: np.ndarray, idx: np.ndarray):
    """Money in at the start of each month, a yearly reset to the targets. Returns the rupee
    value and the time-weighted value of one rupee at each point (point 0 is the first
    contribution), and each path's CPI growth."""
    paths, months = idx.shape
    holdings = np.zeros((paths, len(weights)))
    value = np.empty((paths, months + 1))
    unit = np.ones((paths, months + 1))
    cpi = np.ones(paths)
    for t in range(months):
        if t and t % config.REBALANCE_MONTHS == 0:
            holdings = holdings.sum(axis=1)[:, None] * weights
        holdings = holdings + amount * weights
        start = holdings.sum(axis=1)
        if t == 0:
            value[:, 0] = start
        month = growth[idx[:, t]]
        holdings = holdings * month[:, :3]
        cpi = cpi * month[:, 3]
        value[:, t + 1] = holdings.sum(axis=1)
        unit[:, t + 1] = unit[:, t] * value[:, t + 1] / start
    return value, unit, cpi


def simulate(
    targets_pct: tuple[int, int, int],
    monthly_amount: int,
    years: int,
    fall_limit_pct: int,
    table: Table,
    *,
    paths: int | None = None,
    seed: int | None = None,
) -> PlanRange:
    paths = paths or config.PATHS
    months = years * 12
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    idx = resample(len(table.months), paths, months, rng)
    weights = np.array(targets_pct, dtype=float) / 100.0
    value, unit, cpi = grow(weights, monthly_amount, 1.0 + table.returns, idx)
    end, falls = value[:, -1], worst_falls(unit)
    nominal = np.percentile(end, (10, 50, 90))
    real = np.percentile(end / cpi, (10, 50, 90))
    recovery = float(np.median(falls.recovery_months))
    return PlanRange(
        targets_pct=targets_pct, monthly_amount=monthly_amount, years=years,
        fall_limit_pct=fall_limit_pct, paths=paths, mean_block_months=config.MEAN_BLOCK_MONTHS,
        invested=sig3(monthly_amount * months),
        nominal_p10=sig3(nominal[0]), nominal_median=sig3(nominal[1]),
        nominal_p90=sig3(nominal[2]),
        real_p10=sig3(real[0]), real_median=sig3(real[1]), real_p90=sig3(real[2]),
        hit_limit_pct=round(100 * float(np.mean(falls.fall * 100 >= fall_limit_pct))),
        worst_fall_pct=round(100 * float(np.median(falls.fall))),
        worst_fall_rupees=sig3(float(np.median(value[np.arange(paths), falls.peak] * falls.fall))),
        recovery_months=None if np.isinf(recovery) else round(recovery),
        window_start=table.months[0], window_end=table.months[-1],
        method_version=config.METHOD_VERSION,
    )  # fmt: skip


def horizon_years(profile_years: int) -> int:
    for upper, years in config.HORIZON_YEARS:
        if profile_years <= upper:
            return years
    return config.LONG_HORIZON_YEARS


def plan_range(
    plan: Plan,
    profile: Profile,
    *,
    paths: int | None = None,
    seed: int | None = None,
    table: Table | None = None,
) -> PlanRange:
    """Raises NotRupees for a USD amount. `table` defaults to the cached data/sim table."""
    if (profile.currency or "INR") != "INR":
        raise NotRupees(profile.currency)
    if profile.monthly_amount is None or profile.horizon_years is None:
        raise ValueError(f"{profile.user_id} has no amount or horizon yet")
    return simulate(
        tuple(plan.targets_pct[b] for b in config.BUCKETS),
        profile.monthly_amount, horizon_years(profile.horizon_years), plan.max_drop_ok,
        table or load_table(), paths=paths, seed=seed,
    )  # fmt: skip


CRORE: Final = 10**7
CRORE_HUNDREDTH: Final = 10**5


def rupees(n: int) -> str:
    """₹1,50,000 below a crore, ₹2.7 Cr / ₹1.23 Cr from a crore up. Never rounds further."""
    if n < CRORE or n % CRORE_HUNDREDTH:
        return f"₹{indian_grouping(n)}"
    crores, rest = divmod(n, CRORE)
    decimals = f"{rest // CRORE_HUNDREDTH:02d}".rstrip("0")
    return f"₹{crores}.{decimals} Cr" if decimals else f"₹{crores} Cr"


# Fixed sentences per language; only PlanRange fields fill the gaps. Hindi keeps ASCII digits.
LINES: Final[Mapping[str, Mapping[str, str]]] = {
    "en": {
        "what": "This is your own plan: {safety}% safety, {core}% core, {growth}% growth, "
        "{amount} a month for {years} years. It replays real past months from {start} to "
        "{end}, in blocks of about {block} months, {paths} times.",
        "invested": "Money put in over those years: {invested}.",
        "nominal": "Where it could end up: bad case {nominal_p10}, middle {nominal_median}, "
        "good case {nominal_p90}.",
        "real": "After inflation, in today's rupees: bad case {real_p10}, middle "
        "{real_median}, good case {real_p90}.",
        "hit": "In {hit}% of paths the plan fell by {limit}% or more at some point. That is "
        "the fall you said you can sit through.",
        "fall": "The typical worst fall was {fall}%, about {fall_rupees} of the money held at "
        "the time.",
        "recovery": "In the middle case, the worst fall took about {recovery} months to get back.",
        "not_back": "In the middle case, the worst fall was not back by the end.",
        "label": "This replays real past months. It is not a forecast. Your plan is your choice.",
    },
    "hi": {
        "what": "यह आपका अपना प्लान है: {safety}% सेफ़्टी, {core}% कोर, {growth}% ग्रोथ, हर महीने "
        "{amount}, {years} साल तक। इसमें {start} से {end} तक के असली पुराने महीने, लगभग {block} "
        "महीनों के टुकड़ों में, {paths} बार दोहराए गए हैं।",
        "invested": "इन सालों में लगाया गया कुल पैसा: {invested}।",
        "nominal": "पैसा कहाँ तक पहुँच सकता है: बुरे हाल में {nominal_p10}, बीच में "
        "{nominal_median}, अच्छे हाल में {nominal_p90}।",
        "real": "महँगाई के बाद, आज के रुपयों में: बुरे हाल में {real_p10}, बीच में {real_median}, "
        "अच्छे हाल में {real_p90}।",
        "hit": "{hit}% रास्तों में प्लान कभी न कभी {limit}% या उससे ज़्यादा गिरा। यह वही गिरावट "
        "है जिसे आपने कहा था कि आप सह सकते हैं।",
        "fall": "आम तौर पर सबसे बड़ी गिरावट {fall}% थी, यानी उस समय रखे पैसे में लगभग {fall_rupees}।",
        "recovery": "बीच वाले हाल में सबसे बड़ी गिरावट से वापस आने में लगभग {recovery} महीने लगे।",
        "not_back": "बीच वाले हाल में सबसे बड़ी गिरावट आख़िर तक वापस नहीं आई।",
        "label": "यह असली पुराने महीनों को दोहराता है। यह कोई अनुमान नहीं है। आपका प्लान आपकी अपनी पसंद है।",
    },
    "hinglish": {
        "what": "Yeh aapka apna plan hai: {safety}% safety, {core}% core, {growth}% growth, "
        "har mahine {amount}, {years} saal tak. Ismein {start} se {end} tak ke asli purane "
        "mahine, lagbhag {block} mahine ke blocks mein, {paths} baar dohraaye gaye hain.",
        "invested": "In saalon mein lagaya gaya kul paisa: {invested}.",
        "nominal": "Paisa kahan tak pahunch sakta hai: bure haal mein {nominal_p10}, beech "
        "mein {nominal_median}, achhe haal mein {nominal_p90}.",
        "real": "Mehngai ke baad, aaj ke rupayon mein: bure haal mein {real_p10}, beech mein "
        "{real_median}, achhe haal mein {real_p90}.",
        "hit": "{hit}% raaston mein plan kabhi na kabhi {limit}% ya usse zyada gira. Yeh wahi "
        "giravat hai jo aapne kaha tha ki aap seh sakte hain.",
        "fall": "Aam taur par sabse badi giravat {fall}% thi, yaani us waqt ke paise mein "
        "lagbhag {fall_rupees}.",
        "recovery": "Beech wale haal mein sabse badi giravat se wapas aane mein lagbhag "
        "{recovery} mahine lage.",
        "not_back": "Beech wale haal mein sabse badi giravat aakhir tak wapas nahin aayi.",
        "label": "Yeh asli purane mahinon ko dohraata hai. Yeh koi forecast nahin hai. Aapka "
        "plan aapki apni pasand hai.",
    },
}
ORDER: Final = ("what", "invested", "nominal", "real", "hit", "fall")


def plan_range_lines(r: PlanRange, lang: Lang) -> list[str]:
    safety, core, growth = r.targets_pct
    values = {
        "safety": safety, "core": core, "growth": growth, "amount": rupees(r.monthly_amount),
        "years": r.years, "start": r.window_start.year, "end": r.window_end.year,
        "block": r.mean_block_months, "paths": indian_grouping(r.paths),
        "hit": r.hit_limit_pct, "limit": r.fall_limit_pct, "fall": r.worst_fall_pct,
        "fall_rupees": rupees(r.worst_fall_rupees), "recovery": r.recovery_months,
        **{k: rupees(getattr(r, k)) for k in (
            "invested", "nominal_p10", "nominal_median", "nominal_p90",
            "real_p10", "real_median", "real_p90")},
    }  # fmt: skip
    lines = LINES[lang]
    keys = [*ORDER, "not_back" if r.recovery_months is None else "recovery", "label"]
    return [lines[k].format(**values) for k in keys]


def plan_range_message(user_id: str, store: Store, lang: str | None = None) -> str | None:
    """The bot's /range reply in `lang`, else the user's language. None with no plan, or not
    in rupees."""
    profile, plan = store.get_profile(user_id), store.get_plan(user_id)
    if profile is None or plan is None or profile.monthly_amount is None:
        return None
    if profile.horizon_years is None:
        return None
    try:
        r = plan_range(plan, profile)
    except NotRupees:
        return None
    lang = next(x for x in (lang, profile.lang, "en") if x in LINES)
    return "\n".join(plan_range_lines(r, lang))
