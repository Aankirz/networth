import { expect, test, type Page } from "@playwright/test";

// Run with SHOTS=1 to refresh docs/phases/phase-10-shots/. Skipped in the normal run.
const OUT = "../docs/phases/phase-10-shots";
const USER = "/u/e2eToken.4102444800.abcdef0123456789";

type Shot = { name: string; path: string; act?: (page: Page) => Promise<void> };

const starter = (page: Page, label: string) =>
  page.getByRole("list", { name: "Questions to start with" }).getByRole("button", { name: label }).click();

const SHOTS: Shot[] = [
  { name: "landing", path: "/" },
  {
    name: "landing-full",
    path: "/",
    act: async (page) => {
      // The sketches draw as they come into view, so walk the page once before the full shot.
      for (let y = 0; y < 6000; y += 600) {
        await page.evaluate((top) => window.scrollTo(0, top), y);
        await page.waitForTimeout(150);
      }
      await page.locator("#sample figure path").first().waitFor();
      await page.evaluate(() => window.scrollTo(0, 0));
    },
  },
  { name: "demo-empty", path: "/demo" },
  {
    name: "demo-answer",
    path: "/demo",
    act: async (page) => {
      await starter(page, "My range");
      await page.locator("article[data-card]").first().waitFor();
    },
  },
  {
    name: "demo-canvas",
    path: "/demo",
    act: async (page) => {
      await starter(page, "What happened today?");
      await page.locator("article[data-card]").first().waitFor();
      await page.getByRole("button", { name: "Dashboard", exact: true }).click();
      await page.getByRole("button", { name: "Close the dashboard" }).waitFor();
    },
  },
  {
    name: "user-answer",
    path: USER,
    act: async (page) => {
      await starter(page, "My brief");
      await page.locator("article[data-card]").first().waitFor();
    },
  },
];

for (const width of [320, 1440]) {
  for (const theme of ["dark", "light"] as const) {
    for (const shot of SHOTS) {
      test(`${shot.name} ${width} ${theme}`, async ({ page, context }) => {
        test.skip(!process.env.SHOTS, "screenshots only on SHOTS=1");
        await context.addCookies([{ name: "nw-theme", value: theme, url: "http://127.0.0.1:3100" }]);
        await page.setViewportSize({ width, height: width < 800 ? 740 : 960 });
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.goto(shot.path);
        await shot.act?.(page);
        const overflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - document.documentElement.clientWidth);
        expect(overflow, `horizontal scroll at ${width}px on ${shot.name}`).toBeLessThanOrEqual(0);
        await page.screenshot({ path: `${OUT}/${shot.name}-${width}-${theme}.png`, fullPage: shot.name === "landing-full" });
      });
    }
  }
}
