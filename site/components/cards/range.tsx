import type { PlanRange, PlanRangeCard, RangeRow } from "@/lib/contract";
import { EmptyLedger } from "@/components/pencil";

const ROW_H = 44;
const SERIES = { before: "var(--chart-1)", after: "var(--chart-2)" } as const;

/** Two bars on one scale from zero: bad case to good case, a tick at the middle, the money put in pencilled across. */
function RangeSketch({ r }: { r: PlanRange }) {
  const { bar } = r;
  const base = bar.rows.length * ROW_H;
  const row = (rw: RangeRow, i: number) => (
    <g key={rw.series}>
      <text x="0" y={i * ROW_H + 12} className="fill-graphite text-[12px]">{rw.name}</text>
      <rect x={`${rw.x}%`} y={i * ROW_H + 18} width={`${rw.w}%`} height="16" rx="4" fill={SERIES[rw.series]} />
      <line x1={`${rw.median_x}%`} x2={`${rw.median_x}%`} y1={i * ROW_H + 14} y2={i * ROW_H + 38} stroke="var(--ink)" strokeWidth="2" />
    </g>
  );
  return (
    <figure className="grid gap-2">
      <svg width="100%" height={base + 24} role="img" aria-label={`Before inflation, from ${r.nominal.p10} to ${r.nominal.p90}, middle ${r.nominal.median}. After inflation, from ${r.real.p10} to ${r.real.p90}, middle ${r.real.median}. Put in: ${r.invested}.`} className="overflow-visible">
        {bar.rows.map(row)}
        <line x1={`${bar.invested_x}%`} x2={`${bar.invested_x}%`} y1="14" y2={base} stroke="var(--chart-3)" strokeWidth="1.5" strokeDasharray="4 3" filter="url(#pencil)" />
        <text x="0" y={base + 18} className="fill-graphite text-[12px]">{bar.zero_label}</text>
        <text x={`${bar.invested_x}%`} y={base + 18} textAnchor="middle" className="fill-graphite text-[12px]">{r.invested}</text>
      </svg>
      <figcaption className="text-note text-graphite">
        Each bar runs from the bad case to the good case, on one scale from {bar.zero_label}. The tick on each bar is the middle case. The dashed line is the {r.invested} put in.
      </figcaption>
    </figure>
  );
}

function Cases({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <div className="grid gap-1">
      <h4 className="font-medium">{title}</h4>
      <dl className="grid gap-1">
        {rows.map(([name, value]) => (
          <div key={name} className="flex flex-wrap justify-between gap-x-4 border-b border-rule py-1">
            <dt className="text-graphite">{name}</dt>
            <dd className="figures font-display text-head">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function RangeView({ card, label }: { card: PlanRangeCard; label?: string | null }) {
  const r = card.range;
  if (!r) return card.note ? <EmptyLedger note={card.note} /> : null;
  return (
    <div className="grid gap-5">
      <p>
        {r.plan}. <span className="figures">{r.monthly}</span> a month for {r.years} years puts in{" "}
        <span className="figures">{r.invested}</span>.
      </p>
      {label && <p className="text-graphite">{label}</p>}
      <RangeSketch r={r} />
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
      <div className="grid gap-2">
        <h4 className="font-medium">What a fall felt like</h4>
        <p className="max-w-[65ch]">
          In {r.hit_limit} of the paths, the plan fell by {r.fall_limit} or more at some point. That is the fall picked as one you can sit through.
        </p>
        <p className="max-w-[65ch]">
          In the middle case, the worst fall was {r.worst_fall_pct}, about {r.worst_fall_rupees} of the money held then. {r.recovery}
        </p>
        <p className="text-note text-graphite">
          {r.paths} paths of real months from {r.window}. Index prices only, so dividends are left out. No taxes or fund costs, so the range runs a little high.
        </p>
      </div>
    </div>
  );
}
