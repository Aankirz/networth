// The shape every pencil chart is drawn from. A builder turns one server card into a Spec for a
// given width; <Sketch> hands each Stroke to rough.js and draws the paths it returns. Builders
// only place what the server sent: every label and tip is a server string, every position comes
// from the card's own geometry fields.

export type Shape =
  | { kind: "line"; x1: number; y1: number; x2: number; y2: number }
  | { kind: "rect"; x: number; y: number; w: number; h: number }
  | { kind: "polygon"; points: [number, number][] }
  | { kind: "circle"; x: number; y: number; d: number };

export type Tone = "pencil" | "soft" | "accent";
export type Fill = "hachure" | "cross-hatch" | "dots" | "zigzag" | "solid";

export interface Stroke {
  shape: Shape;
  tone: Tone;
  fill?: Fill;
  angle?: number;
  gap?: number;
  dashed?: boolean;
  width?: number;
}

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** One thing a reader can point at: hover or focus shows `tip`, a screen reader hears `label`. */
export interface Mark {
  id: string;
  label: string;
  tip: string;
  box: Box;
  strokes: Stroke[];
}

export interface Label {
  x: number;
  y: number;
  text: string;
  anchor?: "start" | "middle" | "end";
  tone?: "ink" | "soft";
  figure?: boolean;
}

export interface Spec {
  width: number;
  height: number;
  decor: Stroke[];
  marks: Mark[];
  labels: Label[];
}

export interface Table {
  caption: string;
  head: string[];
  rows: string[][];
}

/** A stable seed from the chart's own words, so a chart never jitters between renders. */
export function seedOf(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return (h >>> 0) % 2 ** 31 || 1;
}

export const clampPct = (n: number): number => Math.min(100, Math.max(0, Number.isFinite(n) ? n : 0));
