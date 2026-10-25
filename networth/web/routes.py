"""Server-rendered pages over data/base_rates.sqlite. Phase 3A mounts `router`;
`python -m networth.web` serves it alone.

Routes call the engine, hand its JSON to a pure view function in views.py, and render. An
APIRouter has no exception handlers, so each route turns the engine's lookup errors into the
friendly 404 itself.
"""

from __future__ import annotations

import datetime as dt
import functools
import math
import sqlite3
from pathlib import Path
from typing import Annotated, Final, NamedTuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from networth import holdings, sim
from networth.app import links
from networth.app.settings import Settings
from networth.app.store import Plan, Profile, Store
from networth.bot.onboarding import (
    BUCKETS,
    DROPS,
    HORIZON_BUTTONS,
    MAX_YEARS,
    OWN_PLAN,
    OWN_PLAN_NAME,
    STARTER_PLANS,
    format_money,
    ordinal,
    plan_line,
)
from networth.engine import odds as engine
from networth.engine.model import CURRENCY, EventType, RatesDB
from networth.sim.data import MissingSeries, Table, load_table
from networth.web import holdings_view, names, plan_view, views
from networth.web.fmt import western_grouping

HERE: Final = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=HERE / "templates")
router = APIRouter()

BOT_URL: Final = "https://t.me/networth_professor_bot"
DEFAULT_AMOUNT: Final = 100_000.0
MAX_AMOUNT: Final = 1e12
CURRENCIES: Final = frozenset(CURRENCY.values())
LANDING_TYPE: Final = "rbi_hike"
TRACK_RECORD_LIMIT: Final = 500
DEMO_AMOUNT: Final = 150_000
DEMO_YEARS: Final = 15
DEMO_FALL: Final = 20


@functools.cache
def settings() -> Settings:
    return Settings.from_env()


def rates_db() -> Path:
    return settings().rates_db


DB = Annotated[Path, Depends(rates_db)]


@functools.cache
def _loaded_table() -> Table:
    return load_table()


def sim_table() -> Table | None:
    """The plan range's table, read once. None until it is built; a failed read isn't
    cached, so building the table later needs no restart."""
    try:
        return _loaded_table()
    except MissingSeries:
        return None


SimTable = Annotated[Table | None, Depends(sim_table)]
Config = Annotated[Settings, Depends(settings)]
BAD_LINK: Final = "This link has expired or isn't right. Type /plan in the bot for a fresh one."


def _page(request: Request, name: str, status: int = 200, **context: object) -> HTMLResponse:
    return templates.TemplateResponse(
        request, name, {"bot_url": BOT_URL, **context}, status_code=status
    )


def _not_found(request: Request, what: str) -> HTMLResponse:
    return _page(request, "not_found.html", 404, what=what, types=names.TYPES)


def _bad_input(request: Request, problem: str, back: str) -> HTMLResponse:
    return _page(request, "bad_input.html", 400, problem=problem, back=back)


def _scoreboard_groups(db: Path, type: str) -> list[tuple[str, engine.CompareJSON]]:
    """compare() for every group whose assets have this type's row; groups left with fewer
    than two assets are skipped."""
    t = EventType(type)
    rates = RatesDB.open(db)
    try:
        have = {a for a in rates.assets() if any(c is None for _, c in rates.rows_for(t, a))}
    finally:
        rates.close()
    out = []
    for market, groups in names.SCOREBOARD_GROUPS.items():
        for group in groups:
            present = [a for a in group if a in have]
            if len(present) >= engine.COMPARE_MIN:
                out.append((market, engine.compare(type, present, db=db)))
    return out


@router.get("/static/networth.css", include_in_schema=False)
def stylesheet() -> FileResponse:
    return FileResponse(HERE / "static" / "networth.css", media_type="text/css")


@router.get("/", response_class=HTMLResponse)
def landing(request: Request, db: DB) -> HTMLResponse:
    groups = _scoreboard_groups(db, LANDING_TYPE)
    sample = views.scoreboard_view(LANDING_TYPE, groups[:1]) if groups else None
    return _page(request, "landing.html", sample=sample)


@router.get("/why/{type}/{asset}", response_class=HTMLResponse)
def why(request: Request, type: str, asset: str, db: DB) -> HTMLResponse:
    if type not in names.TYPES:
        return _not_found(request, f"We don't track an event type called “{type}”.")
    try:
        o = engine.odds(type, asset, db=db)
    except (ValueError, engine.NoBaseRate):
        return _not_found(request, f"We have no history for “{asset}” after this event.")
    return _page(request, "why.html", v=views.why_view(o), share_url=str(request.url))


