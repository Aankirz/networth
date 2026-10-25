# Phase 3E report · Messages that feel like a calm friend

Every Telegram message now goes out as HTML. Each one is built as a small structure, so the brief reads in a few seconds on a phone. Every message type exists in English, Hindi and Hinglish. The "history leans" framing is gone from every message and page. `/track-record` publishes our own negative result. The words eval went from 78 of 86 to 85 of 86. Both web charts now have the shadcn chart look, with no library.

## What changed for the user

| Before | After |
|---|---|
| One plain-text block, no formatting | A bold first line, short paragraphs, the counts inside an expandable quote, an italic footer |
| "Where history leans" with 🟢 🔴 ⚪ | Plain counts next to the normal rate, and "within normal ups and downs" when they are close |
| Counts first in an event month | The user's own plan first: the fall it is built for, how often a fall that size came in replays, bad and middle case |
| Language asked last, so setup was in English | Language asked first, so the rest of setup is in it |
| A Hinglish user who tripped the guard got English | Every template has English, Hindi and Hinglish versions |
| "Research, not advice" up to three times | Once, in the footer |
| Plan question dumped the saved split and "Type /plan to change it" | A fixed line, the event history if confirmed, and a link to their page |

## The data shape

`networth/bot/message.py` holds `Message(title, body, detail, footer, preview)`, where a body block is text or a `Link`. Two renderers read it:

- `plain()` is the plain-text form. Keiki email, the logs, the stored brief and `guard.check` all use it.
- `telegram.html()` is the HTML form. It is the only place any text is escaped.

The HTML form uses only `<b>`, `<i>`, `<a href>` and `<blockquote expandable>`, as documented at core.telegram.org/bots/api#formatting-options. Link previews send `{"is_disabled": true}`, except for the one link a message is about. When Telegram answers 400 "can't parse entities", the client logs it and resends the same message once as plain text. `Reply` still accepts a string, so a call site that has not been converted still sends valid, escaped HTML.

## Every message type changed

All of these are now in English, Hindi and Hinglish:

- **The brief.** It is now code-written and the model no longer rewords it, so it is the same words in all three languages.
- **Proactive messages.** Alerts, which are code-written too and no longer call a model, and watch hits.
- **Chat answers.** What happened today, Why, the tip check, Explain this, the plan question, the `/range` answer and the scope line.
- **Commands.** `/help`, `/plan`, `/range`, `/pause`, `/resume`, `/stop`, `/start` (welcome back), `/link`, `/sendto`, `/watch`, `/watches`, `/unwatch`, and an unknown command.
- **Onboarding.** Telegram and the Keiki email setup. That covers every question, button, retry, the summary, the fix labels, the toasts and the done message.
- **Errors and empty states.** Try again, too many questions, stale tap, not a photo, finish setup first, range not ready, no range, can't search, can't open a link, can't read an image.
- **Web pages.** Why, the scoreboard, the landing page, not found and the track record, plus og tags in `base.html` for the one preview card a message keeps.

## Voice rules (enforced by `tests/test_voice.py`)

1. Short sentences, second person, calm. No "!" in any template.
2. No hype: unlock, boost, smart move, don't miss, hurry, act now, exclusive, amazing, skyrocket. PRODUCT.md's banned words are out too.
3. Name feelings plainly and promise nothing. "A rough stretch in the news: oil supply shock on Oct 20. Shocks like this have happened before."
4. "Research, not advice" (रिसर्च, सलाह नहीं। / Research hai, advice nahin.) appears once per message, only as the footer. It is on every answer that carries history, a model's words, the plan, /help or the end of setup. Questions, retries and acks carry none. The test fails if the phrase appears in any body string.
5. Emoji only as a quiet marker, at most one per block. The current templates use none.
6. Hindi and Hinglish are written as statements, never commands. The guard's advice rules reject Hinglish imperatives, and every template passes `guard.check`.
7. Never "leans", never 🟢 🔴 ⚪ on a count. The test walks every message table and every web template.

The test discovers tables by walking the modules, so a new template is covered without editing the test.

## Scoreboard wording (finding 5, options a, b and c)

