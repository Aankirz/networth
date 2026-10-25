"use client";

import { ArrowUpRight } from "lucide-react";

import { EmptyNote } from "@/components/cards/empty";
import { Sketch } from "@/components/sketch";
import { historySpec, historyTable } from "@/lib/charts";
import type { HistoryCard, HistoryRow } from "@/lib/contract";

function Row({ row }: { row: HistoryRow }) {
  return (
    <li className="grid gap-2">
      <div className="grid gap-1 sm:flex sm:items-baseline sm:justify-between sm:gap-x-4">
        <h4 className="text-sm font-medium">{row.asset_name}</h4>
        <p className="figure flex items-baseline gap-1.5 text-sm text-ink-2">
          <span className="text-ink">{row.count}</span> ·
          <svg width="3" height="11" viewBox="0 0 3 11" aria-hidden="true" className="self-center"><rect width="3" height="11" rx="1" fill="var(--accent-stroke)" /></svg>
          normal {row.normal}
        </p>
      </div>
      <Sketch
        title={`${row.asset_name}, ${row.count}`}
        height={34}
        build={(w) => historySpec(row, w)}
        table={historyTable([row])}
      />
      <p className="max-w-[65ch] text-sm text-ink-2">{row.sentence}</p>
      {row.why_url && (
        <a href={row.why_url} className="inline-flex w-fit items-center gap-1 text-sm text-ink-2 hover:text-ink" rel="noopener">
          The past cases, one by one <ArrowUpRight aria-hidden="true" className="size-3.5" />
        </a>
      )}
    </li>
  );
}

export function HistoryRows({ card }: { card: HistoryCard }) {
  if (!card.rows.length) return card.note ? <EmptyNote note={card.note} /> : null;
  return (
    <ul className="grid gap-6">
      {card.rows.map((row) => (
        <Row key={`${row.type}-${row.asset}`} row={row} />
      ))}
    </ul>
  );
}
