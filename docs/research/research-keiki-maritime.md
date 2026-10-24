# Deja on Keiki x Maritime: platform research (2026-10-24)

Sources: Maritime full docs dump `https://maritime.sh/llms-full.txt` (every page also served as `<url>.md`), Keiki `https://onkeiki.com/llms.txt`, `https://onkeiki.com/llms-full.txt`, `https://onkeiki.com/openapi.json`. Everything below is from those docs unless marked **[UNVERIFIED]** or **[INFERENCE]**.

---

## 1. Maritime

### Deploying a custom agent
- **Any Docker container** with a `Dockerfile` at the repo root. Python is fine (the docs give a FastAPI/uvicorn example). https://maritime.sh/docs/frameworks/custom
- The contract has three parts:
  1. Bind `0.0.0.0:$PORT`. PORT is injected and is currently 18789; hardcoding 8080 boot-loops the VM.
  2. `GET /health` returns any 2xx.
  3. `POST /chat` receives `{"message","source","conversation_id"}` and must reply within **30 s** with `{"response": "..."}` or plain text.
- Gotchas:
  - Install `ca-certificates`, or outbound HTTPS fails.
  - Keep state under `/data` only.
  - Use an **exec-form CMD** with no `sh -c`, or the VM kernel-panics. Use a `start.py` that reads `$PORT`.
- CLI (`npm i -g maritime-cli`, Node 20.12+). https://maritime.sh/docs/cli/llms.txt
  ```
  export MARITIME_TOKEN=mk_...            # maritime keys create --name deja --json (mk_ keys never expire)
  maritime create deja --repo https://github.com/you/deja --public --port 8000 --json
  maritime deploy deja --source github --repo <url> --branch main --wait --json
  maritime env set deja ANTHROPIC_API_KEY=sk-ant-... --reload --json
  maritime status deja --json ; maritime chat deja "hi" --json ; maritime logs deja -f
  maritime exec deja ls /data --json ; maritime history deja --json   # buildLog
  ```
- Other ways to deploy:
  - Upload a ZIP: `POST /api/upload/zip`, then `POST /api/agents` with `framework:"custom"`.
  - Use a public registry image: `imageName`.
  - Builds take 1-3 min. A build that prints nothing for 5 min is killed. https://maritime.sh/docs/builds
- Email verification is required before `create`, `deploy` or `keys create` work; until then they return 403 `email_not_verified`.

### Frameworks
- Templates: `claude_code`, `codex`, `openclaw`, `hermes`, `zeroclaw`, `dsh`. https://maritime.sh/docs/frameworks
- **The Claude Agent SDK is supported.** The `claude_code` template is Node with `@anthropic-ai/claude-agent-sdk`. Its full server code is in the docs. https://maritime.sh/docs/frameworks/claude-code
  - It **requires your own `ANTHROPIC_API_KEY`**, because Maritime's LLM proxy is OpenAI-format only.
  - It requires `IS_SANDBOX=1`, because the container runs as root with `bypassPermissions`.
  - Set `CLAUDE_CONFIG_DIR=/data/.claude` so sessions persist.
- CrewAI, LangGraph and AutoGen run as custom containers.

### Env vars and secrets
- Secret by default and encrypted.
- `maritime env set|import|list|pull|remove`. `--reload` hot-pushes the change; otherwise it applies on the next boot.
- The SDK has `setEnv` and `reloadEnv`. https://maritime.sh/docs/configuration

### Persistent disk
- `/data` survives sleep, restart and redeploy.
- Base allocation is 2 GB RAM and 5 GB SSD, up to 8 GB RAM and 100 GB SSD as add-ons.
- The process is snapshotted and resumed, so do not trust cached wall-clock time, and re-open connections lazily.
- The Files REST API (`/api/agents/{id}/files/*`, 100 MB per file) wakes the agent.