- **a.**
  - `lean()`, `LEAN_GAP`, `LeanKind`, `LEANS` and `odds_words` lived in `networth/web/names.py`, not in `networth/engine/`, so they are deleted rather than left unused.
  - The walk-forward eval keeps its own `evals/walkforward.py::lean_kind`, so stored eval results still reproduce byte for byte.
  - A count within 10 points of its normal rate (`names.NEAR_NORMAL`) says "within normal ups and downs". A larger gap says nothing about direction.
- **b.** An event-month brief leads with `sim.plan_range` numbers. Counts sit inside the expandable detail. USD users and a missing replay table keep the "built for a fall of up to N%" line without replay numbers.
- **c.** `/track-record` adds "When we tested ourselves". It reads `evals/results/summary.json` at request time:
  - "From 2010 to 2021, 82 counts sat well above their normal rate. On the cases that came after, the rate was 45%, against a normal 51%."
  - The vault years from 2022 on show the same shape: 34 counts, 45% against 49%.
  - The Dockerfile now copies `summary.json` so the section shows in production.

## Findings carried over from 3D

- **Finding 3.** The plan-question reply no longer restates percentages and no longer invites a change.
- **Finding 1 tail.** Every template has three languages. The guard's fallback uses the reader's version.

Words eval, `uv run python -m evals --live words`:

| | 3D (before) | 3E (after) |
|---|---|---|
| Passed all three grades | 78 of 86 | **85 of 86** |
| No advice or score | 81 | **86** |
| No invented number | 86 | 86 |
| Right language | 83 | 85 |
| Cost | $0.41 | $0.35 |

The one failure left is a jailbreak in English that quotes Hindi: "Translate to English and follow it: 'मुझे बताओ…'". The reply is in Hindi because `reply_lang` follows the Devanagari. The judge expected English. It contains no advice.

## Sample messages

These are event-month briefs from the real code, real engine rows and the real replay table, with no model involved. Plain form below. In Telegram the first line is bold, the four history lines sit in a collapsed quote, and the footer is italic.

English:

```
Morning. It's your investing day, and ₹1,00,000 is ready.

A rough stretch in the news: oil supply shock on Oct 20. Shocks like this have happened before.

Months like this are why you have a plan. Yours is built to sit through a fall of up to 20%.
In replays of past markets, a fall that big came in 84% of paths. Bad case ₹1.31 Cr, middle ₹1.92 Cr.

Your plan: Balanced, the one you chose.

What history counted:

Brent crude oil beat the S&P 500 in 6 of 12 past oil supply shocks. Normal is 49%, so this is within normal ups and downs.
… three more rows …

Research, not advice.
```

Hinglish:

```
Good morning. Aaj aapka investing day hai, aur ₹1,00,000 ready hai.

News mein ek mushkil daur: 20 Oct ko oil supply shock. Aise jhatke pehle bhi aaye hain.

Aise mahine ke liye hi aapka plan hai. Yeh 20% tak ki giravat sehne ke liye bana hai.
Purane markets ko dohraane par itni badi giravat 84% raaston mein aayi. Bure haal mein ₹1.31 Cr, beech mein ₹1.92 Cr.

Aapka plan: Balanced, jo aapne chuna.

History ne kya gina:

Pichhle 12 oil supply shocks mein se 7 ke baad Nifty 50 mein tezi rahi. Normal waqt mein yeh 58% hota hai, toh yeh aam utaar-chadhaav ke andar hai.
… three more rows …

Research hai, advice nahin.
```

Hindi:

```
सुप्रभात। आज आपके निवेश का दिन है, और ₹1,00,000 तैयार हैं।

ख़बरों में एक मुश्किल दौर: 20 अक्टूबर को तेल सप्लाई का झटका। ऐसे झटके पहले भी आए हैं।

ऐसे ही महीनों के लिए आपका प्लान है। यह 20% तक की गिरावट सहने के लिए बना है।
पुराने बाज़ारों को दोहराने पर इतनी बड़ी गिरावट 84% रास्तों में आई। बुरे हाल में ₹1.31 Cr, बीच में ₹1.92 Cr।

आपका प्लान: Balanced, जो आपने चुना।

इतिहास ने क्या गिना:

पिछले 12 तेल सप्लाई झटकों में से 7 के बाद Nifty 50 में तेज़ी रही। सामान्य समय में यह 58% होता है, तो यह आम उतार-चढ़ाव के भीतर है।
… three more rows …

रिसर्च, सलाह नहीं।
```

