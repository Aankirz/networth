import { ArrowDown, ArrowRight, ArrowUp, ArrowUpRight } from "lucide-react";

import { SourceChip } from "@/components/cards/source-chip";
import type { Driver, RatingCard, View } from "@/lib/ratings-contract";

// The rating card (Phase 13C): the view and its score, what pushed it, where each number came
// from, and how often ratings like it were right. A weak track record is shown as plainly as a
// strong one.

const TONE: Record<View, string> = {
  Strong: "var(--up)",
  Positive: "var(--up)",
  Neutral: "var(--ink-3)",
  Weak: "var(--down)",
  Avoid: "var(--down)",
};

const EFFECT = {
  up: { Icon: ArrowUp, color: "var(--up)", words: "pushed it up" },
  down: { Icon: ArrowDown, color: "var(--down)", words: "pulled it down" },
  flat: { Icon: ArrowRight, color: "var(--ink-3)", words: "no push either way" },
} as const;

const R = 26;
const ARC = 2 * Math.PI * R;

function Dial({ score, view }: { score: number; view: View }) {
  const shown = Math.max(0, Math.min(100, score));
  return (
    <svg viewBox="0 0 64 64" className="size-16 shrink-0 -rotate-90" role="img" aria-label={`Score ${shown} out of 100`}>
      <circle cx="32" cy="32" r={R} fill="none" stroke="var(--line)" strokeWidth="6" />
      <circle cx="32" cy="32" r={R} fill="none" stroke={TONE[view]} strokeWidth="6" strokeLinecap="round" strokeDasharray={`${(shown / 100) * ARC} ${ARC}`} />
      <text x="32" y="32" transform="rotate(90 32 32)" textAnchor="middle" dominantBaseline="central" className="fill-[var(--ink)] text-[17px] font-semibold tabular-nums">
        {shown}
      </text>
    </svg>
  );
}

function DriverRow({ driver }: { driver: Driver }) {
  const { Icon, color, words } = EFFECT[driver.effect];
  return (
    <li className="grid gap-1 border-t border-line py-3 first:border-t-0">
      <p className="flex items-center gap-2 text-sm font-medium text-ink">
        <Icon aria-hidden="true" className="size-4 shrink-0" style={{ color }} />
        {driver.label}
        <span className="sr-only">, {words}</span>
      </p>
      <p className="text-sm text-ink-2 tabular-nums">{driver.value}</p>
      <div><SourceChip source={driver.source} /></div>
    </li>
  );
}

export function RatingView({ card }: { card: RatingCard }) {
  return (
    <article data-card="rating" className="grid gap-5">
      <header className="flex items-center gap-4">
        <Dial score={card.score} view={card.view} />
        <div className="min-w-0">
          <p className="text-sm text-ink-3">{card.name}</p>
          <p className="text-2xl font-semibold tracking-[-0.02em]" style={{ color: TONE[card.view] }}>{card.view}</p>
          <p className="text-xs text-ink-3">Score out of 100 · {card.confidence} confidence</p>
        </div>
      </header>
      <p className="font-semibold text-ink">{card.outlook}</p>
      <section aria-label="What the score is built from">
        <ul className="grid">{card.drivers.map((d) => <DriverRow key={d.key} driver={d} />)}</ul>
        {card.missing.map((line) => (
          <p key={line} className="mt-1 text-sm text-ink-3">{line}</p>
        ))}
      </section>
      <section aria-label="Track record" className="grid gap-1.5">
        <p className="text-sm text-ink-2 tabular-nums">{card.track.edge}</p>
        <p
          data-insight
          className="justify-self-start rounded-full px-3 py-1 text-sm text-ink"
          style={{ background: `color-mix(in oklch, ${card.track.weak ? "var(--ink-3)" : "var(--up)"} 18%, transparent)` }}
        >
          {card.track.text}
        </p>
      </section>
      <a href={card.url} rel="noopener" target="_blank" className="inline-flex w-fit items-center gap-1 text-sm text-ink-2 hover:text-ink">
        Open the shareable page <ArrowUpRight aria-hidden="true" className="size-4" />
      </a>
    </article>
  );
}
