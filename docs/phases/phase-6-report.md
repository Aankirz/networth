# Phase 6 report · Plan range

A user with a plan can now see what real past months say about it, in rupees. The plan is replayed 10,000 times over real Indian months in random blocks of about 12. The user sees a bad case, a middle case and a good case, before and after inflation. They also see how often the plan fell by the amount they said they can sit through, and what the typical worst fall meant in rupees. Only their own plan is ever shown.

## Method

The method was fixed in `docs/phases/phase-6-method.md` and committed in **`102d69b`** ("docs: fix the phase 6 plan range method before the first run"). That commit came before the return table existed and before any simulation ran. Nothing in it changed afterwards. Method version: `plan-range-v1`.

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
| Safety | 3-month interbank rate, India, FRED `INDIR3TIB01STM` (OECD MEI) | https://fred.stlouisfed.org/series/INDIR3TIB01STM | 2012-01 to 2026-09 (series from 2011-11) | FRED has no monthly Indian T-bill series (`INTGSTINM193N` does not exist). The yearly rate `r` becomes `(1 + r/100)^(1/12) − 1` a month. |
| Inflation | India CPI Combined, official YoY %, MoSPI via `networth/engine/macro.py` | https://api.mospi.gov.in/api/cpi | 2012-01 to 2026-09 | YoY becomes an even monthly rate. 2020-04 and 2020-05 have no print and take the straight line between 2020-03 and 2020-06. |

**Window: 2012-01 to 2026-09, 177 months.** The start is set by CPI (2012-01) and the safety rate (2011-11).

Build the table with `uv run python -m networth.sim.data`. It writes `data/sim/returns.csv` and `data/sim/sources.json`, which hold each series' URL, its first and last month, and the fetch time. It needs `data/macro/IN_CPI.csv` (from `uv run python -m networth.engine.macro`) and `FRED_API_KEY`. A missing series stops it with one line, such as `FAILED: sim table: core has no value for 2012-07`.

Yearly growth over the window, from the table: safety 6.35%, core 11.36%, growth 16.66%, CPI 5.53%.

## Sample output

Balanced (20% safety, 70% core, 10% growth), ₹1,50,000 a month, 15 years, 20% fall, 10,000 paths. On this machine, `load_table` took 0.001 s and `simulate` took 0.099 s, measured with `time.perf_counter`.

```
PlanRange(targets_pct=(20, 70, 10), monthly_amount=150000, years=15, fall_limit_pct=20,
  paths=10000, mean_block_months=12, invested=27000000,
  nominal_p10=48100000, nominal_median=66700000, nominal_p90=94300000,
  real_p10=21600000, real_median=29800000, real_p90=41800000,
  hit_limit_pct=68, worst_fall_pct=24, worst_fall_rupees=4200000, recovery_months=8,
  window_start=datetime.date(2012, 1, 1), window_end=datetime.date(2026, 9, 1),
  method_version='plan-range-v1')
```

**Sanity check of the numbers.** The plan's blended yearly return over the window is about 10.9% (0.2 × 6.35 + 0.7 × 11.36 + 0.1 × 16.66). ₹1,50,000 a month for 15 years at that rate comes to about ₹6.5 Cr, close to the ₹6.67 Cr median. ₹6.67 Cr deflated by 5.53% a year over 15 years is ₹2.98 Cr, which matches the real median exactly. 68% of paths hitting a 20% fall fits a 70% Nifty plan in a window that holds the 2020 crash: one 12-month block that covers March 2020 is enough.

### `plan_range_lines`, all passing `guard.check(line, repr(r))`

Each line below was checked by `networth.guard.check` against `repr(r)` with zero problems: no number outside the source, no banned word and no advice phrasing.

**English**
- This is your own plan: 20% safety, 70% core, 10% growth, ₹1,50,000 a month for 15 years. It replays real past months from 2012 to 2026, in blocks of about 12 months, 10,000 times.
- Money put in over those years: ₹2.7 Cr.
- Where it could end up: bad case ₹4.81 Cr, middle ₹6.67 Cr, good case ₹9.43 Cr.
- After inflation, in today's rupees: bad case ₹2.16 Cr, middle ₹2.98 Cr, good case ₹4.18 Cr.
- In 68% of paths the plan fell by 20% or more at some point. That is the fall you said you can sit through.
- The typical worst fall was 24%, about ₹42,00,000 of the money held at the time.
- In the middle case, the worst fall took about 8 months to get back.
- This replays real past months. It is not a forecast. Your plan is your choice. Research, not advice.

