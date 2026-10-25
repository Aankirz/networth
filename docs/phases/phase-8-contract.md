# Phase 8 contract · the site's JSON API

The Python server on Maritime is the truth layer. The Next.js site in `site/` reads only these four routes, from its own server, and renders what comes back. It never computes a number, never calls a model and never holds an API key.

| Route | Who | Returns |
|---|---|---|
| `GET /api/u/{token}/dashboard` | the user whose signed `/u` token this is | `Dashboard` |
| `POST /api/u/{token}/chat` | the same user | `ChatTurn` |
| `GET /api/demo/dashboard` | anyone | `Dashboard` for the sample profile |
| `POST /api/demo/chat` | anyone, rate-limited per visitor | `ChatTurn` |

The server is `networth/web/api.py`. The TypeScript below is the source of truth for the shape. `site/lib/contract.ts` is a byte-for-byte copy of the block, and `tests/test_web_api_contract.py` checks three things. The file equals the block. Every interface's field names equal the keys the real API returns. Every card type the server can send is declared here.

## Rules every field follows

1. **Only fields the server computed.** Every string a card shows is formatted on the server (`format_money`, `percent`, `sim.rupees`, `holdings.lines`). Numeric fields named `x`, `w`, `median_x`, `invested_x`, `hit` and `normal` inside a `bar` are geometry for drawing, in percent of the chart width (or in the holdings bar's own units, out of `width`). The site never prints them.
2. **The words are the server's.** `ChatTurn.text` is `plain(message)`, the same plain render Keiki email, the logs and the guard use. `message` carries the same thing split into blocks so the site can style it. The footer, "Research, not advice." in the reader's language, comes only from `message.footer` or `Dashboard.footer`.
3. **Errors carry their own words.** Every non-200 answer is an `ApiError` whose `message` holds the server's sentence in the reader's language (the hourly-cap words are Telegram's own `TOO_MANY`).
4. **No scores, ranks, buy or sell, allocation advice or F&O, and no "leans".** A history row says "6 of 9" next to "normal 59%". `near_normal` is the engine's own flag for "within normal ups and downs". `weak` is its "too few cases" flag. Neither is a direction.

## Request

`POST .../chat` takes `ChatRequest` as JSON. `text` is 1 to 4096 characters, Telegram's own message limit. Longer text gets `413 too_long` before any model runs. `lang` overrides the reply language for this turn only and is never saved. `forwarded` is Telegram's `is_forward`: true routes a pasted tip to the tip check the same way a forwarded Telegram message is.

## Status codes

| Code | `error` | When |
|---|---|---|
| 200 | | A dashboard or a chat turn |
| 403 | `forbidden_origin` | A browser `Origin` not in `NETWORTH_WEB_ORIGINS` |
| 404 | `not_found` | A token that is unsigned, expired, unknown or the demo user's. Same as `/u/{token}`. |
| 413 | `too_long` | `text` over 4096 characters |
| 422 | | A body that is not `ChatRequest` (FastAPI's validation shape) |
| 429 | `rate_limited` | Past `chat_max_per_hour` for a user, or past the demo's per-visitor or all-visitor cap |
| 500 | `failed` | The pipeline raised. The words are Telegram's `TRY_AGAIN`. |

## Which card a chat turn carries

| Intent | Card |
|---|---|
| `what_happened_today` | `news`: the confirmed stories from the same 24-hour window the answer words, with their publishers |
| `why` | `history`: the engine's `odds()` row behind the answer's `/why` link |
| `plan_range` | `plan_range`: `sim.plan_range` for the asker's own saved plan |
| every other intent | `text`: the message is the whole answer |

`holdings` appears on the dashboard. The chat pipeline has no holdings intent yet, so no chat turn carries one today.

## Types

```ts
// Generated from docs/phases/phase-8-contract.md. Edit the contract, then copy this block.

export type Lang = "en" | "hi" | "hinglish";

export type Intent =
  | "what_happened_today"
  | "why"
  | "tip_check"
  | "explain_this"
  | "plan_question"
  | "plan_range"
  | "watch"
  | "other";

export interface ChatRequest {
  text: string;
  lang?: Lang;
  forwarded?: boolean;
}

export interface TextBlock {
  kind: "text";
  text: string;
}

export interface LinkBlock {
  kind: "link";
  label: string;
  url: string;
}

export type Block = TextBlock | LinkBlock;

export interface Message {
  title: string;
  body: Block[];
  detail: string[];
  footer: string;
  preview: string | null;
}

export interface NewsItem {
  title: string;
  day: string | null;
  publishers: string[];
}

export interface NewsCard {
  type: "news";
  items: NewsItem[];
  note: string | null;
}

export interface HistoryBar {
  hit: number;
  normal: number;
}

export interface HistoryRow {
  type: string;
  asset: string;
  asset_name: string;
  sentence: string;
  count: string;
  rate: string;
  normal: string;
  weak: boolean;
  near_normal: boolean;
  bar: HistoryBar;
  why_url: string | null;
}

export interface HistoryCard {
  type: "history";
  rows: HistoryRow[];
  note: string | null;
}

export interface Cases {
  p10: string;
  median: string;
  p90: string;
}

export interface RangeCase {
  name: string;
  value: string;
}

export interface RangeRow {
  series: "before" | "after";
  name: string;
  x: number;
  w: number;
  median_x: number;
  cases: RangeCase[];
}

export interface RangeBar {
  rows: RangeRow[];
  invested_x: number;
  invested_name: string;
  zero_label: string;
}

export interface PlanRange {
  plan: string;
  monthly: string;
  years: number;
  invested: string;
  nominal: Cases;
  real: Cases;
  fall_limit: string;
  hit_limit: string;
  worst_fall_pct: string;
  worst_fall_rupees: string;
  recovery: string;
  paths: string;
  window: string;
  label: string;
  bar: RangeBar;
}

export interface PlanRangeCard {
  type: "plan_range";
  range: PlanRange | null;
  note: string | null;
}

export interface HoldingRow {
  name: string;
  bucket: string;
  units: string;
  value: string;
  gain: string;
  direction: "up" | "down" | "flat";
  ret: string;
}

export interface MixSegment {
  bucket: string;
  pct: string;
  x: number;
  w: number;
}

export interface MixRow {
  name: string;
  segments: MixSegment[];
}

export interface MixBar {
  width: number;
  rows: MixRow[];
}

export interface HoldingsCard {
  type: "holdings";
  as_of: string;
  count: number;
  rows: HoldingRow[];
  invested: string;
  value: string;
  gain: string;
  ret: string;
  mix: string[];
  bar: MixBar;
  bar_title: string;
  history: string[];
  label: string;
}

export interface TextCard {
  type: "text";
}

export type Card = NewsCard | HistoryCard | PlanRangeCard | HoldingsCard | TextCard;

export interface ChatTurn {
  trace_id: string;
  intent: Intent;
  message: Message;
  text: string;
  card: Card;
}

export interface ProfileLine {
  plan: string | null;
  money: string;
  day: string | null;
}

export interface Dashboard {
  sample: boolean;
  lang: Lang;
  profile: ProfileLine;
  news: NewsCard;
  history: HistoryCard;
  plan_range: PlanRangeCard;
  holdings: HoldingsCard | null;
  footer: string;
}

export type ErrorCode = "forbidden_origin" | "not_found" | "too_long" | "rate_limited" | "failed";

export interface ApiError {
  error: ErrorCode;
  message: Message;
}
```

## Security and isolation

- **Tokens.** The token is the signed `/u` token. `links.verify` checks it with `hmac.compare_digest`, and only then is the link token looked up, so a forged token never reaches the database. A uvicorn access-log filter rewrites `/u/<token>` to `/u/…`. The turn log has no token field.
- **One user per call.** Every route resolves the token to one profile and passes only that profile on. The dashboard reads that user's plan, holdings and last month's events. A chat turn logs its text and reply only to that user's messages. The demo user (`web:demo`) is refused on the token routes.
- **The demo.** `web:demo` is a paused profile with alerts off, so no brief, alert or watch hit is ever sent for it. It is created on first use. `uv run python -m networth.web.api reset-demo` puts it back (idempotent). Demo chats are never logged as messages.
- **CORS.** `NETWORTH_WEB_ORIGINS` lists the allowed origins, comma-separated. One `*` inside an origin covers preview hosts (`https://networth-*-aankirzs-projects.vercel.app`). A bare `*` is ignored, and plain `http` is refused except for localhost. A request with no `Origin` is the site's own server and is allowed.
- **Rate limits.** A user's turns share `store.claim_answer` and `chat_max_per_hour` with Telegram. The demo allows 8 turns per visitor per hour (in memory) and 120 per hour across every visitor (in the store). The second cap is the real limit on model spend, because the visitor key is a header the site forwards.
- **The turn log.** `data/web_turns.jsonl`, one line per turn, with `ts`, `trace_id`, a hashed `user_id`, `channel` (`web` or `demo`), `intent`, `guard`, `cost_usd` and `outcome`. Never the text, the token or the raw user id.
