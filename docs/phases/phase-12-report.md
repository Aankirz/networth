# Phase 12 report: a holdings reply people understand and act on

## What a user sees now

The owner's Groww screenshot (`tests/fixtures/holdings/groww_owner.png`) gives:

```
Got it. 4 holdings, worth ₹2.91 lakh today.

You put in ₹3.25 lakh, so you're down ₹34,373 (11%).

Adani Green Energy: ₹2.13 lakh, 73% of this
Swiggy: ₹68,640, 24%
Vishal Nirmiti: ₹7,881, 3%
Hero Motors: ₹775, under 1%

All 4 are single company shares. Adani Green Energy alone is 73% of this money.

Is this everything? If your app shows more, send the next screenshot and I'll add it.
[That's everything] [Send more] [Something's wrong]
```

The totals are summed before rounding, so they match the screenshot's own printed numbers.
The value is ₹2,90,614.52, which rounds to ₹2,90,615. The invested amount is ₹3,24,987.20.
The returns column sums to −₹34,372.68, which rounds to −₹34,373.

"That's everything" confirms the list and compares it with the saved plan in rupees:

```
Saved.

Your plan is Balanced: about 20% in safe money (liquid, gilt, FD), 70% in broad index funds and 10% in single shares or themes.

Right now 100% is in single shares or themes.

The part furthest from your plan is single shares or themes: at your plan's 10% that would be about ₹29,061, and right now it is ₹2.91 lakh. That's the part worth reading about first.
[Show my plan] [What would history say?]
```

## Build, by brief item

1. **Reading the screenshot.** The reader now also reads the app's own holdings count (`listed`) and whether the list is cut off (`more_below`). Value is units times the price the screenshot shows. When only the row value is printed, the price comes from that value. A holding with no price says "price not shown" and is left out of the total.
2. **The answer comes first.** `networth/holdings/summary.py` computes the numbers. The words are in `networth/bot/holdings_words.py`, in en, hi and hinglish.
3. **Count and merge.** A cut-off list says "I can see 4 of your 22" or "I can see 4 here, and the list goes on". A second screenshot merges into the waiting list by ticker, else by name, so there are no duplicates. The reply then says how many rows were added and how many were updated.
4. **That's everything.** It confirms the list and compares it with the plan in plain words and in rupees. It names the part furthest from the plan as something to read about. This was later replaced by the action plan; see the follow-ups below.
5. **Something's wrong.** It asks "Which one is off?", with one button per holding and a "Start over" button. Picking one asks for the right number in plain words. The kind buttons and "Remove it" are offered too. The typed text can be "15 shares", "average 450" or "remove it". The line being fixed is stored on the list itself (`Holdings.fixing`). The `2 units 15` parser stays as a silent fallback.
6. **No internal words.** `LINES` now says "safe money (liquid, gilt, FD)", "broad index funds" and "single shares or themes" in all three languages.
7. **No picks.** A buy or sell question matches the guard's own `BANNED` or `ADVICE` patterns. It gets fixed words: the decline, the plan gap and the history. It never reaches the writer. Every holdings reply is run through `guard.check` and logged to the guard log.

**Owner decision, added mid-phase.** Gold and silver ETFs (GOLDBEES, SILVERBEES, any GOLD or SILVER ticker or name) and gold funds count as safe money.

## Tests

`tests/test_holdings_reply.py` covers the done-when list:

- The owner's numbers, all three languages, and that the totals equal the screenshot's printed totals.
- The count and the ask for more.
- Merge without duplicates.
- "That's everything", in rupees, with the two buttons and the history.
- "Something's wrong", through buttons and through text.
- A grep of every holdings reply and button label in every language for bare growth, core or safety and the old syntax, with the guard passing on each.
- "What should I sell".
- GOLDBEES and the other gold and silver cases.

The old holdings tests were moved to the new flow.

## Gate

`make check` exit code 0, with 1230 passed and 12 skipped.

## For the coordinator

- **Web holdings page.** It shows the new plain bucket words because it renders `LINES`. No code under `networth/web` or `site/` changed.
- **Live check.** The live check on Telegram with the owner's screenshot is yours.

## Follow-ups after review (2026-10-25)

Each one went in as its own commit, with `make check` run before it.

| Commit | Change | `make check` |
|---|---|---|
| 2cb31eb | Plan screens use plain words: the readback, `/plan`, the starter-plan picker, the own-split ask and the `/range` plan line, in en, hi and hinglish. The picker drops "These are common mixes, shown for education. The plan is always your choice." A test checks every plan screen. | exit 0, 1288 passed |
| acf6f13 | Owner order: no "Research, not advice." footer and no not-advice or your-choice sentence in any holdings reply. A test checks every holdings reply. | exit 0, 1305 passed on the rebased tree |
| fb8284d | A screenshot that adds nothing new no longer says "This screenshot added 0". | exit 0, 1306 passed |
| cb8838e (local) | "That's everything" gives an action plan. Path A rebalances now (the full list is in "That's everything" below). Path B uses new money: the monthly split and the months to plan, with [Show me now] for both paths at once. "Why these?" explains the order and the funds. | exit 0, 1316 passed |
| this commit (local) | A US-dollar holdings fixture (`tests/fixtures/holdings/us_holdings_vision.json`) and its test. A US user sees dollars, "$1.2M" for big amounts, VOO as the broad fund, SGOV and "safe money (cash, Treasury bills, money market)", never rupees, lakh, Nifty or gilt. Two holdings read "Both are single company shares." | exit 0, 1316 passed |

### "That's everything", with the owner's screenshot

```
Here is how to get to your Balanced plan.

On plan, your ₹2.91 lakh would be about ₹58,100 in safe money (liquid, gilt, FD), ₹2.03 lakh in broad index funds and ₹29,100 in single shares or themes.

Right now 100% is in single shares or themes.

Path A, rebalance now: trim about ₹2.62 lakh, weakest first, starting with Vishal Nirmiti, Hero Motors and Swiggy. Then put about ₹2.03 lakh into a Nifty 50 index fund or ETF (such as UTI Nifty 50 Index Fund or NIFTYBEES) and about ₹58,100 into a liquid fund (such as LIQUIDBEES).

Path B, use new money: put your ₹1 lakh a month into the parts below plan, and you're on plan in about 27 months with nothing trimmed.
[Rebalance now] [Use new money] [Why these?]
```

Path A:

- **Trims.** Trims go weakest first. That means the lowest `rate()` view when `Services.ratings` is set (the live server sets `LiveSources`), then the deepest loss, then the biggest holding.
- **Where the money goes.** The rupee targets go to a Nifty 50 index fund and a liquid fund. A dollar list names an S&P 500 fund such as VOO and a money market fund such as SGOV instead.
- **Tax.** The tax line comes from the trims. For the owner it is a loss of about ₹33,600, of which Swiggy's ₹21,080 is the biggest. The owner quoted ₹21,060; the screenshot's own numbers give ₹21,080.

Path B:

- **Monthly money.** The monthly amount is used only when it is in the same currency as the holdings.
- **0% parts.** When the plan holds 0% of the part that is over, Path B says new money alone can't get there.

### Open

- **The shared money formatter.** Holdings now write every short amount with 13A's Python `money()` (`networth/money.py`); `summary.short_money` is gone.
- **"What should I sell?"** It should give a clear view per holding with `rate()`. That is not done yet.
- **The guard.** It still bans "sell" and "buy", so the action plan says "trim" and "put into". 13A owns the guard change.
- **Chat explainer disclaimer.** The chat explainer (not a holdings file) still carried "faisla aapka hai … advice nahin" when last checked. Commit 323158a may have removed it.
