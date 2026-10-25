# Phase 10 report: the web redesign and the landing page

Phase 10 turns the web app into a chat with the dashboard one click away, draws every chart by hand with rough.js, and puts a public landing page at `/`. The brief is [phase-10-web-redesign.md](phase-10-web-redesign.md) and the API contract is [phase-10-contract.md](phase-10-contract.md). Screenshots at 320 and 1440 px, dark and light, are in [phase-10-shots/](phase-10-shots/).

## What a visitor gets

- **`/`, the landing page.** A hero says what Networth is, with "Try the demo" and "Message the bot", and a working question box. The box is a plain GET form, so it works before any script loads: it opens `/demo?q=…`, and the demo asks the question on arrival and drops it from the URL. Below the hero are three steps, each beside a live piece of the sample profile, then the three channels, the line we never cross, our own negative track record from the server, a live range sketch, a six-question FAQ and the footer "Research, not advice."
- **`/demo` and `/u/<token>`, the chat.** A centred chat in the Notion AI style. The empty state is the mark, "What would you like to know about your money?", the composer and four starters. The sidebar has New chat, past chats kept only in this browser, quick links to each dashboard section, the bot and the theme.
- **Pickers.** `@` mentions point at what the dashboard holds (the news, a story, a history row, the plan, the range, the holdings, one holding). `/` runs the web's commands: brief, range, plan, holdings, dashboard and help. A bot-only command such as `/watch` gets one line pointing to the bot. A command that doesn't exist says so.
- **The dashboard.** It opens as a slide-over from the top bar, the sidebar or `/dashboard`, pins open beside the chat on wide screens, and is a full-width sheet on a phone.
- **States.** Thinking, a server error in the server's own words, unreachable, a missing route, rate-limited (with a way to the bot) and over-length are each designed and tested.

## Design direction

The scene is a 25 to 35 year old Indian investor reading on a phone at night on their investing day, so the theme is dark by default, with a light theme designed to match. The palette is restrained: near-black slate, graphite "pencil" strokes, and one highlighter accent for actions, focus and mention chips. Buckets in the holdings mix are told apart by hachure texture, never by colour, so nothing reads as a signal. Type is Geist Sans, with Geist Mono for every figure the server sends.

The taste skill dealt the "product performs" direction (seed 1584661201). The landing page follows it: the hero's working piece is the real question box, and the steps show real pieces of the sample profile rather than descriptions. Its rules on monospace, hairlines and an imagery floor of four photographs give way to the brief, which asks for the Vercel-black system and no figures we cannot back.

## Libraries

- **rough.js 4.6.6 (MIT).** It draws every chart from the server's own geometry, seeded from the chart's title so the same answer draws the same strokes every time. It loads as its own 8.8 KB gzipped chunk only when a chart scrolls into view. The strokes draw in on first view, and draw at once under reduced motion. Hover or focus shows the exact figure in Geist Mono. Every mark is a named `img`, and every chart has a hidden table.
- **CopilotKit 1.80.0 (MIT): read, not used.** It is about 794 KB gzipped and needs a CopilotRuntime or an AG-UI agent. A runtime-free path exists only through `selfManagedAgents`, documented as an Enterprise tier for production, or `agents__unsafe_dev_only`. It has no mentions feature. Its ideas are rebuilt instead: the chat-first layout, suggestion chips, native cards and copy on hover or focus.
- **bencho.dev blocks (MIT): read, nothing copied.**
- **Removed:** shadcn, @base-ui/react, class-variance-authority, cn and tw-animate-css, which nothing used after the redesign.

## The API, added to `networth/web/api.py`

- `POST /api/demo/command` and `POST /api/u/{token}/command` take `{name, lang?}`, where `name` is brief, range, plan, holdings or help. Each runs the same code as the Telegram command and returns the same text and a card. The brief uses `compose_reply`, never `send_brief`, so it is read-only. Demo commands claim a turn like demo chat, so they are rate-limited.
- `GET /api/track-record` returns our own test from the eval summary and the stats.
- `Dashboard.mentions` lists what can be mentioned. Today's stories now carry the day they were first seen, so the chat's news card can draw a timeline.
- **Until Maritime serves `/command`,** the site asks the chat the question each command stands for (`/range` asks "What could my plan become?"). That fallback runs only on a bare 404.

