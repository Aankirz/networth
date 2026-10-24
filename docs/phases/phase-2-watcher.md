# Phase 2 · The news watcher and the model layer

You are the **builder** for Phase 2 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, so only report something as done after you have run it.

You can talk with the owner, Ankit, in this window about anything technical. Keep the scope fence below unless he changes it in writing in this window. If he does, note the change in your hand-off report.

## Read first

0. **Before any other work, invoke the `pstack:poteto-mode` skill and follow it for all building.** If the Skill tool refuses, print an OWNER NEEDED line asking Ankit to type `/pstack:poteto-mode` in this window. Where poteto-mode conflicts with this brief, this brief's scope fence, gate and branch policy win.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc.
2. `tech.html`, sections 03 (Data model), 05 (News watcher and triggers), 05.1 (Who decides what), 13 (Security) and 14 (Risks).
3. `docs/phases/phase-1-report.md` and the Phase 1 engine code. You call the engine. You never re-implement it.
4. `~/.claude/CLAUDE.md` is in force: conventional commits, tests alongside code, an append to `.claude/CHANGELOG.md` after every change, no `Co-Authored-By` or session trailers.

The rule this phase exists to make true: **a story reaches the engine only if it is confirmed, and every rejected story is logged with its reason.**

## Decisions already made (don't reopen)

- **Live models are OpenAI.** `OPENAI_API_KEY` is in `.env`. Bedrock and Keiki's model endpoints are out. Keiki's compatible endpoints take a Keiki agent name, not a model.
- Verified callable on this key: `gpt-5.6-luna`, `gpt-5.6-terra`, `gpt-5.6-sol`. **Look up their pricing and intended use in OpenAI's own docs before mapping roles. Don't guess.** Record the source URL.
- Three roles, set only in config (`networth/config.toml` or similar): `cheap` (grouping news), `judge` (classifying a confirmed event, once per event for all users), `writer` (later phases). Each role maps to a provider and a model id. No model id appears anywhere else in code.
- The improvement loop and all build-time thinking run in Claude Code on Opus 5.5. Not in this phase.
- News search is Exa. `EXA_API_KEY` is in `.env`. One search costs about $0.007.
- This network has **broken IPv6** (connects hang in SYN_SENT). Every HTTP client you write needs an overall deadline and must not hang on IPv6.

## Build

| File | What it does |
|---|---|
| `networth/config.toml` + `networth/config.py` | Roles to provider and model, thresholds (publishers needed, windows, price trigger multiple), Exa query budget. Parsed into a typed object at startup. Fails fast with a clear message if a key in `.env` is missing. |
| `networth/llm.py` | One function per call shape over the OpenAI SDK (Responses API), keyed by role. Structured output parsed and validated at the boundary. Every call logs role, model, input and output tokens and cost to `data/llm_calls.jsonl`. |
| `networth/watcher/pull.py` | Exa news search over the last 48 hours. Queries per event type in `events.csv` types, for both India and the US. Stores raw articles in `data/watcher.sqlite`. Idempotent: the same article never stored twice. |
| `networth/watcher/group.py` | The `cheap` model groups articles into stories. Then plain code decides confirmation: 3 or more original publishers within 24 hours, wire reposts counted once, or 1 primary source (RBI, SEBI, PIB, the Fed, SEC, NSE or BSE filings, OPEC, a company investor page). The primary-source list lives in config as domains. |
| `networth/watcher/classify.py` | For each confirmed story, the `judge` model maps it to one engine `type` and `cause`, or to `none`. Output is validated against the allowed types. Cached per story so it runs once. |
| `networth/watcher/triggers.py` | **News first.** A confirmed, classified story calls the Phase 1 engine for its base rates. **Price first.** An index or sector excess return beyond 2.5 times its 60-day volatility, then look for the confirmed story behind it. Writes `Insight` rows that hold only engine numbers. |
| `networth/watcher/log.py` + `python -m networth.watcher.report` | The decision log. Every story with its publishers, its verdict and the reason (for example "rejected: 1 publisher, no primary source"). The report prints today's confirmed and rejected stories. This is the demo's "honesty moment". |
| `python -m networth.watcher.run --once` | One full cycle: pull, group, confirm, classify, trigger, log. |
| `tests/` | No network. Fixture articles, including a planted single-source viral rumour and a wire story reposted by 5 outlets. LLM calls are faked at the `llm.py` boundary. |

## Not in this phase

Telegram, Keiki agents and webhooks, Maritime deploy, cron, briefs and their wording, chat, onboarding, the web view, guardrails on user messages, the improvement loop, evals beyond the tests below, broker linking, any buy or sell wording anywhere.

## Done when

The coordinator checks every item by running it.

1. `make check` passes from a clean clone after `uv sync`.
2. Starting with a key missing from `.env` exits with a message naming the key, and no traceback.
3. `grep -rn "gpt-" networth/ --include=*.py` finds nothing. Model ids live only in config. The report cites OpenAI's pricing page for each mapped model.
4. `uv run python -m networth.watcher.run --once` runs on real news from the last 48 hours in under 10 minutes and spends under $1 in total (shown from `data/llm_calls.jsonl`).
5. `uv run python -m networth.watcher.report` lists confirmed stories, each with its publishers or primary source, and rejected stories, each with a reason. The Oct 7 2026 RBI repo hike shows as confirmed via rbi.org.in if it is inside the window. If not, the report shows the newest confirmed India story.
6. A test proves the planted single-source rumour is rejected with its reason, and the 5-outlet wire repost counts as 1 publisher.
7. A confirmed `rbi_hike` story produces an `Insight` whose numbers match `odds()` from the Phase 1 sqlite exactly. A test checks this, and the coordinator checks it on the real file.
8. A price-first trigger test: a fixture price jump beyond 2.5 times 60-day volatility fires, one below it does not.
9. Every HTTP call (Exa, OpenAI, source checks) has an overall deadline. A test with a fake socket that never connects finishes within the deadline and is logged as failed.
10. Running `--once` twice leaves the same article and story counts (idempotent).
11. `docs/phases/phase-2-report.md` lists: the role-to-model map with prices and sources, one real cycle's counts (articles, stories, confirmed, rejected by reason), cost per cycle and per day at 43 cycles, known gaps, and every deviation from this brief.
12. Nothing secret is committed, and `data/` is not committed.

## The gate

Run `make check` before every commit. Don't commit red.

## Branch policy

Hackathon mode, decided by the owner. **Commit and push straight to `main`.** No PRs. Remote `origin`. Repo-local git config already sets the author and credentials, so don't change git config. Run `git pull --rebase` before every push. Small conventional commits, pushed after each. Never force-push. Write `PHASE 2 READY FOR REVIEW` as the final line of your hand-off in this window.

## OWNER NEEDED protocol

If you hit a step only a human can do (a credential, a paid action, a sign-up, an account decision), stop that step and print the line below, then continue with other work:

`OWNER NEEDED: <what> — <how to do it, exact steps>`

All keys this phase needs are already in `.env`. Never print a key.
