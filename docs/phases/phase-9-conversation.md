# Phase 9 · A bot you can talk to, and one tap to your dashboard

You are the **builder** for Phase 9 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including live on Telegram and on the web dashboard.

**You work in your own clone.** No other builder is running.
- **You own** `networth/chat/` (the conversation layer), the conversation wiring in `networth/bot/`, a conversation table in `networth/app/store.py` (add, don't rewrite), `networth/app/settings.py` for one new setting, `tests/test_conversation*.py`, `tests/test_dashboard_link*.py`, `evals/` additions, and `docs/phases/phase-9-*`.
- **Never edit** `networth/engine/`, `networth/holdings/`, `site/` or `networth/keiki/` transport code. Keiki and the web reach the chat through `respond_traced`, so they gain the conversation without edits there. If they don't, print `OWNER NEEDED: <what> - <why>`.
- **The repo is public.** Never commit a secret, user data, `.env` or `data/`. Use `git commit -- <paths>` only.

## What the owner wants, in their words

"Our bot should be conversational fully, and also it should be easily navigable to our web dashboard link."

Today each message is answered on its own. Anything outside the fixed intents gets the help line. Live example: "Should I apply for the upcoming LIC IPO?" got "I can tell you what happened today…" on Telegram and the web.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait.
1. `knowledge/PRODUCT.md` in full. "The line we never cross" holds in every reply: no scores, ranks, buy, sell, allocation advice or F&O, and no number the server didn't compute or a source didn't state.
2. `networth/chat/__init__.py` (`classify`, `respond_traced`, `HANDLERS`), `networth/chat/answer.py` (`deliver_traced`, the guard), `networth/chat/today.py` (the help line and `page_link`), `networth/app/llm.py` (roles, cost caps), `docs/phases/phase-3e-report.md` (message shape and voice), `docs/phases/phase-8-report.md` (the web chat calls the same pipeline), and `docs/phases/phase-7b-report.md` (the link-token fix: sign the stored token, rotate only on `/stop`).
3. Telegram's docs, which are the source of truth: https://core.telegram.org/bots/api#setchatmenubutton, https://core.telegram.org/bots/api#menubuttonwebapp, https://core.telegram.org/bots/webapps and https://core.telegram.org/bots/api#setmycommands. Look things up with `tinyfish fetch content get "<url>"`. Never invent a field or method.
4. `~/.claude/CLAUDE.md` is in force.

## Build

| What | Details |
|---|---|
| **Data shape first** | Name the conversation shape before code: a per-user rolling window of turns (role, text, intent, at), the size cap and the age cap. Write it in `docs/phases/phase-9-design.md` with the choices and why. |
| **Memory of the conversation** | Keep the last few turns per user (cap by count and by age, e.g. 8 turns and 24 hours; pick and justify). Stored only in that user's rows. Deleted on `/stop` with the rest of `FORGOTTEN_ON_STOP`. The demo user's turns never mix with a real user's. Never written to any log; the turn logs keep trace id, intent and verdict only, as today. |
| **Follow-ups work** | "why?", "and the US?", "explain that simpler", "in Hindi please", "what about my plan then?" resolve against the last turn. A follow-up to a news answer stays sourced to the same confirmed stories. |
| **Open questions get real answers** | Replace the help-line fallback with a conversational answer for anything investing, money or market related: concepts (IPO, OFS, SIP, expense ratio, repo rate), how a thing works, what a term in a document means, what to look at before deciding. An IPO question explains how IPOs work, what the red-herring prospectus is, what to read in it, and the risks, and offers to explain a specific IPO page if sent one. It never says apply, skip, buy or sell. |
| **Small talk and off-topic** | Greetings, thanks and "who are you" get a short warm reply. Clearly off-topic requests (code, recipes, homework) get one kind line that Networth is for money questions, with a nudge back. No lecture. |
| **The guard on every word** | Every conversational answer goes through `guard.check` exactly as today. A planted advice phrase or an invented number is blocked and replaced by the template fallback in the user's language. Personal "should I" questions get the decline plus the useful facts, in three languages. |
| **Cost and abuse** | Reuse the per-user hourly cap and the LLM cost caps. Long histories are truncated, never sent whole. A message that tries to override instructions ("ignore your rules", mixed-script jailbreaks) is answered as a normal message and still passes the guard. |
| **One tap to the dashboard** | The dashboard is the Vercel site, `https://networth-eight-pied.vercel.app/u/<signed token>`. Add a setting `NETWORTH_SITE_URL` (unset means links fall back to the server's own `/u` page, as today). Every page link the bot builds uses the site when set. Give each onboarded user a persistent way in: set a per-chat menu button with `setChatMenuButton` (a web_app button opening their signed dashboard link, or a plain commands menu if web_app is not allowed for this URL; check the docs and decide by what Telegram allows). Add `/dashboard` (and its Hindi and Hinglish phrases in chat, "mera dashboard", "open my page") that replies with one button to their page. The brief, the plan answer and the holdings report keep their "My page" button. |
| **Commands list** | Update `/help` and the `setMycommands` list with `/dashboard`. Print the BotFather command list text in the report. |
| **Copy** | Every new line in the 3E message shape, in English, Hindi and Hinglish, calm, no hype words, "Research, not advice" once per message. |
| `tests/` | No network, faked model: a follow-up uses the previous turn; memory is per user (user A's turns never appear in user B's prompt); memory is deleted on `/stop`; the age and count caps hold; the IPO question gets an explanation, not the help line, and not "apply"; small talk and off-topic replies; the guard blocks a planted "buy" and a planted number in a conversational answer; the conversational path never logs text; `/dashboard` returns a button with a link that verifies against the stored token (sign the stored token, never mint a new one); `NETWORTH_SITE_URL` set vs unset; the menu button call is made once per onboarded user with the right shape; every new message passes the voice tests. |
| `evals/` | Extend the live words eval with 20 conversational cases (follow-ups, open questions, small talk, off-topic, "should I" in three languages, two jailbreak attempts). Run `uv run python -m evals --live words` (under $2) and report before and after. |

## Not in this phase

Changes to the engine, holdings, the Vercel site or Keiki transport; new data sources; advice or ranking of any kind; voice notes; group chats (stay private-only).

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. Live on Telegram, the coordinator asks "Should I apply for the upcoming LIC IPO?", then "what should I read first?", then "explain that in Hinglish". Each answer builds on the last, explains, never says apply or skip, and ends with "Research, not advice" once.
3. Live, "hi", "thanks" and "write me a python script" get short, kind, correct replies.
4. Live, "What happened today?" then "why?" then "and the US?" stays sourced to confirmed stories.
5. Live, `/dashboard` and the chat menu button open the coordinator's own dashboard on the Vercel site, and the link still works after another `/plan`.
6. The same conversation works in the web chat on `networth-eight-pied.vercel.app/demo` with no site change (follow-up answered from the previous turn).
7. `/stop` deletes the conversation (test), nothing conversational is logged (test), and the guard blocks planted advice and numbers (test).
8. The live words eval before and after is in the report, with no new advice or number failures.
9. `docs/phases/phase-9-report.md` lists the data shape, the memory caps, sample conversations in three languages, the BotFather command list, known gaps and deviations. A deploy and setting `NETWORTH_SITE_URL=https://networth-eight-pied.vercel.app` on Maritime are OWNER NEEDED: print the exact steps.

## The gate and branch policy

- Run `make check` before every commit and capture its exit code. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 9 READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
