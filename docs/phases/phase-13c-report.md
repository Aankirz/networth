# Phase 13C report: ratings, the sector board and the news notifier

Written 2026-10-25 by the Phase 13C builder. The brief is `docs/phases/phase-13c-ratings.md`.

## Who it is for

A Networth user can now ask what we think of a share, a fund, an ETF or an upcoming IPO and get a view (Strong, Positive, Neutral, Weak or Avoid), a score out of 100 and a one-line 12-month outlook. Each rating also lists the numbers it rests on, where each one came from and when, what we couldn't read, and how often ratings like it beat the market since 2015, including when that record is weak. They can see today's sector moves with the confirmed news behind each one, hear once when a confirmed story touches something they own, and share any rating or sector move as a public page.

## What was built

| Piece | Where | What it does |
|---|---|---|
| Rating engine | `networth/ratings` | `rate(query, kind=None, *, now, sources, table)` returns a `Rating`. Shares and ETFs come from Yahoo, mutual funds from mfapi.in (AMFI NAVs), IPOs from NSE's issue API plus the RHP. Indian names are in INR against the Nifty 50, US names in USD against the S&P 500. |
| Drivers | `ratings/score.py`, `ratings/kinds.py` | Share: growth, valuation against sector peers, debt (left out for lenders), price momentum, 30-day news tone from the watcher's confirmed stories, sector trend. Fund: returns against the benchmark and the category, consistency, expense ratio, holdings mix. IPO: valuation against listed peers, financials from the RHP, fresh issue against OFS, use of the money, subscription when live. |
| Track record | `ratings/track.py`, `ratings/backtest.json` | A monthly replay since January 2015 of the price part of the score, for four groups: Indian stocks, Indian funds, US stocks, US ETFs. A hit is beating the Nifty 50 (or the S&P 500) over the next 12 months. |
| IPO facts | `ratings/ipo_rhp.json` | SFCTECH's RHP numbers, each with its page. |
| Sector board | `networth/sectors` | Day, week and month moves of 11 NSE sector indices, each with up to 3 confirmed watcher stories from the last 7 days. |
| `/sectors` | `networth/bot/sectors_cmd.py` | The board on Telegram, phone-sized. Sectors with no prices are named. |
| News notifier | `networth/notify` | After each watcher cycle, a confirmed story about a holding, its sector or the plan's Nifty 50 sends one message through the outbox: the story and its publishers, the move on the last close with its source, the move in the holding's own currency, and our rating if its view changed. |
| `/alerts on`, `/alerts off` | `networth/bot/alerts_cmd.py` | Flips the profile's `alerts_on`. |
| Public pages | `networth/web/ratings_web.py` | `/r/<slug>` for a rating (`/r/hdfcbank`, `/r/mf120716`, `/r/sfctech`, `/r/aapl`), `/r/sectors` and `/r/sector-<key>`. No sign-in. |
| API for the site | same file | `GET /api/rating/{query}`, `GET /api/sectors` and `GET /api/ratings/backtest`, behind the API's origin check. Types in the Phase 13C block of `docs/phases/phase-10-contract.md`. |

No rating, sector, alert or `/r` page carries "Research, not advice." or any other disclaimer (owner order). Money is written only through `networth.ratings.model.money`, which mirrors 13A's `moneyShort` in `site/lib/money.ts`: ₹2.91 lakh, ₹1.2 crore, $12,400, $1.2M.

