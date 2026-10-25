"use client";

import type { Ref } from "react";
import { AlertCircle, Forward, LayoutPanelLeft, RotateCcw, Send } from "lucide-react";

import { AnswerCard } from "@/components/answer";
import { MessageView } from "@/components/message";
import { BOT_URL, isTelegramOnly, type Entry, type Outcome } from "@/lib/chat";

export const WORDS = {
  thinking: "Checking",
  unreachable: "Networth didn't answer just now. Check your connection and ask again.",
  missing: "This one isn't ready on the web yet. Ask it in your own words, or try it in the Telegram bot.",
  telegram: (name: string) => `/${name} works in the Telegram bot, where your chat lives.`,
  unknown: (name: string) => `There's no /${name}. Type / to see the commands that work here.`,
  opened: "The dashboard is open.",
};

function Thinking() {
  return (
    <div className="flex items-center gap-3 text-ink-3" data-state="thinking">
      <svg width="72" height="10" viewBox="0 0 72 10" aria-hidden="true">
        <path d="M2 6 Q 18 2, 36 5 T 70 4" pathLength={1} className="thinking-line" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
      </svg>
      <span className="text-sm">{WORDS.thinking}</span>
    </div>
  );
}

function Failed({ outcome, onRetry }: { outcome: Extract<Outcome, { kind: "failed" }>; onRetry: () => void }) {
  const { error, status } = outcome;
  const limited = error?.error === "rate_limited" || status === 429 || status === 404;
  return (
    <div role="alert" data-error={error?.error ?? (status === 404 ? "missing" : "unreachable")} className="grid gap-3 rounded-lg border border-line p-4">
      <div className="flex items-start gap-2.5">
        <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-3" />
        {error ? <MessageView message={error.message} /> : <p>{status === 404 ? WORDS.missing : WORDS.unreachable}</p>}
      </div>
      <div className="flex flex-wrap gap-2">
        {!limited && (
          <button type="button" className="btn" onClick={onRetry}>
            <RotateCcw aria-hidden="true" /> Ask again
          </button>
        )}
        {limited && (
          <a href={BOT_URL} className="btn" rel="noopener" target="_blank">
            <Send aria-hidden="true" /> Ask in the Telegram bot
          </a>
        )}
      </div>
    </div>
  );
}

function Question({ entry }: { entry: Entry }) {
  const { asked } = entry;
  if (asked.kind === "command") {
    return <p className="figure ml-auto w-fit rounded-xl bg-raised px-3.5 py-2 text-sm">/{asked.name}</p>;
  }
  return (
    <div className="ml-auto grid max-w-[85%] justify-items-end gap-1">
      {asked.forwarded && (
        <span className="flex items-center gap-1 text-xs text-ink-3"><Forward aria-hidden="true" className="size-3" /> Forwarded to me</span>
      )}
      <p className="whitespace-pre-line rounded-xl bg-raised px-3.5 py-2">
        {asked.chips.map((c) => (
          <span key={c.id} className="mark mr-1 inline-block">@{c.label}</span>
        ))}
        {asked.text}
      </p>
    </div>
  );
}

export interface ThreadProps {
  entries: Entry[];
  newestRef: Ref<HTMLLIElement>;
  onRetry: (entry: Entry) => void;
  onOpenCanvas: () => void;
}

export function Thread({ entries, newestRef, onRetry, onOpenCanvas }: ThreadProps) {
  const last = entries.at(-1);
  return (
    <ol aria-label="Conversation" className="grid gap-10">
      {entries.map((entry) => (
        <li key={entry.id} ref={entry === last ? newestRef : undefined} data-entry={entry.id} className="arrive grid scroll-mt-20 gap-4">
          <Question entry={entry} />
          {entry.outcome.kind === "waiting" && <Thinking />}
          {entry.outcome.kind === "answer" && <AnswerCard answer={entry.outcome.answer} />}
          {entry.outcome.kind === "failed" && <Failed outcome={entry.outcome} onRetry={() => onRetry(entry)} />}
          {entry.outcome.kind === "telegram" && !isTelegramOnly(entry.outcome.name) && (
            <p className="text-ink-2" data-state="unknown">{WORDS.unknown(entry.outcome.name)}</p>
          )}
          {entry.outcome.kind === "telegram" && isTelegramOnly(entry.outcome.name) && (
            <p className="text-ink-2" data-state="telegram">
              {WORDS.telegram(entry.outcome.name)}{" "}
              <a href={BOT_URL} rel="noopener" target="_blank" className="underline">Open the bot</a>
            </p>
          )}
          {entry.outcome.kind === "opened" && (
            <p className="flex items-center gap-2 text-ink-2">
              <LayoutPanelLeft aria-hidden="true" className="size-4" /> {WORDS.opened}{" "}
              <button type="button" className="underline" onClick={onOpenCanvas}>Show it again</button>
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
