"""The action plan after "That's everything": how the confirmed holdings get to the saved plan.

    reply = plan_reply(store, profile, services, "overview")   # both paths, in money
    reply = plan_reply(store, profile, services, "rebal")      # Path A in full: trims, tax
    reply = plan_reply(store, profile, services, "newmoney")   # Path B: the monthly split
    reply = plan_reply(store, profile, services, "now")        # both paths in full, at once
    reply = plan_reply(store, profile, services, "why")        # why these holdings and funds

The numbers come from networth.holdings.action. Holdings are rated with networth.ratings when
Services carries rating sources; without them trims go deepest loss first.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Final

from networth import holdings
from networth.app.services import Services
from networth.app.store import Profile, Store
from networth.bot.holdings_words import (
    A_HEAD,
    AND,
    B_HEAD,
    BIGGEST_LOSS,
    BUCKET_WORDS,
    DOWN_NOTE,
    EACH_MONTH,
    FUND_KINDS,
    FUNDS,
    GAP_LINE,
    GAP_OVER,
    GAP_UNDER,
    IN_PART,
    INTO,
    MATCHES,
    MONTHS,
    NEW_MONEY,
    NO_VIEW,
    NOW_IS,
    NOW_PART,
    ON_PLAN,
    PATH_A,
    PATH_B,
    PATH_B_NEVER,
    PATH_B_NO_AMOUNT,
    PLAN_HEAD,
    RATED_NOTE,
    REBALANCE,
    SAFE_USD,
    SHOW_NOW,
    TAX_GAIN,
    TAX_LOSS,
    THEN_PUT,
    TRIM_ALL,
    TRIM_FIRST,
    TRIM_SOME,
    VIEW_HEAD,
    VIEW_ROW,
    VIEW_WORDS,
    WHY,
    WHY_INDEX,
    WHY_ORDER,
    WHY_SAFE,
)
from networth.bot.message import Message, say
from networth.bot.onboarding import Reply, plan_name
from networth.bot.telegram import Button, Keyboard
from networth.holdings.action import ActionPlan, Trim, action_plan
from networth.holdings.model import BUCKETS, Bucket, Holdings, Kind, from_json
from networth.holdings.report import HoldingsReport, Row
from networth.money import money
from networth.ratings import Driver, Rating, View, rate

log = logging.getLogger("networth.bot")

TAP: Final = "hd"
ROUND_TO: Final = 100  # plan amounts are "about": the nearest hundred
NAMED: Final = 3  # Path A names this many holdings in the overview
RATED_KINDS: Final = (Kind.STOCK, Kind.ETF, Kind.MUTUAL_FUND)
ACTIONS: Final = ("overview", "rebal", "newmoney", "now", "why")


def _say(table: dict, lang: str, **values: object) -> str:
    return say(table, lang).format(**values)


def _joined(parts: list[str], lang: str) -> str:
    if len(parts) < 2:
        return "".join(parts)
    return ", ".join(parts[:-1]) + say(AND, lang) + parts[-1]


class Words:
    """One plan's money and words in one language and currency."""

    def __init__(self, plan: ActionPlan, lang: str) -> None:
        self.plan, self.lang = plan, lang
        self.funds = FUNDS.get(plan.currency, FUNDS["INR"])
        self.kinds = FUND_KINDS.get(plan.currency, FUND_KINDS["INR"])

    def money(self, n: int, about: bool = True) -> str:
        n = round(n, -2) if about and abs(n) >= 10 * ROUND_TO else n
        return money(abs(n), self.plan.currency, self.lang)

    def bucket(self, b: Bucket) -> str:
        usd = b is Bucket.SAFETY and self.plan.currency == "USD"
        return say(SAFE_USD if usd else BUCKET_WORDS[b], self.lang)

    def into(self, moves: tuple) -> str:
        return _joined([_say(INTO, self.lang, amount=self.money(m.amount),
                             fund=say(self.funds[m.bucket], self.lang))
                       for m in sorted(moves, key=lambda m: -m.amount)], self.lang)  # fmt: skip

    def trimmed(self) -> int:
        return sum(t.amount for t in self.plan.trims)


def _on_plan(w: Words) -> list[str]:
    p, lang = w.plan, w.lang
    parts = [_say(IN_PART, lang, amount=w.money(p.targets[b]), words=w.bucket(b))
             for b in BUCKETS if p.targets[b]]  # fmt: skip
    held = [_say(NOW_PART, lang, pct=round(100 * p.held[b] / p.total), words=w.bucket(b))
            for b in BUCKETS if p.held[b]]  # fmt: skip
    return [_say(ON_PLAN, lang, total=w.money(p.total, about=False), parts=_joined(parts, lang)),
            _say(NOW_IS, lang, parts=_joined(held, lang))]  # fmt: skip


