// Hand-drawn strokes for the landing page's own drawings, worked out on the server so they cost no
// script. Seeded, so the same drawing comes out on every render and hydration never differs.

type Point = [number, number];

function random(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round = (n: number): number => Math.round(n * 10) / 10;

/** A smooth curve through the points (Catmull-Rom, as cubic Béziers). */
function curve(p: Point[]): string {
  let d = `M${round(p[0][0])} ${round(p[0][1])}`;
  for (let i = 0; i < p.length - 1; i++) {
    const [a, b, c, e] = [p[i - 1] ?? p[i], p[i], p[i + 1], p[i + 2] ?? p[i + 1]];
    const c1: Point = [b[0] + (c[0] - a[0]) / 6, b[1] + (c[1] - a[1]) / 6];
    const c2: Point = [c[0] - (e[0] - b[0]) / 6, c[1] - (e[1] - b[1]) / 6];
    d += ` C${round(c1[0])} ${round(c1[1])} ${round(c2[0])} ${round(c2[1])} ${round(c[0])} ${round(c[1])}`;
  }
  return d;
}

/**
 * A pencil line through the points with a little wobble, drawn twice like a quick hand going
 * over its own stroke. Returns one path per pass.
 */
export function pencil(points: Point[], seed: number, wobble = 1.2): string[] {
  const rand = random(seed);
  return [1, 0.7].map((shake) => curve(points.map(([x, y]): Point => [x + (rand() - 0.5) * wobble * shake * 2, y + (rand() - 0.5) * wobble * shake * 2])));
}

/** Straight pencil strokes through the points, each one bowed a touch, for the corners of icons. */
export function pencilEdges(points: Point[], seed: number, wobble = 0.8): string[] {
  const rand = random(seed);
  return [1, 0.6].map((shake) => {
    const p = points.map(([x, y]): Point => [x + (rand() - 0.5) * wobble * shake * 2, y + (rand() - 0.5) * wobble * shake * 2]);
    let d = `M${round(p[0][0])} ${round(p[0][1])}`;
    for (let i = 1; i < p.length; i++) {
      const [[x0, y0], [x1, y1]] = [p[i - 1], p[i]];
      const bow = (rand() - 0.5) * wobble * 1.6;
      const len = Math.hypot(x1 - x0, y1 - y0) || 1;
      const [mx, my] = [(x0 + x1) / 2 - ((y1 - y0) / len) * bow, (y0 + y1) / 2 + ((x1 - x0) / len) * bow];
      d += ` Q${round(mx)} ${round(my)} ${round(x1)} ${round(y1)}`;
    }
    return d;
  });
}

/** A closed pencil outline: it goes round once and runs a little past where it began. */
export function pencilShape(points: Point[], seed: number, wobble = 0.8): string[] {
  const [first, second] = points;
  const past: Point = [first[0] + (second[0] - first[0]) * 0.12, first[1] + (second[1] - first[1]) * 0.12];
  return pencilEdges([...points, first, past], seed, wobble);
}
