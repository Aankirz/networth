# Phase 3B · The product a user talks to (brief, chat, Explain this, deploy)

You are the **builder** for Phase 3B of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including live in Telegram.

Phases 1, 2, 3A and 4 have passed. Their code is now yours to extend: `networth/app/`, `networth/bot/`, `networth/web/`, `networth/watcher/`, `networth/llm.py` and `networth/config.*`. **The repo is public, so never commit a secret, a user's data or `.env`. Phase 1B is still building in `networth/engine/`. Never edit `networth/engine/`.** Call it only through `odds()`, `compare()`, `position_range()` and, once 1B lands, `split()`. Stage only your own paths by name, and never run `git add -A` or a bare `git commit`. Use `git commit -- <paths>`.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc. Note "The line we never cross" and "Explain this".
2. The reports: `docs/phases/phase-1-report.md`, `phase-2-report.md`, `phase-3a-report.md`, `phase-4-report.md`. Their deviations and known gaps are now your starting point.
3. `docs/research/research-keiki-maritime.md` sections 1, 2 and 4, and `docs/deploy.md`. Look up anything else in Maritime's and Keiki's own docs. Never invent an API, endpoint, model id or flag.
4. `docs/research/research-beginner-videos.md`. Its glossary and teaching patterns are the voice for Explain this and jargon decoding.
5. `~/.claude/CLAUDE.md` is in force.

## Decisions already made

- Live models are OpenAI through `networth/llm.py` and the roles in config. The `writer` role writes every user-facing sentence. No model id outside config.
- Telegram first, through the 3A bot. Production uses the webhook on Maritime. The user must `/start` the bot first.
- Keiki is an extra surface, not the backbone. If Keiki blocks (plan, waitlist, missing feature) for more than 30 minutes, record it as a known gap with the exact error, and ship Telegram only.
- One brief for everyone with the same events. Personal parts are only the user's own plan, amount, currency, investing day, exclusions and language. No allocation advice.
- **No scores.** Never rate a stock, IPO or sector on a scale, and never rank them as best or worst. Explain this gives facts and decoded jargon only.

## Build

| What | Details |
|---|---|
| Integration | `networth.app.main` serves the web router (3A already mounts it). The Why links in every message point to the deployed `/why/...` pages. **The deployed `/` returns 500 today**, most likely because `data/base_rates.sqlite` isn't in the container (`data/` is gitignored). Find the real cause, then make the deployed agent build or receive the engine's sqlite in a repeatable way, documented in `docs/deploy.md`. |
| Jev for closed choices | Typed decisions (`Choice`) through TypeSafe's Python SDK, the pattern in `~/Desktop/zoya/zoya/decisions.py` and `evals/harness/jev_vs_model.py` (read them, copy the pattern, not the code). Keys `AI_GATEWAY_API_KEY`, `AI_GATEWAY_BASE_URL` and `JEV_MODEL` are in `.env`. Use it for the chat-intent pick. Measure it against the `cheap` model on a labelled set of at least 30 messages in English, Hindi and Hinglish, and keep Jev only if its accuracy is at least the model's. Below that, or on any Jev error or timeout, the model decides. Record both accuracies and the latency in the report. |
| `networth/brief/` | The investing-day brief composer. Inputs: the month's confirmed `Insight` rows from the watcher, `compare()` scoreboard rows, and the user's Profile and Plan. It builds a structured draft (lines with their engine numbers), then the `writer` role words it in the user's language. Shape follows the PRODUCT.md example: one-line news, 3 or 4 scoreboard lines with counts and normal rates, weak-signal labels, the user's own plan, buttons. Under 400 characters before the first tap is the target for the top line. |
| `networth/guard.py` | The send gate for every model-written message. (a) Every number in the text must appear in the structured engine output it was written from, after normalising formats (₹1,00,000, 56%, 14 of 22). (b) None of PRODUCT.md's banned words, in English or Hindi transliteration. (c) No imperative advice patterns ("you should", "put your money", "move ₹"). A failed draft gets one rewrite. A second failure sends the plain template version with no model text. Every verdict is logged. |
| Chat intents (`networth/chat/`) | Free text from Telegram goes to a small classifier (the `cheap` role) with closed types: `what_happened_today`, `why`, `tip_check`, `explain_this`, `plan_question`, `other`. Each has a handler. `what_happened_today` uses the watcher's confirmed stories from the last 24 hours. `tip_check` searches for the claim's story, applies the watcher's confirmation rule, and answers with the verdict and, if confirmed and classified, the history line. `other` gets a short polite scope line. |
| Explain this | Forwarded text, a link, or a photo (Telegram `photo`, fetched with `getFile`, read with the vision-capable model in config). Answer: what it is, how big, the 3 or 4 things to know, the jargon decoded using the beginner glossary, with facts only from what was sent or a confirmed source. Never apply, skip, buy, sell, a score, or a rank. Must pass `guard.py` with the sent content as its number source. Hindi and Hinglish replies when the user writes that way or chose it. |
| Per-user pages | `/u/{token}` shows the user's plan and their last brief, with the token signed with `LINK_SIGNING_SECRET`. No login. A bad or expired token gets a friendly 404. |
| Rare alerts | A confirmed event with at least 8 episodes and a large effect (put the threshold in config and justify it in the report) sends one alert to users with `alerts_on`, at most 2 a month per user. Pull-only users never get one. Uses `send()` from 3A, so stopped and paused users stay silent. |
| Schedules | Maritime `GET /schedules` (or the trigger CLI, whichever its docs say works) runs the watcher every 30 minutes in market hours and the brief daily at 08:00 Asia/Kolkata for users whose investing day is today. In-process timers don't count, since the VM sleeps. |
| Deploy | Follow `docs/deploy.md`. The owner has run `maritime login`. If any step still needs the owner, raise OWNER NEEDED with the exact command and continue. Env vars set with `maritime env set`, never in the image. |
| Keiki (stretch, time-boxed) | Use Keiki's **external harness** (https://onkeiki.com/docs/external-harness.md), not a Keiki-hosted model. Keiki owns the channel, inbound screening and traces, and pushes each signed turn to our server. Our server runs the same chat intents and `guard.py`, then sends the exact text through `POST {turnUrl}/messages` and completes the turn. Our words go out unchanged, and our guardrails stay ours. Read the doc's push, relay and inbox modes and pick the simplest that works on Maritime. Key is `KEIKI_API_KEY` in `.env`. |
| `tests/` | No network. Fake Telegram, fake model. Guard tests with planted bad numbers and banned words in English and Hinglish. Intent routing per type. Explain-this on a fixture IPO page text. Alert caps. Schedule handler idempotency (the same brief never goes out twice on the same day). |

