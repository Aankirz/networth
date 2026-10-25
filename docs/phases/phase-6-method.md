# Phase 6 · Plan range method (v1)

This file fixes every choice before the first full run. The report cites the commit that added it. A change to any rule below bumps `METHOD_VERSION` in `networth/sim/config.py` and gets a dated line at the bottom.

## Series

| Bucket | Series | Source | Why this one |
|---|---|---|---|
| Core | Nifty 50, price index, `^NSEI` | Yahoo Finance, https://finance.yahoo.com/quote/%5ENSEI/history/ | The brief names it. NSE's total-return series (https://www.niftyindices.com/reports/historical-data) has no scriptable free endpoint: its JSON API answered 401 to a plain request on 2026-10-25. So the price index is used and **dividends are left out**. Nifty 50 dividends have run near 1 to 1.5% a year, so the core range is conservative by about that much. |
| Growth | Nifty Midcap 50, price index, `^NSEMDCP50` | Yahoo Finance, https://finance.yahoo.com/quote/%5ENSEMDCP50/history/ . Index owner: NSE Indices, https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-midcap-50 | The only broad, citable Indian mid or small cap index with free monthly history back to 2007. Nifty Midcap 150 (`NIFTYMIDCAP150.NS`) starts in 2019 on Yahoo, and Nifty Midcap 100 (`NIFTY_MIDCAP_100.NS`) carries one row. It is a price index, so dividends are left out here too. |
| Safety | 3-month interbank rate for India, `INDIR3TIB01STM`, % a year, monthly | FRED (OECD MEI), https://fred.stlouisfed.org/series/INDIR3TIB01STM | A short rate close to what FDs and liquid funds earn. FRED has no monthly Indian 91-day T-bill series (`INTGSTINM193N` does not exist). Starts 2011-11. |
| Inflation | India CPI Combined, official year-on-year % | MoSPI eSankhyiki via `networth/engine/macro.py` (`data/macro/IN_CPI.csv`), https://api.mospi.gov.in/api/cpi | The brief names it. Starts 2012-01. |

Yahoo ticker histories were checked with `yfinance` on 2026-10-25. The FRED ids were checked against the FRED series API on the same day.

## Turning each series into a monthly return

- **Equity (core, growth).** Daily closes from Yahoo. The month's return is the last close of the month over the last close of the month before, minus 1.
- **Safety.** The rate `r` for month m is FRED's monthly value in % a year. The month's return is `(1 + r/100)^(1/12) − 1`.
- **Inflation.** MoSPI publishes year-on-year %, not an index level. The month's inflation is `(1 + yoy/100)^(1/12) − 1`, an even spread of the year-on-year figure. Over a year of resampled months this lands close to the true price change. It smooths single-month swings, which only matters for the real range by a little. MoSPI has no print for 2020-04 and 2020-05. Those two months take the straight line between 2020-03 and 2020-06.

## Data window

The window is every whole calendar month in which all four series have a value, from the first such month to the last complete month. No gaps are allowed inside it, other than the two CPI months filled above. The table builder fails loudly if it finds one. The report states the first and last month.

On the data seen while choosing sources, this is about 2012-01 to 2026-09. **It leaves out 2008.** The worst fall in the window is the 2020 COVID crash. So the share of paths that hit a fall limit is likely on the low side. The report says this in plain words.

## Resampling

- Stationary block bootstrap (Politis and Romano, 1994) over whole calendar months. One draw picks a month index, and every bucket and CPI take that same month's values, so they move together as they did.
- Each next month continues the block (the following month, wrapping from the last month to the first) with probability `1 − 1/12`, or starts a new block at a uniformly random month with probability `1/12`. The mean block length is 12 months.
- 10,000 paths. The seed is fixed in `networth/sim/config.py`.

## Investing

- The monthly amount goes in at the **start** of each month. The table is monthly, so the day of the month within a month is not modelled. That is a deviation from "on the investing day", and it moves the result by a fraction of one month's return.
- New money is split by the plan's targets. Holdings then drift with returns.
- Every 12 months from the start, holdings are reset to the plan's targets.
- No taxes, fees or expense ratios. This makes the range **optimistic** by about the fund costs, roughly 0.1 to 1% a year depending on the fund.

## Horizon

From `Profile.horizon_years`: 3 or less is 3 years, 5 or less is 5, 10 or less is 10, more is 15. Onboarding's buttons store 2, 4, 7 and 15, which map to 3, 5, 10 and 15.

## Outputs

- **Invested total.** Amount times months.
- **Nominal range.** The 10th percentile, median and 90th percentile of the end value across paths.
- **Real range.** Each path's end value divided by the CPI growth along that same path, so it is in today's rupees.
- **Fall.** For each path, the time-weighted value of one rupee held in the plan (new money excluded) and its largest peak-to-trough fall in %. "Hit your limit" is a fall at or beyond `Plan.max_drop_ok`. The share is over all paths.
- **Worst fall in rupees.** On each path, the portfolio's rupee value at the peak of its worst fall, times that fall in %. That is what the fall would have meant for the money held then. The median across paths is shown.
- **Months to recover.** On each path, the months from the trough of the worst fall until the time-weighted value is back at the peak before it. A path that never gets back counts as longer than any path that does. The median across paths is shown. When that median path did not recover by the end, it is shown as "not back by the end".

## Rounding

`PlanRange` holds every number at the precision it is shown with, so the text and the page print exactly what the engine returned. Rupee figures are rounded to 3 significant figures. Percentages and months are whole numbers. Lines print rupees in Indian format: up to ₹99,90,000 in full grouping, from ₹1 Cr as crore with up to two decimals.

## Currency

INR only. A plan in USD gets "Rupee plans only for now."

## Changes

- 2026-10-25: v1.
