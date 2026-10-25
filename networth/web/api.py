"""The JSON API behind the Next.js site: one user's dashboard and a chat that answers exactly as
Telegram does. docs/phases/phase-8-contract.md is the contract; site/lib/contract.ts mirrors it.

    GET  /api/u/{token}/dashboard     POST /api/u/{token}/chat   {"text": "...", "lang"?: "hi"}
    GET  /api/demo/dashboard          POST /api/demo/chat
    POST /api/u/{token}/command       POST /api/demo/command   {"name": "brief", "lang"?: "hi"}
    GET  /api/track-record
    GET  /api/web/me                  POST /api/web/link   {"code": "123456"}
    POST /api/web/forget              GET  /api/web/dashboard
    POST /api/web/chat                POST /api/web/command

The /api/web routes are for a visitor signed in with Google on the site. Each needs the site's
short-lived signed token (networth.web.session) and answers 401 without one. A Google account
reaches a user only after a /weblink code from the bot ties the two together.

A command answers with the message Telegram sends for the same slash command, built by the bot's
own entry points, and never changes the profile: /plan shows the plan without asking to edit it.

A chat turn runs chat.respond_traced, the Telegram pipeline with its guard, then attaches a card
built only from data the server computed: the intent picks the builder from CARDS. Every turn and
command appends one line to data/web_turns.jsonl (trace id, hashed user id, intent, guard
verdict, cost), never the text or the token.

    uv run python -m networth.web.api reset-demo    # put the sample profile back as it started
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import functools
import hashlib
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Final, Literal, get_args
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from networth import brief, chat, holdings, sim
from networth.app import links
from networth.app.services import Services
from networth.app.settings import Settings
from networth.app.store import Plan, Profile, Status, Step, Store, now_iso
from networth.bot import briefs
from networth.bot import holdings as holdings_flow
from networth.bot.commands import FINISH_FIRST, PLAN_TITLE, TOO_MANY, TRY_AGAIN, help_message
from networth.bot.message import LANGS, Link, Message, plain, say
from networth.bot.onboarding import (
    BUCKETS,
    STARTER_PLANS,
    Reply,
    brief_offer,
    ordinal,
    plan_line,
    with_lead,
)
from networth.bot.onboarding import prompt as ask_for
from networth.brief.lines import Line, day_words, odds_line
from networth.chat.answer import deliver
from networth.engine import odds as engine
from networth.keiki.turn import TURN_LOCK, cost_between
from networth.money import money
from networth.sim.data import Table
from networth.watcher.store import Confirmed
from networth.watcher.store import Store as WatcherStore
from networth.web import holdings_view, plan_view, routes, session
from networth.web.fmt import percent, western_grouping
from networth.web.names import TYPES, asset_name, why_path
from networth.web.routes import BAD_LINK, rates_db, settings, sim_table
from networth.web.routes import router as pages

log = logging.getLogger("networth.web.api")
router = APIRouter(prefix="/api")

MAX_TEXT: Final = 4096  # Telegram's own message limit, so the web takes what the bot takes
DEMO_USER: Final = "web:demo"
DEMO_AMOUNT: Final = 150_000
DEMO_PLAN: Final = "balanced"
DEMO_PER_IP_HOUR: Final = 8
DEMO_ALL_HOUR: Final = 120  # every demo visitor together; the real cap on model spend
HOUR_S: Final = 3600
ORIGINS_ENV: Final = "NETWORTH_WEB_ORIGINS"
VISITOR_HEADER: Final = "X-Networth-Visitor"
TURN_LOG: Final = "web_turns.jsonl"
TOKEN_IN_PATH: Final = re.compile(r"(/u/)[^/?\s]+")
TOO_LONG: Final = {
    "en": "That's longer than one message can be. A shorter piece works.",
    "hi": "यह एक संदेश की सीमा से लंबा है। छोटा हिस्सा भेज सकते हैं।",
    "hinglish": "Yeh ek message ki limit se lamba hai. Chhota hissa bhej sakte hain.",
}
NO_NEWS_YET: Final = {
    "en": "No confirmed story matched our history this month.",
    "hi": "इस महीने कोई पुष्ट ख़बर हमारे इतिहास से मेल नहीं खाई।",
    "hinglish": "Is mahine koi confirmed story hamari history se match nahin hui.",
}
NO_COUNTS: Final = {
    "en": "History counts appear here when a confirmed story matches a past event.",
    "hi": "जब कोई पुष्ट ख़बर किसी पुरानी घटना से मेल खाती है, तब इतिहास की गिनती यहाँ दिखती है।",
    "hinglish": "Jab koi confirmed story kisi purani ghatna se match hoti hai, tab history ki "
    "ginti yahan dikhti hai.",
}
NO_PLAN_YET: Final = {
    "en": "No saved plan yet.",
    "hi": "अभी कोई सेव किया प्लान नहीं है।",
    "hinglish": "Abhi koi saved plan nahin hai.",
}


class RedactTokens(logging.Filter):
    """Access log lines keep the route and drop the token: /u/<token> becomes /u/…"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(TOKEN_IN_PATH.sub(r"\1…", a) if isinstance(a, str) else a
                                for a in record.args)  # fmt: skip
        return True


