import { Mark } from "@/components/mark";
import { pencil } from "@/lib/pencil";

const W = 640;
const H = 240;
const BASE = 214;
const MONTHS = 25;
const DIP = 15;

// A shape, not data: months of steady investing, one hard fall and the climb back. It carries no
// figure, so it says nothing the server didn't.
const LINE: [number, number][] = Array.from({ length: MONTHS }, (_, i) => {
  const x = 24 + (i * (W - 48)) / (MONTHS - 1);
  const trend = 168 - i * 4.2;
  const fall = 46 * Math.exp(-((i - DIP) ** 2) / 4.5);
  const ripple = Math.sin(i * 1.9) * 5;
  return [x, trend + fall + ripple];
});

const [lineA, lineB] = pencil(LINE, 7, 1.6);
const [base] = pencil([[16, BASE], [W / 2, BASE + 1], [W - 16, BASE - 1]], 11, 1);
const TICKS = LINE.filter((_, i) => i % 6 === 0).map(([x], i) => pencil([[x, BASE - 4], [x, BASE + 5]], 20 + i, 0.6)[0]);
const [dipX, dipY] = LINE[DIP];

/** The hero: a pencil line draws itself, then the brief's own line arrives beside the fall. */
export function HeroSketch() {
  return (
    <figure className="hero-sketch relative mx-auto w-full max-w-[760px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full overflow-visible" role="img" aria-label="A pencil line of monthly investing that falls hard for a few months and climbs back">
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          <path d={base} pathLength={1} className="hero-ink" stroke="var(--pencil-soft)" strokeWidth={1.2} />
          {TICKS.map((d, i) => (
            <path key={i} d={d} pathLength={1} className="hero-ink" stroke="var(--pencil-soft)" strokeWidth={1.1} />
          ))}
          <path d={lineA} pathLength={1} className="hero-ink hero-line" stroke="var(--pencil)" strokeWidth={2.2} />
          <path d={lineB} pathLength={1} className="hero-ink hero-line hero-line-2" stroke="var(--pencil)" strokeWidth={1} opacity={0.55} />
        </g>
        <circle cx={dipX} cy={dipY} r={5.5} className="hero-dot" fill="var(--accent-stroke)" />
        <circle cx={dipX} cy={dipY} r={12} className="hero-dot hero-halo" fill="none" stroke="var(--accent-stroke)" strokeWidth={1} />
      </svg>
      <figcaption className="hero-bubble mx-auto mt-5 w-fit max-w-[19rem] rounded-2xl rounded-br-md border border-line bg-raised px-4 py-3 text-left shadow-[0_12px_40px_-12px_var(--scrim)] sm:absolute sm:top-[4%] sm:right-[41%] sm:mt-0">
        <span className="mb-1 flex items-center gap-1.5 text-xs font-medium text-ink-2">
          <Mark className="size-3.5 text-[var(--accent-stroke)]" /> Networth
        </span>
        <span className="block text-[0.9375rem] leading-snug text-balance text-ink">Months like this are why you have a plan.</span>
      </figcaption>
    </figure>
  );
}
