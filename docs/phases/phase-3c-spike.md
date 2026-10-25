# Phase 3C · Step 0 spike: what Keiki can do for Networth

Written 2026-10-25. It answers the 6 Step 0 questions in `phase-3c-keiki.md`. The evidence is Keiki's own docs plus read-only calls with `KEIKI_API_KEY`. Keys are redacted. The Phase 3B builder still had unpushed work in this tree, so this spike made no write call to Keiki. Each answer that needs a write to confirm says which write, and that write is the first build step.

## Sources read

All fetched on 2026-10-25.
- https://onkeiki.com/docs/external-harness.md. The raw markdown came through `curl`, because the tinyfish text dropped the `<...>` placeholders in the signature formats.
- https://onkeiki.com/docs/harnesses.md
- https://onkeiki.com/docs/agent-api.md
- https://onkeiki.com/docs/cloud-agents.md
- https://onkeiki.com/docs/partner-deployments.md
- https://onkeiki.com/docs/mcp.md
- https://onkeiki.com/setup.md
- https://onkeiki.com/llms.txt
- https://onkeiki.com/llms-full.txt, which holds the capabilities, identity and evals pages.
- https://onkeiki.com/openapi.json. It only describes the OpenAI and Anthropic gateway, not the developer API.

The docs have no separate page for Loops, memory or AgentMail. What exists is in the capabilities section of `llms-full.txt`, the managed-features section of `cloud-agents.md`, and the channel table in `partner-deployments.md`.

## Live calls

Each call used `Authorization: Bearer sk_live_REDACTED` against `https://onkeiki.com`.

| Request | Status | Response (trimmed) |
| --- | --- | --- |
| `GET /api/v1/developer/agents` | 200 | `{"agents":[]}` |
| `GET /api/v1/developer/config` | 200 | `{"agent_id":null,"name":"networth-v1","model":"google/gemini-3.8-flash","max_steps":10,"history_limit":16,"features":{},"execution_mode":"platform","webhook_url":null,"harness":"flue","harness_config":null,...}` |
| `GET /api/v1/developer/tools` | 200 | `{"tools":[]}` |
| `GET /api/v1/traces?limit=3` | 200 | `{"traces":[]}` |
| `GET /api/v1/developer/trace-exporters` | 200 | `{"exporters":[]}` |
| `GET /api/v1/developer/usage` | 200 | `{"turns":0,"messages":0,"tokens_in":0,"tokens_out":0,"tool_calls":0}` |
| `GET /api/v1/developer/deployments/networth-spike-probe` | 404 | `{"error":"Deployment not found"}` |
| `GET /api/v1/keys` | 200 | Key `networth-v1` (prefix `sk_live_RhuK...`) has scopes `["*"]` and is org-wide (`agentId: null`). The older `Default` key is revoked. |
| `GET /api/v1/billing`, `GET /api/v1/orgs` | 404 | `No API operation matches ...`. The API has no plan readback, so the Scale plan is taken from the owner. |
| `GET /.well-known/keiki-turn-keys.json` | 200 | One key: `{"kty":"OKP","crv":"Ed25519","kid":"DN6QA6pKiv1PfnCm","alg":"EdDSA",...}` |
| `POST /mcp` `initialize`, then `tools/call list_channel_types` | 401 | `{"error":"invalid_token","error_description":"A bearer token for this deployment is required."}` plus `www-authenticate: Bearer resource_metadata=".../oauth-protected-resource", scope="mcp"` |

The org is empty: no agents, tools, traces or usage. The key is org-wide with `*` scope, so it can create deployments and change agent config. The MCP server takes only an OAuth token from a browser login, not the API key, so every MCP-only tool is out of reach without the owner.

## 1. Which channel types can this org deploy?

**Answer.** The documented deployment channel types are `imessage`, `telegram`, `whatsapp`, `slack`, `agentmail` and `api`. Email is `agentmail`.

The `POST /api/v1/developer/deployments` channel table (partner-deployments.md) gives the fields:

