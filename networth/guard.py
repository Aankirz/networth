"""The send gate for every model-written message.

    verdict = check(text, source)                     # pure: no IO
    out = guarded(write, source, template, log)       # one rewrite, then the template

A draft passes only when (a) every number in it appears in `source`, the structured engine or
sent-content text it was written from, after normalising formats (₹1,00,000 = 1 lakh = 100000,
56%, 14 of 22, Devanagari digits); (b) it holds none of PRODUCT.md's banned words, in English,
Hindi transliteration or Devanagari; and (c) it holds no advice phrasing ("you should", "put
your money", "move ₹", "apply", "skip"). A failed draft gets one rewrite with the problems
named. A second failure sends the template, which code wrote from the same numbers. Every
verdict is appended to the guard log.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

MULTIPLIERS: Final = {
    "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "l": 1e5, "crore": 1e7, "crores": 1e7, "cr": 1e7,
    "k": 1e3, "thousand": 1e3, "million": 1e6, "mn": 1e6, "billion": 1e9, "bn": 1e9,
}  # fmt: skip
NUMBER: Final = re.compile(
    r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(lakhs?|lac|crores?|cr|thousand|million|mn|billion|bn|k|l)(?![a-z]))?",
    re.IGNORECASE,
)
ORDINAL: Final = re.compile(r"(\d)(?:st|nd|rd|th)\b", re.IGNORECASE)

BANNED: Final = re.compile(
    r"\b(buy\w*|sell\w*|guarantee\w*|can'?t lose|cannot lose|sure[- ]?shot|multi-?baggers?|"
    r"target price|kharid\w*|khareed\w*|bech(o|en|ein|na|do|iye|kar|ke)?|gaaranti|pakka)\b"
    r"|खरीद|बेच|गारंटी|पक्का|मल्टीबैगर",
    re.IGNORECASE,
)
ADVICE: Final = re.compile(
    r"\b(you should|you must|you ought|you need to (buy|sell|invest|move|put|switch)|"
    r"put your money|move (your|some|₹|\$|rs)|consider (investing|moving|switching|adding)|"
    r"apply|applying|skip|subscribe to (it|this)|aapko .{0,30}chahiye|tumhe .{0,30}chahiye|"
    r"lagao|daalo|daal do|invest karo|invest kar do|apply karo|skip karo)\b"
    r"|move ₹",
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


def numbers(text: str) -> set[float]:
    """Every number in the text as a plain value. "₹1,00,000", "1 lakh" and "100000" are all
    100000.0; "56%" is 56.0; "5th" is 5.0. A sign is ignored: "−₹4,000" and "₹4,000 lower"
    describe the same figure."""
    text = ORDINAL.sub(r"\1", text)
    return {_value(m.group(1), m.group(2)) for m in NUMBER.finditer(text)}


def check(text: str, source: str) -> Verdict:
    allowed = numbers(source)
    invented = sorted(n for n in numbers(text) if n not in allowed)
    problems = [f"number {n:g} is not in the source" for n in invented]
    problems += [f"banned word {m.group(0)!r}" for m in BANNED.finditer(text)]
    problems += [f"advice phrasing {m.group(0)!r}" for m in ADVICE.finditer(text)]
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
