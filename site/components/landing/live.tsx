import { cache } from "react";

import { PlanBlock } from "@/components/app/canvas";
import { HistoryRows } from "@/components/cards/history";
import { NewsList } from "@/components/cards/news";
import { RangeView } from "@/components/cards/range";
import { getDashboard, getTrackRecord } from "@/lib/api";
import type { Dashboard } from "@/lib/contract";
import { withoutFooter } from "@/lib/words";

// Every live piece on the landing page is the sample profile, read from the server once per
// request. When the server is asleep the piece says so instead of drawing anything of its own.

const demoBoard = cache(async (): Promise<Dashboard | null> => {
  const result = await getDashboard({ kind: "demo" });
  return result.ok ? result.data : null;
});

function Asleep() {
  return <p className="text-sm text-ink-3">The sample profile is waking up. It opens in the demo.</p>;
}

export async function LivePlan() {
  const board = await demoBoard();
  return board ? <PlanBlock board={board} /> : <Asleep />;
}

export async function LiveNews() {
  const board = await demoBoard();
  return board ? <NewsList card={board.news} /> : <Asleep />;
}

export async function LiveHistory() {
  const board = await demoBoard();
  if (!board) return <Asleep />;
  return <HistoryRows card={{ ...board.history, rows: board.history.rows.slice(0, 2) }} />;
}

export async function LiveRange() {
  const board = await demoBoard();
  if (!board) return <Asleep />;
  return <RangeView card={board.plan_range} label={withoutFooter(board.plan_range.range?.label, board.footer)} />;
}

/** Our own test, as the server reads it from the eval summary. Nothing shows if it can't be read. */
export async function LiveTrackRecord() {
  const result = await getTrackRecord();
  if (!result.ok) return <p className="text-sm text-ink-3">The test results are on the server, which is waking up. Try again in a minute.</p>;
  const { tested, stats } = result.data;
  return (
    <div className="grid gap-6">
      {tested && (
        <ul className="grid gap-3">
          {tested.map((line) => (
            <li key={line} className="max-w-[65ch] text-ink">{line}</li>
          ))}
        </ul>
      )}
      {stats.length > 0 && (
        <dl className="flex flex-wrap gap-x-10 gap-y-4">
          {stats.map((s) => (
            <div key={s.label}>
              <dt className="text-xs text-ink-3">{s.label}</dt>
              <dd className="figure text-xl">{s.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
