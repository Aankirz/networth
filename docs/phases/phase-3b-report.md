# Phase 3B report: the product

Networth now talks back. A set-up user gets an investing-day brief with `/brief` or on their investing day at 08:00 Kolkata time. They can ask what happened today, ask why, forward a tip to check, send an IPO page, a link or a screenshot to have it explained, and ask about their plan. They can open their own page from a signed link. A rare, clearly uneven event sends at most two alerts a month. Every sentence a model writes passes a guard against the facts it was written from, and code-written text goes out instead when it fails twice.

Deploy URL: https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea

## What was built

| Piece | Where | What it does |
| --- | --- | --- |
| Guard | `networth/guard.py` | Every number in a draft must be in its source, after normalising ₹1,00,000, 1 lakh, 56%, 14 of 22 and Devanagari digits. No banned words in English, Hinglish or Devanagari. No advice phrasing. One rewrite with the problems named, then the template. Every verdict goes to `data/guard.jsonl`. |
| Brief | `networth/brief/`, `networth/bot/briefs.py` | The month's confirmed events, up to 4 engine rows in words with a 🟢🔴⚪ mark, and the user's own plan. The row with the user's home market leads. The writer only rewords it. It is claimed once per user per day, and a repeat `/brief` resends the stored text with no model call. |
| Chat | `networth/chat/` | One closed intent per message: `what_happened_today`, `why`, `tip_check`, `explain_this`, `plan_question`, `other`. Jev picks when it is configured and at least 0.7 confident, else the cheap model, else phrase rules. The reply language is Hindi for Devanagari, Hinglish for Roman Hindi (two or more common Hindi words), else the user's setup language. |
| Tip check | `networth/chat/tip.py` | Exa search over the last 7 days, a cheap `same_claim` call that keeps only articles reporting the claim, then the watcher's own `group.confirm()`. A confirmed tip that the judge maps to an event type also gets its history line from `odds()`. |
| Explain this | `networth/chat/explain.py` | Pasted or forwarded text, a public link (page text), or a photo (Telegram `getFile`, then the `vision` role transcribes it). The user's text is the guard source, so every number must be on the page. The glossary (`knowledge/glossary.md`) goes into the writer's system prompt. A link is fetched only from a global address, checked on every redirect hop. |
| Per-user page | `networth/app/links.py`, `/u/{token}` | The link token plus a 30-day expiry, HMAC-SHA256 signed with `LINK_SIGNING_SECRET`. It shows the plan and the last brief, with `noindex` and `no-store` headers. A bad or expired token gets the friendly 404. `/plan` and the brief's "My page" button hand it out. |
| Rare alerts | `networth/bot/alerts.py` | A news insight with at least 8 episodes, not a weak signal, and at least 15 points between hit rate and normal rate. It goes to active users with alerts on, in their markets, once per event, at most 2 a month. It is claimed before sending, through `send(proactive=True)`. |
| Schedules | `networth/app/schedule.py` | `GET /schedules` publishes the watcher (`*/30 9-15 * * 1-5`) and the brief (`0 8 * * *`), both Asia/Kolkata. `POST /chat` with `source: "scheduled"` starts the job in a background thread. |
| Jev eval | `evals/intent_accuracy.py` | 36 labelled English, Hindi and Hinglish messages through both pickers. |
| Bot wiring | `networth/bot/commands.py` | `/brief`, the brief buttons (`br:ok` acknowledges, `br:plan` opens plan editing), free text to chat, photos to explain-this. Slow answers run after the update lock is released, so one tip check never holds up another user's setup. |

Tests: 378 pass with no network (`make check`). New files are `tests/test_guard.py` (22), `tests/test_chat.py`, `tests/test_links.py`, `tests/test_alerts.py` and `tests/test_schedule.py`.

## Sample messages

Every sample below came from a live run on 2026-10-25 against the real models and the local `data/` (watcher sqlite and engine sqlite). They were not run through Telegram, because the deployed image predates this code (see OWNER NEEDED).

**Brief** (one writer call, passed the guard first time):

