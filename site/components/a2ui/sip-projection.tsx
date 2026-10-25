"use client";

import { useState } from "react";

import { pencil } from "@/lib/pencil";
import { crossover, project, type SipInput } from "@/lib/a2ui/sip";
import { money as fullMoney, moneyShort } from "@/lib/money";

const W = 600;
const H = 220;
const PAD = { l: 8, r: 8, t: 12, b: 8 };

/** Headline number, its pill, the balance against a dashed "You put in" line, and one insight. */
export function SipProjection({ currency, ...input }: SipInput & { currency: string }) {
  const money = (n: number) => fullMoney(n, currency);
  const short = (n: number) => moneyShort(n, currency);
  const rows = project(input);
  const last = rows[rows.length - 1];
  const top = Math.max(last.balance, 1);
  const x = (year: number) => PAD.l + (year / Math.max(input.years, 1)) * (W - PAD.l - PAD.r);
  const y = (v: number) => H - PAD.b - (v / top) * (H - PAD.t - PAD.b);
  const balance = rows.map((r): [number, number] => [x(r.year), y(r.balance)]);
  const putIn = rows.map((r) => `${x(r.year)},${y(r.invested)}`).join(" ");
  const area = `M${x(0)} ${y(0)} ${balance.map(([a, b]) => `L${a} ${b}`).join(" ")} L${x(input.years)} ${y(0)} Z`;
  const [at, setAt] = useState<number | null>(null);
  const hover = at === null ? null : rows[at];
  const cross = crossover(rows);
  const growth = last.balance - last.invested;

  return (
    <figure className="grid gap-4" data-a2ui="sip-projection">
      <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
        <p className="text-[clamp(2rem,1.4rem+3vw,3rem)] tabular-nums leading-none font-semibold tracking-[-0.03em] text-ink" aria-live="polite">
          {short(last.balance)}{" "}
          <span className="ml-2 text-base font-normal tracking-normal text-ink-2">in {input.years} years</span>
        </p>
        <span className="rounded-full border border-line px-3 py-1 text-sm tabular-nums text-ink-2">
          ≈ {short(last.invested)} put in · {short(growth)} growth
        </span>
      </div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-auto w-full touch-none"
          role="img"
          aria-label={`Balance grows to ${money(last.balance)} after ${input.years} years, against ${money(last.invested)} put in.`}
          onPointerMove={(e) => {
            const box = e.currentTarget.getBoundingClientRect();
            const ratio = ((e.clientX - box.left) / box.width) * W;
            setAt(Math.min(input.years, Math.max(0, Math.round(((ratio - PAD.l) / (W - PAD.l - PAD.r)) * input.years))));
          }}
          onPointerLeave={() => setAt(null)}
        >
          <path d={area} fill="var(--accent)" opacity="0.14" />
          <polyline points={putIn} fill="none" stroke="var(--ink-3)" strokeWidth="1.5" strokeDasharray="5 5" />
          {pencil(balance, 7).map((d, i) => (
            <path key={i} d={d} fill="none" stroke="var(--pencil)" strokeWidth={i ? 1 : 2} strokeLinecap="round" opacity={i ? 0.5 : 1} />
          ))}
          {hover && <circle cx={x(hover.year)} cy={y(hover.balance)} r="5" fill="var(--accent)" stroke="var(--ink)" />}
        </svg>
        <div className="flex justify-between text-xs text-ink-3">
          <span>Today</span>
          <span>Year {input.years}</span>
        </div>
        <p className="mt-2 min-h-5 text-sm tabular-nums text-ink-2">
          {hover ? (
            `Year ${hover.year}: ${money(hover.balance)}, of which you put in ${money(hover.invested)}`
          ) : (
            <>
              <span className="mr-1 inline-block h-0.5 w-4 align-middle bg-[var(--pencil)]" aria-hidden="true" />Balance
              <span className="mr-1 ml-4 inline-block w-4 border-t-[1.5px] border-dashed border-[var(--ink-3)] align-middle" aria-hidden="true" />You put in
            </>
          )}
        </p>
      </div>
      <p className={`justify-self-start rounded-full px-3 py-1 text-sm ${cross ? "bg-[color-mix(in_oklch,var(--up)_18%,transparent)] text-ink" : "bg-hover text-ink-2"}`} data-insight>
        {cross ? `From year ${cross}, growth is bigger than everything you put in.` : "Growth stays below what you put in; more years change that most."}
      </p>
    </figure>
  );
}
