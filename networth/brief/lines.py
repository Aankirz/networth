"""One engine row as a history line, in English, Hindi or Hinglish.

    line = odds_line("rbi_hike", row, row["n_episodes"], row["weak_signal"])
    line.words("hinglish")   # "Pichhle 22 RBI rate hikes mein se 14 ke baad ..."

A line states a count and the normal rate, nothing more. When the count sits within
NEAR_NORMAL of the normal rate it says so ("within normal ups and downs"); otherwise it says
nothing about direction. Under 8 episodes it says the count is too small to call a pattern.
Every number is the engine's, formatted by code. The brief, alerts, watch messages and chat
answers all word their history lines here.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from networth.bot.message import say
from networth.engine import odds as engine
from networth.engine.model import EventType
from networth.web import names
from networth.web.fmt import percent

NEAR_NORMAL: Final = names.NEAR_NORMAL


@dataclass(frozen=True)
class TypeWords:
    title: str  # the event in a news line: "RBI rate hike"
    counted: str  # past episodes, counted: "{n} past RBI rate hikes"


TYPE_WORDS: Final[Mapping[str, Mapping[str, TypeWords]]] = {
    "en": {t: TypeWords(n.title, f"{{n}} {n.plural}") for t, n in names.TYPES.items()},
    "hi": {
        EventType.OIL_SUPPLY: TypeWords("तेल सप्लाई का झटका", "पिछले {n} तेल सप्लाई झटकों"),
        EventType.FED_HIKE: TypeWords("US Fed की दर बढ़ोतरी", "पिछली {n} US Fed दर बढ़ोतरियों"),
        EventType.FED_CUT: TypeWords("US Fed की दर कटौती", "पिछली {n} US Fed दर कटौतियों"),
        EventType.RBI_HIKE: TypeWords("RBI की दर बढ़ोतरी", "पिछली {n} RBI दर बढ़ोतरियों"),
        EventType.RBI_CUT: TypeWords("RBI की दर कटौती", "पिछली {n} RBI दर कटौतियों"),
        EventType.UNION_BUDGET: TypeWords("यूनियन बजट", "पिछले {n} यूनियन बजटों"),
        EventType.INR_SHOCK: TypeWords("रुपये में तेज़ गिरावट", "रुपये की पिछली {n} तेज़ गिरावटों"),
        EventType.MILITARY_CONFLICT: TypeWords("सैन्य संघर्ष", "पिछले {n} सैन्य संघर्षों"),
        EventType.TARIFF: TypeWords("टैरिफ़ का फ़ैसला", "पिछले {n} टैरिफ़ फ़ैसलों"),
        EventType.BANK_STRESS: TypeWords("बैंकों पर दबाव", "बैंकों पर दबाव के पिछले {n} दौरों"),
        EventType.PANDEMIC: TypeWords("महामारी का डर", "महामारी के डर के पिछले {n} दौरों"),
        EventType.ELECTION: TypeWords("चुनाव", "पिछले {n} चुनावों"),
    },
    "hinglish": {
        EventType.OIL_SUPPLY: TypeWords("Oil supply shock", "pichhle {n} oil supply shocks"),
        EventType.FED_HIKE: TypeWords("US Fed rate hike", "pichhle {n} US Fed rate hikes"),
        EventType.FED_CUT: TypeWords("US Fed rate cut", "pichhle {n} US Fed rate cuts"),
        EventType.RBI_HIKE: TypeWords("RBI rate hike", "pichhle {n} RBI rate hikes"),
        EventType.RBI_CUT: TypeWords("RBI rate cut", "pichhle {n} RBI rate cuts"),
        EventType.UNION_BUDGET: TypeWords("Union Budget", "pichhle {n} Union Budgets"),
        EventType.INR_SHOCK: TypeWords("Rupee mein tez giravat", "pichhle {n} sharp rupee falls"),
        EventType.MILITARY_CONFLICT: TypeWords("Military conflict",
                                               "pichhle {n} military conflicts"),
        EventType.TARIFF: TypeWords("Tariff move", "pichhle {n} tariff moves"),
        EventType.BANK_STRESS: TypeWords("Bank stress", "bank stress ke pichhle {n} daur"),
        EventType.PANDEMIC: TypeWords("Pandemic ka darr", "pandemic scare ke pichhle {n} daur"),
        EventType.ELECTION: TypeWords("Election", "pichhle {n} elections"),
    },
}  # fmt: skip
for _lang, _table in TYPE_WORDS.items():
    if set(_table) != set(EventType):
        raise RuntimeError(f"TYPE_WORDS[{_lang}] must name every EventType")

# Hindi and Hinglish names for the assets an Indian brief shows; any other asset keeps its
# English name, which is a proper name anyway ("US banks and finance (XLF)").
ASSET_WORDS: Final[Mapping[str, Mapping[str, str]]] = {
    "hi": {
        "^NSEI": "Nifty 50", "^BSESN": "Sensex",
        "NIFTYBEES.NS": "Nifty 50 इंडेक्स फ़ंड (NIFTYBEES)",
        "GOLDBEES.NS": "रुपये में सोना (GOLDBEES)", "INR=X": "रुपये में डॉलर (USD/INR)",
        "^NSEBANK": "भारतीय बैंक (Nifty Bank)", "^CNXPSUBANK": "सरकारी बैंक (Nifty PSU Bank)",
        "^CNXIT": "भारतीय IT (Nifty IT)", "^CNXAUTO": "भारतीय कार कंपनियाँ (Nifty Auto)",
        "^CNXENERGY": "भारतीय ऊर्जा (Nifty Energy)", "^CNXFMCG": "रोज़मर्रा का सामान (Nifty FMCG)",
        "^CNXINFRA": "भारतीय इंफ़्रा (Nifty Infra)", "^CNXMETAL": "भारतीय मेटल (Nifty Metal)",
        "^CNXPHARMA": "भारतीय फ़ार्मा (Nifty Pharma)",
        "^CNXREALTY": "भारतीय रियल एस्टेट (Nifty Realty)",
        "BZ=F": "ब्रेंट कच्चा तेल", "GLD": "डॉलर में सोना (GLD)",
    },
    "hinglish": {
        "^NSEI": "Nifty 50", "^BSESN": "Sensex",
        "NIFTYBEES.NS": "Nifty 50 index fund (NIFTYBEES)",
        "GOLDBEES.NS": "Rupee mein gold (GOLDBEES)", "INR=X": "Rupee mein dollar (USD/INR)",
        "^NSEBANK": "Indian banks (Nifty Bank)", "^CNXPSUBANK": "Sarkari banks (Nifty PSU Bank)",
        "^CNXIT": "Indian IT (Nifty IT)", "^CNXAUTO": "Indian car companies (Nifty Auto)",
        "^CNXENERGY": "Indian energy (Nifty Energy)",
        "^CNXFMCG": "Rozmarra ka saamaan (Nifty FMCG)", "^CNXINFRA": "Indian infra (Nifty Infra)",
        "^CNXMETAL": "Indian metals (Nifty Metal)", "^CNXPHARMA": "Indian pharma (Nifty Pharma)",
        "^CNXREALTY": "Indian real estate (Nifty Realty)",
        "BZ=F": "Brent crude oil", "GLD": "Dollar mein gold (GLD)",
    },
}  # fmt: skip
BENCHMARK_WORDS: Final[Mapping[str, Mapping[str, str]]] = {
    "hi": {"^NSEI (^BSESN before 2007-09-17)": "Nifty 50", "SPY": "S&P 500",
           "FF:Mkt": "अमेरिकी बाज़ार (1926 से डेटा)"},
    "hinglish": {"^NSEI (^BSESN before 2007-09-17)": "Nifty 50", "SPY": "S&P 500",
                 "FF:Mkt": "US market (1926 se data)"},
}  # fmt: skip

BEAT: Final = {
    "en": "{asset} beat {bench} in {hits} of {counted}.",
    "hi": "{counted} में से {hits} के बाद {asset} ने {bench} से बेहतर किया।",
    "hinglish": "{counted} mein se {hits} ke baad {asset} ne {bench} se behtar kiya.",
}
ROSE: Final = {
    "en": "{asset} rose in {hits} of {counted}.",
    "hi": "{counted} में से {hits} के बाद {asset} में तेज़ी रही।",
    "hinglish": "{counted} mein se {hits} ke baad {asset} mein tezi rahi.",
}
NORMAL: Final = {
    "en": "Normal is {base}.",
    "hi": "सामान्य समय में यह {base} होता है।",
    "hinglish": "Normal waqt mein yeh {base} hota hai.",
}
NORMAL_AND_NEAR: Final = {
    "en": "Normal is {base}, so this is within normal ups and downs.",
    "hi": "सामान्य समय में यह {base} होता है, तो यह आम उतार-चढ़ाव के भीतर है।",
    "hinglish": "Normal waqt mein yeh {base} hota hai, toh yeh aam utaar-chadhaav ke andar hai.",
}
TOO_FEW: Final = {
    "en": "Only {n} past cases, too few to call a pattern.",
    "hi": "सिर्फ़ {n} पुराने मामले हैं, पैटर्न कहने के लिए बहुत कम।",
    "hinglish": "Sirf {n} purane cases hain, pattern kehne ke liye bahut kam.",
}
HINDI_MONTHS: Final = ("जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
                       "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर")  # fmt: skip


def lang_of(lang: str | None) -> str:
    return lang if lang in TYPE_WORDS else "en"


def type_words(type: str, lang: str | None) -> TypeWords:
    return TYPE_WORDS[lang_of(lang)][type]


def asset_words(asset: str, lang: str | None) -> str:
    return ASSET_WORDS.get(lang_of(lang), {}).get(asset) or names.asset_name(asset)


def benchmark_words(benchmark: str, lang: str | None) -> str:
    local = BENCHMARK_WORDS.get(lang_of(lang), {}).get(benchmark)
    return local or names.benchmark_name(benchmark)


def day_words(day: dt.date, lang: str | None) -> str:
    """ "Oct 20", "20 अक्टूबर", "20 Oct"."""
    lang = lang_of(lang)
    if lang == "hi":
        return f"{day.day} {HINDI_MONTHS[day.month - 1]}"
    return f"{day.day} {day:%b}" if lang == "hinglish" else f"{day:%b} {day.day}"


@dataclass(frozen=True)
class Line:
    """One engine row, kept as numbers so it can be worded in any language."""

    type: str
    asset: str
    measure: str
    benchmark: str
    n: int
    hits: int
    hit_rate: float
    baseline: float
    weak: bool

    @property
    def near_normal(self) -> bool:
        return abs(self.hit_rate - self.baseline) < NEAR_NORMAL

    def words(self, lang: str | None) -> str:
        lang = lang_of(lang)
        counted = type_words(self.type, lang).counted.format(n=self.n)
        claim = say(ROSE if self.measure == "raw" else BEAT, lang).format(
            asset=asset_words(self.asset, lang), bench=benchmark_words(self.benchmark, lang),
            hits=self.hits, counted=counted)  # fmt: skip
        normal = say(NORMAL_AND_NEAR if self.near_normal and not self.weak else NORMAL, lang)
        parts = [claim[0].upper() + claim[1:], normal.format(base=percent(self.baseline))]
        if self.weak:
            parts.append(say(TOO_FEW, lang).format(n=self.n))
        return " ".join(parts)


def odds_line(type: str, row: engine.CompareAssetJSON | engine.OddsJSON, n: int,
              weak: bool) -> Line:  # fmt: skip
    return Line(type, row["asset"], row["measure"], row["benchmark"], n, int(row["n_hits"]),
                float(row["hit_rate"]), float(row["baseline"]), weak)  # fmt: skip
