# Phase 1B report: economic context for the engine

The engine can now split a base rate by the economic regime around each event. One example: after a Fed cut, it compares what banks did when a recession followed with what they did when none did. The splits come from four FRED series and MoSPI's official India CPI. They land in a new `regime_rates` table next to the unchanged `base_rates` table. `split()` and `odds(..., regime=...)` read them. Calls that do not name a regime return the same bytes as before this phase. A golden test proves that.

## How to reproduce every check

```bash
uv sync
make check                                              # ruff, format, every test
uv run python -m networth.engine.macro                  # downloads FRED and MoSPI, prints coverage
uv run python -m networth.engine.backtest               # -> data/base_rates.sqlite
uv run python -m networth.engine.backtest --exclude-vault
uv run python -m networth.engine.odds split fed_cut XLF recession_followed
uv run python -m networth.engine.odds split rbi_hike ^NSEBANK inflation_high
uv run python -m networth.engine.odds odds fed_cut XLF recession_followed=no
uv run pytest tests/test_regimes.py -k leak --regime-impl=no_release_lag   # the leak test going red
```

## Series and sources

`networth/engine/macro.py` downloads every series over IPv4 with a wall-clock deadline. It caches each one as `data/macro/<NAME>.csv` with columns `date,value`, one row per month. `data/macro/sources.json` records each URL template, without the key, and any gap reason. The FRED key comes from `.env`. Error text replaces the key with `<FRED_API_KEY>`, and a grep of `networth/`, `tests/`, `docs/` and `data/macro/` finds the key in 0 files.

Coverage on 2026-10-25:

| Series | Source | First | Last | Months | Used by |
|---|---|---|---|---|---|
| USREC | FRED | 1854-12 | 2026-09 | 2062 | `recession_followed` |
| CPIAUCSL | FRED and ALFRED, first releases | 1972-07 | 2026-09 | 650 | `inflation_high`, US |
| FEDFUNDS | FRED | 1954-07 | 2026-09 | 867 | cached only |
| UNRATE | FRED | 1948-01 | 2026-09 | 944 | cached only |
| IN_CPI | MoSPI eSankhyiki API | 2012-01 | 2026-09 | 175 | `inflation_high`, India |

US CPI is fetched with `output_type=4`, which returns only the first print of each month. Each observation's `realtime_start` is the day that print was first published. `CPIAUCSL.csv` therefore has a third column, `released`. YoY for month M is the first print of M over the first print of M-12. The M-12 value may have been revised by the time M came out, so this is close to, not exactly, what the release showed. ALFRED returns no first prints before 1972-07. The first Fed event in the library is in 1994, so no scored event loses coverage. October 2025 has a release date (2025-12-18) and no print, because of the 2025 shutdown. The file keeps that row with an empty value, so an event before 2025-12-18 still reads September.

India CPI is the all-India, Combined-sector general index from `api.mospi.gov.in`. That is MoSPI's official API, and it needs no key. The engine stores MoSPI's own published year-on-year `inflation` field. It does not compute YoY from the index, because the index changes base year twice. For each month, the engine uses the base that was the headline series when that month was released:

| Months | MoSPI series | Endpoint |
|---|---|---|
| 2012-01 to 2014-12 | CPI-C, base 2010 | `/api/cpi/getCPIIndex?base_year=2010` |
| 2015-01 to 2025-12 | CPI-C, base 2012 | `/api/cpi/getCPIIndex?base_year=2012` |
| 2026-01 onward | CPI, base 2024 | `/api/cpi/getCPIData?base_year=2024` |

Two MoSPI press notes confirm the switch dates. PIB release 115396 published January 2015 as the first month on base 2012. MoSPI's January 2026 CPI press note introduced base 2024. The endpoints and their parameters come from MoSPI's own client, `github.com/nso-india/esankhyiki-mcp` (`mospi/client.py` and `swagger/swagger_user_cpi.yaml`).

MoSPI's server needs TLS legacy renegotiation. `macro.mospi_client()` turns on `OP_LEGACY_SERVER_CONNECT` for that one host and keeps certificate checks on. `networth/net.py` is unchanged.

## Regime definitions and why

The rules sit in one registry, `macro.REGIMES`. They were written as constants on 2026-10-25, before any split was computed. Each rule classifies an episode on its onset event. That is the same event the episode is scored on.

| Regime | Applies to | Rule | Hindsight |
|---|---|---|---|
| `recession_followed` | fed_hike, fed_cut | Yes if any USREC month in M+1 to M+12 equals 1, where M is the event's month. Unknown if USREC does not yet cover M+12. | true |
| `inflation_high` | fed_hike, fed_cut | Yes if US CPI YoY (CPIAUCSL) at the last print released before the event is 4% or more. | false |
| `inflation_high` | rbi_hike, rbi_cut | Yes if India CPI YoY at the last print released before the event is 6% or more. | false |

