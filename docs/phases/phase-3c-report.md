# Phase 3C report: Networth on email and Slack through Keiki

Written 2026-10-25 by the Phase 3C builder. The brief is `docs/phases/phase-3c-keiki.md` and the spike is `docs/phases/phase-3c-spike.md`.

## Who it is for

A Networth user can now reach the same product by email, and, once the owner installs a Slack app, by Slack DM. They ask "What happened today?" or paste an IPO text and get the same sourced, guarded answer the Telegram bot gives. They can link their email to their Telegram profile with a six-digit code, so their plan and language follow them. They can ask Networth to watch a topic, and a confirmed story about it brings one message. A brief can bring back a term they asked about earlier.

Keiki only carries messages. Every user-facing word comes from our own pipeline (intent, handler, guard). No Keiki-hosted model ever answered: the harness was switched to `external` before the email channel existed.

## What was built

- `POST /keiki/turn` takes Keiki's signed turns. It checks the Ed25519 signature against Keiki's JWKS (optional HMAC too), rejects stale or foreign-agent turns, answers each turn id once, replies 202, and runs the turn in the background (`networth/keiki/verify.py`, `wire.py`, `turn.py`).
- The turn runs the Telegram pipeline unchanged through `KeikiTurnBot`. The reply goes back through Keiki's turn API as plain text (`render.py`). Email and Slack share this path.
- A new email or Slack contact gets the short four-question setup by text (`onboard.py`). A first message that asks something is answered first, then the setup starts.
- `/link` on Telegram issues a single-use code that lasts 10 minutes. Sending it by email or Slack binds that contact to the Telegram user. `/sendto email|telegram` picks where briefs and alerts go.
- The proactive outbox (`mail.py`) queues briefs, alerts and watch messages for email and asks Keiki for a notice turn to send them.
- Watches (`networth/watch.py`, `networth/bot/watches.py`): `/watch <topic>`, `/watches`, `/unwatch N`, a WATCH chat intent, and refusals for price or trade watches. A cap of 5 active and 4 messages a month applies.
- Memory (`networth/memory.py`): asked glossary terms are kept 60 days. A brief adds one line when this month's news brings one back.
- `data/keiki_turns.jsonl`: one line per turn.

### Fixes from the coordinator's live review (this round)

1. **The turn log leaked the email.** Keiki sends `channel` as an object that also holds the sender address and the inbound text. The log wrote it whole. Now only the channel's `type` is kept (`wire.py` `_channel`). The test fixture now sends the object as Keiki does, and `test_each_turn_logs_its_ids_intent_guard_and_cost_but_no_text` asserts that neither the address nor the text reaches the log. The one live line already on the VM needs a one-off scrub (OWNER NEEDED 2).
2. **`trace_id` was null.** Keiki's payload has no `traceId`, and Keiki's trace id is the turn id (trace `3084530f5c9942b506205342be74b73b` is the turn id of the first email). `trace_id` now falls back to the turn id. Test: `test_a_turn_without_a_trace_id_uses_the_turn_id_as_keiki_does`.
3. **`kind=onboarding` on an answered first email.** The behaviour is intended and is deviation 2 below. A first message that asks something is answered, then the short setup starts, so a stranger's question is never deferred. The brief's text onboarding still happens in the same turn. The log now calls that turn `welcome`, keeps `onboarding` for answers to a setup question, and records the answer's intent and guard. Test: `test_a_first_email_that_asks_something_is_answered_then_set_up`.
4. **Slack (new scope, owner approved).** See the Slack section below.
5. **Build 125ec77 read the wrong key.** The live channel object names its type `channel` (`{'channel': 'agentmail', 'inboxId': …, 'inboundText': …}`), not `type`, so 125ec77 logs an empty channel and would not recognise Slack. The parser now reads `channel` first and `type` as a fallback, and the fixtures mirror the live shape. It needs another redeploy.

## Spike answers (from `phase-3c-spike.md`)

