# Phase 10 · The web app, redesigned: one chat in the middle that reaches everything

You are the **builder** for Phase 10 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including live in a browser at 320 px and 1440 px.

**You work in your own clone.** The Phase 9 builder is running in parallel in another clone and owns the conversation logic.
- **You own** `site/` (all of it), `networth/web/api.py` (add, don't rewrite), `tests/test_web_api*.py`, and `docs/phases/phase-10-*`.
- **Never edit** `networth/chat/`, `networth/bot/`, `networth/app/store.py`, `networth/engine/`, `networth/holdings/` or `networth/keiki/`. Call them, don't change them. If the API needs a pipeline change, print `OWNER NEEDED: <what> - <why>` and keep going on the rest.
- **The repo is public.** Never commit a secret, user data, `.env`, `data/`, `site/.env*`, `.vercel/` or `node_modules/`. Use `git commit -- <paths>` only.
- **Vercel is now connected to GitHub.** Every push to `main` that changes `site/` deploys production at `https://networth-eight-pied.vercel.app`. So never push a red or half-done site. Pushes that don't touch `site/` skip the build.

## The owner's verdict on Phase 8, in their words

"What design you have made, it's sloppy. Improvise it. Remember our UI/UX objective. We wanted something like this: just like Claude has the chat box in between, that chat tab should be there, which has access to all, and the user can chat and @ with and / commands with. The styling theme should be like Vercel, blackish. I hope you used OpenIntelligentUI. Every visualisation should look pencil drawn. Cool graphs."

Phase 8 took ideas from CopilotKit/OpenIntelligentUI but used none of it, put the chat in a side column, and used a Newsreader/Public Sans ledger look. Start from the owner's words, not from Phase 8's design doc.

## Read first

0. **Invoke the `pstack:poteto-mode` skill, then `impeccable` (the owner asked for it by name), then `design-taste-frontend` and `hallmark`, before any other work.** If a skill is refused, print `OWNER NEEDED: type /<skill> in this window` and wait. Where a skill conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. "The line we never cross" holds in every card and chart: no scores, ranks, buy or sell, allocation advice or F&O; no number, colour or label the server didn't send; no 🟢/🔴/⚪ and no "leans".
2. `docs/phases/phase-8-report.md`, `docs/phases/phase-8-contract.md`, `site/` as it is, `networth/web/api.py`, and `docs/phases/phase-3e-report.md` (the message shape every card renders).
3. **References, looked up, not guessed:**
   - https://github.com/CopilotKit/OpenIntelligentUI and CopilotKit's docs. Read the code and the licence. Use its open-source UI pieces (chat, generative-UI cards, mentions, suggestions) **if** they work with our own server as the only backend: no model, key or LLM runtime in the browser or on Vercel. If they can't, say exactly why in the report, and build the same interaction model yourself.
   - claude.ai and Gemini for the layout: the conversation is the page, with one composer centred at the bottom.
   - vercel.com and the Geist design system (https://vercel.com/geist) for the black theme, type (Geist Sans and Geist Mono) and density.
   - rough.js (https://roughjs.com, npm `roughjs`) for hand-drawn charts. Check the current version and licence on npm. Never invent an API or a version.
   - **Off limits:** the owner's employer's internal dashboard. Never open it or copy from it, because this repo is public. Where the owner says "cool graphs like that dashboard", read it as dense, legible, animated charts with crisp hover detail.
4. `~/.claude/CLAUDE.md` and `~/.claude/rules/web/*.md` are in force (performance budgets, accessibility, CSP, no trackers).

## Build

| What | Details |
|---|---|
| **The owner's reference screenshot** | Notion AI's home (app.notion.com/ai), dark: a slim left sidebar (search or ask with ⌘K, New chat, a library of past chats, then quick links), a calm centred empty state with a small mark and one large question ("How can I help you today?"), one wide rounded composer under it with a `+` on the left, a quiet mode label and a send arrow on the right, and a row of action chips below it ("Create Slides", "Spreadsheets", "Research", "Visualize"). Build Networth's home in that shape: sidebar with New chat, past chats for this user (kept in the browser only, never sent anywhere else), and quick links to Dashboard, News, History, My range and Holdings; the centred mark and question (for example "What would you like to know about your money?"); the composer with `+` (attach a screenshot or paste a link) and the send arrow; and action chips such as "What happened today?", "My brief", "My range", "Check a tip". On a phone the sidebar is a drawer. |
| **More inspiration (owner's list, optional)** | getdesign.ai, posts.design, loadmo.re, recent.design, 60fps.design (motion details), supahero.io, navbar.gallery, cta.gallery, inspora.design. The owner also named **https://bencho.dev** (interactive React components and micro-interactions) as the taste bar for hover, press, focus and transition details. Check its licence before reusing any component; if it allows reuse, credit it in the report, otherwise rebuild the interaction yourself. Fetch with `tinyfish fetch content get`, take ideas, copy no code. |
| **Layout** | Chat is the home of `/u/[token]` and `/demo`, like claude.ai: a centred conversation column, the composer pinned at the bottom centre, empty state with a short greeting and starter chips. The dashboard is not a second column. Its panels (this month's news, history counts, plan, plan range, holdings) open from the chat: as rich cards in the thread, and in a slide-over or side "canvas" panel the user can pin open on desktop. A thin top bar holds the profile name, "Sample profile" on the demo, and a dashboard toggle. Works at 320 px with no horizontal scroll: on a phone the canvas is a full-screen sheet. |
| **@ mentions** | Typing `@` opens a keyboard-navigable picker of things the user can point at: `@news` (and each confirmed story this month), `@history` (each sector row), `@plan`, `@range`, `@holdings` (and each holding when there is a list). Picking one inserts a chip. The message goes to the server with the chip as plain text the pipeline already understands (for example "about RBI raises repo rate to 5.50%: …"), so the answer stays the server's. Document the mapping in the contract. |
| **/ commands** | Typing `/` at the start opens a picker of the same commands Telegram has: `/brief`, `/range`, `/plan` (shows the plan, never changes it on the web), `/holdings`, `/dashboard` (opens the canvas), `/help`. Each runs through the server and renders the same message Telegram would send. Add the routes to `networth/web/api.py` by calling the existing bot and chat entry points; never re-implement their copy. A command that only makes sense on Telegram (`/stop`, `/link_broker`) shows one kind line pointing to the bot. |
| **Theme** | Vercel black: near-black background, hairline borders, one quiet accent, Geist Sans and Geist Mono via `next/font` or the `geist` package, tight type scale, real hover, focus and active states. Dark is the default. Keep a light theme that also feels designed. Tokens on `:root` per `~/.claude/rules/web/coding-style.md`. |
| **Pencil-drawn visuals** | Every chart and visual is hand-drawn with rough.js (or its chart wrapper, if you verify one), seeded so it doesn't jitter between renders: history counts with the normal-rate tick, the plan-range fan (bad, middle, good, before and after inflation), holdings by bucket, and a small news timeline. Lines draw in on first view, and the draw stops under `prefers-reduced-motion`. Hover or focus shows the exact server figure in Geist Mono. Every mark has an aria-label, and every chart has a visually hidden table of the same numbers. Charts show only numbers the server sent. |
| **Cards** | One card per server card type (news, history, plan_range, holdings, text), in the generative-UI style: a title, the server's words, the chart, the sources, an expand for detail, and a copy action. "Research, not advice" once per answer. |
| **Chat states** | Thinking, streaming or optimistic send, server error with its own words, unreachable, rate-limited, and over-length, each designed. The thread scrolls to each new turn and announces it (`aria-live`), as Phase 8 fixed. |
| **Performance** | Within `~/.claude/rules/web/performance.md`: app page JS under 300 kb gzipped, rough.js loaded only where a chart renders, no layout shift from charts (fixed boxes). Report the measured bundle sizes. |
| `tests/` | Python, no network: each new command route returns the same message as Telegram for the same profile, a demo token can't reach user routes, a mention chip maps to the documented text. Site: typecheck, lint and build pass; Playwright against the mocked API proves the composer is centred, `@` and `/` pickers open and work by keyboard, a command and a mention each produce a card, a chart has its hidden table, "Research, not advice" shows once per answer, and there's no horizontal scroll at 320 px. The banned-word and no-secret greps from Phase 8 still pass on the built output. |

## Not in this phase

Conversation memory and new chat intents (Phase 9 owns them), any model or key in the browser or on Vercel, analytics, new data sources, sign-up or login, and edits to the paths listed as not yours.

## Done when

1. `make check` passes from a clean clone after `uv sync`, and `cd site && npm ci && npm run build && npm run lint && npm run typecheck` pass, with the Playwright tests.
2. On a Vercel preview, `/demo` opens to a centred chat in a Vercel-black theme. The coordinator uses `@news`, `@range` and `/brief` by keyboard, and each produces the server's answer as a card with a pencil-drawn chart where there is data.
3. The dashboard canvas opens from the top bar and from `/dashboard`, shows news, history, plan, range and holdings with rough.js charts, and works as a sheet at 320 px.
4. `/u/[token]` does the same with the coordinator's own data. An unknown token shows the friendly not-found page.
5. No "leans", no 🟢/🔴/⚪, no hype words, no number the server didn't send, and no secret or token in the built output (tests).
6. The report says exactly what was used from CopilotKit/OpenIntelligentUI and rough.js (package, version, licence) and why anything was not used.
7. Screenshots at 320 px and 1440 px, dark and light, of `/demo` empty, `/demo` with an answer and the canvas open, and `/u/[token]`, in `docs/phases/phase-10-shots/`.
8. `docs/phases/phase-10-report.md` lists the design direction, the mention and command mapping, bundle sizes, known gaps and deviations. Nothing secret is committed.

## The gate and branch policy

- Run `make check` and the `site/` checks before every commit, and capture their exit codes. Don't commit red.
- **Work on the preview first.** Deploy previews with `cd site && vercel deploy --scope aankirzs-projects` (no `--prod`). Push to `main` only when the coordinator has reviewed the preview, because the push deploys production. Until then, commit locally and keep going.
- Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 10 READY FOR REVIEW` and the preview URL as the last lines in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.

## Added by the owner (2026-10-25): a GTM landing page

The owner: "I hope our website has a good GTM page as well."

| What | Details |
|---|---|
| **Landing page at `/`** | A public go-to-market page in the same Vercel-black system, built before or alongside the app redesign. Sections: a hero that says what Networth is in one line (a calm friend for your monthly investing, on Telegram, email and the web) with two CTAs ("Try the demo" to `/demo`, "Message the bot" to `https://t.me/networth_professor_bot`); how it works in three steps; the three channels; what it never does ("The line we never cross", in plain words); the honest track record from `/track-record` (our own negative result: the counts did no better than chance out of sample, so we show them as history); a live pencil-drawn sample chart from the demo data; a short FAQ; and a footer with "Research, not advice". |
| **Copy** | Calm, specific, no hype words, no exclamation marks, no promises of returns, no testimonials or numbers we cannot back. Every figure on the page comes from our server or our eval results. |
| **Reference skill** | Read `landing-page-design/SKILL.md` in https://github.com/elayadesign/ai-design-skills (fetch it with `tinyfish fetch content get`; do not install or run anything from it) for structure, conversion copy and the visual system. This brief and PRODUCT.md win where they conflict. Also read supahero.io, cta.gallery and navbar.gallery from the list above. |
| **Done when (add)** | `/` on the preview loads in under 2.5 s LCP on a throttled mobile Lighthouse run, has both CTAs working, passes the banned-word grep, and has screenshots at 320 and 1440 px, dark and light, in `docs/phases/phase-10-shots/`. |
