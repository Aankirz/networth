# Phase 13B: an answer screen better than Perplexity Finance

## Why

The owner compared our web demo with https://www.perplexity.ai/finance and said ours is worse, and that the UI and UX should have been better.

Perplexity Finance shows:
- index tiles with sparklines and a red or green change
- an answer that starts with a bold verdict line
- a clean table of the user's numbers
- inline source chips on every claim, and a Sources panel
- a collapsible market summary
- answers in about 3 seconds

Ours shows one grey paragraph with no numbers, no chart and no table. It opens with a lecture. A failed answer says "Networth didn't answer just now". The answers themselves are being fixed in Phase 13A. This phase is how they look and feel.

## Read first

0. Invoke `pstack:poteto-mode`, then **`impeccable`** (the owner named it). Run its critique on `/demo` before you start and again at the end. Then `design-taste-frontend`, `hallmark`, `emil-design-eng` and `dataviz`.
1. Use the libraries the owner gave us: shadcn/ui (https://ui.shadcn.com, including https://ui.shadcn.com/charts) and the generative-UI card pattern from https://github.com/CopilotKit/OpenIntelligentUI. Keep the pencil chart look (rough.js) the product already has. Look every API up. Never invent a prop, flag or version.
2. Open https://www.perplexity.ai/finance and ask it 3 questions yourself. Screenshot its answer layout at 1440 and 390 px as the bar.

## Build

Own `site/`. Do not touch `networth/`, which 13A owns.

1. **The market strip.** The top of `/demo` shows Nifty 50, Sensex, Bank Nifty and one US index as tiles. Each tile has the price, the change in red or green, and a pencil sparkline. Use real data from 13A's endpoints. Until 13A ships them, show "loading" states, never fake numbers.
2. **Answer cards.** Render 13A's typed cards (`price`, `history`, `position`, `compare`, `market_today`, `news`) as native cards:
   - the lead line in bold
   - the numbers in a table
   - a chart where there is a series
   - inline source chips that open the source
   - a Sources panel listing them
   
   Text-only answers keep the clean prose style.
2a. **Intelligent UI on every answer (owner's reference image).** The owner showed the OpenIntelligentUI "Plain Chat vs Chat with Intelligent UI" demo. The plain chat answers "Will $800 a month get me to retirement by 60?" with a paragraph. The intelligent one says "Let's map it out. Adjust anything below." and draws a projection card with:
   - a huge headline number, "$694,900 at age 60"
   - a pill, "≈ $27,800 / yr"
   - an area chart of the balance against a dashed "You put in" line
   - live sliders for Monthly, Return and Age, which recompute instantly in the browser

   Every Networth answer that has numbers must work like this. Use https://github.com/CopilotKit/OpenIntelligentUI's pattern for choosing and rendering a component per answer. Read its README and code, and look up every API. Required interactive cards:
   - **goal / SIP projection**, with sliders for monthly, return, years and step-up, plus a "what history did" band
   - **position**, with your P&L and a slider for "what if it moves ±X%"
   - **history**, with a range switch for 1Y, 3Y, 5Y and 10Y, and drawdowns marked
   - **compare**, with two series and a toggle
   - **rating**, from 13C: the view, the score dial, the drivers and the track record
   - **sectors**, from 13C: a heat strip with the news on tap
   
   The owner's second image shows CopilotKit's setup, `<CopilotKit runtimeUrl="/api/copilotkit" openGenerativeUI={…} a2ui={…}>`, and a card that reads "October spending $4,280". It has a donut with a legend and one green insight pill, "Dining is up 18% vs September". Two things to take from it:
   - **Every card ends with one insight pill**, the "so what" in one line, coloured by meaning.
   - **Use A2UI if it fits.** Our Python server is the only brain: no model and no key in the browser or on Vercel. Check whether A2UI's declarative spec can carry our typed cards, so that the server emits the spec and CopilotKit renders it. If it can, use it, and tell the 13A builder the shape. If it needs a model in the runtime, keep our own typed cards and copy the look. Record which path you took and why.

   Recompute in the browser from the data the server sent. A slider never calls the model. Lead each card with one human line, like "Let's map it out. Adjust anything below."
3. **Charts in answers.** Use shadcn charts with the pencil style for series: price over time, drawdowns, and two-line compare. Hovering or tapping shows the value and date. They must be readable at 320 px.
4. **Speed and states.** Stream the answer, or show a skeleton of the card type within 300 ms. A failed answer retries once by itself, then shows a plain retry with what went wrong. Never say "check your connection" when our server is the problem.
5. **Follow-ups.** Under each answer, show 3 suggested follow-ups that fit it (for example "Compare with Zomato", "What did history do after a 20% fall?", "How does this fit my plan?").
6. **One footer.** "Research, not advice." appears once, small, under the answer. Never in the body.
7a. **No filler copy anywhere on the site.** The owner called "Morning. It's your investing day, and ₹1,50,000 is ready." meaningless. It appears in `site/components/landing/mocks.tsx:110` and the demo. Audit every fixed string in `site/` like a sharp product lead. Each line must tell the user something they didn't know, or be cut. Put a before and after list in the report.
7. **The landing page mocks.** The owner flagged that the landing page's live chat mock is "just texty". It opens with "Whether to put money in is your call, so I won't say yes or no", in plain grey bubbles. Rewrite every landing mock to show the new answer cards: a `position` card with a P&L table, a `history` card with a pencil chart, and a `market_today` strip. Use the new no-lecture copy. The landing page must show the product at its best.
8. **Telegram parity.** Nothing to build here, but check the pencil chart style matches the PNG 13A sends.

## Not in this phase

- No changes to the Python answers or guard (13A).
- No new sign-in work (Phase 11 is done).

## Done when

1. The impeccable critique score before and after is in the report, and after is at least 34/40.
2. `/demo` shows the live market strip with real numbers and sparklines once 13A's endpoint is live.
3. Each card type renders with its table, chart and source chips. A Playwright test covers each type against fixtures.
4. Screenshots at 390 and 1440, dark and light, of `/demo` empty, a `history` answer and a `position` answer, side by side with Perplexity's screenshots, are in `docs/phases/phase-13b-shots/`.
5. A failed request retries, then shows a clear error. A test covers it.
6. The lint, type check, build and Playwright all exit 0. Record each exit code.

## The gate

`npm run lint`, the type check, `npm run build` and Playwright in `site/`, plus `make check` at the root. Capture each exit code.

## Branch policy

Push straight to main after `git pull --rebase`. A push that touches `site/` deploys production, so push only after the gate passes. Build card renderers against the contract 13A commits first. Pull often.

## OWNER NEEDED protocol

Print `OWNER NEEDED: <what> — <how>` before any human-only step.

End with `PHASE 13B READY FOR REVIEW`.
