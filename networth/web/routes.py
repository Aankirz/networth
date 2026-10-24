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
from typing import Annotated, Final

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from networth.app.settings import Settings
from networth.engine import odds as engine
from networth.engine.model import CURRENCY, EventType, RatesDB
from networth.web import names, views
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


@functools.cache
def rates_db() -> Path:
    return Settings.from_env().rates_db


DB = Annotated[Path, Depends(rates_db)]


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
