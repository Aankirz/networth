# Deploying Networth to Maritime

One container serves the bot webhook, `/health` and the web pages. Its state is one SQLite file in `/data`, which survives sleep, restart and redeploy. Sources: https://maritime.sh/docs/frameworks/custom, https://maritime.sh/docs/web-apps and https://maritime.sh/docs/cli/llms.txt, all read on 2026-10-25.

## What the container does

- `Dockerfile` at the repo root. Maritime builds it on its own build machine.
- The CMD is in exec form, `python -m networth.app`. That reads the injected `$PORT` and binds `0.0.0.0`. A `sh -c` CMD makes the VM kernel-panic on boot, and a hardcoded port boot-loops it.
- `GET /health` returns 200 with no IO.
- `POST /telegram/webhook` checks the `X-Telegram-Bot-Api-Secret-Token` header.
- On boot, if `PUBLIC_URL` is set, the app calls Telegram `setWebhook` with `PUBLIC_URL/telegram/webhook` and the secret. A Telegram update to a sleeping agent wakes it in about a second.

## Once, by the owner

OWNER NEEDED: Maritime login. Run these steps:

```bash
npm install -g maritime-cli          # Node 20.12+
maritime login                       # or: maritime login --device --json
maritime whoami --json               # exit 0 means logged in
```

Email verification must be done first. Until then, `create` and `deploy` return 403 `email_not_verified`. The repo `Aankirz/networth` is private, so install the Maritime GitHub App on it when Maritime asks.

## Create and deploy

```bash
maritime create networth --repo https://github.com/Aankirz/networth --public --port 8080 --json
maritime info networth --json        # note the agent id; the URL is https://<agent-id>.mtm.sh
```

Set the secrets. Values come from your local `.env` and never go in the repo:

```bash
maritime env set networth TELEGRAM_BOT_TOKEN=... --json
maritime env set networth TELEGRAM_WEBHOOK_SECRET=... --json
maritime env set networth LINK_SIGNING_SECRET=... --json
maritime env set networth PUBLIC_URL=https://<agent-id>.mtm.sh --json
maritime env set networth DATA_DIR=/data --json
```

Deploy the latest `main`. Env vars set without `--reload` apply on the next boot, and a deploy is a fresh boot:

```bash
maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json
```

## Check it

```bash
curl -s https://<agent-id>.mtm.sh/health                 # {"ok":true}
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<agent-id>.mtm.sh/telegram/webhook   # 401
maritime logs networth -f                                 # look for "webhook set"
maritime exec networth ls /data --json                    # networth.sqlite appears after the first /start
```

Then send `/start` to @networth_professor_bot.

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