def _path_b_line(w: Words, report: HoldingsReport) -> str:
    p, lang = w.plan, w.lang
    if p.months is not None:
        return _say(PATH_B, lang, monthly=w.money(p.monthly, about=False), months=p.months)
    if p.monthly:
        zero = next(b for b, pct in zip(BUCKETS, report.plan_pct, strict=True)
                    if pct == 0 and p.held[b] > p.targets[b])  # fmt: skip
        return _say(PATH_B_NEVER, lang, words=w.bucket(zero))
    return _say(PATH_B_NO_AMOUNT, lang, currency=p.currency)


def _note(t: Trim, lang: str) -> str:
    if t.view is not None:
        return _say(RATED_NOTE, lang, view=t.view.value)
    cost = t.amount - t.booked
    return _say(DOWN_NOTE, lang, pct=round(-100 * t.booked / cost)) if t.booked < 0 < cost else ""


def _trim_line(n: int, t: Trim, w: Words) -> str:
    note = _note(t, w.lang)
    if t.whole:
        return _say(TRIM_ALL, w.lang, n=n, name=t.name, amount=w.money(t.amount, False), note=note)
    return _say(TRIM_SOME, w.lang, n=n, name=t.name, amount=w.money(t.amount),
                value=w.money(t.value, about=False), note=note)  # fmt: skip


def _tax(w: Words) -> str:
    booked = w.plan.booked
    if booked > 0:
        return _say(TAX_GAIN, w.lang, amount=w.money(booked))
    if booked == 0:
        return ""
    worst = min(w.plan.trims, key=lambda t: t.booked)
    biggest = _say(BIGGEST_LOSS, w.lang, name=worst.name, amount=w.money(-worst.booked, False))
    return _say(TAX_LOSS, w.lang, amount=w.money(-booked), biggest=biggest)


def _path_a(w: Words) -> list[str]:
    trims = "\n".join(
        [
            say(TRIM_FIRST, w.lang),
            *(_trim_line(n, t, w) for n, t in enumerate(w.plan.trims, start=1)),
        ]
    )
    then = _say(THEN_PUT, w.lang, into=w.into(w.plan.moves))
    return [x for x in (trims, then, _tax(w)) if x]


def _path_b(w: Words, report: HoldingsReport) -> list[str]:
    p = w.plan
    if p.months is None:
        return [_path_b_line(w, report)]
    return [
        _say(EACH_MONTH, w.lang, into=w.into(p.split)),
        _say(MONTHS, w.lang, monthly=w.money(p.monthly, about=False), months=p.months),
    ]


def _button(table: dict, action: str, lang: str) -> Button:
    return Button(say(table, lang), f"{TAP}:{action}")


def _overview(w: Words, report: HoldingsReport, name: str) -> Reply:
    lang, p = w.lang, w.plan
    names = _joined([t.name for t in p.trims[:NAMED]], lang)
    path_a = _say(PATH_A, lang, amount=w.money(w.trimmed()), names=names, into=w.into(p.moves))
    body = (*_on_plan(w), path_a, _path_b_line(w, report))
    keys: Keyboard = ((_button(REBALANCE, "rebal", lang), _button(NEW_MONEY, "newmoney", lang)),
                      (_button(WHY, "why", lang),))  # fmt: skip
    return Reply(Message(_say(PLAN_HEAD, lang, name=name), body), keys)


def _why(w: Words) -> list[str]:
    return [say(WHY_ORDER, w.lang), _say(WHY_INDEX, w.lang, fund=say(w.kinds[Bucket.CORE], w.lang)),
            _say(WHY_SAFE, w.lang, fund=say(w.kinds[Bucket.SAFETY], w.lang))]  # fmt: skip


def _detail(action: str, w: Words, report: HoldingsReport, name: str) -> Reply:
    lang = w.lang
    why = (_button(WHY, "why", lang),)
    if action == "rebal":
        return Reply(Message(say(A_HEAD, lang), tuple(_path_a(w))),
                     ((_button(NEW_MONEY, "newmoney", lang), *why),))  # fmt: skip
    if action == "newmoney":
        return Reply(Message(say(B_HEAD, lang), tuple(_path_b(w, report))),
                     ((_button(SHOW_NOW, "now", lang), *why),))  # fmt: skip
    if action == "now":
        body = (say(A_HEAD, lang), *_path_a(w), say(B_HEAD, lang), *_path_b(w, report))
        return Reply(Message(_say(PLAN_HEAD, lang, name=name), body), (why,))
    return Reply(
        Message(say(WHY, lang), tuple(_why(w))),
        ((_button(REBALANCE, "rebal", lang), _button(NEW_MONEY, "newmoney", lang)),),
    )


