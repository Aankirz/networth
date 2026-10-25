import { pencilEdges, pencilShape } from "@/lib/pencil";

type Stroke = { d: string; accent?: boolean };

const strokes = (paths: string[][], accent: number[] = []): Stroke[] =>
  paths.flatMap((pair, i) => pair.map((d) => ({ d, accent: accent.includes(i) })));

// Drawn once on the server: a paper plane for the bot, a page of news, a calendar with its day ticked.
const ICONS: Record<"plane" | "news" | "day", Stroke[]> = {
  plane: strokes([
    pencilShape([[6, 23], [42, 8], [31, 40], [22, 29]], 3),
    pencilEdges([[22, 29], [42, 8]], 4),
    pencilEdges([[22, 29], [21, 38], [27, 33]], 5),
  ]),
  news: strokes([
    pencilShape([[9, 9], [39, 9], [39, 39], [9, 39]], 6),
    pencilEdges([[15, 17], [33, 17]], 7),
    pencilEdges([[15, 24], [33, 24]], 8),
    pencilEdges([[15, 31], [26, 31]], 9),
  ], [1]),
  day: strokes([
    pencilShape([[8, 13], [40, 13], [40, 40], [8, 40]], 10),
    pencilEdges([[8, 21], [40, 21]], 11),
    pencilEdges([[16, 8], [16, 16]], 12),
    pencilEdges([[32, 8], [32, 16]], 13),
    pencilEdges([[17, 30], [22, 35], [31, 26]], 14),
  ], [4]),
};

/** A hand-drawn icon whose strokes draw in, one after another, when its step scrolls into view. */
export function StepIcon({ name }: { name: keyof typeof ICONS }) {
  return (
    <svg viewBox="0 0 48 48" className="step-icon size-14" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {ICONS[name].map((s, i) => (
        <path
          key={i}
          d={s.d}
          pathLength={1}
          className="ink"
          style={{ ["--i" as string]: i }}
          stroke={s.accent ? "var(--accent-stroke)" : "var(--pencil)"}
          strokeWidth={i % 2 ? 0.9 : 1.6}
          opacity={i % 2 ? 0.6 : 1}
        />
      ))}
    </svg>
  );
}
