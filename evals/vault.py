"""Score the held-out vault once: what the pre-2022 table said, against every episode from 2022
on, under the procedure in docs/phases/phase-5-plan.md.

Run: uv run python -m evals.vault [--after-crash REASON]

It refuses to run unless the plan is committed and unchanged, and both tables match the
committed events.csv. It writes evals/results/vault.json and never runs again once that file
exists. A start marker is written first, so a run that crashed can be told apart from one that
finished. Only a crashed run may be repeated, and only with the reason recorded.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from evals import walkforward as wf
from networth.config import REPO
from networth.engine.backtest import EVENTS_CSV
from networth.engine.model import DEFAULT_DB, PRE_VAULT_DB, VAULT_START

PLAN: Final = REPO / "docs" / "phases" / "phase-5-plan.md"
RESULTS: Final = REPO / "evals" / "results"
VAULT_JSON: Final = RESULTS / "vault.json"
STARTED: Final = RESULTS / "vault.started"
NO_END: Final = dt.date.max


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)


def plan_commit() -> str:
    """The commit that last changed the plan. Raises if it is uncommitted or edited since."""
    rel = str(PLAN.relative_to(REPO))
    sha = _git("log", "-1", "--format=%H", "--", rel).stdout.strip()
    if not sha:
        raise SystemExit(f"{rel} is not committed; commit it before the vault run")
    if _git("diff", "--quiet", "HEAD", "--", rel).returncode != 0:
        raise SystemExit(f"{rel} changed since {sha[:7]}; the vault runs on the committed plan")
    return sha


def check_tables(full: Path, pre: Path) -> str:
    csv_sha = hashlib.sha256(EVENTS_CSV.read_bytes()).hexdigest()
    for path, as_of in ((full, ""), (pre, (VAULT_START - dt.timedelta(days=1)).isoformat())):
        meta = dict(sqlite3.connect(path).execute("SELECT key, value FROM meta").fetchall())
        if meta.get("events_sha256") != csv_sha or meta.get("as_of", "") != as_of:
            raise SystemExit(f"{path} does not match events.csv or its cut; rebuild with backtest")
    return csv_sha


def vault_row(sc: wf.Scored) -> dict:
    s = sc.statement
    return {"type": s.type, "asset": s.asset, "era": s.era, "weak": s.weak, "lean": s.lean,
            "stated_n": s.n, "stated_hits": s.hits, "stated_rate": s.hit_rate,
            "baseline": s.baseline, "vault_n": sc.n, "vault_hits": sc.hits,
            "vault_rate": round(sc.hits / sc.n, 4) if sc.n else None,
            "held": wf.held(sc)}  # fmt: skip


def score(full: Path, pre: Path) -> list[wf.Scored]:
    out = []
    for type, asset in wf.universe():
        s = wf.statement(type, asset, VAULT_START, pre)
        if s is not None:
            out.append(wf.Scored(s, wf.outcomes(s, full, VAULT_START, NO_END)))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-crash", default=None, help="why a crashed run is repeated")
    args = parser.parse_args(argv)
    if VAULT_JSON.exists():
        raise SystemExit(f"{VAULT_JSON} exists: the vault is scored once")
    if STARTED.exists() and not args.after_crash:
        raise SystemExit("a previous vault run started and did not finish; rerun only with "
                         '--after-crash "<reason>"')  # fmt: skip
    sha = plan_commit()
    csv_sha = check_tables(DEFAULT_DB, PRE_VAULT_DB)
    RESULTS.mkdir(parents=True, exist_ok=True)
    STARTED.write_text(dt.datetime.now(dt.UTC).isoformat(timespec="seconds"))
    scored = score(DEFAULT_DB, PRE_VAULT_DB)
    out = {"plan_commit": sha, "events_sha256": csv_sha,
           "run_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
           "after_crash": args.after_crash, "rows": [vault_row(sc) for sc in scored],
           "by_lean": wf.by_lean(scored), "calibration": wf.calibration(scored),
           "scored": wf.scored_json(scored)}  # fmt: skip
    VAULT_JSON.write_text(json.dumps(out, indent=1) + "\n")
    STARTED.unlink()
    for row in out["by_lean"]:
        print(json.dumps(row))
    print(f"wrote {VAULT_JSON} on plan {sha[:7]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
