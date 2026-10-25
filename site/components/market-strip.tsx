import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";

import { SourceChip } from "@/components/cards/source-chip";
import { getMarket, type Scope } from "@/lib/api";
import type { Direction } from "@/lib/contract";
import type { MarketTile } from "@/lib/market";
import { pencil } from "@/lib/pencil";

// The index tiles at the top of the chat: the server's level and change, in green or red, over a
// pencil line of the last few weeks. Drawn on the server, so it costs the page no script.

const SPARK_W = 96;
const SPARK_H = 28;
const SPARK_PAD = 3;
const PLACEHOLDER_TILES = 4;

const TONE: Record<Direction, { color: string; Icon: typeof ArrowUp }> = {
  up: { color: "var(--up)", Icon: ArrowUp },
  down: { color: "var(--down)", Icon: ArrowDown },
  flat: { color: "var(--ink-3)", Icon: ArrowRight },
};

const ROW = "flex snap-x gap-2 overflow-x-auto [scrollbar-width:none] sm:grid sm:grid-cols-4 sm:overflow-visible";
const TILE = "grid min-w-[9.5rem] shrink-0 snap-start gap-1 rounded-xl border border-line bg-raised px-3 py-2.5 sm:min-w-0";

function seedOf(text: string): number {
  return [...text].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
}

function Spark({ tile }: { tile: MarketTile }) {
  const values = tile.series.points.map((p) => p.v);
  if (values.length < 2) return <span className="block" style={{ height: SPARK_H }} />;
  const low = Math.min(...values);
  const span = Math.max(...values) - low || 1;
  const points = values.map((v, i): [number, number] => [
    (i / (values.length - 1)) * SPARK_W,
    SPARK_PAD + (1 - (v - low) / span) * (SPARK_H - 2 * SPARK_PAD),
  ]);
  return (
    <svg viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} className="h-7 w-full" preserveAspectRatio="none" aria-hidden="true" data-spark="">
      {pencil(points, seedOf(tile.symbol), 0.6).map((d, i) => (
        <path key={i} d={d} fill="none" stroke={TONE[tile.direction].color} strokeWidth={i === 0 ? 1.4 : 0.8} strokeLinecap="round" vectorEffect="non-scaling-stroke" opacity={i === 0 ? 1 : 0.5} />
      ))}
    </svg>
  );
}

function Tile({ tile }: { tile: MarketTile }) {
  const { color, Icon } = TONE[tile.direction];
  return (
    <li className={TILE} data-tile={tile.symbol}>
      <p className="truncate text-xs text-ink-2">{tile.name}</p>
      <p className="figure text-base font-semibold text-ink tabular-nums">{tile.level}</p>
      <p className="flex items-center gap-1 text-xs tabular-nums" style={{ color }}>
        <Icon aria-hidden="true" className="size-3 shrink-0" />
        {tile.change} ({tile.change_pct})
      </p>
      <Spark tile={tile} />
    </li>
  );
}

export function MarketStripLoading() {
  return (
    <div data-strip="loading" aria-busy="true">
      <p className="sr-only">Loading index prices</p>
      <ul className={ROW} aria-hidden="true">
        {Array.from({ length: PLACEHOLDER_TILES }, (_, i) => (
          <li key={i} className={TILE}>
            <span className="h-3 w-16 animate-pulse rounded bg-[var(--bubble)]" />
            <span className="h-5 w-24 animate-pulse rounded bg-[var(--bubble)]" />
            <span className="h-3 w-20 animate-pulse rounded bg-[var(--bubble)]" />
            <span className="h-7" />
          </li>
        ))}
      </ul>
    </div>
  );
}

export async function MarketStrip({ scope }: { scope: Scope }) {
  const result = await getMarket(scope);
  if (!result.ok) {
    return <p data-strip="missing" className="text-xs text-ink-3">Index prices aren&apos;t available right now.</p>;
  }
  const { tiles, source } = result.data;
  return (
    <section data-strip="ready" aria-label="Markets" className="grid gap-1.5">
      <ul className={ROW}>
        {tiles.map((t) => <Tile key={t.symbol} tile={t} />)}
      </ul>
      <div className="justify-self-end"><SourceChip source={source} /></div>
    </section>
  );
}
