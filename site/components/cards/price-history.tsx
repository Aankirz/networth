"use client";

import { useState } from "react";

import { Insight, TONE } from "@/components/cards/price";
import { PriceLine, type Span } from "@/components/cards/price-line";
import { SourceChip } from "@/components/cards/source-chip";
import type { Drawdown, Point, PriceHistoryCard } from "@/lib/contract";
import { signed } from "@/lib/money";

// How a share or an index did over the years asked. The range switch cuts the server's closes
// in the browser: the full span shows the server's own return, a shorter one the change between
// the first and last close shown. The worst falls are shaded where they fall in the span.

const RANGES = [1, 3, 5, 10] as const;
const YEAR_MS = 365.25 * 24 * 3600 * 1000;

/** "14 Jan 2020" as the ISO day the series uses. */
const isoDay = (day: string) => new Date(`${day} UTC`).toISOString().slice(0, 10);

function yearsIn(points: Point[]): number {
  if (points.length < 2) return 0;
  return (Date.parse(points.at(-1)!.t) - Date.parse(points[0].t)) / YEAR_MS;
}

function lastYears(points: Point[], years: number): Point[] {
  const start = new Date(Date.parse(points.at(-1)!.t) - years * YEAR_MS).toISOString().slice(0, 10);
  return points.filter((p) => p.t >= start);
}

const inSpan = (d: Drawdown, from: string) => isoDay(d.peak) >= from;

function Fall({ fall, shown }: { fall: Drawdown; shown: boolean }) {
  return (
    <li data-fall="" data-shown={shown || undefined} className={`grid gap-0.5 ${shown ? "" : "opacity-50"}`}>
      <p className="text-sm text-ink tabular-nums">
        <span style={{ color: "var(--down)" }}>{fall.fall}</span> from {fall.peak} to {fall.trough}
      </p>
      <p className="text-xs text-ink-3">{fall.recovered ? `Back to its peak by ${fall.recovered}` : "Not back to its peak yet"}</p>
    </li>
  );
}

export function PriceHistoryView({ card }: { card: PriceHistoryCard }) {
  const all = card.series.points;
  const span = yearsIn(all);
  // A range is offered when the closes cover most of it; the full span is always the last choice.
  const offered = RANGES.filter((y) => y < span * 0.95);
  const [years, setYears] = useState<number | null>(null);
  const points = years === null ? all : lastYears(all, years);
  const from = points[0]?.t ?? "";
  const change = points.length > 1 ? points.at(-1)!.v / points[0].v - 1 : 0;
  const direction = change > 0 ? "up" : change < 0 ? "down" : "flat";
  const headline = years === null ? card.returns[0] : { label: `${years} ${years === 1 ? "year" : "years"}`, value: signed(`${Math.abs(change * 100).toFixed(2)}%`, change) };
  const spans: Span[] = card.drawdowns.filter((d) => inSpan(d, from)).map((d) => ({ from: isoDay(d.peak), to: isoDay(d.trough), label: d.fall }));
  const worst = card.drawdowns.find((d) => inSpan(d, from));
  const series = { ...card.series, points };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4" data-history="">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-xs text-ink-3">{card.name} · {card.symbol}</p>
          <p className="flex flex-wrap items-baseline gap-x-2" data-headline="">
            <span className="figure text-3xl font-semibold tracking-[-0.02em] tabular-nums" style={{ color: TONE[direction].color }}>{headline?.value}</span>{" "}
            <span className="text-sm text-ink-2">over {headline?.label}</span>
          </p>
          {years !== null && <p className="text-xs text-ink-3">From the first and last close on the line.</p>}
        </div>
        {offered.length > 0 && (
          <div role="group" aria-label="Range" className="flex rounded-full border border-line p-0.5">
            {[...offered, null].map((y) => (
              <button
                key={y ?? "all"}
                type="button"
                aria-pressed={years === y}
                onClick={() => setYears(y)}
                className="rounded-full px-3 py-1 text-xs font-medium text-ink-2 transition-colors aria-pressed:bg-[var(--bubble)] aria-pressed:text-ink"
              >
                {y === null ? "All" : `${y}Y`}
              </button>
            ))}
          </div>
        )}
      </header>
      <PriceLine series={series} currency={null} direction={direction} spans={spans} height={180} />
      {years === null && card.returns.length > 1 && (
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
          {card.returns.map((r) => (
            <div key={r.label} className="contents">
              <dt className="text-ink-2">{r.label}</dt>
              <dd className="text-right text-ink tabular-nums">{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {card.drawdowns.length > 0 && (
        <section aria-label="The worst falls" className="grid gap-2">
          <h4 className="text-xs text-ink-3">The worst falls since {card.from}</h4>
          <ul className="grid gap-2">
            {card.drawdowns.map((d) => <Fall key={d.peak} fall={d} shown={inSpan(d, from)} />)}
          </ul>
        </section>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Insight tone={worst ? "var(--down)" : "var(--ink-3)"}>
          {worst
            ? `The worst fall in this stretch was ${worst.fall}${worst.recovered ? `, back by ${worst.recovered}` : ", not back yet"}.`
            : `None of the worst falls since ${card.from} came in this stretch.`}
        </Insight>
        <SourceChip source={card.source} />
      </div>
    </div>
  );
}
