import type { BrowserContext } from "@playwright/test";
import { encode } from "next-auth/jwt";

// Test-only secrets, set on the e2e servers by playwright.config.ts. Never the real ones.
export const E2E_AUTH_SECRET = "e2e-auth-secret-not-a-real-one-0123456789";
export const E2E_WEB_SECRET = "e2e-web-secret-not-a-real-one-0123456789";
const COOKIE = "authjs.session-token";

/** Signs the browser in as a Google account without Google, by writing the Auth.js session
 * cookie the way Auth.js would after its callback. */
export async function signInAs(context: BrowserContext, google: string, name = "Ana", secret = E2E_AUTH_SECRET) {
  const value = await encode({ token: { sub: crypto.randomUUID(), name, google }, secret, salt: COOKIE });
  await context.addCookies([{ name: COOKIE, value, domain: "127.0.0.1", path: "/", httpOnly: true, sameSite: "Lax" }]);
}
