
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
||||||| parent of 19df1a7 (feat: verify Keiki turn signatures with Ed25519 or HMAC)

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
||||||| parent of 72ac779 (docs: fix the phase 5 eval plan before any result, with the walk-forward and vault runners)

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
||||||| parent of 52cb417 (fix: quote a short headline that holds the asked term in the memory line)

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
||||||| parent of da2ecbf (docs: add the Slack setup and the phase 3C report)

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
||||||| parent of a6f8d85 (feat: add the phase 8 Next.js site with the ledger and chat cards)

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
