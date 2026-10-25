import type { ReactNode } from "react";

import { PlanBlock } from "@/components/app/canvas";
import { HistoryRows } from "@/components/cards/history";
import { NewsList } from "@/components/cards/news";
import { InView } from "@/components/landing/in-view";
import { demoBoard } from "@/components/landing/live";
import { Playback } from "@/components/landing/playback";
import { Mark } from "@/components/mark";
import type { Dashboard } from "@/lib/contract";

// Each mock is the real product's own words: the chat is the phase 9 eval's LIC thread, the
// brief is the server's brief lines filled from the sample profile, the email is a real answer.

type Turn = { bot?: boolean; text: ReactNode; wait?: number };

const IPO_THREAD: Turn[] = [
  { text: "Should I apply for the upcoming LIC IPO?" },
  {
    bot: true,
    wait: 2800,
    text: "Whether to put money in is your call, so I won't say yes or no. Here is what it is and how it works. An IPO is when a company offers its shares to the public for the first time, so it can be listed on the stock exchange.",
  },
  { text: "what should I read first?" },
  {
    bot: true,
    wait: 2400,
    text: "The RHP comes first. It covers LIC's business, financial history, debt, risks, and whether the money raised goes to LIC or existing owners.",
  },
  { text: "explain that in Hinglish" },
  {
    bot: true,
    text: (
      <>
        RHP sabse pehle dekhne wala document hai. Isme LIC ka business, finances, owners, paisa kahan use hoga, aur risks likhe hote hain.
        <span className="mt-2 block text-xs text-ink-3">Research hai, advice nahin.</span>
      </>
    ),
  },
];

function Bubble({ turn }: { turn: Turn }) {
  return (
    <li
      data-at=""
      data-bot={turn.bot ? "" : undefined}
      data-wait={turn.wait}
      className={`max-w-[90%] sm:max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[0.9375rem] leading-snug ${
        turn.bot ? "self-start rounded-bl-md border border-line bg-raised text-ink" : "self-end rounded-br-md bg-[var(--bubble)] text-ink"
      }`}
    >
      {turn.text}
    </li>
  );
}

function BotHeader({ title, sub }: { title: string; sub: string }) {
  return (
    <header className="flex items-center gap-3 border-b border-line px-4 py-3">
      <span className="grid size-9 place-items-center rounded-full bg-[var(--accent)] text-[var(--accent-ink)]">
        <Mark className="size-5" />
      </span>
      <span className="grid text-left leading-tight">
        <span className="text-sm font-semibold text-ink">{title}</span>
        <span className="text-xs text-ink-3">
          <span className="mock-idle">{sub}</span>
          <span className="mock-typing">typing…</span>
        </span>
      </span>
    </header>
  );
}

export function ChatMock() {
  return (
    <Playback label="A Telegram chat with the Networth bot about the LIC IPO" className="mock mx-auto w-full max-w-[560px] overflow-hidden rounded-[22px] border border-line bg-bg text-left">
      <BotHeader title="Networth" sub="bot" />
      <ol className="flex flex-col gap-2.5 bg-[var(--chat)] px-3 py-4 sm:px-4">
        {IPO_THREAD.map((turn, i) => (
          <Bubble key={i} turn={turn} />
        ))}
      </ol>
    </Playback>
  );
}

function briefLines(board: Dashboard): string[] {
  const r = board.plan_range.range;
  const story = board.news.items[0];
  const plan = board.profile.plan?.split(".")[0];
  return [
    story && `This month's news: ${story.title}${story.day ? ` on ${story.day}` : ""}.`,
    r && `Months like this are why you have a plan. Yours is built to sit through a fall of up to ${r.fall_limit}.`,
    r && `In replays of past markets, a fall that big came in ${r.hit_limit} of paths. Bad case ${r.nominal.p10}, middle ${r.nominal.median}.`,
    plan && `Your plan: ${plan}, the one you chose.`,
  ].filter((line): line is string => Boolean(line));
}

const BRIEF_BUTTONS = ["Got it", "My range", "Why these counts?"];

