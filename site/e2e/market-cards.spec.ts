import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import type { ChatTurn, PositionCard, PriceCard, PriceHistoryCard } from "../lib/contract";

const turn = (name: string) =>
  JSON.parse(readFileSync(join(process.cwd(), "e2e", "fixtures", `${name}.json`), "utf8")) as ChatTurn;
const TCS = turn("answer-price-inr").card as PriceCard;
const AAPL = turn("answer-price-usd").card as PriceCard;
const HOLDING = turn("answer-position").card as PositionCard;

async function ask(page: Page, question: string, type: string) {
  await page.goto(`/demo?q=${encodeURIComponent(question)}`);
  const card = page.locator(`article[data-card=${type}]`).last();
  await expect(card).toBeVisible({ timeout: 10_000 });
  return card;
}

test("a price answer shows the close, the day's move, the year and its source", async ({ page }) => {
  const card = await ask(page, "What is TCS's price?", "price");
  await expect(card.locator("[data-price] header")).toContainText(TCS.price);
  await expect(card.locator("[data-change]").first()).toHaveText(`${TCS.change} (${TCS.change_pct})`);
  await expect(card.locator("[data-range]")).toContainText(TCS.low_52w);
  await expect(card.locator("[data-range]")).toContainText(TCS.high_52w);
  await expect(card.locator(`a[href="${TCS.source.url}"]`)).toContainText(TCS.source.as_of);
  await expect(card.locator("[data-insight]")).toBeVisible();
});

test("a rise is drawn in the up colour", async ({ page }) => {
  const card = await ask(page, "What is TCS's price?", "price");
  const want = TCS.direction === "up" ? "--up" : "--down";
  const colour = await card.locator("[data-change]").first().evaluate((el) => getComputedStyle(el).color);
  const expected = await page.evaluate((v) => {
    const probe = document.createElement("i");
    probe.style.color = `var(${v})`;
    document.body.append(probe);
    return getComputedStyle(probe).color;
  }, want);
  expect(colour).toBe(expected);
});

test("the chart reads out the first close with the arrow keys, in the card's currency", async ({ page }) => {
  const card = await ask(page, "What is Apple's price?", "price");
  await expect(card.locator("[data-price] header")).toContainText(AAPL.price);
  const chart = card.getByRole("img", { name: new RegExp(AAPL.series.label) });
  await chart.focus();
  await page.keyboard.press("Home");
  const first = AAPL.series.points[0].v.toFixed(2);
  await expect(card.locator("[data-readout]")).toContainText(`$${Number(first).toLocaleString("en-US", { minimumFractionDigits: 2 })}`);
});

test("a holding shows what it is worth against what was paid, with a dashed paid line", async ({ page }) => {
  const card = await ask(page, "I hold 12 TCS bought at 3420", "position");
  for (const v of [HOLDING.value, HOLDING.invested, HOLDING.avg_cost, HOLDING.quantity]) await expect(card).toContainText(v);
  await expect(card.locator("[data-change]").first()).toHaveText(`${HOLDING.gain} (${HOLDING.gain_pct})`);
  await expect(card.locator("[data-level]")).toContainText(`You paid ${HOLDING.avg_cost}`);
});

test("the what-if slider recomputes in the browser without asking the server", async ({ page }) => {
  const card = await ask(page, "I hold 12 TCS bought at 3420", "position");
  const out = card.locator("[data-whatif-out]");
  await expect(out).toContainText(HOLDING.value);
  const requests: string[] = [];
  page.on("request", (r) => { if (!r.url().includes("_rsc=")) requests.push(r.url()); });
  const slider = card.getByRole("slider", { name: /How much .* moves/ });
  await slider.fill("50");
  await expect(card.getByText("+50%")).toBeVisible();
  await expect(out).not.toContainText(HOLDING.value);
  expect(requests).toEqual([]);
});

test("a holding under water says how far it must rise to get back to what was paid", async ({ page }) => {
  test.skip(HOLDING.direction !== "down", "the recorded holding is not under water");
  const card = await ask(page, "I hold 12 TCS bought at 3420", "position");
  await expect(card.locator("[data-insight]")).toContainText("to get back to what you paid");
});

test("the price and holding cards fit a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  for (const [q, type] of [["What is TCS's price?", "price"], ["I hold 12 TCS bought at 3420", "position"]]) {
    await ask(page, q, type);
    // The chat scrolls inside its own box, so the page can't show a card that is too wide.
    const overflow = await page.evaluate(() =>
      Math.max(...[document.documentElement, ...document.querySelectorAll(".overflow-y-auto")].map((el) => el.scrollWidth - el.clientWidth)));
    expect(overflow).toBeLessThanOrEqual(0);
  }
});

const NIFTY = turn("answer-history").card as PriceHistoryCard;
const TEN_YEARS = "How has Nifty 50 done over the last 10 years?";

test("a history answer opens on the server's return for the years asked, with its worst falls", async ({ page }) => {
  const card = await ask(page, TEN_YEARS, "price_history");
  await expect(card.locator("[data-headline]")).toContainText(`${NIFTY.returns[0].value} over ${NIFTY.returns[0].label}`);
  for (const r of NIFTY.returns) await expect(card).toContainText(r.value);
  await expect(card.locator("[data-fall]")).toHaveCount(NIFTY.drawdowns.length);
  await expect(card.locator("[data-span]")).toHaveCount(NIFTY.drawdowns.length);
  await expect(card.locator(`a[href="${NIFTY.source.url}"]`)).toContainText(NIFTY.source.as_of);
});

test("the range switch cuts the line in the browser and shades only the falls inside it", async ({ page }) => {
  const card = await ask(page, TEN_YEARS, "price_history");
  const requests: string[] = [];
  page.on("request", (r) => { if (!r.url().includes("_rsc=")) requests.push(r.url()); });
  await card.getByRole("button", { name: "3Y" }).click();
  await expect(card.getByRole("button", { name: "3Y" })).toHaveAttribute("aria-pressed", "true");
  await expect(card.locator("[data-headline]")).toContainText("over 3 years");
  await expect(card.locator("[data-headline]")).not.toContainText(NIFTY.returns[0].value);
  const shown = await card.locator("[data-fall][data-shown]").count();
  await expect(card.locator("[data-span]")).toHaveCount(shown);
  expect(shown).toBeLessThan(NIFTY.drawdowns.length);
  await card.getByRole("button", { name: "All" }).click();
  await expect(card.locator("[data-headline]")).toContainText(NIFTY.returns[0].value);
  expect(requests).toEqual([]);
});

test("the history card fits a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await ask(page, TEN_YEARS, "price_history");
  const overflow = await page.evaluate(() =>
    Math.max(...[document.documentElement, ...document.querySelectorAll(".overflow-y-auto")].map((el) => el.scrollWidth - el.clientWidth)));
  expect(overflow).toBeLessThanOrEqual(0);
});