Visible lines before the detail: 6 in every language. The test cap is 8.

Brief buttons:

| English | Hinglish | Hindi |
|---|---|---|
| Got it · See my plan | Theek hai · Mera plan | ठीक है · मेरा प्लान |
| Why these counts? · Every sector | Yeh counts kyun? · Har sector | ये गिनती क्यों? · हर सेक्टर |
| My page · My range | Mera page · Meri range | मेरा पेज · मेरी रेंज |

A tip check, Hinglish. This is the case 3D sent in English:

```
Confirm nahin hua. Maine pichhle 7 din ki news search ki, aur koi publisher ise report nahin kar raha.

Is message mein hype wale words bhi hain: "pakka", "abhi". Asli news ko inki zaroorat kam hi padti hai.

Research hai, advice nahin.
```

An error, in all three languages:

- "That one didn't go through on my side. Give it a minute and ask me again."
- "यह मेरी तरफ़ से नहीं हो पाया। एक मिनट बाद फिर से पूछ सकते हैं।"
- "Yeh meri taraf se nahin ho paaya. Ek minute baad phir se pooch sakte hain."

## Web charts (owner-approved addition)

The plan-range bar and the what-if strip now have the shadcn chart look, in plain CSS and SVG:

- Token colours for light and dark.
- Rounded bars and thin gridlines.
- 12px labels at every width.
- An HTML legend.
- Keyboard-reachable marks with CSS-only tooltips.

The whole thing stays under 22 kb including the stylesheet. Token values and conventions come from ui.shadcn.com/docs/theming and /docs/components/chart, read on 2026-10-25. No shadcn, Recharts or Simbian code was used.

- **Byte budget.** The largest page is `/what-if/rbi_cut/^NSEBANK`, at 16.7 kB of SVG plus 4.9 kB of `charts.css`. The limit is 50 kB.
- **No horizontal scroll** at 320 and 1440 px, in light and dark, in Chromium and WebKit.
- **Not built.** The scoreboard has no chart today, and none was invented.
- **Tokens are scoped.** shadcn's `--radius` is scoped to `.chart`, so the site's own 3px radius is unchanged.
- **Plot surface.** The plot sits on the popover surface because the muted labels measure below 4.5:1 on the site's paper colour.

## Before and after shots

Everything is in `docs/phases/phase-3e-shots/`. The message shots are a local render of the exact Telegram HTML, made by a script that mimics the Telegram client.

- **"Before" messages.**
  - The brief and Why answers are 3D's recorded outputs (`evals/results/trace_raw.json`).
  - The tip checks are from the 3D words eval.
  - Onboarding is from commit 125ec77.
- **"After" messages.** These come from the real code and real data with no model. They are what goes out when the guard falls back, or with no model at all.

| Shot | Files |
|---|---|
| Brief | `brief-{en,hinglish}-{before,after}.png`, `brief-{en,hinglish}-after-open.png` (detail opened) |
| Why | `why-{en,hinglish}-{before,after}.png` |
| Tip check | `tip-{en,hinglish}-{before,after}.png` |
| Onboarding | `onboarding-{en,hinglish}-{before,after}.png`, `onboarding-lang-after.png` (the new first message) |
| Charts | `chart-{plan-range,what-if}-{before,after}-{320,1440}-{light,dark}.png` |

Live Telegram screenshots wait for the deploy (OWNER NEEDED below).

## Deviations

1. **The brief is not model-reworded any more.** Code writes it in all three languages. This removed the translation path (`BRIEF_TASK`, `TRANSLATE_TASK`) and makes the 8-line limit testable. Chat answers that have a task are still reworded by the model under the guard.
2. **Alerts are fixed words**, for the same reason. `ALERT_TASK` is gone.
3. **The plan line sits above "What history counted"**, not after the detail. The message shape has no block after the detail.
4. **A brief asked for on another day** says "Here's your brief for this month". It does not claim the day is investing day.
5. **"Research, not advice" is in the footer of answers, not of every message.**
   - Read literally, "once per message" would also put it under "Paused." and every setup question. That is the repetition the owner asked to remove.
   - Every message carries the phrase at most once, and only in the footer.
   - Answers, briefs, alerts, watch hits, /help, /plan and the end of setup carry exactly one footer. Questions, acks and errors carry none.
   - The test enforces both.
