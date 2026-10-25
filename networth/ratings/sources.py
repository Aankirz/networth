"""Where a rating's numbers come from. Free sources with no key, each read with its time.

    src = LiveSources(watcher_db=Path("data/watcher.sqlite"))
    info = src.stock("HDFCBANK.NS")       # Yahoo Finance quote summary, or None
    closes = src.closes("^NSEI")          # Yahoo daily closes
    navs = src.fund_navs(118482)          # mfapi.in NAV history (AMFI's daily NAVs)
    listings = src.ipos()                 # NSE's upcoming and current issues
    stories = src.stories(since)          # confirmed stories from our own watcher

Docs read on 2026-10-25: https://www.mfapi.in (search and scheme endpoints), the NSE IPO pages
behind https://www.nseindia.com/market-data/all-upcoming-issues-ipo (they need the cookie the
home page sets), and yfinance's Ticker.info and Ticker.history.

Every value here is what the source said. Nothing is estimated; a missing field stays None.
"""

from __future__ import annotations

import datetime as dt
import http.cookiejar
import json
import logging
import re
import urllib.parse
import urllib.request
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import pandas as pd

from networth.net import call_with_deadline
from networth.ratings.model import Source

log = logging.getLogger("networth.ratings")

DEADLINE_S: Final = 30.0
USER_AGENT: Final = "Mozilla/5.0 (networth-ratings)"
MFAPI: Final = "https://api.mfapi.in/mf"
NSE: Final = "https://www.nseindia.com"
NSE_UPCOMING: Final = NSE + "/api/all-upcoming-issues?category=ipo"
NSE_CURRENT: Final = NSE + "/api/ipo-current-issue"
NSE_DETAIL: Final = NSE + "/api/ipo-detail?symbol={symbol}&series=EQ"
YAHOO_QUOTE: Final = "https://finance.yahoo.com/quote/{symbol}"
WATCHER: Final = "Networth watcher"


@dataclass(frozen=True)
class StockInfo:
    symbol: str  # "HDFCBANK", without the exchange suffix
    ticker: str  # "HDFCBANK.NS", or "AAPL"
    name: str
    currency: str  # "INR" or "USD"
    sector: str | None
    industry: str | None
    pe: float | None  # trailing
    pb: float | None
    debt_to_equity: float | None  # Yahoo's figure is a percent: 14.8 means 0.148x
    revenue_growth: float | None  # the latest fiscal year over the one before, a fraction
    earnings_growth: float | None  # the same for net income; None when the base was a loss
    margin: float | None  # profit margin, a fraction
    is_fund: bool  # an ETF listed as a share
    source: Source
    ps: float | None = None  # price to trailing 12-month sales
    growth_source: Source | None = None  # the annual statements the growth came from


def annual_growth(stmt: pd.DataFrame | None, row: str) -> tuple[float | None, str | None]:
    """(latest fiscal year over the year before, the latest year's end date). Yahoo's own
    revenueGrowth is a quarterly field that can be wrong (HDFC Bank showed +81% on 2026-10-25
    while its annual statements showed +5.2%), so growth is read from the statements."""
    if stmt is None or stmt.empty or row not in stmt.index:
        return None, None
    s = stmt.loc[row].dropna().sort_index(ascending=False)
    if len(s) < 2:
        return None, None
    end = s.index[0].date().isoformat()
    return (float(s.iloc[0] / s.iloc[1] - 1) if s.iloc[1] > 0 else None), end


@dataclass(frozen=True)
class Closes:
    series: pd.Series  # float closes indexed by date
    source: Source


@dataclass(frozen=True)
class IpoListing:
    symbol: str
    name: str
    price_band: str  # "Rs.313 to Rs.330"
    start: str
    end: str
    status: str
    source: Source


@dataclass(frozen=True)
class IpoDetail:
    issue_size: str  # NSE's words: "Fresh issue of ... and offer for sale up to ..."
    subscribed_times: float | None  # the Total row of bidDetails, None before bidding opens
    rhp_url: str | None
    source: Source