export async function BriefMock() {
  const board = await demoBoard();
  if (!board) return <p className="text-sm text-ink-3">The sample profile is waking up. Its brief opens in the demo.</p>;
  const counted = board.history.rows.slice(0, 2);
  return (
    <Playback label="The monthly brief for the sample profile" className="mock mx-auto w-full max-w-[560px] overflow-hidden rounded-[22px] border border-line bg-bg text-left">
      <BotHeader title="Networth" sub="your brief, on the 1st" />
      <div className="bg-[var(--chat)] px-3 py-4 sm:px-4">
        <article className="grid gap-2.5 rounded-2xl rounded-bl-md border border-line bg-raised px-4 py-3.5 text-[0.9375rem] leading-snug">
          <p data-at="" data-bot="" className="font-semibold text-ink">Morning. It&apos;s your investing day, and {board.profile.money} is ready.</p>
          {briefLines(board).map((line) => (
            <p key={line} data-at="" data-wait={1100} className="text-ink">{line}</p>
          ))}
          {counted.length > 0 && (
            <div data-at="" data-wait={2400} className="grid gap-1.5 border-t border-line pt-2.5">
              <p className="text-sm text-ink-2">What history counted:</p>
              {counted.map((row) => (
                <p key={row.asset + row.type} className="text-sm text-ink">{row.sentence}</p>
              ))}
            </div>
          )}
          <p data-at="" className="text-xs text-ink-3">{board.footer}</p>
        </article>
        <ul data-at="" className="mt-2 grid grid-cols-3 gap-1.5">
          {BRIEF_BUTTONS.map((b) => (
            <li key={b} className="truncate rounded-lg bg-[var(--bubble)] px-2 py-2 text-center text-xs font-medium text-ink">{b}</li>
          ))}
        </ul>
      </div>
    </Playback>
  );
}

export function EmailMock() {
  return (
    <Playback label="An email question and Networth's reply" className="mock mx-auto w-full max-w-[600px] overflow-hidden rounded-[18px] border border-line bg-raised text-left">
      <header className="border-b border-line px-5 py-4">
        <p className="text-base font-semibold text-ink">Re: What is the repo rate?</p>
        <p className="text-xs text-ink-3">Inbox</p>
      </header>
      <ol className="grid">
        <li data-at="" className="grid gap-1 border-b border-line px-5 py-4">
          <p className="text-sm font-medium text-ink">You</p>
          <p className="text-[0.9375rem] text-ink-2">What is the repo rate?</p>
        </li>
        <li data-at="" data-bot="" className="grid gap-2 px-5 py-4">
          <p className="flex items-center gap-2 text-sm font-medium text-ink">
            <Mark className="size-4 text-[var(--accent-stroke)]" /> Networth
          </p>
          <p className="text-[0.9375rem] leading-relaxed text-ink">
            The repo rate is the rate at which the RBI lends to banks, so changes can affect loan and deposit rates.
          </p>
          <p className="text-xs text-ink-3">Research, not advice.</p>
        </li>
      </ol>
      <p className="mock-typing-line px-5 pb-4 text-xs text-ink-3">Networth is writing…</p>
    </Playback>
  );
}

export async function DashboardMock() {
  const board = await demoBoard();
  if (!board) return <p className="text-sm text-ink-3">The sample profile is waking up. Its page opens in the demo.</p>;
  return (
    <div className="mock mx-auto w-full max-w-[880px] overflow-hidden rounded-[20px] border border-line bg-bg text-left">
      <header className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm">
        <Mark className="size-4" />
        <span className="font-medium text-ink">Dashboard</span>
        <span className="text-ink-3">· sample profile</span>
      </header>
      <InView className="grid gap-px bg-line md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <section aria-label="Your plan" className="rise grid content-start gap-4 bg-bg p-5 sm:p-6" style={{ ["--i" as string]: 0 }}>
          <h3 className="text-sm font-medium text-ink-2">Your plan</h3>
          <PlanBlock board={board} />
        </section>
        <section aria-label="The news" className="rise grid content-start gap-4 bg-bg p-5 sm:p-6" style={{ ["--i" as string]: 1 }}>
          <h3 className="text-sm font-medium text-ink-2">The news</h3>
          <NewsList card={board.news} />
        </section>
        <section aria-label="What history counted" className="rise grid content-start gap-4 bg-bg p-5 sm:p-6 md:col-span-2" style={{ ["--i" as string]: 2 }}>
          <h3 className="text-sm font-medium text-ink-2">What history counted</h3>
          <HistoryRows card={{ ...board.history, rows: board.history.rows.slice(0, 2) }} />
        </section>
      </InView>
    </div>
  );
}
