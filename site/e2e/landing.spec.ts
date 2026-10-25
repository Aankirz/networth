import { expect, test } from "@playwright/test";

const BOT = "https://t.me/networth_professor_bot";
const HEADLINE = "Market news, checked against history.";
const overflow = (page: import("@playwright/test").Page) =>
  page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);

test("the hero says what it is and both actions work", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(HEADLINE);
  const hero = page.getByRole("region", { name: HEADLINE });
  await expect(hero.getByText("Built for the Keiki x Maritime hackathon")).toBeVisible();
  await expect(hero.getByRole("link", { name: "Message the bot" })).toHaveAttribute("href", BOT);
  await hero.getByRole("link", { name: "Try the demo" }).click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.getByRole("heading", { name: "What would you like to know about your money?" })).toBeVisible();
});

test("the hero is centred in its column", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const box = (await page.getByRole("heading", { level: 1 }).boundingBox())!;
  expect(Math.abs(box.x + box.width / 2 - 720)).toBeLessThan(4);
});

test("the chat mock plays the IPO thread in order and ends on the Hinglish answer", async ({ page }) => {
  await page.goto("/");
  const chat = page.getByRole("group", { name: "A Telegram chat with the Networth bot about the LIC IPO" });
  await chat.scrollIntoViewIfNeeded();
  const last = chat.locator("[data-at]").last();
  await expect(last).toHaveAttribute("data-off", "");
  await expect(last).not.toHaveAttribute("data-off", "", { timeout: 20_000 });
  await expect(last).toContainText("RHP sabse pehle dekhne wala document hai.");
});

test("under reduced motion every mock shows its whole exchange at once", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.locator("#email").scrollIntoViewIfNeeded();
  await expect(page.locator(".mock [data-at][data-off]")).toHaveCount(0);
  await expect(page.locator("#chat").getByText("The RHP comes first.", { exact: false })).toBeVisible();
});

test("the brief mock is the server's brief for the sample profile", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const brief = page.getByRole("group", { name: "The monthly brief for the sample profile" });
  await expect(brief).toContainText("Morning. It's your investing day, and ₹1,00,000 is ready.");
  await expect(brief).toContainText("Yours is built to sit through a fall of up to 20%.");
});

test("the sample chart is drawn from the demo data", async ({ page }) => {
  await page.goto("/");
  const sample = page.locator("#sample");
  await sample.scrollIntoViewIfNeeded();
  await expect(sample.locator("figure path").first()).toBeAttached();
  await expect(sample.locator(".sr-only table")).toHaveCount(1);
});

test("the letter carries our negative result", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: "Why we built this" })).toContainText("the counts did no better than chance");
});

test("the FAQ opens one answer at a time", async ({ page }) => {
  await page.goto("/");
  const faq = page.locator("#faq");
  await faq.getByText("Is this financial advice?").click();
  await faq.getByText("Can it see my money?").click();
  await expect(faq.locator("details[open]")).toHaveCount(1);
});

test("the footer says research, not advice, and a phone has no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/");
  await expect(page.getByRole("contentinfo").getByText("Research, not advice.", { exact: true })).toBeVisible();
  expect(await overflow(page)).toBeLessThanOrEqual(0);
});
