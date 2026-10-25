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
- `POST /keiki/turn` takes signed Keiki turns for email and Slack (see Keiki below). An unsigned or stale request gets 401.

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

## News on /data

The deployed watcher runs only on weekdays from 09:00 to 15:59 Kolkata, so a fresh deploy outside those hours has no news. `/brief` then finds no event this month and "What happened today?" says it hasn't read the news. To seed the VM, run one cycle locally (about $0.10 in OpenAI and Exa calls) and push its database:

```bash
uv run python -m networth.watcher.run --once      # writes data/watcher.sqlite
npx --no-install maritime exec <agent-id> --json --body-json '{"command":"ls -la /data"}'
scripts/push_data.sh watcher.sqlite <agent-id>
```

Look at the `ls` first. A `watcher.sqlite` there means the VM's own watcher has already run, and the push replaces whatever it wrote. Its alerts are already claimed in `networth.sqlite`, so nothing is sent twice. Only the news it pulled is lost until its next cycle. Once the VM's watcher is running on schedule, stop pushing.

## Plan range table on /data

`/range`, the "My range" button and `/plan-range` read `$DATA_DIR/sim/returns.csv`, the same data dir every other store uses (`/data` on the VM, `data/` locally). The image has no copy, since `data/` is gitignored. Build the table locally, then push both files:

```bash
uv run python -m networth.sim.data                 # writes data/sim/returns.csv and sources.json
scripts/push_data.sh sim/returns.csv <agent-id>
scripts/push_data.sh sim/sources.json <agent-id>
```

Each push prints the sha256 it checked inside the VM. With no table, `/plan-range` returns a 503 page and `/range` says the range isn't available right now. Before Phase 3D the app looked in `/app/data/sim`, which a redeploy wipes.

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

## Keiki: email and the external harness (Phase 3C)

Keiki carries email to and from the same server. Keiki never writes a user-facing word. Its agent runs on the **external harness**, so every inbound email becomes a signed `POST /keiki/turn` to this container. The server answers 202, runs the same intent, handler and guard as Telegram, and sends the exact text back through Keiki's turn API. Sources: https://onkeiki.com/docs/external-harness.md and https://onkeiki.com/docs/partner-deployments.md, read on 2026-10-25.

What exists in the Keiki org (ids, not secrets):

| Resource | Id |
| --- | --- |
| Agent `Networth` (deployment `external_ref: networth`) | `8d5b1d0c-2f0d-42a2-ad0c-e78cabf929c2` |
| Harness | `external`, mode `push`, `dispatchUrl https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/keiki/turn`, `timeoutMs 600000` |
| Email channel | `agentmail`, region `us`, inbox `networth@agentmail.to`, channel id `3ef1287d-8979-41c4-b838-e468d017e95f` |

To recreate them from scratch (org-wide key with `*` scope in `KEIKI_API_KEY`), in this order, so no Keiki-hosted model ever has a channel to answer on:

```bash
K="Authorization: Bearer $KEIKI_API_KEY"; J='Content-Type: application/json'
curl -s -X POST https://onkeiki.com/api/v1/developer/deployments -H "$K" -H "$J" \
  -d '{"external_ref":"networth","agent":{"name":"Networth","model":"google/gemini-3.8-flash","system_prompt":"unused: external harness"}}'
curl -s -X PATCH https://onkeiki.com/api/v1/developer/config -H "$K" -H "$J" \
  -d '{"agent_id":"<agent-id>","harness":"external","harness_config":{"mode":"push","dispatchUrl":"https://api.maritime.sh/a/<maritime-agent-id>/keiki/turn","timeoutMs":600000}}'
curl -s -X POST https://onkeiki.com/api/v1/developer/deployments -H "$K" -H "$J" \
  -d '{"external_ref":"networth","agent":{},"channels":[{"type":"agentmail","region":"us","mode":"create","username":"networth"}]}'
```

The `dispatchUrl` must be the `api.maritime.sh/a/<id>` address. Keiki follows no redirects and rejects plain HTTP.

Env vars (names only; values from `.env`):

```bash
maritime agents env set <agent-id> KEIKI_API_KEY=... KEIKI_AGENT_ID=8d5b1d0c-2f0d-42a2-ad0c-e78cabf929c2 --secret
maritime agents env set <agent-id> KEIKI_EMAIL=networth@agentmail.to
# optional, only if the HMAC signature is turned on (see Rotate below)
maritime agents env set <agent-id> KEIKI_SIGNING_SECRET=whsec_... --secret
```