Rater = Callable[[str], Rating | None]
WEAKEST_FIRST: Final = (View.AVOID, View.WEAK, View.NEUTRAL, View.POSITIVE, View.STRONG)


def _rater(services: Services) -> Rater | None:
    sources = services.ratings
    if sources is None:
        return None

    def rating(query: str) -> Rating | None:
        try:
            return rate(query, sources=sources)
        except Exception:  # a holding the rating sources can't find is shown without a view
            log.info("no rating for a holding", exc_info=True)
            return None

    return rating


def _ratings(h: Holdings, services: Services) -> dict[str, Rating]:
    rater = _rater(services)
    if rater is None:
        return {}
    found = {x.name: rater(x.identifier or x.name) for x in h.items if x.kind in RATED_KINDS}
    return {name: r for name, r in found.items() if r is not None}


def _monthly(profile: Profile, currency: str) -> int | None:
    """The monthly amount, only when it is in the same money as the holdings."""
    return profile.monthly_amount if (profile.currency or "INR") == currency else None


def plan_reply(store: Store, profile: Profile, services: Services, action: str) -> Reply | None:
    """None without a confirmed list or a saved plan."""
    report = holdings.report_for(profile.user_id, store, history=False)
    data, saved = store.holdings_data(profile.user_id), store.get_plan(profile.user_id)
    if report is None or data is None or saved is None:
        return None
    lang = profile.lang or "en"
    views = {name: r.view for name, r in _ratings(from_json(data), services).items()}
    plan = action_plan(report, _monthly(profile, report.currency), views)
    if plan.on_plan:
        return Reply(say(MATCHES, lang))
    w, name = Words(plan, lang), plan_name(saved, lang)
    return _overview(w, report, name) if action == "overview" else _detail(action, w, report, name)


def _top(r: Rating) -> Driver | None:
    """The driver that moved the score most: its weight times its distance from the middle."""
    return max(r.drivers, key=lambda d: d.weight * abs(d.score - 50), default=None)


def _view_row(name: str, r: Rating | None, lang: str) -> str:
    top = _top(r) if r is not None else None
    if r is None or top is None:
        return _say(NO_VIEW, lang, name=name)
    return _say(
        VIEW_ROW,
        lang,
        name=name,
        view=say(VIEW_WORDS[r.view.value], lang),
        points=r.score,
        label=top.label,
        value=top.value,
        source=top.source.name,
    )


def _gap_line(w: Words, name: str) -> str:
    p, lang = w.plan, w.lang
    parts = [_say(GAP_OVER if p.held[b] > p.targets[b] else GAP_UNDER, lang,
                  amount=w.money(abs(p.held[b] - p.targets[b])), words=w.bucket(b))
             for b in BUCKETS if abs(p.held[b] - p.targets[b]) >= ROUND_TO]  # fmt: skip
    return (
        _say(GAP_LINE, lang, name=name, parts=_joined(parts, lang)) if parts else say(MATCHES, lang)
    )


def view_answer(store: Store, profile: Profile, services: Services,
                lang: str) -> tuple[str, Keyboard] | None:  # fmt: skip
    """Networth's view on each holding, weakest first, then the plan gap in money, with the
    action plan's buttons. None without a confirmed list or a saved plan."""
    report = holdings.report_for(profile.user_id, store, history=False)
    data, saved = store.holdings_data(profile.user_id), store.get_plan(profile.user_id)
    if report is None or data is None or saved is None:
        return None
    rated = _ratings(from_json(data), services)

    def order(row: Row) -> tuple[int, int]:
        r = rated.get(row.name)
        return (WEAKEST_FIRST.index(r.view), r.score) if r else (len(WEAKEST_FIRST), 0)

    rows = [
        _view_row(row.name, rated.get(row.name), lang) for row in sorted(report.rows, key=order)
    ]
    plan = action_plan(report, _monthly(profile, report.currency))
    gap = _gap_line(Words(plan, lang), plan_name(saved, lang))
    keys: Keyboard = ((_button(REBALANCE, "rebal", lang), _button(NEW_MONEY, "newmoney", lang)),
                      (_button(WHY, "why", lang),))  # fmt: skip
    return "\n".join([say(VIEW_HEAD, lang), *rows, gap]), keys
