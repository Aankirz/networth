# Phase 3D report: fixes from the evals, Jev back on, `/range`, and two live bugs

The brief is `docs/phases/phase-3d-fixes.md`. Findings 1 to 4 from `docs/phases/phase-5-findings.md` are applied. Jev picks the chat intent again. Telegram has `/range`, a plan-range chat intent and a "My range" button. The coordinator reported two live bugs during the phase, and each has its own `fix:` commit. Finding 5 (lean wording, `LEAN_GAP`, `lean()`) is untouched, as the brief asks. No engine file changed.

## Commits

| Commit | What |
|---|---|
| `fix: read the plan range table from the app's data dir, not /app/data` | Live bug 1. The plan range table now follows `DATA_DIR`. |
| `fix: tell the news judge a paused or delayed action is not the event` | Finding 4. |
| `feat: apply phase 5 findings 1 to 3, turn Jev back on and add /range` | Findings 1 to 3, Jev, `/range`. |
| `fix: rewrite a same-day brief after the user edits their profile` | Live bug 2. A same-day `/brief` now picks up profile edits. |
| `docs: phase 3D eval rerun, findings status and report` | Eval results, Phase 5 report and findings, 3B decision log, this report. |

## Changes

**Finding 1.** `TRANSLATE_TASK` (`networth/chat/answer.py`) now says: "Write any instruction about using the app as a statement ('/plan se badal sakte hain'), never as a command." The guard is unchanged. The live rerun showed that tip verdicts are rewrites, not translations, and those writer drafts still failed on `karein`. So `REWORD_TASK` also got one sentence: "Write every sentence as a statement, never as a command, polite forms included." That is a deviation, covered below.

**Finding 2, option (a).** In `deliver`, a translation whose template already fails `guard.check(template, source)` sends the template with no model call, and logs the verdict as `template`. This only applies to translations, where `task` is None. A reworded reply writes new prose from the source, so it can pass where its template fails, and it still gets both writer attempts. The reviewer caught this. The first version skipped the model for rewrites too.

**Finding 3.** Plan replies open with a fixed line, `today.NOT_A_JUDGE`, carried on the new `Answer.lead` and put in front of whatever `deliver` produces:
- English: "I can't tell you whether a plan is right for you. Here's what you saved."
- Hindi: "मैं नहीं बता सकता कि कोई प्लान आपके लिए सही है या नहीं। आपने यह सेव किया है।"
- Hinglish: "Main nahin bata sakta ki koi plan aapke liye sahi hai ya nahin. Aapne yeh save kiya hai."

All three pass `guard.check`. The summary's own "Here's what I have." is dropped, so the reply has one opening line, not two. A plan question that names an event type gets that type's history line, but only when the type is confirmed this month, as in "RBI hiked, what do I do with my SIP". The type pick is a paid call, so it is skipped when this month has no events.

**Finding 4.** `CLASSIFY_INSTRUCTIONS` (`networth/llm.py`) lists "a pause, delay, suspension or rollback of the action" among the things that are not the event. The paragraph was re-wrapped to stay under 100 columns, and no other word changed.

**Jev back on.** `use_jev_for_intent = true` in `config.toml`, with the comment rewritten to the new rule. The rule now compares the production path (Jev when it is at least 0.7 sure, otherwise the cheap model) with the cheap model alone. The cheap-model fallback is unchanged. The decision is recorded in `docs/phases/phase-3b-report.md` (end of the held-out section) and in `docs/phases/phase-3b-decisions.tsv`.

The reviewer pointed out that the 3B held-out score predates the new `plan_range` criterion. So `uv run python -m evals.intent_accuracy heldout` was rerun with the new criteria, and the result is saved as `evals/intent_results_heldout_3d.json`. The 3B file is left as it was.

| Picker, held-out (24) | 3B run | 3D run, new criteria |
|---|---|---|
| Production path | 24/24 | 24/24 |
| Cheap model | 24/24, median 1,230 ms | 24/24, median 1,249 ms |
| Jev alone | 23/24, median 380 ms | 23/24, median 399 ms |
| Jev confident (at least 0.7) | 22 of 22 right | 22 of 22 right |