def _parse_amount(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return DEFAULT_AMOUNT
    try:
        amount = float(raw.replace(",", ""))
    except ValueError:
        return None
    return amount if math.isfinite(amount) and 0 < amount <= MAX_AMOUNT else None


@router.get("/what-if/{type}/{asset}", response_class=HTMLResponse)
def what_if(
    request: Request,
    type: str,
    asset: str,
    db: DB,
    amount: str | None = None,
    currency: str | None = None,
) -> HTMLResponse:
    if type not in names.TYPES:
        return _not_found(request, f"We don't track an event type called “{type}”.")
    back = f"/what-if/{type}/{asset}"
    value = _parse_amount(amount)
    if value is None:
        return _bad_input(request, "The amount needs to be a positive number, up to 1e12.", back)
    if currency is not None and currency.upper() not in CURRENCIES:
        return _bad_input(request, "The currency needs to be INR or USD.", back)
    try:
        o = engine.odds(type, asset, db=db)
        rng = engine.position_range(value, asset, type, db=db)
    except (ValueError, engine.NoBaseRate):
        return _not_found(request, f"We have no history for “{asset}” after this event.")
    chosen = currency.upper() if currency else rng["currency"]
    v = views.what_if_view(o, rng, value, chosen, rng["currency"])
    return _page(request, "what_if.html", v=v, currencies=sorted(CURRENCIES))


@router.get("/scoreboard/{type}", response_class=HTMLResponse)
def scoreboard(request: Request, type: str, db: DB) -> HTMLResponse:
    if type not in names.TYPES:
        return _not_found(request, f"We don't track an event type called “{type}”.")
    v = views.scoreboard_view(type, _scoreboard_groups(db, type))
    return _page(request, "scoreboard.html", v=v, types=names.TYPES)


@router.get("/track-record", response_class=HTMLResponse)
def track_record(request: Request, db: DB) -> HTMLResponse:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'track_record'"
        ).fetchone()
        columns: list[str] = []
        rows: list[tuple] = []
        if exists:
            cur = conn.execute(f"SELECT * FROM track_record LIMIT {TRACK_RECORD_LIMIT}")
            columns = [d[0].replace("_", " ") for d in cur.description]
            rows = cur.fetchall()
    finally:
        conn.close()
    return _page(request, "track_record.html", columns=columns, rows=rows, count=len(rows))


STATS_QUERIES: Final[tuple[tuple[str, str], ...]] = (
    ("Past news events", "SELECT COUNT(*) FROM events"),
    ("Independent episodes", "SELECT COUNT(*) FROM episodes"),
    ("Base rates", "SELECT COUNT(*) FROM base_rates"),
    (
        "Distinct source links",
        "SELECT COUNT(DISTINCT s.value) FROM events, json_each(events.sources) AS s",
    ),
    ("Event types", "SELECT COUNT(DISTINCT type) FROM base_rates"),
    ("Assets", "SELECT COUNT(DISTINCT asset) FROM base_rates"),
)


@router.get("/stats", response_class=HTMLResponse)
def stats(request: Request, db: DB) -> HTMLResponse:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        counts = [
            (label, western_grouping(conn.execute(sql).fetchone()[0]))
            for label, sql in STATS_QUERIES
        ]
        built = conn.execute("SELECT value FROM meta WHERE key = 'built_at'").fetchone()
    finally:
        conn.close()
    built_at = dt.datetime.fromisoformat(built[0]).strftime("%-d %B %Y") if built else None
    return _page(request, "stats.html", counts=counts, built_at=built_at)


@router.get("/u/{token}", response_class=HTMLResponse)
def user_page(request: Request, token: str, cfg: Config, table: SimTable) -> HTMLResponse:
    """One user's plan and last brief, behind a signed, expiring link. No login."""
    now = dt.datetime.now(dt.UTC)
    link_token = links.verify(token, cfg.link_secret, now) if cfg.link_secret else None
    store = Store(cfg.data_dir)
    profile = store.profile_by_token(link_token) if link_token else None
    if profile is None:
        return _not_found(request, BAD_LINK)
    plan = store.get_plan(profile.user_id)
    money = format_money(profile.monthly_amount or 0, profile.currency or "INR")
    day = ordinal(profile.invest_day) if profile.invest_day else None
    last = store.last_brief(profile.user_id)
    response = _page(request, "user.html", plan=plan_line(plan) if plan else None, money=money,
                     day=day, brief=last, **_user_range(plan, profile, table))  # fmt: skip
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.get("/u/{token}/holdings", response_class=HTMLResponse)
def holdings_page(request: Request, token: str, cfg: Config, table: SimTable) -> HTMLResponse:
    """One user's confirmed holdings, valued at the prices stored with them (no lookups)."""
    now = dt.datetime.now(dt.UTC)
    link_token = links.verify(token, cfg.link_secret, now) if cfg.link_secret else None
    store = Store(cfg.data_dir)
    profile = store.profile_by_token(link_token) if link_token else None
    if profile is None:
        return _not_found(request, BAD_LINK)
    report = holdings.report_for(profile.user_id, store, table=table)
    v = holdings_view.holdings_view(report) if report else None
    response = _page(request, "holdings.html", v=v, empty=holdings_view.NO_HOLDINGS)
    response.headers["X-Robots-Tag"] = "noindex"
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _user_range(plan: Plan | None, profile: Profile, table: Table | None) -> dict:
    """The /u section's context: the range, the rupee-only line, or nothing to show."""
    if plan is None or table is None:
        return {}
    try:
        r = sim.plan_range(plan, profile, table=table)
    except sim.NotRupees:
        return {"note": plan_view.RUPEES_ONLY}
    return {"pr": plan_view.plan_range_view(r, plan_line(plan))}


