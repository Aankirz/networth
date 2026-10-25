# Phase 3F · Hardening from the data-isolation audit

You are the builder for Phase 3F of Networth. A separate coordinator reviews your work. Your ✅ is a claim.

Run `git pull --rebase` first (main has 3E and Phase 7). **Never edit** `networth/engine/`, `networth/bot/` (Phase 7B owns it), `networth/holdings/`, `site/` or `networth/web/api.py` (Phase 8 owns them). The repo is public: never commit a secret, user data, `.env` or `data/`. Use `git commit -- <paths>` only.

Step 0: invoke the `pstack:poteto-mode` skill. If refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Read `knowledge/PRODUCT.md`, `docs/phases/phase-3c-report.md`, `networth/app/store.py`, `networth/keiki/`, `networth/web/routes.py`, `networth/web/links.py`, the Dockerfile and `docs/deploy.md`. `~/.claude/CLAUDE.md` is in force. Look things up; never invent a field.

## Fix (each with a test, no network)

1. **/link code guessing.** The code space is 10^6 and any 6-digit number in an email is tried. Count failed redemptions per contact; after 5 in an hour, stop trying codes from that contact for the hour and answer as a normal message.
2. **Stopped users' pages.** `/u/{token}` and `/u/{token}/holdings` still render after /stop (`profile_by_token` ignores status). Return the friendly 404 when the profile is stopped.
3. **Tokens in access logs.** uvicorn's default access log writes `/u/<token>` paths, which are 30-day credentials. Turn the access log off or redact `/u/` paths, and record which in `docs/deploy.md`.
4. **Data dir permissions.** Create or chmod the data dir to 0700 at startup.
5. **Email sender authentication.** Look up in Keiki's and AgentMail's docs whether inbound email enforces SPF, DKIM or DMARC and whether a turn carries an authentication result. If it does, ignore unauthenticated turns. If the docs say nothing, record it as a known gap with the URLs you read.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. Each fix above has a passing test (5 may be a documented gap instead).
3. `docs/phases/phase-3c-report.md` gets a Hardening section listing each fix, its test and any gap. A deploy is OWNER NEEDED: print the exact command.

Push straight to `main` after `git pull --rebase`. Never force-push. If `.claude/CHANGELOG.md` conflicts, keep both sides. Finish with `PHASE 3F READY FOR REVIEW` as the last line.
