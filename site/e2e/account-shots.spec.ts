import { expect, test, type Page } from "@playwright/test";

import { signInAs } from "./session";

// Run with SHOTS=1 to refresh docs/phases/phase-11-shots/. Skipped in the normal run.
const OUT = "../docs/phases/phase-11-shots";

type Shot = { name: string; path: string; subject: string; act?: (page: Page) => Promise<void> };

const SHOTS: Shot[] = [
  { name: "signed-out-header", path: "/", subject: "" },
  { name: "signed-in-header", path: "/", subject: "linked-shots" },
  {
    name: "signed-in-menu",
    path: "/",
    subject: "linked-shots",
    act: async (page) => {
      await page.getByRole("navigation").first().getByRole("button", { name: "Account: Ana" }).click();
      await page.getByText("Signed in as Ana").waitFor();
    },
  },
  { name: "link-step", path: "/dashboard", subject: "unlinked-shots" },
  {
    name: "link-step-wrong-code",
    path: "/dashboard",
    subject: "unlinked-shots",
    act: async (page) => {
      await page.getByLabel("Code from the bot").fill("123456");
      await page.getByRole("button", { name: "Link" }).click();
      await expect(page.locator("#weblink-error")).toContainText("didn't work");
    },
  },
  { name: "dashboard-linked", path: "/dashboard", subject: "linked-shots" },
];

for (const width of [320, 1440]) {
  for (const theme of ["dark", "light"] as const) {
    for (const shot of SHOTS) {
      test(`${shot.name} ${width} ${theme}`, async ({ page, context }) => {
        test.skip(!process.env.SHOTS, "screenshots only on SHOTS=1");
        await context.addCookies([{ name: "nw-theme", value: theme, url: "http://127.0.0.1:3100" }]);
        if (shot.subject) await signInAs(context, shot.subject, "Ana");
        await page.setViewportSize({ width, height: width < 800 ? 740 : 960 });
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.goto(shot.path);
        await shot.act?.(page);
        const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
        expect(overflow, `horizontal scroll at ${width}px on ${shot.name}`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `${OUT}/${shot.name}-${width}-${theme}.png` });
      });
    }
  }
}
