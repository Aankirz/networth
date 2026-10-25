# Phase 10 contract · the site's JSON API

This replaces `phase-8-contract.md`. Phase 10 adds two command routes, the `@` mentions on the dashboard and one public track-record route.

The Python server on Maritime is the truth layer. The Next.js site in `site/` reads only these seven routes, from its own server, and renders what comes back. It never computes a number, never calls a model and never holds an API key.

| Route | Who | Returns |
|---|---|---|
| `GET /api/u/{token}/dashboard` | the user whose signed `/u` token this is | `Dashboard` |
| `POST /api/u/{token}/chat` | the same user | `ChatTurn` |
| `GET /api/demo/dashboard` | anyone | `Dashboard` for the sample profile |
| `POST /api/demo/chat` | anyone, rate-limited per visitor | `ChatTurn` |
| `POST /api/u/{token}/command` | the user whose signed `/u` token this is | `CommandTurn` |
| `POST /api/demo/command` | anyone, rate-limited per visitor like the demo chat | `CommandTurn` |
| `GET /api/track-record` | anyone | `TrackRecord` |

The server is `networth/web/api.py`. The TypeScript below is the source of truth for the shape. `site/lib/contract.ts` is a byte-for-byte copy of the block, and `tests/test_web_api_contract.py` checks three things. The file equals the block. Every interface's field names equal the keys the real API returns. Every card type the server can send is declared here.

## Rules every field follows