logging.getLogger("uvicorn.access").addFilter(RedactTokens())


# Origins ------------------------------------------------------------------------------------


def allowed_origins() -> tuple[str, ...]:
    """NETWORTH_WEB_ORIGINS: comma-separated origins, each may hold one * for preview hosts,
    such as https://networth-*-aankirz.vercel.app. A bare * is ignored, never allow-all."""
    raw = os.environ.get(ORIGINS_ENV, "")
    return tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip() not in ("", "*"))


def origin_ok(origin: str, allowed: tuple[str, ...]) -> bool:
    parsed = urlparse(origin)
    if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1"):
        return False
    return any(fnmatch.fnmatchcase(origin, pattern) for pattern in allowed)


def check_origin(request: Request) -> None:
    """No Origin is the site's server talking to us; a browser Origin must be one of ours."""
    origin = request.headers.get("origin")
    if origin is not None and not origin_ok(origin, allowed_origins()):
        raise HTTPException(403, "forbidden_origin")


def cors(response: Response, request: Request) -> Response:
    origin = request.headers.get("origin")
    if origin is not None:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


@router.options("/{path:path}", include_in_schema=False)
def preflight(request: Request, path: str) -> Response:
    check_origin(request)
    response = Response(status_code=204)
    response.headers["Access-Control-Allow-Methods"] = "GET, POST"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Max-Age"] = "600"
    return cors(response, request)


# Who is asking ------------------------------------------------------------------------------


@functools.cache
def _services() -> Services:
    return Services.from_settings(settings())


def api_services() -> Services:
    """The bot's services without the link secret: a plan question on the web never mints a new
    page token, which would revoke the link the user is reading this on."""
    return replace(_services(), link_secret=None)


Svc = Annotated[Services, Depends(api_services)]
Config = Annotated[Settings, Depends(settings)]
SimTable = Annotated[Table | None, Depends(sim_table)]


@dataclass(frozen=True)
class Asker:
    store: Store
    profile: Profile
    sample: bool


def user_by_token(token: str, cfg: Settings) -> Asker:
    """The one user this signed token names; any other token is the same 404 as /u."""
    link_token = links.verify(token, cfg.link_secret, dt.datetime.now(dt.UTC)) if (
        cfg.link_secret) else None  # fmt: skip
    store = Store(cfg.data_dir)
    profile = store.profile_by_token(link_token) if link_token else None
    if profile is None or profile.user_id == DEMO_USER:
        raise HTTPException(404, "not_found")
    return Asker(store, profile, sample=False)


def demo_profile(now: str) -> tuple[Profile, Plan]:
    """The sample: Balanced, ₹1,50,000 a month, English. Paused, so no brief, alert or watch
    hit is ever sent for it."""
    profile = Profile(
        DEMO_USER, "web", 0, Step.DONE, "", now, now, status=Status.PAUSED, lang="en",
        invest_day=1, alerts_on=False, goal="wealth", horizon_years=10, drop_comfort=20,
        monthly_amount=DEMO_AMOUNT, currency="INR", exclude=("crypto", "us_stocks"),
    )  # fmt: skip
    targets = dict(zip(BUCKETS, STARTER_PLANS[DEMO_PLAN][1], strict=True))
    return profile, Plan(DEMO_USER, DEMO_PLAN, targets, 20, now)


def reset_demo(store: Store) -> None:
    """Idempotent: the sample profile and plan as they started, its watches stopped."""
    profile, plan = demo_profile(now_iso())
    store.save_profile(profile)
    store.save_plan(plan)
    for watch in store.active_watches(DEMO_USER):
        store.stop_watch(DEMO_USER, watch.id)


def demo_user(cfg: Settings) -> Asker:
    store = Store(cfg.data_dir)
    profile = store.get_profile(DEMO_USER)
    if profile is None:
        reset_demo(store)
        profile = store.get_profile(DEMO_USER)
    assert profile is not None, "reset_demo saved the sample"
    return Asker(store, profile, sample=True)