1. Channel types: `imessage`, `telegram`, `whatsapp`, `slack`, `agentmail`, `api`. Email is `agentmail`.
2. The external harness is set with `PATCH /api/v1/developer/config`.
3. Push mode. Keiki POSTs each turn to our `dispatchUrl`.
4. Loops are created only inside a turn, so watches run on our own watcher.
5. Keiki memory has no API, so asked terms live in our Store.
6. Traces come from `GET /api/v1/traces[/:id]` and have no public share link. Keiki's `costUsd` excludes our OpenAI calls, so cost comes from our own call log.

## Keiki resources (ids, not secrets)

| Resource | Id |
| --- | --- |
| Agent `Networth`, deployment `external_ref: networth` | `8d5b1d0c-2f0d-42a2-ad0c-e78cabf929c2` |
| Harness | `external`, mode `push`, `dispatchUrl https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/keiki/turn`, `timeoutMs 600000`. Re-read live today. |
| Email channel | `agentmail`, region `us`, `networth@agentmail.to`, id `3ef1287d-8979-41c4-b838-e468d017e95f`, `connected`, routing `active` |
| Slack channel | Not created yet. `POST /api/v1/developer/deployments` with `{"type":"slack"}` answers 400 `{"error":"bot_token is required"}`. It needs the owner's Slack app. |
| API key | `networth-v1`, org-wide, scope `*` (value only in `.env`) |
| Maritime agent | `eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea` |

## Live checks

- Deployed `/keiki/turn`: unsigned gets 401 `{"error":"unsigned"}`. A signature an hour old gets 401 `{"error":"stale"}`. A fresh time with Keiki's real `kid` and a random signature gets 401 `{"error":"bad_signature"}`, which also shows the VM fetched Keiki's keys. The coordinator confirmed the unsigned and malformed 401s on their own.
- Replay. A replayed turn can't be forged live, because only Keiki can sign. `test_a_replayed_turn_is_answered_once` and the store's `claim_turn` cover it, and Keiki's traces show one answer per turn.
- First live email. The owner emailed `networth@agentmail.to` at 13:30 IST with "What happened today?" and got the guarded answer at 13:31.

## Turns (Done-when 8)

Keiki's trace id is our turn id. Traces have no share link (spike answer 6), so none is given. Keiki's `costUsd` is null on the external harness, so the cost is ours, from `llm_calls.jsonl` during the turn.

| # | Turn and trace id | Channel | Kind | Intent | Guard | Our cost | Keiki status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `3084530f5c9942b506205342be74b73b` | agentmail | `onboarding` in the old log, `welcome` from this build on | what_happened_today | guarded answer (verdict in the VM log line) | in the VM log line | completed, 7.6 s, tokensIn 0 |
| 2 | pending | agentmail | | | | | |
| 3 | pending | agentmail or slack | | | | | |

`tokensIn 0` on turn 1 is the proof that no Keiki model ran. Rows 2 and 3 need two more owner emails after the redeploy (OWNER NEEDED 1, then 3). The fixed log then carries the trace id, channel type, kind, intent, guard and cost on each line.

## Cost per turn

Keiki bills turns on the org's plan and reports no model cost for an external harness (`costUsd` null, `tokensIn 0`). Our cost per turn is the sum of our own model and search calls during the turn, written to `cost_usd` in each log line. A template answer such as "What happened today?" costs about $0.004 in the test fixture's call log. The live figure is in the VM log lines for turns 1 to 3.

## Sample messages per channel

Email and Slack get the same plain text. Buttons become a "Reply with one of" line, and links become their own lines.

- Email or Slack, first message: "Hi, I'm Networth. I read the market news every day so you don't have to, and I can write to you on the day you invest. Four short questions to set you up. What's this money for?"
- Email or Slack, after a `/link` code: "Linked. Your plan, language and what you left out now apply here too. Briefs and alerts stay on Telegram until you reply /sendto email."
- Telegram `/link`: "Your code is NNNNNN. Email it to networth@agentmail.to within 10 minutes. It works once. …"
- Telegram `/watch RBI rate changes`: "Watching RBI rate changes. I'll stay quiet until the watcher confirms a story about it. Type /watches to see or stop your watches."
- Any channel, "tell me when HDFC hits 1800 so I can buy": "I don't watch prices or tell anyone when to trade. I can tell you when a confirmed story about HDFC appears. Try: watch HDFC."

