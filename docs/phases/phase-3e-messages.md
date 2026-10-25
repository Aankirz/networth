# Phase 3E · Messages that feel like a calm friend, not a newsletter

You are the **builder** for Phase 3E of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including on live Telegram.

You work in your own clone. Run `git pull --rebase` first: 3D must be on `main` before you start. **Never edit `networth/engine/`.** **The repo is public, so never commit a secret, user data, `.env` or `data/`.** Use `git commit -- <paths>` only.

## The problem, in the owner's words

"It feels too texty and too much like a markety thing. I want the interface smooth and delightful to the user's eyes. The message should be very friendly, understanding and empathetic to the user."

Today every message is plain text with no `parse_mode`. The brief is one long block. Disclaimers repeat. Lines read like a report, not like a person who knows you.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** Then invoke **`impeccable`** (for UX copy, hierarchy and empty or error states) and **`design-taste-frontend`** (for the `/u` and Why web pages the messages link to). If a skill is refused, print `OWNER NEEDED: type /<skill> in this window` and wait. Where a skill conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc. "The line we never cross" holds: no scores, ranks, buy, sell or allocation advice.
2. Every place a user-facing string is built: `networth/bot/briefs.py`, `commands.py`, `onboarding.py`, `alerts.py`, `watches.py`, `networth/chat/answer.py`, `networth/keiki/turn.py`, `networth/keiki/onboard.py`, and `networth/bot/telegram.py`.
3. Telegram's formatting rules, from the source: https://core.telegram.org/bots/api#formatting-options and https://core.telegram.org/bots/api#linkpreviewoptions. Look things up. Never invent a tag or a field.
4. `~/.claude/CLAUDE.md` and `~/.claude/rules/web/*.md` are in force.

## Build

| What | Details |
|---|---|
| **Rich text, safely** | Switch Telegram sends to `parse_mode: HTML`. Use only the tags Telegram documents: bold, italic, `blockquote`, `blockquote expandable`, links. Every dynamic value (story titles, IPO names, user text, anything from a model) is HTML-escaped at one boundary in `telegram.py`, never at call sites. If Telegram rejects a message for bad markup, resend it as plain text and log it. Turn off link previews, except the one link a message is about. |
| **One renderer, two channels** | Messages are built as a small structure (title line, body blocks, optional expandable detail, one footer), then rendered to Telegram HTML or to plain text for Keiki email. `guard.check` runs on the plain-text form, so markup can never hide or change a number. |
| **The brief, redesigned** | It should read in 10 seconds on a phone. A warm first line that knows the user ("Morning. It's your investing day. ₹1,50,000 is ready."). This month's news in 2 or 3 short lines. History in one short line per row, with the details and the "normal" baseline inside an expandable blockquote. Their plan in one line. One quiet footer. Buttons stay, with friendlier labels. |
| **Voice** | Short sentences. Second person. Calm, never hype: no exclamation marks, no "unlock", "boost", "smart move", "don't miss". Name feelings plainly when markets fall ("A rough week. Falls like this have happened before, and you planned for one."), without promising anything. Say "Research, not advice" once per message, in the footer, not three times. Emoji only as quiet markers (at most one per block), never as decoration. Keep Hindi and Hinglish natural: write them, don't translate English word for word. |
| **Every message type** | Onboarding, the brief, "What happened today?", Why, the tip check, Explain this, `/range`, watches, alerts, `/help`, errors and "try again". Errors and empty states get a kind, specific line and a next step. |
| **Scoreboard wording (owner decided: finding 5, options a, b and c)** | Phase 5 showed "history leans" don't hold out of sample (walk-forward 45% vs about 51% baseline; vault 45% vs 49%). So:<br>**a)** Drop the "history leans" framing and the 🟢/🔴/⚪ colours from every user-facing message and page. Show plain counts ("beat the Nifty 50 in 6 of 9 past bank-stress months; normal is 59%") and, when the gap is small, say it is "within normal ups and downs". Never imply a direction. Stop calling `lean()` from message code. If `lean()` or `LEAN_GAP` live in `networth/engine/`, leave them there unused and say so in the report.<br>**b)** When the month has a confirmed event, lead with the user's own plan, not the counts: "You planned for falls like this" plus their plan-range numbers from `plan_range` (bad case, middle, and how often a fall of their size happened). Counts come after, inside the expandable detail.<br>**c)** Publish our own negative result on `/track-record`: the walk-forward and vault numbers from `evals/results/summary.json`, in plain words ("When we tested these counts on years they hadn't seen, they did no better than chance. So we show them as history, not as a hint."). |
| **Carried over from 3D (live words eval)** | **Finding 3:** the plan-question reply dumps the whole saved profile, including "Plan: Balanced. 20% safety, 70% core, 10% growth" and "Type /plan to change it." The judge reads that as an allocation and a nudge in 5 cases (`evals/results/words.json` failures). Answer plan questions with the fixed line, the event history if confirmed, and a link to their page, without restating percentages or inviting a change. **Finding 1 tail:** template fallbacks for the tip check and plan replies exist only in English, so a Hinglish user who trips the guard gets English. Every template gets English, Hindi and Hinglish versions. Rerun `uv run python -m evals --live words` (under $1) and report before and after. |
| **Before and after** | `docs/phases/phase-3e-shots/` gets screenshots of the old and new version of the brief, a Why answer, the tip check and onboarding, in English and Hinglish. Use a local render of the Telegram HTML, plus live screenshots once deployed. |
| `tests/` | No network. Escaping: a story title containing `<b>`, `&` or `</blockquote>` renders as text. The fallback to plain text on a Telegram 400. Every number in the HTML form also appears in the plain form, and `guard.check` passes on it. Banned hype words don't appear in any template. Each message type renders in all three languages. The brief fits within Telegram's message length. |

## Not in this phase

Holdings or portfolio reports (Phase 7 owns them), new intents, Keiki config, web page redesigns beyond the link-preview cards, engine edits and deploys.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. Every user-facing Telegram message uses HTML, with escaping in one place and the plain-text fallback tested.
3. Keiki email gets the plain-text render of the same message, and the guard checks that form.
4. The brief reads in about 10 seconds: at most 8 visible lines before the expandable detail, in all three languages.
5. No template contains hype words or exclamation marks, and "Research, not advice" appears once per message. A test enforces both.
6. Before and after screenshots are in `docs/phases/phase-3e-shots/`.
6b. No user-facing message or page says "leans" or shows 🟢/🔴/⚪ on a count (a test greps every template). A brief in an event month leads with the user's plan range. `/track-record` shows the walk-forward and vault result in plain words.
7. `docs/phases/phase-3e-report.md` lists every message type changed, the voice rules, sample messages in all three languages, known gaps and deviations. Nothing secret is committed.
8. A deploy is OWNER NEEDED. Print the exact command and don't run it.

## The gate and branch policy

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 3E READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
