import { expect, test } from "@playwright/test";

import { signInAs } from "./session";

// Owner request: wherever the site says the brief comes on your day, "Get my brief now" loads the
// whole brief straight away through the brief command.

test("signed out, Get my brief now opens the demo and runs the brief at once", async ({ page }) => {
  await page.goto("/");
  const buttons = page.getByRole("link", { name: "Get my brief now" });
  await expect(buttons).toHaveCount(2);
  await buttons.last().click();
  await expect(page).toHaveURL(/\/demo$/);
  await expect(page.locator("article[data-card='history']")).toBeVisible();
});

test("signed in, Get my brief now goes to the visitor's own brief", async ({ page, context }) => {
  await signInAs(context, "linked-brief", "Ana");
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Get my brief now" }).first()).toHaveAttribute("href", "/dashboard?q=%2Fbrief");
  await page.goto("/dashboard?q=%2Fbrief");
  await expect(page.locator("article[data-card='history']")).toBeVisible();
});

test("a /u link with ?q=/brief runs the brief for that user", async ({ page }) => {
  await page.goto("/u/e2eToken.4102444800.abcdef0123456789?q=%2Fbrief");
  await expect(page.locator("article[data-card='history']")).toBeVisible();
});
