"""Pure functions from the engine's JSON to what a template prints. Templates only print.

Every number shown comes from odds(), compare() or position_range(), formatted here. The only
arithmetic is the what-if strip's geometry, which places shapes and is never printed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from networth.engine.odds import CompareJSON, OddsJSON, PositionRangeJSON
from networth.web import names
from networth.web.fmt import money, percent, signed_percent

STRIP_WIDTH: Final = 640
STRIP_PAD: Final = 24
DOT_R: Final = 7
STRIP_BASE: Final = 40


def _claim(measure: str, benchmark: str) -> str:
    """'beat the Nifty 50' or 'rose': what a hit means for this row."""
    if measure == "raw":
        return "rose"
    return f"beat {names.benchmark_name(benchmark)}"


def _result_words(hit: bool, measure: str) -> str:
    if measure == "raw":
        return "Rose" if hit else "Fell"
    return "Beat" if hit else "Lagged"


def _episode_row(e: dict, measure: str) -> dict:
    return {
        "date": e["date"],
        "headline": names.reword_headline(e["headline"]),
        "cause": e["cause"].replace("_", " "),
        "sources": e["sources"],
        "raw": signed_percent(e["raw_return"]),
        "excess": signed_percent(e["excess_return"]),
        "day0": signed_percent(e["day0_raw"]),
        "hit": e["hit"],
        "result": _result_words(e["hit"], measure),
    }


def _era_row(era: dict, name: str, type_plural: str) -> dict:
    return {
        "name": names.ERA_WORDS.get(era["era"], era["era"]),
        "sentence": (
            f"{name} {_claim(era['measure'], era['benchmark'])} in {era['n_hits']} of "
            f"{era['n_episodes']} {type_plural}; normal {percent(era['baseline'])}."
        ),
        "shared": era["n_shared_with_primary"],
        "series": era["series"],
        "weak_signal": era["weak_signal"],
        "lean": names.lean(era["hit_rate"], era["baseline"], era["weak_signal"]),
    }


def _changes(o: OddsJSON, lean: names.Lean, type_plural: str) -> list[str]:
    """Qualitative sentences on what would move this view, each tied to an engine flag."""
    out = []
    if o["weak_signal"]:
        out.append(
            f"Only {o['n_episodes']} past cases. A few more could move this count a lot, "
            "so treat it as a hint, not a pattern."
        )
    elif lean.kind is names.LeanKind.NONE:
        out.append(
            "The count sits close to a normal period, so a couple of new cases could tip it "
            "either way."
        )
    else:
        out.append(
            "Each new case that goes the other way narrows the gap to a normal period. "
            "A run of them would erase it."
        )
    if o["eras_disagree"]:
        out.append(
            "Older data points the other way. If new cases start to look like the older "
            "ones, this view weakens."
        )
    out.append(
        f"A different cause behind the next one. These counts mix every cause of "
        f"{type_plural}, and the causes are listed beside each case below."
    )
    return out


def why_view(o: OddsJSON) -> dict:
    t = names.TYPES[o["type"]]
    h = names.horizon(o["horizon_days"])
    lean = names.lean(o["hit_rate"], o["baseline"], o["weak_signal"])
    name = names.asset_name(o["asset"])
    return {
        "type": o["type"],
        "asset": o["asset"],
        "type_plural": t.plural,
        "asset_name": name,
        "headline": (
            f"{name} {_claim(o['measure'], o['benchmark'])} in {o['n_hits']} of "
            f"{o['n_episodes']} {t.plural}."
        ),
        "normal": f"In a normal {h.period}, {percent(o['baseline'])}.",
        "odds_words": names.odds_words(o["hit_rate"], o["n_episodes"], o["weak_signal"]),
        "n_hits": o["n_hits"],
        "n_episodes": o["n_episodes"],
        "weak_signal": o["weak_signal"],
        "lean": lean,
        "horizon": h.words,
        "benchmark": names.benchmark_name(o["benchmark"]),
        "measure": o["measure"],
        "era": names.ERA_WORDS.get(o["era"], o["era"]),
        "data_start": o["data_start"],
        "data_end": o["data_end"],
        "episodes": [_episode_row(e, o["measure"]) for e in o["episodes"]],
        "other_eras": [_era_row(e, name, t.plural) for e in o["other_eras"]],
        "eras_disagree": o["eras_disagree"],
        "includes_vault": o["includes_vault"],
        "changes": _changes(o, lean, t.plural),
    }


def _stack_levels(xs: Sequence[float]) -> list[int]:
    """Dots closer than one diameter stack upward instead of overlapping."""
    placed: list[tuple[float, int]] = []
    levels = []
    for x in xs:
        taken = {lvl for px, lvl in placed if abs(px - x) < 2 * DOT_R}
        level = next(i for i in range(len(placed) + 1) if i not in taken)
        placed.append((x, level))
        levels.append(level)
    return levels


def strip_geometry(amount: float, episodes: Sequence[dict], rng: PositionRangeJSON) -> dict:
    """Shapes for the what-if strip in SVG units, in money space so the band is the engine's
    own p10..p90 values. Each dot sits at one episode's raw return applied to the amount."""
    moneys = [amount * e["raw_return"] for e in episodes]
    lo = min([*moneys, rng["p10"], 0.0])
    hi = max([*moneys, rng["p90"], 0.0])
    span = (hi - lo) or 1.0
    usable = STRIP_WIDTH - 2 * STRIP_PAD

    def x(v: float) -> float:
        return round(STRIP_PAD + (v - lo) / span * usable, 1)

    xs = [x(v) for v in moneys]
    levels = _stack_levels(xs)
    top = max(levels, default=0)
    height = STRIP_BASE + (top + 1) * (2 * DOT_R + 2) + 8
    base_y = height - STRIP_BASE
    return {
        "width": STRIP_WIDTH,
        "height": height,
        "base_y": base_y,
        "band_x": x(rng["p10"]),
        "band_w": round(x(rng["p90"]) - x(rng["p10"]), 1),
        "median_x": x(rng["median"]),
        "zero_x": x(0.0),
        "r": DOT_R,
        "dots": [
            {
                "cx": cx,
                "cy": round(base_y - DOT_R - 2 - lvl * (2 * DOT_R + 2), 1),
                "label": f"{e['date']}: {signed_percent(e['raw_return'])}",
            }
            for cx, lvl, e in zip(xs, levels, episodes, strict=True)
        ],
    }


