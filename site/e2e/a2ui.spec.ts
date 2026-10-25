import { expect, test } from "@playwright/test";

// The A2UI SIP answer: the server's messages render through the Networth catalog, and a slider
// recomputes the projection in the browser without any request.

test("the SIP answer renders from A2UI messages and its sliders recompute in place", async ({ page }) => {
  await page.goto("/lab/sip");
  const card = page.locator("[data-a2ui='sip-projection']");
  await expect(page.getByText("Let's map it out. Adjust anything below.")).toBeVisible();
  // ₹25,000 a month at 12% for 15 years, raised 10% a year.
  const headline = card.locator("p").first();
  await expect(headline).toContainText("₹2.15 crore");
  await expect(card.locator("[data-insight]")).toContainText("growth is bigger than everything you put in");

  const requests: string[] = [];
  page.on("request", (r) => requests.push(r.url()));
  const years = page.getByRole("slider", { name: "Years", exact: true });
  await years.fill("25");
  await expect(page.locator("output").filter({ hasText: "25 yrs" })).toBeVisible();
  await expect(headline).toContainText("in 25 years");
  await expect(headline).not.toContainText("₹2.15 crore");
  expect(requests).toEqual([]);
});

test("the SIP answer fits a 320px phone", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/lab/sip");
  await expect(page.locator("[data-a2ui='sip-projection']")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
