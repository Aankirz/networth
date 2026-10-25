# Phase 13A: answers better than Perplexity Finance

## Why

The owner tested the live demo against https://www.perplexity.ai/finance and called ours worse. The coordinator ran the same questions on 2026-10-25 at 20:40 IST against `POST /api/demo/chat`.

| Question | Perplexity Finance | Networth today |
|---|---|---|
| "Should I invest in Swiggy shares now? I hold 390 at an average of 230." | 3 s. It leads with the position: cost ₹89,700, worth ₹68,640, down ₹21,060 (23.5%). Then a table, the 52-week range ₹174.95 to ₹434, the Q2 FY27 results (stock fell 16.75%), and 10 inline sources. | Misrouted to `holdings`: "Send me a screenshot of your holdings and I'll read it." It ignored the numbers the user typed. |
| "what is tesla's current price" | A price, a change, and a chart. | "Tesla's current price is not included in the information here…" plus a paragraph of filler. On the web it once failed with "Networth didn't answer just now". |
| "How has Nifty 50 done over the last 5 years?" | Returns, a chart, drawdowns. | Misrouted to `what_happened_today`: RBI repo, the Fed H.4.1 schedule, an Ebola outbreak. Not one Nifty number, although we hold index history for the backtest. |
| "What happened in the Indian market today?" | Sensex −1,605 (−2.15%) to 74,729, Nifty −546 (−2.36%), then why: crude above $117, midcaps hit hardest, foreign selling. 20 sources. | An RBI story from Oct 10, a Fed data schedule, Ebola, US midterms. No index move. "61 other reports could not be confirmed." |
| "how good is jio stock as an investment" (owner's screenshot) | Facts and numbers on Reliance. | Opens with "Whether to put money in is your call, so I won't say yes or no." Every answer repeats a lecture like this. |

## Who it is for

A user asks a money question in plain words and gets, within 5 seconds:
1. the answer with real numbers first,
2. then why,
3. then what history says,
4. then sources.

It is better than Perplexity because it is about *their* money: their holdings, their plan, their monthly amount, and what history did in cases like this.

## Build

Own `networth/chat`, `networth/guard*`, the intent router, the market-data code, and `evals/`. Do not touch `site/`, which the Phase 13B builder owns. Do not touch `networth/holdings` or `networth/bot/holdings*`, which the Phase 12 builder owns.

1. **A quality eval harness first.** Read https://github.com/google-research/harness2 (the owner asked for it), and borrow its loop shape. Build `evals/quality/` with at least 30 real questions: the 5 above, plus prices, index history, a stock's results, comparisons, "what happened today", Hindi and Hinglish, follow-ups, and holdings typed as text. Each case has a rubric:
   - Does the first sentence answer the question?
   - Does it have the numbers it should?
   - Are the numbers right against the source?
   - Is it routed to the right intent?
   - Does it have no lecture?
   - Is it under 5 s?
   
   Score with a judge model, and keep a fixed baseline file. Record Perplexity's answer for the 5 table cases as the bar. Run it before and after, and put the table in the report.
2. **Routing.** Fix the misroutes above with tests. A question that types holdings ("I hold 390 at 230") uses those numbers. "Over the last N years" goes to index or stock history, not news.
3. **Market data.** Add live or last-close prices and day change for NSE and BSE stocks, the main indices (Nifty 50, Sensex, Bank Nifty, midcap and smallcap) and US tickers, plus 52-week range and multi-year history. Look up a free source that needs no key. If every good source needs a key, print OWNER NEEDED with the sign-up steps. Never invent a number. Every number carries its source and time.
4. **"What happened today" leads with the market.** Start with the index moves, then the 2 to 4 confirmed reasons that moved Indian markets *today*. Drop stale and off-topic stories (a Fed data schedule and Ebola are not today's Indian market). Never say "N other reports could not be confirmed" to the user.
5. **No lectures.** Delete every "your call", "I won't say yes or no" and "whether to put money in" opener, and any other repeated caveat in the body. Keep exactly one short footer, "Research, not advice.", and drop it from very short replies (a price, a greeting). 
6. **Networth gives its view (owner decision, 2026-10-25).** The owner dropped the no-picks rule: "forget legalities, bring value". When asked "should I buy, hold or sell X" or "how good is X", answer with a clear Networth view in the first line, the way Perplexity does ("I would not add to Swiggy right now"), then the reasons. The ratings themselves (score, drivers, track record) come from the Phase 13C rating engine in `networth/ratings`. Call it when it exists, and until then give a reasoned view from the facts, labelled "Networth's read". Change the guard so it no longer blocks views. It must still block invented numbers and unsourced claims.
7. **Structured answers for charts.** Every answer with numbers returns a typed card the site can draw: `price` (with a series), `history` (a series and drawdowns), `position` (P&L table), `compare` (two series or a table), `market_today` (index tiles and reasons). Extend `docs/phases/phase-10-contract.md` and tell the 13B builder the shapes by committing the contract first, in your first push.
8. **Telegram gets the same quality.** Send a chart image (PNG, pencil style, matching the site) for history and price answers. Keep the text to what fits a phone screen.

## Not in this phase

- No new providers that need payment.
- The rating engine, the sector board and the news notifier are Phase 13C.
- No `site/` UI work (13B). No holdings screenshot work (Phase 12).

## Done when

1. The quality eval runs with one command and shows the before and after scores. The after score beats the before on every rubric line, and each of the 5 table cases is at least as useful as Perplexity's answer by the judge. The coordinator checks the judge prompt is fair.
2. Each of the 5 table questions, asked live on `/api/demo/chat`, gives the right intent, real sourced numbers in the first sentence, and no lecture. Paste the live replies in the report.
3. "What happened in the Indian market today?" leads with today's Nifty and Sensex move, with sources.
4. A grep test proves no reply opens with or contains "your call", "I won't say yes or no" or "whether to put money".
5. Price and history answers return the typed cards above, and the contract doc lists them.
6. Telegram history answers include a chart image.
7. "Should I buy X" and "should I sell X" get a clear view in the first line with sourced reasons. The guard still blocks a made-up number. Tests cover both.
8. `make check` exits 0. Record the exit code.

## Sources of truth

- harness2: https://github.com/google-research/harness2. Fetch it with `tinyfish fetch content get`.
- The market-data source's own docs. Look it up. Never invent an API, model id, ticker format or flag.

## The gate

`make check`. Capture its exit code. A pipe into `tail` hides it.

## Branch policy

Push straight to main after `git pull --rebase`. Push the contract change first, so 13B can build on it. The coordinator reviews and deploys.

## OWNER NEEDED protocol

Before any step only a human can do (a data-provider key, a payment), print `OWNER NEEDED: <what> — <how>` and wait.

End with `PHASE 13A READY FOR REVIEW`.