class PlanQuery(NamedTuple):
    plan: Plan
    amount: int
    years: int  # as onboarding stores it; sim.horizon_years maps it to simulated years


def _whole(raw: str | None, default: int, lo: int, hi: int) -> int | None:
    if raw is None or raw.strip() == "":
        return default
    text = raw.replace(",", "").strip()
    return int(text) if text.isdigit() and lo <= int(text) <= hi else None


def _own_split(split: tuple[str | None, ...]) -> tuple[int, ...] | None:
    pcts = tuple(_whole(p, -1, 0, 100) for p in split)
    if any(p is None or p < 0 for p in pcts):
        return None
    return pcts if sum(pcts) == 100 else None


def _parse_plan_query(name: str, amount: str | None, years: str | None, fall: str | None,
                      split: tuple[str | None, ...]) -> PlanQuery | str:  # fmt: skip
    """The demo form's GET parameters, or the sentence saying what to fix."""
    targets = STARTER_PLANS[name][1] if name in STARTER_PLANS else None
    if name == OWN_PLAN:
        targets = _own_split(split)
        if targets is None:
            return "Your own split needs safety, core and growth as whole numbers adding to 100."
    if targets is None:
        return "The plan needs to be steady, balanced, ambitious or own."
    money = _whole(amount, DEMO_AMOUNT, 1, int(MAX_AMOUNT))
    if money is None:
        return "The amount needs to be a whole number of rupees, from 1 up to 1e12."
    span = _whole(years, DEMO_YEARS, 1, MAX_YEARS)
    if span is None:
        return f"The time needs to be a whole number of years, from 1 to {MAX_YEARS}."
    limit = _whole(fall, DEMO_FALL, 1, 100)
    if limit is None:
        return "The fall needs to be a whole percent, from 1 to 100."
    plan = Plan("demo", name, dict(zip(BUCKETS, targets, strict=True)), limit, "")
    return PlanQuery(plan, money, span)


def _plan_form(q: PlanQuery) -> dict:
    sim_years = sim.horizon_years(q.years)
    return {
        "plans": [
            *((k, label) for k, (label, _) in STARTER_PLANS.items()),
            (OWN_PLAN, OWN_PLAN_NAME),
        ],
        "plan": q.plan.name,
        "split": [(b, q.plan.targets_pct[b]) for b in BUCKETS],
        "amount": q.amount,
        "horizons": HORIZON_BUTTONS,
        "years": next(v for _, v in HORIZON_BUTTONS if sim.horizon_years(v) == sim_years),
        "falls": sorted({*DROPS, q.plan.max_drop_ok}),
        "fall": q.plan.max_drop_ok,
    }


@router.get("/plan-range", response_class=HTMLResponse)
def plan_range_page(
    request: Request,
    table: SimTable,
    plan: str = "balanced",
    amount: str | None = None,
    years: str | None = None,
    fall: str | None = None,
    safety: str | None = None,
    core: str | None = None,
    growth: str | None = None,
    currency: str | None = None,
) -> HTMLResponse:
    """One plan's range, for a starter plan or a split the viewer types. Never two at once."""
    if currency is not None and currency.upper() != "INR":
        return _page(request, "plan_range.html", note=plan_view.RUPEES_ONLY, form=None)
    q = _parse_plan_query(plan, amount, years, fall, (safety, core, growth))
    if isinstance(q, str):
        return _bad_input(request, q, "/plan-range")
    if table is None:
        return _page(request, "plan_range.html", 503, note=plan_view.NO_TABLE, form=None)
    targets = tuple(q.plan.targets_pct[b] for b in BUCKETS)
    r = sim.simulate(targets, q.amount, sim.horizon_years(q.years), q.plan.max_drop_ok, table)
    return _page(request, "plan_range.html", form=_plan_form(q),
                 pr=plan_view.plan_range_view(r, plan_line(q.plan)))  # fmt: skip