```
Investing day, Oct 25. ₹50,000 ready.

This month's news in one line: a tariff move on Oct 23, bank stress on Oct 22, and a pandemic scare on Oct 20.

What history shows after months like this:
⚪ Indian banks (Nifty Bank) did better than the Nifty 50 in 6 of 9 past bank stress episodes (normal: 59%).
🔴 Indian IT (Nifty IT) did better than the Nifty 50 in 3 of 9 past bank stress episodes (normal: 52%).
🔴 US banks and finance (XLF) did better than the S&P 500 in 4 of 11 past bank stress episodes (normal: 48%).
🟢 US tech (XLK) did better than the S&P 500 in 8 of 11 past bank stress episodes (normal: 57%).

Your plan. You chose Balanced. 20% safety, 70% core, 10% growth. These historical counts are context. The plan is always your choice.
```

Buttons: Invest as planned, Change my plan, Show the scoreboard, Why?, My page.

**What happened today** ("what happened today?"):

```
Confirmed today:

• RBI raised the repo rate to 5.50% — the rate at which RBI lends to banks.
• The US Federal Reserve published its H.4.1 release schedule, covering banking-system data.
• WHO and other sources reported a cross-border Ebola outbreak in Africa.
• Several outlets discussed the U.S. midterm election outlook and possible market impact.
• The U.S. Treasury published a proposal on outbound investment security rules.

48 other reports could not be confirmed, so they are left out.
```

**Same, in Hinglish** ("aaj market mein kya hua"):

```
Aaj ki confirmed khabar: RBI ne repo rate 5.50% kar diya. Repo rate woh rate hai jis par RBI banks ko short-term paise deta hai.
...
48 aur reports confirm nahi ho sakin, isliye unhe chhod diya.
```

**Why** ("Why?"):

```
It starts with RBI restrictions on Puducherry cooperative bank (Oct 22), an official source. We count only confirmed news: 3 publishers within 24 hours, or an official post.

Then we checked every past bank stress episode in our records. In 6 of 9, Indian banks (Nifty Bank) did better than the Nifty 50 afterwards. In normal periods, that happened 59% of the time.
```

**Tip check, fake tip** (forwarded "URGENT: Infosys to be delisted from NSE next week, sell before Friday!"):

```
I checked the news from the last 7 days: no publisher is reporting this. That does not prove it is false, but there is nothing to confirm it yet.
```

**Tip check, one publisher** (forwarded "RBI ne repo rate badha diya, banks ke shares girenge"):

```
This isn't confirmed yet. Only thebharatpost.com reported it in the last 7 days.

We treat news as confirmed when at least 3 publishers report it within 24 hours, or an official source posts it.
```

**Plan question** ("what is my plan?"): the setup summary, ending "Type /plan to change it."

**Other** ("thanks!"): "I can tell you what happened today, why a brief said what it said, and whether a tip you were sent is reported anywhere. You can also send me an IPO page, an article or a screenshot and I'll explain it in plain words. Research, not advice."

**Explain this, screenshot, English.** A low-contrast PNG of an IPO page, read by the `vision` role:

```
Acme Foods Ltd IPO is the company's first public share offering—its way of raising money from public investors.

• Price band: ₹95 to ₹100 per share — the allowed price range per share.
• Lot size: 150 shares — bids are in bundles of 150 shares.
• Issue size: ₹1,200 crore — total money involved. ₹800 crore is a fresh issue, meaning money goes to the company; ₹400 crore is an offer for sale, meaning existing owners are offering shares and that money goes to them.
• Opens: Oct 28, 2026; closes: Oct 30, 2026.
• Retail quota: 35% — this share of the offering is set aside for retail investors.

Risk stated: Acme Foods depends on three suppliers for 60% of its raw materials. A problem with any of them could affect its supply.
```

**Explain this, Hinglish** ("yeh IPO samjhao bhai, kya matlab hai iska:" plus the same page text):