1. **Only fields the server computed.** Every string a card shows is formatted on the server (`format_money`, `percent`, `sim.rupees`, `holdings.lines`). Numeric fields named `x`, `w`, `median_x`, `invested_x`, `hit` and `normal` inside a `bar` are geometry for drawing, in percent of the chart width (or in the holdings bar's own units, out of `width`). The site never prints them.
2. **The words are the server's.** `ChatTurn.text` is `plain(message)`, the same plain render Keiki email, the logs and the guard use. `message` carries the same thing split into blocks so the site can style it. The footer, "Research, not advice." in the reader's language, comes only from `message.footer` or `Dashboard.footer`.
3. **Errors carry their own words.** Every non-200 answer is an `ApiError` whose `message` holds the server's sentence in the reader's language (the hourly-cap words are Telegram's own `TOO_MANY`).
4. **No scores, ranks, buy or sell, allocation advice or F&O, and no "leans".** A history row says "6 of 9" next to "normal 59%". `near_normal` is the engine's own flag for "within normal ups and downs". `weak` is its "too few cases" flag. Neither is a direction.

## Request

`POST .../command` takes `CommandRequest` as JSON. `name` is one of the five `CommandName`s; any other name is `422`. `lang` works as it does for chat.

`POST .../chat` takes `ChatRequest` as JSON. `text` is 1 to 4096 characters, Telegram's own message limit. Longer text gets `413 too_long` before any model runs. `lang` overrides the reply language for this turn only and is never saved. `forwarded` is Telegram's `is_forward`: true routes a pasted tip to the tip check the same way a forwarded Telegram message is.

## Status codes

| Code | `error` | When |
|---|---|---|
| 200 | | A dashboard or a chat turn |
| 403 | `forbidden_origin` | A browser `Origin` not in `NETWORTH_WEB_ORIGINS` |
| 404 | `not_found` | A token that is unsigned, expired, unknown or the demo user's. Same as `/u/{token}`. |
| 413 | `too_long` | `text` over 4096 characters |
| 422 | | A body that is not `ChatRequest` or `CommandRequest` (FastAPI's validation shape) |
| 429 | `rate_limited` | Past `chat_max_per_hour` for a user's chat, or past the demo's per-visitor or all-visitor cap (demo chat and demo commands share it) |
| 500 | `failed` | The pipeline or a command raised. The words are Telegram's `TRY_AGAIN`. |

## Which card a chat turn carries

| Intent | Card |
|---|---|
| `what_happened_today` | `news`: the confirmed stories from the same 24-hour window the answer words, with their publishers |
| `why` | `history`: the engine's `odds()` row behind the answer's `/why` link |
| `plan_range` | `plan_range`: `sim.plan_range` for the asker's own saved plan |
| `holdings` | `holdings`: the asker's own saved holdings report, or `text` when they have none |
| every other intent | `text`: the message is the whole answer |

`holdings` also appears on the dashboard. The demo has no holdings, so its holdings questions get a `text` card.

## Commands

The site's `/` picker sends one of five commands. Each answers with the message Telegram sends for the same slash command and the same profile, built by the bot's own entry point, never by copy written for the web. `CommandTurn.text` equals what the Telegram bot sends, in plain text.

| Command | Entry point | Card | Before setup is done |
|---|---|---|---|
| `brief` | `briefs.compose_reply(profile, store, services, briefs.local_now(profile, now))`. Not `send_brief`, so the web never claims or saves the day's brief. | `history`: this month's history lines, the same rows and empty note as `Dashboard.history` | `briefs.NOT_SET_UP`, `text` card |
| `range` | `deliver(chat.today.plan_range(store, profile, lang), lang, services)`, as `cmd_range` | `plan_range`, as the chat's `plan_range` intent | `FINISH_FIRST`, `text` card |
| `plan` | `cmd_plan`'s first message: `PLAN_TITLE`, `plan_line(plan, lang)` and `FOOTER`. No page link, because the API's services have no link secret. The profile's step is never moved to the plan step and the edit prompt is never sent: the web shows the plan and never changes it. | `text` | `FINISH_FIRST` in front of the setup question, as `cmd_plan` sends it, `text` card |
| `holdings` | `holdings_flow.report_reply(store, profile, services, now)`. No page button, for the same reason. | `holdings`, or `text` when there are none | `FINISH_FIRST`, `text` card |
| `help` | `help_message(lang)` | `text` | the same |

- **Rate limits.** A demo command claims a turn from the demo caps, like a demo chat. A user's commands claim nothing, because Telegram's `/brief`, `/range`, `/plan`, `/holdings` and `/help` don't claim the hourly answer cap either.
- **Logs.** A user's command logs `/name` in and the plain reply out to that user's messages, as Telegram does. Demo commands log no messages. Every command appends one turn-log line with `intent` set to `/name` and `guard` null.
- **Telegram-only commands.** `/start`, `/stop`, `/pause`, `/resume`, `/link`, `/link_broker`, `/sendto`, `/watch`, `/watches` and `/unwatch` change a Telegram account or a channel. The site answers each with one line pointing to the bot (`https://t.me/networth_professor_bot`), and they never reach the server. `/dashboard` only opens the site's canvas and never reaches the server either.

## @ mentions

`Dashboard.mentions` lists what `@` can point at. Picking one sends its `text` to the chat route as plain text, so the answer is the chat pipeline's own. Each text is written so `chat._by_phrase`, the routing the server falls back to without models, sends it to the intent below (tested in `tests/test_web_api_commands.py`). The texts are English; `chat.reply_lang` still answers them in the profile's language.

| `kind` | `id` | `label` | `text` | Intent |
|---|---|---|---|---|
| `news` | `news` | `news` | `What happened today?` | `what_happened_today` |
| `story` | `story:{i}`, one per `Dashboard.news.items[i]` | the story title | `Why does this story matter: {title}?` | `why` |
| `history` | `history:{type}:{asset}`, one per `Dashboard.history.rows` row | `{type title}, {asset_name}` | `Why? What history counted for {type title} and {asset_name}` | `why` |
| `plan` | `plan` | `plan` | `What is my plan?` | `plan_question` |
| `range` | `range` | `range` | `What could my plan become?` | `plan_range` |
| `holdings` | `holdings` | `holdings` | `How are my holdings doing?` | `holdings` |
| `holding` | `holding:{i}`, one per `Dashboard.holdings.rows[i]` | the holding's name | `How are my holdings doing? About {name}` | `holdings` |

`news`, `plan`, `range` and `holdings` are always present; the demo answers its holdings question with its own text. `{type title}` is `names.TYPES[type].title`, such as "RBI rate hike". Without models, a story title that itself contains a watch phrase ("tell me when", "watch") or "what happened" routes to that intent instead; with models the classifier reads the whole sentence.

## Track record

`GET /api/track-record` takes no token and feeds the landing page. `tested` is `routes._own_test(routes.EVAL_SUMMARY)`, the same sentences the `/track-record` page shows under "When we tested ourselves", or null when the eval summary is missing. `stats` are the `/stats` page's `STATS_QUERIES` rows with their values grouped as that page groups them, or an empty list when the rates database is missing.

## Types

```ts
// Generated from docs/phases/phase-10-contract.md. Edit the contract, then copy this block.

export type Lang = "en" | "hi" | "hinglish";

export type Intent =
  | "what_happened_today"
  | "why"
  | "tip_check"
  | "explain_this"
  | "plan_question"
  | "plan_range"
  | "watch"
  | "holdings"
  | "other";

export type CommandName = "brief" | "range" | "plan" | "holdings" | "help";

export interface CommandRequest {
  name: CommandName;
  lang?: Lang;
}

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

export interface CommandTurn {
  trace_id: string;
  command: CommandName;
  message: Message;
  text: string;
  card: Card;
}

export type MentionKind = "news" | "story" | "history" | "plan" | "range" | "holdings" | "holding";

export interface Mention {
  id: string;
  kind: MentionKind;
  label: string;
  text: string;
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
  mentions: Mention[];
  footer: string;
}

export interface Stat {
  label: string;
  value: string;
}

export interface TrackRecord {
  tested: string[] | null;
  stats: Stat[];
}

export type ErrorCode = "forbidden_origin" | "not_found" | "too_long" | "rate_limited" | "failed";

export interface ApiError {
  error: ErrorCode;
  message: Message;
}
```

## Security and isolation

- **Tokens.** The token is the signed `/u` token. `links.verify` checks it with `hmac.compare_digest`, and only then is the link token looked up, so a forged token never reaches the database. A uvicorn access-log filter rewrites `/u/<token>` to `/u/…`. The turn log has no token field.
- **One user per call.** Every token route resolves the token to one profile and passes only that profile on. The dashboard reads that user's plan, holdings and last month's events. A chat turn logs its text and reply only to that user's messages. The demo user (`web:demo`) is refused on the token routes.
- **The demo.** `web:demo` is a paused profile with alerts off, so no brief, alert or watch hit is ever sent for it. It is created on first use. `uv run python -m networth.web.api reset-demo` puts it back (idempotent). Demo chats are never logged as messages.
- **CORS.** `NETWORTH_WEB_ORIGINS` lists the allowed origins, comma-separated. One `*` inside an origin covers preview hosts (`https://networth-*-aankirzs-projects.vercel.app`). A bare `*` is ignored, and plain `http` is refused except for localhost. A request with no `Origin` is the site's own server and is allowed.
- **Rate limits.** A user's turns share `store.claim_answer` and `chat_max_per_hour` with Telegram. The demo allows 8 turns per visitor per hour (in memory) and 120 per hour across every visitor (in the store). The second cap is the real limit on model spend, because the visitor key is a header the site forwards.
- **The turn log.** `data/web_turns.jsonl`, one line per turn or command, with `ts`, `trace_id`, a hashed `user_id`, `channel` (`web` or `demo`), `intent` (`/name` for a command), `guard`, `cost_usd` and `outcome`. Never the text, the token or the raw user id.
