import { expect, test } from "@playwright/test";

test("pinned on a wide screen, the dashboard docks beside the chat and stays pinned", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo");
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await page.getByRole("button", { name: "Pin the dashboard open" }).click();
  await expect(page.getByRole("dialog", { name: "Dashboard" })).toHaveCount(0);
  const docked = page.getByRole("complementary", { name: "Dashboard", exact: true });
  await expect(docked).toBeVisible();
  await page.getByRole("combobox", { name: "Your question" }).fill("still typing");
  await page.reload();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(page.getByRole("button", { name: "Unpin the dashboard" })).toBeVisible();
});

test("on a phone the dashboard is a full-width sheet", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/demo");
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  const sheet = page.getByRole("dialog", { name: "Dashboard" });
  await expect(sheet).toBeVisible();
  expect((await sheet.boundingBox())!.width).toBeCloseTo(320, 0);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});

test("a sidebar link opens the dashboard at its section", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/demo");
  await page.getByRole("navigation", { name: "Dashboard" }).getByRole("button", { name: "My range" }).click();
  await expect(page.locator("#canvas-range-title")).toBeInViewport();
});
