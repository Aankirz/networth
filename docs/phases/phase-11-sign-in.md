# Phase 11: Google sign-in on the web app

## Who it is for

A visitor who already uses the Telegram bot signs in with Google on the site and sees their own plan, dashboard and chat history. A visitor who never signs in still gets the open demo, unchanged.

## Build

1. **Auth.js (NextAuth v5) in `site/`** with the Google provider only. Env names are already set in Vercel production: `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `AUTH_SECRET`. Read them from env, never hardcode. Look the API up in the Auth.js docs for the installed Next.js version; never invent a flag.
2. **Link Google to a Telegram profile with a one-time bot code.** Signed-in and unlinked, the site shows "Send /weblink to @networth_professor_bot and type the code here." The bot's `/weblink` issues a six-digit code, single use, 10 minutes, the same shape as the existing `/link` for email. The server binds the Google subject id (never the email as the key) to that user. Reuse the `/link` code store; do not build a second one.
3. **Per-user chat history on the server.** A linked user's web chat uses their real user id, so `talk.window` and `remember` apply to them. Only `web:demo` stays shared and memoryless.
4. **Server routes** for the site: verify the Auth.js session on the Next.js side, then call the Python API with a signed, short-lived token. Never trust a user id sent by the browser.
5. **Sign out**, and **"Forget me on the web"**, which unlinks the Google account. `/erase` on Telegram also removes the Google link.
6. **A privacy page** at `/privacy`. It says what we keep (Google subject id, display name, the link), what we never keep (Google tokens past the session, contacts, mail), and how to erase.
7. **Header.** "Sign in" next to "Try the demo". Signed in, it shows the avatar and a menu with Dashboard, Sign out, and Forget me.

## Not in this phase

- No other providers. No email or password sign-in.
- No change to the landing page design beyond the header button.
- No sign-up wall. The demo stays open with no sign-in.
- No new Telegram features besides `/weblink`.

## Done when

1. On production, "Sign in" opens Google, and coming back shows the signed-in header.
2. A signed-in, unlinked user who sends `/weblink` to the bot and types the code sees their own plan on `/dashboard`.
3. That user's web chat remembers an earlier turn ("what about it?" works). A second Google account cannot see the first user's chat or dashboard.
4. A forged or missing session against every new API route gets 401. A test proves it.
5. A used code, an expired code, and a wrong code are each refused with plain copy, and a test covers each one.
6. `/erase` on Telegram and "Forget me" each remove the link. A test covers both.
7. `/demo` works signed out, exactly as before.
8. `/privacy` is live and linked from the footer.
9. Screenshots at 320 and 1440, dark and light, of the signed-in header and the link step are in `docs/phases/phase-11-shots/`.
10. `make check` exits 0, and the site's lint, type check, build and Playwright all exit 0. Record each exit code.

## Sources of truth

- Auth.js docs (authjs.dev) for the installed version. Google OAuth docs for the redirect URI.
- `docs/phases/phase-3c-report.md` for how `/link` works.
- Look it up. Never invent an API, model id, or flag.

## The gate

`make check` at the repo root, plus `npm run lint`, the type check, `npm run build` and Playwright in `site/`. Capture each exit code. A pipe into `tail` hides the code.

## Branch policy

Push straight to main (hackathon override). Run `git pull --rebase` before every push. A push to main that touches `site/` deploys Vercel production, so push only after the gate passes. The coordinator redeploys the Python server.

## OWNER NEEDED protocol

Before any step only a human can do, print `OWNER NEEDED: <what> — <how>` and wait. One is expected. The Google OAuth client in the crucible project must list the redirect URI `https://networth-eight-pied.vercel.app/api/auth/callback/google`, plus the preview pattern if you need it. Give the owner the exact console path. Never enter secrets into any form yourself.

End with `PHASE 11 READY FOR REVIEW`.
