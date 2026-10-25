"use client";

import { useState } from "react";
import { Check, ChevronDown, Copy, History, Landmark, Newspaper, TrendingUp, Wallet } from "lucide-react";

import { HistoryRows } from "@/components/cards/history";
import { HoldingsView } from "@/components/cards/holdings";
import { NewsList } from "@/components/cards/news";
import { RangeView } from "@/components/cards/range";
import { MessageView } from "@/components/message";
import type { Answer } from "@/lib/chat";
import type { Card } from "@/lib/contract";

const COPY_RESET_MS = 1600;

/** One renderer per card type the server sends. A text card has no body: the message is the answer. */
const CARDS: { [K in Card["type"]]: { title: string; icon: typeof Newspaper; render: (card: Extract<Card, { type: K }>) => React.ReactNode } } = {
  news: { title: "The news", icon: Newspaper, render: (card) => <NewsList card={card} /> },
  history: { title: "What history counted", icon: History, render: (card) => <HistoryRows card={card} /> },
  plan_range: { title: "What your plan could become", icon: TrendingUp, render: (card) => <RangeView card={card} /> },
  holdings: { title: "What you hold", icon: Wallet, render: (card) => <HoldingsView card={card} /> },
  text: { title: "", icon: Landmark, render: () => null },
  // ponytail: the 13A market cards answer in words until their own renderers land
  price: { title: "", icon: Landmark, render: () => null },
  price_history: { title: "", icon: Landmark, render: () => null },
  position: { title: "", icon: Landmark, render: () => null },
  compare: { title: "", icon: Landmark, render: () => null },
  market_today: { title: "", icon: Landmark, render: () => null },
};

function cardOf(card: Card) {
  const entry = CARDS[card.type] as { title: string; icon: typeof Newspaper; render: (c: Card) => React.ReactNode };
  return { ...entry, body: entry.render(card) };
}

export function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="btn btn-ghost h-8 min-h-8 px-2 text-xs text-ink-3 hover:text-ink"
      onClick={() => {
        navigator.clipboard.writeText(text).then(
          () => {
            setCopied(true);
            setTimeout(() => setCopied(false), COPY_RESET_MS);
          },
          () => setCopied(false),
        );
      }}
    >
      {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

/** The server's answer as one card: its words, the drawing of its numbers, the detail on demand. */
export function AnswerCard({ answer }: { answer: Answer }) {
  const { message, card } = answer;
  const shown = cardOf(card);
  const Icon = shown.icon;
  return (
    <article className="grid gap-4" data-card={card.type}>
      <MessageView message={message} />
      {shown.body && (
        <section aria-label={shown.title} className="grid gap-4 rounded-lg border border-line bg-raised p-4 [--halo:var(--raised)] sm:p-5">
          <h3 className="flex items-center gap-2 text-sm font-medium text-ink-2">
            <Icon aria-hidden="true" className="size-4" />
            {shown.title}
          </h3>
          {shown.body}
        </section>
      )}
      {message.detail.length > 0 && (
        <details className="group">
          <summary className="flex w-fit cursor-pointer list-none items-center gap-1 text-sm text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
            More detail <ChevronDown aria-hidden="true" className="size-4 transition-transform group-open:rotate-180" />
          </summary>
          <div className="mt-2 grid gap-1 whitespace-pre-line text-sm text-ink-2">
            {message.detail.map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </details>
      )}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <CopyButton text={answer.text} />
      </div>
    </article>
  );
}
