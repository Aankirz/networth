
## 2026-10-24 — Precedent build plan
- Added build-plan.html in GrowwOS: 24h build plan, data shape, confidence tiers, timeline, demo flow, risks for the Keiki x Maritime week-one entry.

## 2026-10-24 — Precedent product spec
- Added product-spec.html: PM view (Mom Test, Krug, Hooked, KISS), journey, 7 screens, message anatomy, intents, v1 scope, metrics.

## 2026-10-24 — Build plan v2
- Rewrote build-plan.html: push-first loop, Deja working name, stack from tooling research, harness layout (zoya fork + SimbianOS patterns), 12 skills, autoresearch-style loop with outside check, 3-track timeline.

## 2026-10-24 — Plan v2: Keiki/Maritime findings
- Updated stack and risks in build-plan.html with Keiki notice API, iMessage limits, Maritime deploy contract.

## 2026-10-24 — Name and tagline
- Renamed product to Deja in product-spec.html, domain deja.money, tagline "Know what the news means for your money" in both plans.

## 2026-10-24 — Renamed to Networth
- Product name Networth, domain getnetworth.app, in product-spec.html and build-plan.html.

## 2026-10-24 — Networth final specs (black theme)
- GrowwOS: added assets/style.css and assets/sketch.js (shared black, hand-drawn style with rough.js), product.html (final product spec) and tech.html (final tech spec with architecture, data model, engine, flows, Maritime and Keiki usage, phases, risks). Supersedes build-plan.html and product-spec.html.

