import type { HistoryCard, HistoryRow } from "@/lib/contract";
import { EmptyLedger } from "@/components/pencil";

/** A graphite fill to the hit rate and a pencil tick at the normal rate, in percent of the width. */
function CountBar({ bar }: { bar: HistoryRow["bar"] }) {
  return (
    <svg className="block h-5 w-full text-graphite" aria-hidden="true" preserveAspectRatio="none">
      <line x1="0" x2="100%" y1="10" y2="10" stroke="var(--rule)" strokeWidth="6" strokeLinecap="round" />
      <g filter="url(#pencil)">
        <line x1="0" x2={`${bar.hit}%`} y1="10" y2="10" stroke="currentColor" strokeWidth="6" />
        <line x1={`${bar.normal}%`} x2={`${bar.normal}%`} y1="1" y2="19" stroke="var(--ink)" strokeWidth="1.5" />
      </g>
    </svg>
  );
}

function Row({ row }: { row: HistoryRow }) {
  return (
    <li className="grid gap-2 py-4 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4">
        <h4 className="font-medium">{row.asset_name}</h4>
        <p className="figures text-note text-graphite">
          <span className="font-display text-head text-ink">{row.count}</span> · normal {row.normal}
        </p>
      </div>
      <CountBar bar={row.bar} />
      <p className="max-w-[65ch]">{row.sentence}</p>
      {row.why_url && (
        <a href={row.why_url} className="text-note" rel="noopener">
          The past cases, one by one
        </a>
      )}
    </li>
  );
}

export function HistoryRows({ card }: { card: HistoryCard }) {
  if (!card.rows.length) return card.note ? <EmptyLedger note={card.note} /> : null;
  return (
    <ul className="divide-y divide-rule" /* taste-skill-ignore: a passbook ledger's ruled rows, the design idea */>
      {card.rows.map((row) => (
        <Row key={`${row.type}-${row.asset}`} row={row} />
      ))}
    </ul>
  );
}
