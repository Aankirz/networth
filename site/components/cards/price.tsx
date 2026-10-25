"use client";

import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";

import { PriceLine } from "@/components/cards/price-line";
import { SourceChip } from "@/components/cards/source-chip";
import type { Direction, PriceCard } from "@/lib/contract";
import { parseAmount } from "@/lib/money";

// A share's last close: the price, the day's move, a year of closes and where today sits in its
// 52-week range. Every figure is the server's; the chart and the range marker only place them.

export const TONE: Record<Direction, { color: string; Icon: typeof ArrowUp }> = {
  up: { color: "var(--up)", Icon: ArrowUp },
  down: { color: "var(--down)", Icon: ArrowDown },
  flat: { color: "var(--ink-3)", Icon: ArrowRight },
};

/** The currency a server amount is written in, from its symbol. */
export function currencyIn(text: string): string | null {
  if (text.includes("₹")) return "INR";
  if (text.includes("$")) return "USD";
  return null;
}

export function Change({ direction, amount, pct }: { direction: Direction; amount: string; pct: string }) {
  const { color, Icon } = TONE[direction];
  return (
    <span data-change="" className="inline-flex items-center gap-1 text-sm font-medium tabular-nums" style={{ color }}>
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {amount} ({pct})
    </span>
  );
}

/** Low to high over a year, with a mark where the last close sits. */
export function YearRange({ low, high, now }: { low: string; high: string; now: string }) {
  const [l, h, n] = [parseAmount(low), parseAmount(high), parseAmount(now)];
  const share = l !== null && h !== null && n !== null && h > l ? Math.max(0, Math.min(1, (n - l) / (h - l))) : null;
  return (
    <div className="grid gap-1.5" data-range="">
      <p className="text-xs text-ink-3">52-week range</p>
      <div className="relative h-1.5 rounded-full bg-[var(--line-strong)]">
        {share !== null && (
          <span
            data-range-mark=""
            className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[var(--raised)] bg-[var(--ink)]"
            style={{ left: `${share * 100}%` }}
          />
        )}
      </div>
      <div className="flex justify-between text-xs text-ink-2 tabular-nums">
        <span>{low}</span>
        <span>{high}</span>
      </div>
    </div>
  );
}

/** Where the last close sits in its year, in words: the card's one "so what". */
export function whereInYear(low: string, high: string, now: string): string | null {
  const [l, h, n] = [parseAmount(low), parseAmount(high), parseAmount(now)];
  if (l === null || h === null || n === null || h <= l) return null;
  const share = (n - l) / (h - l);
  if (share >= 2 / 3) return "Nearer its 52-week high than its low.";
  if (share <= 1 / 3) return "Nearer its 52-week low than its high.";
  return "About midway between its 52-week low and high.";
}

export function Insight({ children, tone = "var(--ink-3)" }: { children: React.ReactNode; tone?: string }) {
  return (
    <p data-insight="" className="justify-self-start rounded-2xl px-3 py-1 text-sm text-ink" style={{ background: `color-mix(in oklch, ${tone} 18%, transparent)` }}>
      {children}
    </p>
  );
}

export function PriceView({ card }: { card: PriceCard }) {
  const insight = whereInYear(card.low_52w, card.high_52w, card.price);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4" data-price="">
      <header className="grid gap-1">
        <p className="text-xs text-ink-3">{card.name} · {card.exchange} · {card.symbol}</p>
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="figure text-3xl font-semibold tracking-[-0.02em] text-ink tabular-nums">{card.price}</span>
          <Change direction={card.direction} amount={card.change} pct={card.change_pct} />
        </p>
      </header>
      <PriceLine series={card.series} currency={card.currency} direction={card.direction} />
      <YearRange low={card.low_52w} high={card.high_52w} now={card.price} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        {insight && <Insight>{insight}</Insight>}
        <SourceChip source={card.source} />
      </div>
    </div>
  );
}
