import type { IndexTile, Series, Source } from "@/lib/contract";

// The market strip at the top of the chat. Proposed to Phase 13A, not yet in the contract:
// GET /api/demo/market, /api/u/{token}/market and /api/web/market return a MarketStrip whose
// tiles are already in the order that user should see (Indian indices first for an INR profile,
// the S&P 500, Nasdaq and Dow first for a USD one). The site never reorders or fills a gap.
// Each tile carries its own source, since an Indian and a US close can fall on different days.

export interface MarketTile extends IndexTile {
  series: Series;
  source: Source;
}

export interface MarketStrip {
  tiles: MarketTile[];
}

export function isMarketStrip(body: unknown): body is MarketStrip {
  const m = body as MarketStrip | null;
  return (
    !!m &&
    Array.isArray(m.tiles) &&
    m.tiles.length > 0 &&
    m.tiles.every((t) => typeof t.name === "string" && typeof t.level === "string" && !!t.source && Array.isArray(t.series?.points))
  );
}