The thresholds have these reasons:

- 12 months is the brief's window. It counts months after the event's own month, so a recession that is already running at a cut counts as yes.
- 4% is about twice the Fed's 2% target.
- 6% is the top of the RBI's tolerance band, 4% plus or minus 2.

**No peeking.** An inflation rule reads the newest CPI month whose release date is strictly before the event date. For the US, the release date is the recorded first-publication date from ALFRED. Where no date is recorded, a print counts as public on `month_end(M) + CPI_RELEASE_LAG_DAYS`. That fallback is 14 days for India, the brief's "about 2 weeks", and 21 days for US months before 1972-08.

The first version used a fixed 21-day US lag. The review found it wrong. ALFRED shows 133 US months published more than 21 days after month end, the latest 48 days after. Three real events read a print before it was public: `fed_cut_19960131` (1995-12), `fed_hike_20050322` (2005-02) and `fed_cut_20251210` (2025-10). With recorded dates, all 92 Fed events read a print released before them. `test_every_fed_event_reads_a_us_print_released_before_it` keeps that true on the real cache. A longer lag can only make a rule read an older print, never a future one.

**Hindsight.** `recession_followed` reads the 12 months after the event, and NBER dates recessions months after they start. Every `recession_followed` row stores `hindsight = 1`, and every JSON answer carries `"hindsight": true`. The product may show it only as what happened in each past case, never as a live signal. `inflation_high` uses only data public before the event, so it carries `"hindsight": false`.

**Vault.** `Macro.load(as_of=2021-12-31)` drops every USREC month after `as_of` and every CPI print released after it. The pre-2022 build can therefore never read 2022 macro data. A 2021 cut whose 12-month window reaches 2022 is unknown in that build.

## How the rows are built

`backtest.build` loads the macro cache once and classifies every episode. `regime_rows()` filters the episodes already scored for a panel. It calls the same `base_rate_row` with the same cached baseline. A regime row therefore has the same fields, baseline, eras, `weak_signal` and `includes_vault` as a plain row, plus `regime` (for example `recession_followed=no`) and `hindsight`. Episodes a rule cannot decide go into neither side. `split()` reports them as `n_unclassified`.

The rows live in their own table, `regime_rates`, keyed by `(type, cause, asset, era, regime)`. The code that writes `base_rates` is unchanged, and so is every query that reads it. That is why the existing callers in Phase 2 and Phase 4 see no change. If the macro cache is missing, the build still succeeds. It records the reason in the `macro_gaps` meta key, and `split()` raises `NoRegimeData` with that reason.

| File | `base_rates` rows | `regime_rates` rows |
|---|---|---|
| `data/base_rates.sqlite` | 3,020 (unchanged) | 1,850 |
| `data/base_rates_pre2022.sqlite` | 2,354 (unchanged) | 1,532 |

In the full file, the regime rows split into 743 `inflation_high=no`, 468 `inflation_high=yes`, 358 `recession_followed=no` and 281 `recession_followed=yes`. Both files' `base_rates` tables were compared with copies taken before this phase, every row and every column. They are identical, and so are `episodes` and `reactions`.

## Done-when results

1. `make check` passes with 302 tests (ruff, format and pytest all green). The 43 new tests in `tests/test_regimes.py` read no network and no `data/`. An autouse fixture points the macro cache at an empty folder. A fresh clone with no `data/` was not tested, but that setup is the same one every test already runs in.
2. `macro` downloads all five series and prints the coverage table above. India CPI is listed, not a gap.
3. Both sqlite files build, and `base_rates` still holds 3,020 rows.
4. `split("fed_cut", "XLF", "recession_followed")` returns both sides with every required field and `hindsight: true`. See the first row of the next section.
5. `split("rbi_hike", "^NSEBANK", "inflation_high")` returns both sides. See the last row of the next section.
6. `test_real_answers_match_the_pre_phase_golden` compares four calls on the real file with JSON captured before any edit. The four calls are `odds("rbi_hike","^NSEBANK")`, `odds("fed_cut","XLF")`, `position_range(2000,"JETS","oil_supply")` and `compare("fed_cut",["XLF","QQQ"])`. All four match byte for byte. `test_fixture_book_answers_match_the_pre_phase_golden` does the same on the fixture database, so the check also runs when `data/` is missing.
7. `test_inflation_regime_does_not_leak` checks hand-written events around release dates: the day before, the release day and the day after, including a release recorded far past the fixed lag. `tests/canaries.py` holds four broken classifiers. `same_month_print` reads the event month's print. `no_release_lag` treats month end as the release. `release_day_counts` lets a print count on its own release day. `ignores_release_dates` uses the fixed lag instead of the recorded date, which is the bug the review found. Each one turns the test red. For example, `--regime-impl=ignores_release_dates` fails with `us_delayed_release_past_fixed_lag: read a print other than 2020-10`, and the real-data test fails with `fed_hike_19940418: read a print other than 1994-03`. The real code passes. `test_leak_check_catches_every_canary` runs on every `make check` to prove this.
8. This file.
9. `data/` is gitignored, and no file in the commit holds a key.

