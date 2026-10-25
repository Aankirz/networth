"use client";

import { useEffect, useRef } from "react";
import { History, Newspaper, Pin, PinOff, Target, TrendingUp, Wallet, X } from "lucide-react";

import { HistoryRows } from "@/components/cards/history";
import { HoldingsView } from "@/components/cards/holdings";
import { NewsList } from "@/components/cards/news";
import { RangeView } from "@/components/cards/range";
import { Footer } from "@/components/message";
import type { Dashboard } from "@/lib/contract";
import { withoutFooter } from "@/lib/words";

export type Section = "news" | "history" | "plan" | "range" | "holdings";

export const SECTIONS: { id: Section; title: string; icon: typeof Newspaper }[] = [
  { id: "news", title: "This month's news", icon: Newspaper },
  { id: "history", title: "What history counted", icon: History },
  { id: "plan", title: "Your plan", icon: Target },
  { id: "range", title: "What your plan could become", icon: TrendingUp },
  { id: "holdings", title: "What you hold", icon: Wallet },
];

function Block({ id, children }: { id: Section; children: React.ReactNode }) {
  const meta = SECTIONS.find((s) => s.id === id)!;
  const Icon = meta.icon;
  return (
    <section id={`canvas-${id}`} aria-labelledby={`canvas-${id}-title`} className="grid scroll-mt-4 gap-4">
      <h3 id={`canvas-${id}-title`} className="flex items-center gap-2 text-sm font-medium text-ink-2">
        <Icon aria-hidden="true" className="size-4" />
        {meta.title}
      </h3>
      {children}
    </section>
  );
}

export function PlanBlock({ board }: { board: Dashboard }) {
  const { profile } = board;
  return (
    <div className="grid gap-3">
      <p className="text-sm text-ink">{profile.plan ? `${profile.plan}.` : "No plan picked yet. Type /start in the bot to finish setting up."}</p>
      <dl className="flex flex-wrap gap-x-8 gap-y-2">
        <div>
          <dt className="text-xs text-ink-3">Each month</dt>
          <dd className="figure text-lg">{profile.money}</dd>
        </div>
        {profile.day && (
          <div>
            <dt className="text-xs text-ink-3">Investing day</dt>
            <dd className="figure text-lg">the {profile.day}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}

export interface CanvasProps {
  board: Dashboard;
  pinned: boolean;
  focus: Section | null;
  onPin: (pinned: boolean) => void;
  onClose: () => void;
}

/** The dashboard, opened from the chat: a pinned panel on a wide screen, a sheet everywhere else. */
export function Canvas({ board, pinned, focus, onPin, onClose }: CanvasProps) {
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!focus) return;
    const target = scroller.current?.querySelector<HTMLElement>(`#canvas-${focus}`);
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    target?.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
  }, [focus]);

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <h2 className="mr-auto text-sm font-medium">{board.sample ? "Sample dashboard" : "Your dashboard"}</h2>
        <button
          type="button"
          className="btn btn-ghost btn-icon max-xl:hidden"
          aria-pressed={pinned}
          aria-label={pinned ? "Unpin the dashboard" : "Pin the dashboard open"}
          onClick={() => onPin(!pinned)}
        >
          {pinned ? <PinOff aria-hidden="true" /> : <Pin aria-hidden="true" />}
        </button>
        <button type="button" className="btn btn-ghost btn-icon" aria-label="Close the dashboard" onClick={onClose}>
          <X aria-hidden="true" />
        </button>
      </header>
      <nav aria-label="Dashboard sections" className="flex gap-1 overflow-x-auto border-b border-line px-3 py-2">
        {SECTIONS.filter((s) => s.id !== "holdings" || board.holdings).map((s) => (
          <a key={s.id} href={`#canvas-${s.id}`} className="chip shrink-0 no-underline">
            {s.title}
          </a>
        ))}
      </nav>
      <div ref={scroller} className="grid flex-1 content-start gap-10 overflow-y-auto overscroll-contain px-4 py-6 sm:px-6">
        <Block id="news"><NewsList card={board.news} /></Block>
        <Block id="history"><HistoryRows card={board.history} /></Block>
        <Block id="plan"><PlanBlock board={board} /></Block>
        <Block id="range">
          <RangeView card={board.plan_range} label={withoutFooter(board.plan_range.range?.label, board.footer)} />
        </Block>
        {board.holdings && (
          <Block id="holdings">
            <HoldingsView card={board.holdings} label={withoutFooter(board.holdings.label, board.footer)} />
          </Block>
        )}
        <div className="grid gap-1 pb-4">
          <Footer text={board.footer} />
          {!board.sample && (
            <p className="text-xs text-ink-3">This page is private to you. Anyone with the link can see it, so don&apos;t share it.</p>
          )}
        </div>
      </div>
    </div>
  );
}
