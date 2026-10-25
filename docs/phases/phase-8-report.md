# Phase 8 report · web dashboard and chat

## What shipped

- **The JSON API.** `networth/web/api.py`, added to the existing router with one import at the end of `routes.py`. It has four routes: `GET` and `POST` under `/api/u/{token}/` and `/api/demo/`.
  - Chat runs `respond_traced` and the guard, the same as Telegram.
  - A user's turns share `claim_answer` and `chat_max_per_hour` with Telegram.
  - The demo allows 8 turns per visitor an hour, and 120 an hour across all visitors (kept in the store).
  - CORS comes from `NETWORTH_WEB_ORIGINS`. A bare `*` is ignored.
  - Text is capped at 4096 characters.
  - Each turn goes to a log with no text, token or raw user id.
  - Tokens are checked with `hmac.compare_digest` and redacted from the access log.
- **The site.** `site/` uses Next.js 16.4.3 (App Router, TypeScript strict), shadcn/ui and Tailwind 4.
  - Routes are `/demo` and `/u/[token]`, and `/` redirects to `/demo`.
  - All API calls happen on the site's server (`lib/api.ts`, server-only) through one server action (`app/actions.ts`).
  - Each page gets a nonce CSP from `proxy.ts`, plus security headers. There are no analytics or third-party scripts.
- **Tests.**
  - `tests/test_web_api.py` (26 tests) and `tests/test_web_api_contract.py` (7 tests). `make check` passes 1025.
  - `site/e2e/demo.spec.ts` (Playwright, mocked API). The demo loads, a question gets a card, and "Research, not advice." shows once in the answer. An unknown link gives a 404.
  - `site/scripts/check-build.mjs` (`npm run check:build`) checks the site source for verdict words and for rupee or percent figures it writes itself. It also checks all of `.next/` for every server secret name, for `xox…` and `sk-…` key shapes, and for any `NEXT_PUBLIC_NETWORTH` variable. A planted "Strong buy at ₹100" fails it.
- **Screenshots.** `docs/phases/phase-8-shots/` holds `/demo` and `/u/[token]` at 320 and 1440 px, light and dark, each with an answer card open. The shot test also fails on horizontal scroll.

## The contract

`docs/phases/phase-8-contract.md` is the source of truth, and `site/lib/contract.ts` is a byte-for-byte copy of its TypeScript block. The contract tests check four things:

- The file equals the block.
- Every interface's fields equal the keys the real API returns, for the dashboard, chat turns, errors, history rows, news and holdings.
- Every card type and intent the server has is declared.
- The Playwright fixtures still match the types.

This check caught the phase 7B `holdings` intent during the rebase. A holdings question now gets the asker's own holdings card.

