"""The send gate for every model-written message.

    verdict = check(text, source)                     # pure: no IO
    out = guarded(write, source, template, log)       # one rewrite, then the template

A draft passes only when (a) every number in it appears in `source`, the structured engine or
sent-content text it was written from, after normalising formats (₹1,00,000 = 1 lakh = 100000,
56%, 14 of 22, Rs5000, Devanagari digits) and number words ("fifty", "half", "twice"); (b) it
holds none of PRODUCT.md's banned words, in English, Hindi transliteration or Devanagari; and
(c) it holds no advice phrasing ("should", "recommend", "put your money", "apply", "skip",
चाहिए, Hinglish imperatives such as "daal dein" or "ruko"). Matching runs on an NFKC copy with
zero-width characters removed, and again with spaced-out letters joined ("s e l l"), so
look-alike spellings don't slip through; the text sent is never changed. A failed draft gets
one rewrite with the problems named. A second failure sends the template, which code wrote
from the same numbers. Every verdict is appended to the guard log.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

MULTIPLIERS: Final = {
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "k": 1e3, "thousand": 1e3, "million": 1e6, "mn": 1e6, "billion": 1e9, "bn": 1e9,
}  # fmt: skip
# A digit run not continuing another number: "Rs5000", "Rs.5000" and "INR5000" all count.
NUMBER: Final = re.compile(
    r"(?<!\d)(?<!\d[.,])(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(lakhs?|lac|crores?|cr|thousand|million|mn|billion|bn|k|l)(?![a-z]))?",
    re.IGNORECASE,
)
ORDINAL: Final = re.compile(r"(\d)(?:st|nd|rd|th)\b", re.IGNORECASE)
# ponytail: "one" is left out, it is mostly not a count ("one thing", "no one"); a draft that
# writes "one in three" is still caught on "three".
UNITS: Final = {w: float(i) for i, w in enumerate(
    "zero _ two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split()) if w != "_"}  # fmt: skip
TENS: Final = {w: float(10 * i) for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(), ) if w != "_"}  # fmt: skip
WORD_VALUES: Final[dict[str, tuple[float, ...]]] = {
    "half": (0.5, 50.0), "halves": (0.5, 50.0), "aadha": (0.5, 50.0), "aadhe": (0.5, 50.0),
    "आधा": (0.5, 50.0), "quarter": (0.25, 25.0), "twice": (2.0,), "double": (2.0,),
    "doubled": (2.0,), "thrice": (3.0,), "triple": (3.0,), "tripled": (3.0,),
    "hundred": (100.0,), "dugna": (2.0,), "dogna": (2.0,),
}  # fmt: skip
NUMBER_WORD: Final = re.compile(
    rf"\b(?:({'|'.join(TENS)})[\s-]+({'|'.join(UNITS)})|({'|'.join([*TENS, *UNITS])})|"
    rf"({'|'.join(WORD_VALUES)}))\b|(आधा)",
    re.IGNORECASE,
)
ZERO_WIDTH: Final = re.compile("[\u00ad\u200b-\u200f\u2060\ufeff]")
SPACED: Final = re.compile(r"(?<![^\W_])[^\W\d_](?:[\s.*_-]{1,2}[^\W\d_](?![^\W_])){2,}")
SEPARATORS: Final = re.compile(r"[\s.*_-]")

BANNED: Final = re.compile(
    r"\b(buy\w*|sell\w*|guarantee\w*|can'?t lose|cannot lose|sure[- ]?shot|multi-?baggers?|"
    r"target price|scor(e|es|ed|ing)|rank\w*|kharid\w*|khareed\w*|"
    r"bech(o|en|ein|na|do|iye|kar|ke)?|gaaranti|pakka)\b"
    r"|खरीद|बेच|गारंटी|पक्का|मल्टीबैगर",
    re.IGNORECASE,
)
# Plural nouns and pronouns that end like an imperative: "khabrein" is news, "unhein" is them.
NOT_IMPERATIVE: Final = (
    "unh|tumh|hum|inh|jinh|khabr|baat|cheez|kitaab|kitab|raat|aankh|sharton|shart"
)
ADVICE: Final = re.compile(
    r"\b(should|you must|you ought|you need to (buy|sell|invest|move|put|switch)|"
    r"recommend\w*|put your money|move (your|some|₹|\$|rs)|"
    r"consider (investing|moving|switching|adding)|"
    r"apply|applying|skip|subscribe to (it|this)|chahiye|"
    r"lagao|daal(o|ein|iye| do| dein| dijiye| lo)|nikaa?l(o|ein|iye| lo| do| dein| lijiye)|"
    r"ruk(o|iye|ein| jao| jaiye)|\w+ao mat|mat ghabra\w*|karo|kar do|kar lo|kar dein|"
    r"dein|lein|(?!\w*liye\b)\w{2,}iye|"
    rf"(?!\w*mein\b)(?!({NOT_IMPERATIVE})ein\b)\w{{2,}}ein)\b"
    r"|move ₹|चाहिए|करें|कीजिए",
    re.IGNORECASE,
)

Used = Literal["model", "rewrite", "template"]


@dataclass(frozen=True)
class Verdict:
    problems: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass(frozen=True)
class Guarded:
    text: str
    used: Used
    verdicts: tuple[Verdict, ...]


def _value(digits: str, unit: str | None) -> float:
    return round(float(digits.replace(",", "")) * MULTIPLIERS.get((unit or "").lower(), 1), 2)


def normalise(text: str) -> str:
    """The copy every rule matches: NFKC (fullwidth digits, ligatures), no zero-width marks."""
    return ZERO_WIDTH.sub("", unicodedata.normalize("NFKC", text))


def joined(text: str) -> str:
    """Spaced-out letters joined back up: "s e l l now" -> "sell now"."""
    return SPACED.sub(lambda m: SEPARATORS.sub("", m.group(0)), text)


def numbers(text: str) -> set[float]:
    """Every number in the text as a plain value. "₹1,00,000", "1 lakh" and "100000" are all
    100000.0; "56%" is 56.0; "5th" is 5.0. A sign is ignored: "−₹4,000" and "₹4,000 lower"
    describe the same figure."""
    text = ORDINAL.sub(r"\1", normalise(text))
    return {_value(m.group(1), m.group(2)) for m in NUMBER.finditer(text)}


def word_numbers(text: str) -> list[tuple[str, tuple[float, ...]]]:
    """Each number word with the values it may stand for: "twenty-five" (25), "half" (0.5 or
    50, as in "half the time" next to "50%")."""
    found = []
    for m in NUMBER_WORD.finditer(normalise(text)):
        tens, unit, single, word, devanagari = m.groups()
        if tens:
            found.append((m.group(0), (TENS[tens.lower()] + UNITS[unit.lower()],)))
        elif single:
            key = single.lower()
            found.append((single, (TENS.get(key, UNITS.get(key, 0.0)),)))
        else:
            key = (word or devanagari).lower()
            found.append((key, WORD_VALUES[key]))
    return found


def _invented_words(text: str, source: str, allowed: set[float]) -> list[str]:
    said = normalise(source).lower()
    return [w for w, values in word_numbers(text)
            if not any(v in allowed for v in values) and w.lower() not in said]  # fmt: skip


def _matches(pattern: re.Pattern[str], text: str) -> list[str]:
    seen = dict.fromkeys(m.group(0) for t in (text, joined(text)) for m in pattern.finditer(t))
    return list(seen)


def check(text: str, source: str) -> Verdict:
    allowed = numbers(source)
    invented = sorted(n for n in numbers(text) if n not in allowed)
    problems = [f"number {n:g} is not in the source" for n in invented]
    problems += [f"number word {w!r} is not in the source"
                 for w in _invented_words(text, source, allowed)]  # fmt: skip
    clean = normalise(text)
    problems += [f"banned word {w!r}" for w in _matches(BANNED, clean)]
    problems += [f"advice phrasing {w!r}" for w in _matches(ADVICE, clean)]
    return Verdict(tuple(problems))


def log_verdict(path: Path | None, kind: str, attempt: Used, verdict: Verdict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "kind": kind,
           "attempt": attempt, "ok": verdict.ok, "problems": list(verdict.problems)}  # fmt: skip
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


Write = Callable[[str | None], str]  # feedback on the last draft (None first) -> a new draft


def guarded(write: Write, source: str, template: str, log_path: Path | None, kind: str) -> Guarded:
    """The model's draft if it passes, else one rewrite told what failed, else the template.
    A model that raises counts as a failed draft, so the user still gets the template."""
    verdicts: list[Verdict] = []
    feedback: str | None = None
    for attempt in ("model", "rewrite"):
        try:
            draft = write(feedback)
        except Exception as exc:  # noqa: BLE001 - any model failure falls through to the template
            draft, verdict = "", Verdict((f"writer failed: {type(exc).__name__}",))
        else:
            verdict = check(draft, source)
        verdicts.append(verdict)
        log_verdict(log_path, kind, attempt, verdict)
        if verdict.ok:
            return Guarded(draft, attempt, tuple(verdicts))
        feedback = "; ".join(verdict.problems)
    log_verdict(log_path, kind, "template", Verdict(()))
    return Guarded(template, "template", tuple(verdicts))
