# Phase 3A · Server, Telegram and onboarding (runs in parallel with Phase 2 and Phase 4)

You are the **builder** for Phase 3A of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check.

Two other builders work in the same repo at the same time. **Phase 2** owns `networth/watcher/`, `networth/llm.py` and `networth/config.*`. **Phase 4** owns `networth/web/`. Never edit their files. If you need something from them, use a stub behind a small interface in your own files and note it in your report.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If the Skill tool refuses, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc.
2. `tech.html` sections 03 (Data model), 07 (Request flows), 09 (Maritime and Keiki), 13 (Security), 14 (Risks). `product.html` sections 07 (journey), 08 (messages) and 10 (how people talk to it).
3. `docs/research/research-keiki-maritime.md` for Maritime and Telegram facts. Look up anything else in vendor docs. Never invent an API.
4. `~/.claude/CLAUDE.md` is in force.

## Decisions already made

- Telegram bot `@networth_professor_bot`. `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` and `LINK_SIGNING_SECRET` are in `.env`. Never print them.
- No holdings. Onboarding asks: goal, horizon, monthly amount and currency, investing day, drop comfort, exclusions, language. Then the user picks one of 3 starter plans or their own split.
- **This phase uses no LLM.** Onboarding uses Telegram inline-keyboard buttons plus simple number parsing, so it is fast and deterministic. Free-text chat comes in Phase 3B.
- Hosting is Maritime: one container on `$PORT`, `GET /health`, state in `/data`. Local dev uses long polling, production uses the webhook.
- This network has broken IPv6. Every HTTP client needs an overall deadline.

## Build (you own these paths only)

| Path | What it does |
|---|---|
| `networth/app/main.py` | FastAPI app. `GET /health` returns 200 within 1 second. `POST /telegram/webhook` checks the `X-Telegram-Bot-Api-Secret-Token` header against the secret and rejects anything else. Mounts `networth.web.routes:router` if it imports, and runs fine if it doesn't. |
| `networth/app/store.py` | SQLite in `$DATA_DIR` (default `data/`). Tables for `Profile`, `Plan` and `Message` from tech.html section 03, with `holdings` removed and `invest_day`, `lang` and `alerts_on` added. Idempotent migrations. |
| `networth/bot/telegram.py` | A thin Bot API client (sendMessage with inline keyboards, answerCallbackQuery, setWebhook, getUpdates). Deadlines, and one retry on 429 honouring `retry_after`. |
| `networth/bot/onboarding.py` | A state machine from `start` to `done`. Each step is one message with buttons. Free-typed answers are parsed (for example "1 lakh", "₹50,000", "$500", "25k"). Ends with the plan pick, then a summary read back for "Looks right" or "Fix". Under 60 seconds with taps only. |
| `networth/bot/commands.py` | `/start`, `/plan` (show and change the plan), `/pause`, `/resume`, `/stop` (stops all messages, a user can come back with /start), `/help`. "What happened today?" and tip forwards get a polite "coming soon" in this phase. |
| `networth/bot/poll.py` | `python -m networth.bot.poll` runs the bot locally by long polling. |
| `Dockerfile` + `docs/deploy.md` | Container for Maritime. The deploy doc lists the exact `maritime` commands. Deploying needs the owner's `maritime login`, so raise OWNER NEEDED for that step and continue. |
| `tests/test_onboarding.py`, `tests/test_app.py`, `tests/test_amount_parse.py` | No network. A fake Telegram client. |

## Not in this phase

Briefs, alerts, tip checks, the LLM, Keiki, cron, the news watcher, web pages, broker linking. Any buy or sell wording is forbidden, including in button labels.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. `uv run uvicorn networth.app.main:app --port 8080` starts, and `curl -s localhost:8080/health` returns 200.
3. A webhook POST without the secret header gets 401 or 403. With it, a fake `/start` update returns 200 and stores a Profile in its first state.
4. A test drives onboarding from `/start` to `done` with button taps only and checks every Profile field and the chosen Plan.
5. `/stop` sets the user to stopped, and a later test proves no message can be sent to a stopped user.
6. The amount parser handles at least: `1 lakh`, `1.5L`, `₹50,000`, `50k`, `$500`, `500 dollars`, `10,00,000`. Bad input gets a friendly retry, never a crash.
7. **Live check.** `uv run python -m networth.bot.poll` runs, and the coordinator completes onboarding with @networth_professor_bot in Telegram Web. The summary message is correct.
8. `docker build .` succeeds, and the container answers `/health` on `$PORT`.
9. No message text, button or command contains "buy", "sell", "guaranteed" or "sure shot". A test greps every user-facing string.
10. `docs/phases/phase-3a-report.md` lists what was built, the onboarding flow with every message's exact text, the OWNER NEEDED items, known gaps and deviations.
11. Nothing secret is committed, and `data/` is not committed.

## The gate, branch policy and shared files

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 3A READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
