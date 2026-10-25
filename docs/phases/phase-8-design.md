# Phase 8 design · the ledger and the friend beside it

## The scene

It is the 1st of the month, around 9 pm, in Pune. A 28-year-old has ₹1,00,000 ready and their banking app open in another tab. They open their Networth link on a laptop, or on a phone in a dim room. They want one thing settled before they invest: is there anything I should know first? Then they want to ask about the thing a cousin forwarded.

Both themes matter. Light is the evening laptop. Dark is the phone in bed. Neither is a fallback, and each has its own tokens.

## The idea

**On this page, the counted past becomes a pencil ledger.** Networth's whole claim is that it counts: "6 of 9 past cases, normal 59%". Every count on the page is drawn the way a careful friend would mark a passbook. A graphite bar runs to the count, a short pencil tick marks the normal rate, and the numbers sit beside both in plain type. The competitor test holds. Perplexity Finance shows prices and heatmaps. Nobody else's page is a ledger of counted history next to a calm chat.

The live thing is the chat. Ask anything you would send the Telegram bot, and the answer arrives as a card built from the server's own data.

## Register and stance

This is product UI (impeccable's *product* register): design serves the decision. It is not a landing page. design-taste-frontend's page rules apply where they fit an app screen. No eyebrows, no monospace outside code, no gradients, no glass, no icon-topped card grids, no shadows on things at rest, and headings stay at two lines or fewer. Its imagery floor and section-variety rules are for marketing pages and are not applied here (stated deviation). Hallmark's slop gates apply in full. The brief overrides any skill where they conflict.

## Palette

Restrained, taken from the 3E server pages so `/u/{token}` on Maritime and `/u/[token]` on Vercel feel like one product. OKLCH throughout. No pure black or white.

| Role | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `oklch(96.1% 0.006 135)` | `oklch(20.6% 0.016 235)` | The ground. The cool green-grey of a passbook page. |
| `--sheet` | `oklch(98.6% 0.004 135)` | `oklch(24.4% 0.018 235)` | One tone step up, for the chat column and cards. No borders between surfaces. |
| `--ink` | `oklch(23.5% 0.028 245)` | `oklch(92.8% 0.008 135)` | All running text, at full strength. |
| `--graphite` | `oklch(45% 0.02 240)` | `oklch(75% 0.015 220)` | Pencil marks, secondary notes. |
| `--link` | `oklch(42% 0.1 250)` | `oklch(80% 0.07 245)` | The one accent: links, focus ring, the send action. About 5% of the screen. |
| `--chart-1/2/3` | shadcn's published chart tokens, as 3E used them | the same, dark set | Plan-range bars: before inflation, after inflation, what you put in. |

**Colour carries no verdict.** No red or green on a count. Holdings gains use the server's `direction` only for a glyph (▲ ▼ –), never for colour. No 🟢 🔴 ⚪ anywhere.

## Type

- **Newsreader** (display): headings, the profile's money line and the count figures. Roman only.
- **Public Sans** (text): everything else, including the chat.

These are the 3E pairing, loaded with `next/font/google` (self-hosted at build, `display: swap`). Devanagari falls back to the system's Devanagari face (Kohinoor on Apple devices, Noto Sans Devanagari on Android). It is not a third web font, because it would cost about 150 kB for a minority of turns.

The scale has four steps: 14 / 16 / 22 / 44 px on desktop, with display type tracked at -0.02em. Figures use `tabular-nums`.

## Pencil

One SVG filter, `#pencil` (`feTurbulence` plus `feDisplacementMap` at scale 1.2), gives strokes a drawn edge. It is used in four places only:

1. The count bars on history rows. A graphite fill runs to the hit rate, with a short vertical tick at the normal rate.
2. The plan-range sketch. The bars keep shadcn's chart look, and only the "what you put in" line is pencilled.
3. Empty states. A small pencilled ledger-line drawing sits beside the server's note.
4. The thinking state in the chat. A pencil line draws itself while the server answers.

Pencil never touches text. Under `prefers-reduced-motion` nothing draws, it just appears.

## Layout

- **Desktop (1024 px and up).** Two columns. The ledger (dashboard) sits on the left at about 58%. The chat is on the right, sticky, full height, on the `--sheet` tone. The chat is beside the dashboard, as the brief asks.
- **Phone (320 px and up).** One column. The chat comes first on `/demo`, because the judges are there to ask. The dashboard comes first on `/u/[token]`, because users come for their own numbers. A plain link at the top jumps to the other. No horizontal scroll at 320 px.
- **Navigation.** The wordmark, a "Sample profile" label on the demo, and a light/dark toggle. Nothing else.

## The chat (taken from OpenIntelligentUI)

- It opens straight into the conversation with four starters. They are chips that send real questions: "What happened today?", "Explain OFS in plain words", "What could my plan become?", and a sample forwarded tip.
- Each answer is one card. The card type decides the visual: news shows a source list, history a count bar, plan range a range bar, and text the message alone. The message's own words are always shown in full, and the card adds structure. It never replaces the server's words.
- "Research, not advice." shows once per answer, from `message.footer`, set quiet and italic as in Telegram.
- An expandable detail, like Telegram's `<blockquote expandable>`, is a native `<details>`.
- The reading position holds while an answer arrives. New answers announce through `aria-live="polite"`. Copy is available on hover and focus.
- A "This was forwarded to me" toggle sets `forwarded`, which mirrors Telegram's `is_forward`.

## References and what each gave

| Reference | Taken | Left |
|---|---|---|
| CopilotKit/OpenIntelligentUI | Chat-first opening, starter chips, one native component per answer type, reading position held, copy on hover and focus | The sandboxed generated-UI iframe and model-chosen renderers. Here the card type comes from the server's intent table, and no model writes UI. No code copied. |
| perplexity.ai/finance | News rows that name their sources | Heatmaps, tickers and price cards. PRODUCT.md says not to compete there. |
| kobra.systems | Every state designed (idle, sending, error, rate-limited, offline) and motion that respects reduced motion | Its component code (not used) |
| shadcn/ui and Vercel | shadcn primitives (Button, Textarea, Switch) and its chart tokens; Vercel's quiet, one-accent restraint | Default card grids and the default zinc theme |
| Gemini | The composer as a calm field fixed at the bottom of the chat column | Gradients and sparkle iconography |
| Pencil-drawn visuals | The `#pencil` filter on counts, the range's invested line and empty states | Hand-drawn type |