# Cards: only fields the server computed -----------------------------------------------------


def message_json(m: Message) -> dict:
    body = [{"kind": "text", "text": b} if isinstance(b, str) else
            {"kind": "link", "label": b.label, "url": b.url} for b in m.body]  # fmt: skip
    return {"title": m.title, "body": body, "detail": list(m.detail), "footer": m.footer,
            "preview": m.preview}  # fmt: skip


def history_row(line: Line, lang: str, public_url: str | None) -> dict:
    path = why_path(line.type, line.asset)
    return {
        "type": line.type, "asset": line.asset, "asset_name": asset_name(line.asset),
        "sentence": line.words(lang), "count": f"{line.hits} of {line.n}",
        "rate": percent(line.hit_rate), "normal": percent(line.baseline),
        "weak": line.weak, "near_normal": line.near_normal,
        "bar": {"hit": round(line.hit_rate * 100, 1), "normal": round(line.baseline * 100, 1)},
        "why_url": f"{public_url}{path}" if public_url else None,
    }  # fmt: skip


def plan_range_json(v: dict) -> dict:
    bar = v["bar"]
    rows = [{"series": r["series"], "name": r["name"], "x": r["x"], "w": r["w"],
             "median_x": r["median_x"],
             "cases": [{"name": n, "value": value} for n, value in r["cases"]]}
            for r in bar["rows"]]  # fmt: skip
    keep = (
        "plan",
        "monthly",
        "years",
        "invested",
        "nominal",
        "real",
        "fall_limit",
        "hit_limit",
        "worst_fall_pct",
        "worst_fall_rupees",
        "recovery",
        "paths",
        "window",
        "label",
    )
    return {**{k: v[k] for k in keep}, "bar": {
        "rows": rows, "invested_x": bar["invested_x"], "invested_name": bar["invested_name"],
        "zero_label": bar["zero_label"]}}  # fmt: skip


def plan_range_card(store: Store, profile: Profile, table: Table | None) -> dict:
    plan = store.get_plan(profile.user_id)
    if plan is None:
        return {"type": "plan_range", "range": None, "note": say(NO_PLAN_YET, profile.lang)}
    if table is None:
        return {"type": "plan_range", "range": None, "note": plan_view.NO_TABLE}
    try:
        r = sim.plan_range(plan, profile, table=table)
    except sim.NotRupees:
        return {"type": "plan_range", "range": None, "note": plan_view.RUPEES_ONLY}
    return {"type": "plan_range", "range": plan_range_json(
        plan_view.plan_range_view(r, plan_line(plan))), "note": None}  # fmt: skip


def holdings_card(store: Store, profile: Profile, table: Table | None) -> dict | None:
    report = holdings.report_for(profile.user_id, store, table=table)
    if report is None:
        return None
    v = holdings_view.holdings_view(report)
    rows = [{k: r[k] for k in ("name", "bucket", "units", "value", "gain", "direction", "ret")}
            for r in v["rows"]]  # fmt: skip
    bar = {"width": v["bar"]["width"], "rows": [
        {"name": r["name"], "segments": [{"bucket": s["bucket"], "pct": f"{s['pct']}%",
                                          "x": s["x"], "w": s["w"]} for s in r["segments"]]}
        for r in v["bar"]["rows"]]}  # fmt: skip
    return {"type": "holdings", "as_of": v["as_of"], "count": v["count"], "rows": rows,
            "invested": v["invested"], "value": v["value"], "gain": v["gain"], "ret": v["ret"],
            "mix": v["mix"], "bar": bar, "bar_title": v["bar_title"], "history": v["history"],
            "label": v["label"]}  # fmt: skip


def today_stories(services: Services, now: dt.datetime, lang: str | None = None) -> list[dict]:
    """The confirmed stories today.what_happened words: pulled in the 24 hours before the last
    news check, in the same order. Each carries the day the story was first seen."""
    if not services.watcher_db.exists():
        return []
    ws = WatcherStore.open(services.watcher_db)
    try:
        cycle = ws.latest_cycle()
        anchor = min(now, cycle.finished_at) if cycle else now
        fresh = {s.id for s in ws.stories_pulled_since(anchor - chat.today.DAY)}
        decided = [d for d in ws.decisions() if d.story.id in fresh]
    finally:
        ws.close()
    return [
        {
            "title": d.story.title.rstrip("."),
            "day": day_words(d.story.first_seen.date(), lang),
            "publishers": list(d.verdict.publishers),
        }
        for d in decided
        if isinstance(d.verdict, Confirmed)
    ][: chat.today.MAX_STORIES]


