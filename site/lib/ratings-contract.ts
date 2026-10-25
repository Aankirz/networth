// Phase 13C additions. Copy under the main block when the site renders them.

export type View = "Strong" | "Positive" | "Neutral" | "Weak" | "Avoid";

export type RatingKind = "stock" | "fund" | "etf" | "ipo";

export interface Source {
  name: string;
  url: string;
  as_of: string;
}

export interface Driver {
  key: string;
  label: string;
  value: string;
  effect: "up" | "down" | "flat";
  source: Source;
}

export interface Track {
  text: string;
  hits: number;
  n: number;
  since: string;
  edge: string;
  weak: boolean;
}

export interface RatingCard {
  type: "rating";
  slug: string;
  name: string;
  kind: RatingKind;
  view: View;
  score: number;
  confidence: "high" | "medium" | "low";
  outlook: string;
  drivers: Driver[];
  missing: string[];
  track: Track;
  as_of: string;
  url: string;
  currency: "INR" | "USD";
}

export interface SectorStory {
  title: string;
  day: string | null;
  publishers: string[];
}

export interface SectorRow {
  key: string;
  name: string;
  day: string;
  week: string;
  month: string;
  direction: "up" | "down" | "flat";
  stories: SectorStory[];
  source: Source;
  url: string;
}

export interface SectorsCard {
  type: "sectors";
  as_of: string;
  rows: SectorRow[];
  note: string | null;
  currency: "INR" | "USD";
}

export interface BacktestRow {
  view: View;
  n: number;
  beat: number;
  rate: string;
  excess: string;
}

export interface BacktestGroup {
  kind: "in_stock" | "in_fund" | "us_stock" | "us_fund";
  n: number;
  assets: number;
  baseline: string;
  baseline_rate: number;
  rows: BacktestRow[];
}

export interface RatingsBacktest {
  method: string;
  caveat: string;
  since: string;
  as_of: string;
  skipped: string[];
  groups: BacktestGroup[];
}