### Cron and scheduled jobs (critical)
- **Timers inside a sleeping VM do not fire.** Use platform triggers instead. https://maritime.sh/docs/triggers
  - `maritime triggers create deja --type cron --cron "0 7 * * *"`, with the delivered message set through the API's `config.prompt`.
  - **Or serve `GET /schedules`** returning `[{"id":"brief","cron":"0 7 * * *","tz":"America/New_York","prompt":"RUN_BRIEF","enabled":true}]`. Maritime polls it while the agent is awake, wakes the VM about 10 s early, and POSTs the prompt to `/chat` with `source:"scheduled"`.
  - **Or use the SDK** `push_schedules([...])` from inside the agent.
- An always-on add-on costs $20/mo per agent and keeps in-process timers alive.

### Exposing HTTP
- `--public --port N` gives the agent `https://<agent-id>.mtm.sh/`. It is private (share links) by default; public needs a verified email. A request wakes a sleeping agent. https://maritime.sh/docs/web-apps
- Every agent also gets a webhook invoke URL, `POST https://api.maritime.sh/api/webhooks/{agent_id}` with `X-Maritime-Webhook-Token`, rate-limited to 30/min. It delivers the payload as a chat message.
- Chat API: `POST /api/agents/{id}/chat`. https://maritime.sh/docs/api

### Logs
- CLI: `maritime logs <a> [-f] [--level error]`.
- REST: `GET /api/agents/{id}/logs?limit=&level=`.
- Build logs are in `maritime history --json`.
- SDK lifecycle webhooks: `agent.error`, `agent.woken`, `message.reply`, and others. https://maritime.sh/docs/sdk/webhooks

### Scale plan limits
https://maritime.sh/docs/limits, https://maritime.sh/docs/billing
- $500/mo for **500 machines**, **60 awake at once**. A wake past that limit gets a 429 with a 15 s retry hint.
- Extra machine $1/mo. RAM $2 per GB per month. SSD $1 per 5 GB per month. Always-on $20/mo.
- Hosting is not metered. LLM use through the proxy draws on separate prepaid AI credits; bring-your-own keys bypass them.
- Runtime limits: 30 s chat reply budget; exec 60 s attached and 3600 s detached; 100 MB per file.
- Free plan: 3 agents, 1 awake at a time.
- Students (.edu) get 3 months of Growth or Scale free. https://maritime.sh/students

### One agent per customer
- Python SDK `pip install maritime` or TS `maritime-sdk`. https://maritime.sh/docs/build
- `client.agents.provision(external_id=..., template=..., idle_ttl_seconds=...)` is idempotent.
- `end_users` API: upsert, policy caps, `eu_` tokens, usage per user.
- A project with `newChatPolicy: "spawn"` gives each new Telegram user their own VM.

### Channels on Maritime
- **Telegram (own bot, any framework)**: `POST /api/projects/{projectId}/channels/telegram {"botToken"}`. Maritime registers the webhook and routes messages to `/chat`. https://maritime.sh/docs/channels
- WhatsApp phone pairing and Google exist for OpenClaw-family agents only.
- **No iMessage or SMS on Maritime.**
- No Maritime API for pushing a message to a channel user was found. **[INFERENCE]** For proactive sends, your container calls Telegram's Bot API itself.

---

## 2. Keiki

### Access, API, and pricing
- **Invite-only.** Request access via `POST https://onkeiki.com/api/webapp/auth/waitlist`. https://onkeiki.com/setup.md
- It is **not dashboard-only**. Developer surfaces:
  - MCP server `https://onkeiki.com/mcp` (`claude mcp add --transport http keiki https://onkeiki.com/mcp`). Tools include `deploy_agent`, `talk_to_agent`, `list_channel_types`, `get_deployment`.
  - REST developer API (`/api/v1/developer/*`, `sk_live_` and `sk_test_` keys) and an OpenAPI spec.
  - TS SDK `@onkeiki/agents` (`AgentKit`, `kit.sync()`), which is Bun/TS only. No Python SDK was seen.
  - OpenAI- and Anthropic-compatible endpoints (`/api/v1/openai/chat/completions`, `/api/anthropic/v1/messages`).
  - Partner deployments: `POST /api/v1/developer/deployments` keyed by `external_ref`.
  - Links: https://onkeiki.com/docs/cloud-agents.md, https://onkeiki.com/docs/partner-deployments.md
