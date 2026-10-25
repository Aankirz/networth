
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

## 2026-10-25 — Phase 1 passed, Phase 2 launched
- Phase 1 review passed at 517915e. Spawned Phase 2 builder 4b8feb90. Monitor cron now watches the Phase 2 pane.

## 2026-10-25 — Parallel briefs for Phase 3A and Phase 4
- Added docs/phases/phase-3a-delivery.md and phase-4-web.md with split file ownership so they run alongside Phase 2.

## 2026-10-25 — PRODUCT.md: simplify angle
- Added the "Explain this" moment, widened the promise to simple investing for anyone, logged the decision.

## 2026-10-25 — Watcher config and model layer
- Added networth/config.toml + config.py (typed Config, roles to OpenAI models with prices and source URLs, Exa query table and budget, confirm and trigger thresholds; keys from env or .env, ConfigError names a missing key), net.py (IPv4-only httpx2 client, thread deadline, one jsonl line per paid call) and llm.py (group_articles and classify_story over the Responses API, output validated against inputs and the events.csv table), with tests. Added openai and httpx2 (openai's own HTTP library, imported directly for the IPv4 transport). Why: Phase 2 model layer.

## 2026-10-25 — Watcher store, pull, grouping and confirmation
- Added networth/watcher/store.py (the watcher data model and the only module that knows data/watcher.sqlite: articles, stories, decisions, insights, cycles; keyed writes), pull.py (Exa search over the IPv4 deadline client, results parsed at the boundary into Articles with publisher and wire origin) and group.py (cheap-model grouping of unassigned articles only, and the pure confirm rule: a primary domain, or 3 distinct origins inside 24 h, wire reposts counted once), with fixture articles holding a planted single-source rumour and a Reuters story reposted by 5 outlets. Why: Phase 2 done-when 6 and 10.

## 2026-10-25 — Watcher classification and triggers
- Added networth/watcher/classify.py (judge model once per confirmed story, answers validated against the (type, cause) table from events.csv, a per-cycle cap) and triggers.py (news-first Insights holding the exact odds() dict per configured asset; price-first jump on excess or raw daily return beyond 2.5x the prior 60-day std, linked to a confirmed classified story or noted as unexplained), with tests that compare Insight numbers to odds() on a built db and on the real data/base_rates.sqlite. Why: Phase 2 done-when 7 and 8.

## 2026-10-25 — Watcher cycle, decision log and report
- Added networth/watcher/log.py (decision log entries and their text), run.py (python -m networth.watcher.run --once: pull, group, confirm, classify, trigger, a cycles row and a one-screen summary with counts, rejections by reason and the cycle's spend from llm_calls.jsonl; ConfigError exits 2 with the message) and report.py (confirmed stories with publishers or primary source, rejected stories with reasons, insight headline numbers, latest cycle, spend; last 48 h or --today), with tests for a repeat run leaving counts unchanged, Exa and OpenAI calls that never connect ending at the deadline and logged as failed, and the missing-key exit. Why: Phase 2 done-when 2, 5, 9 and 10.

## 2026-10-25 — Beginner video research doc
- Added docs/research/research-beginner-videos.md (6 reference videos: concepts, teaching patterns, no-copy advice).

## 2026-10-25 — Watcher fixes from the first live cycles
- networth/llm.py: a rule-breaking grouping answer is repaired (unknown ids dropped, duplicates keep the first group, unknown story ids become new stories, left-out articles become their own story) instead of discarded; the judge returns event_date and code rejects an event dated before the lookback window as "old news". Why: live run 1 split 2 of 3 batches into single-article stories (84 artificial "1 publisher" rejections), and Exa dates recrawled pages, so a May 2025 airstrike and the Oct 7 RBI hike read as new events.
- networth/config.toml: judge cap 12 -> 40 (about $0.0033 a call, measured). networth/watcher/group.py: "1 publisher" wording.

## 2026-10-25 — Watcher report lists what the cycle decided
- networth/watcher/store.py and report.py: the decision log filters stories by when they were decided, not by their first article's publish date, with a test that a stale publish date still shows. Why: the live report listed 24 confirmed while the cycle counted 30, because Exa returns date-only or recrawl dates.

## 2026-10-25 — Phase 4 web pages
- Added networth/web/ (FastAPI router: /, /why, /what-if, /scoreboard, /track-record, /stats; Jinja2 templates; one stylesheet with light and dark tokens; python -m networth.web on :8090), tests/test_web.py, docs/phases/phase-4-report.md and 24 screenshots in docs/phases/phase-4-shots/. Added jinja2 via uv add. Why: Phase 4 brief; every number on the pages comes from odds(), compare() or position_range().

## 2026-10-25 — FRED key added
- FRED_API_KEY in GrowwOS .env, verified with USREC, CPIAUCSL, FEDFUNDS.

## 2026-10-25 — Phase 2 hand-off report
- Added docs/phases/phase-2-report.md: role-to-model map with OpenAI prices and source URLs, one live cycle's counts (146 articles, 71 stories, 30 confirmed, 41 rejected by reason, 10 insights), cost per cycle ($0.29 cold, $0.11 warm) and per day at 43 cycles (about $5 to $5.50, mostly Exa), every done-when result, known gaps and deviations. Corrected the judge cost comment in networth/config.toml to the measured $0.006 a call (the earlier entry's $0.0033 predates the event-date field). Why: the coordinator reviews Phase 2 against it.

## 2026-10-25 — Phase 1B brief
- Added docs/phases/phase-1b-regimes.md: FRED and India CPI regimes, additive engine change.

## 2026-10-25 — Phase 3A: server, Telegram bot and onboarding
- Added networth/app (FastAPI: /health, secret-checked /telegram/webhook, optional networth.web mount, SQLite Profile/Plan/Message store, env settings), networth/bot (IPv4 deadline Bot API client with one 429 retry, pure onboarding state machine with amount parser, command shell with a stop/pause send gate, long-poll runner), Dockerfile, .dockerignore, docs/deploy.md, docs/phases/phase-3a-report.md and 62 tests. Added fastapi and uvicorn. Why: Phase 3A brief.

## 2026-10-25 — Phase 1B: macro regimes in the engine (uncommitted, for lead review)
- Added networth/engine/macro.py (FRED USREC/CPIAUCSL/FEDFUNDS/UNRATE and MoSPI India CPI into data/macro/, the recession_followed and inflation_high rules as a registry), regime_rates table and RegimeRate in model.py, regime rows in backtest.py, odds(regime=) and split() in odds.py, regime canaries and --regime-impl in tests, tests/test_regimes.py. Why: Phase 1B brief; base_rates rows unchanged (3,020).

## 2026-10-25 — Watcher: event date and region from the judge, age decided each cycle
- The judge's answer now carries event_date and region (in/us/global) and is cached as a fact; validate_classification no longer drops old events, so a verdict never depends on when it was asked.
- triggers writes insights only for events no older than classify.event_max_age_days (7, reason in config.toml) on the cycle's date, and only for assets in the story's region (India story -> Indian assets).
- Store.open migrates old files once (adds event_date, region; clears every old answer and the derived insights so each story is judged again). The report prints "old news" at render time and now loads config.

## 2026-10-25 — Phase 3B brief drafted
- docs/phases/phase-3b-product.md: brief, chat intents, Explain this, guard, deploy fix for missing sqlite, Jev for intent picks (gated on accuracy), Keiki via external harness. Copied Jev gateway keys from zoya .env into Networth .env (values not printed).

## 2026-10-25 — Watcher: one event, many stories
- Grouping now offers the model every story with an article pulled in the lookback (articles.pulled_at), not stories filtered by first_seen, which comes from stale or date-only search publish dates; a later batch can now join a story an earlier batch made.
- Insights are keyed by type + event date + asset + trigger, stored under the first story, so two stories of one event write one insight set (insights table gains event_date; old rows are cleared and rebuilt).
- The report groups confirmed stories of one (type, event date) under an EVENT heading and opens with the newest confirmed India story.

## 2026-10-25 — Watcher: price-first on fresh closes, threshold pinned
- New networth/watcher/prices.py downloads recent closes for every price_watch asset and benchmark in one yfinance call over an IPv4 curl session, under http.prices_deadline_s (60); nothing is written to data/prices. A failed download is one "price-first skipped" error; each missing asset is its own error line; counts gain price_assets_checked and price_assets_total.
- Threshold tests now build last-day moves at exactly 1.01, 0.99, -1.01 and -0.9 times 2.5 sigma, raw and on the excess, plus one test through the shipped config.toml that goes red if price_multiple is changed to 3.0.

## 2026-10-25 — Phase 3A: idempotent updates and serialized handling
- Added an updates table with claim_update(update_id) and a process-wide lock in handle_update, plus replay and concurrent-tap tests. Why: Telegram delivers at least once and the webhook runs on a threadpool; the live check exposed both risks.

## 2026-10-25 — Bedrock added to Phase 3B brief
- Owner reports CTO approval for Simbian Bedrock. Phase 3B adds a bedrock provider and compares it with OpenAI for the writer role.

## 2026-10-25 — Bedrock removed from Phase 3B brief
- Owner clarified Simbian Bedrock is only for running Claude Code builders when plan usage runs out, never in the product. Reverted the brief line.

## 2026-10-25 — Phase 2 review round 2
- networth/watcher/log.py: the "Newest confirmed India story" line prints the event date and marks old news, with tests. docs/phases/phase-2-report.md: round 2 live cycle (146 articles, 73 stories, 28 confirmed, 45 rejected, 5 region-filtered insights, 24 of 24 price assets on fresh closes, $0.29), 250 tests, the 7-day old-news rule, event-keyed insights, the store migration, and the remaining gap that rejected stories are not merged with their event. Why: coordinator review round 1 items 1 to 6.

## 2026-10-25 — Spec pages brought up to date
- product.html and tech.html now match what was built (OpenAI live models, direct Telegram delivery with Keiki optional, guard.py, Jev, Maritime deploy, 1B regimes, measured watcher cost, Explain this, real phase list), because the pages still described Claude/Bedrock and Keiki notice delivery.

## 2026-10-25 — Phase 1B CPI release dates from ALFRED
- networth/engine/macro.py: US CPI is now FRED/ALFRED initial releases (output_type=4), cached as date,value,released; the inflation rule and the vault cut use each month's recorded first-publication date and fall back to the fixed lag (US 21, IN 14) only where none is recorded. Why: three fed events (fed_cut_19960131, fed_hike_20050322, fed_cut_20251210) read a CPI print released after them under the fixed 21-day lag. Also renames url->url_template, needs->series_by_type, keep->is_all_india_general, and types regime values as Literal["yes","no"]. Tests: delayed-release leak cases, ignores_release_dates canary, real-data check over every fed event.

## 2026-10-25 — Phase 3B: web reads the engine sqlite from DATA_DIR
- networth/web/routes.py rates_db now uses Settings.rates_db (DATA_DIR/base_rates.sqlite) instead of the engine's repo-relative default, because in the container that path is /app/data, which does not exist, and every engine page returned 500. track_record.html gets its row count from the view. The 404 and 400 pages joined the banned-word and disclaimer test.

## 2026-10-25 — Phase 3B: rejected stories shown under the confirmed event they are about
- One cheap-model call per cycle (llm.match_related, classify.relate_rejected) records, for each rejected story, the confirmed event (type:event_date) it is about; stories table gains related_event and related_at. The decision log prints those stories under their EVENT heading with their own rejection reason, and the newest-India line says 'not one of the event types we count' instead of ', none'. Why: the honesty log showed 'RBI holds repo rate' as an unrelated rejection next to the confirmed RBI hike.

## 2026-10-25 — Phase 3B: guard.py send gate and push_rates.sh
- networth/guard.py checks every model draft: numbers must appear in the source text after normalising (lakh, crore, k, commas, %, ordinals, Devanagari digits), no banned words in English, transliterated Hindi or Devanagari, no advice phrasing; one rewrite then the template; verdicts appended to a jsonl log. tests/test_guard.py. scripts/push_rates.sh uploads data/base_rates.sqlite to the Maritime /data volume in 80 KB gzip chunks with a sha256 check, because Maritime's upload fails above about 80 KB.

## 2026-10-25 — Phase 3B chat, briefs and explain-this
- Added networth/chat (intent pick via Jev or the cheap model, what happened today, why, tip check, explain-this for text, links and screenshots, plan question), networth/brief and bot/briefs (investing-day brief, once per day), /brief and brief buttons, photo handling, same_claim model call, Services, glossary. 353 tests green.

## 2026-10-25 — Per-user /u/{token} page
- Added networth/app/links.py (HMAC-signed, 30-day links keyed by LINK_SIGNING_SECRET), the /u/{token} route and user.html (plan and last brief, noindex, no-store), a friendly 404 for bad links, and the link in /plan and on the brief. 363 tests green.

## 2026-10-25 — Rare alerts and Maritime schedules
- Added networth/bot/alerts.py (8+ episodes, 15-point gap, not weak, cap 2 a month, once per event, alerts_on only) and networth/app/schedule.py with GET /schedules (watcher every 30 min in NSE hours, brief 08:00 IST) and POST /chat for scheduled prompts in a background thread, with a 25-minute watcher gap, a single job lock and per-day brief claims. The server now passes real Services to the webhook.

## 2026-10-25 — Jev intent eval
- Added evals/intent_accuracy.py (36 labelled English, Hindi, Hinglish messages). Run 1: Jev and cheap model 34/36 each, medians 386 ms vs 1135 ms. Tightened plan_question, explain_this and tip_check criteria; run 2: 36/36 each, 422 ms vs 1082 ms. Kept use_jev_for_intent=true.

## 2026-10-25 — Phase 3B docs and decision log
- Updated docs/deploy.md (model and Jev env vars, push_rates.sh and the 80 KB upload limit, schedules, /brief). Wrote docs/phases/phase-3b-report.md (built, live samples, guard rules, cost, Jev table, OWNER NEEDED, gaps, deviations). Committed docs/phases/phase-3b-decisions.tsv (17 rows).

## 2026-10-25 — Phase 3B review round 1
- Owner deployed 3B (65ab6449); live routes 200, schedules listed. Wrote docs/phases/phase-3b-round2-gaps.md (12 gaps: guard bypasses, glossary advice, /chat auth, rate limit, lost briefs/alerts, held-out Jev eval) and sent it to the builder.

## 2026-10-25 — Phase 3B live Telegram review
- Live checks on deploy 65ab6449: explain-this and /u pass; brief, today and why empty because the VM has no watcher data. Appended items 13-17 to docs/phases/phase-3b-round2-gaps.md and sent to builder.

## 2026-10-25 — Guard hardening and no long dashes
- guard.py: numbers glued to Rs/INR and fullwidth digits, number words, NFKC and zero-width stripping, spaced-out letters, should/recommend, Devanagari चाहिए करें कीजिए, Hinglish imperatives, score and rank banned. llm.write tells the writer not to use long dashes and replaces any that come through. Review round 2 items 1, 2, 16.

## 2026-10-25 — Chat answers from the last news check and the engine; tip verdict first
- today.py falls back to the last news check and says when; a why question naming an event type answers from brief.history; tip replies lead with Confirmed or Not confirmed and quote hype phrases (round 2 items 13, 14, 15).

## 2026-10-25 — Glossary reads as description
- Reworded advice rows and four guard-flagged rows; dropped teaching patterns 1 and 12; test runs every glossary cell through the guard (round 2 item 3).

## 2026-10-25 — Watcher refuses forged runs outside market hours
- Maritime scheduled prompts carry no secret, so the watcher now runs only inside its own cron window; schedule.py and deploy.md state the bounded cost instead of claiming it is zero (round 2 item 4).

## 2026-10-25 — Hourly cap on paid chat answers
- product.chat_max_per_hour = 20; Store.claim_answer counts a rolling hour in one transaction; past the cap Turn.answer sends a polite note and runs no paid call (round 2 item 5).

## 2026-10-25 — Non-ASCII link tokens get a 404
- links.verify rejects non-ASCII tokens before isdigit and compare_digest, which gave a 500 (round 2 item 6).

## 2026-10-25 — Failed brief releases its claim
- send_brief deletes the day's claim when compose or send raises, so the next run sends it (round 2 item 7).

## 2026-10-25 — Phase 3C Keiki brief
- Wrote docs/phases/phase-3c-keiki.md (Keiki external harness, email channel, watch-this, memory callbacks, traces, Maritime mtm.sh URL and egress allowlist). Spawned the 3C builder limited to the Step 0 spike until 3B round 2 is pushed. Owner says the Keiki org is on the Scale plan.

## 2026-10-25 — Alerts survive a VM stop and a failed send
- watcher_cycle hands alerts every insight decided in the last event_max_age_days, so a stop between cycle and alerts is caught up next run; a failed alert send releases its claim (round 2 item 8).

## 2026-10-25 — Explain-this streams a capped page
- page_text streams the body and stops at MAX_PAGE_BYTES instead of downloading it all (round 2 item 10).

## 2026-10-25 — A fresh page link retires older ones
- /plan and the brief issue a new link_token each time (Store.new_link_token), so earlier /u/ links 404; save_profile no longer overwrites link_token, so a stale profile copy cannot revive a retired link (round 2 item 11).

## 2026-10-25 — Repeat /brief refreshes after newer news
- A repeat /brief rewrites the brief when a news check finished after it was stored; Services.last_news_check replaces schedule.last_cycle_end (round 2 item 13).

## 2026-10-25 — Push watcher data to the VM
- scripts/push_data.sh copies any data/*.sqlite onto /data in checksummed 80 KB chunks; push_rates.sh wraps it; deploy.md documents seeding news after a deploy (round 2 item 13).

## 2026-10-25 — Phase 3B round 2 report
- Report: held-out Jev table and decision, round 2 fixes table, VM news seeding, watcher trigger listing (Asia/Kolkata), guard rules, test count 426; decision-log rows (round 2 items 12, 17).

## 2026-10-25 — Phase 3C spike
- docs/phases/phase-3c-spike.md answers the six Keiki questions with redacted evidence, and records the first writes: agent 8d5b1d0c created, external push harness set, AgentMail inbox networth@agentmail.to connected.

## 2026-10-25 — Phase 6 method v1
- docs/phases/phase-6-method.md fixes the plan-range sources (^NSEI, ^NSEMDCP50, FRED INDIR3TIB01STM, MoSPI CPI), window, bootstrap, investing, fall and rounding rules before any run.

## 2026-10-25 — Phase 6 return table and scaffold
- networth/sim/config.py, data.py build data/sim/returns.csv (177 months, 2012-01..2026-09); sim/__init__.py scaffolds PlanRange and the API; numpy added with uv add because sim imports it directly (it was only a pandas transitive).

## 2026-10-25 — Phase 6 plan range engine and lines
- networth/sim/__init__.py fills simulate, worst_falls, plan_range, rupees, plan_range_lines (en/hi/hinglish) and plan_range_message per docs/phases/phase-6-method.md; tests/test_sim.py covers seed, all-safety, closed form, fall math, invested, horizons, rupee format, guard and the bot function.

## 2026-10-25 — Plan range on the web
- Added /plan-range (demo, own plan only, editable split/amount/years/fall), a plan range section on /u/{token}, networth/web/plan_view.py with an inline SVG range bar, scoped CSS, tests/test_sim_web.py and screenshots in docs/phases/phase-6-shots/.

## 2026-10-25 — Phase 6 report
- docs/phases/phase-6-report.md: method hash 102d69b, sources with URLs and windows, Balanced sample in 0.099 s, guard-checked lines in en/hi/hinglish, deviations and gaps (no 2008 in the window). Fine print on the range section now names fund costs and the missing 2008 crash; shots retaken.

## 2026-10-25 — Phase 6 method v2
- Method v2 recorded before any v2 run: OECD India CPI (INDCPIALLMINMEI) before 2012-01 and OECD short rate (INDLOCOSTORSTM) before 2011-11, so the window can reach 2007-10 and hold the 2008 crash. Code splices them; range-bar labels resized for 12px+ at 320px.

## 2026-10-25 — Range bar labels
- Range bar viewBox 400 wide, labels 18 units, SVG capped at 480px: smallest label renders 13px at 320px. Row names move to the side away from the invested line; test added. Shots retaken on the v2 table.

## 2026-10-25 — Phase 6 report v2
- Report updated for method v2: sources with the OECD splices and rejected ids, window 2007-10..2026-09 (228 months), v1 vs v2 table, new sample and guard-checked lines, label size check, gate counts.

## 2026-10-25 — Verify Keiki turn signatures
- networth/keiki/verify.py trusts a pushed turn only on a valid Ed25519 signature (Keiki's JWKS, refetched at most once a minute on an unknown kid) or, when KEIKI_SIGNING_SECRET is set, a valid HMAC; stale (over 5 minutes), unsigned and unknown-kid requests get a reason. Adds the cryptography dependency (Phase 3C unit 1).

## 2026-10-25 — Keiki wire, clients and email outbox
- networth/keiki/wire.py parses pushed turns into frozen KeikiTurn/Other and strips quoted mail; client.py answers a turn (messages, complete) and sends notices; render.py turns buttons into plain email lines; mail.py queues proactive email in a new outbox table and flushes it on the contact's next turn. Store gains contacts and outbox; Settings reads KEIKI_API_KEY, KEIKI_AGENT_ID, KEIKI_SIGNING_SECRET, KEIKI_EMAIL; Services gains mail and keiki_email (Phase 3C unit 1).

## 2026-10-25 — Answer Keiki turns
- POST /keiki/turn verifies the signature and agent id (401 otherwise, 503 when Keiki is not configured), claims the turn id (a replay answers 200 and runs nothing) and runs the turn in the background. networth/keiki/turn.py flushes queued mail, finds the contact's profile or creates an email-native one (user id is a hash, so logs never carry the address), runs the short email setup (networth/keiki/onboard.py) or the same command and chat path as Telegram through KeikiTurnBot, then completes the turn. commands.on_profile_text is the shared text path; profiles gain deliver_to (Phase 3C unit 2).

## 2026-10-25 — Link email to Telegram and route proactive mail
- /link gives a single-use 6-digit code (link_codes table, expires after link_code_minutes, a new code retires the user's older one); a Keiki turn carrying it binds that contact to the Telegram user. /sendto email|telegram sets deliver_to, checked against a bound contact or a Telegram chat. outbox.send queues proactive briefs, alerts and watches for Keiki when deliver_to is email; the per-user brief claim keeps it to one brief a day across channels. Config gains watch_max_active, watch_max_per_month, link_code_minutes, memory_days; commands take their argument text (Phase 3C unit 3).

## 2026-10-25 — Watch this for me
- networth/watch.py parses a watch into watcher event types (TOPICS table) or a named entity, and refuses price targets and trade triggers; every reply passes the guard's word rules. networth/bot/watches.py sets, lists and stops watches (/watch, /watches with Stop buttons, /unwatch, the new chat intent WATCH) and, after each watcher cycle, tells a user once when a confirmed story first seen after the watch matches it, with its source and the engine's history line and Why link when there is one. Store gains watches and watch_hits; caps are 5 active and 4 messages a month per user (Phase 3C unit 4).

## 2026-10-25 — Memory callbacks in the brief
- networth/memory.py reads glossary terms from knowledge/glossary.md; a short explain-this question with no link stores the terms it asks about (asked_terms table). The investing-day brief adds one line, "Earlier you asked what OFS means. It comes up in this month's news: ...", when a confirmed story of the last 30 days uses an unused term asked in the last memory_days; the line joins the template and the guard source, and the term is marked used once the brief is saved (Phase 3C unit 5).

## 2026-10-25 — Keiki turn traces
- Every Keiki turn appends one line to data/keiki_turns.jsonl: turn and trace ids, user id, channel, kind (chat, command, onboarding, link, notice), chat intent, guard verdict, cost (llm_calls.jsonl records written during the turn) and outcome; never text, address or token. chat.respond_traced and answer.deliver_traced return the intent and which words went out ("fixed" when no model wrote them); respond and deliver delegate (Phase 3C unit 6).

## 2026-10-25 — Answer a first email before setup
- networth/keiki/turn.py: a stranger's first email that asks something gets its answer, then the short setup; a greeting gets the setup only. A /link code is only read from a short message, so a six-digit number inside a question never redeems one.

## 2026-10-25 — Deploy doc: Keiki
- docs/deploy.md gains the Keiki section: resource ids, how to recreate them in a safe order, the KEIKI_* env var names, how turns are trusted, and how to rotate the HMAC secret and the API key.

## 2026-10-25 — Phase 5 plan and walk-forward harness
- docs/phases/phase-5-plan.md fixes every eval choice before any result; evals/walkforward.py rebuilds base rates at a cutoff from the engine's public build steps; evals/vault.py scores the vault once; evals/news/LABELLING.md sets the news label rules; tests/test_evals.py covers the scoring rules.

## 2026-10-25 — Phase 5 eval runners
- evals/__main__.py (make evals), news.py, words.py with words_set.py (86 adversarial messages), trace.py, report.py and spend.py: the paid evals cache raw outputs under evals/results and rescore offline; the words set and rubric were committed before the live run. Restored after a rebase conflict dropped it.

## 2026-10-25 — Phase 5 news labels
- evals/news/labels.jsonl: 63 real stories (29 events of a type, 34 rumours, near misses, old news, opinion and previews), India, US and global, written by three curators and checked URL by URL (evals/news/label_check.jsonl), committed before the judge runs.

## 2026-10-25 — Phase 5 results, findings and report
- evals/results/: cached news, words (rerun after the fixture crash), trace and the one vault run; evals/words.py test user goal fixed to `growth`; evals/report.py adds the by-cutoff table.
- docs/phases/phase-5-findings.md: 5 product changes with failing examples and file:line, none applied. docs/phases/phase-5-report.md: method, results, gaps, deviations, plan hash and spend ($1.22 of $15).

## 2026-10-25 — Keep the measured spend on a clean clone
- evals/__main__.py: with no data/llm_calls.jsonl, `make evals` keeps the spend from the cached summary instead of writing "not measured" over it.

## 2026-10-25 — Cite the rebased plan hash
- docs/phases/phase-5-report.md: the plan commit was rewritten by the pre-push rebase; the report now cites both hashes and the unchanged file blob.

## 2026-10-25 — Memory line quotes a title that holds the term
- networth/memory.py: the brief's memory line quotes the shortest confirmed story or article title that contains the asked term (at most 140 characters), not the story's own title, so the reader sees the term in the headline.


## 2026-10-25 — Plan range table follows DATA_DIR
- networth/sim/config.py: sim_dir() reads the app settings' data dir (DATA_DIR env or .env, else data/), so the VM reads /data/sim, not /app/data/sim. scripts/push_data.sh pushes sim/returns.csv and sim/sources.json; docs/deploy.md documents it. Test in tests/test_sim_data.py.

## 2026-10-25 — News judge: a paused action is not the event
- networth/llm.py CLASSIFY_INSTRUCTIONS lists a pause, delay, suspension or rollback of the action as not the event (phase 5 finding 4); test in tests/test_config_and_llm.py.

## 2026-10-25 — Phase 3D: findings 1 to 3, Jev on, /range
- networth/chat/answer.py: translations and rewrites are told to write app instructions as statements (finding 1); a translation whose template already fails the guard skips the model (finding 2); Answer gains lead (a fixed first line per language) and written. networth/chat/today.py: plan replies open with the fixed line in English, Hindi and Hinglish, plus the history line for an event type confirmed this month (finding 3); plan_range answer. networth/chat/__init__.py: plan_range intent. networth/bot/commands.py: /range and the My range tap. networth/brief: My range button. networth/sim: plan_range_message takes a language. config.toml: use_jev_for_intent = true.

## 2026-10-25 — Same-day /brief follows profile edits
- networth/bot/briefs.py: the stored brief row keeps a key of the profile and plan fields it was written from (briefs.inputs, networth/app/store.py); a same-day /brief resends the stored text only while the key matches. The once-a-day proactive claim is unchanged. Test in tests/test_chat.py.

## 2026-10-25 — Phase 3D eval rerun and report
- evals/results: live words and news rerun after findings 1 to 4; evals/intent_results_heldout_3d.json held-out intent rerun with the new criteria. docs/phases/phase-5-report.md before-and-after section and spend $2.42; phase-5-findings.md status per finding; phase-3b-report.md and phase-3b-decisions.tsv record Jev back on; docs/phases/phase-3d-report.md.

## 2026-10-25 — Phase 3C: clean turn log, trace id, welcome kind, Slack route, report
- The turn log kept Keiki's whole channel object (sender address and email text). It now keeps only the channel type; the fixture sends the object as Keiki does and the log test checks no address or text.
- trace_id falls back to the turn id, which is Keiki's trace id. A first message answered then set up is logged as kind `welcome`.
- Slack turns use the same /keiki/turn pipeline; a Slack author is one contact (`slack:<team>:<user>`) and is never mailed.
- docs/deploy.md gains the Slack setup (OWNER NEEDED app install); docs/phases/phase-3c-report.md written.

## 2026-10-25 — Phase 3C: read the channel type from the live key, fix the log scrub
- The live Keiki channel object names its type `channel`, not `type`; the parser reads `channel` first and the fixtures mirror the live shape.
- The report's one-off log scrub now parses repr-string channels down to the type word, with `unknown` for anything unparseable.

## 2026-10-25 — Phase 3C: one user per email sender, commands in a first email
- Live, each email thread had its own Keiki conversationId, so one sender became three users. The contact is now the channel's userId (lowercased); Slack stays team plus user. Fixtures give each email its own thread.
- A first message that is a slash command gets the setup, not a chat answer. The report's turn table is filled with the three live turns.

## 2026-10-25 — Phase 3E foundation: messages as data, Telegram HTML
- networth/bot/message.py: Message (title, body, detail, footer, preview), Link, the one plain() render, FOOTER per language with say(), and a JSON round trip for stored briefs (a legacy plain-text row reads back as one body block).
- networth/bot/telegram.py: html() is the only renderer and the only place text is escaped; sendMessage uses parse_mode HTML, link previews off unless the message names its link, and a "can't parse entities" 400 is resent once as plain text with a warning that never carries the text.
- Reply holds a Message (a str still works); outbox, KeikiTurnBot and the test fakes pass the Message on; briefs are stored as JSON and resent from storage; /u shows the plain render. Tests in tests/test_message.py.

## 2026-10-25 — Phase 3E: the brief, written by code in three languages
- networth/brief: the brief is a Message built by code in English, Hindi and Hinglish (BRIEF_TASK and its model call are gone; the plain render is still guard-checked and logged as "template"). A greeting by the user's local hour, the month's news (stress events name the feeling), the user's plan range from sim.plan_range in an event month (fall limit only for dollar plans or no table), the plan by name only, the history rows inside an expandable detail, one footer. Buttons are friendlier and localised; callback data unchanged.
- networth/brief/lines.py: history lines as plain counts with the normal rate, "within normal ups and downs" inside names.NEAR_NORMAL (0.10), and a too-few-cases line under 8 episodes; no lean words or colour marks. Hindi and Hinglish event, asset and benchmark names.
- networth/memory.py: the callback line in three languages. evals/trace.py reads the code-written brief. tests/conftest.py keeps data/sim out of tests. Tests in tests/test_brief.py.

## 2026-10-25 — Phase 3E: pages drop the lean framing, /track-record shows our own test
- networth/web: why, scoreboard, scoreboard groups, landing, not found and what-if pages show plain counts with the normal rate and "within normal ups and downs" when close; no "leans", lean marks, lean colour classes or "Usually"/"More often than not". views._changes keys on a count band (weak, near, outside) built on names.NEAR_NORMAL. Unused lean CSS and tokens removed.
- networth/web/names.py: lean(), LEAN_GAP, LeanKind, Lean, LEANS, ODDS_WORDS and odds_words deleted; the eval's own lean classification moved to evals/walkforward.py (lean_kind), unchanged so stored results still read.
- /track-record gains "When we tested ourselves": the walk-forward and vault results from evals/results/summary.json in plain words; left out when the file is missing or unreadable. The Dockerfile copies summary.json. base.html gains og:title, og:description, og:site_name and og:type for link-preview cards.

## 2026-10-25 — Phase 3E: every message in three languages, one footer, setup asks the language first
- Every template in networth/bot (commands, watches, alerts, onboarding), networth/chat (today, why, tip, explain, plan question, range, scope), networth/watch.py and networth/keiki (email setup, link reply) has English, Hindi and Hinglish versions, picked by the user's language. No "!", no hype words, statements instead of imperatives in Hindi and Hinglish.
- "Research, not advice" moved out of every body string (help, done, range label, alerts) into Message.footer: on the brief, alerts, watch hits, every chat answer, /help, /plan and setup done; never on a question, retry, ack or error. Titles only on the brief, alerts, watch hits, /plan and setup done.
- Finding 3: a plan question gets the fixed "I can't tell you whether a plan is right for you" line, the month's history line when the named event is confirmed, and a link to the user's page; no split, no "Type /plan". Finding 1 tail: every fallback is written in all three languages, so the translation path in chat/answer.py is gone.
- Onboarding (Telegram and email) asks the language first with a bilingual greeting; questions, buttons, retries, the summary, fix labels, toasts and the done message follow it. Taps keep their values; typed English and local labels both parse. New profiles start at Step.LANG. Alerts and watch hits are Messages with a title, a link and a footer.
- tests/test_voice.py walks every message table and web template (no "!", hype, lean words or colour marks; guard word rules pass; the footer phrase only in FOOTER) and renders one sample of every message type in each language (footer once at the end where required, none on acks; HTML holds no number the plain render lacks). Existing tests updated for the new copy and language-first setup.

## 2026-10-25 — Phase 3E: Hinglish asset names read naturally mid-sentence
- networth/brief/lines.py: Hinglish names that are common nouns (sarkari banks, rozmarra ka saamaan, rupee/dollar mein gold, rupee mein dollar) start lower case, since they sit mid-sentence; a line that opens with one still gets its first letter capitalised.

## 2026-10-25 — shadcn-look web charts (phase 3E addition)
- New networth/web/static/charts.css holds shadcn's published chart tokens (light and dark) and one series-to-token map. The plan-range bar and the what-if strip now draw rounded bars, thin gridlines, 12px muted labels, an HTML legend and CSS-only tooltips on focusable, labelled marks.
- Chart geometry is now percent across and pixels down, so text, corners and dots keep their size from 320px to 1440px. New `_chart.html` macros, a `/static/charts.css` route and tests/test_charts.py. Before and after shots are in docs/phases/phase-3e-shots/.

## 2026-10-25 — fix: brief news line reads as one sentence, why links escape the asset
- An event type mid-sentence is lower-case ("bank stress", not "Bank stress"); RBI and US keep their capitals.
- Stress months say "shocks like this have happened before" once; the plan line right after it carries "you have a plan", so the brief no longer says it twice.
- Every /why/ link in a message escapes the asset ("%5ENSEBANK") through one names.why_path helper.

## 2026-10-25 — docs: phase 3E words eval rerun
- `uv run python -m evals --live words` after 3E: 85 of 86 pass (was 78), no advice or score 86 (was 81), right language 85 (was 83), $0.35. summary.json, words.json, words_raw.json and the phase 5 report's words section regenerate from it.

## 2026-10-25 — docs: phase 3E report, brief and before/after shots
- Added docs/phases/phase-3e-report.md (message types, voice rules, samples in three languages, words eval, deviations, gaps, OWNER NEEDED deploy), the phase brief, and the message before/after PNGs.

## 2026-10-25 — fix: phase 3E rebased onto 3C fixes and phase 7
- Rebased the ten 3E commits onto ba24bcb. Merge fixes: 3C's footer-link and link-code tests now expect 3E's footer and per-language LINKED; phase 7's holdings row key `lean` renamed `direction` so the 3E voice test's lean grep passes (CSS classes unchanged).

## 2026-10-25 — docs: rebase section in the phase 3E report
- Added a Rebase section to docs/phases/phase-3e-report.md: each conflict and its resolution, the post-merge test fixes, and the branch cleanup (worktree-agent-* deleted; phase-3e-web/charts kept because -d refuses rebased branches).

## 2026-10-25 — Phase 3F hardening
- Rate-limited /link code misses per contact, 404 for stopped users' pages, uvicorn access log off, data dir 0700 on boot, and recorded email sender authentication as a known gap (phase 3C report, Hardening).

## 2026-10-25 — docs: phase 7B brief
- Added docs/phases/phase-7b-holdings-telegram.md, the builder brief for holdings on Telegram.

## 2026-10-25 — fix: rewrite a stored brief written by older code
- networth/bot/briefs.py folds FORMAT_KEY, a hash of the networth/brief sources and message.py, into each brief's inputs key, so a deploy that changes brief wording rewrites that day's stored brief on the next /brief instead of resending old copy. The day's claim is unchanged. Test: tests/test_bot_briefs_format.py.

## 2026-10-25 — feat: holdings on Telegram (phase 7B)
- New networth/bot/holdings.py: photo or image document to a three-language confirm prompt (Looks right, Fix a line, Cancel), typed fixes, the report in the 3E message shape with a holdings page button, /holdings, /link_broker, and holdings questions in chat (new Intent.HOLDINGS) through holdings_answer.
- /stop deletes the user at SnapTrade (forget_snaptrade) and rotates the web link token before the stopped save. Group and channel chats get one line and store nothing.
- Services gains prices (YahooPrices) and an injectable snaptrade client. Tests: tests/test_bot_holdings.py, tests/test_bot_holdings_edges.py.

## 2026-10-25 — docs: phase 7B report
- Added docs/phases/phase-7b-report.md: flows, samples in three languages, the BotFather command list, tests, deviations, known gaps and OWNER NEEDED items (push access, deploy, BotFather, Bank BeES bucket, SnapTrade keys).

## 2026-10-25 — docs: drop the fixed push-access item from the 7B report
- The 403 on push was fixed on the remote side, so the OWNER NEEDED line for it is removed.

## 2026-10-25 — feat: phase 8 web dashboard and chat
- Added networth/web/api.py (JSON API for the site: dashboard and chat for /u tokens and the demo, guard, rate limits, CORS allowlist, length cap, text-free turn log), registered from routes.py with one import.
- Added site/ (Next.js 16, shadcn/ui, Tailwind): /demo and /u/[token], cards per answer type, nonce CSP, light and dark, Playwright test against a mocked API, and a built-output check for verdict words, own figures and secrets.
- Added the contract, design doc, screenshots, and tests/test_web_api*.py (32 new tests).

## 2026-10-25 — fix: phase 8 chat carries the phase 7B holdings intent
- After rebasing onto 7B, the contract test caught the new holdings intent. The API now answers it with the asker's holdings card (a text card when none), and the contract and site types list it.

## 2026-10-25 — fix: phase 8 site polish after the taste gate and screenshots
- Section dividers became spacing; ledger row rules kept as the design idea. The pencil filter now uses a fixed region so the vertical "what you put in" line draws. Holdings mix bars got fixed-size labels and a bucket legend. Primitives name their transition properties. Screenshots refreshed.

## 2026-10-25 — docs: phase 8 report
- Added docs/phases/phase-8-report.md: contract, design direction, what each inspiration gave, the owner steps for the Vercel preview and the Maritime deploy, the production deploy command, known gaps and deviations.

## 2026-10-25 — fix: phase 8 chat follows the newest turn
- The chat panel now scrolls the newest question into view when it is asked and again when its answer lands, and a status region reads the answer's plain text to screen readers instead of the whole card. Playwright covers it. Added site/vercel.json (pins Next.js) and site/.vercelignore (keeps .env* and build output out of uploads).

## 2026-10-25 — docs: phase 8 report records the Vercel project and previews
- Noted that the project's first deploy (dcfke2r2b) went to production without --prod and shows the error page because NETWORTH_API_URL is Preview only; recorded the live preview URL, preview protection and the production steps.

## 2026-10-25 — fix: /u links no longer retire each other
- networth-7b: page links sign the stored link token instead of minting one per /plan, brief or plan answer, which 404d every earlier link live; rotation only on /stop. Regression test in tests/test_links.py, note in docs/phases/phase-7b-report.md.

## 2026-10-25 — docs: phase 9 brief and conversation design
- Added the phase 9 brief and docs/phases/phase-9-design.md: the per-user turn window (8 turns, 24 hours), the Talk routing table under Intent.OTHER (the web contract pins Intent), and the site link and menu button plan.

## 2026-10-25 — feat: phase 9 slice 1, the bot holds a conversation
- networth/chat/talk.py and a turns table: a per-user window of 8 turns over 24 hours, deleted on /stop. Follow-ups resolve against the last answer, open money questions get guarded writer answers (a fixed IPO explainer underneath), small talk and off-topic get fixed kind lines, "should I" gets the decline then the facts, in three languages. respond_traced keeps its signature, so Telegram, Keiki and web gain it unchanged. 20 conversational eval threads added to the words eval.

## 2026-10-25 — feat: phase 9 slice 2, one tap to the dashboard
- NETWORTH_SITE_URL points every page link at the Vercel site (unset keeps the server's /u page); Services.page_url signs the stored token. /dashboard and "mera dashboard" send one button; a per-chat web_app menu button is set when setup finishes and on /dashboard, reset on /stop. setMyCommands on start, /help names /dashboard.

## 2026-10-25 — fix: the web demo answers each message on its own
- Coordinator review of slice 1: every demo visitor is web:demo, so a shared window handed one visitor's words to the next. talk.window and talk.remember now skip SHARED_USERS ({"web:demo"}); test_two_demo_visitors_never_see_each_other.

## 2026-10-25 — Phase 9 slice 3: /erase
- /erase asks with a confirm button, forgets SnapTrade first (aborts on failure), deletes every user_id table plus link_misses, resets the menu, replies in en/hi/hinglish. Added tests/test_erase.py (25 tests).

## 2026-10-25 — should-I answers stop listing steps to decide
- talk.SHOULD_I_TASK: should-I explains what the thing is and its risks only; lead reworded in 3 languages. Live words eval showed 5 should-I replies graded as advice. Test added.

## 2026-10-25 — Phase 9 report
- docs/phases/phase-9-report.md: data shape, caps, samples, command list, /erase, before/after eval, gaps, pending menu check, owner steps.

## 2026-10-25 — a plain ask shows the saved plan
- today.plan: "What is my plan?" (en/hi/hinglish, SHOW_PLAN rule) reads back the saved plan; judging questions keep NOT_A_JUDGE. Finding 3 test now asks a judging question. Tests in tests/test_chat.py.

## 2026-10-25 — /link_broker out of help and the command list
- Owner dropped SnapTrade: removed /link_broker from HELP_COMMANDS (en/hi/hinglish) and COMMAND_LIST; the typed command and snaptrade calls stay. Tests updated.

## 2026-10-25 — report command list without link_broker
- docs/phases/phase-9-report.md BotFather list matches COMMAND_LIST.

## 2026-10-25 — live plan route and erase wording
- chat.build: a plain "What is my plan?" skips the last-answer context, which broke the SHOW_PLAN match after any live exchange (live 13:37 UTC). Test through respond_traced with no fake classifier.
- ERASE_ASK drops "any broker link" in 3 languages (SnapTrade dropped).
- Live menu check: owner chat has web_app "My page" set since /dashboard 12:58 UTC; no code fix.

## 2026-10-25 — report: live menu check result
- Replaced the Pending section with the live getChatMenuButton result.

## 2026-10-25 — web chat 500: torn call log line
- Live /api/demo/chat 500: line 76 of /data/llm_calls.jsonl is 403 NUL bytes (VM stopped mid-append during the Maritime outage); run_turn -> cost_between -> net.read_records raised JSONDecodeError on every web turn. read_records now strips NULs and skips unparseable lines with a warning. Tests: demo chat 200 with a torn log, read_records keeps whole records.

## 2026-10-25 — Phase 10 slice 1: the chat-first web app
- site/: centred chat home for /demo and /u/[token], sidebar with past chats kept in the browser, @ mentions and / commands, Vercel-black theme with Geist and a light theme, one card per server card type, designed thinking, error, unreachable, missing, rate-limited and over-length states.
- site/: rough.js sketches with hidden tables, and the dashboard as a slide-over or pinned canvas.
- site/: commands fall back to the chat question they stand for while the API lacks the command route; a 404 no longer says "check your connection"; past chats get readable titles; the news timeline runs oldest to newest.
- networth/web/api.py: command routes, mentions, track record; today's stories now carry the day they were first seen.
- Removed the unused shadcn and base-ui dependencies, components.json and lib/utils.ts.

## 2026-10-25 — Phase 10 slice 2: the charts and the canvas, checked in a browser
- site/: chart labels get a halo in the surface colour so they read over hatching; range column names stay inside the chart at 320px; range case figures sit right-aligned; the holdings Return keeps its figure in mono and the server's words in text; history rows stack the same way on phones and show the accent tick as the key for "normal".
- site/: on the light theme chart accents use a deeper amber stroke token (--accent-stroke), since the highlighter yellow vanished on paper.
- site/: component CSS now sits in @layer components, so utilities like md:hidden win (the phone menu button was showing on desktop).
- site/e2e: charts.spec.ts (tooltip on focus and hover, named marks, reduced motion, seeded strokes, fixed height) and canvas.spec.ts (pin docks and persists, phone sheet, sidebar links land on their section). Screenshots refreshed.

## 2026-10-25 — Phase 10 slice 3: the landing page at /
- site/app/page.tsx: the GTM page replaces the redirect. Hero with both CTAs and a working question box (a plain GET form to /demo?q=, so it works before script loads); three steps, each beside a live piece of the sample profile; the three channels; the line we never cross; the server's own negative track record; the live range sketch; a six-question FAQ; footer "Research, not advice."
- site/components/landing/: ask.tsx (the question box) and live.tsx (streamed, cached-per-request demo pieces that say "waking up" when the server is asleep).
- site/: /demo asks a ?q= question on arrival and drops it from the URL; hidden chart tables sit in an sr-only wrapper (a table ignores sr-only's width, which widened the body at 320px); Geist Mono loads without a preload.
- site/e2e: landing.spec.ts; overflow checks read body.scrollWidth too; landing screenshots at 320 and 1440, dark and light.

## 2026-10-25 — fix: an unknown / command says it doesn't exist
- site/: /link_broker left the bot's command list (P9 7f41489), so it leaves the web's bot-only set; a / command that is neither a web command nor a bot one now says "There's no /name" instead of pointing at the bot, on screen and in the announcement.

## 2026-10-25 — Phase 10: critique, audit and report
- site/: the light-theme chart accent is now oklch(62% 0.15 75), 3.59:1 on the page and 3.37:1 on cards (WCAG 1.4.11); Safari's details marker is hidden on the FAQ.
- docs/phases/phase-10-report.md: design direction, libraries, the API and mention mapping, bundle and LCP numbers, what the critique and audit changed, known gaps and deviations.

## 2026-10-25 — holdings: Indian ETF tickers placed by bucket
- networth/holdings/model.py: TICKER_RULES read an INR ETF ticker (identifier or ticker-only name): LIQUID/GILT/Bharat Bond safety, sector (BANKBEES, PSUBNKBEES, ITBEES...) growth, broad index core. "nifty it" added to sector words. Tests from the Groww fixture Bank BeES row.

## 2026-10-25 — holdings: small-cap and US tech ETF tickers are growth
- TICKER_RULES growth now matches SML (HDFCSML250), MON100 and FANG (MAFANG). Tests added.

## 2026-10-25 — Phase 10: the landing page, redone Maritime-style
- site/app/page.tsx, app/landing.css, components/landing/{hero-sketch,step-icons,mocks,playback,in-view}.tsx, lib/pencil.ts: `/` rebuilt from scratch as one centred column with the hackathon pill, a self-drawing pencil hero, three self-drawing steps and five product mocks (the LIC IPO chat, the monthly brief, the range chart, an email reply and the dashboard sheet), plus the letter, the line we never cross and the FAQ; the old ask box (components/landing/ask.tsx) is removed.
- site/e2e/landing.spec.ts: tests for the new page (centring, mock playback, reduced motion, the server's brief, the letter); docs/phases/phase-10-report.md: before/after critique, gates and LCP.

## 2026-10-25 — hermetic keiki what-happened tests
- tests/test_keiki_turn.py: the planted-number test runs on a fixed clock with the news check 30 min old; the turn-log test plants its check 30 min back. Both raced the whole-second now_iso() against a check exactly 1h old.

## 2026-10-25 — Phase 11: Google sign-in on the web app
- site/: Auth.js v5 with Google only (auth.ts, app/api/auth); /dashboard (sign in, the /weblink step, the user's own workspace), /privacy, an account button and menu in the landing header (Dashboard, Sign out, Forget me), and a footer Privacy link; server code signs a 60 s HMAC token for the API (lib/session.ts); CSP form-action allows accounts.google.com.
- networth/: /weblink in the bot (the /link code store); web_logins table keyed by Google subject (erased by /erase); /api/web/{me,link,forget,dashboard,chat,command} behind networth/web/session.py token checks; NETWORTH_WEB_SECRET setting.
- tests/test_web_api_auth.py, site/e2e/account*.spec.ts: 401s, code refusals, isolation, memory, forget and erase; docs/phases/phase-11-report.md and phase-11-shots/; contract doc gains the web routes and codes.

## 2026-10-25 — Phase 12: holdings reply leads with the answer
- networth: holdings reply now leads with worth, invested and gain, each share and a takeaway; count and merge across screenshots; plain-word fix flow; plan comparison in rupees on confirm; sell questions get plan gap and history; plain bucket words in LINES; gold and silver ETFs and gold funds are safe money (owner decision); owner Groww fixture and tests; make check exit 0.

## 2026-10-25 — Phase 13C: rate() signature and the ratings/sectors contract
- networth/ratings/{__init__,model}.py: Rating, Driver, Source, Track, View and the rate() signature 13A codes against.
- docs/phases/phase-10-contract.md: Phase 13C routes and the RatingCard, SectorsCard, RatingsBacktest types in their own block.

## 2026-10-25 — Phase 13A card contract
- Added price, price_history, position, compare, market_today cards and five intents to the phase-10 contract; commit the 13A brief.

## 2026-10-25 — Phase 13C: the rating engine and its backtest
- networth/ratings/{sources,score,kinds,track}.py and rate(): stocks, funds, ETFs and NSE IPOs from free sources (Yahoo, mfapi.in, NSE, the watcher), every driver sourced, missing data named.
- networth/ratings/backtest.json: the measured hit rate of the price part since 2015, Indian against the Nifty, US against the S&P 500. ipo_rhp.json holds SFCTECH's RHP numbers with pages.
- Contract: currency on RatingCard and SectorsCard, the backtest as groups.

## 2026-10-25 — plan screens in plain words
- networth/bot/onboarding.py, networth/sim: plan readback, /plan plan_line, the starter-plan picker, the own-split ask and the /range plan line say safe money, broad index funds, single shares or themes in en, hi and hinglish; the picker drops the "common mixes, shown for education" sentence; a grep test guards every plan screen.

## 2026-10-25 — no footer or disclaimer in holdings replies
- networth/holdings/lines.py, networth/bot/holdings.py, holdings_words: dropped "Research, not advice." footer and every not-advice/your-choice sentence in en, hi, hinglish (owner order); tests updated; a grep test fails if any holdings reply carries one.

## 2026-10-25 — site: no disclaimers or answer footer anywhere (owner order)
- Removed "Research, not advice." and every "not advice / your call / your choice / won't say yes or no" line (en, hi, Hinglish) from site copy: landing footer, mocks, letter, FAQ item, metadata, page frame; the site no longer renders any server `footer` (answer, error, dashboard). withoutFooter no longer empties labels when the footer is "".
- scripts/disclaimers.mjs: one phrase list; check-build scans source and .next with it; e2e/no-disclaimer.spec.ts scans every reply fixture and each page. Fixtures scrubbed to a footer-less server.

## 2026-10-25 — Phase 13B spike: A2UI SIP projection, money by currency
- @a2ui/react and @a2ui/web_core 0.14.0 (exact), zod 3.25.76: a Networth A2UI v0.9 catalog (Column, Text, Slider, SipProjection) rendered client-side from server-shaped messages; sliders write the surface data model and the projection recomputes in the browser. /lab/sip shows it; e2e/a2ui.spec.ts proves no request on slider moves.
- lib/money.ts: one formatter from the card's currency (en-IN lakh/crore for INR, en-US for USD and $1.2M); --up/--down tokens; range card says "today's money".

## 2026-10-25 — no merge line when nothing new was added
- networth/bot/holdings.py: a screenshot that adds no new rows no longer says "This screenshot added 0"; test added.

## 2026-10-25 — Phase 13A: no footer, no disclaimers
- Owner order: FOOTER blanked, every "Research, not advice", "your call", "I will not say yes or no" and "your choice" line removed from chat, bot, keiki, web templates and holdings copy; tests now assert none; DISCLAIMER regex strips any a model adds.

## 2026-10-25 — Phase 13A: Hindi/Hinglish buy-sell routing
- No-model phrase rules send "kya bechna chahiye", बेच, खरीद, kharid to the holdings plan-gap path; tests.

## 2026-10-25 — Phase 13A: shared money() formatter
- networth/money.py: money(amount, currency, lang) in lakh/crore for INR, K/M/B for USD, code + grouping otherwise; tests.

## 2026-10-25 — Phase 13A: last "your choice" lines
- Removed "your plan is your choice" from the plan range label and the plan decline in all languages; DISCLAIMER now also catches "your choice"/"aapki pasand"/"आपकी पसंद".

## 2026-10-25 — Phase 13A: amounts through money()
- Onboarding summary, brief title and range line, user page, dashboard, plan range lines and card now use networth.money (lakh/crore, $K/M in the user currency). onboarding.format_money removed; sim.rupees kept only for holdings. Guard reads लाख/करोड़, M and B, and accepts a compact figure within 0.5% of a source amount.

## 2026-10-25 — Phase 13A: Get my brief now
- Setup done (Telegram), /plan and the dashboard reply carry a "Get my brief now" button (br:now); email setup says "Reply /brief now". briefs.brief_now builds the brief with the /brief builder but never claims or saves the day, so the scheduled brief still goes out. Web /plan matches Telegram. tests/test_brief_now.py.

## 2026-10-25 — Phase 13A: market data module
- networth/market.py: quotes (last close, day change, 52-week range), multi-year history, returns, worst falls, index and name lookup (NSE first for rupee readers) from Yahoo Finance via yfinance, no key. tests/test_market.py with a fake source.

## 2026-10-25 — market answers: price, history, holding, compare, Networth's read
- networth/chat/markets.py routes named-stock questions before the classifier and answers from Yahoo Finance with the source and date, plus typed cards; the web API sends the reply's own card; tests in tests/test_markets.py.

## 2026-10-25 — cap the market name search at 2 seconds
- networth/chat/markets.py: found_in_time runs the Yahoo name lookup with a 2s deadline; past it the reply says Yahoo Finance did not answer in time and gives no number. Tests in tests/test_markets.py.

## 2026-10-25 — Phase 13C: /sectors on Telegram
- networth/bot/sectors_cmd.py: /sectors sends the sector board with its confirmed stories and names sectors with no prices; registered in commands.py and the command menu. tests/test_bot_sectors.py. make check exit 0. Committed locally, not pushed (owner order).

## 2026-10-25 — Phase 13C: the news notifier and /alerts
- networth/notify: after each watcher cycle (run_watcher, no new scheduler) a confirmed story about a holding, its sector or the plan's Nifty 50 sends one message through the outbox: the story and publishers, the last close's move with its source, the move in the holding's currency, and the rating when its view changed. 3 a day per user, quiet 22:00-08:00 IST, claims in data/notify.sqlite.
- networth/bot/alerts_cmd.py: /alerts on|off flips the profile's alerts_on. tests/test_notify.py covers the cap, quiet hours, /alerts off, a failed send and the rating line. make check exit 0. Local commit only.

## 2026-10-25 — Phase 13C: /r pages and the ratings API
- networth/web/ratings_web.py: public /r/<slug> pages (a rating, /r/sectors, /r/sector-<key>) with drivers, sources and the backtest table; GET /api/rating/{query}, /api/sectors and /api/ratings/backtest with the API's origin check. One import line in routes.py. Templates r_rating, r_sectors, r_missing. tests/test_ratings_web.py. make check exit 0. Local commit only.

## 2026-10-25 — Phase 13C: money as 13A writes it
- networth/ratings/model.money mirrors 13A's moneyShort (site/lib/money.ts): ₹2.91 lakh, ₹1.2 crore, $12,400, $1.2M. Ratings and news alerts write amounts only through it. make check exit 0. Local commit only.

## 2026-10-25 — Phase 13C: fund comparison wording
- networth/ratings/score.py: "against the Nifty 50 at +5.4%" instead of "the Nifty 50's" / "peers's". make check exit 0. Local commit only.

## 2026-10-25 — Phase 13C report
- docs/phases/phase-13c-report.md: what was built, the done-when table (3 not met: not deployed by owner order), the five live ratings, the backtest and what it says, sources, decisions, gaps, OWNER NEEDED. Local commit only.

## 2026-10-25 — Phase 13C review round 1
- Valuation compares like with like: P/E, else P/S for a loss-maker, else P/B; peers without that measure are left out and each peer's value is shown.
- Growth comes from Yahoo's annual statements (latest fiscal year against the one before) instead of the quarterly revenueGrowth field, which showed HDFC Bank at +81% against +5.2% in its statements. Report updated with the new live ratings. make check exit 0. Local commit only.

## 2026-10-25 — holdings action plan after "That's everything"
- networth/holdings/action.py (new): plan targets, trims weakest first (rating, then loss, then size), moves, tax booked, monthly split, months to plan. networth/bot/holdings_plan.py (new): overview with Path A and Path B, Rebalance now, Use new money with Show me now, Why these?; fund names per currency and language. Services.ratings feeds rate(). short_money says $1.2M. Tests with the owner fixture and a USD fixture.

## 2026-10-25 — USD holdings fixture and the phase 12 report
- tests/fixtures/holdings/us_holdings_vision.json and test: a US user sees dollars, VOO, SGOV and US safe-money words; "Both are" for two holdings; docs/phases/phase-12-report.md lists the follow-ups and gate exit codes.

## 2026-10-25 — Sell question shows the Networth view per holding
- "What should I sell?" / "kya bechna chahiye" after holdings lists each holding's rate() view, score and top driver with its source, weakest first, then the plan gap in money. Removed the old not-a-pick copy and unused plan_gaps/furthest/Gap.

## 2026-10-25 — Rebased the sell view onto 13A
- Rebased onto 13A local work; kept 13A's Hindi/Hinglish sell phrases in chat routing (they cover mine) and pointed 13A's sell test at the per-holding view.

## 2026-10-25 — Holdings use the shared money() formatter
- Holdings replies, the action plan and the sell view write amounts with networth.money.money(); deleted summary.short_money and its test; added a big-USD test ($234K) across every holdings reply.
||||||| parent of 99e7291 (feat: a Get my brief now button wherever the brief is said to come on your day)

## 2026-10-25 — site: "Get my brief now" (owner request)
- Landing step "On your day, a brief" and the brief feature get a "Get my brief now" link: signed out it opens /demo?q=/brief, signed in /dashboard?q=/brief. A `/brief`-style ?q= now runs that server command on arrival (shell `opening`); /u/[token] and /dashboard pass ?q= through. e2e/brief-now.spec.ts covers all three.

## 2026-10-25 — feat: the 13C rating card with a gated lab page
- site/components/cards/rating.tsx (score dial, view, outlook, drivers with effect and source chips, missing data, track record pill) and source-chip.tsx; /lab/rating renders the HDFC and AAPL fixtures (made by the real rate() on test fakes) only when NETWORTH_LAB=1, set in the Playwright config; e2e/rating.spec.ts.

## 2026-10-25 — feat: the 13C sector board card with a gated lab page
- site/components/cards/sectors.tsx: heat strip tinted from the server move strings, Day/Week/Month toggle with no request, tap a sector for its confirmed stories and source chip, biggest-mover insight pill; /lab/sectors (NETWORTH_LAB=1 only) renders the sectors.json fixture from the real board() on test fakes; e2e/sectors.spec.ts.

## 2026-10-25 — feat: the market strip at the top of the chat
- site/components/market-strip.tsx: server-drawn index tiles (level, change in --up/--down with an arrow, pencil sparkline) plus one source chip, streamed under the shell header with a skeleton while loading and a plain line when the route is missing; never a made-up number. Fetched by getMarket() from the proposed per-scope /api/{demo|u/{token}|web}/market route (shape in site/lib/market.ts, tiles already in the user's order, so US profiles lead with S&P 500, Nasdaq, Dow). Phones keep it on the empty chat only.
- site/lib/contract.ts now copies contract block 1 with the 13A market cards (answer.tsx answers them in words for now); SourceChip shows 13A's preformatted as_of whole. Mock API serves market fixtures; e2e/market-strip.spec.ts; charts and a2ui specs no longer assume the chart is in view or count Next's link prefetches.

## 2026-10-25 — feat: the market strip on real Yahoo closes, with a source on every tile
- Rebased the local 13B commits onto 13A's 4be1140 (networth.market). site/e2e/record_market.py records market-in/us.json from real Yahoo data through networth.market (13A has no strip route or card builder yet). Each tile now carries its own source and opens it; the tile shows its close date, the strip names its sources. MarketStrip is {tiles} with per-tile source.

## 2026-10-25 — feat: the price and position cards
- site/components/cards/price.tsx (last close, day move in --up/--down, a year of closes, 52-week range with a marker, where-in-year insight, source chip) and position.tsx (worth now against what was paid, table, dashed paid line, a what-if slider from −50% to +50% computed in the browser, break-even insight when under water); price-line.tsx is the shared pencil line with hover, tap and arrow-key read-out. lib/money gains price(), signed() and parseAmount(). Recorded answer fixtures from real Yahoo closes; the mock routes price and holding questions to them.
- Fix: an answer, its card and the chart figure now use a minmax(0,1fr) column, so a wide caption can no longer push the card past a phone screen inside the chat scroller; the fit test checks the scroller too.

## 2026-10-25 — feat: the history card with a 1Y/3Y/5Y/10Y range switch
- site/components/cards/price-history.tsx renders price_history: the server's return for the years asked, a range switch that cuts the closes in the browser (a shorter span shows the change between the first and last close on the line, and says so), the worst falls shaded on the line and listed with their recovery, a worst-fall-in-this-stretch insight and the source chip. Tested against the recorded 10-year Nifty 50 answer.
||||||| parent of 04c6d79 (feat: what happened today leads with the home index moves, then up to 4 confirmed stories)
||||||| parent of 960dab7 (feat: what happened today leads with the home index moves, then up to 4 confirmed stories)

## 2026-10-25 — what happened today leads with the index moves
- networth/chat/today.py: the reader's home indices (Nifty 50, Sensex and the rest, or the S&P 500, Nasdaq and Dow for USD) lead, then up to 4 confirmed stories first seen in the window; the could-not-confirm count is gone; a market_today card goes with it. api today_stories shares the same query. Tests in tests/test_markets.py.

## 2026-10-25 — the guard lets Networth's view through, still blocks invented numbers
- networth/guard.py: BANNED split into HYPE (always blocked) and VIEW_WORDS; check/guarded take view=True for stock_view answers, which skips view words and advice phrasing but still checks every number. answer.py: Answer.view and VIEW_TASK. Tests in tests/test_markets.py.
||||||| parent of 1f7cf53 (fix: sector board attaches only real news, never calendar releases)

## 2026-10-25 — sector board drops calendar releases
- networth/sectors: scheduled releases (auctions, data releases, statistical reports) never attach to a move; only the story's own headline counts; bare "RBI" and "deposit" no longer match Bank; a move with no story says "No confirmed news behind this move."

## 2026-10-25 — sector board keeps foreign stories off Indian sectors
- networth/sectors: a story must name India, an Indian company or regulator, or the sector's global driver (crude for Energy; steel, aluminium, copper prices, iron ore or LME for Metal); Ebola, US tariff and US housing stories no longer attach.
