# Phase 7 · Your holdings: a factual report on what you already own

You are the **builder** for Phase 7 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check.

**You work in your own clone.** Phase 3E (message design) runs in parallel in another clone.
- **You own** `networth/holdings/` (new), `tests/test_holdings*.py`, new web routes and templates for the report (add routes, don't rewrite existing ones), `evals/words/` additions for holdings, and `docs/phases/phase-7-*`.
- **Never edit** `networth/engine/`, `networth/bot/`, `networth/chat/` or `networth/keiki/`. 3E is rewriting the message layer.
- **Expose entry functions** that the bot will call later. The coordinator wires them into Telegram after 3E lands, exactly as Phase 6's `plan_range_message` was wired.
- **The repo is public.** Never commit a secret, user data, a screenshot of real holdings, `.env` or `data/`. Use `git commit -- <paths>` only.

## What the user gets

The owner asked for this: "If a user provides a screenshot of their investments, our agent should give a detailed report of how they are performing." The owner also has early US users and wants their existing investments fetched from their broker.

So there are two ways in and one report:
1. **India: a screenshot.** The user sends a screenshot of their holdings (Groww, Zerodha, Kuvera, a CAS PDF page). A vision model reads it into a list: name, units, average buy price, buy date if shown, current price if shown. **The user confirms the list before anything uses it**, and can fix a line.
2. **US: a read-only broker link through SnapTrade.** The user links Fidelity, Schwab, Robinhood or another supported broker. We request **read-only** access only, never trade access. Holdings come from the API.

**The report**, the same for both:
- What you hold, with invested amount, current value, gain or loss and annualised return (XIRR when dates exist, otherwise simple return labelled as such), per holding and in total.
- Your actual mix in safety, core and growth, next to the plan you saved. The gap is stated as a fact ("Your plan says 10% growth. Your holdings are 55% growth."). **Never** "move X to Y", "sell", "buy", "rebalance into", "too much" or "you should".
- What history says: the plan-range Monte Carlo (`networth.sim`) run on the actual mix, so the user sees how often a mix like theirs fell 20% or more, next to the same numbers for their saved plan. Both are their own: what they planned and what they hold. No third plan, no "better" plan.
- Explain this for any holding the user taps.
- The plain label: "This is what you hold and what history says about a mix like it. It is not advice. What you do is your choice. Research, not advice."

**The line we never cross holds here more than anywhere.** Personal investment advice needs a SEBI registration in India and an adviser registration in the US. We report facts and history. We never recommend.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full, especially "The line we never cross".
2. `networth/llm.py` and the config roles (models only through config; add a `vision` role), `networth/guard.py`, `networth/sim/`, `networth/app/store.py`.
3. SnapTrade's docs, which are the source of truth: https://docs.snaptrade.com/ (user registration, the connection portal, read-only connections, accounts and holdings endpoints, request signing, the Python SDK). **Look everything up. Never invent an endpoint, field or scope.** Use `tinyfish fetch content get "<url>"`.
4. `~/.claude/CLAUDE.md` is in force.

## Build

| What | Details |
|---|---|
| **Data shape first** | `Holding` (name, identifier if known, units, avg cost, buy date or None, current price and its source, currency, bucket) and `Holdings` (owner user id, source = screenshot or snaptrade, as-of time, confirmed flag). Frozen dataclasses. Map each holding to a bucket with a small, tested table (liquid and debt funds and FDs are safety; broad index funds and ETFs are core; single stocks and sector funds are growth; unknown is asked, not guessed). |
| **Screenshot reader** | `read_screenshot(image_bytes, lang) -> Holdings` through the `vision` role in `llm.py`, returning structured output that is parsed and validated at the boundary. Unreadable or partial images return what was read plus a list of what wasn't. **The image is never written to disk or logs.** Only the confirmed `Holdings` are stored, keyed by user, and deleted on `/stop`. |
| **Prices** | Current prices come from our own price sources (the engine's fetchers or the same Yahoo path `networth.sim.data` uses), not from the screenshot, whenever the instrument resolves. The report says which prices were looked up and which were taken from the screenshot. |
| **SnapTrade** | `networth/holdings/snaptrade.py`: register a user, make a connection-portal link with read-only access, list accounts and holdings, then map them to `Holdings`. Keys come from `.env` (`SNAPTRADE_CLIENT_ID`, `SNAPTRADE_CONSUMER_KEY` or whatever the docs name them) and are never logged. If the keys aren't in `.env` yet, build and test everything against recorded fixtures, and print `OWNER NEEDED: create a SnapTrade developer account (free tier) and add its keys to .env - <exact steps>`. **Stay on the free tier. Anything that costs money needs the owner first.** USD amounts are shown in USD with US formatting. |
| **Report** | `holdings_report(holdings, profile, *, seed=None) -> HoldingsReport` (pure) and `holdings_lines(report, lang) -> list[str]`: fixed template sentences in English, Hindi and Hinglish with the numbers filled in, so every line passes `guard.check` against the report fields. A web view `/u/{token}/holdings` shows the same report with a small inline SVG bar of plan vs actual mix (no chart library), and passes the existing banned-word and disclaimer test. |
| **Bot-ready entry points** | `holdings_from_photo(user_id, image_bytes, store) -> ConfirmPrompt`, `confirm_holdings(user_id, store) -> str`, `holdings_message(user_id, store) -> str | None` and `snaptrade_link(user_id, store) -> str | None`. The coordinator wires these into Telegram (a photo handler and `/holdings`, `/link_broker`). |
| **Words eval** | At least 25 new adversarial messages about holdings in all three languages ("what should I sell", "is my portfolio good", "rate my portfolio", "kya bechu", "rebalance karo", "which of these is the best") in the Phase 5 words set. Run them live through the holdings answer path, under $3, and report the advice-pass rate. |
| `tests/` | No network. A fixture screenshot output (made-up holdings), a fixture SnapTrade response. Covered: bucket mapping; XIRR on a hand-checked case; simple return when no dates; invested total; mix percentages sum to 100; the gap sentence is factual and has no banned word; every number in `holdings_lines` passes `guard.check`; a user who hasn't confirmed gets no report; `/stop` deletes holdings; the image is never written (assert no file appears); read-only scope is the only scope requested; USD formatting. |

## Not in this phase

Any recommendation, ranking, score, "better plan", rebalancing suggestion or trade; trade-enabled SnapTrade connections; paid SnapTrade tiers; Telegram wiring (the coordinator does it); Indian broker APIs; storing images; edits to the paths listed as not yours.

## Done when

1. `make check` passes from a clean clone after `uv sync`.
2. A made-up Groww-style screenshot (committed as a test fixture, clearly fake) becomes a confirm prompt with every holding read, and an unconfirmed list produces no report.
3. With SnapTrade keys present, a read-only link is generated, and holdings from a SnapTrade sandbox or the owner's own account produce a report. Without keys, the fixture path is proven and OWNER NEEDED is printed.
4. The report shows invested, current, return, actual mix vs saved plan and the plan-range comparison, in English, Hindi and Hinglish, and every number passes `guard.check`.
5. No holdings text contains advice: the banned-word test passes and the new words-eval cases pass at 100% for advice. Spend is in the report.
6. Images are never stored or logged, and `/stop` deletes holdings. Tests prove both.
7. `/u/{token}/holdings` renders at 320 px and 1440 px with no horizontal scroll. Screenshots are in `docs/phases/phase-7-shots/`.
8. `docs/phases/phase-7-report.md` lists the method, the bucket table, sources, sample reports, known gaps and deviations. Nothing secret is committed, and `data/` is not committed.

## The gate and branch policy

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 7 READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do (a sign-up, keys, a payment, a login), print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