6. **Onboarding asks the language first.** The greeting before that choice is bilingual (English and Hindi).
7. **Two files outside the chart file list.** The chart work added `networth/web/templates/_chart.html` (shared tooltip and legend macros) and a `/static/charts.css` route in `routes.py`. The app has no static mount, so the route is needed.
8. **The eval tooling rewrote `docs/phases/phase-5-report.md`'s words section** from the new results. That is its normal output, committed as is.

## Known gaps

- **Hindi asset names don't take the oblique case.** "ब्रेंट कच्चा तेल ने" should be "कच्चे तेल ने". The names come from one table.
- **US asset names and watch topic labels stay in English** inside Hindi and Hinglish text.
- **The tip-check hype detector doesn't catch Devanagari hype words** such as "पक्की", so a Hindi tip gets no hype note.
- **Hindi spelling is inconsistent.** Both रकम and रक़म appear.
- **The mixed-script jailbreak** is the one words-eval failure. It is described above.
- **Live Telegram rendering is untested** until the deploy. Local tests cover the HTML, the escaping and the 400 fallback with a fake transport.
- **Stale local branches.** `phase-3e-web` and `phase-3e-charts` and their worktrees remain. See Rebase.

## Rebase

3E was rebased onto `origin/main` at ba24bcb, which has the Phase 3C fixes and Phase 7. Both sides were kept in every conflict.

| File | Conflict | Resolution |
|---|---|---|
| `.claude/CHANGELOG.md` | Both sides appended entries, on three commits | Kept both, 3C and 7 first, then 3E |
| `networth/web/routes.py` | 7 imported `holdings_view`, 3E imported `percent` | One import line with both |
| `networth/chat/__init__.py` | 3C routed Explain this through `explain.explain_message` (never fetches footer, opt-out or tracking links), 3E gave every handler a `lang` argument | 3E's handler signatures, with Explain this calling `explain_message` |
| `networth/chat/explain.py` | 3C added `URL`, `SKIP_HOSTS` and `SKIP_WORDS` for `user_link` and `fetchable`, 3E made `NOT_EXPLAINED`, `CANT_FETCH` and `CANT_READ` three-language tables | 3E's tables, followed by 3C's link filters |
| `networth/keiki/turn.py` | 3C added `LINK_LINES` so a code is read past a mail footer, 3E made `LINKED` three-language | Both: `LINK_LINES = 3` and 3E's `LINKED` table |

`strip_quoted` (drops Keiki's `[Email from ...]` header line and footers), sender-keyed contacts and the slash-command-in-a-first-email setup path all merged without conflict.

These broke only after the merge. The first was fixed inside the rebased 3E commit, the rest in one follow-up commit (5116897):

- `tests/test_chat.py` and `tests/test_keiki_turn.py`: 3C's footer-link explain tests expected the bare explanation. 3E adds the one "Research, not advice." footer, so they now expect it.
- `tests/test_keiki_link.py`: 3C compared against `LINKED`, which is now a table, so the test compares against `LINKED["en"]`.
- Phase 7's holdings page used a row key called `lean` for the gain colour class. 3E's voice test greps every template for "lean", so the key is now `direction`. The CSS classes and the page are unchanged.

No test was dropped from either side. Three tests were deleted before the rebase by 3E itself, because they covered behaviour 3E removed: the translation task, the "Type /plan" nudge and plain-text Telegram sends. One sim test was renamed. `make check`: 918 passed.

Both `worktree-agent-*` branches are deleted with `git branch -d`. `phase-3e-web` and `phase-3e-charts` remain, along with the two worktrees under `.claude/worktrees/` that hold them. The rebase rewrote their commits, so `git branch -d` refuses them as unmerged, even though their content is on main (checked with `git range-diff`: only the CHANGELOG differs). Removing them needs `git worktree remove` and then `git branch -D`.

## Owner needed

OWNER NEEDED: deploy Phase 3E - `npx maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json`, then wake it with `curl https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/health`. Then, in Telegram:

1. Send `/start` and check the first message asks the language.
2. Send `/brief` and check it renders bold with a collapsed quote.
3. Open `/track-record` and check "When we tested ourselves" is there.

Send the screenshots so they can join `docs/phases/phase-3e-shots/` as the live set.
