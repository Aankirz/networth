# Phase 6 · Plan range: a Monte Carlo of the user's own plan, built from real history

You are the **builder** for Phase 6 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check.

**You work in your own clone, not the shared tree.** Other builders (3B, 3C and Phase 5) are working in parallel.
- **You own** `networth/sim/` (new), `tests/test_sim*.py`, the new web routes and templates you add under `networth/web/` (add routes, don't rewrite existing ones), and `docs/phases/phase-6-*`.
- **Never edit** `networth/engine/`, `networth/bot/`, `networth/chat/` or `networth/app/`.
- **Expose one function** that the bot can call later. The coordinator wires it into Telegram after 3C lands.
- **The repo is public.** Never commit a secret, user data, `.env` or `data/`. Use `git commit -- <paths>` only.

## What the user gets

A user set up a plan in onboarding, for example "₹1,50,000 a month on the 1st, 10+ years, Balanced: 20% safety, 70% core, 10% growth, can sit through a 20% fall". Phase 6 shows them, in rupees:
- **What history says about their own plan.** Real past months are replayed in random 12-month blocks, 10,000 times. The result is the range of where the money could end up: a bad case (p10), the middle (median) and a good case (p90). Next to it are the total amount they put in and the same range after inflation.
- **What a fall feels like in their money.** In how many of the paths the plan fell by the amount they said they can sit through, or more. The typical worst fall in rupees. How many months the worst fall took to recover, in the middle case.
- **A plain label.** "This replays real past months. It is not a forecast. Your plan is your choice. Research, not advice."

**Only the user's own plan is shown.** Never put two plans side by side, never say one plan is better, and never suggest a change. If the user edits their own split, the range updates. That is the only comparison, and it's one the user chooses.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc. Note "The line we never cross", and that plans are shown "for education".
2. `networth/app/store.py` for `Profile` and `Plan`. Read the onboarding in `networth/bot/` to see what each plan bucket means: safety is FDs and liquid funds, core is broad index funds held for years, growth is single stocks and sectors.
3. `networth/engine/fetch.py`, `networth/engine/macro.py` (India CPI) and `docs/phases/phase-1-report.md` for which price series are cached and how.
4. `networth/web/` for the page style, tokens, Indian number formatting and the "Research, not advice" footer.
5. `~/.claude/CLAUDE.md` and `~/.claude/rules/web/*.md` are in force.

## Method (fix these choices and commit them in `docs/phases/phase-6-method.md` before you look at any output)

| Choice | Rule |
|---|---|
| **Bucket proxies** | **Core** is the Nifty 50 (`^NSEI`). Prefer a total-return index if a free, citable source exists. Otherwise use the price index and say plainly that dividends are left out, which makes the range conservative. **Growth** is the most broad, citable Indian mid or small cap index you can get with at least 15 years of monthly data. Name it and say why. **Safety** is a short-rate series for India (a 91-day T-bill or 3-month interbank rate, from FRED or RBI DBIE), turned into a monthly return. **Look up every series, cite its URL, and never guess a ticker or a series id.** |
| **Data window** | Monthly returns over the longest window every bucket has. Report the start and end months. |
| **Resampling** | Stationary block bootstrap of whole calendar months, so all buckets move together as they did in that month, with a mean block length of 12 months. 10,000 paths, and a fixed seed in config. |
| **Investing** | The monthly amount goes in on the user's investing day each month. The mix is rebalanced to the plan once a year. No taxes, fees or expense ratios. Say so, and say it makes the range optimistic by about the fund costs. |
| **Horizon** | From the profile: within 3 years is 3, 3 to 5 is 5, 5 to 10 is 10, 10+ is 15. Put this in config. |
| **Inflation** | Deflate with India CPI from `networth/engine/macro.py` over the same resampled months. Show both nominal and real ranges. |
| **Fall** | Peak-to-trough fall in portfolio value excluding new money (time-weighted). "Hit your limit" means a fall at or beyond the user's "fall you can sit through". |
| **Currency** | INR only for this phase. A user with a USD amount gets a polite "rupee plans only for now". |

## Build

| What | Details |
|---|---|
| `networth/sim/data.py` | Builds and caches the aligned monthly return table (safety, core, growth, CPI) under `data/sim/`. It uses `networth/net.py`'s deadline client (this network has broken IPv6) and fails loudly with one clear line if a series is missing. |
| `networth/sim/__init__.py` | `plan_range(plan, profile, *, paths=None, seed=None) -> PlanRange`, a pure function over the cached table. `PlanRange` is a frozen dataclass with: invested total; nominal and real p10, median and p90; the share of paths that hit the user's fall limit; the median worst fall in percent and in rupees; the median months to recover; the window; and the method version. It's deterministic for a seed. It runs in under 2 seconds for 10,000 paths and 15 years on this machine. Use numpy if it's already a dependency. Otherwise add it with `uv add` and say why. |
| `plan_range_lines(r: PlanRange, lang) -> list[str]` | Template sentences in English, Hindi and Hinglish, with numbers in Indian format (₹1,00,000, ₹1.2 Cr). No model writes these. They are fixed strings with the numbers filled in, so they pass `guard.check` against the `PlanRange` fields. Include the plain label. |
| **Web** | A section on `/u/{token}` that shows the user's own range. Add it through the existing template with a new include, and keep the change to the `/u` view small. Also add a public demo page `/plan-range?plan=balanced&amount=150000&years=15&fall=20` that renders the same thing for the three starter plans or a custom split. Add a small dot chart or range bar in inline SVG, under 50 kb with no chart library. It must pass the existing banned-word and disclaimer test. |
| **One bot-ready function** | `plan_range_message(user_id, store) -> str | None`, which the coordinator will later wire to a Telegram `/range` command. It returns None for USD or a missing plan. |
| `tests/` | No network: a small fixture return table. Covered cases:<br>- The same seed gives identical output.<br>- 100% safety gives a range close to the safety series compounded.<br>- A known constant-return table gives the closed-form answer.<br>- Fall math on a hand-built path.<br>- The invested total equals amount times months.<br>- Indian formatting.<br>- Every number in `plan_range_lines` passes `guard.check` against its source.<br>- `/plan-range` returns 200 and has no banned words.<br>- USD returns None. |

## Not in this phase

ML or any learned model, forecasts, ranking or comparing plans, suggesting a plan or a change, taxes and fees modelling, US or crypto buckets, Telegram wiring, and edits to the paths listed as not yours.

## Done when

1. `make check` passes from a clean clone after `uv sync` (with the cached table built by a documented command).
2. `docs/phases/phase-6-method.md` was committed before the first full run, and the report cites its hash.
3. Every series is cited with a URL, its window, and the dividend note if a price index is used.
4. `plan_range` for Balanced, ₹1,50,000 a month, 15 years and a 20% fall gives a full `PlanRange` in under 2 seconds, and the report shows it.
5. The sanity tests pass: the seed, all-safety, the constant table, and the invested total.
6. `/plan-range` and the `/u/{token}` section render at 320 px and 1440 px with no horizontal scroll, carry the label and "Research, not advice", and show only the user's own plan. Screenshots are in `docs/phases/phase-6-shots/`.
7. `plan_range_lines` in English, Hindi and Hinglish all pass `guard.check`, with samples in the report.
8. `docs/phases/phase-6-report.md` lists the method, sources, sample output, known gaps and deviations. Nothing secret is committed, and `data/` is not committed.

## The gate and branch policy

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 6 READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