## Memory sample (Done-when 7)

The brief below was built from a copy of the local data with templates only. The asked term is "Inflation". Test: `test_the_line_quotes_a_title_that_holds_the_term` and the memory tests.

```
Investing day, Oct 25. ₹50,000 ready.

This month's news, in one line. Tariff move on Oct 23; Bank stress on Oct 22; Pandemic scare on Oct 20.

Where history leans after months like this:
⚪ Indian banks (Nifty Bank) beat the Nifty 50 in 6 of 9 past bank stress episodes (normal: 59%).
🔴 Indian IT (Nifty IT) beat the Nifty 50 in 3 of 9 past bank stress episodes (normal: 52%).
🔴 US banks and finance (XLF) beat the S&P 500 in 4 of 11 past bank stress episodes (normal: 48%).
🟢 US tech (XLK) beat the S&P 500 in 8 of 11 past bank stress episodes (normal: 57%).

Your plan. You chose Balanced. 20% safety, 70% core, 10% growth. History's counts are context. The plan is always your choice.

Earlier you asked what Inflation means. It comes up in this month's news: The Fed Can Pause, But Inflation Won't | The Daily Economy.

Show the scoreboard: https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/scoreboard/bank_stress
Why?: https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/why/bank_stress/^NSEBANK
```

## Slack

Slack runs on the same agent, the same external harness and the same `/keiki/turn` route. A Slack DM or mention becomes a signed turn, runs the same intent, handler and guard, and gets the same plain text as email.

- **Identity.** Keiki's Slack conversation is a thread, so one person has many. The contact is the author, `slack:<teamId>:<userId>`, read from the turn's channel object. Test: `test_a_slack_author_is_one_contact_across_threads` and `test_a_slack_dm_runs_the_same_pipeline_and_threads_share_one_profile`. The key names come from Keiki's trace docs (`metadata.slack` and its flat `teamId`, `userId`), not from a live Slack turn. The first payload after a boot now logs the channel's keys, never values, so the first Slack turn confirms them. If they differ, the fallback is one contact per thread, which still answers correctly.
- **Delivery.** Slack only answers. Briefs, alerts and watch messages never go to Slack. `Store.contact_for` returns only email contacts, so the outbox never mails a Slack id. Test: `test_a_slack_contact_is_never_mailed`.
- **Setup.** The owner must create and install a Slack app (OWNER NEEDED 4). After that, the channel is one API call or the dashboard form. `docs/deploy.md` has both ways.

## OWNER NEEDED

1. **Redeploy** `main` so the log fix, `welcome` kind, trace id, memory headline fix and Slack routing go live:
   ```bash
   maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json
   ```
