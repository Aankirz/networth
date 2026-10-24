# Phase 1 · The history engine (US + India)

You are the **builder** for Phase 1 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, so only report something as done after you have run it.

You can talk with the owner, Ankit, in this window about anything technical. Keep the scope fence below unless he changes it in writing in this window. If he does, note the change in your hand-off report.

## Read first

1. `tech.html`, sections 03 (Data model), 04 (The engine) and 14 (Risks). `product.html`, sections 04.1 (Made for you) and 06 (Showing our work). Open them in a browser or read the HTML.
2. `docs/research/research-tooling.md` for data sources. `docs/research/research-investor-thinking.md` for the method rules.
3. `~/.claude/CLAUDE.md` is in force. That means conventional commits, tests alongside code, and an append to `.claude/CHANGELOG.md` after every change. Never add `Co-Authored-By` or session trailers to commits.

The one rule from the spec that this phase exists to make true: **the engine computes every number.** Nothing in this phase calls an LLM.

## Build

Create a Python 3.12 package `networth/` at the repo root, using `uv` (`uv init`, `pyproject.toml`). Put ruff and pytest in dev dependencies.

| File | What it does |
|---|---|
| `networth/engine/fetch.py` | Downloads daily prices into `data/prices/` (gitignored) and prints a coverage table (ticker, first date, last date, rows). It is idempotent and caches results. **US:** SPY, QQQ, TLT, GLD, BTC-USD, JETS, the XL* sector ETFs and the other tickers in the research notes. **India:** `^BSESN`, `^NSEI`, `^NSEBANK`, `^CNXIT`, `^CNXAUTO`, `^CNXPHARMA`, `^CNXFMCG`, `^CNXMETAL`, `^CNXENERGY`, `^CNXREALTY`, `^CNXPSUBANK`, `^CNXINFRA`, `INR=X`, `BZ=F`, `NIFTYBEES.NS`, `GOLDBEES.NS`. **Long history:** Kenneth French 12 or 49 industry daily returns (look up the exact file on the French data library site, don't guess the URL). |
| `networth/engine/events.csv` | The event library. Columns are `id, date, time_known, tz, region (us/in/global), type, cause, headline, source_url, notes`. Types are `oil_supply, fed_hike, fed_cut, rbi_hike, rbi_cut, union_budget, inr_shock, military_conflict, tariff, bank_stress, pandemic, election`. |
| `networth/engine/check_events.py` | Validates the CSV. It checks required fields, allowed types and regions, ISO dates, no duplicate ids, and that each `source_url` returns HTTP 2xx or 3xx (with a timeout and a concurrency cap). It prints a report and exits non-zero on failure. |
| `networth/engine/fomc.csv` | Scheduled FOMC announcement dates and times, taken from the Federal Reserve's own calendars or historical materials pages, with the source URL. |
| `networth/engine/backtest.py` | Turns events and prices into `data/base_rates.sqlite`, following the spec's `Event`, `Reaction` and `BaseRate` shapes. |
| `networth/engine/odds.py` | Pure functions over the sqlite file: `odds(type, asset, cause=None, era=None)` and `position_range(value, asset, type, ...)`. Each returns the spec's JSON shape. A comparison call for 2 or 3 assets after the same event type. |
| `networth/engine/outside_check.py` | Reproduces the pre-FOMC drift (see below) and prints a short report. |
| `tests/` | pytest, testing behaviour. The tests must not hit the network. Use small fixture price frames. |
| `Makefile` | `make check` runs `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`. |
| `docs/phases/phase-1-report.md` | Your hand-off report (see below). |

### Method rules (from the spec, all required)

- **No peeking.** An event after the market close counts from the next session. The close is 16:00 America/New_York for US assets and 15:30 Asia/Kolkata for Indian assets. If `time_known` is unknown, assume after the close.
- **Excess return.** US assets are measured against SPY, or the market factor for the French data. Indian assets are measured against `^NSEI`, or `^BSESN` before 2007.
- **Fixed horizons per type,** written in code before any results are looked at (for example a `HORIZONS` dict with a comment saying why). Don't tune them on results.
- **Episodes.** Events of the same type within 21 trading days merge into one episode. Odds count episodes, not events.
- **Baseline.** The hit rate over 1,000 random windows of the same length, with a fixed seed, reported next to the event hit rate.
- **Eras.** For US assets, `since_1926` (French industries) and `since_1998` (ETFs). For India, `since_1997` (Sensex) and `since_2007` (Nifty and sectors).
- **Weak signal.** `weak_signal = n_episodes < 8`, stored on every BaseRate row.
- **Vault.** Every row is tagged with whether it includes 2022 to 2026 events. `backtest.py --exclude-vault` builds the table without them, for later phases.

### Event library

Use subagents. Assign one curator per region or type group, and one checker who confirms each row against its source. Every row needs a real source, preferably primary: the Fed, the RBI, the Ministry of Finance or PIB, OPEC, FDIC, or Wikipedia when the page cites primary sources. Set targets of **at least 80 rows, at least 20 of them India-relevant, and at least 5 rows for every type.** A row you can't source gets dropped. Never invent a date.

### Outside check

The spec cites Lucca and Moench (2015), "The Pre-FOMC Announcement Drift", from memory. **First confirm the paper and its headline claim** from the paper itself, the NY Fed staff report or the Journal of Finance version, and quote the claim with its URL in your report. Then compute the SPY return over the window before scheduled FOMC announcements and compare it with other days. Use daily closes if you have no intraday data, and say so. Report whether the sign and rough size match. A mismatch is a finding. Investigate it and don't hide it.

## Not in this phase

The news watcher, any LLM or Anthropic or Bedrock call, Telegram, Keiki, Maritime, FastAPI routes, the web view, the harness or zoya-harness fork, the improvement loop and walk-forward eval, broker linking, and Docker. Don't add features beyond this list.

## Done when

The coordinator checks every item by running it.

1. `make check` passes from a clean clone after `uv sync`.
2. `uv run python -m networth.engine.fetch` downloads every listed series and prints the coverage table. Indian start dates match roughly: Sensex from 1997, Nifty, Bank and IT from 2007, most sectors from 2010 or 2011. Any series that fails is listed as failed, not silently skipped.
3. `uv run python -m networth.engine.check_events` exits 0 on at least 80 rows, at least 20 India rows and at least 5 rows per type, with every `source_url` live.
4. `fomc.csv` covers the scheduled announcements from 1994 (or the earliest year you can source) to the present, with sources.
5. `uv run python -m networth.engine.backtest` builds `data/base_rates.sqlite`. A query for `oil_supply` and `JETS`, and one for `rbi_hike` and `^NSEBANK`, each return rows with every BaseRate field filled, including both eras where the data exists.
6. A **leak test** fails if any return uses a price dated after the event's first usable session. It also covers the US and India close-time rules. It must be shown failing on a deliberately broken version, so prove it can catch a leak.
7. The tests prove three things: episodes merge within 21 trading days, the baseline is seeded and reproducible, and `weak_signal` flips at 8.
8. `odds()`, `position_range()` and the comparison function return the spec's JSON shapes from the real sqlite file. `position_range(2000, "JETS", "oil_supply")` gives p10, median and p90 in dollars.
9. `uv run python -m networth.engine.outside_check` prints the reproduction, and the report quotes the paper's claim with its URL.
10. `docs/phase-1-report.md` (or `docs/phases/phase-1-report.md`) lists:
    - the coverage table;
    - event counts by type and region;
    - the five most interesting base rates, each with n_episodes and baseline;
    - the outside-check result;
    - known gaps;
    - every deviation from this brief.
11. Nothing secret is committed, and `data/` is not committed.

## The gate

Run `make check` before every commit. Don't commit red.

## Branch policy

Hackathon mode, decided by the owner. **Commit and push straight to `main`.** No PRs and no feature branches. The remote is `origin` (github.com/Aankirz/networth, private). Repo-local git config already sets the author and the credentials, so don't change git config. Before every push, run `git pull --rebase`. Make small conventional commits (`feat:`, `test:`, `fix:`), run `make check` green before each one, and push after each one so the coordinator can review as you go. Never force-push. When you're done, write `PHASE 1 READY FOR REVIEW` as the final line of your hand-off in this window.

## OWNER NEEDED protocol

If you hit a step only a human can do, such as a credential, a paid action, a sign-up or an account decision, stop that step and print the following, then continue with other work:

`OWNER NEEDED: <what> — <how to do it, exact steps>`

This phase should need no keys. If a data source suddenly needs one, use OWNER NEEDED and don't work around it.