WHY_LINK: Final = re.compile(r"/why/([a-z_]+)/([^/?#]+)$")


def why_card(reply: Message, profile: Profile, services: Services, lang: str) -> dict:
    """The counts behind the one /why link the answer carries, read back from odds()."""
    url = next((b.url for b in reply.body if isinstance(b, Link)), "")
    m = WHY_LINK.search(url)
    if m is None:
        return {"type": "text"}
    try:
        row = engine.odds(m.group(1), unquote(m.group(2)), db=services.rates_db)
    except (engine.NoBaseRate, ValueError):
        return {"type": "text"}
    line = odds_line(m.group(1), row, row["n_episodes"], row["weak_signal"])
    return {"type": "history", "rows": [history_row(line, lang, services.public_url)],
            "note": None}  # fmt: skip


@dataclass(frozen=True)
class TurnFacts:
    asker: Asker
    reply: Message
    lang: str
    services: Services
    table: Table | None
    now: dt.datetime


CardBuilder = Callable[[TurnFacts], dict]
CARDS: Final[Mapping[chat.Intent, CardBuilder]] = {
    chat.Intent.WHAT_HAPPENED_TODAY: lambda f: {
        "type": "news",
        "items": today_stories(f.services, f.now, f.lang),
        "note": None,
    },
    chat.Intent.WHY: lambda f: why_card(f.reply, f.asker.profile, f.services, f.lang),
    chat.Intent.PLAN_RANGE: lambda f: plan_range_card(f.asker.store, f.asker.profile, f.table),
    chat.Intent.HOLDINGS: lambda f: (
        holdings_card(f.asker.store, f.asker.profile, f.table) or {"type": "text"}
    ),
}  # every other intent is a text card: the message itself


def card_for(intent: chat.Intent, facts: TurnFacts) -> dict:
    build = CARDS.get(intent)
    return build(facts) if build else {"type": "text"}


# Dashboard ----------------------------------------------------------------------------------


def month_brief(store: Store, profile: Profile, services: Services,
                now: dt.datetime) -> brief.Brief:  # fmt: skip
    """This month's events and history lines for the profile, as the dashboard shows them."""
    plan = store.get_plan(profile.user_id)
    today = now.astimezone(ZoneInfo(profile.tz)).date()
    events = brief.month_events(services.watcher_db, today)
    return brief.compose(events, profile, plan, services.rates_db,
                         dt.datetime.combine(today, dt.time()))  # fmt: skip


def history_card(drafted: brief.Brief, lang: str, services: Services) -> dict:
    rows = [history_row(line, lang, services.public_url) for line in drafted.lines]
    return {"type": "history", "rows": rows, "note": None if rows else say(NO_COUNTS, lang)}


MentionKind = Literal["news", "story", "history", "plan", "range", "holdings", "holding"]


def mention(id: str, kind: MentionKind, label: str, text: str) -> dict:
    return {"id": id, "kind": kind, "label": label, "text": text}


def mentions(news: list[dict], history: list[dict], holdings: dict | None) -> list[dict]:
    """What @ can point at. Each text is a plain question the chat pipeline already routes, so
    the answer stays the server's. English on purpose: chat.reply_lang still answers an English
    question in the profile's own language."""
    rows = holdings["rows"] if holdings else []
    return [
        mention("news", "news", "news", "What happened today?"),
        *(mention(f"story:{i}", "story", n["title"], f"Why does this story matter: {n['title']}?")
          for i, n in enumerate(news)),
        *(mention(f"history:{h['type']}:{h['asset']}", "history",
                  f"{TYPES[h['type']].title}, {h['asset_name']}",
                  f"Why? What history counted for {TYPES[h['type']].title} and {h['asset_name']}")
          for h in history),
        mention("plan", "plan", "plan", "What is my plan?"),
        mention("range", "range", "range", "What could my plan become?"),
        mention("holdings", "holdings", "holdings", "How are my holdings doing?"),
        *(mention(f"holding:{i}", "holding", r["name"],
                  f"How are my holdings doing? About {r['name']}") for i, r in enumerate(rows)),
    ]  # fmt: skip


