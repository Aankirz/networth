# Phase 1 report: the history engine

The engine now turns 287 sourced events and 85 daily price series into `data/base_rates.sqlite`. Nothing in it calls an LLM. Every number below comes from a command in this repo, and the section for each "Done when" item names the command that reproduces it.

## How to reproduce every check

```bash
uv sync
make check                                          # ruff, format, 63 tests (4 skip before a build)
uv run python -m networth.engine.fetch              # coverage table; exits 1 if any series fails
uv run python -m networth.engine.check_events       # rows, targets, live links; exits 1 on any failure
uv run python -m networth.engine.backtest           # -> data/base_rates.sqlite
uv run python -m networth.engine.backtest --exclude-vault   # -> data/base_rates_pre2022.sqlite
uv run python -m networth.engine.outside_check      # pre-FOMC drift reproduction
uv run python -m networth.engine.odds odds oil_supply JETS
uv run python -m networth.engine.odds range 2000 JETS oil_supply
uv run python -m networth.engine.odds compare rbi_hike ^NSEBANK ^CNXIT
uv run pytest tests/test_leak.py --leak-impl=previous_close_entry   # the leak test going red
```

## Coverage

All 36 sources downloaded on 2026-10-24. None failed. Yahoo closes are auto-adjusted, so they are total returns. A second run reads the cache in under a second.

| Series | First | Last | Rows |
|---|---|---|---|
| SPY | 1993-01-29 | 2026-10-23 | 8492 |
| ^GSPC | 1927-12-30 | 2026-10-23 | 24821 |
| ^SP500TR | 1988-01-04 | 2026-10-23 | 9776 |
| QQQ | 1999-03-10 | 2026-10-23 | 6950 |
| TLT | 2002-07-30 | 2026-10-23 | 6099 |
| GLD | 2004-11-18 | 2026-10-23 | 5517 |
| BTC-USD | 2014-09-17 | 2026-10-24 | 4421 |
| JETS | 2015-04-30 | 2026-10-23 | 2889 |
| XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | 1998-12-22 | 2026-10-23 | 7002 each |
| XLRE | 2015-10-08 | 2026-10-23 | 2777 |
| XLC | 2018-06-19 | 2026-10-23 | 2099 |
| BZ=F | 2007-07-30 | 2026-10-23 | 4789 |
| ^BSESN | 1997-07-01 | 2026-10-23 | 7221 |
| ^NSEI | 2007-09-17 | 2026-10-23 | 4686 |
| ^NSEBANK | 2007-09-17 | 2026-10-23 | 4701 |
| ^CNXIT | 2007-09-17 | 2026-10-23 | 4701 |
| ^CNXAUTO | 2011-07-12 | 2026-10-23 | 3747 |
| ^CNXPHARMA | 2011-01-31 | 2026-10-23 | 3873 |
| ^CNXFMCG | 2011-01-31 | 2026-10-23 | 3858 |
| ^CNXMETAL | 2011-07-12 | 2026-10-23 | 3747 |
| ^CNXENERGY | 2011-01-31 | 2026-10-23 | 3859 |
| ^CNXREALTY | 2010-07-19 | 2026-10-23 | 3994 |
| ^CNXPSUBANK | 2011-01-31 | 2026-10-23 | 3859 |
| ^CNXINFRA | 2010-07-19 | 2026-10-23 | 3994 |
| INR=X | 2003-12-01 | 2026-10-24 | 5939 |
| NIFTYBEES.NS | 2009-01-02 | 2026-10-23 | 4389 |
| GOLDBEES.NS | 2009-01-02 | 2026-10-23 | 4388 |
| FF:Mkt and 49 French industries | 1926-07-01 | 2026-08-31 | 26317 each |

The Indian start dates match the risk table in `tech.html`. The French data comes from `49_Industry_Portfolios_daily_CSV.zip` and `F-F_Research_Data_Factors_daily_CSV.zip`, both named on the data library page. The market series is Mkt-RF plus RF.

## Event library

