import type { HistoryRow, HoldingsCard, NewsItem, PlanRange } from "@/lib/contract";
import { clampPct, type Fill, type Mark, type Spec, type Table } from "@/lib/sketch";

const PAD = 8;

/** One history row: a hachured bar to the hit rate and a taller tick at the normal rate. */
export function historySpec(row: HistoryRow, width: number): Spec {
  const usable = width - PAD * 2;
  const at = (pct: number) => PAD + (clampPct(pct) / 100) * usable;
  const y = 10;
  const h = 14;
  const tip = `${row.count} · ${row.rate} · normal ${row.normal}`;
  return {
    width,
    height: 34,
    decor: [{ shape: { kind: "line", x1: PAD, y1: y + h / 2, x2: width - PAD, y2: y + h / 2 }, tone: "soft", width: 1 }],
    marks: [
      {
        id: "hit",
        label: `${row.asset_name}: ${row.count}, ${row.rate}`,
        tip,
        box: { x: PAD, y, w: Math.max(at(row.bar.hit) - PAD, 6), h },
        strokes: [{ shape: { kind: "rect", x: PAD, y, w: at(row.bar.hit) - PAD, h }, tone: "pencil", fill: "hachure", gap: 3.5 }],
      },
      {
        id: "normal",
        label: `normal ${row.normal}`,
        tip: `normal ${row.normal}`,
        box: { x: at(row.bar.normal) - 4, y: 2, w: 8, h: 30 },
        strokes: [{ shape: { kind: "line", x1: at(row.bar.normal), y1: 2, x2: at(row.bar.normal), y2: 32 }, tone: "accent", width: 2 }],
      },
    ],
    labels: [],
  };
}

export function historyTable(rows: HistoryRow[]): Table {
  return {
    caption: "What history counted",
    head: ["Asset", "Count", "Rate", "Normal"],
    rows: rows.map((r) => [r.asset_name, r.count, r.rate, r.normal]),
  };
}

const RANGE_TOP = 18;
const RANGE_BOTTOM = 34;

/**
 * The plan range as a fan: from the start, each series opens out to its bad and good case, with
 * the middle case ticked and the money put in pencilled across. Heights are the server's own
 * percent-of-scale geometry.
 */
export function rangeSpec(r: PlanRange, width: number, height: number): Spec {
  const base = height - RANGE_BOTTOM;
  const span = base - RANGE_TOP;
  const yOf = (pct: number) => base - (clampPct(pct) / 100) * span;
  const originX = PAD + 4;
  const cols = r.bar.rows.length;
  const colW = Math.min(64, (width - originX) / (cols * 2.4));
  const colX = (i: number) => width - PAD - colW / 2 - (cols - 1 - i) * colW * 1.7;
  const marks: Mark[] = r.bar.rows.map((row, i) => {
    const cx = colX(i);
    const top = yOf(row.x + row.w);
    const bottom = yOf(row.x);
    const mid = yOf(row.median_x);
    const hatch: Fill = row.series === "before" ? "hachure" : "cross-hatch";
    return {
      id: row.series,
      label: `${row.name}: ${row.cases.map((c) => `${c.name} ${c.value}`).join(", ")}`,
      tip: row.cases.map((c) => `${c.name} ${c.value}`).join(" · "),
      box: { x: cx - colW / 2, y: top, w: colW, h: Math.max(bottom - top, 6) },
      strokes: [
        { shape: { kind: "polygon", points: [[originX, base], [cx - colW / 2, top], [cx - colW / 2, bottom]] }, tone: "soft", fill: hatch, gap: 7, width: 0.8 },
        { shape: { kind: "rect", x: cx - colW / 2, y: top, w: colW, h: Math.max(bottom - top, 2) }, tone: "pencil", fill: hatch, gap: 4 },
        { shape: { kind: "line", x1: cx - colW / 2 - 6, y1: mid, x2: cx + colW / 2 + 6, y2: mid }, tone: "accent", width: 2.2 },
      ],
    };
  });
  const investedY = yOf(r.bar.invested_x);
  return {
    width,
    height,
    decor: [
      { shape: { kind: "line", x1: originX, y1: base, x2: width - PAD, y2: base }, tone: "soft", width: 1 },
      { shape: { kind: "line", x1: originX, y1: investedY, x2: width - PAD, y2: investedY }, tone: "pencil", dashed: true, width: 1 },
      { shape: { kind: "circle", x: originX, y: base, d: 7 }, tone: "pencil", fill: "solid" },
    ],
    marks,
    labels: [
      { x: originX, y: base + 18, text: r.bar.zero_label, figure: true },
      { x: originX + 2, y: investedY - 6, text: `${r.bar.invested_name} ${r.invested}`, figure: true, tone: "ink" },
      ...r.bar.rows.map((row, i) => ({ x: colX(i), y: base + 18, text: row.name, anchor: "middle" as const })),
    ],
  };
}

