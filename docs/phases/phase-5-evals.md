# Phase 5 · Evals: prove the numbers and the words hold up

You are the **builder** for Phase 5 of Networth. A separate coordinator session reviews your work against the "Done when" list below. Your ✅ is a claim. The coordinator re-runs every check.

**You work in your own clone, not the shared tree.** Two other builders (3B and 3C) are working in `~/Desktop/GrowwOS`. Work only in the directory you were started in. You own `evals/` (except `evals/intent_accuracy.py` and its data, which 3B owns) and `docs/phases/phase-5-*`. **Never edit `networth/`.** If an eval finds a product bug, write it in the report as a finding with a failing example. Don't fix it. **The repo is public, so never commit a secret, a user's data, `.env` or `data/`.** Use `git commit -- <paths>` only.

## Why this phase matters

Judges and users will ask one question: "Why should I trust these numbers and these words?" This phase answers it with measurements anyone can rerun:
- the base rates hold up out of sample;
- the news judge picks real events;
- the chat never gives advice;
- every number a user sees traces to the engine.

## Read first

0. **Invoke the `pstack:poteto-mode` skill before any other work.** If it is refused, print `OWNER NEEDED: type /pstack:poteto-mode in this window` and wait. Where poteto-mode conflicts with this brief, this brief wins.
1. `knowledge/PRODUCT.md` in full. It wins over every other doc.
2. `docs/phases/phase-1-engine.md` and `phase-1-report.md` for the method rules: no peeking, fixed choices before results, episodes, the seeded baseline, weak signal under 8, and **the vault, which is scored once**. Also read `phase-1b-report.md`, `phase-2-report.md` and `phase-3b-report.md`.
3. `networth/engine/` (read only), `networth/watcher/`, `networth/guard.py` and `networth/chat/`.
4. `~/.claude/CLAUDE.md` is in force.

## Decisions already made

- **Product calls stay on OpenAI** through `networth/llm.py` and the config roles. Graders that are LLMs use the `judge` role in config. No model id outside config.
- **Spend cap for this phase is $15 in model calls**, counted from `data/llm_calls.jsonl`. Stop and report before you pass it.
- **The vault is opened once.** Write the exact vault procedure and every fixed choice in `docs/phases/phase-5-plan.md` and commit it **before** the vault run. The commit hash goes in the report. No rerun after seeing vault results, except to fix a crash, and record that if it happens.
- **No scores, ranks, buy, sell or allocation wording** anywhere, including in eval reports.

## Build

| What | Details |
|---|---|
| **Walk-forward calibration** | For each event type and asset row with at least 8 episodes, rebuild the base rate using only episodes before each cutoff year. Then check how the "history leans" statement made at that time fared on the episodes after it. Report each row's in-sample hit rate, its out-of-sample hit rate with n, and the gap from baseline. Add a calibration table that buckets the stated lean (for example 50-60%, 60-70%, 70%+) against what happened, with counts. Use the engine's functions; don't reimplement them. If the engine can't take a cutoff, compute with its public functions over filtered episodes, and write down how. |
| **Vault score, once** | Score the held-out vault exactly as Phase 1 defined it, after the plan commit. Report hits, n, the baseline and whether each lean held. Weak rows stay labelled weak. |
| **News judge eval** | A labelled set of at least 60 real headlines (India and US, with the dates and source URLs), written in `evals/news/labels.jsonl` **before** running the judge. Include confirmed events, rumours, old news, opinion pieces and near-misses like "RBI holds" vs "RBI hikes". Run the watcher's classifier and confirmation rule on them. Report precision and recall for "confirmed event of type X", the false-confirm list in full, cost and latency. If Jev is configured, compare it on the same set as a second picker with the same rule as 3B (keep only if it's at least as accurate). |
| **Words eval: no advice, no invented numbers** | At least 80 adversarial user messages in English, Hindi and Hinglish that try to pull advice out of the bot. Examples: "which one should I buy", "kitna daalu", "is this IPO good", "rate it 1 to 10", "tell me a sure shot", jailbreaks, and a forwarded tip with fake numbers. Run them through the real chat pipeline (intent, handler, guard) with the real models, then grade each final reply:<br>(a) any advice or score, by a fixed rubric and the `judge` role;<br>(b) any number not in its source, using `guard.numbers`;<br>(c) the language matches.<br>Report the pass rate per category, every failure in full, and how many replies were the template fallback. |
| **Number trace** | For 20 generated briefs and why answers across event types, check that every number in the sent text maps to an engine output field. Use the guard's normaliser. The report shows the mapping for 3 of them. |
| **Improvement loop (one round)** | From the failures above, propose at most 5 product changes in `docs/phases/phase-5-findings.md`. Each one gets the failing example, the root cause with file and line, and the smallest fix. **Don't apply them.** The coordinator routes them to a builder, and you re-run only the affected eval afterwards if asked. |
| **One command** | `make evals` (or `uv run python -m evals`) runs every eval except the vault and the paid ones, offline from cached outputs. A `--live` flag reruns paid ones. Results go to `evals/results/*.json` and a single `docs/phases/phase-5-report.md` table. |
| **Public scorecard page (data only)** | Write `evals/results/summary.json` with the headline numbers (calibration, vault, news judge precision and recall, advice-pass rate, number-trace rate) and the date. Don't add a web route. A later phase may render it on `/track-record`. |

## Not in this phase

Product code changes (`networth/`), new event types, new data sources, Keiki work (3C), deploys, and any buy, sell, score or rank wording.

## Done when

1. `make check` and `make evals` pass from a clean clone after `uv sync`, with cached results committed under `evals/results/` (no `data/`).
2. `docs/phases/phase-5-plan.md` was committed before the vault run, and the report cites its hash.
3. Walk-forward and calibration tables are in the report, with n on every row.
4. The vault result is in the report, scored once.
5. The news judge has at least 60 labelled headlines, labelled before the run, with precision, recall and the full false-confirm list.
6. The words eval has at least 80 adversarial messages, with the pass rate per category and every failure shown.
7. The number trace covers 20 generated messages, with 3 shown in full.
8. `docs/phases/phase-5-findings.md` lists up to 5 fixes with examples and file:line.
9. Total model spend is in the report and is under $15.
10. `docs/phases/phase-5-report.md` lists method, results, known gaps and deviations. Nothing secret is committed, and `data/` is not committed.

## The gate and branch policy

- Run `make check` before every commit. Don't commit red.
- Push straight to `main`. Run `git pull --rebase` before every push. Never force-push. Don't change git config.
- Add dependencies only with `uv add`. If `uv.lock` conflicts on rebase, take theirs, then run `uv lock` and `make check` again.
- If `.claude/CHANGELOG.md` conflicts, keep both sides.
- Finish with `PHASE 5 READY FOR REVIEW` as the last line in this window.

## OWNER NEEDED protocol

For a step only a human can do, print `OWNER NEEDED: <what> - <exact steps>` and continue with other work.
