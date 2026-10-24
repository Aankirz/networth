# Phase 1B · Economic context for the engine (US and India)

You are the **builder** for Phase 1B of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check.

Three other builders are running in the same working tree. **Phase 2** owns `networth/watcher/`, `networth/llm.py` and `networth/config.*`. **Phase 3A** owns `networth/app/` and `networth/bot/`. **Phase 4** owns `networth/web/`. Phase 2 and Phase 4 call `odds()`, `compare()` and `position_range()`. **Your changes to those functions must be additive.** Existing calls return byte-identical JSON. Stage only your own paths by name, and never run `git add -A`.

You own: `networth/engine/` and the new tests you add.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait.
1. `knowledge/PRODUCT.md`, then `docs/phases/phase-1-engine.md` and `docs/phases/phase-1-report.md`. The method rules there still hold: no peeking, fixed choices before results, episodes, a seeded baseline, weak signal under 8, and the vault.
2. FRED API docs (https://fred.stlouisfed.org/docs/api/fred/). `FRED_API_KEY` is in `.env`. Never print it. This network has broken IPv6, so use `networth/net.py`'s deadline client or force IPv4.

## The question this phase answers

"After a Fed cut, what did banks do **when no recession followed** compared with **when one did**?" Also "after a hike, when inflation was high compared with low?" And the same for India where the data allows. These splits are the most useful context a judge or user can see, and they must stay honest about smaller samples.

## Build

| What | Details |
|---|---|
| `networth/engine/macro.py` | Downloads and caches FRED series into `data/macro/`: `USREC` (NBER recession months), `CPIAUCSL` (CPI), `FEDFUNDS`, `UNRATE`. India CPI from an official no-key source (MOSPI or RBI DBIE). **Look up the exact source. Don't guess a URL.** If no machine-readable India CPI is reachable in 20 minutes, record that as a known gap and ship the US part. |
| Regimes, fixed before any result is looked at | Written as constants with a comment saying why: `recession_followed` (any USREC month in the 12 months after the event) for `fed_hike` and `fed_cut`; `inflation_high` (CPI year-on-year at the last release **before** the event, at least 4% US and 6% India, the RBI's upper band) for `fed_hike`, `fed_cut`, `rbi_hike` and `rbi_cut`. |
| No peeking | Inflation regimes use only data released before the event date, using the CPI release lag (about 2 weeks after month end). `recession_followed` is hindsight by design. Label it `hindsight: true` in every row and in the JSON, so the product can only use it as "what happened in each case", never as a live signal. |
| `backtest.py` | Adds BaseRate rows per regime value (for example `regime="recession_followed=no"`), with the same fields, baseline, eras, weak_signal and vault tags. Rows without a regime are unchanged. |
| `odds.py` | Optional `regime=` argument, and a `split(type, asset, regime_name)` function that returns both sides with n, hits, hit rate, baseline and weak_signal. Calls without `regime` are unchanged. |
| `tests/` | Regime assignment on hand-written dates, CPI release lag (an event the day before a release uses the older print), the hindsight flag present, and existing `odds()` output unchanged (a golden JSON snapshot taken before you edit). |

## Not in this phase

New event types, the LLM, any watcher, bot or web file, broker linking, and any buy or sell wording.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. `uv run python -m networth.engine.macro` downloads every series and prints a coverage table. India CPI is either listed or reported as a gap with the reason.
3. `uv run python -m networth.engine.backtest` still builds both sqlite files, and the existing row count for rows without a regime is unchanged (3,020, unless you report why).
4. `split("fed_cut", "XLF", "recession_followed")` returns both sides, each with n_episodes, n_hits, hit_rate, baseline, weak_signal and `hindsight: true`.
5. `split("rbi_hike", "^NSEBANK", "inflation_high")` returns both sides, or a clear "no India CPI" error if that source was a gap.
6. The golden test proves that `odds("rbi_hike","^NSEBANK")` and `position_range(2000,"JETS","oil_supply")` return byte-identical JSON to before.
7. A leak test fails if an inflation regime uses a CPI print released after the event. Show it failing on a deliberately broken version.
8. `docs/phases/phase-1b-report.md` lists the series and sources, the regime definitions and why, the 5 most interesting splits with both sides' n and baselines, known gaps and deviations.
9. Nothing secret is committed, and `data/` is not committed.

## The gate and branch policy

- Run `make check` before every commit. If it's red only because of another builder's uncommitted files, confirm your own tests are green and say so in the commit message.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Finish with `PHASE 1B READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
