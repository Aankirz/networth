"""Plain words for the engine's identifiers, as tables. The pages look words up here and never
branch on a type, an asset or a market themselves."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from networth.engine.model import EraName, EventType


@dataclass(frozen=True)
class TypeName:
    plural: str
    title: str
    region: str


TYPES: Final[dict[str, TypeName]] = {
    EventType.OIL_SUPPLY: TypeName("past oil supply shocks", "Oil supply shock", "global"),
    EventType.FED_HIKE: TypeName("past US Fed rate hikes", "US Fed rate hike", "us"),
    EventType.FED_CUT: TypeName("past US Fed rate cuts", "US Fed rate cut", "us"),
    EventType.RBI_HIKE: TypeName("past RBI rate hikes", "RBI rate hike", "in"),
    EventType.RBI_CUT: TypeName("past RBI rate cuts", "RBI rate cut", "in"),
    EventType.UNION_BUDGET: TypeName("past Union Budgets", "Union Budget", "in"),
    EventType.INR_SHOCK: TypeName("past sharp rupee falls", "Sharp rupee fall", "in"),
    EventType.MILITARY_CONFLICT: TypeName("past military conflicts", "Military conflict", "global"),
    EventType.TARIFF: TypeName("past tariff moves", "Tariff move", "global"),
    EventType.BANK_STRESS: TypeName("past bank stress episodes", "Bank stress", "global"),
    EventType.PANDEMIC: TypeName("past pandemic scares", "Pandemic scare", "global"),
    EventType.ELECTION: TypeName("past elections", "Election", "global"),
}
if set(TYPES) != set(EventType):
    raise RuntimeError("names.TYPES must name every EventType")

ASSETS: Final[dict[str, str]] = {
    "^NSEI": "The Nifty 50",
    "^BSESN": "The Sensex",
    "NIFTYBEES.NS": "A Nifty 50 index fund (NIFTYBEES)",
    "GOLDBEES.NS": "Gold in rupees (GOLDBEES)",
    "INR=X": "The dollar in rupees (USD/INR)",
    "^NSEBANK": "Indian banks (Nifty Bank)",
    "^CNXPSUBANK": "Indian state-run banks (Nifty PSU Bank)",
    "^CNXIT": "Indian IT (Nifty IT)",
    "^CNXAUTO": "Indian carmakers (Nifty Auto)",
    "^CNXENERGY": "Indian energy (Nifty Energy)",
    "^CNXFMCG": "Indian everyday goods (Nifty FMCG)",
    "^CNXINFRA": "Indian infrastructure (Nifty Infra)",
    "^CNXMETAL": "Indian metals (Nifty Metal)",
    "^CNXPHARMA": "Indian pharma (Nifty Pharma)",
    "^CNXREALTY": "Indian real estate (Nifty Realty)",
    "SPY": "The S&P 500 (SPY)",
    "^GSPC": "The S&P 500 index",
    "^SP500TR": "The S&P 500 with dividends",
    "QQQ": "The Nasdaq 100 (QQQ)",
    "TLT": "Long US government bonds (TLT)",
    "GLD": "Gold in dollars (GLD)",
    "BZ=F": "Brent crude oil",
    "BTC-USD": "Bitcoin",
    "JETS": "US airlines (JETS)",
    "XLB": "US materials (XLB)",
    "XLC": "US communication services (XLC)",
    "XLE": "US energy (XLE)",
    "XLF": "US banks and finance (XLF)",
    "XLI": "US industrials (XLI)",
    "XLK": "US tech (XLK)",
    "XLP": "US everyday goods (XLP)",
    "XLRE": "US real estate (XLRE)",
    "XLU": "US utilities (XLU)",
    "XLV": "US health care (XLV)",
    "XLY": "US shopping and leisure (XLY)",
}

BENCHMARK_WORDS: Final[dict[str, str]] = {
    "^NSEI (^BSESN before 2007-09-17)": "the Nifty 50",
    "SPY": "the S&P 500",
    "FF:Mkt": "the US market (1926 data)",
}

ERA_WORDS: Final[dict[str, str]] = {
    EraName.SINCE_1998: "Since 1998",
    EraName.SINCE_1926: "Since 1926, on long-run US industry data",
    EraName.SINCE_2007: "Since 2007",
    EraName.SINCE_1997: "Since 1997, with the Sensex standing in before the Nifty",
}


@dataclass(frozen=True)
class Horizon:
    words: str
    period: str


HORIZONS: Final[dict[int, Horizon]] = {
    21: Horizon("over the next 21 trading days, about a month", "month"),
    63: Horizon("over the next 63 trading days, about three months", "three months"),
}

# Ordered high to low; the first lower bound a hit rate reaches gives the words.
ODDS_WORDS: Final[tuple[tuple[float, str], ...]] = (
    (0.90, "Almost always"),
    (0.70, "Usually"),
    (0.56, "More often than not"),
    (0.45, "A coin flip"),
    (0.30, "Less often than not"),
    (0.0, "Rarely"),
)

LEAN_GAP: Final = 0.10


class LeanKind(StrEnum):
    UP = "leans-up"
    DOWN = "leans-down"
    NONE = "no-pattern"


@dataclass(frozen=True)
class Lean:
    kind: LeanKind
    mark: str  # the text marker beside a row, so colour is never the only signal


LEANS: Final[dict[str, Lean]] = {
    "up": Lean(LeanKind.UP, "History leans toward"),
    "down": Lean(LeanKind.DOWN, "History leans against"),
    "none": Lean(LeanKind.NONE, "No clear pattern"),
    "weak": Lean(LeanKind.NONE, "Weak signal"),
}

# Display-only rewording of real headlines whose wording this site never uses.
HEADLINE_REWORDS: Final[tuple[tuple[str, str], ...]] = (("agrees to buy", "agrees to take over"),)

SCOREBOARD_MARKETS: Final[dict[str, str]] = {"in": "Indian sectors", "us": "US sectors"}

# Each group shares one data start, so compare()'s shared episodes are each asset's full row.
SCOREBOARD_GROUPS: Final[dict[str, list[tuple[str, ...]]]] = {
    "in": [
        ("^NSEBANK", "^CNXIT"),
        ("^CNXREALTY", "^CNXINFRA"),
        ("^CNXPHARMA", "^CNXFMCG"),
        ("^CNXPSUBANK", "^CNXENERGY"),
        ("^CNXAUTO", "^CNXMETAL"),
    ],
    "us": [
        ("XLF", "XLK", "XLE"),
        ("XLV", "XLY", "XLP"),
        ("XLI", "XLU", "XLB"),
        ("JETS", "XLRE"),
    ],
}


def asset_name(asset: str) -> str:
    return ASSETS.get(asset, asset)


def benchmark_name(benchmark: str) -> str:
    return BENCHMARK_WORDS.get(benchmark, benchmark)


def horizon(days: int) -> Horizon:
    return HORIZONS.get(days, Horizon(f"over the next {days} trading days", "stretch"))


def odds_words(hit_rate: float, n_episodes: int, weak_signal: bool) -> str:
    if weak_signal:
        return f"Weak signal, only {n_episodes} past cases"
    return next(words for bound, words in ODDS_WORDS if hit_rate >= bound)


def lean(hit_rate: float, baseline: float, weak_signal: bool) -> Lean:
    if weak_signal:
        return LEANS["weak"]
    gap = hit_rate - baseline
    if gap >= LEAN_GAP:
        return LEANS["up"]
    if gap <= -LEAN_GAP:
        return LEANS["down"]
    return LEANS["none"]


def reword_headline(headline: str) -> str:
    for old, new in HEADLINE_REWORDS:
        headline = headline.replace(old, new)
    return headline
