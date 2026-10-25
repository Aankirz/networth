# Phase 12: a holdings reply people understand and act on

## Why

The owner sent a real Groww screenshot. The bot replied with this:

```
Here is what I read.
1. Swiggy: 390 units, average cost ₹230.05 (growth)
2. Vishal Nirmiti: 68 units, average cost ₹220.00 (growth)
3. Adani Green Energy: 180 units, average cost ₹1,217.90 (growth)
4. Hero Motors: 7 units, average cost ₹155.10 (growth)

To fix a line, type its number and the change: 2 units 15, 2 cost 450, 2 growth or 2 drop.
[Looks right] [Fix a line] [Cancel]
```

The owner's verdict: vague, confusing, and it doesn't tell the user what to do. It reads like a data-entry form.
- It never says what the money is worth now, or whether it's up or down.
- "growth" is our internal word, and the user doesn't know what it means.
- "2 units 15" is a syntax to learn.
- It doesn't say the screenshot showed 4 of the user's 22 holdings.
- There is no next step besides confirming.

## Build

Own `networth/holdings` and the holdings handler and copy in `networth/bot`. Do not touch `site/`, `networth/web`, the `/link` code store or `/erase`. The Phase 11 builder owns those right now.

1. **Read what the screenshot shows.** Groww's holdings screen shows the current value, the invested amount and the returns per row. Read them when they are there. When they are not, compute the value from the price the screenshot shows. Never invent a number. A value we can't read is "not shown", not a guess.
2. **The first reply leads with the answer.** The shape is below. Use real numbers from the user's own rows, and keep it short enough to read on a phone without scrolling.
   ```
   Got it. 4 holdings, worth ₹2.91 lakh today.
   You put in ₹3.25 lakh, so you're down ₹34,400 (11%).

   Adani Green   ₹2.13 lakh   73% of this
   Swiggy        ₹68,640      24%
   Vishal Nirmiti ₹7,881       3%
   Hero Motors   ₹775        under 1%

   All 4 are single company shares. One company is almost three quarters of this money.

   Is this everything? If Groww shows more, send the next screenshot and I'll add it.
   [That's everything] [Send more] [Something's wrong]
   ```
   The numbers above are illustrative. Compute them yourself and test them against the owner's screenshot rows.
3. **Say how many rows were read.** When a screenshot is cut off, say so ("I can see 4 here. Scroll in Groww and send the rest."). Several screenshots add up to one list and never make duplicates.
4. **"That's everything" brings the useful part.** Compare the holdings with the user's saved plan in plain words: "Your plan is Balanced: about 60% in broad funds, 30% in single shares or themes, 10% safe. Right now 100% is in single shares." Then one concrete thing to look at, phrased as research, never as an order: which part is furthest from the plan and by how much in rupees. End with two buttons: "Show my plan" and "What would history say?" (the existing range or backtest path).
5. **"Something's wrong" asks in plain words.** "Which one is off?" with one button per holding, then "What should it be?" with free text such as "15 shares" or "remove it". Drop the `2 units 15` syntax from user-facing copy. Keep the parser as a fallback.
6. **Drop internal words.** "growth", "core" and "safety" never appear bare. Say "single company shares", "broad index funds", "safe money (liquid, gilt, FD)".
7. **The line we never cross still holds.** No "sell X" and no "buy Y". "What should I sell?" gets the plan gap and the history, never a pick. The existing guard runs on every reply.

## Not in this phase

- No new data sources. No live prices beyond what the screenshot shows.
- No web dashboard changes. Phase 11 owns `site/`.

## Done when

1. Sending the owner's 4-row Groww screenshot (fixture from `~/Desktop/groww-holdings.png`, copied into tests, no personal names beyond the stock names) gives a first reply with the total value, the invested amount, the gain or loss, each holding's rupees and share, and a one-line takeaway. A test checks the numbers.
2. The reply says how many rows it read and asks for more.
3. A second screenshot adds rows without making duplicates. A test covers it.
4. "That's everything" gives the plan comparison in rupees and the two buttons. A test covers it.
5. "Something's wrong" fixes a holding through buttons and plain text. A test covers it.
6. No reply contains a bare "growth", "core" or "safety", or the `2 units 15` syntax. A test greps every holdings reply.
7. "What should I sell?" after holdings gives the plan gap and history, never a pick, and the guard passes.
8. Live check by the coordinator on Telegram with the owner's screenshot.
9. `make check` exits 0. Record the exit code.

## Sources of truth

- `docs/phases/phase-7-holdings.md` and its report for the existing reader and model.
- The owner's screenshot at `~/Desktop/groww-holdings.png`.
- Look it up. Never invent an API, model id or flag.

## The gate

`make check`. Capture its exit code. A pipe into `tail` hides it.

## Branch policy

Push straight to main after `git pull --rebase`. The coordinator reviews and deploys.

## OWNER NEEDED protocol

Before any step only a human can do, print `OWNER NEEDED: <what> — <how>` and wait.

End with `PHASE 12 READY FOR REVIEW`.