| Mention | Text sent to the chat | Intent |
|---|---|---|
| news | What happened today? | what_happened_today |
| story | Why does this story matter: {title}? | why |
| history | Why? What history counted for {event} and {asset} | why |
| plan | What is my plan? | plan_question |
| range | What could my plan become? | plan_range |
| holdings | How are my holdings doing? | holdings |
| holding | How are my holdings doing? About {name} | holdings |

## Numbers

- **JavaScript.** `/demo` loads 195.6 KB gzipped on first load, against a budget of 300 KB. rough.js is the separate 8.8 KB chunk above.
- **Landing LCP, local production build.** With real DevTools mobile throttling, LCP is 1.5 s and CLS is 0.032. Simulated mobile Lighthouse gave 2.26, 2.49 and 2.61 s over three runs, right at the 2.5 s target. The LCP element is the h1, and its observed LCP is 447 ms, the same as first paint. The simulated time comes from Lighthouse modelling the framework scripts on slow 4G.
- **Preview LCP: not measured.** Previews sit behind Vercel Authentication (302), and I didn't change the project's protection settings.
- **Tests.** `make check` gives 1194 passed and 12 skipped, including 28 command tests and the contract checks. Playwright gives 30 passed across the chat, the charts, the canvas and the landing page, plus 24 screenshot runs.

## What the critique and the audit changed

The critique reviewed screenshots at 320 and 1440 in both themes. The audit covered contrast, computed from the OKLCH tokens, plus keyboard paths, reduced motion, overflow and performance.

1. **Light theme ticks.** The accent ticks vanished on the light theme. A new `--accent-stroke` token sets them in amber at 3.59:1 on the page and 3.37:1 on cards (WCAG 1.4.11). All text is at least 5.57:1 in both themes.
2. **Menu button on desktop.** The phone menu button showed on desktop because the component CSS sat outside a Tailwind layer. It moved into `@layer components`.
3. **Range chart labels.** Labels were struck through by hatching and now carry a halo in the surface colour. Column names stay inside the chart at 320.
4. **Figures that wrapped.** The range case figures and the holdings Return cell wrapped badly. The figures now line up on the right, and the server's words sit under the figure instead of in the mono column.
5. **History rows.** They stacked inconsistently on phones and now stack the same way. The accent tick has a key next to "normal".
6. **Landing hero.** The hero headline broke into four lines at 1440. It now runs full width in two lines, with the sentence and buttons beside the question box. Section padding came down so no screen reads empty.
7. **Hidden chart tables.** They widened the body to 693px at 320, because `sr-only` cannot shrink a table. Each now sits in a wrapper, and the overflow tests read `body.scrollWidth`.
8. **Commands.** A missing route now degrades to the chat question. A 404 no longer says "check your connection". Past chats are titled by what they ask. The news timeline runs oldest to newest. An unknown `/` command says it doesn't exist.
9. **Small fixes.** Safari's `details` marker is hidden on the FAQ. The landing placeholder no longer truncates at 320. Geist Mono loads without a preload.

The first-visitor test is covered end to end: from `/`, "Try the demo" opens the chat, a starter or typed question gets a card, and the Dashboard button opens the dashboard, with no instructions needed.

## Known gaps

- **Command routes and dated chat news need a Maritime deploy of `api.py`.** Until then, commands use the chat fallback and the chat's news card shows no timeline. The live `/api/demo/chat` returned 500 after the outage; P9 owns that fix.
- **Screenshots go to the bot.** The API takes text only, so "Attach a screenshot" points to the bot.
- **The bot's dashboard button may be blocked.** P9's Telegram menu button opens `/u/<token>`. If Telegram Web shows it in an iframe, `frame-ancestors 'none'` blocks it. This needs an owner decision on the CSP.
- **The site's own labels are English only.** The server's words follow the chosen language, but the buttons and headings don't.
- **Mentions use fixed text.** A mention sends set text that the server routes to an intent; no model picks it.
- **A rare test flake.** The brief greets by the hour, so a command test that runs across an hour boundary can fail once.
- **The headline wraps to four lines at 320.** Two lines are not possible at a readable size.
- **Each answer shows figures twice.** The server's words appear in full above each card, which repeats some figures the card also shows. This is by design: a card adds structure and never replaces the server's words.

## Deviations from the brief

