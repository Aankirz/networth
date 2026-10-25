"use client";

import { EmptyNote } from "@/components/cards/empty";
import { Sketch } from "@/components/sketch";
import { newsSpec, newsTable } from "@/lib/charts";
import type { NewsCard } from "@/lib/contract";

export function NewsList({ card }: { card: NewsCard }) {
  if (!card.items.length) return card.note ? <EmptyNote note={card.note} /> : null;
  return (
    <div className="grid gap-3">
      {card.items.filter((i) => i.day).length > 1 && (
        <Sketch title="The stories, oldest to newest" height={52} build={(w) => newsSpec(card.items, w)} table={newsTable(card.items)} />
      )}
      <ol className="grid gap-3">
        {card.items.map((item, i) => (
          <li key={`${i}-${item.title}`} className="grid grid-cols-[3.75rem_minmax(0,1fr)] gap-x-3">
            <span className="figure pt-px text-xs text-ink-3">{item.day}</span>
            <div className="min-w-0">
              <p className="text-sm font-medium">{item.title}</p>
              {item.publishers.length > 0 && (
                <p className="text-xs text-ink-3">Reported by {item.publishers.join(", ")}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
