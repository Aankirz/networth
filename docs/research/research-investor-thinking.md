# Thinking Like a Professional Investor: A Reasoning Playbook for the Investment OS Agent

Research brief, 2026-10-24. Scope: how event-driven hedge funds, macro traders, sell-side analysts and bankers reason about news and make probabilistic calls, turned into steps our agents can run. It is written to fit the existing design in `investment-os/product.html` and `architecture.html`: the odds engine (`odds.py`) produces every number, the LLM narrates, deterministic checks run before display, the downside is shown first, and fewer than 30 look-alikes means "not enough history."

Everything below is a summary in my own words. Direct quotes are kept to one short line per source and attributed. Where a figure comes from a source it is attributed. Figures marked `[engine]` must come from our own data at runtime, never from the model.

---

## 0. The one-paragraph version

Professionals don't ask "is this news good or bad?" They ask four other questions. **What did the market already expect, and how far is this from that?** (the surprise, not the news). **What usually happens after things like this?** (the reference class and its base rate, with N). **Which world are we in?** (the regime, which decides which analogs count). **What hurts if I'm wrong, and what would make me change my mind?** (risk first, and the signposts to watch). The agent's job is to run those four questions in order, with numbers from data, and to say plainly when the history is too thin or too different to trust.

---

## 1. Core mental models (each with the check the agent runs)

Grouped by the question they answer. Each entry gives what the model is, where it comes from, and the **check** that turns it into code or a prompt step.

### A. "Is it real and what exactly is it?"

**1. Primary-source verification (journalism and intelligence practice).**
Markets have reacted to fake news within seconds. Three cases: the hacked AP Twitter account's "White House explosions" post (April 2013), the AI-generated "Pentagon explosion" image (May 2023), and the hacked SEC X account that falsely announced bitcoin ETF approval (January 2024). Each moved prices before it was debunked.
**Check:** find the primary document (exchange filing, EDGAR 8-K, central-bank statement, ministry press release, company IR page). Failing that, two independent tier-1 outlets. Record the first-seen timestamp and whether the story is new or old news going round again. Assign a status: `confirmed_primary`, `credible_reported`, `single_source`, `rumor`, `denied`, `false`.

**2. Analysis of Competing Hypotheses (Heuer, *Psychology of Intelligence Analysis*, CIA 1999).**
List every explanation that fits the evidence and look for the evidence that rules hypotheses out, not the evidence that supports your favourite one.
**Check:** for ambiguous headlines ("volume spike is market-driven," "in talks to acquire"), list two to four readings, for example a real deal, a leak, a denial, or a pump. Name the one fact that would separate them.

**3. Event taxonomy discipline (MacKinlay 1997).**
An event study only works if "the event" is defined precisely and dated to the first moment the market could have known it.
**Check:** map the headline to exactly one canonical event type, with subtype attributes (cash or stock deal, hostile or friendly, CFO departure with or without a named successor, supply-driven or demand-driven oil move). Set `entry_date` to the first public timestamp. A filing after the close counts from the next session, as in the existing point-in-time rules.

### B. "What usually happens after things like this?"

**4. Outside view and reference-class forecasting (Kahneman & Tversky 1979; Kahneman & Lovallo 1993; Flyvbjerg 2008).**
People forecast from the specifics of the case in front of them (the "inside view") and ignore how similar cases turned out. The fix has three steps: pick a reference class, get its distribution of outcomes, then adjust for the specifics. Kahneman and Tversky's original version had five: reference class, distribution, intuitive estimate, how predictable the outcome is, and a correction that pulls the estimate toward the class mean in proportion to how unpredictable it is.
**Check:** the engine's look-alike set *is* the reference class. Always state which class was used and how many cases it holds, and show at least one broader class next to it (event type, all markets) so the user can see how sensitive the answer is to that choice.

**5. Regression toward the mean and shrinkage (Kahneman & Tversky; Mauboussin, *The Success Equation*).**
The noisier an outcome, the more a small sample's extreme rate should be pulled toward the long-run rate. Mauboussin's skill-versus-luck continuum says the same thing: where luck dominates, small samples tell you little.
**Check:** this is the beta-binomial shrinkage already in `odds.py`. Show the raw rate only alongside the shrunk rate and N. Never narrate the raw rate when N < 30.

**6. Base rates as the anchor (Mauboussin & Callahan, *The Base Rate Book*, Credit Suisse 2016).**
Start every forecast from how often outcomes of this size happen across a large population, for example how rarely large companies sustain high sales growth, and only then adjust.
**Check:** every Odds Card carries **two** base rates. The first is the *conditional* one: after this event type, how often the stock beat the benchmark. The second is the *unconditional* one: in any random window of the same length, how often a stock of the same size and sector beat the benchmark. If the conditional rate isn't clearly different from the unconditional one, the honest headline is "this event has not historically changed the odds much."

**7. Superforecasting habits (Tetlock & Gardner 2015; Good Judgment Project).**
The habits that improved real forecasters' accuracy: triage (don't waste effort on unforecastable "cloud-like" questions), break problems into parts, balance the inside and outside views, update in small steps rather than overreacting, look for forces pulling in opposite directions, use fine-grained probabilities, and keep score with Brier scores.
**Check:** (a) a triage flag that says whether the question is forecastable from history at all; (b) decompose compound events, for example "oil up, rupee down, OMC under-recoveries"; (c) when a new fact arrives, update the previous card's probability in small, explained steps; (d) log every probability shown and score it (the public calibration page already planned).

### C. "What is already in the price?"

**8. Surprise, not news (Bernanke & Kuttner 2005; Ball & Brown 1968; Kuttner 2001).**
Prices respond to the *unexpected* part of news. Bernanke and Kuttner found that a 25 bp *unanticipated* Fed cut went with roughly a 1% rise in broad US stocks, while the anticipated part had little effect. Ball and Brown showed that most of the annual earnings information had already reached prices before the announcement month.
**Check:** before any base rate, compute `surprise = actual − expected`. Expected comes from the consensus estimate, fed-funds or OIS futures, a prediction market, the company's own guidance, or the pre-event deal spread. If no expectation can be measured, say so.

**9. Expectations investing: reverse-engineer the price (Rappaport & Mauboussin, *Expectations Investing*, 2001; 2nd edition 2021).**
Start from today's price and ask what future it implies, instead of forecasting cash flows first. Opportunities exist only where the news changes those implied expectations.
**Check (retail-safe version):** how much has the asset already moved since the story first appeared? How does that compare with the typical total move for this event type (`[engine]` median CAR)? If the move so far is at or beyond the typical full move, flag "much of the typical reaction may have already happened."

**10. Market-implied probabilities (event-driven practice).**
Event-driven funds read probabilities straight from prices. Merger-arb spread: implied deal probability ≈ (current price − fallback price) / (offer price − fallback price). Option straddles give the implied size of an earnings move. Futures give the implied path of policy rates. Prediction markets give election and geopolitical odds. Mitchell & Pulvino (2001) documented that merger arbitrage has a lopsided, insurance-like payoff: small gains when deals close, large losses when they fail.
**Check:** when a market price for the event exists, show it next to our historical base rate. If the two disagree, that is the interesting part, and the agent should say which one it trusts less and why.

**11. Second-level thinking and variant perception (Marks, *The Most Important Thing*, 2011; Steinhardt).**
First-level thinking says "good news, stock up." Second-level thinking asks what the consensus already thinks, how this differs, and what happens if the consensus is right or wrong. Steinhardt described variant perception as "a well-founded view that was meaningfully different from market consensus" (from his memoir, *No Bull*).
**Check:** the card must state the consensus reading in one line ("most coverage frames this as…") before the base rate. Then: does history support the consensus reading, contradict it, or say nothing?