- The landing page has no photographs. The brief asks that every figure come from the server, and stock pictures would be decoration, so the live product pieces are the imagery.
- The design references' text-gradient hero and the taste skill's two-line headline rule both give way to the brief and the impeccable bans.

## The landing page, redone

The owner found the first landing page weak, so `/` was rebuilt from scratch. Maritime is the model, with Vercel's black and heyclicky's centred column as secondary references. All three were viewed in a browser at 1440. No code or assets were copied from them.

### Critique before (impeccable, on the shipped `/`)

Score 27/40. The AI slop verdict failed.

- **No hero moment.** The hero was a left-aligned headline above a grid with a paragraph and an ask box. It had no visual, and nothing on the first screen showed the product.
- **A widget instead of a promise.** The side ask box competed with the two buttons.
- **A kicker above every heading.** "How it works", "Where it lives" and "Track record" sat as small labels above each h2: the repeated-label tell.
- **Raw fragments.** The live dashboard pieces were set in plain boxes beside the step text. They read as parts of a dashboard, not as the product at work.
- **An identical card row.** The channels section was three icon-plus-text cells of the same size.
- **No motion,** except the charts drawing in.
- **A flat rhythm.** Every section used the same padding and the same two-column split.

The deterministic detector could not run (`detect.mjs`: bundled detector not found), so this is the model's assessment only.

### What it is now

- **Hero.**
  - One centred column: the hackathon pill, then "Market news, checked against history.", one line under it, and "Try the demo" and "Message the bot".
  - Under the buttons, a pencil line of monthly investing draws itself and falls. The brief's own line arrives beside the fall: "Months like this are why you have a plan."
  - A faint grid and one soft glow sit behind it. The line is a shape with no figure on it.
- **Three steps.** Each has a hand-drawn icon that draws stroke by stroke as it scrolls into view.
- **Five product mocks, each under a big two-part heading:**
  - **The Telegram chat.** It plays the phase 9 eval's LIC thread one message at a time, and the header says "typing…" before each reply. The thread runs from the question to "what should I read first?" and ends on the Hinglish answer, using the real reply text.
  - **The monthly brief.** These are the server's brief lines (`networth/brief`), filled in from the sample profile's live dashboard data.
  - **The pencil range chart.** It is drawn live from the demo data.
  - **An email reply.** It uses the real repo-rate answer text.
  - **The dashboard sheet.** It is the real plan, news and history components.
- **The rest of the page:**
  - a "why we built this" letter that states the negative result;
  - "The line we never cross";
  - the FAQ accordion;
  - a footer with "Research, not advice."

### Motion

- **Entrances.** The hero draws once and doesn't loop. Blocks below the fold fade and rise once, 90 ms apart. They use opacity and transform only.
- **The mocks** play only while on screen and loop after a six-second hold.
- **Reduced motion** and no-script both show every mock's whole exchange at once. A block is held back only if it starts below the fold, so the first screen never flickers.
- **New code:**
  - `components/landing/playback.tsx` plays the mocks;
  - `components/landing/in-view.tsx` runs the entrances;
  - `lib/pencil.ts` draws the hand-drawn strokes on the server, seeded, with no script.

### Critique after

Score 34/40. The AI slop verdict passes.

- **Fixed:**
  - the hero now has one visual and one promise;
  - every section shows the product doing the thing its heading says;
  - the kicker labels and the identical card row are gone;
  - the vertical rhythm varies by section.
- **Still short:**
  - the headline takes three lines at 320;
  - the hero bubble is a little wider than its text on desktop;
  - the brief mock shows the raw `^NSEI` ticker, because that is the server's sentence;
  - the site has no photographs, by choice, as before.

### Checks

| Gate | Exit code | Result |
| --- | --- | --- |
| `make check` | 0 | 1194 passed, 12 skipped |
| `npm run lint` | 0 | |
| `npm run typecheck` | 0 | |
| `npm run build` | 0 | clean `.next` |
| `scripts/check-build.mjs` | 0 | banned-word grep green |
| Playwright | 0 | 32 passed (9 on the landing page) |

- **LCP.** Locally with 4x CPU throttling and 1.6 Mbps at 150 ms latency, LCP is 0.70 s at 390 and 0.75 s at 1440. The LCP element is the h1.
- **Screenshots.** They are `phase-10-shots/landing-{320,1440}-{dark,light}.png` and `landing-full-*`.
