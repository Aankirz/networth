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
