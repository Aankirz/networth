# Phase 6 report · Plan range

A user with a plan can now see what real past months say about it, in rupees. The plan is replayed 10,000 times over real Indian months in random blocks of about 12. The user sees a bad case, a middle case and a good case, before and after inflation. They also see how often the plan fell by the amount they said they can sit through, and what the typical worst fall meant in rupees. Only their own plan is ever shown.

## Method

The method was fixed in `docs/phases/phase-6-method.md` and committed in **`102d69b`** ("docs: fix the phase 6 plan range method before the first run"). That commit came before the return table existed and before any simulation ran.

**v2, after review.** The review asked for the longest window every bucket has. v1 started in 2012 only because MoSPI CPI and the 3-month interbank rate start late, which left the 2008 crash out. v2 adds two older OECD series from FRED, each used only for the months before the newer series starts. It was recorded in **`53cf2e9`** ("docs: extend the plan range window to 2007 as method v2") before the v2 table was built or run. Nothing else in the method changed. Method version: `plan-range-v2`.

In short:
- A stationary block bootstrap of whole calendar months, with a mean block of 12 months.
- 10,000 paths and seed `20261025` (`networth/sim/config.py`).
- Money goes in at the start of each month, split by the plan.
- A yearly reset to the plan's split.
- No taxes or fees.
- Real values are deflated by India CPI along the same resampled months.
- The fall is time-weighted (new money excluded). "Hit your limit" means a fall at or beyond `Plan.max_drop_ok`.
- Horizons map 3 years or less to 3, 5 or less to 5, 10 or less to 10, and longer to 15.

## Sources

| Bucket | Series | URL | Window used | Note |
|---|---|---|---|---|
| Core | Nifty 50 price index `^NSEI` (Yahoo) | https://finance.yahoo.com/quote/%5ENSEI/history/ | 2012-01 to 2026-09 (series from 2007-09) | **Price index: dividends are left out**, so the range is conservative by about the dividend yield (roughly 1 to 1.5% a year). NSE's total-return endpoint (https://www.niftyindices.com/reports/historical-data) refused scripted requests with 401. |
| Growth | Nifty Midcap 50 price index `^NSEMDCP50` (Yahoo). Index owner NSE Indices. | https://finance.yahoo.com/quote/%5ENSEMDCP50/history/ , https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-midcap-50 | 2012-01 to 2026-09 (series from 2007-09) | The only broad, citable Indian mid or small cap index with free monthly history of 15+ years. Midcap 150 starts in 2019 on Yahoo, and Midcap 100 has one row. **Price index: dividends left out.** |
| Safety | 3-month interbank rate, India, FRED `INDIR3TIB01STM` (OECD MEI), from 2011-11. **Before 2011-11:** OECD MEI short-term rate for India, FRED `INDLOCOSTORSTM` (the overnight call money rate, 1999-04 to 2023-12). | https://fred.stlouisfed.org/series/INDIR3TIB01STM , https://fred.stlouisfed.org/series/INDLOCOSTORSTM | 2007-10 to 2026-09 | The yearly rate `r` becomes `(1 + r/100)^(1/12) − 1` a month. Over 146 shared months the call rate averages 0.29 points below the 3-month rate. It spikes in stress months (18.6% in 2008-10), which overstates what FDs and liquid funds earned in those few months. FRED has no monthly Indian T-bill series: the suggested IMF id `INTGSTINM193N` does not exist. `IRSTCI01INM156N` was rejected because it reads a flat 6.0% from 2006 to 2011, which is RBI's bank rate, not a market rate. |
| Inflation | India CPI Combined, official YoY %, MoSPI via `networth/engine/macro.py`, from 2012-01. **Before 2012-01:** OECD all-items CPI for India, FRED `INDCPIALLMINMEI` (index 2015=100, 1957-01 to 2025-03). | https://api.mospi.gov.in/api/cpi , https://fred.stlouisfed.org/series/INDCPIALLMINMEI | 2007-10 to 2026-09 | MoSPI YoY becomes an even monthly rate. 2020-04 and 2020-05 have no print and take the straight line between 2020-03 and 2020-06. Before 2012 it is the OECD index's month-on-month change. Over 157 shared months, OECD YoY runs 0.1 points above MoSPI on average. The OECD series is not seasonally adjusted, so single months swing (July 2009 is +4.6%, on food prices). |

