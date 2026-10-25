# Phase 11 report · Google sign-in on the web app

## What a visitor sees

- **Signed out:** the landing header shows "Try the demo" and "Sign in". `/demo` is unchanged and needs no sign-in. `/dashboard` offers "Sign in with Google" and points back to the demo.
- **Signed in, not linked:** `/dashboard` says "Send /weblink to @networth_professor_bot and type the code here." It has a code box under that. A refused code gets the server's plain sentence.
- **Signed in and linked:** `/dashboard` opens the user's own workspace, with their plan, dashboard and chat. The chat runs under their real user id, so `talk.window` and `remember` apply. Only `web:demo` stays shared and memoryless.
- **The header when signed in:** an avatar (the first letter of the Google name, never Google's picture) opens a menu with "Signed in as …", Dashboard, Sign out and "Forget me on the web".
- **`/privacy`** says what we keep, what we never keep and how to erase. The footer links to it.

## How it works

1. **Auth.js v5 (`next-auth@5.0.0-beta.32`), Google only** (`site/auth.ts`, `app/api/auth/[...nextauth]/route.ts`).
   - It reads `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` and `AUTH_SECRET` from env, as the Auth.js docs describe.
   - The JWT callback keeps only `sub`, `name` and `google`, which is Google's `providerAccountId`, the stable subject id. Email and Google's tokens never enter the session cookie.
2. **Site to Python.** Server code checks the Auth.js session (`lib/session.ts`, `signedIn()`). Then it mints `v1.<payload>.<mac>` with HMAC-SHA256 over `{sub, name, exp}`.
   - `NETWORTH_WEB_SECRET` signs it, and it lives 60 s.
   - The token travels as `Authorization: Bearer` to `/api/web/*`.
   - `networth/web/session.py` checks the MAC in constant time, the shape and lengths, and an expiry no more than 300 s ahead.
   - No secret on the server means everyone is refused. The browser never sends a user id, and a `user_id` in a body is ignored (there's a test for it).
3. **`/weblink`** (`networth/bot/commands.py`) mirrors `/link`.
   - It issues a six-digit code that works once, for 10 minutes, from the same `link_codes` store via `new_link_code` / `redeem_link_code`.
   - `/api/web/link` redeems the code, refuses the demo user, and binds the Google subject to that user in a new `web_logins` table, keyed by subject and never by email.
   - Misses count against `google:<subject>`, and five an hour block that account, the same as `/link`.
4. **Forget me** calls `/api/web/forget`, which deletes the binding, then signs out. `web_logins` has a `user_id` column, so it is in `USER_TABLES`, and `/erase` deletes it with everything else.
5. **CSP:** `form-action` now allows `https://accounts.google.com`, because the Sign in server action redirects the form there. `img-src` is unchanged, because no Google image is loaded.

## Done-when checklist

| # | Item | Status |
|---|---|---|
| 1 | On production, Sign in opens Google and the header comes back signed in | Needs the owner's `NETWORTH_WEB_SECRET` (below) for the linked view. Sign in itself needs only the Google env and the redirect URI, both in place. e2e proves the redirect goes to `accounts.google.com` with `redirect_uri=…/api/auth/callback/google`. |
| 2 | `/weblink` code, then the user's own plan on `/dashboard` | `test_a_weblink_code_shows_the_linked_user_their_own_plan`, and e2e "the right one shows their plan" |
| 3 | Chat memory, and a second account is isolated | `test_a_linked_users_web_chat_remembers_the_turn_before`, `test_a_second_google_account_cannot_see_the_first_users_chat_or_dashboard` |
| 4 | Forged or missing session gets 401 on every new route | `test_every_web_route_refuses_a_missing_session` and `…_a_forged_session` (6 routes × 5 forgeries), plus e2e for a forged cookie |
| 5 | Used, expired and wrong codes refused in plain copy | `test_a_used_code…`, `test_an_expired_code…`, `test_a_wrong_code…` (3 shapes), `test_a_wrong_six_digit_code…`, plus e2e for wrong and used codes |
| 6 | `/erase` and Forget me remove the link | `test_erase_on_telegram_removes_the_google_link`, `test_forget_me_removes_the_link_and_keeps_the_bot_user`, and e2e "Forget me unlinks and signs out" |
| 7 | `/demo` unchanged signed out | The existing demo specs, plus e2e "/demo works signed out exactly as before" |
| 8 | `/privacy` live and linked from the footer | e2e "the footer links to /privacy" |
| 9 | Screenshots at 320 and 1440, dark and light | `docs/phases/phase-11-shots/`: 24 shots (signed-out header, signed-in header, open menu, link step, wrong code, linked dashboard) |
| 10 | Gate exit codes | Below |

## Gate (clean `.next`)

| Command | Exit |
|---|---|
| `make check` (ruff check, ruff format --check, pytest: 1261 passed, 12 skipped) | 0 |
| `npm run lint` | 0 |
| `npm run typecheck` | 0 |
| `npm run build` | 0 |
| `node scripts/check-build.mjs` | 0 |
| `npx playwright test` (45 passed, 48 screenshot tests skipped outside `SHOTS=1`) | 0 |
| `SHOTS=1 npx playwright test e2e/account.spec.ts e2e/account-shots.spec.ts` (37 passed) | 0 |

## Deviations and notes

- **Landing header.** On phones narrower than 640px the "Networth" wordmark is screen-reader-only, so Sign in fits beside "Try the demo" at 320 with no sideways scroll; the mark stays visible. The account button sits right of "Try the demo", so its menu opens inside the screen.
- **Shared code store.** `/link` and `/weblink` codes share one store, as the brief asks, so either command's code works in either place. Both expire in 10 minutes and work once.
- **Contract.** `docs/phases/phase-10-contract.md` gained the `/api/web/*` routes and the `signed_out`, `not_linked` and `bad_code` codes. `site/lib/contract.ts` still matches it byte for byte.
- **e2e.** The e2e suite forges Auth.js session cookies with test-only secrets (`e2e/session.ts`) and never calls Google. The mock API checks the same HMAC token the Python server does.

## Owner steps

- Done: the redirect URI `https://networth-eight-pied.vercel.app/api/auth/callback/google` and the JS origin are set on the crucible OAuth client.
- **Needed:** set one random value as `NETWORTH_WEB_SECRET` in both Vercel production and the Maritime server env, then redeploy the Python server. Until then, signed-in pages say Networth can't load and the demo works as before.