**`/range` in Telegram.**
- `/range` (`networth/bot/commands.py`). Fixed sentences, so there is no model call and no hourly chat claim. The replay runs after the update lock.
- The `plan_range` intent. "what could my plan become", "how bad can a fall get" and the Hindi and Hinglish forms. Its criterion is in `networth/chat/__init__.py`, and phrase rules cover the no-model path.
- A "My range" button next to "My page" on the brief (`networth/brief/__init__.py`). It is a callback, `br:range`.
- All three answer through `today.plan_range`, which calls `sim.plan_range_message(user_id, store, lang)`. `lang` is new and optional. Chat replies follow the language the user writes in, and `/range` follows the saved language.
- A USD plan, or a missing plan, amount or horizon, gets `today.NO_RANGE` in the user's language. A missing table gets `today.RANGE_NOT_READY`.
- The range is sent as written (`Answer.written`), so no model rewords it. Tests check that it passes `guard.check(text, repr(PlanRange))` in all three languages.

**Live bug 1: the plan range table ignored `DATA_DIR`.** `networth/sim/config.py` built `SIM_DIR` from the repo's `data/`, so the VM read `/app/data/sim`. `config.sim_dir()` now uses `Settings.from_env().data_dir`, the same data dir the app uses: `DATA_DIR` from the environment or `.env`, otherwise `data/`.
- `scripts/push_data.sh` accepts `sim/returns.csv` and `sim/sources.json`. They are copied as they are, while databases keep the sqlite snapshot.
- `docs/deploy.md` has a new "Plan range table on /data" section.
- Both files are on the VM. `scripts/push_data.sh sim/returns.csv` confirmed sha256 `e116065a…` inside the VM, and `sim/sources.json` confirmed `89b466f1…`. `ls /data/sim` shows both, and `DATA_DIR=/data` there.
- Nothing reads `/data/sim` until this code is deployed.

**Live bug 2: a same-day `/brief` ignored profile edits.** The briefs row has a new `inputs` column, added by the existing migrate step. It holds a 16-character sha256 key of the fields the brief is written from: language, goal, horizon, fall, amount, currency, investing day, markets, exclusions, time zone, and the plan's name, split and fall. A same-day `/brief` resends the stored text only while the key matches and no news check is newer. Otherwise it writes the brief again.

The day's claim is not touched, so a scheduled run still returns early after the first brief. A key was chosen over a timestamp because the profile is stamped with the update's clock and the brief with the wall clock. Rows written before this change have an empty key, so each user's next same-day `/brief` is written fresh once.

## Tests

`make check`: 605 passed in this clone after rebasing on `ac158d8`. From a fresh `git clone` with no `data/` and no `.env`, after `uv sync`, `make check` passes at each of the five commits (567, 568, 592, 593 and 593 passed, 12 skipped each). The skips are older engine and real-database tests that need built data. `make evals` passes at HEAD and leaves the tree clean.

| Test | Covers | Red before its fix |
|---|---|---|
| `test_a_translation_tells_the_writer_app_instructions_are_statements` | finding 1 | yes |
| `test_a_reworded_reply_tells_the_writer_to_use_statements` | finding 1, rewrite sentence | written with the fix (deviation) |
| `test_a_hinglish_hyped_tip_skips_the_writer_it_could_never_pass` | finding 2, no model call | yes |
| `test_a_reworded_reply_with_a_failing_template_still_asks_the_writer` | review fix to finding 2 | not run red; it pins the narrowed rule |
| `test_a_plan_question_leads_with_the_fixed_line` (en, hi, hinglish) | finding 3 | yes |
| `test_a_plan_question_about_this_months_event_adds_its_history_line` | finding 3, event line | yes |
| `test_the_news_judge_is_told_a_paused_action_is_not_the_event` | finding 4 | yes |
| `test_jev_is_on_in_the_shipped_config` | Jev on | yes |
| `test_jev_down_falls_back_to_the_model`, plus the existing unsure-pick and Jev-off tests | fallback | passed before (the fallback already existed) |
| `test_range_command_sends_the_plan_range_in_the_users_language` (3 languages) | `/range`, guard | yes |
| `test_a_plan_range_question_answers_with_the_range` (3 languages), `..._routes_by_phrase_without_models` | intent | yes |
| `test_a_dollar_plan_gets_the_polite_range_line` | USD | yes |
| `test_the_polite_range_lines_pass_the_guard`, `test_a_missing_range_table_says_the_range_is_not_ready` | polite lines | yes for `NO_RANGE`; the table test was added after review |
| `test_the_brief_has_a_my_range_button_next_to_my_page` | button and its tap | yes |
| `test_the_table_is_read_from_the_data_dir_the_app_uses` | live bug 1 | yes |
| `test_a_language_change_reaches_the_same_day_brief` | live bug 2, and the proactive cap | yes (it got the Hinglish brief again) |