**Window: 2007-10 to 2026-09, 228 months.** It now starts where the equity indices start (Yahoo daily history from 2007-09-17, so the first whole month is 2007-10), and it holds the 2008 crash. In v1 it was 2012-01 to 2026-09, 177 months.

Build the table with `uv run python -m networth.sim.data`. It writes `data/sim/returns.csv` and `data/sim/sources.json`, which hold each series' URL, its first and last month, and the fetch time. It needs `data/macro/IN_CPI.csv` (from `uv run python -m networth.engine.macro`) and `FRED_API_KEY`. A missing series stops it with one line, such as `FAILED: sim table: core has no value for 2012-07`.

Yearly growth over the window, from the table: safety 6.34%, core 8.24%, growth 9.89%, CPI 6.45%. In v1 these were 6.35%, 11.36%, 16.66% and 5.53%. The equity figures fall because the window now starts near the 2007 peak and holds 2008. Inflation before 2012 averages 9.68% a year.

## Sample output

Balanced (20% safety, 70% core, 10% growth), ₹1,50,000 a month, 15 years, 20% fall, 10,000 paths, method v2. On this machine, `load_table` took under 0.001 s and `simulate` took 0.114 s, measured with `time.perf_counter`.

```
PlanRange(targets_pct=(20, 70, 10), monthly_amount=150000, years=15, fall_limit_pct=20,
  paths=10000, mean_block_months=12, invested=27000000,
  nominal_p10=33500000, nominal_median=54600000, nominal_p90=87800000,
  real_p10=12900000, real_median=21600000, real_p90=34800000,
  hit_limit_pct=94, worst_fall_pct=36, worst_fall_rupees=6220000, recovery_months=23,
  window_start=datetime.date(2007, 10, 1), window_end=datetime.date(2026, 9, 1),
  method_version='plan-range-v2')
```

**What 2008 changed.** Same plan and seed, v1 against v2:

| | v1 (2012-01 to 2026-09) | v2 (2007-10 to 2026-09) |
|---|---|---|
| Before inflation (bad / middle / good) | ₹4.81 Cr / ₹6.67 Cr / ₹9.43 Cr | ₹3.35 Cr / ₹5.46 Cr / ₹8.78 Cr |
| After inflation | ₹2.16 Cr / ₹2.98 Cr / ₹4.18 Cr | ₹1.29 Cr / ₹2.16 Cr / ₹3.48 Cr |
| Paths that fell 20% or more | 68% | 94% |
| Typical worst fall | 24%, about ₹42,00,000 | 36%, about ₹62,20,000 |
| Months to recover, middle case | 8 | 23 |

**Sanity check of the numbers.** The plan's blended yearly return over the v2 window is about 8.0% (0.2 × 6.34 + 0.7 × 8.24 + 0.1 × 9.89). ₹1,50,000 a month for 15 years at that rate comes to about ₹5.1 Cr, close to the ₹5.46 Cr median. The yearly reset adds a little on top. ₹5.46 Cr deflated by 6.45% a year over 15 years is ₹2.14 Cr, against the ₹2.16 Cr real median. 94% of paths hitting a 20% fall fits a 70% Nifty plan in a window that holds 2008 (Nifty fell about 60% peak to trough) as well as 2011, 2016 and 2020. A 180-month path drawn from 228 months almost always carries a block from one of them.

### `plan_range_lines`, all passing `guard.check(line, repr(r))`

Each line below was checked by `networth.guard.check` against `repr(r)` with zero problems: no number outside the source, no banned word and no advice phrasing.

