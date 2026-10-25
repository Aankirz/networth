"""Phase 5's model spend, counted from data/llm_calls.jsonl after the rows earlier phases wrote.

spend.check()          # raises Over before a call that could pass the stop line
spend.phase_usd()      # every row after BASELINE_ROWS
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from networth.config import DATA_DIR

CALL_LOG: Final = DATA_DIR / "llm_calls.jsonl"
BASELINE_ROWS: Final = 334  # rows before Phase 5's first call (docs/phases/phase-5-plan.md)
CAP_USD: Final = 15.0
STOP_USD: Final = 14.0  # a dollar of margin under the cap for calls already in flight


class Over(RuntimeError):
    """Phase 5 spend reached STOP_USD."""


def rows(path: Path = CALL_LOG) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def phase_usd(path: Path = CALL_LOG) -> float:
    return sum(r.get("cost_usd") or 0.0 for r in rows(path)[BASELINE_ROWS:])


def since(start: int, path: Path = CALL_LOG) -> list[dict]:
    """The call rows appended after row number `start`."""
    return rows(path)[start:]


def check(path: Path = CALL_LOG) -> None:
    usd = phase_usd(path)
    if usd >= STOP_USD:
        raise Over(f"phase 5 spend is ${usd:.2f}, at the ${STOP_USD:.0f} stop line")
