import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageFrame } from "@/components/account/page-frame";
import { RatingView } from "@/components/cards/rating";
import aapl from "@/e2e/fixtures/rating-aapl.json";
import hdfc from "@/e2e/fixtures/rating-hdfcbank.json";
import type { RatingCard } from "@/lib/ratings-contract";

// The 13C rating card against fixtures from the real engine on test data. The ratings are fake,
// so the page exists only where NETWORTH_LAB is set (Playwright), never on production.
export const metadata: Metadata = { title: "Rating · Networth lab", robots: { index: false } };
export const dynamic = "force-dynamic";

const CARDS = [hdfc, aapl] as RatingCard[];

export default function RatingLab() {
  if (process.env.NETWORTH_LAB !== "1") notFound();
  return (
    <PageFrame>
      <div className="grid gap-6">
        {CARDS.map((card) => (
          <section key={card.slug} className="rounded-2xl border border-line bg-raised p-5 sm:p-6">
            <RatingView card={card} />
          </section>
        ))}
      </div>
    </PageFrame>
  );
}