**English**
- This is your own plan: 20% safety, 70% core, 10% growth, ₹1,50,000 a month for 15 years. It replays real past months from 2007 to 2026, in blocks of about 12 months, 10,000 times.
- Money put in over those years: ₹2.7 Cr.
- Where it could end up: bad case ₹3.35 Cr, middle ₹5.46 Cr, good case ₹8.78 Cr.
- After inflation, in today's rupees: bad case ₹1.29 Cr, middle ₹2.16 Cr, good case ₹3.48 Cr.
- In 94% of paths the plan fell by 20% or more at some point. That is the fall you said you can sit through.
- The typical worst fall was 36%, about ₹62,20,000 of the money held at the time.
- In the middle case, the worst fall took about 23 months to get back.
- This replays real past months. It is not a forecast. Your plan is your choice. Research, not advice.

**Hindi**
- यह आपका अपना प्लान है: 20% सेफ़्टी, 70% कोर, 10% ग्रोथ, हर महीने ₹1,50,000, 15 साल तक। इसमें 2007 से 2026 तक के असली पुराने महीने, लगभग 12 महीनों के टुकड़ों में, 10,000 बार दोहराए गए हैं।
- इन सालों में लगाया गया कुल पैसा: ₹2.7 Cr।
- पैसा कहाँ तक पहुँच सकता है: बुरे हाल में ₹3.35 Cr, बीच में ₹5.46 Cr, अच्छे हाल में ₹8.78 Cr।
- महँगाई के बाद, आज के रुपयों में: बुरे हाल में ₹1.29 Cr, बीच में ₹2.16 Cr, अच्छे हाल में ₹3.48 Cr।
- 94% रास्तों में प्लान कभी न कभी 20% या उससे ज़्यादा गिरा। यह वही गिरावट है जिसे आपने कहा था कि आप सह सकते हैं।
- आम तौर पर सबसे बड़ी गिरावट 36% थी, यानी उस समय रखे पैसे में लगभग ₹62,20,000।
- बीच वाले हाल में सबसे बड़ी गिरावट से वापस आने में लगभग 23 महीने लगे।
- यह असली पुराने महीनों को दोहराता है। यह कोई अनुमान नहीं है। आपका प्लान आपकी अपनी पसंद है। रिसर्च, सलाह नहीं।

**Hinglish**
- Yeh aapka apna plan hai: 20% safety, 70% core, 10% growth, har mahine ₹1,50,000, 15 saal tak. Ismein 2007 se 2026 tak ke asli purane mahine, lagbhag 12 mahine ke blocks mein, 10,000 baar dohraaye gaye hain.
- In saalon mein lagaya gaya kul paisa: ₹2.7 Cr.
- Paisa kahan tak pahunch sakta hai: bure haal mein ₹3.35 Cr, beech mein ₹5.46 Cr, achhe haal mein ₹8.78 Cr.
- Mehngai ke baad, aaj ke rupayon mein: bure haal mein ₹1.29 Cr, beech mein ₹2.16 Cr, achhe haal mein ₹3.48 Cr.
- 94% raaston mein plan kabhi na kabhi 20% ya usse zyada gira. Yeh wahi giravat hai jo aapne kaha tha ki aap seh sakte hain.
- Aam taur par sabse badi giravat 36% thi, yaani us waqt ke paise mein lagbhag ₹62,20,000.
- Beech wale haal mein sabse badi giravat se wapas aane mein lagbhag 23 mahine lage.
- Yeh asli purane mahinon ko dohraata hai. Yeh koi forecast nahin hai. Aapka plan aapki apni pasand hai. Research, advice nahin.

## What was built

