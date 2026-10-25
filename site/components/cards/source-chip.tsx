import { ArrowUpRight } from "lucide-react";

import type { Source } from "@/lib/ratings-contract";

const ISO_TIME = /^\d{4}-\d{2}-\d{2}T/;

/** Where a number came from and when, opening the source. */
export function SourceChip({ source }: { source: Source }) {
  // 13C sends ISO times, cut to the day; 13A sends its own words ("last close 24 Oct 2026") as they are.
  const when = ISO_TIME.test(source.as_of) ? source.as_of.slice(0, 10) : source.as_of;
  return (
    <a
      href={source.url}
      rel="noopener"
      target="_blank"
      className="inline-flex max-w-full items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs text-ink-2 no-underline hover:border-line-strong hover:text-ink"
    >
      <span className="truncate">{source.name}</span>
      <span className="figure shrink-0 text-ink-3">{when}</span>
      <ArrowUpRight aria-hidden="true" className="size-3 shrink-0" />
    </a>
  );
}
