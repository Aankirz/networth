"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { EmptyNote } from "@/components/cards/empty";
import { SourceChip } from "@/components/cards/source-chip";
import type { SectorRow, SectorsCard } from "@/lib/ratings-contract";

// The sector board (Phase 13C): a heat strip of the server's own moves for the day, week or
// month. Tapping a sector shows the confirmed stories behind it and where the number came from.

const PERIODS = [
  { key: "day", label: "Day", span: "on the day" },
  { key: "week", label: "Week", span: "this week" },
  { key: "month", label: "Month", span: "this month" },
] as const;
type Period = (typeof PERIODS)[number]["key"];

// A move this big (in percent) gets the strongest tint; smaller moves fade toward the ground.
const FULL_TINT_AT = 4;

function moved(text: string): number {
  const n = Number.parseFloat(text.replace(/[^\d.+-]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function tint(text: string): string {
  const n = moved(text);
  const share = Math.round(8 + Math.min(Math.abs(n) / FULL_TINT_AT, 1) * 32);
  return `color-mix(in oklch, ${n < 0 ? "var(--down)" : n > 0 ? "var(--up)" : "var(--ink-3)"} ${share}%, transparent)`;
}

function Stories({ row }: { row: SectorRow }) {
  return (
    <div className="grid gap-2 px-3 pb-3">
      {row.stories.length === 0 ? (
        <p className="text-sm text-ink-3">No confirmed story behind this move.</p>
      ) : (
        <ul className="grid gap-2">
          {row.stories.map((s) => (
            <li key={s.title} className="grid gap-0.5">
              <p className="text-sm text-ink">{s.title}</p>
              <p className="text-xs text-ink-3">
                {s.publishers.join(", ")}
                {s.day && ` · ${s.day}`}
              </p>
            </li>
          ))}
        </ul>
      )}
      <div><SourceChip source={row.source} /></div>
    </div>
  );
}

function Row({ row, period }: { row: SectorRow; period: Period }) {
  const [open, setOpen] = useState(false);
  const value = row[period];
  return (
    <li className="overflow-hidden rounded-xl" style={{ background: tint(value) }}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-transform duration-150 active:scale-[0.99]"
      >
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{row.name}</span>
        <span className="figure text-sm text-ink tabular-nums">{value}</span>
        <ChevronDown aria-hidden="true" className={`size-4 shrink-0 text-ink-3 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <Stories row={row} />}
    </li>
  );
}

function biggest(rows: SectorRow[], period: Period): SectorRow {
  return rows.reduce((a, b) => (Math.abs(moved(b[period])) > Math.abs(moved(a[period])) ? b : a));
}

export function SectorsView({ card }: { card: SectorsCard }) {
  const [period, setPeriod] = useState<Period>("day");
  if (card.rows.length === 0) return <EmptyNote note={card.note ?? "No sector moves yet."} />;
  const top = biggest(card.rows, period);
  const span = PERIODS.find((p) => p.key === period)!.span;
  return (
    <article data-card="sectors" className="grid gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-ink-3">Sectors · {card.as_of}</p>
        <div role="group" aria-label="Period" className="flex rounded-full border border-line p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              type="button"
              aria-pressed={period === p.key}
              onClick={() => setPeriod(p.key)}
              className="rounded-full px-3 py-1 text-xs font-medium text-ink-2 aria-pressed:bg-[var(--bubble)] aria-pressed:text-ink"
            >
              {p.label}
            </button>
          ))}
        </div>
      </header>
      {card.note && <p className="text-sm text-ink-2">{card.note}</p>}
      <ul className="grid gap-1.5">
        {card.rows.map((row) => <Row key={row.key} row={row} period={period} />)}
      </ul>
      <p data-insight className="justify-self-start rounded-full px-3 py-1 text-sm text-ink" style={{ background: tint(top[period]) }}>
        {top.name} moved most {span}, {top[period]}.
      </p>
    </article>
  );
}