def what_if_view(
    o: OddsJSON, rng: PositionRangeJSON, amount: float, currency: str, engine_currency: str
) -> dict:
    t = names.TYPES[o["type"]]
    h = names.horizon(o["horizon_days"])
    return {
        "type": o["type"],
        "asset": o["asset"],
        "asset_name": names.asset_name(o["asset"]),
        "type_plural": t.plural,
        "amount": money(round(amount), currency, signed=False),
        "amount_value": f"{amount:.2f}".rstrip("0").rstrip("."),
        "currency": currency,
        "p10": money(rng["p10"], currency),
        "median": money(rng["median"], currency),
        "p90": money(rng["p90"], currency),
        "n_episodes": rng["n_episodes"],
        "weak_signal": rng["weak_signal"],
        "horizon": h.words,
        "period": h.period,
        "fx_note": currency != engine_currency,
        "engine_currency": engine_currency,
        "normal": (
            f"In a normal {h.period}, {names.asset_name(o['asset'])} "
            f"{_claim(o['measure'], o['benchmark'])} {percent(o['baseline'])} of the time."
        ),
        "strip": strip_geometry(amount, o["episodes"], rng),
    }


def scoreboard_group_view(c: CompareJSON) -> dict:
    t = names.TYPES[c["type"]]
    rows = []
    for a in c["assets"]:
        lean = names.lean(a["hit_rate"], a["baseline"], c["weak_signal"])
        rows.append(
            {
                "asset": a["asset"],
                "name": names.asset_name(a["asset"]),
                "lean": lean,
                "text": (
                    f"{_claim(a['measure'], a['benchmark'])} in {a['n_hits']} of "
                    f"{c['n_episodes']} shared {t.plural}; normal {percent(a['baseline'])}"
                ),
            }
        )
    return {
        "n_episodes": c["n_episodes"],
        "weak_signal": c["weak_signal"],
        "rows": rows,
    }


def scoreboard_view(type: str, groups: Sequence[tuple[str, CompareJSON]]) -> dict:
    t = names.TYPES[type]
    markets = []
    for market, label in names.SCOREBOARD_MARKETS.items():
        mine = [scoreboard_group_view(c) for m, c in groups if m == market]
        if mine:
            markets.append({"label": label, "groups": mine})
    return {
        "type": type,
        "type_plural": t.plural,
        "markets": markets,
    }