## Done when

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Five ratings with view, score, sourced drivers and the track line | Met | Pasted below, live on 2026-10-25 |
| 2 | Backtest table exists and its hit rate is computed | Met | `uv run python -m networth.ratings.track` rewrites `networth/ratings/backtest.json`. A rerun left the file unchanged. `test_the_backtest_hit_rate_is_computed_from_prices` |
| 3 | `/sectors` live on Telegram | **Not met** | The command and its test are committed. It is not deployed, because the owner ordered no pushes. Its output on live prices is pasted below. See OWNER NEEDED 1 |
| 4 | One alert per story, with the cap, quiet hours and `/alerts off` tested | Met in tests | `tests/test_notify.py`: 10 tests. Not seen live, for the same reason as item 3 |
| 5 | `/r/<slug>` opens without sign-in and shows the rating and its sources | Met locally | `tests/test_ratings_web.py`. A local render on live sources answered 200 for `/r/hdfcbank`, `/r/sectors` and `/r/sector-it` |
| 6 | Every number traces to a source and a time | Met | `test_no_driver_lacks_a_source_and_a_time` runs over a share, a fund, an IPO, a US share and a fund found by name |
| 7 | `make check` exits 0 | Met | Exit 0 on `9182e92`: 1337 passed, 13 skipped |

## The five ratings (done-when 1)

Run on this machine, which has no `data/watcher.sqlite`, so news tone shows as missing here. On the VM the watcher's database exists and the news driver is read from it.

