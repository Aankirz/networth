import "server-only";

import type { ApiError, ChatRequest, ChatTurn, Dashboard, Message } from "@/lib/contract";

// The one place the site talks to the Python server. NETWORTH_API_URL is a server-only
// variable: it is never read in a client component and never prefixed NEXT_PUBLIC_.

export type Scope = { kind: "demo" } | { kind: "user"; token: string };

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; error: ApiError | null };

const DASHBOARD_TIMEOUT_MS = 15_000;
const CHAT_TIMEOUT_MS = 60_000;
const TOKEN = /^[A-Za-z0-9_-]+\.\d+\.[a-f0-9]+$/;

function base(): string | null {
  const url = process.env.NETWORTH_API_URL?.trim().replace(/\/+$/, "");
  return url ? url : null;
}

/** A token that cannot be ours never leaves this server. */
export function plausibleToken(token: string): boolean {
  return token.length <= 200 && TOKEN.test(token);
}

function path(scope: Scope, route: "dashboard" | "chat"): string {
  return scope.kind === "demo"
    ? `/api/demo/${route}`
    : `/api/u/${encodeURIComponent(scope.token)}/${route}`;
}

function isMessage(value: unknown): value is Message {
  const m = value as Message | null;
  return !!m && typeof m.title === "string" && Array.isArray(m.body) && typeof m.footer === "string";
}

function asError(body: unknown): ApiError | null {
  const e = body as ApiError | null;
  return e && typeof e.error === "string" && isMessage(e.message) ? e : null;
}

async function call<T>(
  scope: Scope,
  route: "dashboard" | "chat",
  init: RequestInit,
  timeout: number,
  valid: (body: unknown) => body is T,
): Promise<Result<T>> {
  const root = base();
  if (!root) return { ok: false, status: 503, error: null };
  try {
    const response = await fetch(`${root}${path(scope, route)}`, {
      ...init,
      cache: "no-store",
      signal: AbortSignal.timeout(timeout),
    });
    const body: unknown = await response.json().catch(() => null);
    if (response.ok && valid(body)) return { ok: true, data: body };
    return { ok: false, status: response.ok ? 502 : response.status, error: asError(body) };
  } catch {
    return { ok: false, status: 504, error: null };
  }
}

function isDashboard(body: unknown): body is Dashboard {
  const d = body as Dashboard | null;
  return !!d && typeof d.sample === "boolean" && !!d.profile && !!d.news && !!d.plan_range;
}

function isTurn(body: unknown): body is ChatTurn {
  const t = body as ChatTurn | null;
  return !!t && typeof t.trace_id === "string" && isMessage(t.message) && !!t.card;
}

export function getDashboard(scope: Scope): Promise<Result<Dashboard>> {
  return call(scope, "dashboard", { method: "GET" }, DASHBOARD_TIMEOUT_MS, isDashboard);
}

export function postChat(
  scope: Scope,
  request: ChatRequest,
  visitor: string | null,
): Promise<Result<ChatTurn>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (visitor) headers["X-Networth-Visitor"] = visitor;
  return call(
    scope,
    "chat",
    { method: "POST", headers, body: JSON.stringify(request) },
    CHAT_TIMEOUT_MS,
    isTurn,
  );
}