```
Acme Foods Ltd ka IPO matlab company pehli baar public ko shares dekar paisa raise kar rahi hai.

• Price band ₹95 to ₹100 per share: ek share ki minimum aur maximum keemat.
• Lot size 150 shares: ek bid fixed 150 shares ka hota hai.
• Issue size ₹1,200 crore: IPO se uthne wala kul paisa. Ismein fresh issue ₹800 crore hai—naye shares ka paisa company ko jayega. Offer for sale ₹400 crore hai—existing owners ke shares hain, paisa unke paas jayega.
• Opens: Oct 28, 2026; Closes: Oct 30, 2026: IPO in dates ke beech khula rahega.
• Retail quota 35%: total shares ka 35% retail investors ke liye rakha gaya hai.

Risk: company raw materials ke 60% ke liye sirf three suppliers par depend karti hai. In suppliers mein dikkat hui, to supply aur business par asar pad sakta hai.
```

Neither explanation has a score, and neither says apply or skip. The guard rejects "apply" and "skip" outright.

## The guard's rules

1. Every number in the draft appears in the source. Formats are normalised: `₹1,00,000`, `1 lakh` and `100000` are equal, `5th` is 5, a sign is ignored, Devanagari digits are read.
2. No banned word: buy, sell, guarantee, can't lose, sure shot, multibagger, target price, and the Hinglish and Devanagari forms (kharid, bech, gaaranti, pakka, खरीद, बेच, गारंटी, पक्का, मल्टीबैगर).
3. No advice phrasing: "you should", "you must", "put your money", "move ₹", "consider investing", "apply", "skip", "aapko ... chahiye", "lagao", "invest karo" and similar.
4. A failed draft gets one rewrite told exactly what failed. A second failure sends the code-written template. A model that raises counts as a failed draft.

Tests plant an invented number, banned words and "you should" phrasing in English and Hinglish (`tests/test_guard.py`), and the chat tests prove an invented "70%" and a "You should apply." never reach the user.

## Cost

From `data/llm_calls.jsonl`, live runs on 2026-10-25 (UTC Oct 24, 21:00 onward):

| Call | Role | n | Avg cost |
| --- | --- | --- | --- |
| `write` | writer | 6 | $0.0110 |
| `pick` | cheap | 82 | $0.00007 |
| `same_claim` | cheap | 1 | $0.0005 |
| `read_image` | vision | 1 | $0.0050 |
| `exa_search` | exa | 1 | $0.0070 |
| `jev_pick` | jev | 72 | not reported by the gateway |

| Turn | Calls | Cost |
| --- | --- | --- |
| Brief | 1 write | $0.0137 measured |
| Chat turn (today, why, plan) | pick + write | about $0.011 |
| Scope line in English | pick only | about $0.0001 |
| Tip check | pick + Exa + same_claim + write (+ judge when confirmed) | about $0.019 |
| Screenshot explain | pick + read_image + write | about $0.016 |

The writer is almost all of a plain chat turn and over half of a tip check, because its system prompt carries PRODUCT.md and the glossary. If cost matters, prompt caching on that fixed prefix is the lever.

## Jev against the cheap model

`uv run python -m evals.intent_accuracy`, 36 labelled messages (21 English, 6 Devanagari Hindi, 9 Hinglish), results in `evals/intent_results.json`.

| Run | Picker | Correct | Accuracy | Median latency | Max latency |
| --- | --- | --- | --- | --- | --- |
| 1 | Jev | 34/36 | 94.4% | 386 ms | 885 ms |
| 1 | cheap model | 34/36 | 94.4% | 1,135 ms | 1,536 ms |
| 2 | Jev | 36/36 | 100% | 422 ms | 546 ms |
| 2 | cheap model | 36/36 | 100% | 1,082 ms | 1,749 ms |

Both pickers missed the same two messages in run 1: "did I leave out crypto?" (plan question, picked other) and a forwarded IPO page (explain-this, picked tip check). Each was a gap in the criteria text, not in either model. Run 2 names exclusions under plan questions and forwarded documents under explain-this. Run 2 is in-sample, so it overstates accuracy on new messages. In run 1, all 34 Jev picks above the 0.7 floor were right. Decision: `use_jev_for_intent = true`. Accuracy is equal, latency is about 2.5x lower, and the cheap model still answers whenever Jev is unsure, slow or down.

## Alert threshold