## Not in this phase

Evals and walk-forward calibration (Phase 5), holdings or broker linking, IPO history data, fundamentals data, factor cards, WhatsApp, any score or rank, any buy or sell wording.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. The server runs on Maritime at a public URL. `/health` returns 200 there, and `/why/rbi_hike/^NSEBANK` renders there.
3. The Telegram webhook points at the Maritime URL. The coordinator completes onboarding live in Telegram Web, then gets a real investing-day brief by a command you document (for example `/brief` for the owner only). Every number in it matches the engine.
4. A guard test proves a draft with an invented number is blocked, rewritten, then sent as a template on a second failure. Another proves banned words and "you should" phrasing are blocked in English and Hinglish.
5. Live, the coordinator sends "What happened today?", a forwarded fake tip, and "Why?" and gets correct, sourced answers. The fake tip is rejected with its reason.
6. Live, the coordinator forwards a real IPO page (text or screenshot) and gets Explain this back in plain words. It has jargon decoded, no score, no apply or skip. The same in Hinglish when asked in Hinglish.
7. `/u/{token}` works with a real token and returns a friendly 404 with a tampered one.
8. The schedule is registered on Maritime and listed by its CLI or API. A test proves the daily brief is idempotent per user per day.
9. Alert rules are tested: below 8 episodes no alert, a stopped user no alert, the monthly cap holds.
10. The deployed `/` and `/why/rbi_hike/^NSEBANK` return 200 after a fresh redeploy. The Jev vs model intent accuracy table is in the report.
11. Keiki is either working (one live tool call shown in the report) or recorded as a gap with the exact blocking error.
12. `docs/phases/phase-3b-report.md` lists what was built, sample messages (brief, each intent, Explain this in English and Hinglish), the guard's rules, the deploy URL, cost per brief and per chat turn from `data/llm_calls.jsonl`, OWNER NEEDED items, known gaps and deviations.
13. Nothing secret is committed, and `data/` is not committed.

## The gate, branch policy and shared files

- Run `make check` before every commit. Don't commit red. If it's red only because of Phase 1B's uncommitted engine files, confirm your own tests are green and say so in the commit message.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Messages to real people other than the owner are out. Test only with the owner's and coordinator's chats.
- Finish with `PHASE 3B READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
