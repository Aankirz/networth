import type { Card, ChatTurn } from "@/lib/contract";
import { HistoryRows } from "@/components/cards/history";
import { HoldingsView } from "@/components/cards/holdings";
import { NewsList } from "@/components/cards/news";
import { RangeView } from "@/components/cards/range";
import { Footer, MessageView } from "@/components/message";

/** One renderer per card type the server sends. "text" has none: the message is the answer. */
const CARDS: { [K in Card["type"]]: (card: Extract<Card, { type: K }>) => React.ReactNode } = {
  news: (card) => <NewsList card={card} />,
  history: (card) => <HistoryRows card={card} />,
  plan_range: (card) => <RangeView card={card} />,
  holdings: (card) => <HoldingsView card={card} />,
  text: () => null,
};

function cardBody(card: Card): React.ReactNode {
  const render = CARDS[card.type] as (c: Card) => React.ReactNode;
  return render(card);
}

export function AnswerCard({ turn }: { turn: ChatTurn }) {
  const body = cardBody(turn.card);
  return (
    <article className="grid gap-4 rounded-lg bg-sheet p-4 sm:p-5" data-card={turn.card.type}>
      <MessageView message={turn.message} />
      {body && <div className="border-t border-rule pt-4">{body}</div>}
      <Footer text={turn.message.footer} />
    </article>
  );
}
