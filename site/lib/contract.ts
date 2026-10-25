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
  | "price"
  | "price_history"
  | "position"
  | "compare"
  | "stock_view"
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

export type Direction = "up" | "down" | "flat";

export interface Source {
  name: string;
  url: string;
  as_of: string;
}

export interface Point {
  t: string;
  v: number;
}

export interface Series {
  name: string;
  label: string;
  points: Point[];
}

export interface PriceCard {
  type: "price";
  symbol: string;
  name: string;
  exchange: string;
  currency: string;
  price: string;
  change: string;
  change_pct: string;
  direction: Direction;
  low_52w: string;
  high_52w: string;
  series: Series;
  source: Source;
}

export interface ReturnRow {
  label: string;
  value: string;
}

export interface Drawdown {
  fall: string;
  peak: string;
  trough: string;
  recovered: string | null;
}

export interface PriceHistoryCard {
  type: "price_history";
  symbol: string;
  name: string;
  from: string;
  to: string;
  series: Series;
  returns: ReturnRow[];
  drawdowns: Drawdown[];
  source: Source;
}

export interface PositionCard {
  type: "position";
  symbol: string;
  name: string;
  quantity: string;
  avg_cost: string;
  price: string;
  invested: string;
  value: string;
  gain: string;
  gain_pct: string;
  direction: Direction;
  low_52w: string;
  high_52w: string;
  series: Series;
  source: Source;
}

export interface CompareRow {
  label: string;
  values: string[];
}

export interface CompareCard {
  type: "compare";
  from: string;
  to: string;
  series: Series[];
  columns: string[];
  rows: CompareRow[];
  source: Source;
}

export interface IndexTile {
  symbol: string;
  name: string;
  level: string;
  change: string;
  change_pct: string;
  direction: Direction;
}

export interface Reason {
  text: string;
  publishers: string[];
}

export interface MarketTodayCard {
  type: "market_today";
  day: string;
  tiles: IndexTile[];
  reasons: Reason[];
  source: Source;
}

export type Card =
  | NewsCard
  | HistoryCard
  | PlanRangeCard
  | HoldingsCard
  | TextCard
  | PriceCard
  | PriceHistoryCard
  | PositionCard
  | CompareCard
  | MarketTodayCard;

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

export type ErrorCode = "forbidden_origin" | "not_found" | "too_long" | "rate_limited" | "failed" | "signed_out" | "not_linked" | "bad_code";

export interface ApiError {
  error: ErrorCode;
  message: Message;
}
