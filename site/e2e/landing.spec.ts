import { expect, test } from "@playwright/test";

const BOT = "https://t.me/networth_professor_bot";

test("the hero says what it is and both actions work", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("A calm friend for your monthly investing.");
  const hero = page.getByRole("region", { name: "A calm friend for your monthly investing." });
  await expect(hero.getByRole("link", { name: "Message the bot" })).toHaveAttribute("href", BOT);
  await hero.getByRole("link", { name: "Try the demo" }).click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByRole("heading", { name: "What would you like to know about your money?" })).toBeVisible();
});

test("a question typed on the landing page is asked in the demo", async ({ page }) => {
  await page.goto("/");
  const field = page.getByLabel("Ask the sample profile a question");
  await field.fill("What happened today?");
  await field.press("Enter");
  await expect(page.locator("article[data-card='news']")).toBeVisible();
  await expect(page).toHaveURL(/\/demo$/);
  await page.reload();
  await expect(page.locator("article[data-card='news']")).toHaveCount(0);
});

test("a starter on the landing page opens the demo with its answer", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("list", { name: "Or start with" }).getByRole("link", { name: "What could my plan become?" }).click();
  await expect(page.locator("article[data-card='plan_range']")).toBeVisible();
});

test("the track record shows the server's own negative result", async ({ page }) => {
  await page.goto("/");
  const record = page.getByRole("region", { name: "We tested ourselves. It came back negative." });
  await expect(record.getByText("From 2010 to 2021", { exact: false })).toBeVisible();
});

test("the sample chart is drawn from the demo data", async ({ page }) => {
  await page.goto("/");
  const sample = page.locator("#sample");
  await sample.scrollIntoViewIfNeeded();
  await expect(sample.locator("figure path").first()).toBeAttached();
  await expect(sample.locator(".sr-only table")).toHaveCount(1);
});

test("the FAQ opens one answer at a time", async ({ page }) => {
  await page.goto("/");
  const faq = page.locator("#faq");
  await faq.getByText("Is this financial advice?").click();
  await faq.getByText("Can it see my money?").click();
  await expect(faq.locator("details[open]")).toHaveCount(1);
});

test("the footer line shows once and a phone has no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");
  await expect(page.getByText("Research, not advice.", { exact: true })).toHaveCount(1);
  const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
});
