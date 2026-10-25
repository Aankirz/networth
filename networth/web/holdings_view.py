"""A HoldingsReport into what /u/{token}/holdings prints. Every number is a report field,
formatted by networth.holdings.lines; the only arithmetic is the mix bar's geometry."""

from __future__ import annotations

from typing import Final

from networth.holdings import lines
from networth.holdings.model import BUCKETS
from networth.holdings.report import HoldingsReport

NO_HOLDINGS: Final = "Send a screenshot of your holdings in the bot, then confirm it."
BAR_WIDTH: Final = 400
BAR_PAD: Final = 8
BAR_H: Final = 28
ROW_GAP: Final = 70
FIRST_ROW_Y: Final = 30
MIN_LABEL_W: Final = 44  # narrower segments carry no text; the title and the list do


def mix_bar(report: HoldingsReport) -> dict:
    """Two stacked bars on one 0 to 100% scale: the saved plan, then the holdings."""
    usable = BAR_WIDTH - 2 * BAR_PAD
    rows = []
    for i, (name, pcts) in enumerate((("Your plan", report.plan_pct),
                                      ("Your holdings", report.held_pct))):  # fmt: skip
        y, x, segments = FIRST_ROW_Y + i * ROW_GAP, float(BAR_PAD), []
        for bucket, pct in zip(BUCKETS, pcts, strict=True):
            w = round(pct / 100 * usable, 1)
            segments.append({"bucket": bucket.value, "pct": pct, "x": round(x, 1), "w": w,
                             "labelled": w >= MIN_LABEL_W, "mid": round(x + w / 2, 1)})  # fmt: skip
            x += w
        rows.append({"name": name, "label_y": y - 10, "y": y, "h": BAR_H, "segments": segments})
    return {"width": BAR_WIDTH, "height": rows[-1]["y"] + BAR_H + 10, "x": BAR_PAD,
            "rows": rows}  # fmt: skip


def holdings_view(r: HoldingsReport) -> dict:
    c, lang = r.currency, "en"
    rows = [{
        "n": row.n, "name": row.name, "bucket": row.bucket.value, "units": lines.units(row.units),
        "avg_cost": lines.unit_money(row.avg_cost, c), "invested": lines.money(row.invested, c),
        "value": lines.money(row.value, c), "gain": lines.gain(row.gain, c),
        "direction": "up" if row.gain > 0 else "down" if row.gain < 0 else "flat",
        "ret": lines.return_text(row.ret, lang),
        "price": lines.price_text(row.price_from, r.as_of, lang),
    } for row in r.rows]  # fmt: skip
    return {
        "as_of": lines.day(r.as_of, lang), "count": r.count, "rows": rows,
        "invested": lines.money(r.invested, c), "value": lines.money(r.value, c),
        "gain": lines.gain(r.gain, c), "ret": lines.return_text(r.ret, lang),
        "mix": lines.mix_lines(r, lang), "bar": mix_bar(r),
        "bar_title": "Your plan: " + ", ".join(
            f"{p}% {b.value}" for b, p in zip(BUCKETS, r.plan_pct, strict=True)
        ) + ". Your holdings: " + ", ".join(
            f"{p}% {b.value}" for b, p in zip(BUCKETS, r.held_pct, strict=True)) + ".",
        "history": lines.history_lines(r.history, lang),
        "prices": lines.price_lines(r, lang),
        "label": lines.LINES[lang]["label"],
    }  # fmt: skip
