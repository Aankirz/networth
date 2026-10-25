import { expect, test } from "@playwright/test";

import { money, moneyShort } from "../lib/money";

// Money follows the user's currency: lakh and crore for rupees, thousands and M for dollars.
test("money is written the way each currency's reader says it", () => {
  expect(moneyShort(291000, "INR")).toBe("₹2.91 lakh");
  expect(moneyShort(12000000, "INR")).toBe("₹1.2 crore");
  expect(money(291000, "INR")).toBe("₹2,91,000");
  expect(money(12400, "USD")).toBe("$12,400");
  expect(moneyShort(12400, "USD")).toBe("$12,400");
  expect(moneyShort(1200000, "USD")).toBe("$1.2M");
});
