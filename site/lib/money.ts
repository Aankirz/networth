// Money in the user's own currency. Every card carries a `currency` (ISO 4217, from the profile);
// nothing on the site writes a currency symbol of its own.

const LOCALE: Record<string, string> = { INR: "en-IN", USD: "en-US" };
const localeOf = (currency: string): string => LOCALE[currency] ?? "en-US";

function format(amount: number, currency: string, maxDigits: number): string {
  return new Intl.NumberFormat(localeOf(currency), {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: maxDigits,
  }).format(amount);
}

/** The whole amount: ₹2,91,000 or $12,400. */
export function money(amount: number, currency: string): string {
  return format(Math.round(amount), currency, 0);
}

/** A big amount the way its reader says it: ₹2.91 lakh, ₹1.2 crore, $1.2M. */
export function moneyShort(amount: number, currency: string): string {
  if (currency === "INR") {
    if (Math.abs(amount) >= 1e7) return `${format(amount / 1e7, currency, 2)} crore`;
    if (Math.abs(amount) >= 1e5) return `${format(amount / 1e5, currency, 2)} lakh`;
    return money(amount, currency);
  }
  if (Math.abs(amount) < 1e6) return money(amount, currency);
  return new Intl.NumberFormat(localeOf(currency), { style: "currency", currency, notation: "compact", maximumFractionDigits: 1 }).format(amount);
}

/** A share price or an index level to the paisa or cent: ₹2,530.00, $347.73, or 22,600.00 bare. */
export function price(amount: number, currency: string | null): string {
  const style = currency ? { style: "currency" as const, currency } : {};
  return new Intl.NumberFormat(localeOf(currency ?? ""), { ...style, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
}

const MINUS = "−";

/** "+" in front of a gain, the true minus sign in front of a loss, as the server writes them. */
export function signed(text: string, amount: number): string {
  return `${amount < 0 ? MINUS : amount > 0 ? "+" : ""}${text.replace(/^[−-]/, "")}`;
}

const UNITS: Record<string, number> = { lakh: 1e5, crore: 1e7, k: 1e3, m: 1e6, b: 1e9 };
const AMOUNT = /([\d,]+(?:\.\d+)?)\s*(lakh|crore|k|m|b)?(?![a-z])/i;

/** The number in a server amount ("₹3,420.00", "$1.2M", "−₹10,680", "12"), or null. */
export function parseAmount(text: string): number | null {
  const m = AMOUNT.exec(text);
  if (!m) return null;
  const n = Number.parseFloat(m[1].replace(/,/g, "")) * (m[2] ? UNITS[m[2].toLowerCase()] : 1);
  if (!Number.isFinite(n)) return null;
  return /^\s*[−-]/.test(text) ? -n : n;
}