| `type` | Fields |
| --- | --- |
| `agentmail` | `region`, `mode` (`create` or `existing`), optional `inbox_id` (required when `mode` is `existing`), `username`, `domain` |
| `telegram` | `bot_token` |
| `api` | optional `passthrough` |
| `imessage` | none. It provisions a paid line, which is out of scope. |
| `whatsapp`, `slack` | Out of scope. |

SMS is not a deployment channel ("the person buys and attaches the line on the dashboard's Channels page", setup.md). Phone calls, SMS/RCS and A2A are "not live yet (early access)" (cloud-agents.md).

**Not confirmed.** Whether `agentmail` connects for this org, and which `region` and `domain` values it accepts. `list_channel_types` would say, but it is MCP-only and returned 401 with the API key. The first build write settles it. It is a deployment POST with `channels: [{"type":"agentmail","mode":"create",...}]`. Each channel reports `connected`, `needs_payment`, `error` or `skipped`, and a channel failure "does not undo the agent or the other channels". If the result is `needs_payment` or `error`, the brief's fallback applies: a Keiki-side `telegram` channel on a second test bot.

## 2. Can an agent use the external harness on this plan?

**Answer.** The config field exists for this org, and the docs name no plan gate. Use is not confirmed until the first write.

- `GET /api/v1/developer/config` returns `"harness":"flue","harness_config":null,"execution_mode":"platform"`. The field is live on this org's config object.
- external-harness.md gives the body: `{"harness":"external","harness_config":{"mode":"push","dispatchUrl":"https://.../keiki/turn","timeoutMs":600000}}`. `timeoutMs` goes up to ten minutes.
- The deployments API only accepts `harness` values `flue` or `hermes` in the inline agent spec (partner-deployments.md). So the agent gets created with a deployment POST, and the harness is switched afterwards with `PATCH /api/v1/developer/config` with `agent_id` in the body. cloud-agents.md says "A `PATCH` only changes the fields it sends" and that an org-wide key names the agent with `agent_id`.
- No doc ties the external harness to a plan. The one plan gate documented is `402 plan_required` when a sandbox org asks for channels.

**First write to confirm.** First a deployment POST with `external_ref: "networth"` and no channels. Then `PATCH /api/v1/developer/config` with the external harness. Then `GET /api/v1/developer/config?agent_id=...` to read it back. A rejection gets its exact status and body recorded in the report.

## 3. Push, relay or inbox on Maritime, given the VM sleeps?

**Answer.** Push.

| Mode | How it works (external-harness.md) | Fit with a sleeping Maritime VM |
| --- | --- | --- |
| Push | Keiki POSTs the signed turn to `dispatchUrl`, and we return 2xx at once. "Push turns are synchronous: if the endpoint is down, the turn fails rather than being queued." | Good. An HTTPS request wakes our VM in about a second, the same way Telegram's webhook does today (`docs/deploy.md`). We already answer `/chat` fast and do the work in a background thread. |
| Relay | "A connected relay ... claims work from `GET /api/v1/harness/turns/next`" and forwards it to the app. | Needs a relay process that never sleeps. We don't have one, and it adds a hop. Relay also takes no mid-turn arrivals. |
| Inbox | Our server long-polls `GET /api/v1/harness/inbox/next?wait=25`. "Nothing is sent to contacts while the agent is offline", and test or steer turns fail with `inbox_offline` without a recent poll. | Bad. Polling keeps the VM awake forever, and a sleeping VM never polls. |

