import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import type { RatingCard } from "../lib/ratings-contract";

const fixture = (name: string) =>
  JSON.parse(readFileSync(join(process.cwd(), "e2e", "fixtures", name), "utf8")) as RatingCard;
const HDFC = fixture("rating-hdfcbank.json");
const AAPL = fixture("rating-aapl.json");

test("the rating card shows the view, the score and the outlook", async ({ page }) => {
  await page.goto("/lab/rating");
  const card = page.locator("[data-card=rating]").first();
  await expect(card.getByText(HDFC.view, { exact: true })).toBeVisible();
  await expect(card.getByRole("img", { name: `Score ${HDFC.score} out of 100` })).toBeVisible();
  await expect(card.getByText(HDFC.outlook)).toBeVisible();
});

test("every driver names its source and opens it", async ({ page }) => {
  await page.goto("/lab/rating");
  const card = page.locator("[data-card=rating]").first();
  for (const d of HDFC.drivers) {
    await expect(card.getByText(d.value)).toBeVisible();
    await expect(card.locator(`a[href="${d.source.url}"]`).first()).toContainText(d.source.as_of.slice(0, 10));
  }
});

test("a weak track record is said plainly, with the missing data", async ({ page }) => {
  await page.goto("/lab/rating");
  const card = page.locator("[data-card=rating]").nth(1);
  await expect(card.locator("[data-insight]")).toHaveText(AAPL.track.text);
  await expect(card.getByText(AAPL.track.edge)).toBeVisible();
  for (const line of AAPL.missing) await expect(card.getByText(line)).toBeVisible();
});

test("the rating card fits a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/lab/rating");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
