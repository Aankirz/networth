import "server-only";

import { createHash, createHmac } from "node:crypto";

import { auth } from "@/auth";

// The site vouches for a signed-in visitor to the Python API with a token that lasts a minute,
// signed with NETWORTH_WEB_SECRET (networth/web/session.py checks it). The browser never sends
// a user id; the API only believes this token.

const TOKEN_LIFE_S = 60;

export interface WebVisitor {
  subject: string;
  name: string;
}

export async function signedIn(): Promise<WebVisitor | null> {
  const session = await auth();
  return session?.subject ? { subject: session.subject, name: session.user?.name ?? "" } : null;
}

const b64url = (data: Buffer | string): string => Buffer.from(data).toString("base64url");

/** `v1.<payload>.<mac>`, or null when this server has no secret to sign with. */
export function webToken(visitor: WebVisitor, nowMs: number = Date.now()): string | null {
  const secret = process.env.NETWORTH_WEB_SECRET;
  if (!secret) return null;
  const exp = Math.floor(nowMs / 1000) + TOKEN_LIFE_S;
  const payload = b64url(JSON.stringify({ sub: visitor.subject, name: visitor.name, exp }));
  const mac = createHmac("sha256", secret).update(`v1.${payload}`).digest("base64url");
  return `v1.${payload}.${mac}`;
}

/** Keeps one Google account's saved chats apart from another's in the same browser. */
export function accountKey(visitor: WebVisitor): string {
  return createHash("sha256").update(visitor.subject).digest("hex").slice(0, 16);
}