Constraints on push that the build has to meet:
- **URL.** Keiki "will not push turns to private networks, redirects, URLs with credentials, or plain HTTP". `docs/deploy.md` says `https://<agent-id>.mtm.sh` served a mismatched certificate on 2026-10-25, so `dispatchUrl` should be `https://api.maritime.sh/a/<agent-id>/keiki/turn`, the same base as `PUBLIC_URL`. It must answer without a redirect.
- **Signature.** Verify `Keiki-Signature-Ed25519: t=<unix-seconds>,kid=<key id>,v1=<base64url Ed25519 signature over "<unix-seconds>.<turn-token>.<raw-body>">` against the JWKS above. That needs no per-agent secret: "An agent with no signing secret is then pushed with only this header". The HMAC form, `Keiki-Signature: t=...,v1=<hex HMAC-SHA256(secret, "<unix-seconds>.<raw-body>")>`, needs `POST /api/v1/developer/agents/:agentId/harness/signing-secret`, whose `whsec_...` value is shown once. Use Ed25519 as the primary check, and keep HMAC optional behind an env var so the secret can be rotated. The docs set no staleness window for turns. The identity webhook page says "reject anything older than five minutes", and we use that window here.
- **Request types on `dispatchUrl`.** `keiki.turn`, `keiki.turn.arrival`, `keiki.turn.cancelled` and `keiki.reaction`. A cancellation and a reaction carry no turn token, so their Ed25519 signature is over an empty token.
- **Replies.** Send with `POST {turnUrl}/messages` `{"text": ..., "idempotencyKey": ...}` and `Authorization: Bearer <Keiki-Turn-Token>`, then `POST {turnUrl}/complete` `{"status":"completed"}`. "Keiki never sends twice under one message idempotency key", and a repeated `/complete` is "acknowledged as a duplicate". Keying on the turn id gives replay safety on both sides.
- **Held-back turns.** Playground and steered turns set `heldBack: true`. Their messages are captured and not delivered, so they are safe for testing.

## 4. Do Loops run with an external harness, and how is a loop made for one user?

**Answer.** Partly, and only from inside a turn. Watches go on our own watcher.

- Loops is a capability toggle that gives the agent the tools `create_loop`, `list_loops`, `update_loop`, `delete_loop`, `run_loop` and `diff_since_last_run`. "A loop runs its prompt on a cron or interval schedule, and quiet loops send nothing when there is nothing to report" (llms-full.txt, capabilities).
- A loop is made by the agent calling `create_loop` during a conversation. No developer REST endpoint creates a loop for a given user. The capability manifest's `loops` presets (`name`, `prompt`, `scheduleType` of `once`, `cron` or `interval`, `scheduleExpression`) are agent-wide, not per user.
- With the external harness, a loop firing would reach us as a turn. The turn payload carries a `quietLoop` flag, and trace metadata names "turns the platform starts itself (loops, notices)". To create one, our app would call `create_loop` through the turn's `keiki.mcpUrl` (`/api/v1/harness/mcp`). The docs never say that capability tools are served there for an external agent. That is unverified.

**Decision.** Build `watch` on our own watcher and schedule, keyed by our user id. Four reasons:
1. A watch has to work on Telegram, which stays direct and never passes through Keiki. Keiki loops cannot see those users.
2. Our watcher already confirms stories every 30 minutes in market hours. A Keiki loop would only wake our server to run the same check, so it adds a hop and does no work.
3. No REST endpoint creates a per-user loop. Creating one from our server depends on the unverified harness MCP path.
4. The caps (5 watches and 4 messages per user per month) and the quiet-by-default rule belong next to the alert caps we already enforce.

## 5. Where does per-user memory live, and can our server read and write it?

**Answer.** Keiki's memory feature has no documented read or write API. We store asked terms ourselves.

- Memory is "no tools, purely behavioural. The agent extracts durable facts and preferences about each user from conversations and recalls them automatically in later turns" (llms-full.txt). It is configured as `memory: { enabled, provider: 'supermemory', autoRetrieve, categories }` (cloud-agents.md). No endpoint reads or writes it.
- It runs inside Keiki's own loop. With the external harness our app owns the loop, so we expect it does not run for our agent. That is an inference, not tested.
- Two stores are documented. `ctx.storage` is a JSON row store shared by all of an agent's conversations, and our server can reach it with `PUT` and `GET /api/v1/developer/agents/:agentId/storage/:entity`. `ctx.userState` is per end user, but only authored tools can reach it, and it has no REST route.

**Decision.** Keep asked terms in our own `Store`, keyed by our user id, with a timestamp for the 60-day window. Telegram users never touch Keiki, and the brief composer already reads `Store`. Keiki agent storage would add a network read to every brief for no gain.

## 6. How are traces reached, and can a trace link be shared?

**Answer.** Our server reads them through the API. No public share link is documented.