```
rate('SWIGGY') -> Swiggy Limited (stock, INR)
View: Neutral, score 52/100, confidence medium. Rated 2026-10-25T16:43:33+00:00.
Outlook: Over the next 12 months we see Swiggy as Neutral, helped by valuation against sector peers and balance sheet, held back by price momentum, with medium confidence (2 inputs missing).
- Growth (flat): Revenue +36% year on year (latest quarter); still loss-making, margin -13%. Source: Yahoo Finance, https://finance.yahoo.com/quote/SWIGGY.NS, 2026-10-25T16:43:35+00:00
- Valuation against sector peers (up): P/B 2.8 against a peer median of 36.3 (ETERNAL, NYKAA). Source: Yahoo Finance, https://finance.yahoo.com/quote/SWIGGY.NS, 2026-10-25T16:43:35+00:00
- Balance sheet (up): Debt is 0.15x equity. Source: Yahoo Finance, https://finance.yahoo.com/quote/SWIGGY.NS, 2026-10-25T16:43:35+00:00
- Price momentum (down): -29% against the Nifty 50 over 12 months (last month left out); -37% from its 200-day average. Source: Yahoo Finance, https://finance.yahoo.com/quote/SWIGGY.NS/history, 2026-10-23
- Missing: News tone: the watcher's confirmed stories were not available.
- Missing: Sector trend: no NSE sector index matches this company.
Track: Ratings like this beat the Nifty 6 times in 10 since 2015 (829 of 1435 tested stock months). Every tested stock beat it 6 times in 10, so the edge is 0 points. That is too small to lean on.

rate('HDFCBANK') -> HDFC Bank Limited (stock, INR)
View: Neutral, score 56/100, confidence high. Rated 2026-10-25T16:43:36+00:00.
Outlook: Over the next 12 months we see HDFC Bank as Neutral, helped by growth, held back by price momentum, with high confidence (1 input missing).
- Growth (up): Revenue +81% and profit +21% year on year (latest quarter). Source: Yahoo Finance, https://finance.yahoo.com/quote/HDFCBANK.NS, 2026-10-25T16:43:37+00:00
- Valuation against sector peers (flat): P/E 15.1 against a peer median of 14.9 (ICICIBANK, KOTAKBANK, AXISBANK, SBIN). Source: Yahoo Finance, https://finance.yahoo.com/quote/HDFCBANK.NS, 2026-10-25T16:43:37+00:00
- Price momentum (down): -16% against the Nifty 50 over 12 months (last month left out); -12% from its 200-day average. Source: Yahoo Finance, https://finance.yahoo.com/quote/HDFCBANK.NS/history, 2026-10-23
- Sector trend (flat): Nifty Bank -4.1% over 3 months against the Nifty 50's -5.3%. Source: Yahoo Finance, https://finance.yahoo.com/quote/%5ENSEBANK/history, 2026-10-23
- Missing: News tone: the watcher's confirmed stories were not available.
Track: Ratings like this beat the Nifty 6 times in 10 since 2015 (829 of 1435 tested stock months). Every tested stock beat it 6 times in 10, so the edge is 0 points. That is too small to lean on.

rate('MF120716') -> UTI Nifty 50 Index Fund - Direct Plan - Growth (fund, INR)
View: Positive, score 62/100, confidence medium. Rated 2026-10-25T16:43:39+00:00.
Outlook: Over the next 12 months we see UTI Nifty 50 Index Fund as Positive, helped by consistency, with medium confidence (2 inputs missing).
- Returns against the benchmark (flat): +6.4% a year over 3 years against the Nifty 50 at +5.4%. Source: mfapi.in (AMFI NAVs), https://api.mfapi.in/mf/120716, 2026-10-23
- Consistency (up): Beat the Nifty 50 in 10 of the last 12 months. Source: mfapi.in (AMFI NAVs), https://api.mfapi.in/mf/120716, 2026-10-23
- Returns against its category (flat): +6.4% a year over 3 years against the median of 4 category peers at +7.2%. Source: mfapi.in (AMFI NAVs), https://api.mfapi.in/mf/120716, 2026-10-23
- Missing: Expense ratio: no free source we can read yet.
- Missing: Holdings mix: the fund's monthly portfolio isn't read yet.
Track: Ratings like this beat the Nifty 9 times in 10 since 2015 (529 of 613 tested fund months). Every tested fund beat it 8 times in 10, so the edge is +5 points. That is too small to lean on.

rate('MF118778') -> Nippon India Small Cap Fund - Direct Plan - Growth Option (fund, INR)
View: Positive, score 60/100, confidence medium. Rated 2026-10-25T16:43:40+00:00.
Outlook: Over the next 12 months we see Nippon India Small Cap Fund as Positive, helped by consistency, with medium confidence (2 inputs missing).
- Returns against the benchmark (flat): +12.6% a year over 3 years against the Nifty Smallcap 250 at +11.2%. Source: mfapi.in (AMFI NAVs), https://api.mfapi.in/mf/118778, 2026-10-23
- Consistency (up): Beat the Nifty Smallcap 250 in 8 of the last 12 months. Source: mfapi.in (AMFI NAVs), https://api.mfapi.in/mf/118778, 2026-10-23
- Returns against its category (flat): +12.6% a year over 3 years against the median of 4 category peers at +9.8%. Source: mfapi.in (AMFI NAVs), https://api.mfapi.in/mf/118778, 2026-10-23
- Missing: Expense ratio: no free source we can read yet.
- Missing: Holdings mix: the fund's monthly portfolio isn't read yet.
Track: Ratings like this beat the Nifty 9 times in 10 since 2015 (529 of 613 tested fund months). Every tested fund beat it 8 times in 10, so the edge is +5 points. That is too small to lean on.

rate('SFCTECH') -> SFC Environmental Technologies Limited (ipo, INR)
View: Positive, score 73/100, confidence high. Rated 2026-10-25T16:43:40+00:00.
Outlook: Over the next 12 months we see SFC Environmental Technologies as Positive, helped by valuation against listed peers and financials from the RHP, with high confidence (1 input missing).
- Valuation against listed peers (up): P/E 20.0 at the top of the Rs.313 to Rs.330 band against a listed-peer average of 101.4 (range 31.3 to 220.8). Source: Red Herring Prospectus, pages 184 and 185; price band from NSE, https://nsearchives.nseindia.com/content/ipo/RHP_SFCTECH.zip, 2026-10-25
- Financials from the RHP (up): Revenue +10.6% a year from FY2024 to FY2026, profit margin 19.9% in FY2026, net debt 0.05x equity. Source: Red Herring Prospectus, page 184, https://nsearchives.nseindia.com/content/ipo/RHP_SFCTECH.zip, 2026-10-25
- Fresh issue against offer for sale (flat): ₹150 crore fresh against about ₹517.53 crore sold by existing holders at the top of the band: 22% new money. Source: Red Herring Prospectus, page 168, https://nsearchives.nseindia.com/content/ipo/RHP_SFCTECH.zip, 2026-10-25
- Use of the money raised (up): Prepaying borrowings ₹42.23 crore; Working capital ₹74.92 crore; General corporate purposes, up to 25% of the fresh issue. Source: Red Herring Prospectus, page 169, https://nsearchives.nseindia.com/content/ipo/RHP_SFCTECH.zip, 2026-10-25
- Missing: Subscription: bidding opens 27-Oct-2026.
Track: No tested record for IPOs: a new listing has no price history to replay. Nothing to compare yet.
```

