"""One rater per kind: a share, a fund or ETF, an upcoming IPO. Each returns its drivers and
what was missing; rate() in __init__ turns them into a Rating.

    got = rate_stock(info, src, now)    # Rated(drivers, missing, ...)
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from networth.ratings import score
from networth.ratings.model import Driver, Source, money
from networth.ratings.score import Missing, Scored, clip, pct
from networth.ratings.sources import Closes, IpoListing, Sources, StockInfo, mentions
from networth.ratings.track import (
    CATEGORY_INDEX,
    FUNDS,
    INDEX_NAMES,
    MARKET_INDEX,
    category_of,
)

RHP_FACTS: Final = Path(__file__).with_name("ipo_rhp.json")
NEWS_DAYS: Final = 30

STOCK_WEIGHTS: Final = {
    "growth": 0.2,
    "valuation": 0.15,
    "debt": 0.1,
    "momentum": 0.25,
    "news": 0.1,
    "sector": 0.2,
}
FUND_WEIGHTS: Final = {
    "benchmark": 0.3,
    "category": 0.2,
    "consistency": 0.25,
    "expense": 0.15,
    "holdings": 0.1,
}
IPO_WEIGHTS: Final = {
    "valuation": 0.3,
    "financials": 0.25,
    "fresh": 0.15,
    "use": 0.15,
    "subscription": 0.15,
}
LENDERS: Final = re.compile(r"^(Banks|Credit Services|Mortgage Finance|Insurance)", re.I)
INDEX_NAMES_ALL: Final = {**INDEX_NAMES, "^GSPC": "S&P 500"}

# Peers by Yahoo industry: the larger listed names in the same line of business. Their
# multiples are read live from Yahoo; only the list is ours.
PEERS: Final[dict[str, tuple[str, ...]]] = {
    "Banks - Regional": ("HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS"),
    "Internet Retail": ("ETERNAL.NS", "NYKAA.NS", "SWIGGY.NS"),
    "Information Technology Services": ("TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"),
    "Drug Manufacturers - Specialty & Generic": ("SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS"),
    "Auto Manufacturers": ("MARUTI.NS", "M&M.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS"),
    "Household & Personal Products": ("HINDUNILVR.NS", "DABUR.NS", "MARICO.NS"),
    "Steel": ("TATASTEEL.NS", "JSWSTEEL.NS", "JINDALSTEL.NS"),
    "Oil & Gas Refining & Marketing": ("RELIANCE.NS", "BPCL.NS", "IOC.NS"),
    "Consumer Electronics": ("AAPL", "SONY"),
    "Software - Infrastructure": ("MSFT", "ORCL", "ADBE"),
    "Semiconductors": ("NVDA", "AMD", "INTC", "AVGO"),
    "Internet Content & Information": ("GOOGL", "META"),
}
# NSE sector indices by Yahoo industry first, then sector. US names use the SPDR sector ETFs.
IN_INDUSTRY: Final = {
    "Banks - Regional": ("^NSEBANK", "Nifty Bank"),
    "Auto Manufacturers": ("^CNXAUTO", "Nifty Auto"),
    "Auto Parts": ("^CNXAUTO", "Nifty Auto"),
}
IN_SECTOR: Final = {
    "Technology": ("^CNXIT", "Nifty IT"),
    "Healthcare": ("^CNXPHARMA", "Nifty Pharma"),
    "Consumer Defensive": ("^CNXFMCG", "Nifty FMCG"),
    "Basic Materials": ("^CNXMETAL", "Nifty Metal"),
    "Energy": ("^CNXENERGY", "Nifty Energy"),
    "Utilities": ("^CNXENERGY", "Nifty Energy"),
    "Real Estate": ("^CNXREALTY", "Nifty Realty"),
}
US_SECTOR: Final = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}


@dataclass(frozen=True)
class Rated:
    name: str
    symbol: str
    kind: str
    currency: str
    market: str  # "in" | "us"
    drivers: tuple[Driver, ...]
    missing: tuple[Missing, ...]
    weights: dict[str, float]


def split(scored: Sequence[Scored]) -> tuple[tuple[Driver, ...], tuple[Missing, ...]]:
    return (
        tuple(s for s in scored if isinstance(s, Driver)),
        tuple(s for s in scored if isinstance(s, Missing)),
    )


def short_name(name: str) -> str:
    """'HDFC Bank Limited' -> 'HDFC Bank'; 'X Fund - Direct Plan - Growth' -> 'X Fund'."""
    name = name.split(" - ")[0]
    return re.sub(r"\s+(Limited|Ltd\.?|Inc\.?|Corporation|Corp\.?|plc)$", "", name, flags=re.I)


def news_scored(src: Sources, words: Sequence[str], now: dt.datetime, weight: float) -> Scored:
    stories = src.stories(now - dt.timedelta(days=NEWS_DAYS))
    if stories is None:
        return score.news_driver(None, None, weight)
    found = mentions(stories.items, words)
    return score.news_driver([(s.title, s.type) for s in found], stories.source, weight)


def peer_multiples(
    info: StockInfo, src: Sources
) -> tuple[str, list[tuple[str, float]], float | None]:
    """(measure, [(peer, multiple)], own multiple): P/E, or P/B when it has no earnings."""
    peers = [p for p in PEERS.get(info.industry or "", ()) if p != info.ticker]
    got = [(p, src.stock(p)) for p in peers]
    use_pe = info.pe is not None and info.pe > 0
    vals = [(i.symbol, i.pe if use_pe else i.pb) for _, i in got if i is not None]
    return (
        "P/E" if use_pe else "P/B",
        [(n, v) for n, v in vals if v],
        info.pe if use_pe else info.pb,
    )


def sector_of(info: StockInfo) -> tuple[str, str] | None:
    if info.currency == "USD":
        etf = US_SECTOR.get(info.sector or "")
        return (etf, f"US {info.sector} ({etf})") if etf else None
    return IN_INDUSTRY.get(info.industry or "") or IN_SECTOR.get(info.sector or "")


def rate_stock(info: StockInfo, src: Sources, now: dt.datetime) -> Rated:
    w = STOCK_WEIGHTS
    market = "us" if info.currency == "USD" else "in"
    bench_ticker = MARKET_INDEX[market]
    own, bench = src.closes(info.ticker), src.closes(bench_ticker)
    bench_name = INDEX_NAMES_ALL[bench_ticker]
    measure, peers, mine = peer_multiples(info, src)
    sector = sector_of(info)
    sector_closes = src.closes(sector[0]) if sector else None
    scored: list[Scored] = [
        score.growth_driver(
            info.revenue_growth, info.earnings_growth, info.margin, info.source, w["growth"]
        ),
        score.valuation_driver(mine, peers, measure, info.source, w["valuation"]),
        score.debt_driver(
            info.debt_to_equity, bool(LENDERS.match(info.industry or "")), info.source, w["debt"]
        ),
        (
            score.momentum_driver(own.series, bench.series, own.source, bench_name, w["momentum"])
            if own and bench
            else Missing("momentum", "Price momentum: no price history.")
        ),
        news_scored(src, [info.symbol, short_name(info.name)], now, w["news"]),
        (
            score.sector_driver(
                sector_closes.series if sector_closes else None,
                bench.series,
                sector[1] if sector else None,
                sector_closes.source if sector_closes else None,
                w["sector"],
            )
            if bench
            else Missing("sector", "Sector trend: no market history.")
        ),
    ]
    if market == "us" and isinstance(scored[-1], Driver):
        scored[-1] = Driver(
            scored[-1].key,
            scored[-1].label,
            scored[-1].value.replace("Nifty 50", "S&P 500"),
            scored[-1].score,
            scored[-1].weight,
            scored[-1].source,
        )
    drivers, missing = split(scored)
    return Rated(
        info.name,
        info.symbol,
        "etf" if info.is_fund else "stock",
        info.currency,
        market,
        drivers,
        missing,
        w,
    )


def fund_drivers(
    navs: Closes, bench: Closes | None, bench_name: str, peers: Sequence[tuple[str, Closes]]
) -> list[Scored]:
    w = FUND_WEIGHTS
    s = navs.series
    if bench is None:
        out: list[Scored] = [
            Missing("benchmark", "Returns against the benchmark: no index history."),
            Missing("consistency", "Consistency: no index history."),
        ]
    else:
        out = [
            score.excess_driver(
                "benchmark",
                "Returns against the benchmark",
                score.cagr(s, 3),
                score.cagr(bench.series, 3),
                f"the {bench_name}",
                3,
                navs.source,
                w["benchmark"],
            ),
            score.consistency_driver(s, bench.series, navs.source, bench_name, w["consistency"]),
        ]
    peer_cagrs = [c for _, p in peers if (c := score.cagr(p.series, 3)) is not None]
    if len(peer_cagrs) >= 2:
        out.append(
            score.excess_driver(
                "category",
                "Returns against its category",
                score.cagr(s, 3),
                statistics.median(peer_cagrs),
                f"the median of {len(peer_cagrs)} category peers",
                3,
                navs.source,
                w["category"],
            )
        )
    else:
        out.append(Missing("category", "Returns against its category: too few peers we track."))
    out.append(Missing("expense", "Expense ratio: no free source we can read yet."))
    out.append(Missing("holdings", "Holdings mix: the fund's monthly portfolio isn't read yet."))
    return out


def rate_fund(code: int, src: Sources) -> Rated | None:
    got = src.fund_navs(code)
    if got is None:
        return None
    name, navs = got
    cat = FUNDS.get(code) or category_of(name)
    bench_ticker = CATEGORY_INDEX[cat]
    peers = []
    for c in (c for c, k in FUNDS.items() if k == cat and c != code):
        p = src.fund_navs(c)
        if p is not None:
            peers.append(p)
    scored = fund_drivers(navs, src.closes(bench_ticker), INDEX_NAMES_ALL[bench_ticker], peers)
    drivers, missing = split(scored)
    return Rated(name, f"MF{code}", "fund", "INR", "in", drivers, missing, FUND_WEIGHTS)


def rate_etf(info: StockInfo, src: Sources) -> Rated:
    market = "us" if info.currency == "USD" else "in"
    bench_ticker = (
        MARKET_INDEX[market] if market == "us" else CATEGORY_INDEX[category_of(info.name)]
    )
    own = src.closes(info.ticker)
    if own is None:
        scored: list[Scored] = [Missing("benchmark", "Returns against the benchmark: no history.")]
    else:
        scored = fund_drivers(own, src.closes(bench_ticker), INDEX_NAMES_ALL[bench_ticker], ())
    drivers, missing = split(scored)
    return Rated(
        info.name, info.symbol, "etf", info.currency, market, drivers, missing, FUND_WEIGHTS
    )


# --- IPOs ----------------------------------------------------------------------------------


def rhp_facts(symbol: str, path: Path = RHP_FACTS) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")).get(symbol.upper())


def cap_price(band: str) -> float | None:
    nums = re.findall(r"\d+(?:\.\d+)?", band.replace(",", ""))
    return float(nums[-1]) if nums else None


def rhp_source(facts: dict, pages: str) -> Source:
    return Source(f"Red Herring Prospectus, {pages}", facts["rhp_url"], facts["read_at"])


def ipo_drivers(
    listing: IpoListing, facts: dict | None, subscribed: float | None, nse: Source
) -> list[Scored]:
    w = IPO_WEIGHTS
    if facts is None:
        gap = "the RHP's numbers are not read in yet"
        return [
            Missing("valuation", f"Valuation against listed peers: {gap}."),
            Missing("financials", f"Financials: {gap}."),
            Missing("fresh", f"Fresh issue against OFS: {gap}."),
            Missing("use", f"Use of the money: {gap}."),
            Missing("subscription", "Subscription: not live yet."),
        ]
    cap = cap_price(listing.price_band)
    eps, peer = facts["diluted_eps_fy2026"]["value"], facts["peer_pe"]
    out: list[Scored] = []
    if cap and eps > 0:
        pe = cap / eps
        out.append(
            Driver(
                "valuation",
                "Valuation against listed peers",
                f"P/E {pe:.1f} at the top of the {listing.price_band} band against a "
                f"listed-peer average of {peer['average']:.1f} (range "
                f"{peer['lowest']:.1f} to {peer['highest']:.1f})",
                score.ratio_score(pe / peer["average"]),
                w["valuation"],
                rhp_source(
                    facts,
                    f"pages {facts['diluted_eps_fy2026']['page']} and "
                    f"{peer['page']}; price band from NSE",
                ),
            )
        )
    else:
        out.append(Missing("valuation", "Valuation against listed peers: no price band yet."))
    rev, pat = facts["revenue"], facts["pat"]
    growth = (rev["FY2026"] / rev["FY2024"]) ** 0.5 - 1
    margin = pat["FY2026"] / rev["FY2026"]
    nde = facts["net_debt_to_equity_fy2026"]["value"]
    fin = clip(45 + 125 * growth + (10 if margin > 0.15 else 0) - (15 if nde > 1 else 0))
    out.append(
        Driver(
            "financials",
            "Financials from the RHP",
            f"Revenue {pct(growth, 1)} a year from FY2024 to FY2026, profit margin "
            f"{margin * 100:.1f}% in FY2026, net debt {nde:.2f}x equity",
            fin,
            w["financials"],
            rhp_source(facts, f"page {rev['page']}"),
        )
    )
    fresh_m = facts["fresh_issue"]["value"]
    if cap:
        ofs_m = facts["ofs_shares"]["value"] * cap / 1e6
        share = fresh_m / (fresh_m + ofs_m)
        out.append(
            Driver(
                "fresh",
                "Fresh issue against offer for sale",
                f"{money(fresh_m * 1e6, 'INR')} fresh against about "
                f"{money(ofs_m * 1e6, 'INR')} sold by existing holders at the top of "
                f"the band: {share * 100:.0f}% new money",
                30 + 60 * share,
                w["fresh"],
                rhp_source(facts, f"page {facts['fresh_issue']['page']}"),
            )
        )
    else:
        out.append(Missing("fresh", "Fresh issue against OFS: no price band yet."))
    items = facts["use_of_proceeds"]["items"]
    growth_m = sum(i["amount"] or 0 for i in items if i["kind"] == "growth")
    named = "; ".join(
        f"{i['label']}{' ' + money(i['amount'] * 1e6, 'INR') if i['amount'] else ''}" for i in items
    )
    out.append(
        Driver(
            "use",
            "Use of the money raised",
            named,
            clip(40 + 50 * growth_m / fresh_m),
            w["use"],
            rhp_source(facts, f"page {facts['use_of_proceeds']['page']}"),
        )
    )
    if subscribed:
        out.append(
            Driver(
                "subscription",
                "Subscription so far",
                f"Bids for {subscribed:.2f} times the shares on offer",
                clip(40 + 15 * math.log2(1 + subscribed)),
                w["subscription"],
                nse,
            )
        )
    else:
        out.append(
            Missing("subscription", f"Subscription: bidding opens {listing.start or 'later'}.")
        )
    return out


def rate_ipo(listing: IpoListing, src: Sources) -> Rated:
    detail = src.ipo_detail(listing.symbol)
    facts = rhp_facts(listing.symbol)
    scored = ipo_drivers(
        listing,
        facts,
        detail.subscribed_times if detail else None,
        detail.source if detail else listing.source,
    )
    drivers, missing = split(scored)
    return Rated(listing.name, listing.symbol, "ipo", "INR", "in", drivers, missing, IPO_WEIGHTS)
