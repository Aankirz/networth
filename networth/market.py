"""Prices and history for a stock, an ETF or an index, from a free source that needs no key.

    q = quote("SWIGGY.NS")                 # Quote: last close, day change, 52-week range, a year
    h = history("^NSEI", years=5)          # History: daily closes over the asked years
    symbols = resolve("should I buy swiggy", "INR")   # ("SWIGGY.NS",)
    falls = drawdowns(h.closes)            # the worst peak-to-trough falls, worst first

The source is Yahoo Finance through yfinance, the library the engine already uses. Every number
comes back with the source's own date, so a reply can say where and when it is from; nothing
here fills a gap with a guess. A symbol the source doesn't know gives None.
"""

from __future__ import annotations

import datetime as dt
import re
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol
from urllib.parse import quote as urlquote

import pandas as pd

SOURCE_NAME: Final = "Yahoo Finance"
US_EXCHANGES: Final = {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NYQ": "NYSE"}
YEAR_DAYS: Final = 365
MAX_YEARS: Final = 30
MAX_FALLS: Final = 3
MIN_FALL: Final = 0.05  # a dip under 5% is noise, not a fall worth naming


@dataclass(frozen=True)
class Index:
    symbol: str
    name: str
    market: str  # "in" or "us"
    words: str  # a regex of the names people use


INDICES: Final = (
    Index("^NSEBANK", "Nifty Bank", "in", r"bank ?nifty|nifty ?bank"),
    Index("^NSEMDCP50", "Nifty Midcap 50", "in", r"mid ?caps?|midcap index"),
    Index("NIFTYSMLCAP250.NS", "Nifty Smallcap 250", "in", r"small ?caps?|smallcap index"),
    Index("^NSEI", "Nifty 50", "in", r"nifty(?: ?50)?|निफ्टी"),
    Index("^BSESN", "Sensex", "in", r"sensex|सेंसेक्स|bse"),
    Index("^GSPC", "S&P 500", "us", r"s ?& ?p(?: ?500)?|s and p|sp ?500"),
    Index("^IXIC", "Nasdaq", "us", r"nasdaq"),
    Index("^DJI", "Dow Jones", "us", r"dow(?: jones)?"),
)
BY_SYMBOL: Final = {i.symbol: i for i in INDICES}
HOME_INDICES: Final = {
    "in": ("^NSEI", "^BSESN", "^NSEBANK", "^NSEMDCP50", "NIFTYSMLCAP250.NS"),
    "us": ("^GSPC", "^IXIC", "^DJI"),
}
# Names the source's search misses or reads another way: Zomato listed as Eternal; "Jio" is how
# people say Reliance, Jio's parent.
ALIASES: Final = {
    r"zomato|eternal": ("ETERNAL.NS", "Eternal (Zomato)"),
    r"jio(?! ?fin)": ("RELIANCE.NS", "Reliance Industries, Jio's parent"),
    r"jio ?fin\w*": ("JIOFIN.NS", "Jio Financial Services"),
}
STOP: Final = frozenset(
    "a an the is are was what whats what's how has have had did do does should i me my we you "
    "your of in on for to at by with and or vs versus compare compared against than now today "
    "current currently price prices share shares stock stocks quote worth value invest "
    "investing investment buy sell hold add keep good bad over last past year years month months "
    "done doing performed perform return returns since ago it its this that there here tell "
    "about much many any ka ki ke hai kya kaisa kaise mein aaj abhi lena chahiye kharidna bechna "
    "rs inr usd at avg average bought holding hold held please pls as be will can could would "
    "go up down from into gone get got one two three five ten us india indian market markets "
    "index fund funds etf etfs company ltd limited inc".split()
)
WORD: Final = re.compile(r"[a-z][a-z.&-]*")


class Source(Protocol):
    def closes(self, symbol: str, years: float) -> pd.Series: ...
    def info(self, symbol: str) -> dict: ...
    def search(self, text: str) -> list[dict]: ...


class Yahoo:
    """yfinance, warnings off: it trips pandas deprecations on every call."""

    def closes(self, symbol: str, years: float) -> pd.Series:
        import yfinance as yf

        period = "max" if years > MAX_YEARS else f"{max(1, int(years + 0.999))}y"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            frame = yf.Ticker(symbol).history(period=period, auto_adjust=True)
        if frame is None or frame.empty:
            return pd.Series(dtype=float)
        s = frame["Close"].dropna().astype(float)
        s.index = pd.to_datetime(s.index.date)
        return s[~s.index.duplicated(keep="last")]

    def info(self, symbol: str) -> dict:
        import yfinance as yf

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fast = yf.Ticker(symbol).fast_info
            return {"currency": fast.get("currency"), "exchange": fast.get("exchange"),
                    "low_52w": fast.get("yearLow"), "high_52w": fast.get("yearHigh")}  # fmt: skip

    def search(self, text: str) -> list[dict]:
        import yfinance as yf

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return list(yf.Search(text, max_results=6).quotes)


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    exchange: str
    currency: str
    price: float
    prev_close: float
    low_52w: float
    high_52w: float
    day: dt.date  # the source's date for `price`
    closes: pd.Series  # a year of daily closes

    @property
    def change(self) -> float:
        return self.price - self.prev_close

    @property
    def change_pct(self) -> float:
        return self.change / self.prev_close if self.prev_close else 0.0

    @property
    def is_index(self) -> bool:
        return self.symbol in BY_SYMBOL


@dataclass(frozen=True)
class History:
    symbol: str
    name: str
    currency: str
    closes: pd.Series

    @property
    def total(self) -> float:
        return float(self.closes.iloc[-1] / self.closes.iloc[0] - 1)

    @property
    def years(self) -> float:
        return (self.closes.index[-1] - self.closes.index[0]).days / YEAR_DAYS

    @property
    def per_year(self) -> float:
        """The compound yearly return over the span."""
        return float((1 + self.total) ** (1 / self.years) - 1) if self.years > 0 else 0.0


@dataclass(frozen=True)
class Fall:
    fall: float  # 0.32 for a 32% fall
    peak: dt.date
    trough: dt.date
    recovered: dt.date | None


def source_url(symbol: str) -> str:
    return f"https://finance.yahoo.com/quote/{urlquote(symbol)}"


def exchange_name(symbol: str, raw: str | None) -> str:
    if symbol in BY_SYMBOL:
        return "index"
    if symbol.endswith(".NS"):
        return "NSE"
    if symbol.endswith(".BO"):
        return "BSE"
    return {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NYQ": "NYSE"}.get(
        raw or "", raw or ""
    )


def currency_of(symbol: str, src: Source) -> str:
    index = BY_SYMBOL.get(symbol)
    if index:
        return "USD" if index.market == "us" else "INR"
    return str(src.info(symbol).get("currency") or "USD").upper()


def name_of(symbol: str, hint: str | None = None) -> str:
    if symbol in BY_SYMBOL:
        return BY_SYMBOL[symbol].name
    return hint or symbol.removesuffix(".NS").removesuffix(".BO")


def quote(symbol: str, src: Source | None = None, name: str | None = None) -> Quote | None:
    src = src or Yahoo()
    closes = src.closes(symbol, 1)
    if len(closes) < 2:
        return None
    info = src.info(symbol)
    year = closes[closes.index >= closes.index[-1] - pd.Timedelta(days=YEAR_DAYS)]
    low, high = info.get("low_52w"), info.get("high_52w")
    return Quote(
        symbol, name_of(symbol, name), exchange_name(symbol, info.get("exchange")),
        str(info.get("currency") or currency_of(symbol, src)).upper(),
        float(closes.iloc[-1]), float(closes.iloc[-2]),
        float(low) if low else float(year.min()), float(high) if high else float(year.max()),
        closes.index[-1].date(), year,
    )  # fmt: skip


def history(symbol: str, years: float, src: Source | None = None,
            name: str | None = None) -> History | None:  # fmt: skip
    src = src or Yahoo()
    closes = src.closes(symbol, years)
    if len(closes) < 2:
        return None
    start = closes.index[-1] - pd.Timedelta(days=round(years * YEAR_DAYS))
    span = closes[closes.index >= start]
    return History(symbol, name_of(symbol, name), currency_of(symbol, src), span)


def drawdowns(closes: pd.Series, k: int = MAX_FALLS) -> list[Fall]:
    """The worst peak-to-trough falls that don't overlap, worst first, each with the day it got
    back to its peak, or None when it hasn't yet."""
    falls: list[Fall] = []
    days = [d.date() for d in closes.index]
    peak, peak_day = float(closes.iloc[0]), days[0]
    trough, trough_day = peak, peak_day
    for v, day in zip(closes.to_numpy()[1:], days[1:], strict=True):
        if v >= peak:
            if trough < peak * (1 - MIN_FALL):
                falls.append(Fall(1 - trough / peak, peak_day, trough_day, day))
            peak, peak_day, trough, trough_day = float(v), day, float(v), day
        elif v < trough:
            trough, trough_day = float(v), day
    if trough < peak * (1 - MIN_FALL):
        falls.append(Fall(1 - trough / peak, peak_day, trough_day, None))
    return sorted(falls, key=lambda f: -f.fall)[:k]


def indices_in(text: str) -> list[str]:
    """Indices named in the text, in the order written. Each match is blanked before the next
    looks, so "bank nifty" is Nifty Bank and not also Nifty 50."""
    left = text.lower()
    found: list[tuple[int, str]] = []
    for i in INDICES:
        m = re.search(rf"(?<![a-z])(?:{i.words})(?![a-z])", left)
        if m:
            found.append((m.start(), i.symbol))
            left = left[: m.start()] + " " * (m.end() - m.start()) + left[m.end() :]
    return [symbol for _, symbol in sorted(found)]


@dataclass(frozen=True)
class Found:
    symbol: str
    name: str | None  # the source's long name, when the search gave one


def _pick(quotes: Sequence[dict], currency: str | None) -> Found | None:
    """The listing for this reader: NSE first for a rupee reader, then BSE; a US share first
    for a dollar reader. Shares and ETFs only."""
    kept = [q for q in quotes if q.get("quoteType") in ("EQUITY", "ETF") and q.get("symbol")]
    indian = [q for q in kept if str(q["symbol"]).endswith((".NS", ".BO"))]
    us = [q for q in kept if "." not in str(q["symbol"])]
    nse = [q for q in indian if str(q["symbol"]).endswith(".NS")]
    order = (nse + indian + us) if (currency or "INR") == "INR" else (us + nse + indian)
    if not order:
        return None
    top = order[0]
    name = top.get("longname") or top.get("shortname")
    return Found(str(top["symbol"]), str(name).strip() if name else None)


def candidates(text: str) -> list[str]:
    """The words left once question words are gone, in order, as the phrases to look up: each
    run of kept words is one name ("hdfc bank", "tata motors")."""
    runs, run = [], []
    for w in WORD.findall(text.lower()):
        if w in STOP or len(w) < 2:
            if run:
                runs.append(" ".join(run))
            run = []
        else:
            run.append(w)
    if run:
        runs.append(" ".join(run))
    return runs


def resolve(text: str, currency: str | None, src: Source | None = None) -> tuple[Found, ...]:
    """Every index, alias and searchable name the text mentions: indices and aliases first,
    then names the source's search finds."""
    src = src or Yahoo()
    found = [Found(s, BY_SYMBOL[s].name) for s in indices_in(text)]
    lowered = text.lower()
    for words, (symbol, name) in ALIASES.items():
        if re.search(rf"\b(?:{words})\b", lowered) and symbol not in {f.symbol for f in found}:
            found.append(Found(symbol, name))
    named = {re.sub(r"[^a-z]", "", f.name.lower()) for f in found if f.name}
    for phrase in candidates(text):
        squashed = phrase.replace(" ", "")
        if any(squashed in n or n in squashed for n in named) or any(
            re.fullmatch(rf"(?:{w})", phrase) for w in [*ALIASES, *(i.words for i in INDICES)]
        ):
            continue
        try:
            hit = _pick(src.search(phrase), currency)
        except Exception:  # noqa: BLE001 - a search that fails finds nothing; never a guess
            hit = None
        if hit and hit.symbol not in {f.symbol for f in found}:
            found.append(hit)
    return tuple(found)


YEARS: Final = re.compile(
    r"(?:last|past|over|pichhle|pichle|पिछले)\s+(\d{1,2}|one|two|three|five|ten)\s*"
    r"(?:years?|yrs?|saal|साल)|(\d{1,2})\s*(?:years?|yrs?|saal|साल)",
    re.I,
)
WORD_YEARS: Final = {"one": 1, "two": 2, "three": 3, "five": 5, "ten": 10}


def years_asked(text: str) -> int | None:
    m = YEARS.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    n = WORD_YEARS.get(raw.lower(), None) or int(raw)
    return max(1, min(n, MAX_YEARS))
