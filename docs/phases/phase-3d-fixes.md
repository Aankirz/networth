# Phase 3D · Fixes from the evals, Jev back on, and `/range` in Telegram

You are the **builder** for Phase 3D of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check.

You work in this clone (`~/Desktop/networth-p6`). Run `git pull --rebase` first: 3B, 3C, 5 and 6 are all on `main`. **Never edit `networth/engine/`.** **The repo is public, so never commit a secret, user data, `.env` or `data/`.** Use `git commit -- <paths>` only. If a push needs credentials, the clone's local credential helper already has them. Don't run `gh auth login` and don't change git config.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md`.
2. `docs/phases/phase-5-findings.md`: fix findings 1 to 4 exactly as described. **Finding 5 (lean wording) is waiting on an owner decision. Don't touch `LEAN_GAP`, `lean()` or any lean wording.**
3. `docs/phases/phase-3b-report.md`, the held-out Jev section.
4. `docs/phases/phase-6-report.md` for `plan_range_message`.
5. `~/.claude/CLAUDE.md` is in force.

## Build

| What | Details |
|---|---|
| **Finding 1** | Add the sentence to `TRANSLATE_TASK` as written in the findings: instructions about using the app are statements, never commands. Keep the guard as strict as it is. |
| **Finding 2** | Option (a): in `deliver`, skip the model and send the template when `guard.check(template, source)` already fails. Add a test that no model call is made. |
| **Finding 3** | Start the plan-question reply with the fixed line: "I can't tell you whether a plan is right for you. Here's what you saved." Write it in English, Hindi and Hinglish. A question like "RBI hiked, what do I do with my SIP" should still get this line, plus the event's history line if the event is confirmed this month. |
| **Finding 4** | Add "a pause, delay, suspension or rollback of the action" to the not-the-event list in `CLASSIFY_INSTRUCTIONS`. |
| **Jev back on** | Set `use_jev_for_intent = true`. The rule compares the production path (Jev when it's at least 0.7 confident, otherwise the cheap model), which scored 24 of 24 on the held-out set, the same as the cheap model alone, and about 3 times faster. Record this in the 3B decision log and the report. The cheap-model fallback must stay. |
| **`/range` in Telegram** | Add a `/range` command, and a `plan_range` chat intent for questions like "what could my plan become" or "how bad can a fall get". Both call `plan_range_message`. Also add a "My range" button next to "My page" on the brief. A USD or missing plan gets the polite line. The reply passes `guard.check`. |
| **Rerun the evals** | Run `uv run python -m evals --live words news` (paid, under $3). Update `docs/phases/phase-5-report.md` results with before and after, and mark each finding fixed in `phase-5-findings.md`. |
| `tests/` | One test per fix, failing before the fix. Plus `/range` routing, the button, and the USD case. |

## Not in this phase

Lean wording or `LEAN_GAP` (owner decision pending), Keiki changes beyond routing the new intent, deploys, and engine edits.

## Done when

1. `make check` and `make evals` pass from a clean clone.
2. Each of findings 1 to 4 has a test that failed before its fix, and the live words and news evals show it fixed.
3. Jev is on, with the fallback tested, and the decision is recorded.
4. `/range` and the plan-range intent work in tests, in English, Hindi and Hinglish.
5. `docs/phases/phase-3d-report.md` lists every change, the eval before-and-after numbers, the spend and any deviations. Nothing secret is committed.
6. A deploy is OWNER NEEDED. Print the exact command and don't run it.

Finish with `PHASE 3D READY FOR REVIEW` as the last line.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
