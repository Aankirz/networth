import { expect, test, type Page } from "@playwright/test";

const fan = async (page: Page) => {
  await page.goto("/demo");
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  const chart = page.locator("article[data-card='plan_range'] figure").first();
  await chart.locator("g.mark-hit").first().waitFor();
  // The strokes are drawn once the chart scrolls near the view, and the market strip can push it below.
  await chart.scrollIntoViewIfNeeded();
  return chart;
};

test("focusing a mark shows its exact figures", async ({ page }) => {
  const chart = await fan(page);
  await chart.locator("g.mark-hit").first().focus();
  await expect(chart.locator("[data-tip]")).toContainText("₹70,20,000");
});

test("hovering a mark shows its exact figures", async ({ page }) => {
  const chart = await fan(page);
  await chart.evaluate((el) => el.scrollIntoView({ block: "center" }));
  await chart.locator("g.mark-hit").nth(1).locator("rect[data-focus]").hover();
  await expect(chart.locator("[data-tip]")).toContainText("₹55,30,000");
});

test("each mark is named for a screen reader", async ({ page }) => {
  const chart = await fan(page);
  await expect(chart.getByRole("img", { name: /Before inflation: .*₹70,20,000/ })).toBeAttached();
});

test("under reduced motion the strokes are drawn at once", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const chart = await fan(page);
  const path = chart.locator("path[data-draw]").first();
  await expect(path).toBeAttached();
  expect(await path.evaluate((p) => getComputedStyle(p).strokeDashoffset)).toMatch(/^0(px)?$/);
});

test("the same answer draws the same strokes every time", async ({ page }) => {
  const first = await (await fan(page)).locator("path[data-draw]").first().getAttribute("d");
  const again = await (await fan(page)).locator("path[data-draw]").first().getAttribute("d");
  expect(again).toBe(first);
});

test("the chart box keeps its height while rough.js loads", async ({ page }) => {
  const chart = await fan(page);
  const box = chart.locator("> div").first();
  expect((await box.boundingBox())!.height).toBeGreaterThan(100);
});
