"use client";

import { useState } from "react";

import { Change, currencyIn, Insight, TONE, YearRange } from "@/components/cards/price";
import { PriceLine } from "@/components/cards/price-line";
import { SourceChip } from "@/components/cards/source-chip";
import type { PositionCard } from "@/lib/contract";
import { moneyShort, parseAmount, signed } from "@/lib/money";

// A holding the reader typed: what it is worth at the last close against what they paid, and a
// slider for "what if it moves". The slider works only from the server's own figures, in the
// browser, and never asks the server again.

const MOVE_LIMIT = 50;

interface Basis {
  quantity: number;
  paid: number;
  now: number;
  currency: string;
}

/** The raw figures the slider needs, read back from the server's strings; null if any is missing. */
function basisOf(card: PositionCard): Basis | null {
  const quantity = parseAmount(card.quantity);
  const paid = parseAmount(card.avg_cost);
  const now = card.series.points.at(-1)?.v ?? parseAmount(card.price);
  const currency = currencyIn(card.avg_cost);
  if (!quantity || !paid || !now || !currency) return null;
  return { quantity, paid, now, currency };
}

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;

function WhatIf({ card, basis }: { card: PositionCard; basis: Basis }) {
  const [move, setMove] = useState(0);
  const value = basis.quantity * basis.now * (1 + move / 100);
  const gain = value - basis.quantity * basis.paid;
  const moved = signed(`${Math.abs(move)}%`, move);
  return (
    <div className="grid gap-2 rounded-lg border border-line p-3" data-whatif="">
      <label className="flex items-baseline justify-between gap-3 text-sm text-ink-2">
        <span>If {card.name} moves</span>
        <span className="figure text-ink tabular-nums">{moved}</span>
      </label>
      <input
        type="range"
        min={-MOVE_LIMIT}
        max={MOVE_LIMIT}
        step={1}
        value={move}
        onChange={(e) => setMove(Number(e.target.value))}
        aria-label={`How much ${card.name} moves`}
        aria-valuetext={moved}
        className="w-full accent-[var(--ink)]"
      />
      <p className="text-sm text-ink tabular-nums" data-whatif-out="" aria-live="polite">
        Worth {moneyShort(value, basis.currency)},{" "}
        <span style={{ color: TONE[gain < 0 ? "down" : gain > 0 ? "up" : "flat"].color }}>
          {signed(moneyShort(Math.abs(gain), basis.currency), Math.round(gain))}
        </span>{" "}
        on what you put in.
      </p>
    </div>
  );
}

const ROWS: { label: string; key: keyof PositionCard }[] = [
  { label: "Shares", key: "quantity" },
  { label: "You paid, each", key: "avg_cost" },
  { label: "Last close", key: "price" },
  { label: "You put in", key: "invested" },
  { label: "Worth now", key: "value" },
];

function insightOf(card: PositionCard, basis: Basis | null): { text: string; tone: string } {
  if (basis && basis.now < basis.paid) {
    return { text: `It needs to rise ${pct(basis.paid / basis.now - 1)} to get back to what you paid.`, tone: "var(--down)" };
  }
  return { text: `${card.gain_pct} on what you put in.`, tone: TONE[card.direction].color };
}

export function PositionView({ card }: { card: PositionCard }) {
  const basis = basisOf(card);
  const insight = insightOf(card, basis);
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4" data-position="">
      <header className="grid gap-1">
        <p className="text-xs text-ink-3">{card.name} · {card.symbol}</p>
        <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="figure text-3xl font-semibold tracking-[-0.02em] text-ink tabular-nums">{card.value}</span>
          <Change direction={card.direction} amount={card.gain} pct={card.gain_pct} />
        </p>
      </header>
      <table className="w-full text-sm">
        <caption className="sr-only">Your holding at the last close</caption>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.key} className="border-t border-line first:border-t-0">
              <th scope="row" className="py-1.5 text-left font-normal text-ink-2">{r.label}</th>
              <td className="py-1.5 text-right text-ink tabular-nums">{String(card[r.key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <PriceLine
        series={card.series}
        currency={basis?.currency ?? null}
        direction={card.direction}
        level={basis ? { value: basis.paid, label: `You paid ${card.avg_cost}` } : null}
      />
      {basis && <WhatIf card={card} basis={basis} />}
      <YearRange low={card.low_52w} high={card.high_52w} now={card.price} />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Insight tone={insight.tone}>{insight.text}</Insight>
        <SourceChip source={card.source} />
      </div>
    </div>
  );
}
