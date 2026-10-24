# Phase 3A report · Server, Telegram and onboarding

Built 2026-10-25 against `docs/phases/phase-3a-delivery.md`.

## What a user gets

A person who taps Start on @networth_professor_bot answers seven questions with buttons: goal, time, monthly amount, investing day, drop comfort, what to leave out, and language. They pick one of three starter plans or type their own split, then read their answers back and tap "Looks right" or fix one field. Taps alone take about ten messages. No LLM is involved, so it is fast and gives the same result every time. After that, `/plan`, `/pause`, `/resume`, `/stop` and `/help` work. "What happened today?" and forwarded tips get a polite "coming soon".

## What was built

| Path | What it does |
|---|---|
| `networth/app/store.py` | The `Profile`, `Plan` and `Message` shapes and `$DATA_DIR/networth.sqlite` (default `data/`). Tables are created on first use. A missing column is added with `ALTER TABLE`, so a second run changes nothing. It has no holdings. It adds `invest_day`, `lang`, `alerts_on`, an onboarding `step` and a `status` (active, paused or stopped). |
| `networth/app/settings.py` | Reads env vars, with `.env` filling gaps. It never writes to `os.environ`, so other phases' config tests see a clean environment. |
| `networth/app/main.py` | The FastAPI app. `GET /health` returns `{"ok": true}` with no IO. `POST /telegram/webhook` checks the secret header with `hmac.compare_digest` and returns 401 on a mismatch, 503 when no secret is configured, and 200 after handling. If handling fails it still returns 200, so Telegram doesn't redeliver forever. On boot, if `PUBLIC_URL` is set, it calls `setWebhook`. It mounts `networth.web.routes:router` if that imports. Any import failure is logged and the server keeps running. |
| `networth/app/__main__.py` | `python -m networth.app` serves `0.0.0.0:$PORT`. This is the Docker CMD in exec form, as Maritime requires. |
| `networth/bot/telegram.py` | A thin Bot API client covering sendMessage with inline keyboards, answerCallbackQuery, editMessageReplyMarkup, setWebhook, deleteWebhook and getUpdates. It uses IPv4 only, from `networth/net.py`, under a wall-clock deadline. It retries once on 429 after `retry_after`, capped at 30 s. Errors name the method, never the URL or token, and the `httpx2` request logger is silenced because its lines contain the URL. |
| `networth/bot/onboarding.py` | A pure state machine with one registry entry per step (parse, apply, retry line) and one prompt table. A tap and a typed answer go through the same parse. The next-step rule is "go to the summary once every answer and a plan exist, otherwise go to the next question". That rule makes "Fix something" work with no extra flag. It also holds the amount parser and money formatting (₹1,00,000, $1,000). |
| `networth/bot/commands.py` | The IO shell. It parses a raw update into `Text`, `Tap` or `Media` at the boundary. It runs commands from a table. `send()` is the only way out: it sends nothing to a stopped user, and no proactive message to a paused one. State is saved before anything is sent. |
| `networth/bot/poll.py` | `python -m networth.bot.poll` removes any webhook, then long-polls. A bad update or a dropped connection is logged and skipped. Ctrl-C exits with code 0. |
| `Dockerfile`, `.dockerignore` | `python:3.12-slim` with `ca-certificates`, `uv sync --frozen --no-dev`, `DATA_DIR=/data` and an exec-form CMD. `.env`, `data/`, tests and docs stay out of the image. |
| `docs/deploy.md` | The exact `maritime` commands, checked against Maritime's docs on 2026-10-25. |
| `tests/test_onboarding.py`, `test_app.py`, `test_amount_parse.py`, `test_wording.py` | 62 tests, with no network and a fake Telegram client. |

## Done-when checks, as run by the builder

| # | Check | Result |
|---|---|---|
| 1 | `make check` | Passed: 226 tests, ruff clean. This includes the other builders' uncommitted tests in the shared tree. |
| 2 | `uv run uvicorn networth.app.main:app --port 8080`, then `curl localhost:8080/health` | `{"ok":true}` with 200 |
| 3 | Webhook POST without the header | 401. With the header, a fake `/start` returns 200 and stores a Profile at step `goal` (`test_webhook_with_the_secret_stores_a_profile_at_the_first_step`). |
| 4 | Taps-only onboarding | `test_button_taps_take_start_to_done_and_store_every_field` checks every Profile field and the Plan. |
| 5 | `/stop` | `test_stop_silences_everything_until_start`: status `stopped`, `send()` returns False and nothing reaches the bot, free text gets no reply, and `/start` brings the user back. |
| 6 | Amount parser | `1 lakh`, `1.5L`, `₹50,000`, `50k`, `$500`, `500 dollars`, `10,00,000`, `1 crore`, `rs 5000`, `usd 1200` and more all parse. `""`, `abc`, `0`, `-5`, `lots`, `5 years` and `$5` are rejected, and the user gets a retry line. Nothing crashes. |
| 7 | Live check | The coordinator's step. The builder ran `python -m networth.bot.poll` against the real bot. It removed the webhook, polled with no errors, and stopped in 0.1 s on Ctrl-C. No log line contained the token. |
| 8 | `docker build .` | Succeeded. `docker run -e PORT=18789` answered `/health` 200 on 18789. |
| 9 | Banned words | `test_wording.py` scans every string literal in `networth/bot` and `networth/app`, plus every text and button label sent during a full onboarding and every command. |
| 10 | This report | Here. |
| 11 | Secrets | `.env` and `data/` are gitignored and in `.dockerignore`. No token is in any test or log. |

