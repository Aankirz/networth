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
