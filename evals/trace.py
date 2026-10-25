"""Number trace: 20 messages (a brief and a why answer for 10 event types), each number in the
sent text mapped back to the engine field, event date or profile field it came from.

    raw = run(services)       # paid: the writer words each why answer through the guard
    scores = score(raw)       # offline: every number mapped, or listed as unmapped

A brief is brief.compose() over an Event whose odds are odds(type, asset) for the type's
configured assets, in the reader's language, written by code as bot.briefs.compose_reply
writes it (no model, so used is "template"). A why answer is today.type_history() through
deliver(). Fields are the values the message was built from, each read through guard.numbers
so "56%" and "₹1,00,000" normalise the same way.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Final

from evals import spend
from evals.words import NOW, PLAN, USER
from networth import brief, guard
from networth.app.services import Services
from networth.bot.message import plain
from networth.bot.onboarding import format_money, plan_line
from networth.chat.answer import deliver
from networth.chat.today import type_history
from networth.engine import odds as engine
from networth.web import names
from networth.web.fmt import percent

TYPES: Final = ("rbi_hike", "rbi_cut", "union_budget", "inr_shock", "fed_hike", "fed_cut",
                "tariff", "oil_supply", "bank_stress", "military_conflict")  # fmt: skip
LANGS: Final = ("en",) * 5 + ("hinglish",) * 3 + ("hi",) * 2
EVENT_DATE: Final = dt.date(2026, 10, 20)
TODAY: Final = NOW.date()


def _odds_fields(prefix: str, row: Mapping) -> list[dict]:
    return [{"path": f"{prefix}.n_hits", "kind": "engine", "value": str(row["n_hits"])},
            {"path": f"{prefix}.n_episodes", "kind": "engine",
             "value": str(row.get("n_episodes", row.get("n_episodes_all")))},
            {"path": f"{prefix}.baseline", "kind": "engine",
             "value": percent(row["baseline"])}]  # fmt: skip


def engine_fields(type: str, assets: Sequence[str], rates_db) -> tuple[list[engine.OddsJSON],
                                                                        list[dict]]:  # fmt: skip
    """Every odds() row for the type's assets, and every compare() row the scoreboard reads."""
    rows, fields = [], []
    for asset in assets:
        try:
            o = engine.odds(type, asset, db=rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        rows.append(o)
        fields += _odds_fields(f"odds({type},{asset})", o)
    for market in USER.markets:
        group = names.SCOREBOARD_GROUPS[market][0]
        try:
            c = engine.compare(type, group, db=rates_db)
        except (engine.NoBaseRate, ValueError):
            continue
        fields.append({"path": f"compare({type}).n_episodes", "kind": "engine",
                       "value": str(c["n_episodes"])})  # fmt: skip
        for a in c["assets"]:
            fields += [f for f in _odds_fields(f"compare({type},{a['asset']})", a)
                       if not f["path"].endswith("n_episodes")]  # fmt: skip
    return rows, fields


def name_fields() -> list[dict]:
    """Asset and benchmark names: "Nifty 50" and "S&P 500" hold numbers that are not figures."""
    return [{"path": f"name:{name}", "kind": "name", "value": name}
            for name in {*names.ASSETS.values(), *names.BENCHMARK_WORDS.values()}
            if guard.numbers(name)]  # fmt: skip


def profile_fields() -> list[dict]:
    return [*name_fields(), {"path": "profile.monthly_amount", "kind": "profile",
             "value": format_money(USER.monthly_amount, USER.currency)},
            {"path": "profile.plan", "kind": "profile", "value": plan_line(PLAN)},
            {"path": "brief.today", "kind": "profile", "value": f"{TODAY:%b} {TODAY.day}"},
            {"path": "event.event_date", "kind": "event",
             "value": f"{EVENT_DATE:%b} {EVENT_DATE.day}"}]  # fmt: skip


def one_brief(type: str, lang: str, services: Services) -> dict:
    assets = services.cfg.triggers.assets_by_type[type]
    rows, fields = engine_fields(type, assets, services.rates_db)
    event = brief.Event(type, EVENT_DATE, names.TYPES[type].title, tuple(rows))
    draft = brief.compose([event], USER, PLAN, services.rates_db, NOW)
    text = plain(draft.message(lang))
    return {"kind": "brief", "type": type, "lang": lang, "text": text, "used": "template",
            "template": text, "fields": fields + profile_fields()}  # fmt: skip


def one_why(type: str, lang: str, services: Services) -> dict:
    assets = services.cfg.triggers.assets_by_type[type]
    _, fields = engine_fields(type, assets, services.rates_db)
    answer = type_history(type, USER, services)
    if answer is None:
        return {"kind": "why", "type": type, "lang": lang, "error": "no history line"}
    spend.check()
    start = len(spend.rows(services.guard_log))
    reply = deliver(answer, lang, services)
    verdicts = spend.rows(services.guard_log)[start:]
    return {"kind": "why", "type": type, "lang": lang, "text": reply.text,
            "used": verdicts[-1]["attempt"] if verdicts else "fixed",
            "template": answer.template, "fields": fields + name_fields()}  # fmt: skip


def run(services: Services) -> dict:
    start = len(spend.rows())
    msgs = [f(t, lang, services) for f in (one_brief, one_why)
            for t, lang in zip(TYPES, LANGS, strict=True)]  # fmt: skip
    calls = spend.since(start)
    return {"run_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "messages": msgs,
            "cost_usd": round(sum(c["cost_usd"] or 0 for c in calls), 4)}  # fmt: skip


def mapping(msg: Mapping) -> list[dict]:
    """Each number in the sent text with the first field whose value holds it, engine first."""
    order = {"engine": 0, "event": 1, "profile": 2, "name": 3}
    fields = sorted(msg["fields"], key=lambda f: order[f["kind"]])
    out = []
    for n in sorted(guard.numbers(msg["text"])):
        hit = next((f for f in fields if n in guard.numbers(f["value"])), None)
        out.append({"number": n, "path": hit["path"] if hit else None,
                    "kind": hit["kind"] if hit else None})  # fmt: skip
    return out


def shown(mapped: Sequence[Mapping]) -> list[Mapping]:
    """An English brief, a Hindi brief and a Hinglish why answer: one of each surface."""
    picks = (("brief", "en"), ("brief", "hi"), ("why", "hinglish"))
    return [m for kind, lang in picks
            for m in [next((x for x in mapped if (x["kind"], x["lang"]) == (kind, lang)), None)]
            if m is not None]  # fmt: skip


def score(raw: Mapping) -> dict:
    msgs = [m for m in raw["messages"] if "error" not in m]
    mapped = [{**m, "mapping": mapping(m)} for m in msgs]
    numbers = [x for m in mapped for x in m["mapping"]]
    figures = [x for x in numbers if x["kind"] != "name"]  # a name's digits are not a figure
    unmapped = [{"type": m["type"], "kind": m["kind"], "lang": m["lang"], "number": x["number"],
                 "text": m["text"]}
                for m in mapped for x in m["mapping"] if x["path"] is None]  # fmt: skip
    return {"messages": len(raw["messages"]), "errors": len(raw["messages"]) - len(msgs),
            "numbers": len(numbers), "unmapped": unmapped,
            "engine": sum(x["kind"] == "engine" for x in numbers),
            "event": sum(x["kind"] == "event" for x in numbers),
            "profile": sum(x["kind"] == "profile" for x in numbers),
            "name": sum(x["kind"] == "name" for x in numbers),
            "figures": len(figures),
            "trace_rate": round(1 - len(unmapped) / len(figures), 4) if figures else None,
            "messages_fully_traced": sum(all(x["path"] for x in m["mapping"]) for m in mapped),
            "used": {u: sum(m["used"] == u for m in msgs) for u in {m["used"] for m in msgs}},
            "shown": [{k: m[k] for k in ("kind", "type", "lang", "text", "mapping")}
                      for m in shown(mapped)],
            "cost_usd": raw["cost_usd"]}  # fmt: skip