## Five splits worth a look

"Hit" follows each row's measure. For an excess row, it means the asset beat its benchmark (SPY in the US, the Nifty and Sensex splice in India) over 21 trading days. The baseline is the row's normal-month hit rate, and both sides share it. All rows use cause = all causes on the asset's primary era.

The engine holds 101 split pairs where both sides have at least 4 episodes. Some large gaps will appear by chance, so treat each row as a lead, not a finding. The rows below have the largest gaps among pairs where at least one side has 8 or more episodes.

| Split | Era | Side | Episodes | Hits | Hit rate | Median | Baseline | Unclassified |
|---|---|---|---|---|---|---|---|---|
| fed_cut → XLF, recession followed | since_1998 | yes | 16 | 3 | 19% | -1.7% | 46% | 2 |
| | | no | 8 | 6 | 75% | +1.0% | | |
| fed_cut → SPY, recession followed | since_1998 | yes | 16 | 6 | 38% | -1.3% | 67% | 2 |
| | | no | 8 | 7 | 88% | +1.3% | | |
| fed_cut → XLP, recession followed | since_1998 | yes | 16 | 13 | 81% | +1.8% | 42% | 2 |
| | | no | 8 | 3 | 38% | -1.7% | | |
| fed_hike → ^CNXPSUBANK, inflation high | since_2007 | yes | 10 | 8 | 80% | +3.5% | 46% | 0 |
| | | no | 11 | 4 | 36% | -1.4% | | |
| rbi_hike → ^NSEBANK, inflation high | since_2007 | yes | 8 | 8 | 100% | +1.3% | 56% | 11 |
| | | no | 3 (weak) | 0 | 0% | -0.7% | | |

The first three rows answer the brief's question. When a recession followed a Fed cut, banks lagged SPY in 13 of 16 episodes. When none followed, they beat it in 6 of 8. Consumer staples did the opposite. SPY, which is scored on its raw return, rose in 7 of 8 no-recession episodes and only 6 of 16 recession ones. The yes episodes cluster in three easing cycles (2001, 2007 to 2008, 2019 to 2020), so they are fewer independent cases than 16 suggests. All three rows are hindsight.

The India row has a weak "no" side, and 5 of its 8 "yes" episodes are the 2022 hikes, which sit in the vault. The 11 unclassified hikes come before 2012, where MoSPI has no CPI-Combined YoY.

## Known gaps

- **India CPI starts in 2012-01.** MoSPI publishes no CPI-Combined YoY before then, so RBI events from 2006 to 2011 are unclassified. That is 11 of the 22 `^NSEBANK` hike episodes. This phase does not substitute another source for those years.
- **No India CPI for 2020-04 and 2020-05.** MoSPI did not publish those months (COVID), so the May 2020 RBI cut is unclassified.
- **Recent USREC zeros are provisional.** NBER announces recessions late, so `recession_followed=no` for the 2024 and 2025 cuts could flip. Cuts whose window runs past 2026-09 are unclassified, which accounts for the 2 in each `fed_cut` row above.
- **India has no release calendar.** MoSPI's API publishes no release dates, so India uses the fixed 14-day lag. A delayed India release could still be read early. This phase did not check historical India release dates.
- **The prior-year CPI value is not the vintage that was public.** The first print of M-12 can differ from the revised value that was public when M came out. This only matters for events with inflation near 4%. Switching to first prints moved one event, `fed_hike_20060629`, from 3.98% to 4.02%, so it is now `inflation_high=yes`.
- **FEDFUNDS and UNRATE are cached but unused.** The brief asks for them to be downloaded. No regime reads them yet.
- **A database built before this phase has no `regime_rates` table.** `split()` raises a raw sqlite error on such a file until the backtest runs again.

## Deviations from the brief

- **India CPI has three base years, not one.** As explained above, each month uses the base that was the headline series when that month was released.
- **US CPI uses recorded release dates and first prints, not a fixed lag on the revised series.** The brief's fixed lag let three real events read unpublished prints. See "No peeking". The download is still CPIAUCSL from FRED.
- **`odds(..., regime=...)` takes `regime` as a keyword-only argument after `db`.** It returns `RegimeOddsJSON`, which is the `OddsJSON` keys plus `regime` and `hindsight`. It answers on the same era as plain `odds()`. `OddsJSON` itself gained no key.
- **The FRED key reader is a small `.env` reader inside `macro.py`.** It does not import `networth.config`, which Phase 2 owns and was editing during this phase.
- **The macro CLI downloads again on every run.** There is no freshness check. A failed download keeps the cached file.