## 2026-10-24 — Networth personalization and plan
- GrowwOS product.html: added "Made for you" section (profile inputs, one event for three people, user-chosen wealth-manager-style plan with buckets, the personalized-advice line we don't cross), scope and tagline updates. tech.html: Profile/Plan fields and the per-user filter, rank, size, compose pipeline. Why: the user asked for messages that differ per user.

## 2026-10-24 — No F&O, user-written rules
- product.html scope: cut futures/options/leverage/shorting; added user-authored rule alerts as the honest version of buy/sell timing.

## 2026-10-24 — Channels confirmed in Keiki
- tech.html: Keiki supports Telegram, WhatsApp and iMessage ($300/mo, coupon field) from one agent; launch order Telegram, WhatsApp, iMessage.

## 2026-10-24 — Spec consistency pass
- product.html, tech.html: replaced iMessage-first wording with Telegram, WhatsApp, iMessage through one Keiki agent; updated limits, landing buttons, open questions and the architecture sketch labels. Verified both pages load with no console errors and all sketches draw.

## 2026-10-24 — Demo shows the proof
- product.html demo: added watcher log, event study, outside check, leak test and held-out score steps; nothing faked.

## 2026-10-24 — Build-time vs live Claude
- tech.html: improvement loop and evals run in Claude Code at build time; API key only for the live product (Haiku, Sonnet). Dropped Opus API use.

## 2026-10-24 — Dropped iMessage
- product.html, tech.html: removed iMessage per user; channels are Telegram then WhatsApp via Keiki. iMessage moved to Cut.

## 2026-10-24 — Who decides what
- tech.html: new section mapping each decision to Haiku, Opus, the engine, code or Sonnet; Opus 5.5 does per-event judgment once for all users; who pays for models.

## 2026-10-24 — Per-user COGS
- tech.html: added cost-per-user-per-month table (variable vs shared) under Who decides what.

## 2026-10-24 — Full unit economics
- tech.html: replaced the per-user cost table with token-level model call costs, free levers (Batch API, caching), and other costs (Exa, market data licensing, platforms, WhatsApp, domain).

## 2026-10-24 — Broker linking for the demo
- product.html, tech.html: added US read-only broker connection via SnapTrade (free Build tier, 5 connections) to v1 onboarding, env vars and security; India linking deferred.

## 2026-10-24 — Parked broker linking
- product.html, tech.html: removed SnapTrade from v1 and the demo per user; listed broker linking as parked until the user asks.

## 2026-10-24 — India and US markets
- product.html, tech.html: India added alongside US (personas, scope, SEBI note, Indian events and data, NSE hours, Indian sources, curator, risks, Profile currency/markets).

## 2026-10-24 — Verified Indian data coverage
- tech.html risks: recorded actual yfinance start dates for Indian indices (Sensex 1997, Nifty 2007, most sectors 2010-11, Media/Fin missing).

## 2026-10-24 — Repo and phase 1 brief
- git init (branch phase/p1-engine, no commits on main), .gitignore, docs/research copied from scratchpad, docs/phases/phase-1-engine.md brief for the builder session.

## 2026-10-24 — GitHub remote, push to main
- Repo Aankirz/networth (private) created; local git identity set to Aankirz noreply; branch renamed to main; phase 1 brief branch policy changed to push straight to main per owner.

## 2026-10-24 — Builders use poteto-mode
- Phase 1 brief: builder must invoke pstack:poteto-mode first, per owner.

## 2026-10-24 — Product knowledge file and investing-day framing
- Added knowledge/PRODUCT.md, the product knowledge every agent loads and every builder reads.
- Rewrote product.html around the investing-day brief, the scoreboard, rare alerts, pull-only "today", tip checks, Hindi/Hinglish, the public track record and a "Why not Perplexity" section. Removed holdings, screenshots, the 7am brief and the Sunday report card.
- tech.html: harness loads PRODUCT.md into every agent prompt (cache-stable), Profile drops holdings and gains invest_day and lang, onboarding and brief flows and the cost table updated for one brief a month.

## 2026-10-24 — Phase 1 scaffold and price fetcher
- Added uv package `networth/` (Python 3.12, pandas, yfinance; ruff and pytest dev), Makefile `make check`, and `networth/engine/fetch.py`, which caches US, India and Kenneth French 49-industry daily series in data/prices/ and prints a coverage table. Why: the Phase 1 engine needs local price history before any backtest.

## 2026-10-24 — Created .env
- Generated TELEGRAM_WEBHOOK_SECRET and LINK_SIGNING_SECRET, set AWS_REGION and AWS_PROFILE. File is gitignored, mode 600.

## 2026-10-24 — Networth switches live models to OpenAI
- Copied OPENAI_API_KEY from zoya .env into GrowwOS .env, removed AWS_PROFILE. Verified gpt-5.6 luna/terra/sol. Memory updated.

## 2026-10-24 — Event library and FOMC calendar
- Added networth/engine/events.csv (287 sourced rows: 133 us, 111 in, 43 global; every type has 11+ rows) built by three curator agents and confirmed row by row against its source by a checker agent (9 source or note fixes, 0 deletions), and networth/engine/fomc.csv (261 scheduled FOMC announcements 1994-02-04 to 2026-09-16 from the Fed's own calendar pages). Why: the backtest and the pre-FOMC outside check need dated, sourced events.

## 2026-10-24 — Keiki key added
- KEIKI_API_KEY in GrowwOS .env, verified. Keiki compatible endpoints route to Keiki agents, not raw models.

## 2026-10-24 — Exa key added
- EXA_API_KEY in GrowwOS .env, verified with one search.

## 2026-10-24 — Telegram bot token added
- TELEGRAM_BOT_TOKEN for @networth_professor_bot in GrowwOS .env, verified with getMe.

## 2026-10-24 — Backtest and leak test
- Added networth/engine/model.py (Event/Episode/Reaction/BaseRate dataclasses, the sqlite schema, atomic write_db, read-only RatesDB) and backtest.py (no-peek entry rule with KnownTime/UnknownTime, trading-day episode merging, eras as data, French 49-industry proxies, Nifty-on-Sensex benchmark splice, seeded per-row baseline, vault as an as_of cut), with tests: a leak test with six broken canaries and a poisoned real-build case, and the method-rule tests. Why: the engine computes every base rate, and the leak test must prove no return peeks.

## 2026-10-24 — Phase 2 brief
- Added docs/phases/phase-2-watcher.md: news watcher, confirmation, classification, triggers, OpenAI model layer via config.

## 2026-10-24 — Odds API, event checker and outside check
- Added networth/engine/odds.py (odds, position_range, compare as TypedDict shapes over the sqlite file), check_events.py (one parser, library targets, live link check with a 20 s per-URL deadline, IPv4 first, one retry on transport errors) and outside_check.py (pre-FOMC drift on SPY and ^GSPC daily closes against Lucca and Moench 2015), with tests. Why: Phase 1 done-when items 3, 8 and 9; the retry exists because one resolver blip failed a live run.

## 2026-10-25 — Phase 1 hand-off report
- Added docs/phases/phase-1-report.md: coverage table, event counts by type and region, the method as built, every done-when result with its command, five base rates with episodes and baselines, the pre-FOMC outside check (matches in the paper's sample, fades after 2011), known gaps and every deviation from the brief. Why: the coordinator reviews Phase 1 against it.

## 2026-10-25 — check_events: per-host cap and 429 backoff
- check_events.py now allows at most 2 requests per host (1 for web.archive.org), round-robins URLs across hosts, and on HTTP 429 waits for Retry-After (clamped to 5 s, 2 s if missing) before one retry inside the 20 s deadline; a persistent 429 is still a dead link. pandemic_20090611 now cites the CDC page on the WHO declaration instead of web.archive.org, with UN News in notes. Why: coordinator review round 1 saw archive.org answer 429 and check_events exit 1 twice from a clean clone.

## 2026-10-25 — Phase 1 report: review round 1 numbers
- Updated docs/phases/phase-1-report.md with the per-host cap and 429 rules, the CDC source for pandemic_20090611, the new test counts (59 pass and 4 skip on a clean clone, 63 with a build), and two clean-clone check_events runs that both exited 0. Why: the report must match a fresh run.
