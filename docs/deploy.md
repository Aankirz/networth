# Deploying Networth to Maritime

One container serves the bot webhook, `/health` and the web pages. Its state is one SQLite file in `/data`, which survives sleep, restart and redeploy. Sources: https://maritime.sh/docs/frameworks/custom, https://maritime.sh/docs/web-apps and https://maritime.sh/docs/cli/llms.txt, all read on 2026-10-25.

## What the container does

- `Dockerfile` at the repo root. Maritime builds it on its own build machine.
- The CMD is in exec form, `python -m networth.app`. That reads the injected `$PORT` and binds `0.0.0.0`. A `sh -c` CMD makes the VM kernel-panic on boot, and a hardcoded port boot-loops it.
- `GET /health` returns 200 with no IO.
- `POST /telegram/webhook` checks the `X-Telegram-Bot-Api-Secret-Token` header.
- On boot, if `PUBLIC_URL` is set, the app calls Telegram `setWebhook` with `PUBLIC_URL/telegram/webhook` and the secret. A Telegram update to a sleeping agent wakes it in about a second.
- `GET /schedules` publishes the scheduled jobs, and `POST /chat` runs the one Maritime delivers (see Schedules below).
- `GET /u/{token}` is a user's own page, signed with `LINK_SIGNING_SECRET`.

## Once, by the owner

OWNER NEEDED: Maritime login. Run these steps:

```bash
npm install -g maritime-cli          # Node 20.12+
maritime login                       # or: maritime login --device --json
maritime whoami --json               # exit 0 means logged in
```

Email verification must be done first. Until then, `create` and `deploy` return 403 `email_not_verified`. The repo `Aankirz/networth` is public, so Maritime clones it with no GitHub App. If it is ever made private, install the Maritime GitHub App (Settings → GitHub).

## Create and deploy

```bash
maritime create networth --repo https://github.com/Aankirz/networth --public --port 8080 --json
maritime info networth --json        # note the agent id
```

Set the secrets. Values come from your local `.env` and never go in the repo. Use the `api.maritime.sh/a/<agent-id>` address for `PUBLIC_URL`. On 2026-10-25 the `https://<agent-id>.mtm.sh` address served a certificate that did not match its hostname, and Telegram only delivers webhooks over valid TLS:

```bash
maritime env set networth TELEGRAM_BOT_TOKEN=... --json
maritime env set networth TELEGRAM_WEBHOOK_SECRET=... --json
maritime env set networth LINK_SIGNING_SECRET=... --json
maritime env set networth PUBLIC_URL=https://api.maritime.sh/a/<agent-id> --json
maritime env set networth DATA_DIR=/data --json
```

Phase 3B adds the model, search and Jev keys. Without them the bot still answers, from code-written templates only:

```bash
maritime agents env set <agent-id> OPENAI_API_KEY=... EXA_API_KEY=... --secret
maritime agents env set <agent-id> AI_GATEWAY_API_KEY=... AI_GATEWAY_BASE_URL=... JEV_MODEL=... --secret
maritime agents env list <agent-id> --json   # names only; secret values are masked
```

The CLI writes one variable per request. On 2026-10-25 some writes failed with `Okibi Identity authorization: ... context deadline exceeded` while others in the same command landed, so check `env list` and re-run only the missing keys.

## Engine data on /data

`data/` is gitignored, so the image has no `base_rates.sqlite` and every engine page answers 500 until it is copied onto the volume. Run this once, and again after every engine rebuild:

```bash
scripts/push_rates.sh <agent-id>
```

Maritime's file upload refuses bodies above about 80 KB (`HTTP 500 Write failed`), so the script uploads the file gzipped in 80 KB chunks, joins it inside the VM and checks its sha256.

## Schedules

A sleeping VM's timers never fire, so Maritime is the alarm clock (https://maritime.sh/docs/triggers). The app serves `GET /schedules`:

| id | cron (Asia/Kolkata) | prompt | does |
| --- | --- | --- | --- |
| `watcher` | `*/30 9-15 * * 1-5` | `RUN_WATCHER` | one watcher cycle, then rare alerts |
| `brief` | `0 8 * * *` | `RUN_BRIEF` | the brief for every user whose investing day is today |

Maritime polls the list while the agent is awake, registers wake triggers, and POSTs each prompt to `/chat` with `source: "scheduled"`. The job runs in a background thread so `/chat` answers at once. `/chat` is public and Maritime sends no secret with a scheduled prompt (its docs say to treat the URL as the secret), so a forged call is possible and its cost is bounded, not zero. The watcher refuses runs outside Mon to Fri, 09:00 to 15:59 Kolkata, and within 25 minutes of the last cycle, so forgery adds at most about one paid cycle (about $0.10) an hour during market hours. One job runs at a time, briefs are claimed once per user per day, and alerts once per user per event. After a deploy, wake the agent once (`curl .../health`) and check:

```bash
maritime agents triggers list <agent-id> --json   # expect watcher and brief
```

If the list stays empty, register the same two by hand with `maritime triggers create` and the prompts above.

Deploy the latest `main`. Env vars set without `--reload` apply on the next boot, and a deploy is a fresh boot:

```bash
maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json
```

## Check it

```bash
curl -s https://api.maritime.sh/a/<agent-id>/health      # {"ok":true}
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.maritime.sh/a/<agent-id>/telegram/webhook   # 401
maritime logs networth -f                                 # look for "webhook set"
maritime exec networth ls /data --json                    # networth.sqlite appears after the first /start
```

Then send `/start` to @networth_professor_bot. After setup, `/brief` sends this month's brief (once per day; a repeat resends the same text), and free text, forwards, links and photos get chat answers.

## Local development

```bash
uv sync
uv run python -m networth.bot.poll        # long polling, reads .env
```

`poll` calls `deleteWebhook` first, because Telegram refuses `getUpdates` while a webhook is set. This disconnects production until the server restarts and sets the webhook again. To restore it without a redeploy:

```bash
maritime restart networth --json
```

Run the server alone with `uv run uvicorn networth.app.main:app --port 8080`.

## Build the image locally

```bash
docker build -t networth .
docker run --rm -e PORT=18789 -p 18789:18789 networth
curl -s localhost:18789/health
```
