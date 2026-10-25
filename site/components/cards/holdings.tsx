import type { HoldingsCard, MixRow } from "@/lib/contract";

const GLYPH = { up: "▲", down: "▼", flat: "–" } as const;
const BUCKET = { safety: "var(--chart-3)", core: "var(--chart-2)", growth: "var(--chart-1)" } as Record<string, string>;
function MixBar({ row, width }: { row: MixRow; width: number }) {
  return (
    <div className="grid gap-1">
      <p className="text-note text-graphite">{row.name}</p>
      <svg viewBox={`0 0 ${width} 12`} preserveAspectRatio="none" className="block h-3 w-full" aria-hidden="true">
        {row.segments.map((s) => (
          <rect key={s.bucket} x={s.x} y="0" width={s.w} height="12" fill={BUCKET[s.bucket] ?? "var(--graphite)"} />
        ))}
      </svg>
    </div>
  );
}

function MixBars({ card }: { card: HoldingsCard }) {
  return (
    <figure className="grid gap-3" role="img" aria-label={card.bar_title}>
      {card.bar.rows.map((row) => (
        <MixBar key={row.name} row={row} width={card.bar.width} />
      ))}
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-note text-graphite" aria-hidden="true">
        {(card.bar.rows[0]?.segments ?? []).map((s) => (
          <li key={s.bucket} className="flex items-center gap-1.5">
            <svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" fill={BUCKET[s.bucket] ?? "var(--graphite)"} /></svg>
            {s.bucket}
          </li>
        ))}
      </ul>
    </figure>
  );
}

export function HoldingsView({ card, label }: { card: HoldingsCard; label?: string | null }) {
  return (
    <div className="grid gap-5">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        {[["Put in", card.invested], ["Worth now", card.value], ["Gain or loss", card.gain]].map(([k, v]) => (
          <div key={k}>
            <dt className="text-note text-graphite">{k}</dt>
            <dd className="figures font-display text-head">{v}</dd>
          </div>
        ))}
        <div className="col-span-2 sm:col-span-1">
          <dt className="text-note text-graphite">Return</dt>
          <dd className="text-note">{card.ret}</dd>
        </div>
      </dl>
      <div className="grid gap-2">
        <MixBars card={card} />
        <ul className="grid gap-1">
          {card.mix.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>
      <div className="-mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[30rem] text-left text-note">
          <caption className="sr-only">Your holdings, valued on {card.as_of}</caption>
          <thead className="text-graphite">
            <tr>
              <th scope="col" className="py-2 pr-3 font-normal">Holding</th>
              <th scope="col" className="py-2 pr-3 text-right font-normal">Units</th>
              <th scope="col" className="py-2 pr-3 text-right font-normal">Worth now</th>
              <th scope="col" className="py-2 text-right font-normal">Gain or loss</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-rule">
            {card.rows.map((r) => (
              <tr key={r.name}>
                <th scope="row" className="py-2 pr-3 font-medium">{r.name}<span className="block font-normal text-graphite">{r.ret}</span></th>
                <td className="figures py-2 pr-3 text-right">{r.units}</td>
                <td className="figures py-2 pr-3 text-right">{r.value}</td>
                <td className="figures py-2 text-right"><span aria-hidden="true">{GLYPH[r.direction]} </span>{r.gain}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="grid gap-1 text-graphite">
        {card.history.map((line) => <li key={line} className="max-w-[65ch]">{line}</li>)}
      </ul>
      {label && <p className="text-graphite">{label}</p>}
      <p className="text-note text-graphite">Valued on {card.as_of}: {card.count} holdings.</p>
    </div>
  );
}