`alert_min_episodes = 8` is PRODUCT.md's floor for a non-weak row. `alert_min_gap = 0.15`: the scoreboard's lean words start at a 10-point gap, and the alert asks for half again as wide, so an alert fires only where the scoreboard would already show a clear lean. On the live engine, 6 of 9 bank-stress episodes against a 59% normal rate is a 7.7-point gap and would not alert. A row at 10 of 12 against 55% (a 28-point gap) would, which is the case `tests/test_alerts.py` sends.

## OWNER NEEDED

1. OWNER NEEDED: deploy Phase 3B - run `npx maritime deploy networth --source github --repo https://github.com/Aankirz/networth --branch main --wait --json`. The auto-mode permission check refused it for me, and deploys are a step I pause on. All env vars are already set, and the engine sqlite is already on `/data`.
2. OWNER NEEDED: after the deploy, confirm the schedules registered - run `curl -s https://api.maritime.sh/a/eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea/health`, wait a minute, then `npx maritime agents triggers list eeaab0d3-f621-4548-b8c8-6a5fe0e8f0ea --json`. Expect `watcher` and `brief`. It returned `[]` before the deploy, as expected.
3. OWNER NEEDED: the live Telegram checks with the coordinator after the deploy - `/start` to done, `/brief`, "What happened today?", a forwarded fake tip, "Why?", a forwarded IPO page or screenshot, the same in Hinglish, and `/plan` to open the `/u/` link.

## Done-when status

| # | Item | Status |
| --- | --- | --- |
| 1 | `make check` from a clean clone | 378 pass |
| 2 | Server on Maritime, `/health` and `/why/rbi_hike/^NSEBANK` | `/health` 200 now. `/why` needs the deploy (item 1 above). The 500 cause is fixed in code (6cf727b) and the sqlite is on `/data`. |
| 3 | Webhook, onboarding and a real brief live | needs the deploy. `/brief` is the command. |
| 4 | Guard tests | done, `tests/test_guard.py` |
| 5 | Live today, fake tip, why | proven against real models locally (samples above). Telegram run needs the deploy. |
| 6 | Live explain-this, English and Hinglish | proven locally, screenshot and text. Telegram run needs the deploy. |
| 7 | `/u/{token}` real and tampered | tested (`tests/test_links.py`). Live after the deploy. |
| 8 | Schedule registered, brief idempotent | idempotency tested (`tests/test_schedule.py`). Registration needs the deploy. |
| 9 | Alert rules tested | done, `tests/test_alerts.py` |
| 10 | Fresh redeploy 200s, Jev table | Jev table above. 200s need the deploy. |
| 11 | Keiki | gap, see below |
| 12 | This report | here |
| 13 | No secrets, no `data/` | checked on every commit |

## Known gaps

- **Keiki (stretch).** Not wired. `KEIKI_API_KEY` authenticates. `GET https://onkeiki.com/api/v1/developer/agents` returns `200 {"agents":[]}`, so no Keiki agent or channel exists to set `harness: "external"` on. Wiring it needs a new outward-facing Keiki channel, a `/keiki/turn` endpoint that verifies `Keiki-Signature-Ed25519` against Keiki's JWKS (no Ed25519 library is installed), and the turn API calls `/messages` and `/complete`. That is past the time box. The external-harness doc is https://onkeiki.com/docs/external-harness.md.
- **Link fetch and DNS rebinding.** `explain.page_text` resolves the host and checks the addresses are global, then httpx resolves again. A rebinding attacker could slip between the two. That is marked in code with the upgrade path (pin the checked address in the transport).
- **Jev cost.** The gateway reports no price, so Jev calls log $0.
- **Watcher wakes cost money when forged.** `/chat` is public. The 25-minute gap and the job lock cap a forged-wake flood at one watcher cycle per 25 minutes, around the clock, against the schedule's two an hour in market hours.

## Deviations

- `/brief` works for any set-up user, not the owner only. It is pull-only and claimed once per day, so it can't spam, and the coordinator needs it to test.
- "Invest as planned" only acknowledges ("Noted. Your plan stays as it is."). Networth never moves money, and the user invests in their own app.
- The chat answers "what happened today" from stories pulled in the last 24 hours, including confirmed stories that are not one of the 12 event types (for example the H.4.1 schedule). Event types gate history lines, not news.
- Maritime env vars were set with `maritime agents env set ... --secret`, the current name for `maritime env set`.
