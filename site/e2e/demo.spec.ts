import { expect, test } from "@playwright/test";

const FOOTER = "Research, not advice.";

test("a first visit lands on a centred composer with starters", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "What would you like to know about your money?" })).toBeVisible();
  const field = page.getByRole("combobox", { name: "Your question" });
  const box = (await field.boundingBox())!;
  const view = page.viewportSize()!;
  const sidebar = 256;
  const centre = sidebar + (view.width - sidebar) / 2;
  expect(Math.abs(box.x + box.width / 2 - centre)).toBeLessThan(40);
  await expect(page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My brief" })).toBeVisible();
});

test("a starter gets a card and the footer shows once in the answer", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  const answer = page.locator("article[data-card='plan_range']");
  await expect(answer).toBeVisible();
  await expect(answer.getByText(FOOTER, { exact: false })).toHaveCount(1);
});

test("the / picker runs a command by keyboard", async ({ page }) => {
  await page.goto("/demo");
  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("/bri");
  await expect(page.getByRole("listbox", { name: "Commands" })).toBeVisible();
  await field.press("Enter");
  await expect(page.locator("article[data-card='history']")).toBeVisible();
});

test("a telegram-only command gets one kind line", async ({ page }) => {
  await page.goto("/demo");
  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("/watch");
  await field.press("Enter");
  await expect(page.locator("[data-state='telegram']")).toContainText("/watch works in the Telegram bot");
});

test("a command that doesn't exist says so instead of pointing at the bot", async ({ page }) => {
  await page.goto("/demo");
  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("/frobnicate");
  await field.press("Enter");
  await expect(page.locator("[data-state='unknown']")).toContainText("There's no /frobnicate");
});

test("a command the API can't serve yet still gets an answer", async ({ page }) => {
  await page.goto("/demo");
  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("/plan");
  await field.press("Enter");
  await expect(page.locator("article[data-card]")).toBeVisible();
  await expect(page.getByText("Check your connection")).toHaveCount(0);
});

test("the @ picker adds a chip by keyboard and the mention gets a card", async ({ page }) => {
  await page.goto("/demo");
  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("@ran");
  await expect(page.getByRole("listbox", { name: "Things to mention" })).toBeVisible();
  await field.press("ArrowDown");
  await field.press("ArrowUp");
  await field.press("Enter");
  await expect(page.getByRole("button", { name: "Remove @range" })).toBeVisible();
  await field.press("Enter");
  await expect(page.locator("article[data-card='plan_range']")).toBeVisible();
});

test("a chart carries a hidden table of its figures", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  const answer = page.locator("article[data-card='plan_range']");
  await expect(answer.locator(".sr-only table")).toHaveCount(1);
  await expect(answer.locator(".sr-only table tbody tr").first()).toBeAttached();
});

test("the dashboard opens from the top bar and closes with Escape", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  const canvas = page.getByRole("dialog", { name: "Dashboard" });
  await expect(canvas).toBeVisible();
  await expect(canvas.getByRole("heading", { name: "What your plan could become" })).toBeAttached();
  await page.keyboard.press("Escape");
  await expect(canvas).toBeHidden();
});

test("too many questions shows the server's words and a way to the bot", async ({ page }) => {
  await page.goto("/demo");
  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("one too many");
  await field.press("Enter");
  const alert = page.locator("[role=alert][data-error]");
  await expect(alert).toContainText("That's a lot of questions in one hour");
  await expect(alert.getByRole("link", { name: "Ask in the Telegram bot" })).toBeVisible();
});

test("a phone has no sideways scroll, empty or answered", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/demo");
  const overflow = () => page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
  expect(await overflow()).toBeLessThanOrEqual(0);
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  await expect(page.locator("article[data-card='plan_range']")).toBeVisible();
  expect(await overflow()).toBeLessThanOrEqual(0);
});

test("an unknown link is the friendly not-found page", async ({ page }) => {
  const response = await page.goto("/u/not-a-real.123.abc");
  expect(response?.status()).toBe(404);
  await expect(page.getByText("This link has expired or isn't right.")).toBeVisible();
});

test("each new turn scrolls into view and is announced", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  await expect(page.locator("article[data-card='plan_range']")).toBeVisible();

  const field = page.getByRole("combobox", { name: "Your question" });
  await field.fill("What happened today?");
  await field.press("Enter");

  const news = page.locator("article[data-card='news']");
  await expect(news).toBeInViewport();
  await expect(page.getByTestId("chat-status")).toContainText("Confirmed in the 24 hours");
});

test("a chat stays in this browser's list after a reload", async ({ page }) => {
  await page.goto("/demo");
  await page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: "My range" }).click();
  await expect(page.locator("article[data-card='plan_range']")).toBeVisible();
  await page.reload();
  await expect(page.getByRole("region", { name: "Your chats" }).getByRole("button", { name: "What your plan could become", exact: true })).toBeVisible();
});