## OWNER NEEDED

- **Maritime login and deploy.** Follow `docs/deploy.md`: `npm i -g maritime-cli`, `maritime login`, verify your email, install the Maritime GitHub App on the private repo, then `maritime create`, the `env set` lines and `maritime deploy`.

## Deviations from the brief and spec

- **No `/chat` route.** Maritime's contract has a `POST /chat`, but Phase 3A has no free-text chat. It comes with Phase 3B. `/health` is the part Maritime needs to boot.
- **`max_drop_ok` in Plan duplicates `drop_comfort`.** tech.html section 03 asks for it, so it is kept and re-synced whenever drop comfort changes.
- **`Plan` stores `name` and `targets_pct`** (safety, core, growth). It has no separate `buckets` field, because the three bucket names are fixed.
- **`markets` is derived from `exclude`.** Leaving out US stocks drops `us`. It is a property, so it can't drift, and it is also written to its column for SQL readers.
- **`link_token` is random** (`secrets.token_urlsafe(16)`). Signing it with `LINK_SIGNING_SECRET` happens when per-user links ship in 3B.
- **`lang` is asked and stored, but onboarding stays in English.** Hindi and Hinglish replies need 3B's model or hand translations.
- **`tests/test_app.py` drives the ASGI app directly** rather than through `TestClient`. It needs no extra test dependency.
- **The starter plans show no crash history yet.** product.html's sample says "Here's how each did through every crash since 2008". Those numbers must come from the engine, which has no portfolio replay yet, so the message leaves them out rather than invent them.
- **fastapi and uvicorn landed in Phase 4's commit `49dd86e`.** This phase added them with `uv add`, and the lock file is shared, so Phase 4 committed them with its own `jinja2`.

## Known gaps

- Words for numbers ("five lakh") are not parsed. The user gets the retry line. One sentence carrying several answers ("house, in 4 years, 1 lakh on the 1st") also waits for 3B's model.
- Running `poll` removes the production webhook until the server restarts. `docs/deploy.md` says so.
- A stopped user's taps are still answered (to clear Telegram's spinner) and logged. No message is sent.
- Investing days run 1 to 28 only, so every month has the day.
- The webhook handles updates inline. Each one is a few SQLite writes and one or two sendMessage calls under a 15 s deadline, well inside Telegram's webhook timeout.

## Live check, round 1 (2026-10-25 01:45)

The coordinator saw answers it never tapped: a horizon of 4 years, 10% instead of 20%, Defence toggled on, and the language question twice. Cause: the builder was tapping the same chat from Telegram Web at the same minute, and new messages shifted the buttons under its cursor. Ruled out from evidence: no local poller was running, the account has one agent, and Telegram's `getWebhookInfo` showed no pending updates and no delivery error, so there were no redeliveries. The duplicate language question is the stale-tap reply (a toast, then the current question again).

Two real gaps showed up on review and are fixed:
- **Redelivery.** Telegram delivers updates at least once. Each `update_id` is now claimed in an `updates` table before handling, and a replay is dropped (`test_a_redelivered_update_is_applied_once`).
- **Concurrent taps.** Webhook requests run on a threadpool, so two taps on one question could both read the old step and both apply. `handle_update` now holds one process-wide lock (`test_two_taps_on_one_question_at_once_apply_only_one`). Both tests fail with the guards removed.

## The onboarding flow, every message word for word

Generated by driving the real `handle_update` with the fake bot. Nothing below was typed by hand.

**User:** types `/start`

```
Hi. I read the market news every day so you don't have to, and I'll check in on the day you invest. A few quick taps to set you up.

What's this money for?
```
Buttons: [A house] [Retirement] / [Education] [Just growing it]

**User:** taps `ob:goal:house`

```
When will you need it?
```
Buttons: [Within 3 years] [3 to 5 years] / [5 to 10 years] [10+ years]

**User:** taps `ob:horizon:4`

```
About how much do you invest each month? Tap one, or type it like 25k, 1 lakh or $500.
```
Buttons: [₹10,000] [₹25,000] [₹50,000] / [₹1,00,000] [$500] [$1,000]

**User:** types `five lakh`

```
I didn't catch that amount. Try something like 25k, 1 lakh or $500.

About how much do you invest each month? Tap one, or type it like 25k, 1 lakh or $500.
```
Buttons: [₹10,000] [₹25,000] [₹50,000] / [₹1,00,000] [$500] [$1,000]

**User:** taps `ob:amount:100000`

```
Which day of the month do you usually invest? I'll check in that morning.
```
Buttons: [1st] [5th] [10th] / [15th] [20th] [25th]

**User:** taps `ob:day:1`

