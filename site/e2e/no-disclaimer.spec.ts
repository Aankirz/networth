import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { DISCLAIMERS } from "../scripts/disclaimers.mjs";

// The owner's order: no "Research, not advice." footer and no disclaimer like it, in any
// language. Every reply the mock API serves, and every page a visitor can open, is checked.

const FIXTURES = join(process.cwd(), "e2e", "fixtures");
const found = (text: string) => DISCLAIMERS.filter((re) => re.test(text)).map(String);

test("no reply fixture carries a disclaimer", () => {
  for (const name of readdirSync(FIXTURES).filter((n) => n.endsWith(".json"))) {
    expect(found(readFileSync(join(FIXTURES, name), "utf8")), name).toEqual([]);
  }
});

for (const path of ["/", "/demo", "/privacy", "/dashboard", "/lab/sip"]) {
  test(`${path} shows no disclaimer`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(found(await page.locator("body").innerText())).toEqual([]);
    expect(found((await page.locator('meta[name="description"]').getAttribute("content")) ?? "")).toEqual([]);
  });
}

test("a demo answer and the dashboard show no disclaimer", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  await page.locator("article[data-card]").first().waitFor();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Close the dashboard" }).waitFor();
  expect(found(await page.locator("body").innerText())).toEqual([]);
});