@dataclass(frozen=True)
class Seen:
    """A confirmed watcher story."""

    title: str
    titles: tuple[str, ...]  # the story's title and its articles' titles
    day: dt.date
    publishers: tuple[str, ...]
    type: str | None  # the event type, when the judge gave one


@dataclass(frozen=True)
class Stories:
    items: tuple[Seen, ...]
    source: Source


class Sources(Protocol):
    def stock(self, ticker: str) -> StockInfo | None: ...
    def closes(self, ticker: str, period: str = "15y") -> Closes | None: ...
    def fund_search(self, query: str) -> list[tuple[int, str]]: ...
    def fund_navs(self, code: int) -> tuple[str, Closes] | None: ...
    def ipos(self) -> list[IpoListing]: ...
    def ipo_detail(self, symbol: str) -> IpoDetail | None: ...
    def stories(self, since: dt.datetime) -> Stories | None: ...


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _get(url: str, opener: urllib.request.OpenerDirector | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with (opener or urllib.request.build_opener()).open(req, timeout=DEADLINE_S) as resp:
        return resp.read()


def _num(x: object) -> float | None:
    return float(x) if isinstance(x, int | float) and x == x else None


class LiveSources:
    def __init__(self, watcher_db: Path | None = None) -> None:
        self.watcher_db = watcher_db
        self._nse: urllib.request.OpenerDirector | None = None

    def stock(self, ticker: str) -> StockInfo | None:
        import yfinance as yf

        def fetch() -> tuple[dict, pd.DataFrame | None]:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # yfinance trips pandas deprecation warnings
                tk = yf.Ticker(ticker)
                info = tk.info or {}
                stmt = tk.income_stmt if info.get("quoteType") == "EQUITY" else None
                return info, stmt

        info, stmt = call_with_deadline(fetch, DEADLINE_S, "Yahoo info")
        name = info.get("longName") or info.get("shortName")
        currency = info.get("currency")
        if not name or currency not in ("INR", "USD"):
            return None
        revenue, year_end = annual_growth(stmt, "Total Revenue")
        earnings, _ = annual_growth(stmt, "Net Income")
        statements = Source(
            "Yahoo Finance annual statements",
            YAHOO_QUOTE.format(symbol=ticker) + "/financials",
            year_end or _now(),
        )
        is_fund = info.get("quoteType") in ("ETF", "MUTUALFUND") or (
            info.get("industry") is None and re.search(r"\b(ETF|BeES)\b", name, re.I) is not None
        )
        return StockInfo(
            ticker.split(".")[0],
            ticker,
            name,
            currency,
            info.get("sector"),
            info.get("industry"),
            _num(info.get("trailingPE")),
            _num(info.get("priceToBook")),
            _num(info.get("debtToEquity")),
            revenue,
            earnings,
            _num(info.get("profitMargins")),
            is_fund,
            Source("Yahoo Finance", YAHOO_QUOTE.format(symbol=ticker), _now()),
            _num(info.get("priceToSalesTrailing12Months")),
            statements if year_end else None,
        )

    def closes(self, ticker: str, period: str = "15y") -> Closes | None:
        import yfinance as yf

        def fetch() -> pd.Series | None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
            if hist is None or hist.empty or "Close" not in hist:
                return None
            s = hist["Close"].dropna()
            s.index = pd.to_datetime(s.index.date)
            return s[~s.index.duplicated(keep="last")].astype(float)

        s = call_with_deadline(fetch, DEADLINE_S, "Yahoo history")
        if s is None or len(s) < 2:
            return None
        url = YAHOO_QUOTE.format(symbol=urllib.parse.quote(ticker)) + "/history"
        return Closes(s, Source("Yahoo Finance", url, s.index[-1].date().isoformat()))

    def fund_search(self, query: str) -> list[tuple[int, str]]:
        rows = json.loads(_get(f"{MFAPI}/search?q={urllib.parse.quote(query)}"))
        return [(int(r["schemeCode"]), str(r["schemeName"])) for r in rows]

    def fund_navs(self, code: int) -> tuple[str, Closes] | None:
        body = json.loads(_get(f"{MFAPI}/{code}"))
        data = body.get("data") or []
        if not data:
            return None
        s = pd.Series(
            {
                pd.Timestamp(dt.datetime.strptime(r["date"], "%d-%m-%Y")): float(r["nav"])
                for r in data
            }
        ).sort_index()
        s = s[s > 0]
        name = body.get("meta", {}).get("scheme_name") or str(code)
        return name, Closes(
            s, Source("mfapi.in (AMFI NAVs)", f"{MFAPI}/{code}", s.index[-1].date().isoformat())
        )

    def _nse_json(self, url: str) -> object:
        if self._nse is None:
            jar = http.cookiejar.CookieJar()
            self._nse = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            try:
                _get(NSE + "/", self._nse)  # sets the cookies the API needs; it may answer 403
            except Exception as exc:  # noqa: BLE001 - the cookies come with the 403 too
                log.info("NSE home page: %s", type(exc).__name__)
        return json.loads(_get(url, self._nse))

    def ipos(self) -> list[IpoListing]:
        out: list[IpoListing] = []
        for url in (NSE_CURRENT, NSE_UPCOMING):
            rows = self._nse_json(url)
            at = _now()
            for r in rows if isinstance(rows, list) else []:
                if not r.get("symbol") or any(o.symbol == r["symbol"] for o in out):
                    continue
                out.append(
                    IpoListing(
                        r["symbol"],
                        r.get("companyName") or r["symbol"],
                        r.get("issuePrice") or "",
                        r.get("issueStartDate") or "",
                        r.get("issueEndDate") or "",
                        r.get("status") or "",
                        Source("NSE", url, at),
                    )
                )
        return out

    def ipo_detail(self, symbol: str) -> IpoDetail | None:
        url = NSE_DETAIL.format(symbol=urllib.parse.quote(symbol))
        body = self._nse_json(url)
        if not isinstance(body, dict):
            return None
        info = {
            d.get("title"): d.get("value") for d in body.get("issueInfo", {}).get("dataList", [])
        }
        total = next((b for b in body.get("bidDetails", []) if b.get("category") == "Total"), None)
        times = _num(float(total["noOfTime"])) if total and total.get("noOfTime") else None
        return IpoDetail(
            str(info.get("Issue Size") or "").strip('"'),
            times or None,
            info.get("Red Herring Prospectus"),
            Source("NSE", url, _now()),
        )

    def stories(self, since: dt.datetime) -> Stories | None:
        if self.watcher_db is None or not self.watcher_db.exists():
            return None
        return stories_from(self.watcher_db, since)


def stories_from(path: Path, since: dt.datetime) -> Stories:
    from networth.llm import Classified
    from networth.watcher.store import Confirmed
    from networth.watcher.store import Store as WatcherStore

    db = WatcherStore.open(path)
    try:
        articles = db.articles_by_story()
        seen: list[Seen] = []
        for d in db.decisions():
            if not isinstance(d.verdict, Confirmed) or d.story.first_seen < since:
                continue
            c = d.story.classification
            seen.append(
                Seen(
                    d.story.title,
                    (d.story.title, *(a.title for a in articles.get(d.story.id, ()))),
                    d.story.first_seen.date(),
                    d.verdict.publishers,
                    c.type.value if isinstance(c, Classified) else None,
                )
            )
        last = db.latest_cycle()
    finally:
        db.close()
    at = last.finished_at.isoformat(timespec="seconds") if last else _now()
    return Stories(
        tuple(sorted(seen, key=lambda s: s.day, reverse=True)), Source(WATCHER, "/track-record", at)
    )


def mentions(stories: Sequence[Seen], words: Sequence[str]) -> list[Seen]:
    """Stories whose titles name any of the words as whole words."""
    pats = [re.compile(rf"(?<!\w){re.escape(w.casefold())}(?!\w)") for w in words if w]
    return [s for s in stories if any(p.search(t.casefold()) for t in s.titles for p in pats)]
