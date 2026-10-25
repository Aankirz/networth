"""Every Phase 5 eval but the vault, offline from cached outputs unless --live.

Run: uv run python -m evals                    (or make evals)
     uv run python -m evals --live news words  (rerun the named paid evals first)
     uv run python -m evals --live             (rerun every paid eval first)

The walk-forward is recomputed when data/ holds the prices and the pre-2022 table, and must
match evals/results/walkforward.json; from a clean clone the cached file is used. The news,
words and trace evals are rescored from their cached raw outputs; --live reruns their model
calls first. The vault is read from evals/results/vault.json, never run from here.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from evals import news, report, spend, trace, words
from evals import walkforward as wf
from networth.app.services import Services
from networth.app.settings import ENV_FILE, read_dotenv
from networth.app.store import Store
from networth.config import DATA_DIR, load_config
from networth.engine import fetch
from networth.engine.model import PRE_VAULT_DB
from networth.llm import OpenAIModels
from networth.watcher.pull import ExaSearch

RESULTS: Final = Path(__file__).with_name("results")
WALKFORWARD_JSON: Final = RESULTS / "walkforward.json"
PAID: Final = ("news", "words", "trace")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def walkforward() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        dbs = [(c, wf.build_before(c, Path(tmp) / f"{c.year}.sqlite")) for c in wf.CUTOFFS]
        scored = wf.walk(wf.universe(), dbs, PRE_VAULT_DB)
    return {"cutoffs": [c.isoformat() for c in wf.CUTOFFS], "end": wf.WALK_END.isoformat(),
            "statements": len(scored), "per_row": wf.per_row(scored, PRE_VAULT_DB),
            "by_lean": wf.by_lean(scored), "calibration": wf.calibration(scored),
            "scored": wf.scored_json(scored)}  # fmt: skip


def walkforward_stage() -> dict:
    cached = read_json(WALKFORWARD_JSON)
    if not (PRE_VAULT_DB.exists() and any(fetch.PRICES_DIR.glob("*.csv"))):
        if cached is None:
            raise SystemExit("no data/ and no cached walkforward.json")
        print("walk-forward: no data/, using the cached result")
        return cached
    fresh = walkforward()
    if cached is not None and cached != fresh:
        raise SystemExit("walk-forward differs from the cached result; rerun with --refresh")
    if cached is None:
        write_json(WALKFORWARD_JSON, fresh)
    print(f"walk-forward: recomputed {fresh['statements']} statements, matches the cache")
    return fresh


def live_services() -> Services:
    cfg = load_config()
    env = {**read_dotenv(ENV_FILE), **os.environ}
    return Services(DATA_DIR, None, OpenAIModels(cfg, spend.CALL_LOG),
                    ExaSearch(cfg, spend.CALL_LOG), cfg, env)  # fmt: skip


def live(name: str) -> dict:
    services = live_services()
    if name == "news":
        return news.run(news.load_labels(), services.cfg, services.models, services.env)
    if name == "words":
        return words.run(services, Store(DATA_DIR / "evals_words"))
    return trace.run(services)


SCORERS: Final[dict[str, Callable[[dict], dict]]] = {
    "news": lambda raw: news.score(news.load_labels(), raw),
    "words": words.score,
    "trace": trace.score,
}


def paid_stage(name: str, rerun: bool) -> dict | None:
    raw_path = RESULTS / f"{name}_raw.json"
    if rerun:
        write_json(raw_path, live(name))
        print(f"{name}: ran live, phase spend now ${spend.phase_usd():.2f}")
    raw = read_json(raw_path)
    if raw is None:
        print(f"{name}: no cached run yet; run with --live {name}")
        return None
    scores = SCORERS[name](raw)
    write_json(RESULTS / f"{name}.json", scores)
    return scores


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", nargs="*", choices=PAID, default=None,
                        help="rerun these paid evals first (all when none are named)")  # fmt: skip
    parser.add_argument("--refresh", action="store_true", help="rewrite walkforward.json")
    args = parser.parse_args(argv)
    rerun = set() if args.live is None else set(args.live or PAID)
    if args.refresh:
        WALKFORWARD_JSON.unlink(missing_ok=True)
    results = {"walkforward": walkforward_stage(), "vault": read_json(RESULTS / "vault.json")}
    results |= {name: paid_stage(name, name in rerun) for name in PAID}
    results["spend_usd"] = round(spend.phase_usd(), 4) if spend.CALL_LOG.exists() else None
    write_json(RESULTS / "summary.json", report.summary(results, dt.date.today()))
    report.write(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
