"""Ratings and the sector board on the web: public pages anyone can open and share, and the
JSON the site builds its cards on. No sign-in anywhere here.

    GET /r/{slug}               a rating (/r/hdfcbank, /r/mf120716, /r/sfctech), the sector
                                board (/r/sectors) or one sector (/r/sector-bank)
    GET /api/rating/{query}     RatingCard
    GET /api/sectors            SectorsCard
    GET /api/ratings/backtest   RatingsBacktest, the stored table

A rating reads several free sources, so each one is kept for CACHE_S. Unknown names get the
friendly 404 page, or the API's not_found error.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from networth import sectors
from networth.app.settings import Settings
from networth.ratings import Rating, rate, rating_json, track
from networth.ratings.sources import LiveSources, Sources
from networth.web.api import check_origin, cors, error
from networth.web.routes import BOT_URL, settings
from networth.web.routes import router as pages

HERE: Final = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=HERE / "templates")
api = APIRouter(prefix="/api")
public = APIRouter()

CACHE_S: Final = 3600.0
CACHE_MAX: Final = 200
NOT_FOUND: Final = {"en": "We couldn't find a share, fund or upcoming IPO by that name."}
NO_TABLE: Final = {"en": "The backtest table hasn't been built yet."}
SECTOR_PREFIX: Final = "sector-"


def live_sources(data_dir: Path) -> Sources:
    return LiveSources(data_dir / "watcher.sqlite")


SOURCES: Callable[[Path], Sources] = live_sources  # tests swap in fakes

# ponytail: one in-process cache with a global lock; a shared cache if we ever run two workers.
_cache: dict[str, tuple[float, Rating]] = {}
_lock = threading.Lock()


def rating_for(query: str, cfg: Settings) -> Rating:
    """Raises LookupError for an unknown name."""
    key = query.strip().upper()
    with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_S:
            return hit[1]
    r = rate(key, sources=SOURCES(cfg.data_dir))
    with _lock:
        if len(_cache) >= CACHE_MAX:
            _cache.clear()
        _cache[key] = (time.monotonic(), r)
    return r


def board_for(cfg: Settings) -> dict:
    return sectors.board(SOURCES(cfg.data_dir), dt.datetime.now(dt.UTC), cfg.public_url)


def group_for(r: Rating) -> dict | None:
    """The backtest group this rating's track line comes from, for the page's table."""
    market = "us" if r.currency == "USD" else "in"
    kind = f"{market}_{'fund' if r.kind in ('fund', 'etf') else 'stock'}"
    table = track.load() or {}
    return next((g for g in table.get("groups", []) if g["kind"] == kind), None)


def _page(request: Request, name: str, status: int = 200, **context: object) -> HTMLResponse:
    return templates.TemplateResponse(request, name, {"bot_url": BOT_URL, **context},
                                      status_code=status)  # fmt: skip


Config = Depends(settings)


@public.get("/r/{slug}", response_class=HTMLResponse)
def share_page(request: Request, slug: str, cfg: Settings = Config) -> HTMLResponse:
    if slug == "sectors" or slug.startswith(SECTOR_PREFIX):
        card = board_for(cfg)
        key = slug.removeprefix(SECTOR_PREFIX) if slug != "sectors" else None
        rows = [r for r in card["rows"] if key is None or r["key"] == key]
        if key is not None and key not in sectors.BY_KEY:
            return _page(request, "r_missing.html", 404, what=slug)
        return _page(request, "r_sectors.html", card=card, rows=rows,
                     single=rows[0]["name"] if key and rows else None)  # fmt: skip
    try:
        r = rating_for(slug, cfg)
    except LookupError:
        return _page(request, "r_missing.html", 404, what=slug)
    table = track.load() or {}
    return _page(request, "r_rating.html", r=r, card=rating_json(r), group=group_for(r),
                 caveat=table.get("caveat"), method=table.get("method"))  # fmt: skip


@api.get("/rating/{query}", dependencies=[Depends(check_origin)])
def rating_api(request: Request, query: str, cfg: Settings = Config) -> Response:
    try:
        r = rating_for(query, cfg)
    except LookupError:
        return error(404, "not_found", NOT_FOUND, "en", request)
    return cors(JSONResponse(rating_json(r, cfg.public_url)), request)


@api.get("/sectors", dependencies=[Depends(check_origin)])
def sectors_api(request: Request, cfg: Settings = Config) -> Response:
    return cors(JSONResponse(board_for(cfg)), request)


@api.get("/ratings/backtest", dependencies=[Depends(check_origin)])
def backtest_api(request: Request) -> Response:
    table = track.load()
    if table is None:
        return error(404, "not_found", NO_TABLE, "en", request)
    return cors(JSONResponse(table), request)


pages.include_router(public)
pages.include_router(api)
