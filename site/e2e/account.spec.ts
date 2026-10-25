import { expect, test } from "@playwright/test";

import { signInAs } from "./session";

const LINK_STEP = "Send /weblink to @networth_professor_bot and type the code here.";
const PLAN = "Balanced. 20% safety, 70% core, 10% growth";
const overflow = (page: import("@playwright/test").Page) =>
  page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);

test("signed out, the header has Sign in next to Try the demo", async ({ page }) => {
  await page.goto("/");
  const nav = page.getByRole("navigation").first();
  await expect(nav.getByRole("button", { name: "Sign in" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Try the demo" })).toBeVisible();
});

test("Sign in hands the visitor to Google", async ({ page }) => {
  // Google itself is out of reach in tests, so stop at the redirect and check where it points.
  await page.route("https://accounts.google.com/**", (route) => route.fulfill({ status: 200, body: "google" }));
  await page.goto("/");
  const [request] = await Promise.all([
    page.waitForRequest((r) => r.url().startsWith("https://accounts.google.com/")),
    page.getByRole("navigation").first().getByRole("button", { name: "Sign in" }).click(),
  ]);
  const url = new URL(request.url());
  expect(url.searchParams.get("redirect_uri")).toBe("http://127.0.0.1:3100/api/auth/callback/google");
  expect(url.searchParams.get("client_id")).toBe("e2e-client-id");
});

test("signed in, the header shows the avatar and a menu with Dashboard, Sign out and Forget me", async ({ page, context }) => {
  await signInAs(context, "linked-header", "Ana");
  await page.goto("/");
  const nav = page.getByRole("navigation").first();
  await expect(nav.getByRole("button", { name: "Sign in" })).toHaveCount(0);
  await nav.getByRole("button", { name: "Account: Ana" }).click();
  await expect(nav.getByText("Signed in as Ana")).toBeVisible();
  await expect(nav.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
  await expect(nav.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(nav.getByRole("button", { name: "Forget me on the web" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(nav.getByText("Signed in as Ana")).toHaveCount(0);
});

test("a forged session cookie is treated as signed out", async ({ page, context }) => {
  await signInAs(context, "linked-forger", "Eve", "not-the-site-secret-0123456789abcdef");
  await page.goto("/dashboard");
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  await expect(page.getByText(PLAN)).toHaveCount(0);
});

test("signed out, /dashboard asks for Google and leaves the demo open", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
  await expect(page.getByRole("link", { name: "The demo" })).toHaveAttribute("href", "/demo");
});

test("an unlinked visitor is told how to link, a wrong code is refused, the right one shows their plan", async ({ page, context }) => {
  await signInAs(context, "fresh-linker", "Ben");
  await page.goto("/dashboard");
  await expect(page.getByText(LINK_STEP)).toBeVisible();
  const field = page.getByLabel("Code from the bot");
  await field.fill("123456");
  await page.getByRole("button", { name: "Link" }).click();
  await expect(page.locator("#weblink-error")).toContainText("That code didn't work. A code works once and only for 10 minutes.");
  await field.fill("246 810");
  await page.getByRole("button", { name: "Link" }).click();
  await expect(page.getByText(PLAN).first()).toBeVisible();
});

test("a used code is refused in plain words", async ({ page, context }) => {
  await signInAs(context, "second-linker", "Cara");
  await page.goto("/dashboard");
  await page.getByLabel("Code from the bot").fill("975310");
  await page.getByRole("button", { name: "Link" }).click();
  await expect(page.locator("#weblink-error")).toContainText("Send /weblink to the bot for a new one.");
});

test("a linked visitor's dashboard opens on their own plan", async ({ page, context }) => {
  await signInAs(context, "linked-dash", "Ana");
  await page.goto("/dashboard");
  await expect(page.getByText(PLAN).first()).toBeVisible();
});

test("Forget me unlinks and signs out", async ({ page, context }) => {
  await signInAs(context, "linked-forget", "Ana");
  await page.goto("/");
  const nav = page.getByRole("navigation").first();
  await nav.getByRole("button", { name: "Account: Ana" }).click();
  await nav.getByRole("button", { name: "Forget me on the web" }).click();
  await expect(page).toHaveURL(/\/\?forgotten=1$/);
  await expect(page.getByRole("navigation").first().getByRole("button", { name: "Sign in" })).toBeVisible();
  await signInAs(context, "linked-forget", "Ana");
  await page.goto("/dashboard");
  await expect(page.getByText(LINK_STEP)).toBeVisible();
});

test("Sign out returns to the landing page signed out", async ({ page, context }) => {
  await signInAs(context, "linked-out", "Ana");
  await page.goto("/");
  const nav = page.getByRole("navigation").first();
  await nav.getByRole("button", { name: "Account: Ana" }).click();
  await nav.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("navigation").first().getByRole("button", { name: "Sign in" })).toBeVisible();
});

test("/demo works signed out exactly as before", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "What would you like to know about your money?" })).toBeVisible();
});

test("the footer links to /privacy, which says what we keep and how to erase", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("contentinfo").getByRole("link", { name: "Privacy" }).click();
  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("heading", { name: "What we keep" })).toBeVisible();
  await expect(page.getByText("subject id", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "How to erase it" })).toBeVisible();
});

test("on a phone the signed-in header and the link step have no sideways scroll", async ({ page, context }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await signInAs(context, "phone-user", "Ana");
  await page.goto("/");
  expect(await overflow(page)).toBeLessThanOrEqual(0);
  await page.goto("/dashboard");
  await expect(page.getByText(LINK_STEP)).toBeVisible();
  expect(await overflow(page)).toBeLessThanOrEqual(0);
});