```
Markets fall sometimes. In a bad year, how big a fall could you sit through without losing sleep?
```
Buttons: [10%] [20%] / [30%] [40% or more]

**User:** taps `ob:drop:20`

```
Anything you want left out? Tap to toggle, then Done.
```
Buttons: [US stocks] / [Crypto] / [Tobacco, alcohol, gambling] / [Defence] / [Done]

**User:** taps `ob:exclude:crypto`

Toast: Crypto left out
Keyboard updated: [US stocks] / [✓ Crypto] / [Tobacco, alcohol, gambling] / [Defence] / [Done]

**User:** taps `ob:exclude:done`

```
Which language do you want me to use?
```
Buttons: [English] [हिंदी] [Hinglish]

**User:** taps `ob:lang:en`

```
Pick a starting plan, or make your own. These are common mixes, shown for education. The plan is always your choice.

Safety is money you'll need soon: FDs, liquid funds.
Core is broad index funds you hold for years.
Growth is single stocks and sectors.

Steady: 60% safety, 40% core, 0% growth
Balanced: 20% safety, 70% core, 10% growth
Ambitious: 10% safety, 60% core, 30% growth
```
Buttons: [Steady] [Balanced] [Ambitious] / [My own split]

**User:** taps `ob:plan:balanced`

```
Here's what I have.

Goal: A house, in about 4 years
Each month: ₹1,00,000 on the 1st
A fall you can sit through: up to 20%
Left out: Crypto
Language: English
Plan: Balanced. 20% safety, 70% core, 10% growth

Looks right?
```
Buttons: [Looks right] [Fix something]

**User:** taps `ob:confirm:fix`

```
What would you like to change?
```
Buttons: [Goal] [Time] [Amount] / [Day] [Fall] [Left out] / [Language] [Plan]

**User:** taps `ob:confirm:day`

```
Which day of the month do you usually invest? I'll check in that morning.
```
Buttons: [1st] [5th] [10th] / [15th] [20th] [25th]

**User:** types `31`

```
Pick a day from 1 to 28, so every month has it.

Which day of the month do you usually invest? I'll check in that morning.
```
Buttons: [1st] [5th] [10th] / [15th] [20th] [25th]

**User:** taps `ob:day:5`

```
Here's what I have.

Goal: A house, in about 4 years
Each month: ₹1,00,000 on the 5th
A fall you can sit through: up to 20%
Left out: Crypto
Language: English
Plan: Balanced. 20% safety, 70% core, 10% growth

Looks right?
```
Buttons: [Looks right] [Fix something]

**User:** taps `ob:confirm:ok`

```
You're all set. I'll message you on the 5th of each month, the morning you invest, with what history says about months like this one.

Meanwhile, type /help to see what I can do.

Research, not advice.
```

**User:** types `what happened today?`

```
Good question. Daily answers and tip checks are coming soon. I'll let you know when they're ready.
```

**User:** types `/plan`

```
Your plan: Balanced. 20% safety, 70% core, 10% growth.
```
```
Pick a starting plan, or make your own. These are common mixes, shown for education. The plan is always your choice.

Safety is money you'll need soon: FDs, liquid funds.
Core is broad index funds you hold for years.
Growth is single stocks and sectors.

Steady: 60% safety, 40% core, 0% growth
Balanced: 20% safety, 70% core, 10% growth
Ambitious: 10% safety, 60% core, 30% growth
```
Buttons: [Steady] [Balanced] [Ambitious] / [My own split]

**User:** taps `ob:plan:own`

```
Type your split as three numbers that add up to 100: safety, core, growth. For example: 20 70 10
```

**User:** types `30 60 10`

```
Here's what I have.

Goal: A house, in about 4 years
Each month: ₹1,00,000 on the 5th
A fall you can sit through: up to 20%
Left out: Crypto
Language: English
Plan: Your own split. 30% safety, 60% core, 10% growth

Looks right?
```
Buttons: [Looks right] [Fix something]

**User:** taps `ob:confirm:ok`

```
You're all set. I'll message you on the 5th of each month, the morning you invest, with what history says about months like this one.

Meanwhile, type /help to see what I can do.

Research, not advice.
```

**User:** types `/help`

```
Here's what I can do.

/plan see or change your plan
/pause pause briefs and alerts
/resume turn them back on
/stop stop all messages
/start set up again or see your answers

Soon you'll be able to ask "What happened today?" or forward me a tip to check.

Research, not advice.
```

**User:** types `/pause`

```
Paused. I won't send briefs or alerts until you type /resume. You can still ask me things.
```

**User:** types `/resume`

```
Back on. I'll check in on the 5th.
```

**User:** types `/stop`

```
Stopped. I won't message you again. Type /start any time to come back.
```

**User:** types `hello?`


**User:** types `/start`

```
Welcome back.

Here's what I have.

Goal: A house, in about 4 years
Each month: ₹1,00,000 on the 5th
A fall you can sit through: up to 20%
Left out: Crypto
Language: English
Plan: Your own split. 30% safety, 60% core, 10% growth

Looks right?
```
Buttons: [Looks right] [Fix something]

**User:** types `/foo`

```
I don't know that one yet. Type /help to see what I can do.
```