How a turn is trusted: the server checks `Keiki-Signature-Ed25519` against Keiki's public keys at https://onkeiki.com/.well-known/keiki-turn-keys.json (cached, refetched on an unknown `kid`). With `KEIKI_SIGNING_SECRET` set it also accepts a valid HMAC `Keiki-Signature`. Anything unsigned, signed with an unknown key, more than 5 minutes off, or for another agent id gets 401. A repeated turn id answers 200 and runs nothing.

Rotate:
- The Ed25519 key is Keiki's. When Keiki rotates it, the new `kid` appears in the key set and the server refetches it. Nothing to do.
- The HMAC secret: `curl -s -X POST -H "$K" https://onkeiki.com/api/v1/developer/agents/<agent-id>/harness/signing-secret` returns a new `whsec_...` once. Set it with `maritime agents env set <agent-id> KEIKI_SIGNING_SECRET=... --secret`, then restart the agent. Until the restart, Ed25519 still verifies every turn.
- The API key: `curl -s -X POST -H "$K" https://onkeiki.com/api/v1/keys/<key-id>/rotate` returns the new key once; the old one stops at once. Update `.env` and `KEIKI_API_KEY` on Maritime.

Check it after a deploy:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://api.maritime.sh/a/<agent-id>/keiki/turn -d '{}'   # 401 unsigned
```

Then email `networth@agentmail.to` from your own address. `data/keiki_turns.jsonl` on the VM gets one line per turn (turn id, trace id, hashed user id, channel type, kind, intent, guard verdict, cost; never message text or an address), and `GET https://onkeiki.com/api/v1/traces?limit=5` shows Keiki's side of the same turns. Keiki's trace id for a turn is the turn id.

### Slack through the same harness

Slack is a second Keiki channel on the same agent and the same harness. A Slack message becomes a signed `POST /keiki/turn` like an email, runs the same intent, handler and guard, and gets the same plain text back. The contact is the Slack author (`slack:<team>:<user>`), so all of one person's threads and DMs are one profile. A first message gets the same short setup as a first email. `/link` works from Slack too: the user sends the six-digit code there instead of by email. Briefs and alerts are never sent to Slack. They stay on Telegram or email. Source: https://onkeiki.com/docs/slack-agents.md and the channel table in https://onkeiki.com/docs/partner-deployments.md, read on 2026-10-25.

The agent answers DMs to the app and messages that mention it. Keiki ignores other channel chatter before it reaches the harness.

OWNER NEEDED: create and install a Slack app. Keiki needs its bot token and signing secret, and only the workspace owner can install an app. Use one of these two ways.

**A. From the Keiki dashboard (recommended).** Keiki writes the app manifest with the right scopes and its own event URLs.
1. Open https://onkeiki.com/dashboard, go to agent `Networth`, then Channels, then Slack.
2. Follow its "create app from manifest" link. In Slack, pick the workspace, paste the manifest and click Create.
3. In the Slack app: Install App, then Install to Workspace, then Allow.
4. Paste the Bot User OAuth Token (`xoxb-...`, under OAuth & Permissions) and the Signing Secret (under Basic Information) back into Keiki's Slack form.
5. Do not change the harness or the model on that page. The harness stays `external`.

**B. Through the developer API.** Use this if the dashboard has no Slack option. Create the app at https://api.slack.com/apps (From scratch), install it, and copy the bot token and signing secret into the local `.env` as `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`. Never commit them. Then:

```bash
curl -s -X POST https://onkeiki.com/api/v1/developer/deployments -H "$K" -H "$J" \
  -d "{\"external_ref\":\"networth\",\"agent\":{},\"channels\":[{\"type\":\"slack\",\"bot_token\":\"$SLACK_BOT_TOKEN\",\"signing_secret\":\"$SLACK_SIGNING_SECRET\"}]}"
curl -s -H "$K" https://onkeiki.com/api/v1/developer/deployments/networth   # the slack channel's detail
```

Paste the URLs from the channel's `detail` into the Slack app. Event Subscriptions takes the events URL. Interactivity takes the actions URL if one is listed. Keiki's dashboard manifest lists the scopes. Without it, these are a guess, not taken from Keiki: `app_mentions:read`, `chat:write`, `im:history`, `im:read`, `im:write`, `users:read`, `reactions:write`, with bot events `app_mention` and `message.im`. Turn on App Home, then Messages Tab, then "Allow users to send messages".

No Maritime env var changes. The server needs nothing new for Slack.

Check it: DM the app `What happened today?`. The answer must match the email and Telegram answers. Then `GET https://onkeiki.com/api/v1/traces?limit=5` shows a trace with `metadata.channel` `slack`, and `data/keiki_turns.jsonl` gets a line with `"channel": "slack"`. The first payload after a boot logs its channel keys (never values). If that log shows no `teamId` and `userId`, each Slack conversation becomes its own contact. The fix is then the key names in `networth/keiki/wire.py` `_contact`.

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
