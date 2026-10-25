"use client";

import { Sketch } from "@/components/sketch";
import { BUCKET_FILL, mixHeight, mixSpec, mixTable } from "@/lib/charts";
import type { HoldingsCard } from "@/lib/contract";

const GLYPH = { up: "▲", down: "▼", flat: "–" } as const;

/** A legend key in the same pencil texture as the bars. */
function Swatch({ bucket }: { bucket: string }) {
  const fill = BUCKET_FILL[bucket]?.fill;
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" className="text-pencil" stroke="currentColor" fill="none">
      <rect x="1" y="1" width="12" height="12" rx="1.5" strokeWidth="1.2" />
      {fill === "dots" ? (
        <g fill="currentColor" stroke="none"><circle cx="5" cy="5" r="1" /><circle cx="9" cy="9" r="1" /><circle cx="9" cy="5" r="1" /><circle cx="5" cy="9" r="1" /></g>
      ) : (
        <path d={fill === "cross-hatch" ? "M3 11 11 3M3 3l8 8" : "M3 8 8 3M5 11l6-6"} strokeWidth="1" />
      )}
    </svg>
  );
}

export function HoldingsView({ card, label }: { card: HoldingsCard; label?: string | null }) {
  const buckets = card.bar.rows[0]?.segments.map((s) => s.bucket) ?? [];
  return (
    <div className="grid gap-5">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {[["Put in", card.invested], ["Worth now", card.value], ["Gain or loss", card.gain], ["Return", card.ret]].map(([k, v]) => (
          <div key={k} className="min-w-0">
            <dt className="text-xs text-ink-3">{k}</dt>
            <Total value={v} />
          </div>
        ))}
      </dl>
      <div className="grid gap-2">
        <p className="text-xs text-ink-3">{card.bar_title}</p>
        <Sketch title={card.bar_title} height={mixHeight(card)} build={(w) => mixSpec(card, w)} table={mixTable(card)} />
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2" aria-hidden="true">
          {buckets.map((b) => (
            <li key={b} className="flex items-center gap-1.5"><Swatch bucket={b} />{b}</li>
          ))}
        </ul>
        <ul className="grid gap-1 text-sm text-ink-2">
          {card.mix.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </div>
      <details className="text-sm">
        <summary className="w-fit cursor-pointer text-ink-2 hover:text-ink">Every holding</summary>
        <div className="-mx-1 mt-2 overflow-x-auto px-1">
          <table className="w-full min-w-[28rem] text-left text-sm">
            <caption className="sr-only">Your holdings, valued on {card.as_of}</caption>
            <thead className="text-xs text-ink-3">
              <tr>
                <th scope="col" className="py-1.5 pr-3 font-normal">Holding</th>
                <th scope="col" className="py-1.5 pr-3 text-right font-normal">Units</th>
                <th scope="col" className="py-1.5 pr-3 text-right font-normal">Worth now</th>
                <th scope="col" className="py-1.5 text-right font-normal">Gain or loss</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {card.rows.map((r) => (
                <tr key={r.name}>
                  <th scope="row" className="py-2 pr-3 font-medium">{r.name}<span className="block text-xs font-normal text-ink-3">{r.ret}</span></th>
                  <td className="figure py-2 pr-3 text-right">{r.units}</td>
                  <td className="figure py-2 pr-3 text-right">{r.value}</td>
                  <td className="figure py-2 text-right"><span aria-hidden="true">{GLYPH[r.direction]} </span>{r.gain}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <ul className="grid gap-1 text-sm text-ink-2">
        {card.history.map((line) => <li key={line} className="max-w-[65ch]">{line}</li>)}
      </ul>
      {label && <p className="text-sm text-ink-3">{label}</p>}
      <p className="text-xs text-ink-3">Valued on {card.as_of}: {card.count} holdings.</p>
    </div>
  );
}

/** The figure in mono; any words the server adds after it stay in the text face, smaller. */
function Total({ value }: { value: string }) {
  const [figure, ...words] = value.split(" ");
  return (
    <dd className="grid gap-0.5">
      <span className="figure text-sm">{figure}</span>
      {words.length > 0 && <span className="text-xs text-ink-3">{words.join(" ")}</span>}
    </dd>
  );
}
