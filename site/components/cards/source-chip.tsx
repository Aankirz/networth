import { ArrowUpRight } from "lucide-react";

import type { Source } from "@/lib/ratings-contract";

/** Where a number came from and when, opening the source. */
export function SourceChip({ source }: { source: Source }) {
  const when = source.as_of.slice(0, 10);
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