- `GET /api/v1/traces?limit=20` lists traces, `GET /api/v1/traces?status=error` lists failures, and `GET /api/v1/traces/:traceId` returns `{ trace, spans }`. Keiki keeps them 14 days by default. The list call answered 200 with `{"traces":[]}` on this org.
- `trace` carries `traceId`, `agentId`, `phone` (the conversation identity), `startedAt`, `endedAt`, `durationMs`, `model`, `tokensIn`, `tokensOut`, `totalSteps`, `costUsd`, `status` and `metadata`. `metadata` holds `harness`, `channel` and the inbound text (partner-deployments.md, Turn traces).
- With an external harness, the cost of our OpenAI calls is not in Keiki's `costUsd`. "Model tokens your own provider serves are between you and that provider" (harnesses.md). Our own `data/llm_calls.jsonl` stays the cost source, and Keiki's trace id is the join key.
- Sharing. Traces are in the org dashboard behind login. The only shareable URL the docs mention is an eval run (`/improve/runs/:id`, "has a URL that survives a reload and can be shared"), and that is also an org dashboard page. The docs give no public trace link and no dashboard trace URL format, so the report will list trace ids and not invent links. Trace exporters (Braintrust, Axiom, OpenTelemetry or a custom endpoint, configured in Settings) are the way to get traces into a system we can share. That is Phase 5 work.

**Mapping a turn to its trace.** The trace id is not in the documented `keiki.turn` field list. The Ed25519 turn credential binds "the agent and trace ID", so a turn and its trace are linked. The first live turn will show whether `turnId` equals `traceId` or the payload carries a separate field. Until then, log `turnId` and look up the trace with `GET /api/v1/traces?limit=...` by `metadata` and time.

## What changes in the build

| Brief row | Change from the spike |
| --- | --- |
| Keiki agent and harness | Create the agent with `POST /api/v1/developer/deployments` (`external_ref: "networth"`). Switch it to `harness: external`, `mode: push` with `PATCH /api/v1/developer/config`. Verify Ed25519 via JWKS. The HMAC secret is optional. |
| Email channel | Add `agentmail` to the same deployment. If it returns `needs_payment` or `error`, record that and fall back to a Keiki `telegram` channel on a second test bot. |
| One identity | The Keiki contact identity is the turn's `conversationId` (`phone` in traces). For email we expect the sender address, but the first live email turn confirms it. Map it to our `Store` user with the `/link` code flow. |
| Watch | Our watcher and schedule, keyed by our user id (Q4). |
| Memory callbacks | Our `Store` (Q5). |
| Traces | Log `turnId` and the Keiki trace id next to intent, guard verdict and cost. Report ids only, no links (Q6). |

## OWNER NEEDED candidates

None blocks the build yet. Two may come up:
- If `agentmail` needs an exact `region` or `domain` value that a failed deployment POST doesn't name, the owner can run `claude mcp add --transport http keiki https://onkeiki.com/mcp`, sign in once, and call `list_channel_types`.
- If an `agentmail` inbox needs a dashboard step or payment, that is the owner's call.

## After the gate: the first writes

Run on 2026-10-25 once the coordinator approved the build.

| Request | Status | Result |
| --- | --- | --- |
| `POST /api/v1/developer/deployments` `{"external_ref":"networth","agent":{"name":"Networth",...}}` with no channels | 201 | Agent `8d5b1d0c-2f0d-42a2-ad0c-e78cabf929c2` created. |
| `PATCH /api/v1/developer/config` `{"agent_id":...,"harness":"external","harness_config":{"mode":"push","dispatchUrl":"https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/keiki/turn","timeoutMs":600000}}` | 200 | `{"status":"updated"}`. A read-back shows `"harness":"external"` with that config. Q2 is confirmed on this plan. |
| `POST /api/v1/developer/deployments` with `{"type":"agentmail","mode":"create","username":"networth"}` | 400 | `{"error":"region is required"}` |
| The same with `"region":"us"` | 200 | `agentmail` `connected`, inbox `networth@agentmail.to`. Q1 is confirmed for email. |

The harness was switched to external before the email channel was added. No Keiki-hosted model ever had a channel to answer on.
