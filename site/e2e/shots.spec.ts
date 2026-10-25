import { test } from "@playwright/test";

// Run with SHOTS=1 to refresh docs/phases/phase-8-shots/. Skipped in the normal run.
const OUT = "../docs/phases/phase-8-shots";
const USER = "/u/e2eToken.4102444800.abcdef0123456789";
const PAGES = [
  { name: "demo", path: "/demo", ask: "What could my plan become?" },
  { name: "user", path: USER, ask: "What happened today?" },
];

for (const width of [320, 1440]) {
  for (const scheme of ["light", "dark"] as const) {
    for (const p of PAGES) {
      test(`${p.name} ${width} ${scheme}`, async ({ page }) => {
        test.skip(!process.env.SHOTS, "screenshots only on SHOTS=1");
        await page.setViewportSize({ width, height: width < 800 ? 740 : 960 });
        await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
        await page.goto(p.path);
        const starter = page.getByRole("button", { name: p.ask });
        await starter.click();
        await page.locator("article[data-card]").first().waitFor();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
        if (overflow) throw new Error(`horizontal scroll at ${width}px on ${p.name}`);
        await page.screenshot({ path: `${OUT}/${p.name}-${width}-${scheme}.png`, fullPage: true });
      });
    }
  }
}
