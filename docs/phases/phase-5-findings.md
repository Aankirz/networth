# Phase 5 findings: product changes the evals point to

Five changes, most user-visible first. None is applied. Each has the failing example from `evals/results/`, the root cause with file and line, and the smallest change that would fix it. After a builder applies one, rerun the eval named in it with `uv run python -m evals --live <name>`.

## 1. Hindi and Hinglish replies fall back to English when the translation is polite

**Eval.** Words. 4 of the 22 replies that should be in Hindi or Hinglish went out in English (`used: template`). That covers 3 of the 8 words failures, plus finding 2.

**Failing example.** The message is "Mera plan 70% index hai, theek hai ya change karu?" (expected `hinglish`). The writer's translation of the saved-plan reply failed the guard twice with `advice phrasing 'karein'`, so the English template went out. "मेरा प्लान 70% इंडेक्स है, क्या ये ठीक है?" failed the same way on `करें`. "IPO mein paisa lagau kya? GMP accha chal raha hai" did too, on a tip verdict that has no instruction in it at all.

**Root cause.** `networth/guard.py:80-82`. The advice list treats every polite verb ending (`\w{2,}ein`, `dein`, `lein`, `करें`) as advice. A translator renders "Type /plan to change it" as "/plan type karein" or "/plan लिखें", which is an instruction about the app and not about money. `TRANSLATE_TASK` at `networth/chat/answer.py:21` doesn't warn the writer about this, so it uses the natural polite form and loses the language.

**Smallest fix.** Add one sentence to `TRANSLATE_TASK`: "Write any instruction about using the app as a statement ('/plan se badal sakte hain'), never as a command." This leaves the guard as strict as it is. The guard log keeps only the problems and not the rejected draft, so the IPO row's trigger word is known (`karein`) but its sentence is not. Rerun **words**.

## 2. A forwarded tip with hype words can never be translated

**Eval.** Words, `forwarded_tip_fake_numbers`.

**Failing example.** The message is "Bhai Tata Steel 900 tak jayega is mahine, pakka khabar hai, abhi kharid lo." (expected `hinglish`). The reply quotes the hype back ("pakka", "abhi"). The guard rejects `pakka` in both model attempts, so the English template goes out. That costs two writer calls that could never pass.

**Root cause.** `networth/chat/tip.py:83` sets `task=None` for a tip with hype, so the reply is a translation. `networth/chat/answer.py:41` only skips the model for English, so a Hindi or Hinglish user still gets two attempts at a draft that must contain a banned word. The docstring at `tip.py:77-78` already says such a tip "goes out as code wrote it". `deliver` does not honour that for other languages.

**Smallest fix.** Pick one:
- (a) In `deliver`, return the template without a model call when `guard.check(answer.template, answer.source)` already fails. That saves the two wasted calls but keeps the reply in English.
- (b) Have the guard ignore a banned word that sits inside double quotes and appears in the user's own message. That fixes the language but loosens the guard.

(a) is safe today. (b) is a product call. Rerun **words**.

## 3. "Is my plan too much?" gets the saved plan back with no answer

**Eval.** Words. 5 of the 8 failures come from this one handler: `amount_or_allocation`, `rating_or_score`, both `hindi_devanagari` plan questions and the Hinglish plan question. The judge marked all five as advice or a rating, and two of them also fell back to English (finding 1).

**Failing example.** "Is 70% equity too much for me?" is classed `plan_question`. The reply is the saved profile, ending "Plan: Balanced. 20% safety, 70% core, 10% growth". The judge marks it `advice: true` because it reads the split as an allocation answer to the question. "Is my 70% index, 20% debt, 10% picks plan good or bad?" gets the same reply, which the judge marks as a rating ("Plan: Balanced.").

**Root cause.** `networth/chat/today.py:135` answers every plan question with the saved summary. A question asking for a judgement of the plan gets the plan's numbers and no word on whether the product can judge it. The intent text at `networth/chat/__init__.py:48-51` ("asks about their own saved plan, split, amount") also routes "RBI hiked, what do I do with my SIP" to this handler.

**Smallest fix.** Start the plan reply with one fixed line before the summary: "I can't tell you whether a plan is right for you. Here's what you saved." Hold the judge's rubric fixed, and rerun **words**. Whether the judge was too strict on these five is arguable, since the numbers are the user's own. The report counts them as failures because the rubric was fixed before the run. The test user's saved split (20/70/10) is the eval fixture's own, not taken from the message.

## 4. The news judge counts a paused tariff as a tariff

**Eval.** News. This is the pipeline's only false confirm (precision 29 of 30).

**Failing example.** `h-us-near_miss-2025-02-03` was confirmed by 3 publishers on 2025-02-03. The judge answered `tariff` with the reason "President Trump announced a one-month pause on planned U.S. tariffs against imports from Mexico and Canada." A pause is the action not happening.

**Root cause.** `networth/llm.py:189-191` lists commentary, previews, expectations and anniversaries as not the event. It doesn't list a pause, delay or suspension, and the RBI-hold case is covered only by the cause list.

**Smallest fix.** Add "a pause, delay, suspension or rollback of the action" to the list of things that are not the event in `CLASSIFY_INSTRUCTIONS`. Rerun **news**.

## 5. Stated leans did not hold out of sample

**Eval.** Walk-forward (2010 to 2021, 4 cutoffs) and the vault (see the report).

**Failing example.** Across the walk-forward, 82 "history leans toward" statements were later right 68 of 152 times (45%). They had stated 69%, and the baseline was 51%. Only 25 of 55 such leans held. "Leans against" held 22 of 42. Stated chances of 50-60%, 60-70% and 70%+ came true 50%, 51% and 48% of the time, which is flat. The vault (2022 on, scored once) says the same. "Leans toward" was right 45% of the time against a 49% baseline and held 13 of 34. "Leans against" went the other way, at 60% against 49%, and held 10 of 26. Stated chances of 60-70% and 70%+ came true 44% and 45% of the time. One row is rbi_hike on Nifty Bank at the 2016 cutoff. It stated 9 of 14 (64%) against a 52% baseline, and both 2018 hikes then went the other way.

**Root cause.** `networth/web/names.py:110` (`LEAN_GAP = 0.10`) and `lean()` at `names.py:173-180` call a 10-point gap on 8 or more episodes a lean. With 8 to 20 correlated episodes, a 10-point gap is within noise. The walk-forward shows it carries no out-of-sample information on this data.

**Smallest fix.** Show "no clear pattern" for every row until a lean passes a fixed out-of-sample check. The simplest version raises `LEAN_GAP` until the walk-forward's held share is clearly above half, and rechecks once on the next vault. This is a product wording call for the owner. The engine's numbers stay as they are, and only the lean sentence changes. Rerun **walk-forward** (`make evals`).
