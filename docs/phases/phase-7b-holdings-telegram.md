# Phase 7B · Holdings on Telegram: send a screenshot, get your report

You are the **builder** for Phase 7B of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including live on Telegram.

**You work in your own clone.** Phase 8 (web dashboard and chat) runs in parallel in another clone.
- **You own** the Telegram wiring in `networth/bot/` (a photo handler, `/holdings`, `/link_broker`, the confirm and fix flow, `/stop`), message copy for those flows in the 3E message shape, `tests/test_bot_holdings*.py`, `evals/` additions, and `docs/phases/phase-7b-*`.
- **Never edit** `networth/engine/`, `networth/holdings/` (call its entry points, don't change them; if one is wrong, print `OWNER NEEDED: <what>` and say why), `networth/web/`, `site/` or `networth/keiki/`.
- **The repo is public.** Never commit a secret, user data, a real holdings screenshot, `.env` or `data/`. Use `git commit -- <paths>` only.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait.
1. `knowledge/PRODUCT.md` in full. "The line we never cross" holds more here than anywhere.
2. `docs/phases/phase-7-report.md` (the entry points and their contracts, including that `/stop` must call `snaptrade.forget_snaptrade` before saving the stopped profile) and `docs/phases/phase-3e-report.md` (the message shape, the HTML renderer, the voice rules, three languages, one footer).
3. `networth/holdings/__init__.py`, `networth/holdings/snaptrade.py`, `networth/bot/` (how `/range` was wired for Phase 6 is the pattern), and Telegram's docs for photos and documents: https://core.telegram.org/bots/api#photosize and https://core.telegram.org/bots/api#getfile. Look things up. Never invent a field.
4. `~/.claude/CLAUDE.md` is in force.

## Build

| What | Details |
|---|---|
| **Photo in** | A photo (or an image sent as a document) from an onboarded user goes to `holdings_from_photo`. The image bytes are fetched, passed on and dropped: never written to disk or a log. The user gets the confirm prompt in their language with buttons: "Looks right", "Fix a line", "Cancel". An image that doesn't look like holdings still goes to Explain this, as today; decide by what the reader returns, not by guessing. |
| **Confirm and fix** | "Looks right" calls `confirm_holdings` and sends the report. "Fix a line" accepts the fix format `fix_line` parses and shows the prompt again. An unconfirmed list never produces a report. |
| **`/holdings`** | Sends `holdings_message` for a confirmed list, with a button to the `/u/{token}/holdings` page, or the one-line "send a screenshot" prompt when there is none. A holdings question in chat ("how are my investments doing", "kya mera portfolio theek hai") routes to `holdings_answer`, which already declines advice. |
| **`/link_broker`** | For a USD user, sends `snaptrade_link` as a button. For an INR user, a kind line that broker linking is US-only for now and a screenshot works. With no SnapTrade keys on the server, a kind "not available yet" line, never an error. |
| **`/stop`** | Calls `snaptrade.forget_snaptrade` before saving the stopped profile, so the user is also deleted at SnapTrade. |
| **Copy** | Every new line in the 3E message shape, in English, Hindi and Hinglish, calm, no hype words, "Research, not advice" once per message. Add the new commands to `/help` and BotFather's command list text in the report. |
| `tests/` | No network: a photo turns into a confirm prompt, confirm gives a report, fix then confirm, cancel leaves nothing stored, an unconfirmed list gives no report, `/holdings` with and without a list, `/link_broker` for USD, INR and no keys, `/stop` calls forget and deletes holdings, the image is never written (assert no new file), every message passes the voice tests. |

## Not in this phase

Changes to `networth/holdings/`, any advice or ranking, paid SnapTrade tiers, web pages and the Phase 8 site, Keiki channels.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. Live on Telegram, the coordinator sends the fake Groww screenshot from `tests/fixtures/holdings/groww_fake.png`, gets a confirm prompt listing all 7 holdings, confirms, and gets the report with every number matching `holdings_lines` for the same list.
3. `/holdings` and the holdings page button work live. "What should I sell?" after a confirmed list gets the decline plus the factual report, in the user's language.
4. `/link_broker` behaves as specified for the coordinator's INR profile live, and for USD and no-keys in tests.
5. `/stop` deletes holdings and calls `forget_snaptrade` (test).
6. The image is never stored or logged (test), and nothing secret is committed.
7. `docs/phases/phase-7b-report.md` lists the flows, sample messages in all three languages, the BotFather command list, known gaps and deviations. A deploy is OWNER NEEDED: print the exact command.

## The gate and branch policy

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 7B READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