2. **Scrub the live log lines** that hold the email text and address. The first line stores `channel` as a Python repr string, so the script parses it (`ast.literal_eval`, then a regex for `channel` or `type`) down to the type word, fills `trace_id`, and keeps the turn's other fields. A line it cannot parse gets `unknown`, never the text. Tested here on a repr string, a truncated repr, a dict, a plain word and an empty string. Run after the redeploy:
   ```bash
   npx --no-install maritime exec networth --json --body-json '{"command": "echo aW1wb3J0IGFzdCwganNvbiwgcmUKcCA9ICIvZGF0YS9rZWlraV90dXJucy5qc29ubCIKcm93cyA9IFtqc29uLmxvYWRzKGxpbmUpIGZvciBsaW5lIGluIG9wZW4ocCldCmRlZiBraW5kKGMpOgogICAgaWYgaXNpbnN0YW5jZShjLCBzdHIpIGFuZCByZS5mdWxsbWF0Y2gociJbYS16X10rIiwgYyk6CiAgICAgICAgcmV0dXJuIGMKICAgIGlmIGlzaW5zdGFuY2UoYywgc3RyKToKICAgICAgICB0cnk6CiAgICAgICAgICAgIGMgPSBhc3QubGl0ZXJhbF9ldmFsKGMpCiAgICAgICAgZXhjZXB0IChWYWx1ZUVycm9yLCBTeW50YXhFcnJvcik6CiAgICAgICAgICAgIG0gPSByZS5zZWFyY2gociJbJ1wiXSg/OmNoYW5uZWx8dHlwZSlbJ1wiXVxzKjpccypbJ1wiXShbYS16X10rKVsnXCJdIiwgYykKICAgICAgICAgICAgcmV0dXJuIG0uZ3JvdXAoMSkgaWYgbSBlbHNlICJ1bmtub3duIgogICAgaWYgaXNpbnN0YW5jZShjLCBkaWN0KToKICAgICAgICByZXR1cm4gc3RyKGMuZ2V0KCJjaGFubmVsIikgb3IgYy5nZXQoInR5cGUiKSBvciAidW5rbm93biIpCiAgICByZXR1cm4gInVua25vd24iCm91dCA9IFt7KipyLCAiY2hhbm5lbCI6IGtpbmQoci5nZXQoImNoYW5uZWwiKSksICJ0cmFjZV9pZCI6IHIuZ2V0KCJ0cmFjZV9pZCIpIG9yIHJbInR1cm5faWQiXX0gZm9yIHIgaW4gcm93c10Kb3BlbihwLCAidyIpLndyaXRlKCIiLmpvaW4oanNvbi5kdW1wcyhyKSArICJcbiIgZm9yIHIgaW4gb3V0KSkKcHJpbnQobGVuKG91dCksICJyb3dzLCBjaGFubmVscyIsIHNvcnRlZCh7clsiY2hhbm5lbCJdIGZvciByIGluIG91dH0pKQo= | base64 -d | /app/.venv/bin/python"}'
   ```
   Expect `N rows, channels ['agentmail']`. A turn logged by build 125ec77 shows `unknown` (see the next fix).
3. **Two more email turns** for the table. From the owner's address to `networth@agentmail.to`: first an IPO text, then `/brief`. Then `npx --no-install maritime exec networth --json --body-json '{"command":"cat /data/keiki_turns.jsonl"}'` and paste the lines. Each line is safe to paste once the scrub has run.
4. **Slack app.** Keiki dashboard, agent Networth, Channels, Slack, then create the app from Keiki's manifest, install it to the workspace, and paste the `xoxb-` bot token and the signing secret into Keiki. The fallback path through the developer API, with `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in the local `.env`, is in `docs/deploy.md`. Then DM the app "What happened today?" and compare it with Telegram.

## Known gaps

- **Notice delivery is unproven live.** Proactive email waits in the outbox until Keiki runs a notice turn. If Keiki never dispatches it, the mail goes out on the contact's next email.
- **The HMAC secret format is unverified.** Ed25519 verifies every turn, and HMAC is optional.
- **Slack is untested live.** The author key names come from Keiki's docs, and the scopes in deploy path B are a guess unless Keiki's manifest is used.
- **No proactive Slack.** A Slack-only user gets answers and `/brief` on demand, but no scheduled brief until they link Telegram or email. Their setup still says "I'll write on the …", which is only true after linking.
- **Replay is proven by test only** (see Live checks).
- **No rate limit on link-code guessing.** A code is 6 digits, lasts 10 minutes and works once, and only messages of 40 characters or fewer are read as codes.
- **Cost is attributed by time window.** Turns run one at a time under a process-wide lock, so the window is exact unless a scheduled job runs during a turn.
- **Entity watches match the whole phrase,** and a story's first-seen time comes from its publish time.
- **The deployment runs `c80dbbe`.** This round's fixes and `ac158d8` need OWNER NEEDED 1.

## Deviations from the brief

1. Email-native user ids are `kk:<sha256(address)[:16]>`, so no log line names an address. A Slack contact hashes the same way.
2. A first message that asks something is answered before the short setup. The brief says a new email user gets text onboarding. They still do, in the same turn.
3. The memory line quotes the shortest headline that holds the term, capped at 140 characters.
4. Pushes authenticate as `Aankirz` per command (`git -c credential.helper=…`), because the default credential gets 403. Git config is unchanged.
5. Each rebase kept both sides of `.claude/CHANGELOG.md` conflicts.
6. Slack is new scope, approved by the owner through the coordinator. The brief listed it as out of scope.
