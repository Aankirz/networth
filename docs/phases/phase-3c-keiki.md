# Phase 3C · Keiki as the reach and relationship layer

You are the **builder** for Phase 3C of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including live on each channel.

Phases 1, 1B, 2, 3A, 3B and 4 have passed or are passing review. Everything outside `networth/engine/` is yours to extend. **Never edit `networth/engine/`.** **The repo is public, so never commit a secret, a user's data or `.env`.** Stage only your own paths by name, never run `git add -A` or a bare `git commit`, and use `git commit -- <paths>`.

## The idea, in one paragraph

Keiki is the reach and relationship layer. Our server stays the truth layer. Every number still comes from the engine, and every word still passes `networth/guard.py`. Keiki adds:
- channels we don't have;
- memory of each person;
- standing per-user watches;
- traces that show our work.

Keiki connects through its **external harness**, so Keiki delivers our exact text. **Never use a Keiki-hosted model to write a user-facing message**, because that would bypass the guard. Telegram keeps working directly as it does today.

The demo line is: "Ask on any channel, get the same sourced numbers, and set your own watch. It stays quiet until history has something to say."

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc. Note "The line we never cross", rare alerts, and pull-only users.
2. `docs/phases/phase-3b-report.md`, `docs/phases/phase-3b-round2-gaps.md` and `docs/deploy.md`. Chat intents, the guard, alerts, schedules and the Maritime deploy are your starting point.
3. `docs/research/research-keiki-maritime.md` section 2 and 3. It's a starting map, not truth. Several items are marked UNVERIFIED.
4. Keiki's own docs, which are the source of truth. Read them in full: https://onkeiki.com/docs/external-harness.md, https://onkeiki.com/docs/agent-api.md, https://onkeiki.com/docs/cloud-agents.md, https://onkeiki.com/docs/harnesses.md, https://onkeiki.com/setup.md, plus whatever they link for channels (email / AgentMail), Loops, memory and traces. **Look everything up. Never invent an endpoint, field, scope, header or channel type.** Use `tinyfish fetch content get "<url>"` to read them.
5. `~/.claude/CLAUDE.md` is in force.

## Decisions already made