- **Pricing is "proposed", and plans "open at launch".** https://onkeiki.com/pricing.md
  - Starter: $1/mo promo (normally $20) with $20 credits.
  - Pro: $100/mo, bring-your-own keys.
  - Max: $500/mo.
  - **Phone lines are extra: $300/mo on Starter, $150 on Pro, $99 on Max.**
  - An MCP connection needs an org with a plan. A sandbox org that requests channels gets 402 `plan_required`.
  - **[UNVERIFIED]** Competition credits or line grants. Keiki also runs a startup program offering credit and iMessage-line support (https://onkeiki.com/startups).

### External HTTP tools, webhooks, and MCP: YES
- **Webhook tools**: `POST /api/v1/developer/tools` with `{"name","description","inputSchema","executionType":"webhook","webhookUrl"}`.
  - Keiki POSTs `{input, context}` and the agent reads the JSON you return.
  - `context` includes `userId`/`phone`, and `X-Orchid-User-Id` is sent as a header.
  - Code tools (`executionType: "code"`) also exist.
- **MCP or OpenAPI connections**: `mcp_connections` on a deployment, up to 10, with `auth_mode` public, headers or oauth. Per-user headers go through `PUT /mcp-senders`. This needs the `sandbox` and `mcp` features.
- **Governed actions / approval** are available ("ask" before a tool runs).

### Proactive and outbound messages: YES, but mediated
1. **Notices API.** `POST /api/v1/developer/agents/{agentId}/notice {"text","phone"?}`.
   - The text goes **to the agent, not the user**: "only the agent decides whether and how to tell each person in its own words."
   - `phone` must match an **existing conversation**; otherwise you get a 404.
   - Omit `phone` to broadcast to up to 200 recent conversations (returns 202).
   - Needs the `agents:write` scope.
   - https://onkeiki.com/docs/agent-api.md#notices-from-your-server
2. **Alerts** (`defineAlert`, SDK).
   - A cron schedule with timezone, `dedupKey`, `shouldSend`, and `generate` returning text or media. Each alert fires per subscriber.
   - This is exactly a "7am daily briefing" (their own example is `0 7 * * *`).
   - **[UNVERIFIED]** How a user becomes a "subscriber".
3. **Loops capability.**
   - The agent creates cron or interval loops per user: `create_loop`, `run_loop`, `diff_since_last_run`.
   - "Quiet loops" send nothing when there is nothing to report, which fits rare same-day alerts.
- No raw "send this exact text to this phone" endpoint exists for Keiki-hosted agents. Exact text is only possible inside a turn: the external harness `POST {turnUrl}/messages`, or tool `delivered`.

### Channel rules for proactive sends
- **iMessage.** https://onkeiki.com/docs/imessage-best-practices.md
  - **Let the user text first.** Use an `sms:+1...?body=Hi` link.
  - Hard limit of 50 new conversations per line per day. Guideline is 5,000 messages per line per day; hard cap 7,000.
  - Avoid one-way broadcasts, bursts, and odd hours. Aim for about 1 user reply per 2 agent sends.
  - Opt-outs are enforced (`opted_out`).
  - A daily 7am brief to users who replied is fine. Keep same-day alerts genuinely rare.
  - Images and photos inbound are supported.
- **SMS.** Conflicting docs.
  - setup.md says SMS lines are bought in the dashboard and "SMS is not a deployment channel".
  - cloud-agents.md says "Phone calls, SMS/RCS and A2A … are not live yet (early access)".
  - Treat SMS as **unavailable** for 24h.
- **WhatsApp.**
  - You bring your own Meta credentials (`access_token`, `phone_number_id`, `app_secret`, `verify_token`).
  - Keiki surfaces error `131047 Re-engagement message`, which is Meta's 24h-window error.
  - **No template-message support is documented.** **[INFERENCE]** Outside the 24h window, proactive WhatsApp sends will fail.
- **Telegram.**
  - Bring a bot token. No window rules, provided the user has DM'd the bot first (Telegram Bot API norm).
  - Telegram is the lowest-risk push channel.
- Email (AgentMail) and Slack are also supported.

### Phone numbers
- Yes. Deploying an `imessage` channel makes **Keiki provision a dedicated line** (a paid recurring add-on). `get_deployment` shows the `phoneNumber`.
- There is also `POST /api/v1/developer/phones/acquire`.

### Inbound media and images: YES
- On iMessage and WhatsApp, a photo and its text arrive as one message.
- The `media` feature can `describe` images. Webhook tools called with an `attachment_id` get `context.attachments[id].url`, valid for **15 min**, to fetch the original. The sandbox has `download_attachment`.
- For a brokerage screenshot, fetch the original bytes in our tool and OCR or vision them ourselves rather than trust the description.

### Memory and per-user state
- Built-in per-user memory (supermemory: facts and preferences, auto-retrieve).
- Per-agent **entity storage**: `PUT/GET /api/v1/developer/agents/:id/storage/:entity`.
- "People" records.
- **[INFERENCE]** For holdings, keep the source of truth in our own store, keyed by Keiki `context.phone` / `userId`.

### Observability
- Traces with spans per turn (14 days), retry, evals, replay.

---

## 3. How Keiki and Maritime fit together

- **Keiki's own docs describe a "Keiki VM (Maritime)" harness.** https://onkeiki.com/docs/harnesses.md
  - Keiki runs each agent's turn loop in its own Maritime micro-VM.
  - Channels, history, tools, traces and delivery stay on Keiki. Turns are driven by long-polls under Maritime's 30 s limit, and the VM holds no credentials.
  - It is a *platform* setting (`ENABLE_MARITIME=true`, `MARITIME_API_KEY`), not a per-agent choice.
  - **[UNVERIFIED]** Whether onkeiki.com has it on, and whether you can select it.
- **Generic integration: the external harness.** https://onkeiki.com/docs/external-harness.md
  - Keiki pushes a signed `keiki.turn` (Ed25519 via JWKS, or HMAC `whsec_`) to your `dispatchUrl`.
  - You answer 202, then call `{turnUrl}/messages` and `/complete`. Turn deadline is up to 10 min.
  - Modes are `push`, `relay`, and `inbox`. Inbox means long-polling `GET /api/v1/harness/inbox/next?wait=25`, which needs no public URL.
  - A Maritime public URL can be the `dispatchUrl`. Note that turn tools come only through Keiki's MCP URL in the payload.
- Maritime's docs do not mention Keiki.
- **No public competition brief, integration guide, or example repo for "Keiki x Maritime" was found** (two searches). Ask the organizers.

---

## 4. Recommended architecture (simplest that satisfies (a)-(e))

**Primary design.** Keiki is the face and brain. Maritime is the always-on backend and scheduler.

```
User (iMessage line or Telegram bot) <──> Keiki cloud agent (prompt, memory, media, Loops)
                                            │ webhook tools / MCP
                                            ▼
             Maritime agent "deja-core" (Python FastAPI, --public --port, /data SQLite)
               • /tools/*        event/base-rate engine + holdings CRUD (keyed by Keiki phone/userId)
               • /tools/parse_screenshot  fetches context.attachments[id].url → Claude vision → holdings
               • /health, /chat  (Maritime contract) ; GET /schedules → 07:00 tz brief + */15 market-hours scan
               • on scheduled /chat: compute per-user brief/alert → POST Keiki /notice {text, phone}
```

| Requirement | How it is met |
| --- | --- |
| (a) Push | The Maritime cron trigger wakes deja-core at 07:00. It computes each user's brief and calls Keiki `notice` per phone; the agent words it and delivers it. Same-day alerts: a */15 scan sends a notice only when a threshold trips. |
| (b) Follow-ups | Native Keiki conversation. |
| (c) Our tools | Keiki webhook tools, or one `openapi` MCP connection pointing at deja-core. |
| (d) Image | Keiki inbound media. A tool receives the `attachment_id`, fetches the URL within 15 min, and parses it. |
| (e) Scheduled jobs | Maritime `/schedules` (or Keiki Alerts/Loops as the alternative). |

Other notes:
- One Maritime agent serves every user for the hackathon. Pitch Maritime SDK `provision(external_id=user)` as the per-user VM story.
- The Free plan is enough to build (3 agents, 1 awake). Scale or students covers the demo.
- Prefer Keiki-native **Alerts** if the TS SDK is acceptable and the "subscriber" semantics work. That removes one hop for (a), but moves the schedule to Keiki.

**Fallback.** Keiki cannot push, call tools, or we are not off the waitlist.

Run Deja entirely on Maritime with the **Telegram Bot API directly**:
- A Python container with the Anthropic SDK, or the Claude Agent SDK via the `claude_code` server pattern.
- `setWebhook` to `https://<agent-id>.mtm.sh/tg`, rather than the Maritime project channel, so we receive raw `photo` updates. Ack 200 fast and process asynchronously.
- `getFile` downloads screenshots, then Claude vision parses them.
- Proactive messages via `sendMessage(chat_id)` from the 07:00 and */15 `/schedules` wakes. Store `chat_id` and holdings in `/data/deja.db`.
- No line cost and no 24h window. The user must `/start` the bot first.

---

## 5. 15-minute spike tests (do these first, in parallel)

**Keiki**
1. **Access.** Can we sign in, connect `claude mcp add ... keiki`, and run `current_context`? Is the org on a plan, or is it 402 `plan_required` when adding a channel?
2. **Line.** `deploy_agent` with `channels:[{type:"telegram",bot_token}]`. Then try `imessage`: does it return `connected` with a `phoneNumber`, or `needs_payment`? What does the line cost us?
3. **Push.** Text the agent once. Then `curl POST /api/v1/developer/agents/$ID/notice -d '{"text":"Brief: AAPL earnings tonight, base rate +3.1% move","phone":"<E.164 or tg id>"}'`.
   - Does a message arrive within 30 s?
   - How faithfully does the agent keep the numbers?
   - What `phone` format does Telegram use?
4. **Broadcast.** Notice with no `phone`. Is it 202, and does it reach every recent conversation?
5. **Tool.** Register a webhook tool pointing at a webhook.site/ngrok URL. Ask "what's my exposure?". Capture the `context` JSON: `phone`, `userId`, attachments.
6. **Image.** Send a brokerage screenshot.
   - Does the tool call get `attachment_id` and a fetchable `context.attachments[id].url`?
   - What does `media.image: describe` output for the numbers?
7. **Schedule.** Create an Alert (SDK) or a Loop (`create_loop` with cron `*/2 * * * *`). Does it fire unprompted to a real conversation? How is someone made a subscriber?
8. **Harness.** Does the agent harness picker show "Maritime VM" or "External"? Point external push at a Maritime public URL and check that a turn round-trips.

**Maritime**
9. Deploy a FastAPI hello image with `--public --port 8000`.
   - Does `https://<id>.mtm.sh/health` answer?
   - Time a wake after `maritime sleep`.
10. Serve `GET /schedules` with `*/2 * * * *` and `tz`. Sleep the agent. Does `/chat` get `source:"scheduled"` on time? Check `maritime logs`.
11. **Background work after the response.** Return 202, then work for 90 s and write to `/data`. Does the VM stay awake (is the idle timer request-based?), or does it get snapshotted mid-task? Set `--idle 600` if needed.
12. **Outbound.** From inside the VM, `curl` Telegram `sendMessage` and the Keiki notice endpoint, to confirm egress and TLS.
13. **Fallback check.** Point the Telegram `setWebhook` at the public URL, send a photo, and confirm we get `photo[].file_id` and can `getFile`. Optionally compare with the Maritime project-channel route: does `/chat` receive any attachment info? **[UNVERIFIED]**

**Organizers**
14. Ask:
    - Is a reference integration, credits, or a pre-provisioned iMessage line available?
    - Must the demo use iMessage, or is Telegram acceptable?