| Piece | Where |
|---|---|
| Fixed choices (seed, paths, block, horizons, series ids and URLs) | `networth/sim/config.py` |
| Return table builder and loader | `networth/sim/data.py` |
| `plan_range(plan, profile, *, paths, seed, table) -> PlanRange`, `simulate`, `plan_range_lines(r, lang)`, `rupees(n)` | `networth/sim/__init__.py` |
| Bot-ready function | `networth.sim.plan_range_message(user_id, store) -> str \| None`. None for no profile, no plan, no amount or horizon, or a non-INR amount. Otherwise the lines in the user's language. Not wired to Telegram. |
| Demo page | `GET /plan-range?plan=balanced&amount=150000&years=15&fall=20`. The plan is a starter plan, or `own` with `safety`, `core` and `growth`. `currency=USD` gets "Rupee plans only for now." A GET form lets the viewer edit their own split. |
| `/u/{token}` section | `templates/_plan_range.html`, included from `user.html` with one line. `user_page` gains one dependency and one helper. |
| View and SVG range bar | `networth/web/plan_view.py`. Inline SVG, no chart library. `/plan-range` HTML is about 6 kb and `/u` about 5 kb. |
| Tests | `tests/test_sim.py` (30), `tests/test_sim_data.py` (10), `tests/test_sim_web.py` (21). No network, all on hand-made tables. |
| Screenshots | `docs/phases/phase-6-shots/plan-range-{320,1440}.png`, `user-{320,1440}.png` |

The sanity tests cover:
- The same seed gives identical output.
- 100% safety lands close to the safety series compounded.
- A constant-return table gives the closed form `A(1+r)((1+r)^T − 1)/r` to 3 significant figures, with real equal to nominal when CPI is 0.
- Fall and recovery on a hand-built path.
- The invested total equals amount × months.
- Indian formatting.
- Every line in three languages passes guard.
- `/plan-range` returns 200 with no banned words and carries the label and "Research, not advice".
- USD returns None.

**Screens.** Both pages were shot with Playwright at 320 px and 1440 px, from the real table. `document.documentElement.scrollWidth` read 320 at 320 px and 1440 at 1440 px on both pages, so there is no horizontal scroll. The range bar's smallest label renders at 13.0 px at 320 px wide and 21.6 px at 1440 px, measured as computed font size times the SVG's on-screen scale. Its row names sit on the side away from the invested line, and a Playwright check confirmed the line crosses no name on either page. The `/u` shot uses a throwaway Store and a throwaway link secret in the session scratchpad, not real user data.

**Gate.** `make check` passes in this clone (487 passed). It also passes from a fresh `git clone` with no `data/` after `uv sync` (475 passed, 12 skipped). The 12 skips are older engine and real-database tests that need built data. None are Phase 6.

## Deviations

- **Investing day.** The table is monthly, so the money goes in at the start of each month, not on the investing day. The difference is a fraction of one month's return.
- **Core is a price index, not total return**, because NSE's total-return data has no free scriptable source. This is stated on the page and in the method.
- **Growth is the Nifty Midcap 50**, not a broader midcap index, because it is the only one with 15+ years of free monthly data.
- **`/plan-range` with no table built returns 503**, with a friendly page naming the build command. It is not a crash.
- **The page prints `PlanRange` fields directly** rather than `plan_range_lines`. Every number on it still comes only from `PlanRange`. The view's only arithmetic is SVG geometry.
- **numpy was added with `uv add numpy`.** It was already installed through pandas, but `networth/sim` imports it directly.
- **`networth/sim` imports `networth.web.fmt.indian_grouping`** for Indian digit grouping rather than copying it. `networth/web/__init__.py` is empty, so the import is cheap.

## Known gaps

- **Safety and CPI are spliced in v2.** Before 2011-11 safety is the overnight call rate, which spikes in stress months and overstates what FDs and liquid funds earned then. Before 2012-01 CPI is the OECD India index rather than MoSPI's CPI Combined. Where they overlap, the series agree to within 0.29 and 0.1 points on average.
- **The window starts in 2007-10, after the 2003-2007 run-up.** It holds the 2008 fall but not the rise before it. Free monthly history for the equity indices begins in 2007-09.
- **Dividends are left out (range a little low) and fund costs are left out (range a little high).** The two partly cancel. Both are stated.
- **CPI is spread evenly from year-on-year figures**, which smooths single-month inflation swings.
- **Tests not written:** the yearly rebalance on its own (the closed-form cases use equal returns in every column), and a fall exactly equal to the limit (floats make that hard to build).
- **Telegram wiring** is left for the coordinator, as the brief says.

Nothing secret is committed and `data/` is not committed. The FRED key is read from `.env` and redacted from errors by the existing `macro._redacted`.