**Hindi**
- यह आपका अपना प्लान है: 20% सेफ़्टी, 70% कोर, 10% ग्रोथ, हर महीने ₹1,50,000, 15 साल तक। इसमें 2012 से 2026 तक के असली पुराने महीने, लगभग 12 महीनों के टुकड़ों में, 10,000 बार दोहराए गए हैं।
- इन सालों में लगाया गया कुल पैसा: ₹2.7 Cr।
- पैसा कहाँ तक पहुँच सकता है: बुरे हाल में ₹4.81 Cr, बीच में ₹6.67 Cr, अच्छे हाल में ₹9.43 Cr।
- महँगाई के बाद, आज के रुपयों में: बुरे हाल में ₹2.16 Cr, बीच में ₹2.98 Cr, अच्छे हाल में ₹4.18 Cr।
- 68% रास्तों में प्लान कभी न कभी 20% या उससे ज़्यादा गिरा। यह वही गिरावट है जिसे आपने कहा था कि आप सह सकते हैं।
- आम तौर पर सबसे बड़ी गिरावट 24% थी, यानी उस समय रखे पैसे में लगभग ₹42,00,000।
- बीच वाले हाल में सबसे बड़ी गिरावट से वापस आने में लगभग 8 महीने लगे।
- यह असली पुराने महीनों को दोहराता है। यह कोई अनुमान नहीं है। आपका प्लान आपकी अपनी पसंद है। रिसर्च, सलाह नहीं।

**Hinglish**
- Yeh aapka apna plan hai: 20% safety, 70% core, 10% growth, har mahine ₹1,50,000, 15 saal tak. Ismein 2012 se 2026 tak ke asli purane mahine, lagbhag 12 mahine ke blocks mein, 10,000 baar dohraaye gaye hain.
- In saalon mein lagaya gaya kul paisa: ₹2.7 Cr.
- Paisa kahan tak pahunch sakta hai: bure haal mein ₹4.81 Cr, beech mein ₹6.67 Cr, achhe haal mein ₹9.43 Cr.
- Mehngai ke baad, aaj ke rupayon mein: bure haal mein ₹2.16 Cr, beech mein ₹2.98 Cr, achhe haal mein ₹4.18 Cr.
- 68% raaston mein plan kabhi na kabhi 20% ya usse zyada gira. Yeh wahi giravat hai jo aapne kaha tha ki aap seh sakte hain.
- Aam taur par sabse badi giravat 24% thi, yaani us waqt ke paise mein lagbhag ₹42,00,000.
- Beech wale haal mein sabse badi giravat se wapas aane mein lagbhag 8 mahine lage.
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
| Tests | `tests/test_sim.py` (30), `tests/test_sim_data.py` (9), `tests/test_sim_web.py` (19). No network, all on hand-made tables. |
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

**Screens.** Both pages were shot with Playwright at 320 px and 1440 px, from the real table. `document.documentElement.scrollWidth` read 320 at 320 px and 1440 at 1440 px on both pages, so there is no horizontal scroll. The `/u` shot uses a throwaway Store and a throwaway link secret in the session scratchpad, not real user data.

**Gate.** `make check` passes in this clone (484 passed). It also passes from a fresh `git clone` with no `data/` after `uv sync` (472 passed, 12 skipped). The 12 skips are older engine and real-database tests that need built data. None are Phase 6.

## Deviations

- **Investing day.** The table is monthly, so the money goes in at the start of each month, not on the investing day. The difference is a fraction of one month's return.
- **Core is a price index, not total return**, because NSE's total-return data has no free scriptable source. This is stated on the page and in the method.
- **Growth is the Nifty Midcap 50**, not a broader midcap index, because it is the only one with 15+ years of free monthly data.
- **`/plan-range` with no table built returns 503**, with a friendly page naming the build command. It is not a crash.
- **The page prints `PlanRange` fields directly** rather than `plan_range_lines`. Every number on it still comes only from `PlanRange`. The view's only arithmetic is SVG geometry.
- **numpy was added with `uv add numpy`.** It was already installed through pandas, but `networth/sim` imports it directly.
- **`networth/sim` imports `networth.web.fmt.indian_grouping`** for Indian digit grouping rather than copying it. `networth/web/__init__.py` is empty, so the import is cheap.

## Known gaps

- **2008 is not in the window.** The months start in 2012, because India CPI and the safety rate start there. The worst fall available is the 2020 crash. So the share of paths that hit a fall limit, and the worst fall, likely read low. The page says the 2008 crash is not in the months. Extending CPI (for example with CPI-IW from the Labour Bureau) and the short rate (RBI DBIE 91-day T-bill) back to 2007 would fix it.
- **Dividends are left out (range a little low) and fund costs are left out (range a little high).** The two partly cancel. Both are stated.
- **CPI is spread evenly from year-on-year figures**, which smooths single-month inflation swings.
- **Tests not written:** the yearly rebalance on its own (the closed-form cases use equal returns in every column), and a fall exactly equal to the limit (floats make that hard to build).
- **Telegram wiring** is left for the coordinator, as the brief says.

Nothing secret is committed and `data/` is not committed. The FRED key is read from `.env` and redacted from errors by the existing `macro._redacted`.