export function rangeTable(r: PlanRange): Table {
  const names = r.bar.rows[0]?.cases.map((c) => c.name) ?? [];
  return {
    caption: `${r.plan}: ${r.monthly} a month for ${r.years} years, ${r.invested} put in`,
    head: ["", ...names],
    rows: r.bar.rows.map((row) => [row.name, ...row.cases.map((c) => c.value)]),
  };
}

/** Buckets are told apart by pencil texture, never by a colour that could read as a verdict. */
export const BUCKET_FILL: Record<string, { fill: Fill; angle: number }> = {
  safety: { fill: "hachure", angle: -41 },
  core: { fill: "cross-hatch", angle: 45 },
  growth: { fill: "dots", angle: 0 },
};
const OTHER_FILL = { fill: "zigzag" as Fill, angle: 30 };

const MIX_ROW = 30;

export function mixSpec(card: HoldingsCard, width: number): Spec {
  const usable = width - PAD * 2;
  const scale = (n: number) => (n / (card.bar.width || 100)) * usable;
  const marks = card.bar.rows.flatMap((row, r) =>
    row.segments.map((s) => {
      const texture = BUCKET_FILL[s.bucket] ?? OTHER_FILL;
      const x = PAD + scale(s.x);
      const w = Math.max(scale(s.w), 1);
      const y = r * (MIX_ROW + 18) + 16;
      return {
        id: `${r}-${s.bucket}`,
        label: `${row.name}: ${s.bucket} ${s.pct}`,
        tip: `${s.bucket} ${s.pct}`,
        box: { x, y, w, h: MIX_ROW - 8 },
        strokes: [{ shape: { kind: "rect" as const, x, y, w, h: MIX_ROW - 8 }, tone: "pencil" as const, fill: texture.fill, angle: texture.angle, gap: 4 }],
      };
    }),
  );
  return {
    width,
    height: mixHeight(card),
    decor: [],
    marks,
    labels: card.bar.rows.map((row, r) => ({ x: PAD, y: r * (MIX_ROW + 18) + 10, text: row.name })),
  };
}

export const mixHeight = (card: HoldingsCard): number => card.bar.rows.length * (MIX_ROW + 18) + 4;

export function mixTable(card: HoldingsCard): Table {
  const buckets = card.bar.rows[0]?.segments.map((s) => s.bucket) ?? [];
  return {
    caption: card.bar_title,
    head: ["", ...buckets],
    rows: card.bar.rows.map((row) => [row.name, ...buckets.map((b) => row.segments.find((s) => s.bucket === b)?.pct ?? "")]),
  };
}

/** The month's stories in the server's order along one pencil line, each dated where the server dated it. */
/** The server lists stories newest first; the timeline runs oldest to newest, left to right. */
export function newsSpec(newestFirst: NewsItem[], width: number): Spec {
  const items = [...newestFirst].reverse();
  const y = 22;
  const step = items.length > 1 ? (width - PAD * 6) / (items.length - 1) : 0;
  const xOf = (i: number) => (items.length > 1 ? PAD * 3 + i * step : width / 2);
  const roomy = items.length < 2 || step > 64;
  return {
    width,
    height: 52,
    decor: [{ shape: { kind: "line", x1: PAD, y1: y, x2: width - PAD, y2: y }, tone: "soft", width: 1 }],
    marks: items.map((item, i) => ({
      id: `${i}`,
      label: item.day ? `${item.day}: ${item.title}` : item.title,
      tip: item.title,
      box: { x: xOf(i) - 8, y: y - 8, w: 16, h: 16 },
      strokes: [{ shape: { kind: "circle", x: xOf(i), y, d: 11 }, tone: "pencil", fill: "solid" }],
    })),
    labels: items.flatMap((item, i) =>
      item.day && (roomy || i === 0 || i === items.length - 1)
        ? [{ x: xOf(i), y: y + 24, text: item.day, anchor: "middle" as const, figure: true }]
        : [],
    ),
  };
}

export function newsTable(items: NewsItem[]): Table {
  return {
    caption: "This month's confirmed stories",
    head: ["Story", "Day", "Reported by"],
    rows: items.map((i) => [i.title, i.day ?? "", i.publishers.join(", ")]),
  };
}