**12. "Who is on the other side?" (Mauboussin, 2019).**
Mispricings come from four sources: behavioral (overreaction, herding), analytical (same facts, weighed better), informational (rare, and often illegal), and technical (forced selling: index deletions, spinoff dumping, margin calls).
**Check:** for a retail user, assume no informational edge. The only edges the agent may describe are technical (forced or indifferent sellers, as in Greenblatt's special situations) and behavioral (the documented history of overreaction). It must never imply the user knows something the market doesn't.

### D. "What follows from it: who wins, who loses?"

**13. Second- and third-order effects (Marks; Hardin's "you can never do merely one thing"; Bastiat's "the seen and the unseen").**
Every shock spreads through costs, revenues, competitors, financing, currency and, crucially, the *policy response*.
**Check:** build a winners/losers matrix. For each sector or asset give the channel, an exposure measure (`[engine]` or filing data, such as fuel as a share of costs or imports as a share of COGS), the sign, and a confidence level. Always include a "policy response" row. Example: India's July 2022 windfall tax on domestic crude producers capped upstream gains from the oil spike.

**14. Not all shocks are alike (Kilian 2009 for oil; Caldara & Iacoviello 2022 for geopolitics).**
An oil price rise caused by strong global demand goes with *rising* stocks. One caused by a supply disruption or precautionary buying hurts. Caldara and Iacoviello's Geopolitical Risk index separates *threats* from *acts*. Higher readings predict lower investment, lower stock prices and more downside risk, and threats alone already do damage.
**Check:** the event classifier must tag the *cause* of a macro move (demand or supply; threat or act; surprise or scheduled) and match on that tag, not just on the size of the move.

**15. Reflexivity (Soros, *The Alchemy of Finance*, 1987).**
Prices don't just reflect fundamentals, they change them. Rising prices ease credit, which funds growth, which lifts prices, until the gap between perception and reality breaks. Booms and busts follow a recognisable sequence: an unrecognised trend, self-reinforcement, a successful test, growing conviction, a widening gap, a moment of truth, then the mirror-image process downward.
**Check:** flag events whose price move can feed back into fundamentals: bank deposit runs, margin-funded rallies, a stock used as acquisition currency, promoter pledges (in India, pledged shares get sold when the price falls), crypto collateral loops. For these, the historical distribution has fatter tails and the card must say so.

### E. "Which world are we in?"

**16. Regimes and the economic machine (Dalio, *How the Economic Machine Works*, 2013; *Big Debt Crises*, 2018; *Principles*, 2017).**
Asset behaviour depends on where growth and inflation are heading relative to expectations (Dalio's four "seasons") and on where we are in the short-term and long-term debt cycles. Dalio's lesson from his wrong 1982 depression call was to study every analog across countries and centuries, not just the one you remember.
**Check:** tag every historical case and the current moment with regime labels: trend (index above or below its 200-day average, already in the engine), volatility (VIX or India VIX bucket), rate direction (hiking, cutting, on hold), inflation (above or below target) and stock-bond correlation sign. Match on regime when there are enough cases; otherwise show the regime split as a caveat.

**17. Structural change (Lo, adaptive markets; empirical decay of anomalies).**
Relationships change. Post-earnings drift was about 2% over 60 days in Bernard & Thomas (1989); Martineau (2022) argues it has largely disappeared in recent data, though the debate is live again (UCLA Anderson Review, Jan 2026). The US is now a net energy exporter: Morgan Stanley (Mar 2026) notes US oil use per unit of GDP is down almost 70% since 1980. The stock-bond correlation turned positive in the 2022 inflation regime.
**Check:** for every event type, the engine compares the base rate in the first half of the history with the second half. If they differ materially, the card shows the recent half and a "this pattern has changed over time" note.

### F. "What could go wrong, and how bad?"

**18. Risk means permanent loss, not volatility (Marks; Graham's margin of safety).**
Marks defines the risk that matters as the chance of permanent loss, and stresses that many futures were possible even though only one happens. Graham's margin of safety is the cushion between price and a conservative estimate of value, which absorbs being wrong. One Marks memo title says it in four words: "You Can't Predict. You Can Prepare." (Marks, 2001).
**Check:** the worst-decile outcome is drawn first (existing principle). Add "how often did it fall more than X%?" as a natural frequency, and the worst case actually observed in the class, labelled as such.

**19. Fat tails (Taleb, *The Black Swan* 2007; *Statistical Consequences of Fat Tails* 2020).**
In fat-tailed data, sample averages and standard deviations are unstable. A 15-year sample can contain no real tail at all. Avoiding ruin matters more than the expected value.
**Check:** never summarise outcomes with a mean and a standard deviation. Use quantiles (q10, q50, q90) and the observed minimum. If the class contains no crisis-regime case, say "no crash-period examples in this history." Never call any loss "impossible."

**20. Special situations and forced sellers (Greenblatt, *You Can Be a Stock Market Genius*, 1997).**
Corporate events (spinoffs, restructurings, rights offerings, merger securities, post-bankruptcy equity) create mispricings because the natural holders are forced or indifferent sellers. The book cites a Penn State study (Cusatis, Miles & Woolridge 1993) in which spinoffs beat the market by about 10% a year over their first three years. Greenblatt's discipline is to look at the downside first.
**Check:** for these event types, the engine should split the base rate by the forced-selling mechanism, for example a spinoff that is too small for the parent's index. Later studies show these effects shrinking, so apply check 17.

**21. Pre-mortem and kill criteria (Klein's pre-mortem; buy-side memo practice; Tetlock's error-balancing).**
Before committing, imagine the call has failed and explain why. Every buy-side memo lists what would invalidate the thesis.
**Check:** every card ends with two to four observable signposts, each with a direction ("if X, the historical comparison weakens") and a date or trigger to re-check.

### G. How the professionals structure it (format models)

**22. The sell-side initiation.** Rating and price target, then the thesis in three bullets, estimates against consensus, valuation (DCF plus multiples), catalysts with dates, bull/base/bear scenarios (often drawn as a risk-reward chart), and "risks to our view." *Lesson:* scenarios and risks are a required section, and estimates are always shown relative to consensus.

**23. The buy-side or hedge-fund memo.** Thesis, variant perception, why the price is wrong (who's on the other side), catalyst and timeline, payoff (upside and downside prices with probabilities, and the expected value), key risks and pre-mortem, sizing, and kill criteria. *Lesson:* the downside price and the "why now" are explicit.

**24. The investment-banking toolkit.** Comparable companies and precedent transactions *are* reference classes. The "football field" chart shows valuation as overlapping ranges, never a single point. Control-premium and deal-completion base rates anchor M&A talk. *Lesson:* bankers present ranges from several methods, and so should we.

**25. The macro trader.** What's priced (futures, OIS curve, positioning), what the reaction function is (what the central bank or government does next), and where the payoff is asymmetric. A practitioner heuristic: the market's *reaction* to news tells you more than the news itself. Bad news followed by a rally means the bad news was priced. *Lesson:* include "how did the market react on day 1 compared with what the history predicted?" as a signal of positioning.

**26. Humility: news explains less than we think (Cutler, Poterba & Summers 1989; Baker, Bloom, Davis & Sammon 2021; Fama 1998).**
Many of the biggest daily moves have no clear news trigger, and identifiable macro news explains only a minority of return variance. Fama found studies of long-horizon "anomalies" split roughly evenly between overreaction and underreaction, and the results depend heavily on method. *Check:* the agent never says the event "caused" a later move. It says "after events like this…"

---

## 2. The reasoning procedure: headline to investable insight

An ordered checklist. Each step has a **gate**, a point where the agent stops or downgrades instead of pressing on. Steps marked ⚙ call deterministic tools; steps marked ✍ are LLM reasoning over tool output.

**Step 0. Parse the request.** ✍
Extract the claim, the entities (company, sector, country, commodity), the user's holdings or watchlist overlap (`portfolio_exposure`), the region (for legal gating) and the time the user saw it.
*Gate:* if the input isn't a market-relevant event (opinion pieces, price-target chatter), route to the jargon decoder or a general explainer instead.

**Step 1. Verify.** ⚙✍ (`verify-event`)
Find the primary source and record the first-public timestamp, current status and any denials. Check that it isn't old news. Note what is confirmed and what is speculation ("in talks" is not "agreed").
*Gate:* `rumor`, `single_source` or `denied` means no Odds Card. Show "unverified" with the base rate for *rumors of this type* if the engine has one (for example, how often "in talks" reports turn into announced deals); otherwise stop.

**Step 2. Classify.** ⚙✍ (`classify-event`)
Map to one canonical event type plus subtype attributes. For macro events, tag the cause (demand or supply, threat or act, scheduled or unscheduled). Flag compound events (several events on one day).
*Gate:* classifier confidence below threshold means show the two leading interpretations and their separate base rates, labelled as such.

**Step 3. Measure the surprise.** ⚙ (`priced-in-check`, part 1)
Measure expected against actual (consensus, futures, guidance, prediction market, deal spread). Check whether it was a scheduled event. Measure the move since first public time compared with the typical full reaction.
*Gate:* if the surprise is about zero, for example a fully expected Fed decision, say: "this was expected; historically, expected moves like this have not moved markets much." Then focus on the *guidance* or the details, which are the real surprise.

**Step 4. Build the reference class.** ⚙ (`reference-class`)
Pull look-alikes: same type, subtype and market, then size bucket, then regime. Report N at each level of narrowing, and the effective N after clustering events by date.
*Gate:* N_eff < 30 at the narrow level means fall back one level, show "not enough history for companies like this," and give the broader rate.

**Step 5. Check the regime.** ⚙✍ (`regime-check`)
Compare today's regime vector with the regimes of the historical cases. Show the regime split (for example, "in falling markets: [engine]; in rising markets: [engine]"). Run the stability test across the two halves of the history (model 17). Flag known structural breaks, such as US energy independence, decimalisation or SEBI rule changes.
*Gate:* if the current regime is absent or rare in history, use the "this time may differ" banner and widen the bands (the existing high-volatility rule).

**Step 6. Compute base rates with uncertainty.** ⚙ (`odds_card`)
For each horizon: the shrunk probability of beating the benchmark, an interval around that probability, q10/q50/q90 of abnormal return, the observed worst case, and the unconditional comparison rate. Benchmark-relative always; sector benchmark where one exists.
*Gate:* if the conditional rate's interval overlaps the unconditional rate, lead with "no clear historical edge."

**Step 7. Map second-order effects.** ⚙✍ (`second-order-effects`)
Build the winners/losers matrix across direct exposure, suppliers and customers, competitors, currency, financing, the policy response and demand response. Each row gets an exposure figure from data where possible, and each row's sign is checked against the macro playbook's history (Appendix A).
*Gate:* rows with no data support are labelled "mechanism only, not tested."

**Step 8. Weigh the inside view.** ✍
Name the specifics of this case that make it *unlike* the class: size of the shock, balance-sheet strength, valuation starting point, policy space. Adjust *direction only*, in words. The model never changes the numbers. Kahneman and Tversky's rule applies: the less predictable the outcome, the smaller the adjustment.

**Step 9. Frame risk first.** ✍ (`risk-first-explainer`)
Lead with the downside: the worst 10%, how often it lost more than X%, the worst observed case. Then the median and the comparison with simply holding the index. Then the user's exposure, in money terms if they have linked holdings.

**Step 10. Say what would change the view.** ✍ (`signposts`)
Give two to four observable triggers with a direction and a re-check date. Include the most likely way this card turns out wrong (the pre-mortem).

**Step 11. Decode and finalize.** ✍⚙ (`jargon-decoder`, then the harness checks)
Translate every term. Then the existing gates run: every number traces to a tool result, banned phrases are filtered, the region gate applies, and code appends the disclaimer.
*Gate:* if the checks fail twice, show the template card.

**Step 12. Log for scoring.** ⚙
Store each shown probability with its event_id and horizon so the calibration page can score it.

### A compact example of the reasoning shape (no invented numbers)

Headline: *"Brent jumps 12% as tanker traffic through Hormuz halts."* (A March 2026 analog exists: LPL and Morgan Stanley both covered an Iran conflict with Hormuz effectively closed and Brent above $100.)

1. **Verify.** Check exchange price data and two wire services. Status `confirmed_primary` for the price move. The *cause* is `credible_reported`.
2. **Classify.** `macro_shock.oil`, cause = supply / geopolitical *act*, size = Brent +X% in 20 days `[engine]`.
3. **Surprise.** The futures curve shape and option-implied vol show how much was expected `[engine]`. Brent moved Y% since the first report, compared with a typical full move of Z% `[engine]`.
4. **Reference class.** Supply-driven oil spikes since 1973. Narrow N is small and calls for a fallback, possibly to "all geopolitical military events" (LPL's set of about 20-30 events since 1941).
5. **Regime.** Today's inflation and rate regime against the cases. Flag the structural change: the US is a net energy exporter, while India imports most of its oil, so US and Indian results diverge.
6. **Base rates.** Nifty and S&P against their own history, by sector `[engine]`. Context from published sources: LPL reports an average S&P drawdown of about 7%, recovered in about 55 days, across wars and significant military operations (as of 2026), and about 4.7%, with roughly 19 days to the bottom and 42 to recover, across a broader set of geopolitical events. Treat both as small-N, selected, US-only tables (see Section 4).
7. **Second-order effects (India).** Likely losers: aviation (fuel is the biggest cost), paints and tyres (crude-derived inputs), oil marketing companies (if retail prices are frozen), the rupee and the fiscal deficit. Likely winners: upstream producers (but watch the windfall-tax policy response) and tankers. Each row carries `[engine]` exposure and sector base rates.
8. **Inside view.** Duration of the disruption is the key unknown. Morgan Stanley's March 2026 note says the economic risk is mainly about how *long* prices stay high.
9. **Risk first.** Worst 10% for the user's oil-sensitive holdings `[engine]`.
10. **Signposts.** Ceasefire or reopening of the strait (the analog weakens and reverses); Brent holding above a level for N weeks (moves the case toward the "persistent shock" class); an RBI response; a government move on retail fuel prices.

---

## 3. Proposed SKILL.md specs

These are written for a skill-driven harness. The tool names reuse the existing harness tools (`get_events`, `odds_card`, `explain_term`, `portfolio_exposure`, `filing_excerpt`, `compare_assets`) plus a few new ones, marked *new*. The common contract for every skill: **the skill never emits a number that isn't in a tool result**, and every output is JSON the narrator renders.

### 3.1 `verify-event`

```markdown
---
name: verify-event
description: Use first on any user-submitted headline, screenshot or forwarded message before analysis. Establishes whether the event happened, when the market could first know it, and what is confirmed versus speculative.
---
## When to use
- Every new headline or forwarded message. Also when a story is updated, denied or amended.
## Inputs
- headline_text, optional url or image, user_seen_at, user_region
## Tools
- filings.search (NSE/BSE announcements, EDGAR) [get_events], web.search (new), web.fetch (new),
  prices.intraday (new, for "did the market react at that time?")
## Steps
1. Extract the factual claim(s) as atomic statements (who, what, how much, when).
2. Search primary sources first: exchange filing, regulator, central bank, company IR, government release.
3. If no primary source exists, look for >= 2 independent tier-1 outlets. Wire copy repeated by several outlets counts as ONE source.
4. Find the earliest public timestamp. Is it a re-circulation of older news? Check the date on the source page and whether the price data shows a reaction at the original time.
5. Check for denials, clarifications (for example an exchange "clarification on news item"), amendments or retractions.
6. Separate confirmed facts from hedged language ("in talks", "considering", "sources say").
7. Red-flag checks: screenshots without a source, verified-account hacks, AI-generated images, satire domains, numbers that don't reconcile with filings.
8. Assign a status and the entry_date per the point-in-time rules (an after-close filing counts from the next session).
## Output
{ "claims":[{"text":..., "status":"confirmed_primary|credible_reported|single_source|rumor|denied|false",
   "evidence":[{"source":..., "url":..., "published_at":...}]}],
  "first_public_at":..., "entry_session":..., "is_recirculated": bool,
  "speculative_parts":[...], "proceed": bool, "reason": "..." }
## Gate
proceed=false unless the core claim is confirmed_primary or credible_reported.
```

### 3.2 `classify-event`

```markdown
---
name: classify-event
description: Use after verify-event to map a verified event to the canonical taxonomy with the subtype attributes the odds engine matches on, including the CAUSE of macro moves.
---
## Inputs
- verified claims, entity identifiers (ISIN/CIK/ticker), market
## Tools
- taxonomy.lookup (new), filing_excerpt, prices.history (new), classifier model (Haiku) for free text
## Steps
1. Choose exactly one canonical type. If several apply on one day, mark compound=true and list the components.
2. Fill the subtype attributes the type requires, for example:
   - M&A: cash/stock/mixed, friendly/hostile, premium %, target or acquirer, regulatory review needed
   - Management exit: role, effective immediately?, successor named?, stated reason
   - Oil/macro: cause = demand | supply | precautionary/geopolitical; threat vs act (Caldara-Iacoviello);
     scheduled vs unscheduled; magnitude over 1d/20d
   - Policy rate: expected vs unexpected component (from priced-in-check), first move in a cycle?
3. Run Analysis of Competing Hypotheses for ambiguous text: list 2-4 readings and the fact that separates them.
4. Record the classifier's confidence. Below 0.7, keep the top two readings.
## Output
{ "event_type":..., "attributes":{...}, "compound": bool, "components":[...],
  "alternatives":[{"event_type":..., "why":...}], "confidence": 0-1 }
```

### 3.3 `priced-in-check`

```markdown
---
name: priced-in-check
description: Use before quoting any base rate. Estimates how much of the news the market already expected and how much of the typical reaction has already happened.
---
## Inputs
- event (classified), first_public_at, now
## Tools
- consensus.get (new: EPS/revenue consensus, macro survey medians), rates.implied_path (new: fed funds/OIS, RBI OIS),
  options.implied_move (new, where available), deal.spread (new), prediction_markets.get (new, optional),
  prices.history, odds_card (for typical CAR by horizon)
## Steps
1. Scheduled or unscheduled? For scheduled events, fetch the market expectation.
2. Compute surprise = actual - expected, in the event's natural unit (bp, % of consensus, standard deviations of past surprises).
3. Measure the move since first_public_at (asset and sector, benchmark-adjusted).
4. Compare with the engine's typical full reaction at day 1 and day 5 for this class: share_already = move_so_far / typical_move.
5. Look for pre-event run-up in the 5-20 sessions before the news (leakage or anticipation).
6. If a market-implied probability exists (deal spread, futures, prediction market), report it alongside the historical rate.
7. Day-1 reaction against history: a reaction much smaller than usual, or in the opposite direction, suggests positioning had already anticipated it. Report this as an observation, not a signal to trade.
## Output
{ "scheduled": bool, "expected":..., "actual":..., "surprise":..., "surprise_unit":...,
  "move_since_news":..., "typical_move":..., "share_already": ..., "pre_event_runup":...,
  "market_implied":{"source":..., "probability":...} | null, "summary_flag":"mostly_unexpected|partly_priced|largely_priced|unknown" }
## Rules
- If expectation can't be measured, summary_flag="unknown". Never guess.
- Derive implied probabilities with the documented formula only, for example deal p = (P - P_fallback)/(Offer - P_fallback),
  and show the fallback price assumption.
```

### 3.4 `reference-class`

```markdown
---
name: reference-class
description: Use to choose and justify the set of historical look-alikes. Makes the outside view explicit and shows how sensitive the answer is to the choice of class.
---
## Inputs
- classified event, entity features as of entry_date (size, momentum, sector, valuation bucket), regime vector
## Tools
- odds.lookalikes (engine), odds.cluster_stats (new: effective N after date clustering)
## Steps
1. Build a ladder of classes from broad to narrow:
   L0 all events of this type, all markets → L1 same market → L2 + subtype → L3 + size bucket → L4 + regime.
2. At each level report N, N_eff (events within the same 20-session window and same sector count as one cluster),
   date span, and share of cases from the single busiest year.
3. Pick the narrowest level with N_eff >= 30 (MIN_CASES). If none, use L0 or L1 and set enough_history=false.
4. Note how the headline probability changes across levels. If the levels disagree a lot, sensitivity="high".
5. List the three most similar individual cases (name, date, outcome) for storytelling, chosen by similarity score
   and NOT by outcome, to avoid cherry-picking.
## Output
{ "ladder":[{"level":"L2","n":..,"n_eff":..,"span":"2008-2026","p_beat":..}], "chosen_level":..,
  "enough_history": bool, "sensitivity":"low|medium|high", "exemplars":[...], "excluded_reasons":[...] }
```

### 3.5 `regime-check`

```markdown
---
name: regime-check
description: Use after reference-class. Decides whether today's market environment resembles the environments in which the historical cases happened, and whether the pattern itself has been stable over time.
---
## Inputs
- entry_date, market, chosen reference class
## Tools
- regime.vector (new): trend (index vs 200d MA), volatility bucket (VIX / India VIX), policy-rate direction,
  inflation vs target, stock-bond correlation sign, GPR/EPU level (Caldara-Iacoviello; Baker-Bloom-Davis);
  odds.split (engine: base rate by regime and by first half vs second half of history)
## Steps
1. Compute today's regime vector.
2. Compute the regime mix of the historical cases. What share of cases happened in today's regime?
3. Get base rates split by the one or two regime variables that matter most for this event type (for oil: inflation and
   trend; for rate cuts: recession vs no recession, per CFA Institute 2025, which found only 2 of 10 prior cutting
   cycles avoided recession).
4. Stability test: first-half vs second-half base rate. Flag decay (as with PEAD) or sign flips.
5. Check the known-structural-break list for this market (for example, US net energy exporter; SEBI disclosure changes;
   T+1 settlement; index-inclusion rule changes).
## Output
{ "today":{...}, "share_cases_in_today_regime":.., "split":[{"regime":..,"n":..,"p_beat":..}],
  "stable_over_time": bool, "structural_breaks":[...], "banner": null | "this-time-may-differ" | "high-volatility" }
```

### 3.6 `second-order-effects`

```markdown
---
name: second-order-effects
description: Use for macro, policy, commodity and large-company events to map who wins and who loses beyond the obvious first-order effect, and to tie each link to data or history.
---
## Inputs
- classified event, user holdings/watchlist, market
## Tools
- playbooks.get (new: Appendix A playbooks as structured data), exposure.sector (new: cost/revenue shares,
  import dependence, FX exposure from filings), portfolio_exposure, odds_card (sector-level base rates for this event type)
## Steps
1. Load the playbook for the event type. If none exists, build the chain from first principles:
   direct → suppliers/customers → substitutes/competitors → currency → financing/rates → policy response → demand response.
2. For each link, write the mechanism in one sentence and attach an exposure number from data where available.
3. Check each predicted sign against the sector base rate for this event type. Mark rows as
   "supported", "contradicted by history", or "untested mechanism".
4. Add the policy-response row explicitly (central bank, government taxes/subsidies/price controls, regulator).
5. Ask "and then what?" once more for the top two rows (third-order effect), but label it speculative.
6. Intersect with the user's holdings and rank by exposure × confidence.
## Output
{ "rows":[{"asset_or_sector":..,"direction":"+|-|?","mechanism":..,"exposure":..,"history_check":"supported|contradicted|untested",
   "base_rate_ref":..,"confidence":"low|med|high"}], "policy_response":[...], "user_impacts":[...] }
## Rules
- Never present an untested mechanism with the same weight as a supported row.
- If history contradicts the intuitive sign, say so prominently. That is second-level thinking.
```

### 3.7 `base-rate-odds`

```markdown
---
name: base-rate-odds
description: Use to fetch and sanity-check the numeric Odds Card before narration. Enforces the honesty rules on sample size, unconditional comparison, intervals and quantiles.
---
## Inputs
- event_id, chosen reference level, horizons (default 5/20/60/250), benchmark
## Tools
- odds_card, odds.unconditional (new: same-size, same-sector random-window rate), odds.interval (new: Jeffreys/Wilson
  interval on p, or beta posterior quantiles)
## Steps
1. Fetch p_beat (shrunk), raw wins/N, N_eff, q10/q50/q90, observed min and max, per horizon.
2. Fetch the unconditional rate for the same horizon and peer group.
3. Compute edge = p_beat - p_unconditional and whether its interval excludes zero.
4. Pick ONE headline horizon (pre-registered per event type, not the "best-looking" one) and keep the others as secondary.
5. Attach confidence: high only if N_eff >= 100, regime stable, sensitivity low and the calibration bucket is
   well-calibrated out of sample; low if N_eff < 30 or any banner is set; else medium.
## Output
Odds Card JSON (existing schema) + {"unconditional":..,"edge":..,"edge_significant":bool,"headline_horizon":..,
 "n_tests_run": .., "confidence_reasons":[...]}
## Rules
- No raw rate is narrated when N < 30.
- The headline horizon is fixed per event type in config. Choosing it after seeing results is forbidden.
```

### 3.8 `risk-first-explainer`

```markdown
---
name: risk-first-explainer
description: Use to write the user-facing card text. Leads with the downside, uses natural frequencies, compares to doing nothing, and keeps the language plain.
---
## Inputs
- outputs of verify, priced-in, reference-class, regime, base-rate-odds, second-order, signposts; user context and region
## Steps
1. Line 1, what happened: one plain sentence and its verification status.
2. Line 2, so what: who is exposed (the user's holdings first).
3. Downside first: "In the worst 1 in 10 similar cases, it fell X% or more vs the index." Then "N of M cases lost more than Y%."
4. Then the middle: "Typical outcome: [q50]. Holding the index instead: [Δ]."
5. Then the comparison: "In any random [h]-day stretch, stocks like this beat the index [u] of the time.
   After events like this: [p]." If no edge, say "history doesn't show this event changing the odds much."
6. Priced-in sentence when share_already is high or the surprise is ~0.
7. Confidence label with its reason in words ("few cases", "different market conditions today").
8. Signposts (from signposts skill).
9. Reading age at or below 15 years; every term passes through jargon-decoder.
## Output
Card text blocks: what_happened, so_what, downside, typical, vs_index, priced_in, confidence, watch_next.
## Rules
- Natural frequencies ("14 of 20") before percentages; never a percentage without N.
- Never use the words: will, guaranteed, sure, safe bet, buy, sell, should.
- Never say the event "caused" a later move.
```

### 3.9 `signposts` (what would change the view)

```markdown
---
name: signposts
description: Use at the end of every analysis to list the observable developments that would strengthen, weaken or reverse the historical comparison, with a re-check date. Also runs a one-paragraph pre-mortem.
---
## Inputs
- classified event, reference-class result, regime result, second-order rows
## Steps
1. Pre-mortem: "Six months from now, this comparison turned out misleading. The most likely reason is…" Pick from:
   a different regime, a policy response, duration (a one-off vs a persistent shock), a compound event, contagion/reflexivity.
2. Turn each reason into an observable trigger with a threshold where possible (price level held for N weeks, official
   decision, filing, data release date).
3. For each trigger, state the direction: "makes the historical comparison weaker / stronger / points to a different class."
4. Set re-check dates tied to scheduled releases (next policy meeting, results date, deal deadline).
5. Subscribe the user to those triggers (digest integration).
## Output
{ "premortem":"...", "signposts":[{"trigger":..,"threshold":..,"effect":..,"recheck_on":..}] }
```

### 3.10 `jargon-decoder`

```markdown
---
name: jargon-decoder
description: Use whenever user-facing text or a source document contains finance terms. Translates each term into plain words and, where possible, attaches its size relative to the company or the user's money.
---
## Inputs
- text, market, entity (optional)
## Tools
- explain_term (glossary, cached), fundamentals.asof (new: market cap, revenue, debt for sizing)
## Steps
1. Detect terms (glossary match + model detection): OFS, QIP, promoter pledge, SAST, bps, CAR, beta, spread, OIS,
   guidance, EPS beat, capex, windfall tax, under-recovery, mark-to-market, HTM losses, etc.
2. Give each a one-line plain definition (reading age at or below 15) and one "why it matters" line.
3. Size it: "₹1,000 Cr capex = X% of the company's market value" using as-of data.
4. Keep the user's original word in brackets the first time, so they learn it.
## Output
[{ "term":..,"plain":..,"why_it_matters":..,"sized":".." | null }]
```

### 3.11 (optional) `macro-playbook`

A data-backed library skill that `second-order-effects` and `classify-event` call. It holds the structured version of Appendix A: for each macro event type, the classifier questions, transmission channels, typical sector signs, regime splits and literature references. It is versioned so that the autoresearch loop can test edits against the frozen eval.

---

## 4. Pitfalls that make retail-facing odds misleading, and how to show uncertainty honestly

### 4.1 Pitfalls and their countermeasures

| Pitfall | How it fools you | Countermeasure in our stack |
|---|---|---|
| **Look-ahead bias** | Using information not knowable on the event date: restated fundamentals, revised macro data, today's index membership, an event label assigned with hindsight. | The point-in-time rules already in place. Add: macro data from first-release vintages (ALFRED for US data), and event labels frozen at classification time. The existing leak test (scramble future prices → Brier returns to baseline). |
| **Survivorship bias** | Delisted, bankrupt and acquired firms disappear and the base rate looks rosier. At market level, "markets always recover from wars" is told from the US, a survivor. Jorion & Goetzmann (1999) show that markets which closed or collapsed (Russia 1917, for example) are left out of most long histories. | Universe rebuilt per date, including delisted names (already planned). For market-level geopolitical claims, say "in US/Indian history" and note the selection. Include dead crypto tokens in v2. |
| **Small N** | 9 of 12 looks like 75%, but the honest interval runs from about 45% to 93%. | Beta-binomial shrinkage, the MIN_CASES = 30 fallback, and always showing the interval or band. |
| **Overlapping windows and event clustering** | 250-day windows starting a week apart share most of their returns. Events cluster (2008, March 2020), so 200 events may really be 15 independent episodes. Cross-sectional correlation inflates significance (Kothari & Warner 2007). | Report N_eff after date clustering, and use the date-block bootstrap (already in eval) for intervals as well as for the eval. For long horizons, prefer calendar-time portfolio checks (Fama 1998; Barber & Lyon 1997). |
| **Long-horizon measurement bias** | Buy-and-hold abnormal returns are skewed, and the choice of benchmark can manufacture "anomalies." Fama (1998) found many anomalies fade under reasonable changes of method. | Show q10/q50/q90, not the mean. Compute against two benchmarks (market and sector) and flag when they disagree. Treat 250-day results as lower confidence by default. |
| **Regime change and structural decay** | The pattern was real but has changed: PEAD shrinking, US energy independence, the stock-bond correlation sign. | regime-check skill: first-half vs second-half test, regime splits, structural-break list, "this time may differ" banner. |
| **Multiple comparisons / data mining** | Ten horizons × 20 sectors × 5 subtypes = 1,000 tests; about 50 will look significant at 5% by chance. Harvey, Liu & Zhu (2016) argue new factors need a t-stat above roughly 3.0. Bailey & López de Prado's deflated Sharpe ratio and probability of backtest overfitting formalise this. | Fixed headline horizon per event type (no horizon shopping). Count and log the tests run per card. Use a Bonferroni or false-discovery-rate threshold before calling an edge "clear". Keep the sealed test set (planned) and the autoresearch noise floor. |
| **Unconditional base-rate blindness** | "Stocks rose 12 months later in 75% of cases" sounds informative until you notice that broad indices rise in most 12-month windows anyway. | Always show the unconditional rate and the edge (base-rate-odds skill). Benchmark-relative outcomes by default. |
| **Defining events by their outcomes** | "Oil shocks" picked as the big spikes everyone remembers, or "wars" picked from an analyst's list, are selected after the fact. | Rule-based triggers (Brent ±10% in 20 days, already planned) rather than curated lists. When quoting a third-party table (LPL and similar), label it "curated list, about N events." |
| **Attention and media selection** | Headlines users forward are the dramatic, widely covered ones, which may differ from the average filing of the same type. | Allow conditioning on coverage intensity or GPR/EPU level as a feature. Note "widely covered events of this type" where the data supports it. |
| **Compound and confounded events** | Results plus a CEO exit plus a buyback on one day. | Compound tag (planned). Show single-type odds with a "mixed signals" note. Never sum effects. |
| **Narrative fallacy and false causation** | "After X, stocks fell" is read as "X makes stocks fall." Cutler, Poterba & Summers (1989) show many big moves have no clear news trigger. | Banned causal phrasing. Use "after events like this…" |
| **Fat tails hidden by averages** | A mean of +3% and a standard deviation of 8% hide a −60% case. | Quantiles plus the observed worst case, drawn first. Never call a loss impossible. |
| **Calibration drift** | The engine's "60%" turns into a 50% hit rate over time. | Monthly calibration page (planned), with per-confidence-bucket reliability shown to users. |

### 4.2 How to show uncertainty to a non-expert

The communication-research findings that matter most:

- **Natural frequencies beat percentages** (Gigerenzer; Galesic, Garcia-Retamero & Gigerenzer 2009 on icon arrays). "14 of 20 similar cases" is understood better than "70%," especially by people with low numeracy. *Design:* a 20- or 50-dot icon array, where each dot is a past case coloured by outcome, red first. Clicking a dot shows the case.
- **Ranges don't destroy trust; vague words do** (van der Bles et al., PNAS 2020). Giving a number with a range barely lowered trust, while verbal-only uncertainty ("it's uncertain…") did lower it. *Design:* always pair a word label with a number and a range.
- **Separate "how likely" from "how good is the evidence"** (Spiegelhalter 2017; van der Bles et al. 2019; the IPCC practice of likelihood plus confidence). *Design:* two separate fields: the probability band, and evidence quality (high/medium/low) with its reason ("only 18 cases"; "different conditions today"; "the pattern has weakened since 2015").
- **A fixed words-to-numbers scale** (Sherman Kent's "Words of Estimative Probability," 1964; IPCC calibrated language). Proposed mapping for card copy:
  - 90% or more: "nearly always"
  - 70-90%: "usually"
  - 55-70%: "more often than not"
  - 45-55%: "about as often as not"
  - 30-45%: "less often than not"
  - 10-30%: "rarely"
  - under 10%: "very rarely"

  Never "will," "certain" or "guaranteed."
- **Always compare with the do-nothing baseline.** "Holding the index instead" and "any random 60-day stretch" turn an abstract probability into a choice.
- **Downside first, in money.** "If you hold ₹50,000 of this, the worst 1 in 10 similar cases meant losing ₹X or more vs the index" (needs linked holdings and the region gate).
- **Show the spread visually, not a point.** A range bar from q10 to q90 with the median tick. Bars widen with fewer cases (planned). Never one big headline percentage on its own.
- **Name the specific reason for doubt.** "Few cases," "today's market is falling, most past cases happened in rising markets," "much of the usual move has already happened." Specific reasons build more trust than a generic "past performance" line, which should still be appended by code.
- **Publish your own scorecard** (Tetlock). The calibration page should say, in plain words, "when we said 'usually', it happened X of Y times."

---

## 5. Reading list, ranked by usefulness for this product

1. **MacKinlay, "Event Studies in Economics and Finance," *J. Econ. Lit.* (1997).** The engine's methodology spec: estimation and event windows, normal-return models, abnormal returns and their testing.
2. **Kothari & Warner, "Econometrics of Event Studies" (Handbook chapter, 2007).** Why short-horizon results are reliable and long-horizon ones fragile; clustering and volatility changes. Guards the 250-day horizon.
3. **Kahneman & Lovallo, "Timid Choices and Bold Forecasts" (1993), and Kahneman & Tversky, "Intuitive Prediction: Biases and Corrective Procedures" (1979).** The outside view and the five-step correction, which is exactly what reference-class plus shrinkage does.
4. **Tetlock & Gardner, *Superforecasting* (2015).** Triage, decomposition, small updates, Brier scoring. The blueprint for the calibration page and the update logic.
5. **Mauboussin & Callahan, *The Base Rate Book* (Credit Suisse, 2016), and "Who Is on the Other Side?" (2019).** How to anchor on base rates, plus a taxonomy of edges that keeps the agent honest about what retail users can and cannot know.
6. **Rappaport & Mauboussin, *Expectations Investing* (2001; revised 2021).** Reading the price for what it already implies. The intellectual basis of priced-in-check.
7. **Bernanke & Kuttner, "What Explains the Stock Market's Reaction to Federal Reserve Policy?" (*J. Finance*, 2005).** The cleanest proof that only the surprise moves prices; a template for macro-surprise measurement.
8. **Harvey, Liu & Zhu, "…and the Cross-Section of Expected Returns" (*RFS*, 2016), plus Bailey & López de Prado, "The Deflated Sharpe Ratio" (2014).** Multiple-testing discipline for the autoresearch loop and per-card test counting.
9. **Howard Marks, *The Most Important Thing* (2011) and the Oaktree memos.** Second-level thinking, risk as permanent loss, "you can't predict, you can prepare." The voice of the risk-first card.
10. **Kilian, "Not All Oil Price Shocks Are Alike" (*AER*, 2009), and Hamilton on oil shocks and recessions.** Why the classifier must tag the cause of a macro move, not just its size.
11. **Caldara & Iacoviello, "Measuring Geopolitical Risk" (*AER*, 2022), and the GPR data.** A free, daily, regime-able measure of geopolitical risk with threat/act split, ready to use as an engine feature.
12. **Fama, "Market Efficiency, Long-Term Returns, and Behavioral Finance" (*JFE*, 1998), and Barber & Lyon (1997).** A sceptic's toolkit: long-run "anomalies" are fragile to method. Good inoculation against overclaiming.
13. **Gigerenzer, *Risk Savvy* (2014); Galesic et al. (2009); van der Bles et al. (PNAS 2020); Spiegelhalter, *The Art of Uncertainty* (2024).** Evidence-based ways to show odds to non-experts.
14. **Heuer, *Psychology of Intelligence Analysis* (CIA, 1999, free), and Sherman Kent, "Words of Estimative Probability" (1964).** Verification under uncertainty, competing hypotheses, and calibrated language.
15. **Greenblatt, *You Can Be a Stock Market Genius* (1997), with Cusatis, Miles & Woolridge (1993) and Mitchell & Pulvino (2001).** The special-situations playbook (spinoffs, merger arbitrage) and the forced-seller mechanism behind event-driven edges.
16. **Dalio, *Principles for Navigating Big Debt Crises* (2018, free PDF) and "How the Economic Machine Works."** Regime templates and the "study every analog" habit; the source for the regime vector.
17. **Taleb, *The Black Swan* (2007) and *Statistical Consequences of Fat Tails* (2020, free on arXiv).** Why to use quantiles and worst cases, never mean and standard deviation; humility about tails that aren't in the sample.
18. **Reinhart & Rogoff, *This Time Is Different* (2009), and Dimson, Marsh & Staunton's *Triumph of the Optimists* / Global Investment Returns Yearbook.** Cross-country, century-long base rates for crises. The antidote to US-only survivorship.
19. **Bernard & Thomas (1989) on PEAD, with Martineau (2022) and Ball & Brown (1968).** A worked example of an event pattern that was real, got arbitraged, and is still argued over. Use it as the test case for the stability check.
20. **Soros, *The Alchemy of Finance* (1987).** Reflexivity and the boom-bust sequence; useful for flagging feedback-loop events (bank runs, pledges, crypto leverage), less useful as a quantitative tool.
21. **Cutler, Poterba & Summers, "What Moves Stock Prices?" (1989), and Baker, Bloom, Davis & Sammon, "What Triggers Stock Market Jumps?" (2021).** Humility: news explains less of price movement than people assume. Supports the "no causal claims" rule.
22. **Practitioner formats: sell-side initiation templates (CFI, Mergers & Inquisitions guides), hedge-fund one-pagers (Street of Walls), Steinhardt's *No Bull* (variant perception).** Structure for the card: scenarios, catalysts, risks, kill criteria.
23. **Graham, *The Intelligent Investor* (chapters 8 and 20).** Margin of safety and Mr. Market. Timeless framing, low operational value for an event engine.
24. **Market-strategist event tables (LPL geopolitical tables; CFA Institute "When the Fed Cuts," 2025; Morgan Stanley oil-shock notes, 2026).** Useful as sanity checks and copy inspiration, but they are small-N curated lists, so never use them as the engine's base rates.

---

## Appendix A. Macro and corporate playbooks (seed data for `macro-playbook`)

Each playbook gives the classifier questions, transmission channels, typical winners and losers, what the literature says, and the regime splits to compute. Signs are hypotheses for the engine to test, not conclusions.

### A1. Oil price shock
- **Classify:** demand-driven or supply-driven/precautionary (Kilian 2009); magnitude (Brent ±10% in 20 days); expected duration (temporary disruption or lasting loss of supply).
- **Channels:** input costs → margins; consumer real income → demand; inflation → central-bank reaction → rates; currency for importers (INR is sensitive, because India imports most of its crude); fiscal effects (subsidies, excise cuts, windfall taxes).
- **Usual signs (to test):** upstream energy +; oilfield services +; tankers +. Airlines −, paints and chemicals −, tyres −, logistics −. Indian OMCs − when retail prices are held. Importer currencies −, exporter currencies +. Bonds mixed: inflation hurts them, growth fears help them.
- **Literature:** Hamilton (1983, 1985): most postwar US recessions were preceded by oil price increases. Kilian (2009): the stock response depends on the cause. Morgan Stanley (Mar 2026): in the 75-year history of shocks they studied, the S&P was on average up 8.4% twelve months later, and the US is far less oil-intensive than in 1980.
- **Regime splits:** inflation above or below target; trend; whether the central bank is already hiking.

### A2. Central-bank decisions and cycles
- **Classify:** expected or unexpected component (futures/OIS); first move or continuation; size; guidance or dot-plot surprise; cut "because of weakness" or "because inflation is beaten."
- **Literature:** Bernanke & Kuttner (2005): a 25 bp surprise cut goes with about +1% for stocks, mostly through a lower risk premium. CFA Institute (2025): in 10 of 12 cycles the Fed started cutting only after stocks had already peaked; only 2 of 10 prior cutting cycles avoided recession; style performance after cuts was inconsistent.
- **Regime split that matters most:** recession followed or not. Since that isn't knowable at the time, show both branches with their counts. That is the honest way to present a Fed card.
- **India:** RBI surprise against the OIS-implied path; rate-sensitive sectors (banks, NBFCs, real estate, autos); INR and FPI flows react to the gap between US and Indian rates.

### A3. War and geopolitical events
- **Classify:** threat or act (Caldara-Iacoviello); involvement of a major power or energy chokepoint; expected duration; sanctions.
- **Literature:** GPR shocks predict lower investment and stock prices and higher downside risk (Caldara & Iacoviello 2022). LPL tables: an average drawdown of about 4.7% with about 19 days to the bottom and about 42 days to recover across a broad set of events, and about 7% with about 55 days to recover for wars and major military operations (as of 2026). Both are US-only curated lists; see the survivorship note.
- **Usual signs (to test):** defence +; energy + if supply is affected; gold and safe-haven currencies +; airlines, travel and EM importers −; the affected region's assets −.
- **Duration is the key variable.** Morgan Stanley (2026) frames the economic risk around how long oil stays high.

### A4. Tariffs and trade measures
- **Classify:** announcement, implementation or retaliation; breadth (one sector or many countries); negotiable (pauses and deadlines) or locked in.
- **Literature:** event studies of 2018-19 US tariff announcements found negative abnormal returns over short windows, especially for firms exposed through imports or China sales (for example Wengerek et al.). FRBSF (Oct 2025): markets read the 2025 tariff changes as lowering expected corporate profits.
- **Channels:** importer input costs; exporter demand; retaliation targets (agriculture, specific brands); currency adjustment; supply-chain relocation winners (for India, "China+1" beneficiaries such as electronics manufacturing).
- **Reflexivity note:** policy reversals (pauses, carve-outs) often follow sharp market falls, so the event class must track subsequent reversals as a signpost.

### A5. Bank stress and financial contagion
- **Classify:** idiosyncratic (fraud, one bad book) or systemic (rate-driven unrealized losses, deposit flight); size and interconnectedness; whether a policy backstop exists (in March 2023, US authorities guaranteed SVB's deposits and the Fed created the Bank Term Funding Program).
- **Reflexive dynamics:** falling share prices trigger deposit flight, which deepens the losses (Soros-style loop). Fat-tailed outcome distribution.
- **Signposts:** deposit flows, wholesale funding spreads, CDS, emergency-facility usage, regulator statements.
- **Long-run base rates:** Reinhart & Rogoff (2009) for systemic crises (deep and long equity and housing declines). Contrast with idiosyncratic failures, which usually don't spread.

### A6. Corporate events (seed hypotheses for the engine to test)
- **M&A:** target premium and completion probability. Acquirers often fall on announcement, and Mitchell, Pulvino & Stafford (2004) attribute almost half of that drop to merger-arbitrage short selling in stock deals. Hostile deals complete less often (Mitchell & Pulvino 2001). Use the deal spread as the market-implied probability.
- **Spinoffs:** historical outperformance of the spun-off firm (Cusatis, Miles & Woolridge 1993), with forced selling as the mechanism. Test for decay.
- **Buybacks:** long-run abnormal returns after open-market buyback announcements, especially for value stocks (Ikenberry, Lakonishok & Vermaelen 1995). Test for decay and for authorized-versus-executed buybacks.
- **Insider buying:** opportunistic (non-routine) insider trades carry information; routine trades do not (Cohen, Malloy & Pomorski 2012). India: PIT disclosures; also watch promoter pledges (reflexive risk).
- **Earnings surprises:** the announcement reaction captures most of it; post-announcement drift historically existed (Bernard & Thomas 1989) but has weakened (Martineau 2022). Show the day-1 reaction and the drift separately.
- **IPOs:** first-day pop, then long-run underperformance against matched firms in the classic sample (Ritter 1991). Split by issue type (fresh issue vs OFS share in India).
- **CFO/CEO sudden exits, auditor resignations:** engine-measured. Subtype on "effective immediately," "no successor" and "stated disagreement," which literature and practice associate with worse outcomes.

---

## Appendix B. Sources consulted (via TinyFish search/fetch, 2026-10-24)

- MacKinlay 1997 (BU mirror): https://www.bu.edu/econ/files/2011/01/MacKinlay-1996-Event-Studies-in-Economics-and-Finance.pdf
- Kothari & Warner: https://www.bu.edu/econ/files/2011/01/KothariWarner2.pdf
- Barber & Lyon / long-run tests: https://www.eventstudytools.com/long-run-event-study
- Reference class forecasting overview: https://en.wikipedia.org/wiki/Reference_class_forecasting ; Flyvbjerg 2008: https://www.tandfonline.com/doi/abs/10.1080/09654310701747936
- Tetlock's Ten Commandments (Farnam Street summary): https://fs.blog/ten-commandments-for-superforecasters/
- Mauboussin, Who Is on the Other Side?: https://www.morganstanley.com/im/publication/insights/articles/article_whoisontheotherside
- Expectations Investing: https://www.expectationsinvesting.com/
- Marks memo "It's Not Easy" (second-level thinking): https://www.oaktreecapital.com/docs/default-source/memos/2015-09-09-its-not-easy.pdf
- Steinhardt on variant perception: https://acquirersmultiple.com/2021/12/michael-steinhardt-develop-a-variant-perception/
- Greenblatt / spinoff study summary: https://medium.com/@mpf/greenblatt-on-spin-offs-72cfcdbdd6d6 ; Cusatis et al. 1993: https://www.sciencedirect.com/science/article/pii/0304405X9390009Z
- Soros on boom-bust: https://www.georgesoros.com/2014/01/13/fallibility-reflexivity-and-the-human-uncertainty-principle-2
- Dalio, Big Debt Crises: https://www.bridgewater.com/big-debt-crises/principles-for-navigating-big-debt-crises-by-ray-dalio.pdf
- Taleb, Statistical Consequences of Fat Tails: https://arxiv.org/abs/2001.10488
- Caldara & Iacoviello GPR: https://www.matteoiacoviello.com/gpr.htm ; AER: https://www.aeaweb.org/articles?id=10.1257/aer.20191823
- Baker, Bloom & Davis EPU: https://www.policyuncertainty.com/
- PEAD review (Fink 2021): https://www.sciencedirect.com/science/article/pii/S2214635020303750 ; Martineau: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607 ; UCLA Anderson Review 2026: https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- Ball & Brown retrospective: https://publications.aaahq.org/accounting-review/article/89/1/1/3546/Ball-and-Brown-1968-A
- Bernanke & Kuttner: https://www.federalreserve.gov/pubs/feds/2004/200416/200416pap.pdf
- Kilian 2009: https://www.aeaweb.org/articles?id=10.1257/aer.99.3.1053 ; Hamilton 1985: https://www.jstor.org/stable/41322100
- Harvey, Liu & Zhu: https://academic.oup.com/rfs/article/29/1/5/1843824 ; Deflated Sharpe: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Fama 1998: https://papers.ssrn.com/sol3/papers_newer.cfm?abstract_id=15108
- Cutler, Poterba & Summers: https://www.nber.org/papers/w2538 ; Baker et al. jumps: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3821973
- Mitchell & Pulvino 2001: https://www.jstor.org/stable/2697819 ; Ritter 1991: https://www.jstor.org/stable/2328687 ; Ikenberry et al. 1995: https://www.sciencedirect.com/science/article/abs/pii/0304405X9500826Z ; Cohen, Malloy & Pomorski: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1692517
- LPL, Lessons From Past Conflicts (Apr 2026): https://www.lpl.com/research/weekly-market-commentary/lessons-from-past-conflicts-for-todays-stock-market.html
- Morgan Stanley, Iran, Oil and the U.S. Economy (Mar 2026): https://www.morganstanley.com/insights/articles/iran-war-oil-shock-stock-market-impacts
- CFA Institute, When the Fed Cuts (Sep 2025): https://rpc.cfainstitute.org/blogs/enterprising-investor/2025/when-the-fed-cuts-lessons-from-past-cycles-for-investors
- FRBSF, Market Reactions to Tariff Announcements (Oct 2025): https://www.frbsf.org/research-and-insights/publications/economic-letter/2025/10/market-reactions-to-tariff-announcements/ ; Wengerek et al. 2025: https://www.sciencedirect.com/science/article/pii/S1544612325006415
- Icon arrays (Galesic et al. 2009): https://pubmed.ncbi.nlm.nih.gov/19290713/ ; van der Bles et al. 2020: https://www.pnas.org/doi/10.1073/pnas.1913678117 ; Spiegelhalter 2017: https://regulation.org.uk/library/2017-Spiegelhalter-Risk_and_Uncertainty_Communication.pdf
- Stock-bond correlation regimes (Vanguard): https://www.vanguard.co.uk/professional/vanguard-365/investment-knowledge/portfolio-construction/understanding-stock-bond-correlations
- Hedge-fund one-pager format: https://www.streetofwalls.com/finance-training-courses/hedge-fund-training/hedge-fund-case-study-1-page/ ; Equity research report structure: https://mergersandinquisitions.com/equity-research-report/

Notes on confidence: book-level summaries (Marks, Greenblatt, Soros, Dalio, Graham, Taleb, Heuer, Kent) come from my prior knowledge of these widely-discussed works, checked against the summaries and abstracts above. I did not re-read them in full. The specific figures quoted (Bernanke-Kuttner ~1%, Bernard-Thomas ~2% over 60 days, LPL drawdowns, CFA cut-cycle counts, Morgan Stanley 8.4%, Cusatis ~10%/yr) were confirmed in the fetched sources or their abstracts. The fake-news market incidents (AP 2013, Pentagon image 2023, SEC account 2024) are from memory and should be re-cited before use in public copy.