## The backtest (done-when 2)

`uv run python -m networth.ratings.track`, rerun 2026-10-25. The coordinator can rerun it and diff `networth/ratings/backtest.json`.

```
in_stock: 6052 cases over 50 assets, all beat 58%
  Strong      941/1607   59%  0 points
  Positive    763/1321   58%  0 points
  Neutral     829/1435   58%  0 points
  Weak        586/1046   56%  -2 points
  Avoid       395/643    61%  +3 points
in_fund: 1671 cases over 13 assets, all beat 82%
  Strong       29/44     66%  -16 points
  Positive    529/613    86%  +5 points
  Neutral     675/821    82%  +1 points
  Weak        110/163    67%  -14 points
  Avoid        19/30     63%  -18 points
us_stock: 3870 cases over 30 assets, all beat 58%
  Strong      567/907    63%  +5 points
  Positive    544/1014   54%  -4 points
  Neutral     574/1054   54%  -3 points
  Weak        350/604    58%  0 points
  Avoid       205/291    70%  +13 points
us_fund: 1419 cases over 11 assets, all beat 56%
  Strong       30/40     75%  +19 points
  Positive    266/394    68%  +12 points
  Neutral     291/604    48%  -7 points
  Weak        167/330    51%  -5 points
  Avoid        35/51     69%  +13 points
```

**What it says.** The price part of the score has no measurable edge for Indian stocks: every view beats the Nifty about 58% of the time, the same as every stock tested. For Indian funds, Strong did worse than average (66% against 82%), on only 44 cases. For US stocks the views don't line up: Avoid did best. Only US ETFs show a pattern in the expected direction (Strong +19 points, Positive +12), on small samples. Every rating says this in its track line, and calls an edge under 5 points or a sample under 30 "too small to lean on".

**Limits of the test, also on every `/r` page:**
- Only the price part of the score is replayed: momentum and trend for shares, momentum and consistency for funds. Growth, valuation, debt and news have no free point-in-time history, so the full score is untested.
- The stock lists are today's Nifty 50 and today's largest US companies, so there is survivorship bias.
- The Nifty 50 here is the price index without dividends, which flatters funds by about a point a year. That is why 82% of fund months beat it.

## `/sectors` on live prices (done-when 3, not yet on Telegram)

```
Sector moves to 2026-10-23

🔴 Bank -1.2% today, -2.7% this week, -3.4% this month
🔴 IT -0.3% today, +4.2% this week, +11.9% this month
🔴 Pharma -1.0% today, -1.9% this week, -5.9% this month
🔴 Auto -0.6% today, -2.8% this week, -8.2% this month
🔴 FMCG -1.0% today, -4.7% this week, -6.5% this month
🔴 Metal -2.7% today, -4.5% this week, -11.6% this month
🔴 Energy -1.7% today, -4.7% this week, -8.5% this month
🔴 Realty -2.4% today, -5.4% this week, -9.0% this month
🔴 PSU -1.6% today, -4.0% this week, -7.6% this month
🔴 Midcap -2.1% today, -5.2% this week, -10.1% this month
🔴 Smallcap -2.8% today, -7.0% this week, -10.3% this month

The watcher's stories aren't available, so moves show without news.

Prices: Yahoo Finance, NSE index closes to 2026-10-23. News: confirmed by the Networth watcher.
```

Locally there is no watcher database, so no stories show. With one, each sector lists up to 3 stories as "· title (publisher, publisher)" (tested in `tests/test_sectors.py` and `tests/test_bot_sectors.py`).

## Sources

