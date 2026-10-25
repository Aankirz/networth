"use client";

import { useEffect, useRef, useState } from "react";

import type { Direction, Point, Series } from "@/lib/contract";
import { price } from "@/lib/money";
import { pencil } from "@/lib/pencil";

// One pencil line of closes. Hover, a tap or the arrow keys read out the day and the close at that
// point; the line is the source's own closes, so the figure shown is the source's figure.

const PAD_Y = 8;
const DAY = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

const TONE: Record<Direction, string> = { up: "var(--up)", down: "var(--down)", flat: "var(--pencil-soft)" };

/** A stretch of the line to shade, such as a fall from its peak to its trough. */
export interface Span {
  from: string;
  to: string;
  label: string;
}

export interface PriceLineProps {
  series: Series;
  /** The currency for the read-out; null writes the close bare, as for an index. */
  currency: string | null;
  direction: Direction;
  height?: number;
  /** A level to draw dashed across the chart, such as what the reader paid. */
  level?: { value: number; label: string } | null;
  spans?: Span[];
}

function useWidth() {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const resize = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    resize.observe(el);
    return () => resize.disconnect();
  }, []);
  return { box, width };
}

function seedOf(text: string): number {
  return [...text].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 11);
}

function scale(points: Point[], width: number, height: number, extra: number[]) {
  const values = [...points.map((p) => p.v), ...extra];
  const low = Math.min(...values);
  const span = Math.max(...values) - low || 1;
  const x = (i: number) => (points.length < 2 ? width / 2 : (i / (points.length - 1)) * width);
  const y = (v: number) => PAD_Y + (1 - (v - low) / span) * (height - 2 * PAD_Y);
  return { x, y };
}

function indexOfDay(points: Point[], day: string): number {
  const i = points.findIndex((p) => p.t >= day);
  return i === -1 ? points.length - 1 : i;
}

export function PriceLine({ series, currency, direction, height = 160, level = null, spans = [] }: PriceLineProps) {
  const { box, width } = useWidth();
  const [at, setAt] = useState<number | null>(null);
  const points = series.points;
  const last = points.length - 1;
  const { x, y } = scale(points, width, height, level ? [level.value] : []);
  const strokes = width > 0 && points.length > 1 ? pencil(points.map((p, i): [number, number] => [x(i), y(p.v)]), seedOf(series.name), 0.5) : [];
  const shown = at ?? last;
  const color = TONE[direction];

  function pick(clientX: number) {
    const rect = box.current?.getBoundingClientRect();
    if (!rect || points.length < 2) return;
    setAt(Math.max(0, Math.min(last, Math.round(((clientX - rect.left) / rect.width) * last))));
  }

  function key(e: React.KeyboardEvent) {
    const step = e.shiftKey ? 20 : 1;
    const moves: Record<string, number> = { ArrowLeft: shown - step, ArrowRight: shown + step, Home: 0, End: last };
    if (!(e.key in moves)) return;
    e.preventDefault();
    setAt(Math.max(0, Math.min(last, moves[e.key])));
  }

  return (
    <figure className="grid grid-cols-[minmax(0,1fr)] gap-1.5" data-line="">
      <figcaption className="flex items-baseline justify-between gap-3 text-xs text-ink-3">
        <span className="truncate">{series.label}</span>
        <span className="figure shrink-0 text-ink tabular-nums" data-readout="" aria-live="polite">
          {points[shown] && `${DAY.format(new Date(points[shown].t))} · ${price(points[shown].v, currency)}`}
        </span>
      </figcaption>
      <div
        ref={box}
        tabIndex={0}
        role="img"
        aria-label={`${series.label}. Use the arrow keys to read each close.`}
        className="relative touch-pan-y rounded-md focus-visible:outline-2 focus-visible:outline-offset-2"
        style={{ height }}
        onPointerMove={(e) => pick(e.clientX)}
        onPointerDown={(e) => pick(e.clientX)}
        onPointerLeave={(e) => e.pointerType === "mouse" && setAt(null)}
        onKeyDown={key}
        onBlur={() => setAt(null)}
      >
        {width > 0 && (
          <svg width={width} height={height} className="absolute inset-0 overflow-visible" aria-hidden="true">
            {spans.map((s) => {
              const a = x(indexOfDay(points, s.from));
              const b = x(indexOfDay(points, s.to));
              return <rect key={s.from} data-span={s.label} x={a} y={0} width={Math.max(b - a, 2)} height={height} fill="var(--down)" opacity={0.1} rx={3} />;
            })}
            {level && (
              <g data-level="">
                <line x1={0} x2={width} y1={y(level.value)} y2={y(level.value)} stroke="var(--pencil-soft)" strokeDasharray="5 5" />
                <text x={4} y={y(level.value) - 5} className="fill-[var(--ink-3)] text-[11px]">{level.label}</text>
              </g>
            )}
            {strokes.map((d, i) => (
              <path key={i} d={d} fill="none" stroke={color} strokeWidth={i === 0 ? 1.6 : 0.9} opacity={i === 0 ? 1 : 0.45} strokeLinecap="round" />
            ))}
            {at !== null && (
              <g data-cursor="">
                <line x1={x(at)} x2={x(at)} y1={0} y2={height} stroke="var(--line-strong)" />
                <circle cx={x(at)} cy={y(points[at].v)} r={3.5} fill={color} stroke="var(--raised)" strokeWidth={2} />
              </g>
            )}
          </svg>
        )}
      </div>
    </figure>
  );
}