Three existing tests changed:
- The routing table expects the new plan line and a `plan_range` row, and its test now patches the sim table so it never reads `data/`.
- `test_jev_is_not_asked_when_config_turns_it_off` turns Jev off explicitly, since the shipped config now has it on.

## Evals: before and after

`uv run python -m evals --live words news`. Full tables are in `docs/phases/phase-5-report.md`, which now opens its results with a before-and-after section. Words ran twice. Run A used the first version of the fixes, before review. Run B used the committed code, and its tables are the ones in the report.

| Eval | Measure | Before | After (run B) |
|---|---|---|---|
| News | Pipeline precision | 29 of 30 | 29 of 29 |
| News | False confirms | 1 | 0 |
| News | Judge alone, false positives | 8 | 5 |
| Words | Passed every grade | 78 of 86 | 78 of 86 (run A: 79) |
| Words | No advice or score | 81 | 81 (run A: 83) |
| Words | Right language | 81 | 83 (run A: 82) |
| Words | No invented number | 86 | 86 |
| Words | Sent as the template | 4 | 2 |

**What the live evals show.**
- **Finding 4: fixed.**
- **Finding 2: works as designed.** No writer call, and the reply is still in English, as option (a) says.
- **Finding 1: partly fixed.** The Hindi and Hinglish plan replies keep their language. The Hinglish IPO tip still drafts `karein` twice, so it falls back to English.
- **Finding 3: not fixed by the judge's measure.** The fixed line is on every plan reply, and 2 of the 5 original failures now pass. With Jev on, 3 more messages were picked as plan questions (9, up from 6). 5 plan replies still fail, because the judge quotes the saved split as an allocation.

## Spend

The rerun cost $1.1957, under the $3 cap. That covers news $0.34, words run A $0.45, words run B $0.41, Jev picks, search, and the held-out intent rerun. These are rows 335 to 701 of this clone's `data/llm_calls.jsonl`. The Phase 5 calls were logged in another clone. So `evals/results/summary.json` and the Phase 5 spend line carry the sum: $1.2206 + $1.1957 = $2.42 of $15. In this clone, `make evals` would rewrite that line to this clone's count. From a clean clone it keeps $2.42.

## Deviations

- **The rewrite task got a statement-only sentence too.** The brief named only `TRANSLATE_TASK`. Finding 1's own IPO example is a rewrite, so the translation sentence could not reach it. It still did not fix that row.
- **The finding 2 skip is limited to translations.** Option (a) as written applies to any template. A rewrite can pass where its template fails, so skipping it would have dropped good drafts.
- **Words was run twice.** The first live run used code from before review.
- **Commits go to `main`.** That is this repo's phase policy (`phase-5-evals.md`), and every earlier phase did the same. `~/.claude/CLAUDE.md` says never commit to `main`. The repo's own policy was followed, and this note flags it.
- **`.claude/CHANGELOG.md` already holds three diff3 conflict markers (`|||||||`) from earlier rebases, including one in upstream `ac158d8`.** The changelog rule says append only, so they are left in place.
- **The live bug 1 fix also pushed data.** `/data/sim` on the VM was written with `scripts/push_data.sh`. This is additive, and nothing reads that path until the deploy.

## Open for the owner

- Finding 3. Either leave the saved split out of replies to "is my plan right" questions, or accept that the rubric reads it as an allocation.
- Finding 1's leftover. The Hinglish tip rewrite still produces `karein`. The guard log keeps only the problems, so the sentence that triggered it is unknown.
- Finding 5, as before.
- The deploy. Live bug 1 needs it before `/range` and `/plan-range` read `/data/sim`. The hand copy in `/app/data/sim` disappears with it, and that is fine once this code is live.

OWNER NEEDED: deploy Phase 3D - `npx maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json`, then wake it with `curl https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/health` and check that `/plan-range?plan=balanced&amount=150000&years=15&fall=20` returns 200 and `/range` answers in Telegram.