`networth/engine/events.csv` has 287 rows. Three curator agents built it: US Fed, India, and global shocks. A fourth agent then opened every `source_url` and checked the event, the date and any stated time. It fixed 9 rows (8 oil rows moved off a mirror of EIA's chronology to Wikipedia, energy.gov, CNN or BBC, and one note was corrected) and deleted none. After review, `pandemic_20090611` moved from a web.archive.org copy of the WHO statement to the CDC page on the declaration, because archive.org rate-limits the checker. `check_events` confirms all 264 distinct URLs return 2xx or 3xx.

| Type | global | in | us | Total | Episodes |
|---|---|---|---|---|---|
| bank_stress | 2 | 5 | 10 | 17 | 12 |
| election | 0 | 7 | 10 | 17 | 17 |
| fed_cut | 0 | 0 | 40 | 40 | 31 |
| fed_hike | 0 | 0 | 52 | 52 | 50 |
| inr_shock | 0 | 13 | 0 | 13 | 10 |
| military_conflict | 10 | 8 | 3 | 21 | 18 |
| oil_supply | 20 | 0 | 0 | 20 | 20 |
| pandemic | 11 | 0 | 0 | 11 | 11 |
| rbi_cut | 0 | 28 | 0 | 28 | 26 |
| rbi_hike | 0 | 27 | 0 | 27 | 25 |
| tariff | 0 | 0 | 18 | 18 | 12 |
| union_budget | 0 | 23 | 0 | 23 | 23 |
| **Total** | 43 | 111 | 133 | 287 | 255 |

`networth/engine/fomc.csv` has 261 scheduled announcements from 1994-02-04 to 2026-09-16, each sourced to the Fed's `fomchistorical{YEAR}.htm` page or `fomccalendars.htm`. Statement times come from each release from 2016, from press-conference pages for 2011 to 2015, and from two Fed rule releases (2011-03-24 and 2013-03-13). For September 1994 to March 2011 the time is 14:15, taken from the paper's statement that releases came "at, or a few minutes after, 2:15 pm". Eight meetings have no sourced time.

## The method, as built

- **No peeking.** The return runs from the close of the first usable session to the close `horizon` sessions later. A session is usable when its close (16:00 New York, or 15:30 Kolkata) is strictly after the event. An event with no time counts from the first session dated after its local date, in every market. `backtest.entry_index` is the only code that turns an event time into a price index.
- **Excess return.** US assets are measured against SPY, or FF:Mkt for the French proxies. Indian assets are measured against one spliced series that takes ^NSEI's daily return where it exists and ^BSESN's before 2007-09-17. A series that is part of its own benchmark (SPY, FF:Mkt, ^NSEI, ^BSESN) is the market itself and is scored on its raw return.
- **Horizons.** `HORIZONS` in `backtest.py` was written before any result existed. It uses 21 sessions for every type, because the user decides once a month. Bank stress and pandemics use 63, because contagion and pandemics unfold over a quarter.
- **Episodes.** Same-type events chain when each is at most 21 trading days after the previous one. Trading days come from the US calendar, or from the Sensex calendar when both events are Indian. An episode is scored on its first event's reaction.
- **Baseline.** 1,000 random windows of the same length on the same series, with a seed derived from the row's series, benchmark, era and horizon. A row's baseline does not change with build order.
- **Eras.** `ERAS` is a table. JETS and the XL sectors get `since_1998` (the ETF) and `since_1926` (a French industry proxy, for example JETS to FF49:Trans). ^BSESN and INR=X get `since_1997` and `since_2007`. ^NSEBANK and the CNX sectors get `since_2007` only, because their data starts there.
- **Weak signal.** `weak_signal = n_episodes < 8` on every row. It matches on all 3,020 rows.
- **Vault.** Every row carries `includes_vault`. `--exclude-vault` cuts events and prices at 2021-12-31, so neither windows nor baselines can read a 2022 price. It writes `data/base_rates_pre2022.sqlite` (216 events, 192 episodes, 2,354 rows). The 192 episode ids match the full build.

## Done-when results

1. `make check` passes from a clean clone after `uv sync`: 59 passed and 4 skipped, because the 4 real-file tests need a built database. With the database built, 63 pass.
2. `fetch` downloaded every series. See the coverage table above.
3. `check_events` exits 0 on 287 rows, 111 India rows and at least 11 rows per type, with 264 of 264 URLs live. Two back-to-back runs from a clean clone of `5c780de` both exited 0, in 16.1 and 16.2 seconds.
4. `fomc.csv` covers 1994 to 2026-09-16, with sources.
5. Both required rows exist with every field filled:

| type | asset | era | n_episodes | hits | hit_rate | baseline | median | p10 | p90 |
|---|---|---|---|---|---|---|---|---|---|
| oil_supply | JETS | since_1998 | 11 | 5 | 0.455 | 0.450 | -0.10% | -16.9% | +9.7% |
| oil_supply | JETS (FF49:Trans) | since_1926 | 20 | 6 | 0.300 | 0.477 | -1.82% | -4.0% | +3.8% |
| rbi_hike | ^NSEBANK | since_2007 | 22 | 14 | 0.636 | 0.558 | +0.76% | -3.5% | +3.9% |

6. The leak test (`tests/test_leak.py`) checks 19 hand-written entry dates, covering both close times, closes to the minute, unknown times, weekends, holidays, DST, and events in Baghdad and Jerusalem. It poisons every close outside the window, and a second case runs the whole build that way. It fails on each of six broken versions in `tests/canaries.py`, and every `make check` proves that. It also failed on the real code: changing `side="right"` to `side="left"` in `entry_index` (an event at exactly the close counts the same day) turned `test_reactions_do_not_leak` and `test_build_reads_only_the_window_closes` red, and restoring it turned all 54 tests then in the suite green again.
7. `tests/test_method_rules.py` proves that events 21 trading days apart merge and 22 stay apart, and that gaps count trading days, not weekdays. It proves the baseline is reproducible, changes with the seed and ignores build order. It proves `weak_signal` is true at 7 episodes and false at 8.
8. `odds()`, `position_range()` and `compare()` return TypedDict shapes, and a test checks the keys. On the real file, `position_range(2000, "JETS", "oil_supply")` returns `{"value": 2000, "currency": "USD", "basis": "raw", "p10": -258, "median": -1, "p90": 211, "n_episodes": 11}`. `compare()` takes 2 or 3 assets and scores each on the episodes they all share.
9. `outside_check` prints the reproduction below.
10. This file.
11. `data/` and `.env` are gitignored. No key or secret appears in any committed file.

## Five base rates worth a look

These are strong-signal rows (8 or more episodes) whose story makes sense on its own. The table holds 3,020 rows, so a large gap can appear by chance. With 11 episodes and a 46% baseline, 10 or more hits happens about 0.3% of the time, which predicts about 8 such rows from luck alone. Treat each as a lead to check, not a finding.

| Event → asset | Era | Episodes | Beat the market | Normal month | Median excess |
|---|---|---|---|---|---|
| oil_supply → ^CNXENERGY | since_2007 | 11 | 9 (82%) | 44% | +3.6% |
| fed_cut → GLD | since_1998 | 18 | 14 (78%) | 47% | +5.3% |
| tariff → XLY | since_1998 | 12 | 2 (17%) | 51% | -0.7% |
| oil_supply → JETS (FF49:Trans) | since_1926 | 20 | 6 (30%) | 48% | -1.8% |
| rbi_hike → ^NSEBANK | since_2007 | 22 | 14 (64%) | 56% | +0.8% |

The JETS pair shows why both eras matter. In the ETF era airlines beat SPY in 5 of 11 oil episodes, the same as a normal month. Over the 1926 proxy, transportation stocks lagged in 14 of 20. The two eras share 11 episodes, so they are not independent samples, and `odds()` reports `n_shared_with_primary` for that reason.

Some rows near the top of the gap ranking are not signal. NIFTYBEES.NS against ^NSEI and ^SP500TR against SPY compare a total-return series with its own price index, so they "beat the market" in most windows. Union budget against US utilities is almost certainly chance.

## Outside check: the pre-FOMC drift

The paper is confirmed. Lucca and Moench, "The Pre-FOMC Announcement Drift", Journal of Finance 70(1), 2015, pages 329 to 371, also NY Fed Staff Report 512. Its introduction says:

> "We document that since 1994, the S&P500 index has on average increased 49 basis points in the 24 hours before scheduled FOMC announcements. These returns do not revert in subsequent trading days and are orders of magnitude larger than those outside the 24-hour pre-FOMC window."

Source: https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr512.pdf . The paper's window runs from 2 pm the day before to 2 pm on the announcement day, and its intraday sample runs from September 1994 to March 2011.

We have daily closes only, so the window becomes close(D-1) to close(D). That window drops the last two hours of D-1 and adds the two hours after the announcement, which the paper reports average about zero.

| Period | Window | FOMC days | Mean on FOMC days | Mean on other days | Welch t |
|---|---|---|---|---|---|
| Paper sample, 1994-09 to 2011-03 | close(D-1) to close(D) | 133 | +35.1 bp | +3.0 bp | 3.14 |
| Paper sample | placebo, close(D-2) to close(D-1) | 133 | +22.8 bp | +3.4 bp | 1.46 |
| After the paper, 2011-04 on | close(D-1) to close(D) | 123 | +12.0 bp | +5.5 bp | 0.62 |
| All | close(D-1) to close(D) | 261 | +23.6 bp | +4.2 bp | 2.65 |

The sign matches and the size is close inside the paper's own sample: +35 bp against the paper's +49 bp, about ten times a normal day. ^GSPC, the price index the paper used, gives +35.3 bp. Our number is likely smaller because the close-to-close window loses part of the 2 pm to 4 pm drift on D-1, which then shows up in the placebo row (inferred, not measured, since we have no intraday data).

After March 2011 the effect fades to +12 bp, about 2 times a normal day, with t = 0.62. That is a mismatch with the paper's size, and we report it as a finding. Two things probably contribute (a guess, not tested here). Statements moved to 2:00 pm and to 12:30 pm on 2011 and 2012 press-conference days, so the daily window lines up differently. The drift has also been widely reported as weaker after the paper was published. The engine reproduces the published result on the published sample, which is the test the spec asked for.

## Known gaps

- India RBI rows start in 2005. Before October 2004 the RBI's "repo rate" meant what is now the reverse repo rate, so earlier moves were left out rather than mislabelled. The Sensex `since_1997` era has few RBI episodes as a result.
- Some events were left out because their source could not be fetched: the June and July 2008 RBI hikes, the 2018-09-04 IL&FS default, and five rupee lows sourced only to Reuters.
- The French data ends 2026-08-31, so `since_1926` rows miss September and October 2026 events.
- Non-equity assets (TLT, GLD, BTC-USD, BZ=F, INR=X, GOLDBEES.NS) are measured against SPY or the Nifty, as the brief says. Their "beat the market" rate mixes the asset's own move with the equity market's. Their raw quantiles are stored too.
- BTC-USD is measured only on days SPY trades, so its 21 sessions are 21 US sessions.
- Proxy choices are judgment calls: XLK to Chips, XLI to Mach, XLY to Rtail, XLB to Chems. QQQ, TLT, GLD and BTC-USD have no `since_1926` era.
- Every type is computed for every asset, including pairs with no economic link, such as an Indian budget and US utilities. The odds API is the filter, and the multiple-comparisons warning above applies.
- Two event times are when the event happened, not when it was announced: the 2025-06-21 US strike on Iran and the 2022-02-24 invasion of Ukraine (the time of the VOA broadcast).
- `union_budget_20260201` cites the generic `Budget_Speech.pdf` URL on indiabudget.gov.in, which will probably point to the 2027 speech after February 2027.
- With 63-session horizons and 21-day episode gaps, bank-stress episode windows can overlap.

## Deviations from the brief

- **Branch policy.** The brief now says to commit and push to `main`. That overrides the "never commit to main" rule in `~/.claude/CLAUDE.md` for this phase, because the owner decided it in the brief.
- **Entry convention.** Returns start at the close of the first usable session, not the close before it. This leaves out that session's own move. A textbook event study includes it. We chose the investable version because the user acts after the news, and the future track record will measure from the moment we speak. Each reaction also stores `day0_raw` and `day0_excess`, so the size of what is left out is visible. For oil events, JETS's mean day-0 excess is -0.78% against -2.48% over the window. Base rates do not use these columns. If the owner wants the textbook version, it is a one-line change in `reaction_between` plus the hand-written leak table.
- **Leak definition.** The brief says a leak is "a price dated after the event's first usable session". The test enforces two things instead: the entry is exactly the first usable session, and the return reads no close other than its entry and exit. A return that started before the news, or used any later price, fails.
- **`position_range` basis.** It applies raw-return quantiles to the amount (`basis: "raw"`), because it describes money. The spec's placeholder numbers match the excess quantiles instead.
- **Hit definition.** A hit means the asset beat its market over the window, or rose, for a market series. The spec example's hit rate of .73 with a negative median does not fit that definition. Its figures are placeholders.
- **Extra schema fields.** Reaction gains era, series, benchmark, entry and exit dates, and the day-0 columns. BaseRate gains `n_hits`, `market`, `measure`, `series`, `benchmark`, data dates, raw quantiles and `includes_vault`. All spec fields are present with their spec names.
- **Unknown times across markets.** An event with no time counts from the first session after its local date in every market, including markets in other time zones. This is the strict reading of "assume after the close".
- **Episode calendar.** Gaps are counted on real trading days, so episode merging reads the price files. Episode ids come from the onset event, and they match across the full and pre-2022 builds.
- **Vault file.** `--exclude-vault` writes `data/base_rates_pre2022.sqlite` rather than replacing `base_rates.sqlite`, so the main file is never overwritten by the smaller build.
- **`check_events`.** Each URL has a 20-second wall-clock deadline once it starts, and connects over IPv4 first with 5 seconds per address. At most 2 requests go to one host at a time, and 1 to web.archive.org, with URLs taken round-robin across hosts. A transport error, such as a DNS failure, gets one retry. A 429 waits for its Retry-After (at most 5 seconds, 2 if the header is missing) and gets one retry. Every other HTTP status is final. A stuck, failed or still-limited URL is reported as failed. These rules came from a run that hung on broken IPv6 routes, a run that failed one URL on a resolver error, and the review's two runs where web.archive.org answered 429. `--offline` skips links and says so.
- **`compare()`** reports each asset on shared episodes and never ranks them, because Networth does not say what to buy.
- **Process.** The owner asked for the `pstack:poteto-mode` skill. The engine design came from two competing sketches and an independent judge. One delegate wrote the engine code, and I reviewed it and reran every check above.

PHASE 1 READY FOR REVIEW
