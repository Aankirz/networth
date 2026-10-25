import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageFrame } from "@/components/account/page-frame";
import { SectorsView } from "@/components/cards/sectors";
import board from "@/e2e/fixtures/sectors.json";
import type { SectorsCard } from "@/lib/ratings-contract";

// The 13C sector board against a fixture from the real board() on test data. The moves are fake,
// so the page exists only where NETWORTH_LAB is set (Playwright), never on production.
export const metadata: Metadata = { title: "Sectors · Networth lab", robots: { index: false } };
export const dynamic = "force-dynamic";

export default function SectorsLab() {
  if (process.env.NETWORTH_LAB !== "1") notFound();
  return (
    <PageFrame>
      <section className="rounded-2xl border border-line bg-raised p-5 sm:p-6">
        <SectorsView card={board as SectorsCard} />
      </section>
    </PageFrame>
  );
}
