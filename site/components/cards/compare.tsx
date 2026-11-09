"use client";

import { useState } from "react";

import { Insight } from "@/components/cards/price";
import { DAY, seedOf, useWidth } from "@/components/cards/price-line";
import { SourceChip } from "@/components/cards/source-chip";
import type { CompareCard, Series } from "@/lib/contract";
import { pencil } from "@/lib/pencil";

// Two to four shares or indices side by side, each rebased to 100 on the first day, so the lines
// show what 100 put into each became. A chip per line turns it on or off; the numbers under the
// chart are the server's table.

const HEIGHT = 180;
const PAD_Y = 10;
const BASE = 100;
const COLOURS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"];
const LEVEL = new Intl.NumberFormat("en-US", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** "−8.6%" as −8.6, for telling which column did better; null when it isn't a number. */
function valueOf(text: string): number | null {
  const n = Number.parseFloat(text.replace("−", "-").replace(/[^\d.+-]/g, ""));
  return Number.isFinite(n) ? n : null;
}

function leader(card: CompareCard): string | null {
  const row = card.rows[0];
  if (!row || card.columns.length < 2) return null;
  const scored = card.columns.map((name, i) => ({ name, value: row.values[i], n: valueOf(row.values[i] ?? "") }));
  if (scored.some((s) => s.n === null)) return null;
  const [best, ...rest] = [...scored].sort((a, b) => b.n! - a.n!);
  if (rest.some((r) => r.n === best.n)) return null;
  return `${best.name} did best over ${row.label}: ${best.value}, against ${rest.map((r) => `${r.value} for ${r.name}`).join(" and ")}.`;
}

function Lines({ series, shown }: { series: Series[]; shown: boolean[] }) {
  const { box, width } = useWidth();
  const [at, setAt] = useState<number | null>(null);
  const visible = series.filter((_, i) => shown[i]);
  const length = Math.max(...series.map((s) => s.points.length));
  const last = length - 1;
  const values = [BASE, ...visible.flatMap((s) => s.points.map((p) => p.v))];
  const low = Math.min(...values);
  const span = Math.max(...values) - low || 1;
  const x = (i: number, n: number) => (n < 2 ? width / 2 : (i / (n - 1)) * width);
  const y = (v: number) => PAD_Y + (1 - (v - low) / span) * (HEIGHT - 2 * PAD_Y);
  const shownAt = at ?? last;
  const day = series[0]?.points[Math.min(shownAt, series[0].points.length - 1)]?.t;

  function pick(clientX: number) {
    const rect = box.current?.getBoundingClientRect();
    if (!rect || length < 2) return;
    setAt(Math.max(0, Math.min(last, Math.round(((clientX - rect.left) / rect.width) * last))));
  }

  function key(e: React.KeyboardEvent) {
    const step = e.shiftKey ? 20 : 1;
    const moves: Record<string, number> = { ArrowLeft: shownAt - step, ArrowRight: shownAt + step, Home: 0, End: last };
    if (!(e.key in moves)) return;
    e.preventDefault();
    setAt(Math.max(0, Math.min(last, moves[e.key])));
  }

  return (
    <figure className="grid grid-cols-[minmax(0,1fr)] gap-1.5">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-3 text-xs text-ink-3">
        <span>100 put in on the first day, as it grew</span>
        <span className="figure text-ink tabular-nums" data-readout="" aria-live="polite">
          {day && DAY.format(new Date(day))}
          {series.map((s, i) => shown[i] && s.points[shownAt] && (
            <span key={s.name} style={{ color: COLOURS[i] }}> · {LEVEL.format(s.points[shownAt].v)}</span>
          ))}
        </span>
      </figcaption>
      <div
        ref={box}
        tabIndex={0}
        role="img"
        aria-label={`${visible.map((s) => s.name).join(" and ")}, each rebased to 100. Use the arrow keys to read each day.`}
        className="relative touch-pan-y rounded-md focus-visible:outline-2 focus-visible:outline-offset-2"
        style={{ height: HEIGHT }}
        onPointerMove={(e) => pick(e.clientX)}
        onPointerDown={(e) => pick(e.clientX)}
        onPointerLeave={(e) => e.pointerType === "mouse" && setAt(null)}
        onKeyDown={key}
        onBlur={() => setAt(null)}
      >
        {width > 0 && (
          <svg width={width} height={HEIGHT} className="absolute inset-0 overflow-visible" aria-hidden="true">
            <line x1={0} x2={width} y1={y(BASE)} y2={y(BASE)} stroke="var(--line-strong)" strokeDasharray="5 5" />
            {series.map((s, i) => shown[i] && (
              <g key={s.name} data-series={s.name}>
                {pencil(s.points.map((p, j): [number, number] => [x(j, s.points.length), y(p.v)]), seedOf(s.name), 0.5).map((d, k) => (
                  <path key={k} d={d} fill="none" stroke={COLOURS[i]} strokeWidth={k === 0 ? 1.6 : 0.9} opacity={k === 0 ? 1 : 0.45} strokeLinecap="round" />
                ))}
              </g>
            ))}
            {at !== null && <line x1={x(at, length)} x2={x(at, length)} y1={0} y2={HEIGHT} stroke="var(--line-strong)" />}
          </svg>
        )}
      </div>
    </figure>
  );
}

export function CompareView({ card }: { card: CompareCard }) {
  const [shown, setShown] = useState(() => card.series.map(() => true));
  const said = leader(card);

  function flip(i: number) {
    const next = shown.map((on, j) => (j === i ? !on : on));
    if (next.some(Boolean)) setShown(next);
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4" data-compare="">
      <header className="grid gap-2">
        <p className="text-xs text-ink-3">{card.from} to {card.to}</p>
        <div role="group" aria-label="Lines to show" className="flex flex-wrap gap-1.5">
          {card.series.map((s, i) => (
            <button
              key={s.name}
              type="button"
              aria-pressed={shown[i]}
              onClick={() => flip(i)}
              className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs text-ink-3 transition-[color,border-color,transform] duration-150 active:scale-[0.97] aria-pressed:border-line-strong aria-pressed:text-ink"
            >
              <span aria-hidden="true" className="size-2 shrink-0 rounded-full" style={{ background: shown[i] ? COLOURS[i] : "var(--line-strong)" }} />
              <span className="truncate">{s.name}</span>
            </button>
          ))}
        </div>
      </header>
      <Lines series={card.series} shown={shown} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">{card.columns.join(" against ")}, {card.from} to {card.to}</caption>
          <thead>
            <tr className="text-xs text-ink-3">
              <th scope="col" className="py-1.5 text-left font-normal"><span className="sr-only">Measure</span></th>
              {card.columns.map((c, i) => (
                <th key={c} scope="col" className="py-1.5 pl-3 text-right font-normal">
                  <span className="flex items-start justify-end gap-1.5">
                    <span aria-hidden="true" className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: COLOURS[i] }} />
                    <span>{c}</span>
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {card.rows.map((r) => (
              <tr key={r.label} className="border-t border-line">
                <th scope="row" className="py-1.5 text-left font-normal text-ink-2">{r.label}</th>
                {r.values.map((v, i) => <td key={i} className="py-1.5 pl-3 text-right text-ink tabular-nums">{v}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {said && <Insight>{said}</Insight>}
        <SourceChip source={card.source} />
      </div>
    </div>
  );
}
