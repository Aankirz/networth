"use client";

import { EmptyNote } from "@/components/cards/empty";
import { Sketch } from "@/components/sketch";
import { rangeSpec, rangeTable } from "@/lib/charts";
import type { PlanRange, PlanRangeCard } from "@/lib/contract";

const FAN_HEIGHT = 230;

function Cases({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="grid content-start gap-1.5">
      <h4 className="text-xs text-ink-3">{title}</h4>
      <dl className="grid gap-1">
        {rows.map(([name, value]) => (
          <div key={name} className="flex flex-wrap items-baseline justify-between gap-x-4">
            <dt className="text-sm text-ink-2">{name}</dt>
            <dd className="figure text-sm">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Fan({ r }: { r: PlanRange }) {
  return (
    <Sketch
      title={`${r.plan}, ${r.monthly} a month for ${r.years} years`}
      height={FAN_HEIGHT}
      build={(w) => rangeSpec(r, w, FAN_HEIGHT)}
      table={rangeTable(r)}
    />
  );
}

export function RangeView({ card, label }: { card: PlanRangeCard; label?: string | null }) {
  const r = card.range;
  if (!r) return card.note ? <EmptyNote note={card.note} /> : null;
  return (
    <div className="grid gap-5">
      <p className="text-sm text-ink-2">
        {r.plan}. <span className="figure text-ink">{r.monthly}</span> a month for {r.years} years puts in{" "}
        <span className="figure text-ink">{r.invested}</span>.
      </p>
      <Fan r={r} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Cases
          title="Where the money could end up"
          rows={[
            ["A bad case (1 in 10 paths did worse)", r.nominal.p10],
            ["The middle case", r.nominal.median],
            ["A good case (1 in 10 paths did better)", r.nominal.p90],
          ]}
        />
        <Cases
          title="The same range after inflation, in today's rupees"
          rows={[
            ["A bad case", r.real.p10],
            ["The middle case", r.real.median],
            ["A good case", r.real.p90],
          ]}
        />
      </div>
      <details className="group text-sm">
        <summary className="w-fit cursor-pointer text-ink-2 hover:text-ink">What a fall felt like</summary>
        <div className="mt-2 grid gap-2 text-ink-2">
          <p className="max-w-[65ch]">
            In <span className="figure text-ink">{r.hit_limit}</span> of the paths, the plan fell by{" "}
            <span className="figure text-ink">{r.fall_limit}</span> or more at some point. That is the fall picked as one you can sit through.
          </p>
          <p className="max-w-[65ch]">
            In the middle case, the worst fall was <span className="figure text-ink">{r.worst_fall_pct}</span>, about{" "}
            <span className="figure text-ink">{r.worst_fall_rupees}</span> of the money held then. {r.recovery}
          </p>
          <p className="text-xs text-ink-3">
            {r.paths} paths of real months from {r.window}. Index prices only, so dividends are left out. No taxes or fund costs, so the range runs a little high.
          </p>
        </div>
      </details>
      {label && <p className="text-sm text-ink-3">{label}</p>}
    </div>
  );
}
