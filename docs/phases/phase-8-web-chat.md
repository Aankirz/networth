# Phase 8 · A web dashboard with chat: talk to Networth in the browser

You are the **builder** for Phase 8 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including live in a browser.

**You work in your own clone.** A separate builder wires Phase 7 holdings into Telegram in parallel.
- **You own** a new Next.js app in `site/` (top level), a new JSON API module `networth/web/api.py` registered in `networth/web/__init__.py` or `routes.py` (add, don't rewrite), `tests/test_web_api*.py`, and `docs/phases/phase-8-*`.
- **Never edit** `networth/engine/`, `networth/bot/`, `networth/holdings/`, `networth/keiki/`, or the chat pipeline's logic in `networth/chat/`. Call it, don't change it. If you believe the pipeline needs a change, print `OWNER NEEDED: <what> - <why>` and stop that thread.
- **The repo is public.** Never commit a secret, user data, `.env`, `data/`, `site/.env*`, `.vercel/` or `node_modules/`. Use `git commit -- <paths>` only.

## What the user gets

The owner, in their words: "a web dashboard + chat view as well, where the user can talk with us. Just like for anything general a user goes to claude.ai and asks, for investment they come to us."

- **Their dashboard.** On their private link (`/u/{token}`, the token they already get), one screen shows: this month's confirmed news, the history counts with the normal rate, their plan and their plan range, and their holdings report if they have one. Every number comes from our server.
- **A chat beside it.** The user types anything they would send the Telegram bot ("What happened today?", an IPO note, a forwarded tip, "explain OFS", "my range"). The answer is **exactly** what Telegram would send: same pipeline, same guard, same three languages, same "Research, not advice" footer. Answers render as rich cards (a news list, a history-count card with the normal rate, a plan-range card with its bar, a holdings card) in the generative-UI style of OpenIntelligentUI, not as raw text.
- **A public demo** at `/demo` with a made-up profile (Balanced, ₹1,50,000 a month, English) so judges can try it without a Telegram account. The demo profile is clearly labelled as a sample and its chat is rate-limited.

**The line we never cross holds in every card.** No scores, ranks, buy or sell, allocation advice or F&O. A card never adds a number, colour or label the server didn't send. No 🟢/🔴/⚪ and no "leans" (finding 5).

## Decisions already made (owner, 2026-10-25)

- **Stack: Next.js on the owner's Vercel account (Aankirz), with shadcn/ui.** This reverses the earlier no-React rule for this surface only. The Python server on Maritime stays the truth layer: the site never computes a number, never calls a model, and never holds an API key.
- **Access: existing users through their `/u` token, plus the public `/demo`.** No new sign-up flow.
- **Design inspiration:** perplexity.ai/finance, Gemini, https://kobra.systems/, shadcn, Vercel, pencil-drawn visuals, and https://github.com/CopilotKit/OpenIntelligentUI (the owner says this one is the most useful). Read them, take ideas, don't copy code you can't license. The owner's employer's internal dashboard repo is **off limits**: never open it, never copy from it, because this repo is public.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work. Then invoke `design-taste-frontend`, `impeccable` and `hallmark`** (the owner asked for all three on this UI). If a skill is refused, print `OWNER NEEDED: type /<skill> in this window` and wait. Where a skill conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc.
2. `docs/phases/phase-3e-report.md`: the message data shape (`Message`, body blocks, footer) and the voice rules. Your cards render that shape. Don't invent copy the server didn't write.
3. `networth/chat/__init__.py` (`respond_traced`), `networth/chat/answer.py` (`deliver_traced`), `networth/web/routes.py` (`/u/{token}`, `/plan-range`, `/u/{token}/holdings`), `networth/app/store.py`, and `networth/keiki/turn.py` for how another channel already reuses the pipeline.
4. Vendor docs, which are the source of truth: Next.js (App Router), shadcn/ui, Vercel CLI and project env vars, and CopilotKit / OpenIntelligentUI if you use them. **Look everything up. Never invent an API, prop, flag or package version.** Use `tinyfish fetch content get "<url>"`.
5. `~/.claude/CLAUDE.md` and `~/.claude/rules/web/*.md` are in force (performance budgets, accessibility, security headers, CSP).

## Build

| What | Details |
|---|---|
| **Data shape first** | Write the JSON contract before any UI: a chat turn request (`token`, `text`, optional `lang`) and a response holding the server's `Message` (title, body blocks, expandable detail, footer, links) plus a typed `card` (`news`, `history`, `plan_range`, `holdings`, `text`) carrying only fields the server computed. Commit it as `docs/phases/phase-8-contract.md` and as TypeScript types generated or hand-mirrored from it, with a test that the two match. |
| **Server API** (`networth/web/api.py`) | `GET /api/u/{token}/dashboard` and `POST /api/u/{token}/chat`, plus the same two under `/api/demo`. Chat runs `respond_traced` exactly as Telegram does, then `guard` as today. Unknown token gives 404, the same as `/u`. Per-user rate limit reusing `store.claim_answer` and `chat_max_per_hour`; the demo gets a stricter per-IP limit. CORS allows only the Vercel production and preview origins from an env var, never `*`. Inbound text is length-capped. Log the turn like the Keiki log does: trace id, intent, guard verdict, cost, never the text. |
| **The site** (`site/`) | Next.js App Router, TypeScript strict, shadcn/ui, Tailwind. Routes: `/u/[token]` (dashboard + chat) and `/demo`. The site fetches only our API, server-side where it can, so the token never lands in client logs or a third-party script. Streaming or optimistic UI is fine; the final text is always the server's. Cards for each `card` type, a plain fallback for `text`, and visible "Research, not advice" once per answer. Light and dark that both feel designed. Works at 320 px with no horizontal scroll. Keyboard and screen-reader usable. No analytics or third-party trackers. |
| **Look** | A specific direction, not a template: write it down in `docs/phases/phase-8-design.md` with the palette, type pairing and two or three references before building. Pencil-drawn visual touches are welcome where they help (empty states, the plan-range sketch). Reuse the shadcn chart look 3E gave the inline SVG charts, so the web and the server pages match. |
| **Deploy** | Link `site/` to a Vercel project on the owner's Aankirz account with the Vercel CLI or MCP. Set `NETWORTH_API_URL` (the Maritime agent URL) as a Vercel env var. Deploy a preview yourself. **A production deploy is OWNER NEEDED**: print the exact command and wait. Never put a secret in a `NEXT_PUBLIC_` variable. |
| **Per-user isolation** | Every API call resolves the token to one user and reads only that user's rows (profile, messages, asked terms, watches, holdings). A chat turn can never read or write another user's data. The demo profile is its own user and is reset by a documented command; demo chats never land in a real user's history. Tokens are compared in constant time and never logged. |
| `tests/` | Python, no network: user A's token never returns user B's plan, holdings or messages (dashboard and chat); dashboard JSON for a known token, 404 for an unknown one, chat runs the guard (a planted bad number is blocked), the reply equals what the Telegram path returns for the same profile and text, rate limits, CORS rejects other origins, no text in the turn log. Site: typecheck, lint and build pass; one Playwright test against a mocked API proves the demo loads, a question gets a card, and "Research, not advice" shows once. |

## Not in this phase

A new sign-up or login, payments, any model or key in the browser, new intents or new copy in the pipeline, edits to the paths listed as not yours, analytics, and a production Vercel deploy (OWNER NEEDED).

## Done when

1. `make check` passes from a clean clone after `uv sync`, and `cd site && npm ci && npm run build && npm run lint && npm run typecheck` pass.
2. The JSON contract is committed, and a test proves the TypeScript types match it.
3. For the same profile and text, the web chat answer's plain text equals what Telegram's pipeline returns, and the guard ran on it (a test proves both).
4. A Vercel preview URL loads `/demo`. The coordinator asks "What happened today?", an IPO question and a forwarded tip there, and gets the same sourced answers as Telegram, as cards, with "Research, not advice" once each.
5. `/u/[token]` on the preview shows the coordinator's own dashboard (news, history counts with the normal rate, plan, plan range) and chat. An unknown token shows a friendly not-found page.
6. No "leans", no 🟢/🔴/⚪, no hype words, and no number the server didn't send, anywhere in the site. A test greps the built output.
7. Rate limits, CORS and the length cap hold (tests). No secret or token appears in client bundles (a test greps `.next/` for the API key names and `xox`, `sk-`).
8. Screenshots at 320 px and 1440 px, light and dark, of `/demo` and `/u/[token]` with a card open, in `docs/phases/phase-8-shots/`.
9. `docs/phases/phase-8-report.md` lists the contract, the design direction, what was taken from each inspiration, the preview URL, known gaps, deviations and the production deploy command. Nothing secret is committed.

## The gate and branch policy

- Run `make check` and the `site/` checks before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Python dependencies only with `uv add`; JS dependencies only with `npm install` inside `site/`, never `--legacy-peer-deps`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 8 READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do (a Vercel login, a production deploy, a dashboard click), print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
