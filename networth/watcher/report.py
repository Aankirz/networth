"""Print the decision log: confirmed stories with their publishers or primary source, rejected
stories with their reason, the insights' headline numbers, the latest cycle and the spend.

Run: uv run python -m networth.watcher.report            # stories first seen in the last 48 h
     uv run python -m networth.watcher.report --today    # since midnight, India time
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from networth.config import DATA_DIR
from networth.watcher import log
from networth.watcher.run import Paths
from networth.watcher.store import Store

DEFAULT_HOURS: Final = 48
INDIA: Final = ZoneInfo("Asia/Kolkata")


def window_start(now: dt.datetime, hours: int, today: bool) -> dt.datetime:
    if today:
        local = now.astimezone(INDIA)
        return local.replace(hour=0, minute=0, second=0, microsecond=0)
    return now - dt.timedelta(hours=hours)


def render(paths: Paths, since: dt.datetime) -> list[str]:
    store = Store.open(paths.watcher_db)
    try:
        entries = log.decision_log(store, since)
        cycle = store.latest_cycle()
    finally:
        store.close()
    lines = [f"Decision log, stories first seen since {since.astimezone(dt.UTC):%Y-%m-%d %H:%M} "
             f"UTC", ""]  # fmt: skip
    lines += log.render_log(entries)
    lines.append("")
    if cycle is None:
        lines.append("no cycle has run yet")
    else:
        counts = ", ".join(f"{k} {v}" for k, v in cycle.counts.items())
        lines += [f"latest cycle {cycle.started_at:%Y-%m-%d %H:%M} UTC: {counts}; "
                  f"cost ${cycle.cost_usd:.4f}; {len(cycle.errors)} errors"]  # fmt: skip
    spent = log.spend_since(paths.call_log, since)
    lines.append(f"spend since window start: ${spent.cost_usd:.4f} over {spent.calls} calls "
                 f"({spent.failed} failed), from {paths.call_log.name}")  # fmt: skip
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS)
    parser.add_argument("--today", action="store_true", help="since midnight in India")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args(argv)
    paths = Paths(args.data_dir)
    if not paths.watcher_db.exists():
        print(f"no watcher data at {paths.watcher_db}; run networth.watcher.run --once first",
              file=sys.stderr)  # fmt: skip
        return 1
    since = window_start(dt.datetime.now(dt.UTC), args.hours, args.today)
    print("\n".join(render(paths, since)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
