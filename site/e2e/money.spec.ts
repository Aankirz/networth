import { expect, test } from "@playwright/test";

import { money, moneyShort, parseAmount, price, signed } from "../lib/money";

// Money follows the user's currency: lakh and crore for rupees, thousands and M for dollars.
test("money is written the way each currency's reader says it", () => {
  expect(moneyShort(291000, "INR")).toBe("₹2.91 lakh");
  expect(moneyShort(12000000, "INR")).toBe("₹1.2 crore");
  expect(money(291000, "INR")).toBe("₹2,91,000");
  expect(money(12400, "USD")).toBe("$12,400");
  expect(moneyShort(12400, "USD")).toBe("$12,400");
  expect(moneyShort(1200000, "USD")).toBe("$1.2M");
});

test("a price keeps its paisa or cents, and an index level has no symbol", () => {
  expect(price(2530, "INR")).toBe("₹2,530.00");
  expect(price(347.73, "USD")).toBe("$347.73");
  expect(price(22600, null)).toBe("22,600.00");
});

test("a server amount reads back as its number, whatever its unit or sign", () => {
  expect(parseAmount("₹3,420.00")).toBe(3420);
  expect(parseAmount("12")).toBe(12);
  expect(parseAmount("₹2.91 lakh")).toBeCloseTo(291000);
  expect(parseAmount("$1.2M")).toBeCloseTo(1_200_000);
  expect(parseAmount("−₹10,680")).toBe(-10680);
  expect(parseAmount("no number")).toBeNull();
});

test("a signed amount uses plus for a gain and the true minus for a loss", () => {
  expect(signed("₹4,000", 4000)).toBe("+₹4,000");
  expect(signed("₹4,000", -4000)).toBe("−₹4,000");
  expect(signed("₹0", 0)).toBe("₹0");
});
