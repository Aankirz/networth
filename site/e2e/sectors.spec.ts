import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import type { SectorsCard } from "../lib/ratings-contract";

const BOARD = JSON.parse(
  readFileSync(join(process.cwd(), "e2e", "fixtures", "sectors.json"), "utf8"),
) as SectorsCard;
const BANK = BOARD.rows.find((r) => r.key === "bank")!;
const IT = BOARD.rows.find((r) => r.key === "it")!;

test("the board shows each sector's move and switches period without a request", async ({ page }) => {
  await page.goto("/lab/sectors");
  const card = page.locator("[data-card=sectors]");
  const bank = card.getByRole("button", { name: new RegExp(`^${BANK.name}`) });
  await expect(bank).toContainText(BANK.day);
  const requests: string[] = [];
  // Next prefetches the footer links on its own; only a request from the toggle counts.
  page.on("request", (r) => { if (!r.url().includes("_rsc=")) requests.push(r.url()); });
  await card.getByRole("button", { name: "Month" }).click();
  await expect(bank).toContainText(BANK.month);
  await expect(card.getByRole("button", { name: "Month" })).toHaveAttribute("aria-pressed", "true");
  expect(requests).toEqual([]);
});

test("tapping a sector shows its confirmed stories and its source", async ({ page }) => {
  await page.goto("/lab/sectors");
  const card = page.locator("[data-card=sectors]");
  const bank = card.getByRole("button", { name: new RegExp(`^${BANK.name}`) });
  await bank.click();
  await expect(bank).toHaveAttribute("aria-expanded", "true");
  const story = BANK.stories[0];
  await expect(card.getByText(story.title)).toBeVisible();
  await expect(card.getByText(story.publishers.join(", "), { exact: false })).toBeVisible();
  await expect(card.locator(`a[href="${BANK.source.url}"]`)).toBeVisible();
});

test("a move with no story says so", async ({ page }) => {
  await page.goto("/lab/sectors");
  const card = page.locator("[data-card=sectors]");
  await card.getByRole("button", { name: new RegExp(`^${IT.name}`) }).click();
  await expect(card.getByText("No confirmed story behind this move.")).toBeVisible();
});

test("the board ends with the biggest mover", async ({ page }) => {
  await page.goto("/lab/sectors");
  const top = BOARD.rows.reduce((a, b) =>
    Math.abs(parseFloat(b.day)) > Math.abs(parseFloat(a.day)) ? b : a);
  await expect(page.locator("[data-card=sectors] [data-insight]")).toHaveText(
    `${top.name} moved most on the day, ${top.day}.`,
  );
});

test("the board fits a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/lab/sectors");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
