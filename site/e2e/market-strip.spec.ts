import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import type { MarketStrip } from "../lib/market";
import { signInAs } from "./session";

const fixture = (name: string) =>
  JSON.parse(readFileSync(join(process.cwd(), "e2e", "fixtures", `${name}.json`), "utf8")) as MarketStrip;
const IN = fixture("market-in");
const US = fixture("market-us");

test("the demo opens with the server's index tiles, each with its change and a pencil line", async ({ page }) => {
  await page.goto("/demo");
  const strip = page.locator("[data-strip=ready]");
  await expect(strip.locator("[data-tile]")).toHaveCount(IN.tiles.length);
  for (const t of IN.tiles) {
    const tile = strip.locator(`[data-tile="${t.symbol}"]`);
    await expect(tile).toContainText(t.name);
    await expect(tile).toContainText(t.level);
    await expect(tile).toContainText(`${t.change} (${t.change_pct})`);
    await expect(tile.locator("[data-spark] path").first()).toBeAttached();
    await expect(tile.locator("a")).toHaveAttribute("href", t.source.url);
    await expect(tile).toContainText(t.source.as_of);
  }
  await expect(strip).toContainText(`Prices from ${IN.tiles[0].source.name}`);
});

test("a fall is drawn in the down colour, apart from any rise", async ({ page }) => {
  await page.goto("/demo");
  const strip = page.locator("[data-strip=ready]");
  const fell = IN.tiles.find((t) => t.direction === "down")!;
  // The recorded day may have no rise at all; a fall is always checked.
  const rose = IN.tiles.find((t) => t.direction === "up");
  const colourOf = (symbol: string) =>
    strip.locator(`[data-tile="${symbol}"] [data-change]`).evaluate((el) => getComputedStyle(el).color);
  const down = await colourOf(fell.symbol);
  if (rose) expect(await colourOf(rose.symbol)).not.toEqual(down);
  const want = await page.evaluate(() => {
    const probe = document.createElement("i");
    probe.style.color = "var(--down)";
    document.body.append(probe);
    return getComputedStyle(probe).color;
  });
  expect(down).toEqual(want);
});

test("a US profile sees the tiles in the server's order, S&P 500 first", async ({ context, page }) => {
  await signInAs(context, "linked-us-ana", "Ana");
  await page.goto("/dashboard");
  const names = page.locator("[data-strip=ready] [data-tile] a > span:first-child");
  await expect(names).toHaveText(US.tiles.map((t) => t.name));
});

test("a slow price source shows a loading strip, then the tiles", async ({ context, page }) => {
  await signInAs(context, "linked-slow-ben", "Ben");
  await page.goto("/dashboard", { waitUntil: "commit" });
  await expect(page.locator("[data-strip=loading]")).toBeAttached();
  await expect(page.locator("[data-strip=ready] [data-tile]")).toHaveCount(IN.tiles.length, { timeout: 10_000 });
  await expect(page.locator("[data-strip=loading]")).toHaveCount(0);
});

test("without index data the strip says so and shows no number", async ({ context, page }) => {
  await signInAs(context, "linked-nomarket-cy", "Cy");
  await page.goto("/dashboard");
  const missing = page.locator("[data-strip=missing]");
  await expect(missing).toHaveText("Index prices aren't available right now.");
  await expect(page.locator("[data-tile]")).toHaveCount(0);
});

test("the strip fits a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto("/demo");
  await expect(page.locator("[data-strip=ready]")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
