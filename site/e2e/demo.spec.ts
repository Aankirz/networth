import { expect, test } from "@playwright/test";

const FOOTER = "Research, not advice.";

test("the demo loads, a question gets a card, and the footer shows once in the answer", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByText("Sample profile")).toBeVisible();
  await expect(page.getByRole("heading", { name: "A sample plan" })).toBeVisible();

  await page.getByRole("button", { name: "What could my plan become?" }).click();

  const answer = page.locator("article[data-card='plan_range']");
  await expect(answer).toBeVisible();
  await expect(answer.getByText("Where the money could end up")).toBeVisible();
  await expect(answer.getByText(FOOTER, { exact: false })).toHaveCount(1);
});

test("an unknown link is the friendly not-found page", async ({ page }) => {
  const response = await page.goto("/u/not-a-real.123.abc");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("This link has expired or isn't right.")).toBeVisible();
});

test("each new turn scrolls into view and is announced", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("button", { name: "What could my plan become?" }).click();
  await expect(page.locator("article[data-card='plan_range']")).toBeVisible();

  const field = page.getByLabel("Your question");
  await field.fill("What happened today?");
  await field.press("Enter");

  const news = page.locator("article[data-card='news']");
  await expect(news).toBeInViewport();
  await expect(page.getByTestId("chat-status")).toContainText("Confirmed in the 24 hours");
  await expect(page.locator("article[data-card='plan_range']")).not.toBeInViewport({ ratio: 1 });
});
