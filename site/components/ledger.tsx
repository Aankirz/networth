import type { Dashboard } from "@/lib/contract";
import { HistoryRows } from "@/components/cards/history";
import { HoldingsView } from "@/components/cards/holdings";
import { NewsList } from "@/components/cards/news";
import { RangeView } from "@/components/cards/range";
import { Footer } from "@/components/message";
import { withoutFooter } from "@/lib/words";

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid gap-4 pt-4">
      <h2 id={id} className="text-head">{title}</h2>
      {children}
    </section>
  );
}

/** The dashboard: the user's plan line, then the counted past, all in the server's words and figures. */
export function Ledger({ board }: { board: Dashboard }) {
  const { profile } = board;
  return (
    <div className="grid gap-12">
      <header className="grid gap-3">
        <h1 className="text-display">{board.sample ? "A sample plan" : "Your plan"}</h1>
        {profile.plan ? (
          <p className="max-w-[60ch]">{profile.plan}.</p>
        ) : (
          <p className="max-w-[60ch]">You haven&apos;t picked a plan yet. Type /start in the bot to finish setting up.</p>
        )}
        <dl className="flex flex-wrap gap-x-10 gap-y-2">
          <div>
            <dt className="text-note text-graphite">Each month</dt>
            <dd className="figures font-display text-display">{profile.money}</dd>
          </div>
          {profile.day && (
            <div>
              <dt className="text-note text-graphite">Investing day</dt>
              <dd className="figures font-display text-display">the {profile.day}</dd>
            </div>
          )}
        </dl>
      </header>

      <Section id="news-title" title="This month's news">
        <NewsList card={board.news} />
      </Section>
      <Section id="history-title" title="What history counted">
        <HistoryRows card={board.history} />
      </Section>
      <Section id="range-title" title="What history says about this plan">
        <RangeView card={board.plan_range} label={withoutFooter(board.plan_range.range?.label, board.footer)} />
      </Section>
      {board.holdings && (
        <Section id="holdings-title" title="What you hold">
          <HoldingsView card={board.holdings} label={withoutFooter(board.holdings.label, board.footer)} />
        </Section>
      )}

      <div className="grid gap-1 pt-2">
        <Footer text={board.footer} />
        {!board.sample && (
          <p className="text-note text-graphite">This page is private to you. Anyone with the link can see it, so don&apos;t share it.</p>
        )}
      </div>
    </div>
  );
}