def dashboard(asker: Asker, services: Services, table: Table | None, now: dt.datetime) -> dict:
    store, profile = asker.store, asker.profile
    lang = profile.lang if profile.lang in LANGS else "en"
    plan = store.get_plan(profile.user_id)
    drafted = month_brief(store, profile, services, now)
    news = [{"title": e.title.rstrip("."), "day": day_words(e.event_date, lang),
             "publishers": []} for e in drafted.events]  # fmt: skip
    history = history_card(drafted, lang, services)
    held = holdings_card(store, profile, table)
    return {
        "sample": asker.sample, "lang": lang,
        "profile": {"plan": plan_line(plan, lang) if plan else None,
                    "money": money(profile.monthly_amount or 0, profile.currency, lang),
                    "day": ordinal(profile.invest_day) if profile.invest_day else None},
        "news": {"type": "news", "items": news, "note": None if news else say(NO_NEWS_YET, lang)},
        "history": history,
        "plan_range": plan_range_card(store, profile, table),
        "holdings": held,
        "mentions": mentions(news, history["rows"], held),
        "footer": "",
    }  # fmt: skip


# Chat ---------------------------------------------------------------------------------------


class ChatIn(BaseModel):
    text: str = Field(min_length=1)
    lang: str | None = None
    forwarded: bool = False


def error(status: int, code: str, words: Mapping[str, str], lang: str | None,
          request: Request) -> Response:  # fmt: skip
    body = {"error": code, "message": message_json(Message(body=(say(words, lang),)))}
    return cors(JSONResponse(body, status_code=status), request)


class Window:
    """At most cap hits per key in the last hour, in memory. ponytail: per process, so a
    restart forgets it; the store-backed demo cap still holds across restarts."""

    def __init__(self, cap: int) -> None:
        self.cap, self.hits, self.lock = cap, dict[str, deque[float]](), threading.Lock()

    def claim(self, key: str, now: float) -> bool:
        with self.lock:
            q = self.hits.setdefault(key, deque())
            while q and q[0] <= now - HOUR_S:
                q.popleft()
            if len(q) >= self.cap:
                return False
            q.append(now)
            return True


DEMO_WINDOW: Final = Window(DEMO_PER_IP_HOUR)


def visitor(request: Request) -> str:
    """The site forwards its visitor's address; a direct caller is keyed by its own."""
    forwarded = request.headers.get(VISITOR_HEADER) or request.headers.get("x-forwarded-for")
    first = (forwarded or "").split(",")[0].strip()
    return first or (request.client.host if request.client else "unknown")


def claim_turn(asker: Asker, services: Services, request: Request, now: dt.datetime) -> bool:
    """The same hourly cap Telegram uses for a real user; the demo adds a per-visitor cap."""
    if asker.sample:
        return DEMO_WINDOW.claim(visitor(request), time.time()) and asker.store.claim_answer(
            DEMO_USER, now, DEMO_ALL_HOUR
        )
    cfg = services.cfg
    return cfg is None or asker.store.claim_answer(asker.profile.user_id, now,
                                                   cfg.product.chat_max_per_hour)  # fmt: skip


