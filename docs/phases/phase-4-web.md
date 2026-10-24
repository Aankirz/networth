# Phase 4 · The web pages (runs in parallel with Phase 2 and Phase 3A)

You are the **builder** for Phase 4 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check, including in a real browser.

Two other builders work in the same repo at the same time. **Phase 2** owns `networth/watcher/`, `networth/llm.py` and `networth/config.*`. **Phase 3A** owns `networth/app/`, `networth/bot/` and the `Dockerfile`. Never edit their files. You own `networth/web/` only.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If the Skill tool refuses, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc.
2. `product.html` sections 06 (Showing our work), 09 (Web view) and 14 (The demo). `tech.html` section 08 (Web view).
3. `docs/phases/phase-1-report.md` and `networth/engine/odds.py`. Every number on every page comes from `odds()`, `compare()` or `position_range()` on `data/base_rates.sqlite`. Never compute a number in a template.
4. `~/.claude/CLAUDE.md` and `~/.claude/rules/web/*.md` are in force. Use the `frontend-design` or `impeccable` skill for the visual direction.

## What the pages are for

These pages are the demo's proof. A judge taps "Why?" and sees every past episode behind a number, with its date, its source link, its return and the normal-period rate next to it. They must be readable on a phone in 5 seconds and trustworthy at a glance.

## Build (you own these paths only)

| Path | What it does |
|---|---|
| `networth/web/routes.py` | A FastAPI `APIRouter` named `router`. Phase 3A mounts it. Server-rendered with Jinja2, no JS framework, no login. |
| `/why/{type}/{asset}` | **The Why card.** It shows the event type and asset in plain words, then the headline count ("Banks beat the market in 14 of 22 past RBI hikes. In a normal month, 56%."). It also shows the weak-signal label when it applies, every episode (date, headline, source link, return, hit or miss), the eras, the horizon, the excluded day-0 jump, and "What would change this view". A share button copies the URL. |
| `/what-if/{type}/{asset}?amount=100000&currency=INR` | An illustration in the user's money from `position_range()`: p10, median and p90 in rupees or dollars, Indian number formatting (₹1,00,000), and a dot per past episode against normal months. It's labelled history, not a forecast. |
| `/scoreboard/{type}` | Where history leans after this event type, across Indian and US sectors, from `compare()`. Green, grey or red by gap from baseline, and never ranked as "best to buy". |
| `/` | The landing page: the tagline, a real scoreboard sample from the engine, buttons for t.me/networth_professor_bot, and "Free. No account. Research, not advice." |
| `/track-record` | It renders from a `track_record` table if one exists. Otherwise it shows an honest empty state ("We start counting from our first message"). |
| `/stats` | Counts only: events, episodes, base rates, sources. No personal data. |
| `networth/web/__main__.py` | `python -m networth.web` serves the router alone on port 8090 for development and review. |
| `networth/web/templates/`, `networth/web/static/` | One stylesheet, design tokens on `:root`, light and dark themes, mobile first. |
| `tests/test_web.py` | Uses FastAPI's TestClient with a small fixture sqlite. Every page returns 200, every number on a page equals the engine's output, and an unknown type returns a friendly 404. |

## Not in this phase

Per-user pages with tokens (they come with the server in Phase 3B), the LLM, Telegram, the watcher, broker linking, any chart library over 50 kb, and any buy or sell wording.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. `uv run python -m networth.web` serves on port 8090, and `/`, `/why/rbi_hike/^NSEBANK`, `/what-if/oil_supply/JETS?amount=2000&currency=USD`, `/scoreboard/rbi_hike`, `/track-record` and `/stats` all return 200 from the real `data/base_rates.sqlite`.
3. `/why/rbi_hike/^NSEBANK` shows 22 episodes and 14 hits, matching `odds()`, and every episode has a working source link.
4. `/what-if/oil_supply/JETS?amount=2000&currency=USD` shows −$258, −$1 and +$211, matching `position_range()`.
5. A test proves no page contains "buy", "sell", "guaranteed" or "sure shot", and every page carries "Research, not advice".
6. The pages work at 320 px and 1440 px with no horizontal scroll. Screenshots for both are saved in `docs/phases/phase-4-shots/`.
7. Lighthouse or an equivalent check gives accessibility of 90 or more on `/why/...`. Contrast passes in both themes.
8. `docs/phases/phase-4-report.md` lists every route, the screenshots, how numbers flow from the engine to the page, known gaps and deviations.
9. Nothing secret is committed, and `data/` is not committed.

## The gate, branch policy and shared files

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 4 READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
