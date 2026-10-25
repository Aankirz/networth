import type { NewsCard } from "@/lib/contract";
import { EmptyLedger } from "@/components/pencil";

export function NewsList({ card }: { card: NewsCard }) {
  if (!card.items.length) return card.note ? <EmptyLedger note={card.note} /> : null;
  return (
    <ol className="divide-y divide-rule" /* taste-skill-ignore: a passbook ledger's ruled rows, the design idea */>
      {card.items.map((item, i) => (
        <li key={`${i}-${item.title}`} className="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-4 py-3 first:pt-0">
          <span className="figures pt-0.5 text-note text-graphite">{item.day}</span>
          <div className="min-w-0">
            <p className="font-medium">{item.title}</p>
            {item.publishers.length > 0 && (
              <p className="text-note text-graphite">Reported by {item.publishers.join(", ")}.</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
