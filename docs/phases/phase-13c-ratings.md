# Phase 13C: ratings, the sector board and the news notifier

## Why

These are the owner's words on 2026-10-25:
- "we have rates a fund or a share or a stock or an ipo, based on what future potential it can have"
- "forget legalities bro, now we have to think on how to bring value"
- "where is the news notifier, where is the sector related growth or loss backed by news"
- "my mentor said we can share our analysis to the users and wider audience"

The no-picks rule is gone. Networth now gives a view. What makes it better than Perplexity is that every view shows what it is based on, and how often views like it were right in the past.

## Build

Own the new modules `networth/ratings`, `networth/sectors` and `networth/notify`, plus their tests. Add bot commands only in new files, and register them with one line each in `networth/bot/commands.py`. Do not touch `site/` (13B), `networth/chat` or the guard (13A), or `networth/holdings` (Phase 12). 13A calls your `rate(...)` function, so commit its signature first.

1. **The rating engine** (`networth/ratings`). It rates a stock, a mutual fund, an ETF or an upcoming IPO:
   - a view: **Strong**, **Positive**, **Neutral**, **Weak** or **Avoid**
   - a score out of 100
   - a 12-month outlook in one sentence
   - its drivers, each with a sourced number:
     - growth: revenue and profit trend
     - valuation against sector peers
     - balance sheet: debt
     - price momentum
     - the news tone over the last 30 days, from our confirmed-story pipeline
     - the sector trend
   - for a fund: its returns against its category and benchmark, the expense ratio, its consistency, and its holdings mix
   - for an IPO: the valuation against listed peers, the fresh issue against the offer for sale (OFS), the use of the money raised, the subscription numbers when live, and the financials from the RHP
   
   Every input comes from a real source with a time. Missing data lowers the confidence and says so. It is never filled in.
2. **The track record is part of the product.** Backtest the scoring on our index and stock history: how often did a Strong or Positive rating beat the Nifty over the next 12 months? Show that hit rate on every rating ("Ratings like this beat the Nifty 6 times in 10 since 2015"). If the measured edge is weak, show that too. Honesty is what sets us apart. Store the backtest table so the site can draw it.
3. **The sector board** (`networth/sectors`). Show the day, week and month change for the main NSE sectors (Bank, IT, Pharma, Auto, FMCG, Metal, Energy, Realty, PSU, Midcap, Smallcap). Beside each move, show the 1 to 3 confirmed news stories behind it. Expose `/sectors` in the bot and a typed `sectors` card for the site (add it to `docs/phases/phase-10-contract.md`).
4. **The news notifier** (`networth/notify`). Push a Telegram message when a confirmed story moves something the user owns, watches or has in their plan. It covers a holding, its sector, or an index they follow. The message gives what happened, the price move, what it means for their rupees, and our rating if it changed. Caps: at most 3 alerts a day per user, quiet hours 22:00 to 08:00 IST, and `/alerts off` to stop. Reuse the watcher and the outbox that exist. Never build a second scheduler.
5. **Shareable analysis.** Each rating and sector move gets a public page, `/r/<slug>`, that anyone can open without signing in. It shows the rating, the drivers, the sources and the track record, so users can share it. Serve it from the Python server's existing templates. 13B may restyle it later.

## Not in this phase

- No paid data providers without an OWNER NEEDED.
- No auto-trading.

## Done when

1. `rate("SWIGGY")`, `rate("HDFCBANK")`, a large-cap index fund, a small-cap fund and one upcoming IPO each return a view, a score, the drivers with sources, and the track-record line. Paste them in the report.
2. The backtest table exists, and its hit rate is computed rather than written by hand. The coordinator reruns it.
3. `/sectors` shows today's sector moves with the news behind each one, live on Telegram.
4. A confirmed story about a user's holding sends one alert that respects the caps and quiet hours. Tests cover the cap, quiet hours and `/alerts off`.
5. `/r/<slug>` opens without sign-in and shows the rating and its sources.
6. Every number in every rating traces to a source and a time. A test checks that no driver lacks a source.
7. `make check` exits 0. Record the exit code.

## Sources of truth

- Look up each data source's own docs. Never invent an API, ticker format, model id or flag. Prefer free sources with no key. If one needs a key, print OWNER NEEDED.
- `docs/phases/phase-3c-report.md` for watches and the outbox. Read the backtest code that exists for history.

## The gate

`make check`. Capture its exit code. A pipe into `tail` hides it.

## Branch policy

Push straight to main after `git pull --rebase`. Push the `rate()` signature and the contract change first. The coordinator reviews and deploys.

## OWNER NEEDED protocol

Before a human-only step, print `OWNER NEEDED: <what> — <how>` and wait.

End with `PHASE 13C READY FOR REVIEW`.