| Data | Source | Key |
|---|---|---|
| Share and ETF facts (growth, P/E, P/B, debt to equity, margin, sector) | Yahoo Finance via yfinance `Ticker.info` | none |
| Daily closes, NSE sector indices, Nifty 50, S&P 500, SPDR sector ETFs | Yahoo Finance via `Ticker.history` | none |
| Mutual fund NAVs and scheme search | https://api.mfapi.in (AMFI's daily NAVs) | none |
| Upcoming and current IPOs, issue size, subscription | NSE `api/all-upcoming-issues`, `api/ipo-current-issue`, `api/ipo-detail` (the cookie from the home page) | none |
| IPO financials, peer P/E, use of proceeds | The RHP PDF from NSE's archive, read with pdftotext; numbers and pages in `ipo_rhp.json` | none |
| News | The Networth watcher's confirmed stories (`data/watcher.sqlite`) | none |

Yahoo tickers checked live: `^NSEBANK`, `^CNXIT`, `^CNXPHARMA`, `^CNXAUTO`, `^CNXFMCG`, `^CNXMETAL`, `^CNXENERGY`, `^CNXREALTY`, `^CNXPSE` (PSU), `^NSEMDCP50` (Midcap), `NIFTYSMLCAP250.NS` (Smallcap). `^CNXMIDCAP`, `^CNXSMCAP` and `^CRSMID` have no data on Yahoo.

## Decisions

1. **The contract block.** The 13C types are in a second `ts` block in `phase-10-contract.md`, so `site/lib/contract.ts` stays a copy of the main block until 13B adds this one.
2. **One switch for alerts.** `/alerts off` flips the existing `alerts_on`, so it also silences the older rare-event alerts. Briefs and watches the user asked for still arrive.
3. **No double messages.** Watched topics stay with `networth.bot.watches`. The notifier covers holdings, their sectors and the plan's Nifty 50.
4. **Rating changes.** The first time a user hears about a holding, its view is only remembered. The rating line appears when a later view differs.
5. **The watcher job's status line** now ends with ", N news alerts sent", and the three `test_schedule.py` assertions changed with it. A notifier failure is logged and never undoes the cycle's other messages.
6. **Peers and sector indices** are short lists by Yahoo industry, in `ratings/kinds.py`. Only the lists are ours; every multiple is read live. An industry with no list says "no peer set" and lowers the confidence.
7. **Money** goes through one Python function that mirrors 13A's TypeScript `moneyShort`, because the cards send formatted strings.

## Known gaps

- **Expense ratio and holdings mix** for funds have no free, no-key source I could find, so every fund rating names them as missing. A paid provider would need an OWNER NEEDED.
- **IPO financials** come from a file of RHP numbers, filled for SFCTECH only. Another IPO rates on NSE's live data and names the RHP items as missing until its numbers are read in.
- **News tone** is a word list over confirmed headlines, not a model. The ceiling is sarcasm and mixed headlines. The upgrade is a tone field from the watcher's judge.
- **Peer sets** cover 12 industries. Swiggy has no NSE sector index, so its sector trend is missing. AAPL has only one peer with a multiple, so its valuation is missing.
- **The rating cache** is per process, one hour. Each new name costs about 5 to 10 seconds of source reads the first time.
- **Nothing here is deployed.** Every 13C commit after `0b26b4d` is local only.

## Commits

Pushed: `55a0177` (signature and contract), `decdd59` (engine and backtest), `0b26b4d` (sector board).
Local only, by owner order: `668a746` (`/sectors`), `de91784` (notifier and `/alerts`), `d9e38d1` (`/r` pages and the API), `e7b0f5d` (money), `9182e92` (fund wording), and this report.

## OWNER NEEDED

1. **Push and deploy.** Allow the local commits to go to `main`, then redeploy:
   ```bash
   git push origin main
   maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json
   ```
   Then send `/sectors` to the bot on Telegram for done-when 3, and open `https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/r/hdfcbank` signed out for done-when 5.
2. **A live alert.** Save holdings that include HDFC Bank, then wait for a watcher cycle in market hours that confirms a story naming it. One message should arrive, and none between 22:00 and 08:00 IST.