def hashed(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def log_turn(services: Services, row: dict) -> None:
    try:
        path = services.data_dir / TURN_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        log.exception("web turn %s not logged", row.get("trace_id"))


def run_turn(asker: Asker, body: ChatIn, services: Services, table: Table | None) -> dict:
    """One answer through the Telegram pipeline, its card, and one log line."""
    now = dt.datetime.now(dt.UTC)
    trace_id = uuid.uuid4().hex
    profile = replace(asker.profile, lang=body.lang) if body.lang in LANGS else asker.profile
    with TURN_LOCK:  # cost is read from the call log by time window, so turns never overlap
        start, outcome = dt.datetime.now(dt.UTC), "completed"
        try:
            reply, intent, used = chat.respond_traced(asker.store, profile, body.text,
                                                      body.forwarded, services, now)  # fmt: skip
        except Exception:
            log.exception("web turn %s failed", trace_id)
            reply, intent, used, outcome = None, None, None, "failed"
        cost = cost_between(services.call_log, start, dt.datetime.now(dt.UTC))
    log_turn(services, {
        "ts": now.isoformat(timespec="seconds"), "trace_id": trace_id,
        "user_id": hashed(profile.user_id), "channel": "demo" if asker.sample else "web",
        "intent": intent.value if intent else None, "guard": used, "cost_usd": cost,
        "outcome": outcome,
    })  # fmt: skip
    if reply is None or intent is None:
        raise TurnFailed(trace_id)
    message = reply.message
    assert isinstance(message, Message), "Reply wraps a plain string in a Message"
    lang = chat.reply_lang(body.text, profile)
    if not asker.sample:
        asker.store.log_message(profile.user_id, "in", body.text)
        asker.store.log_message(profile.user_id, "out", plain(message))
    card = (
        dict(reply.card)
        if reply.card
        else card_for(intent, TurnFacts(asker, message, lang, services, table, now))
    )
    return {"trace_id": trace_id, "intent": intent.value, "message": message_json(message),
            "text": plain(message), "card": card}  # fmt: skip


class TurnFailed(Exception):
    pass


def answer(asker: Asker, body: ChatIn, services: Services, table: Table | None,
           request: Request) -> Response:  # fmt: skip
    lang = body.lang if body.lang in LANGS else asker.profile.lang
    if len(body.text) > MAX_TEXT:
        return error(413, "too_long", TOO_LONG, lang, request)
    if not claim_turn(asker, services, request, dt.datetime.now(dt.UTC)):
        return error(429, "rate_limited", TOO_MANY, lang, request)
    try:
        return cors(JSONResponse(run_turn(asker, body, services, table)), request)
    except TurnFailed:
        return error(500, "failed", TRY_AGAIN, lang, request)


# Commands -----------------------------------------------------------------------------------

CommandName = Literal["brief", "range", "plan", "holdings", "help"]


@dataclass(frozen=True)
class CommandFacts:
    asker: Asker
    profile: Profile  # the asker's, in this command's language
    services: Services
    table: Table | None
    now: dt.datetime


TEXT_CARD: Final = {"type": "text"}


def not_set_up(f: CommandFacts, words: Mapping[str, str]) -> tuple[Message, dict] | None:
    """Telegram's reply to a command from a user who hasn't finished setup."""
    if f.profile.step is Step.DONE:
        return None
    return Message(body=(say(words, f.profile.lang),)), TEXT_CARD


def run_brief(f: CommandFacts) -> tuple[Message, dict]:
    """compose_reply, not send_brief: the web shows the brief and never claims or saves it."""
    if early := not_set_up(f, briefs.NOT_SET_UP):
        return early
    local = briefs.local_now(f.profile, f.now)
    reply, _ = briefs.compose_reply(f.profile, f.asker.store, f.services, local)
    drafted = month_brief(f.asker.store, f.profile, f.services, f.now)
    return message_of(reply), history_card(drafted, f.profile.lang or "en", f.services)


def run_range(f: CommandFacts) -> tuple[Message, dict]:
    if early := not_set_up(f, FINISH_FIRST):
        return early
    lang = f.profile.lang or "en"
    reply = deliver(chat.today.plan_range(f.asker.store, f.profile, lang), lang, f.services)
    return message_of(reply), plan_range_card(f.asker.store, f.profile, f.table)


def run_plan(f: CommandFacts) -> tuple[Message, dict]:
    """cmd_plan's first message without the page link and without moving the profile to the
    plan step: the web shows the plan, it never changes it."""
    plan = f.asker.store.get_plan(f.profile.user_id)
    lang = f.profile.lang
    if f.profile.step is not Step.DONE or plan is None:
        return message_of(with_lead(say(FINISH_FIRST, lang), ask_for(f.profile, plan))), TEXT_CARD
    body = (f"{plan_line(plan, lang)}.", brief_offer(f.profile))
    return Message(say(PLAN_TITLE, lang), body), TEXT_CARD


def run_holdings(f: CommandFacts) -> tuple[Message, dict]:
    if early := not_set_up(f, FINISH_FIRST):
        return early
    reply = holdings_flow.report_reply(f.asker.store, f.profile, f.services, f.now)
    return message_of(reply), holdings_card(f.asker.store, f.profile, f.table) or TEXT_CARD


CommandBuilder = Callable[[CommandFacts], tuple[Message, dict]]
COMMANDS: Final[Mapping[str, CommandBuilder]] = {
    "brief": run_brief,
    "range": run_range,
    "plan": run_plan,
    "holdings": run_holdings,
    "help": lambda f: (help_message(f.profile.lang), TEXT_CARD),
}
if set(COMMANDS) != set(get_args(CommandName)):
    raise RuntimeError("COMMANDS must build every CommandName")


def message_of(reply: Reply) -> Message:
    m = reply.message
    return m if isinstance(m, Message) else Message(body=(m,))


class CommandIn(BaseModel):
    name: CommandName
    lang: str | None = None


def run_command(asker: Asker, body: CommandIn, services: Services, table: Table | None) -> dict:
    """One command's message and card, and one log line with the command, never the text."""
    now = dt.datetime.now(dt.UTC)
    trace_id = uuid.uuid4().hex
    profile = replace(asker.profile, lang=body.lang) if body.lang in LANGS else asker.profile
    facts = CommandFacts(asker, profile, services, table, now)
    with TURN_LOCK:
        start, outcome = dt.datetime.now(dt.UTC), "completed"
        try:
            message, card = COMMANDS[body.name](facts)
        except Exception:
            log.exception("web command %s failed", trace_id)
            message, card, outcome = None, None, "failed"
        cost = cost_between(services.call_log, start, dt.datetime.now(dt.UTC))
    log_turn(services, {
        "ts": now.isoformat(timespec="seconds"), "trace_id": trace_id,
        "user_id": hashed(profile.user_id), "channel": "demo" if asker.sample else "web",
        "intent": f"/{body.name}", "guard": None, "cost_usd": cost, "outcome": outcome,
    })  # fmt: skip
    if message is None or card is None:
        raise TurnFailed(trace_id)
    if not asker.sample:
        asker.store.log_message(profile.user_id, "in", f"/{body.name}")
        asker.store.log_message(profile.user_id, "out", plain(message))
    return {"trace_id": trace_id, "command": body.name, "message": message_json(message),
            "text": plain(message), "card": card}  # fmt: skip


def command(asker: Asker, body: CommandIn, services: Services, table: Table | None,
            request: Request) -> Response:  # fmt: skip
    """The demo shares the chat's caps; a user's commands, like Telegram's, claim no hourly
    answer."""
    lang = body.lang if body.lang in LANGS else asker.profile.lang
    if asker.sample and not claim_turn(asker, services, request, dt.datetime.now(dt.UTC)):
        return error(429, "rate_limited", TOO_MANY, lang, request)
    try:
        return cors(JSONResponse(run_command(asker, body, services, table)), request)
    except TurnFailed:
        return error(500, "failed", TRY_AGAIN, lang, request)


# Track record -------------------------------------------------------------------------------


def track_record(db: Path) -> dict:
    """The /track-record page's own test sentences and the /stats page's counts."""
    stats: list[dict] = []
    if db.exists():
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            stats = [{"label": label, "value": western_grouping(conn.execute(sql).fetchone()[0])}
                     for label, sql in routes.STATS_QUERIES]  # fmt: skip
        finally:
            conn.close()
    return {"tested": routes._own_test(routes.EVAL_SUMMARY), "stats": stats}


# Routes -------------------------------------------------------------------------------------

Origin = Depends(check_origin)


@router.get("/u/{token}/dashboard", dependencies=[Origin])
def user_dashboard(request: Request, token: str, cfg: Config, services: Svc,
                   table: SimTable) -> Response:  # fmt: skip
    try:
        asker = user_by_token(token, cfg)
    except HTTPException:
        return error(404, "not_found", {"en": BAD_LINK}, "en", request)
    return cors(JSONResponse(dashboard(asker, services, table, dt.datetime.now(dt.UTC))), request)


@router.post("/u/{token}/chat", dependencies=[Origin])
def user_chat(request: Request, token: str, body: ChatIn, cfg: Config, services: Svc,
              table: SimTable) -> Response:  # fmt: skip
    try:
        asker = user_by_token(token, cfg)
    except HTTPException:
        return error(404, "not_found", {"en": BAD_LINK}, "en", request)
    return answer(asker, body, services, table, request)


@router.get("/demo/dashboard", dependencies=[Origin])
def demo_dashboard(request: Request, cfg: Config, services: Svc, table: SimTable) -> Response:
    asker = demo_user(cfg)
    return cors(JSONResponse(dashboard(asker, services, table, dt.datetime.now(dt.UTC))), request)


@router.post("/demo/chat", dependencies=[Origin])
def demo_chat(request: Request, body: ChatIn, cfg: Config, services: Svc,
              table: SimTable) -> Response:  # fmt: skip
    return answer(demo_user(cfg), body, services, table, request)


@router.post("/u/{token}/command", dependencies=[Origin])
def user_command(request: Request, token: str, body: CommandIn, cfg: Config, services: Svc,
                 table: SimTable) -> Response:  # fmt: skip
    try:
        asker = user_by_token(token, cfg)
    except HTTPException:
        return error(404, "not_found", {"en": BAD_LINK}, "en", request)
    return command(asker, body, services, table, request)


@router.post("/demo/command", dependencies=[Origin])
def demo_command(request: Request, body: CommandIn, cfg: Config, services: Svc,
                 table: SimTable) -> Response:  # fmt: skip
    return command(demo_user(cfg), body, services, table, request)


@router.get("/track-record", dependencies=[Origin])
def track_record_route(request: Request, db: Annotated[Path, Depends(rates_db)]) -> Response:
    return cors(JSONResponse(track_record(db)), request)


# Signed in with Google ----------------------------------------------------------------------

WEB_CONTACT_PREFIX: Final = "google:"  # link-code misses are counted per Google account
CODE_SHAPE: Final = re.compile(r"\d{6}")
SIGNED_OUT: Final = {"en": "Your sign-in has run out. Sign in again to go on."}
NOT_LINKED: Final = {"en": "Send /weblink to @networth_professor_bot and type the code here."}
BAD_CODE: Final = {
    "en": "That code didn't work. A code works once and only for 10 minutes. Send /weblink to "
    "the bot for a new one."
}


class CodeIn(BaseModel):
    code: str = Field(max_length=32)


def signed_in(request: Request, cfg: Settings) -> session.WebVisitor | None:
    return session.verify(request.headers.get("authorization"), cfg.web_secret,
                          dt.datetime.now(dt.UTC))  # fmt: skip


def linked_user(store: Store, visitor: session.WebVisitor) -> Asker | None:
    """The user this Google account was tied to, while that user is still with us."""
    user_id = store.user_for_web_login(visitor.subject)
    profile = store.get_profile(user_id) if user_id else None
    if profile is None or profile.status is Status.STOPPED or profile.user_id == DEMO_USER:
        return None
    return Asker(store, profile, sample=False)


def web_asker(request: Request, cfg: Settings) -> Asker | Response:
    """The signed-in, linked visitor's user, or the 401 or 403 that says why not."""
    visitor = signed_in(request, cfg)
    if visitor is None:
        return error(401, "signed_out", SIGNED_OUT, "en", request)
    asker = linked_user(Store(cfg.data_dir), visitor)
    return asker or error(403, "not_linked", NOT_LINKED, "en", request)


@router.get("/web/me", dependencies=[Origin])
def web_me(request: Request, cfg: Config) -> Response:
    visitor = signed_in(request, cfg)
    if visitor is None:
        return error(401, "signed_out", SIGNED_OUT, "en", request)
    linked = linked_user(Store(cfg.data_dir), visitor) is not None
    return cors(JSONResponse({"linked": linked, "name": visitor.name}), request)


@router.post("/web/link", dependencies=[Origin])
def web_link(request: Request, body: CodeIn, cfg: Config) -> Response:
    """A /weblink code ties this Google account to the bot user who asked for it. A used, expired
    or wrong code gets the same plain refusal, and misses count towards the hourly limit."""
    visitor = signed_in(request, cfg)
    if visitor is None:
        return error(401, "signed_out", SIGNED_OUT, "en", request)
    code = re.sub(r"\s", "", body.code)
    store = Store(cfg.data_dir)
    contact = WEB_CONTACT_PREFIX + visitor.subject
    user_id = store.redeem_link_code(code, dt.datetime.now(dt.UTC), contact) if (
        CODE_SHAPE.fullmatch(code)) else None  # fmt: skip
    if user_id is None or user_id == DEMO_USER:
        return error(400, "bad_code", BAD_CODE, "en", request)
    store.bind_web_login(visitor.subject, user_id, visitor.name)
    return cors(JSONResponse({"linked": True, "name": visitor.name}), request)


@router.post("/web/forget", dependencies=[Origin])
def web_forget(request: Request, cfg: Config) -> Response:
    """ "Forget me on the web": the Google link goes; the bot user and their data stay."""
    visitor = signed_in(request, cfg)
    if visitor is None:
        return error(401, "signed_out", SIGNED_OUT, "en", request)
    Store(cfg.data_dir).forget_web_login(visitor.subject)
    return cors(JSONResponse({"linked": False}), request)


@router.get("/web/dashboard", dependencies=[Origin])
def web_dashboard(request: Request, cfg: Config, services: Svc, table: SimTable) -> Response:
    asker = web_asker(request, cfg)
    if isinstance(asker, Response):
        return asker
    return cors(JSONResponse(dashboard(asker, services, table, dt.datetime.now(dt.UTC))), request)


@router.post("/web/chat", dependencies=[Origin])
def web_chat(request: Request, body: ChatIn, cfg: Config, services: Svc,
             table: SimTable) -> Response:  # fmt: skip
    asker = web_asker(request, cfg)
    return asker if isinstance(asker, Response) else answer(asker, body, services, table, request)


@router.post("/web/command", dependencies=[Origin])
def web_command(request: Request, body: CommandIn, cfg: Config, services: Svc,
                table: SimTable) -> Response:  # fmt: skip
    asker = web_asker(request, cfg)
    return asker if isinstance(asker, Response) else command(asker, body, services, table, request)


pages.include_router(router)

if __name__ == "__main__":
    if sys.argv[1:] != ["reset-demo"]:
        sys.exit("usage: uv run python -m networth.web.api reset-demo")
    reset_demo(Store(Settings.from_env().data_dir))
    print(f"demo profile {DEMO_USER} reset")  # noqa: T201
