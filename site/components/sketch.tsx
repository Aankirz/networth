"use client";

import { useEffect, useId, useRef, useState } from "react";

import { seedOf, type Mark, type Spec, type Stroke, type Table } from "@/lib/sketch";

type Generator = {
  line: (x1: number, y1: number, x2: number, y2: number, o: object) => unknown;
  rectangle: (x: number, y: number, w: number, h: number, o: object) => unknown;
  polygon: (points: [number, number][], o: object) => unknown;
  circle: (x: number, y: number, d: number, o: object) => unknown;
  toPaths: (drawable: unknown) => { d: string; stroke: string; strokeWidth: number; fill?: string }[];
};

const TONE = { pencil: "var(--pencil)", soft: "var(--pencil-soft)", accent: "var(--accent-stroke)" } as const;

interface Drawn {
  d: string;
  stroke: string;
  width: number;
  fill: string;
  dashed: boolean;
}

/** rough.js is fetched the first time any chart scrolls into view, and never on a page without one. */
let roughGenerator: Promise<() => Generator> | null = null;
function loadRough(): Promise<() => Generator> {
  roughGenerator ??= import("roughjs").then((m) => () => m.default.generator() as unknown as Generator);
  return roughGenerator;
}

function draw(gen: Generator, stroke: Stroke, seed: number): Drawn[] {
  const color = TONE[stroke.tone];
  const options = {
    seed,
    roughness: 1.1,
    bowing: 0.8,
    stroke: color,
    strokeWidth: stroke.width ?? 1.3,
    ...(stroke.fill && {
      fill: color,
      fillStyle: stroke.fill,
      hachureAngle: stroke.angle ?? -41,
      hachureGap: stroke.gap ?? 4,
      fillWeight: 0.9,
    }),
  };
  const s = stroke.shape;
  const drawable =
    s.kind === "line" ? gen.line(s.x1, s.y1, s.x2, s.y2, options)
    : s.kind === "rect" ? gen.rectangle(s.x, s.y, Math.max(s.w, 0.5), s.h, options)
    : s.kind === "polygon" ? gen.polygon(s.points, options)
    : gen.circle(s.x, s.y, s.d, options);
  return gen.toPaths(drawable).map((p) => ({
    d: p.d,
    stroke: p.stroke === "none" ? "none" : p.stroke,
    width: p.strokeWidth,
    fill: p.fill && p.fill !== "none" ? p.fill : "none",
    dashed: !!stroke.dashed,
  }));
}

function Paths({ paths, from }: { paths: Drawn[]; from: number }) {
  return paths.map((p, i) => (
    <path
      key={i}
      d={p.d}
      stroke={p.stroke}
      strokeWidth={p.width}
      fill={p.fill}
      strokeDasharray={p.dashed ? "6 5" : undefined}
      strokeLinecap="round"
      pathLength={p.dashed ? undefined : 1}
      data-draw={p.dashed ? undefined : ""}
      style={{ "--i": from + i } as React.CSSProperties}
    />
  ));
}

function HiddenTable({ table, id }: { table: Table; id: string }) {
  return (
    // sr-only cannot shrink a table, so a wrapper carries it.
    <div className="sr-only">
      <table id={id}>
        <caption>{table.caption}</caption>
        <thead>
          <tr>{table.head.map((h) => <th key={h} scope="col">{h}</th>)}</tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, c) => (c === 0 ? <th key={c} scope="row">{cell}</th> : <td key={c}>{cell}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface SketchProps {
  title: string;
  height: number;
  build: (width: number) => Spec;
  table: Table;
  className?: string;
}

/**
 * One hand-drawn chart in a fixed-height box, so nothing shifts when the strokes arrive. The marks
 * are focusable; hover or focus shows the server's exact figure. The same numbers sit in a visually
 * hidden table for screen readers.
 */
export function Sketch({ title, height, build, table, className }: SketchProps) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [gen, setGen] = useState<Generator | null>(null);
  const [drawn, setDrawn] = useState(false);
  const [active, setActive] = useState<Mark | null>(null);
  const tableId = useId();

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const resize = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    resize.observe(el);
    const seen = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        seen.disconnect();
        loadRough().then((make) => {
          setGen(make());
          requestAnimationFrame(() => requestAnimationFrame(() => setDrawn(true)));
        });
      },
      { rootMargin: "120px" },
    );
    seen.observe(el);
    return () => {
      resize.disconnect();
      seen.disconnect();
    };
  }, []);

  const spec = width > 0 ? build(width) : null;
  const seed = seedOf(title);
  // Each group's draw-in stagger starts where the previous group's paths ended.
  const groups = gen && spec ? [spec.decor, ...spec.marks.map((m) => m.strokes)].map((strokes) => strokes.flatMap((s, i) => draw(gen, s, seed + i))) : [];
  const starts = groups.map((_, g) => groups.slice(0, g).reduce((n, out) => n + out.length, 0));
  const paths = (g: number) => (groups[g] ? <Paths paths={groups[g]} from={starts[g]} /> : null);

  return (
    <figure className={`relative m-0 ${className ?? ""}`}>
      <div ref={box} className="relative w-full" style={{ height }}>
        {spec && (
          <svg
            width={spec.width}
            height={spec.height}
            viewBox={`0 0 ${spec.width} ${spec.height}`}
            className={`sketch block overflow-visible ${drawn ? "is-drawn" : ""}`}
            role="group"
            aria-label={title}
            aria-describedby={tableId}
          >
            <g aria-hidden="true">{paths(0)}</g>
            {spec.marks.map((mark, m) => (
              <g
                key={mark.id}
                className="mark-hit"
                role="img"
                tabIndex={0}
                aria-label={mark.label}
                onPointerEnter={() => setActive(mark)}
                onPointerLeave={() => setActive((m) => (m?.id === mark.id ? null : m))}
                onFocus={() => setActive(mark)}
                onBlur={() => setActive((m) => (m?.id === mark.id ? null : m))}
              >
                <rect data-focus x={mark.box.x - 3} y={mark.box.y - 3} width={mark.box.w + 6} height={mark.box.h + 6} rx="4" fill="transparent" stroke="transparent" strokeWidth="1.5" />
                {paths(m + 1)}
              </g>
            ))}
            <g aria-hidden="true">
              {spec.labels.map((l, i) => (
                <text
                  key={i}
                  x={l.x}
                  y={l.y}
                  textAnchor={l.anchor ?? "start"}
                  // A halo in the page colour keeps a label readable where it crosses hatching.
                  stroke="var(--halo, var(--bg))"
                  strokeWidth={6}
                  strokeLinejoin="round"
                  paintOrder="stroke"
                  className={`${l.figure ? "figure" : ""} ${l.tone === "ink" ? "fill-ink" : "fill-ink-3"} text-[12px]`}
                >
                  {l.text}
                </text>
              ))}
            </g>
          </svg>
        )}
        {active && spec && (
          <div
            role="presentation"
            data-tip
            className="figure pointer-events-none absolute z-10 max-w-[16rem] -translate-x-1/2 -translate-y-full rounded-sm border border-line bg-raised px-2 py-1 text-xs text-ink shadow-lg"
            style={{
              left: Math.min(Math.max(active.box.x + active.box.w / 2, 64), spec.width - 64),
              top: Math.max(active.box.y - 8, 0),
            }}
          >
            {active.tip}
          </div>
        )}
      </div>
      <HiddenTable table={table} id={tableId} />
    </figure>
  );
}