| Intent | Card |
|---|---|
| `what_happened_today` | `news` |
| `why` | `history` (the engine's `odds()` row behind the answer's `/why` link) |
| `plan_range` | `plan_range` (the asker's own plan) |
| `holdings` | `holdings` (the asker's own report, or `text` when they have none) |
| every other intent | `text` |

## The design direction

The direction is "the ledger and the friend beside it", written up in `docs/phases/phase-8-design.md`. Every count is drawn the way a careful friend would mark a passbook. A graphite fill runs to the hit rate, with a pencil tick at the normal rate and the figures in type beside it.

- **Palette.** Taken from the 3E server pages, in OKLCH, with a light and a dark set. Colour carries no verdict: gains use only ▲ ▼ –.
- **Type.** Newsreader for display and Public Sans for text, self-hosted with `next/font`.
- **Pencil filter.** One `#pencil` SVG filter is used on the count bars, the range's "put in" line, empty states and the thinking line.
- **Layout.** Two columns on desktop, with the chat sticky on the right. On a phone the demo puts the chat first and a user's page puts the dashboard first.
- **Theme.** The system theme by default. A toggle stores the choice in a cookie, so the server renders it with no flash and no inline script.

### What each inspiration gave

| Reference | Taken | Left |
|---|---|---|
| CopilotKit/OpenIntelligentUI | Chat-first opening, four starter chips, one native card per answer type, a copy action on hover and focus, `aria-live` answers | Model-generated UI and the sandboxed iframe. The card comes from the server's intent table. No code copied. |
| perplexity.ai/finance | News rows that name their publishers | Tickers, heatmaps, price cards |
| kobra.systems | Every chat state designed (thinking, answer, server error with its own words, unreachable), and motion that stops under reduced motion | Its component code |
| shadcn/ui and Vercel | Button, Textarea and Switch primitives, the chart tokens, one quiet accent | The default zinc theme and card grids |
| Gemini | A calm composer field at the foot of the chat column | Gradients and sparkle icons |
| Pencil-drawn visuals | The `#pencil` filter on counts, the invested line and empty states | Hand-drawn type |

## Skill gates

- **taste lint.** 0 FAIL and 1 WARN.
  - The WARN is "in today's rupees", the server template's own wording, kept so the site matches `_plan_range.html`.
  - The ledger's row rules carry `taste-skill-ignore`, because they are the design idea.
  - The section dividers became spacing.
- **Not applied, by design.** The skill's imagery floor and section-variety rules are for marketing pages, and this is product UI.
- **Not run.** `inspect.mjs`. Playwright covers its overflow check at 320 and 1440 px, and I read the screenshots instead.

## Preview URL

**Live preview:** https://networth-l05e1qqm5-aankirzs-projects.vercel.app/demo (target preview, behind Vercel Authentication). See "What happened on Vercel" below. The section that follows was the original OWNER NEEDED request, kept for the record.

- The Aankirz Vercel connector was not available in the session that finished this phase.
- The local Vercel CLI is logged into a different account (team Simbian, user `claude-marketing-team-8513`). I did not deploy with it.

The steps, in `site/`:

```sh
vercel logout && vercel login                          # sign in as Aankirz
vercel link --scope aankirzs-projects --project networth --yes
vercel env add NETWORTH_API_URL preview                # the Maritime agent URL, e.g. https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea
vercel env add NETWORTH_API_URL production
vercel deploy                                          # preview
```

Don't connect the Git repo to the project. Pushes go straight to `main`, so every push would become a production deploy.

The API must be live on Maritime first:

```sh
npx maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json
```

Then set `NETWORTH_WEB_ORIGINS` on Maritime to the production origin and the preview pattern, for example `https://networth-aankirzs-projects.vercel.app,https://networth-*-aankirzs-projects.vercel.app`. Strictly, the site's server-side calls send no `Origin`, so CORS only matters for browsers.

The demo profile is created on the first demo call. To reset it: `uv run python -m networth.web.api reset-demo`.

### What happened on Vercel

- **The project.** It is `networth` in `aankirzs-projects` (`prj_8XCYQpjz5itLlABMXeveU0P0Uqrl`). It was created with `vercel project add`, so no Git repo is connected. `NETWORTH_API_URL` is set for Preview only. `site/vercel.json` pins the Next.js framework, because the project was created with the "Other" preset. `site/.vercelignore` keeps `.env*` (including the `.env.local` OIDC token that `vercel link` writes) and build output out of uploads.
- **The first deploy went to production.** The builder ran `vercel deploy` without `--prod`, but the CLI made it a production deployment anyway, because it was the new project's first deploy. That deployment is `networth-dcfke2r2b-aankirzs-projects.vercel.app`, aliased to `networth-eight-pied.vercel.app`. `NETWORTH_API_URL` exists only for Preview, so the server had no API URL there. `lib/api.ts` answers 503 before making a request, and every page shows "Networth can't load this page right now". It is not a code bug, and it is left in place for the owner.
- **Real previews.** Every later deploy uses `vercel deploy --target preview`.
- **Preview protection.** Previews sit behind Vercel Authentication, which stays on. Judges therefore need the production URL for `/demo`. That needs `NETWORTH_API_URL` set for Production and the deploy below.

## Production deploy command

OWNER NEEDED, after the preview checks out:

```sh
cd site
vercel env add NETWORTH_API_URL production   # the same Maritime agent URL
vercel deploy --prod --scope aankirzs-projects
```

## Known gaps

- **Production is broken until it is redeployed.** See "What happened on Vercel".
- **`/u` 404s for real users.** This is a server bug the phase 7B builder is fixing. The site's `/u/[token]` page works against the mock.
- **The plan range on Maritime.** If `data/sim/returns.csv` is missing on Maritime, plan range cards show the server's "not ready" note. It is built with `uv run python -m networth.sim.data`.
- **Chrome is English only.** Answers come in English, Hindi or Hinglish. The site's headings and table labels (copied from the server's English templates) are English only, and so are the server's own `/u` pages.
- **The demo's per-visitor cap lives in memory.** It resets when the server restarts. The 120-an-hour cap in the store is the real limit on spend.
- **Chat history resets on reload.** It lives in the page. A user's turns are still logged to their own messages on the server, the same as Telegram.
- **Mock data quirks.** These come from the fixtures, not the product.
  - The demo fixture copies the user fixture, so the shots show ₹1,00,000 where the real demo sends ₹1,50,000.
  - The fixture's history sentences say "beat ^NSEI", because the fixture builds odds lines without the server's asset-name config.
- **Not run.** Lighthouse, and the Firefox and Safari passes.

## Deviations

- **Plan questions on the web don't create a page link.** `today.plan` makes a link by calling `store.new_link_token`, which would revoke the link the user is reading. Web chat runs with `link_secret=None`, so it never makes one. Plan answers on the web therefore leave out the "open your page" link that Telegram sends. The words are otherwise the same.
- **Every page renders per request.** `cacheComponents` is off because a nonce CSP needs it. Each page fetches per request anyway (`no-store`).
- **`style-src` allows `'unsafe-inline'`.** The drawings set geometry inline. Scripts stay nonce-only with `'strict-dynamic'`.
- **The site writes a few labels of its own.** These are the section headings, "Reported by", "normal", "The past cases, one by one", the starter chips and the error line for an unreachable server. Each label is copied from the server's templates or messages where one exists. None of them is a number, a colour verdict or a direction. `check:build` enforces that no figure appears in the site's own text.
- **Card labels drop their footer.** The range and holdings `label` strings end in "Research, not advice.", and the site removes that suffix. The footer then shows once per answer, from `message.footer` or `Dashboard.footer`.
- **Visitor key.** The demo's visitor key is a SHA-256 of the client IP, made on the site's server, so no raw IP reaches the API.
- **Token check before the API.** `/u/[token]` checks the token's shape before calling the API, so a malformed token never leaves the site's server. Both cases give the same 404 page with the server's `BAD_LINK` words.