- **The org is on Keiki's Scale plan.** The owner has done this. `KEIKI_API_KEY` is in `.env`, and `GET /api/v1/developer/agents` returned `200 {"agents":[]}` in 3B. You may create the Keiki agent, deployment, channels, tools and loops through Keiki's developer API or MCP with that key. That's configuring our own org, not creating an account. Anything that needs the dashboard, a payment or a human login is OWNER NEEDED.
- **Channels in scope:** Telegram stays direct (don't move the existing bot), and **email** is added through Keiki. A Keiki-side Telegram channel on a **second** test bot is allowed only if email is blocked.
- **Out of scope:** WhatsApp (needs the owner's Meta credentials and a 24-hour window), iMessage, phone lines, SMS and any other paid add-on. Ask the owner before anything that costs money beyond the plan.
- **Live product models stay OpenAI** through `networth/llm.py`. Keiki carries our text and does not write it.
- **No scores, no ranks, no buy, sell or allocation advice, no F&O.** Same rules as 3B.

## Build

| What | Details |
|---|---|
| **Step 0 spike (30 minutes, timeboxed)** | Using the docs and the API with `KEIKI_API_KEY`, answer these 6 questions and write them in `docs/phases/phase-3c-spike.md`, with the exact request and response status (redact keys):<br>1. Which channel types can this org deploy?<br>2. Can an agent use `harness: external` (or whatever the docs call it) on the Scale plan?<br>3. Which external-harness mode works best on Maritime: push, relay or inbox? Note that our VM sleeps.<br>4. Do Loops (per-user scheduled checks) run with an external harness, and how is a loop created for one user?<br>5. Where per-user memory lives, and whether our server can read and write it.<br>6. How traces are reached, and whether a trace link can be shared.<br>Every later row adapts to these answers. If a capability is missing, use the fallback in its row and record the exact error. |
| **Keiki agent and harness** | Create one Keiki agent for Networth with the external harness pointed at our Maritime server. Add an endpoint (for example `POST /keiki/turn`) that verifies Keiki's signature exactly as documented (Ed25519 via JWKS, or HMAC; add a vetted library with `uv add` if needed), answers fast, runs the same chat pipeline as Telegram (intent, handler, `guard.py`), then sends our exact text with the documented message and complete calls. Reject unsigned or stale turns with 401. Replay of the same turn id must not answer twice. Keiki config such as the agent id and secrets goes in env vars with `maritime env set`, never in the repo. |
| **One identity across channels** | Map a Keiki user (`userId` or phone or email, per the docs) to our `Store` user. A person who has onboarded on Telegram can link their email with a short code (for example `/link` on Telegram gives a 6-digit code that they send by email, valid for 10 minutes and single use). After that, plan, language and exclusions apply on both channels. A brand-new email user gets a short text onboarding: goal, amount, investing day, language. |
| **Email channel** | Deploy Keiki's email channel. The investing-day brief can go by email to users who chose it, from the same composer and through the same guard, with a plain-text body and the Why links. The monthly cap and `send()` rules (stopped and paused users stay silent) apply per person, not per channel. Never send the same brief twice to one person on the same day across channels. |
| **"Watch this for me"** | A new chat intent `watch`, plus `/watch` and `/watches` on Telegram. A user names an event type or a topic ("tell me if RBI changes rates", "watch bank stress news", "watch Paras Defence"). It maps to an existing watcher event type, or to a named entity matched by the watcher's confirmed stories. It never maps to a price target or a buy/sell trigger. **Quiet by default:** nothing is sent until the watcher confirms a matching story. Then that user alone gets one message with the confirmed story, its source and, if the event type has history, the engine's history line and the Why link. Caps: at most 5 active watches per user and at most 4 watch messages per user per month, configured in config. Pull-only users may set watches, because a watch is an explicit request. Implement it with Keiki Loops if the spike says they work with our harness. Otherwise implement it on our own watcher and schedule, keyed by our user id, and record why. `/watches` lists them with a way to stop each one. |
| **Memory callbacks** | When a user asked what a term meant (an explain-this or jargon question) in the last 60 days, the next brief may add one line connecting it to this month, only if this month's confirmed stories or explain sources contain that term (for example "Last month you asked what OFS means. This month's Orbit Solar IPO has one."). Store the asked terms ourselves, keyed by user, or in Keiki memory if the spike shows our server can read it. The line passes the guard like everything else. |
| **Traces as proof** | Every Keiki turn we answer records, in our `data/llm_calls.jsonl` or a sibling log, the Keiki turn or trace id next to the intent, the guard verdict and the cost. If the spike shows a trace can be shared, add the trace link to the report for 3 sample turns. Phase 5 will reuse this. |
| **Maritime's new agent URL and Network card** | Maritime now gives each agent that serves a port its own URL, `https://<agent-id>.mtm.sh`. It's private by default, with share links, and a visit wakes the agent in about a second. Each agent also has a Network card that controls where it can connect out to (everything, nothing or an allowlist), enforced on Maritime's server. Look up both in Maritime's docs.<br>1. If the `mtm.sh` URL is a cleaner and faster target for the Keiki dispatch and the Telegram webhook than `api.maritime.sh/a/<id>`, use it and record why. It must be Public for Keiki and Telegram to reach it.<br>2. Set an outbound allowlist with exactly the hosts the product calls (OpenAI, the AI gateway, Telegram, Keiki, Exa, FRED, the price and news sources). Run a full watcher cycle and a chat turn to prove nothing broke. If only the dashboard can set it, raise OWNER NEEDED with the exact list. |
| **Deploy** | Follow `docs/deploy.md`. Update it with every Keiki step, env var name (never the value) and how to rotate the harness secret. A deploy is OWNER NEEDED: print the exact command and wait. Don't run it yourself. |
| **`tests/`** | No network: fake Keiki turns, fake model, fake clock. Signature valid, invalid and stale. Replay of a turn id. A turn runs the guard (a planted bad number is blocked). Linking: a code works once, expires and is per user. Watch: maps to an event type, rejects a price-target or buy request, is quiet with no confirmed story, sends once on a match, holds the caps, and `/watches` stops one. Memory: the callback line appears only when the term is in this month's sources. The cross-channel brief goes out once per person per day. |

## Not in this phase

WhatsApp, iMessage, SMS, phone lines, any paid add-on, Keiki-hosted models writing user text, holdings or broker linking, scores or ranks, evals and calibration (Phase 5), and changes to `networth/engine/`.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. `docs/phases/phase-3c-spike.md` answers the 6 Step 0 questions with redacted evidence.
3. A Keiki agent with the external harness exists, and its id is listed in the report. An unsigned or stale turn gets 401 from the deployed server, and a replayed turn is not answered twice.
4. Live, the coordinator emails the Keiki address with "What happened today?" and an IPO text, and gets the same sourced, guarded answers the Telegram bot gives. The report shows the turn ids.
5. Live, the coordinator links their Telegram user to email with the code flow, and `/brief` (owner only) delivers the brief by email once, with the numbers matching the engine.
6. Live, the coordinator sets "watch RBI rate changes" on Telegram, and `/watches` lists it. A test proves it fires once on a confirmed match, stays quiet otherwise, and holds both caps. A request like "tell me when HDFC hits 1800 so I can buy" is politely refused.
7. A test proves the memory callback line, and a sample brief with it is in the report.
8. The report shows 3 turns with their trace ids (and links if shareable), intent, guard verdict and cost.
9. `docs/phases/phase-3c-report.md` lists what was built, the spike answers, sample messages per channel, every Keiki resource created (ids, not secrets), the cost per turn, OWNER NEEDED items, known gaps and deviations. `docs/deploy.md` is updated.
10. Nothing secret is committed, and `data/` is not committed.

## The gate, branch policy and shared files

- **Start only after Phase 3B round 2 is pushed.** Run `git pull --rebase` first and confirm `git log` shows the 3B round-2 commits. If they aren't there yet, do Step 0 (docs and read-only API calls) and wait.
- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Messages to real people other than the owner are out. Test only with the owner's and coordinator's own Telegram and email.
- Finish with `PHASE 3C READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do (a deploy, a dashboard click, a payment, a login, an email address only the owner can receive at), print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
