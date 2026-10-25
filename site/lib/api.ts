import "server-only";

import type { ApiError, ChatRequest, ChatTurn, CommandRequest, CommandTurn, Dashboard, Message, TrackRecord } from "@/lib/contract";
import { webToken, type WebVisitor } from "@/lib/session";

// The one place the site talks to the Python server. NETWORTH_API_URL is a server-only
// variable: it is never read in a client component and never prefixed NEXT_PUBLIC_.

export type Scope = { kind: "demo" } | { kind: "user"; token: string } | { kind: "me"; visitor: WebVisitor };

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

type Route = "dashboard" | "chat" | "command";

function path(scope: Scope, route: Route): string {
  if (scope.kind === "me") return `/api/web/${route}`;
  return scope.kind === "demo"
    ? `/api/demo/${route}`
    : `/api/u/${encodeURIComponent(scope.token)}/${route}`;
}

/** A signed-in visitor's request carries a fresh signed token; null when it can't be signed. */
function signedHeaders(scope: Scope): Record<string, string> | null {
  if (scope.kind !== "me") return {};
  const token = webToken(scope.visitor);
  return token ? { Authorization: `Bearer ${token}` } : null;
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
  url: string,
  init: RequestInit,
  timeout: number,
  valid: (body: unknown) => body is T,
): Promise<Result<T>> {
  const root = base();
  if (!root) return { ok: false, status: 503, error: null };
  try {
    const response = await fetch(`${root}${url}`, {
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

const UNSIGNED: Result<never> = { ok: false, status: 503, error: null };

export async function getDashboard(scope: Scope): Promise<Result<Dashboard>> {
  const headers = signedHeaders(scope);
  if (!headers) return UNSIGNED;
  return call(path(scope, "dashboard"), { method: "GET", headers }, DASHBOARD_TIMEOUT_MS, isDashboard);
}

export async function postChat(
  scope: Scope,
  request: ChatRequest,
  visitor: string | null,
): Promise<Result<ChatTurn>> {
  const init = post(request, visitor, scope);
  return init ? call(path(scope, "chat"), init, CHAT_TIMEOUT_MS, isTurn) : UNSIGNED;
}

function post(body: object, visitor: string | null, scope: Scope): RequestInit | null {
  const signed = signedHeaders(scope);
  if (!signed) return null;
  const headers: Record<string, string> = { "Content-Type": "application/json", ...signed };
  if (visitor) headers["X-Networth-Visitor"] = visitor;
  return { method: "POST", headers, body: JSON.stringify(body) };
}

function isCommandTurn(body: unknown): body is CommandTurn {
  const t = body as CommandTurn | null;
  return !!t && typeof t.command === "string" && isMessage(t.message) && !!t.card;
}

export async function postCommand(
  scope: Scope,
  request: CommandRequest,
  visitor: string | null,
): Promise<Result<CommandTurn>> {
  const init = post(request, visitor, scope);
  return init ? call(path(scope, "command"), init, CHAT_TIMEOUT_MS, isCommandTurn) : UNSIGNED;
}

function isTrackRecord(body: unknown): body is TrackRecord {
  const t = body as TrackRecord | null;
  return !!t && Array.isArray(t.stats) && (t.tested === null || Array.isArray(t.tested));
}

export function getTrackRecord(): Promise<Result<TrackRecord>> {
  return call("/api/track-record", { method: "GET" }, DASHBOARD_TIMEOUT_MS, isTrackRecord);
}

// Signed in with Google -----------------------------------------------------------------------

export interface WebAccount {
  linked: boolean;
  name: string;
}

function isAccount(body: unknown): body is WebAccount {
  const a = body as WebAccount | null;
  return !!a && typeof a.linked === "boolean";
}

function accountCall(visitor: WebVisitor, route: "me" | "link" | "forget", body?: object): Promise<Result<WebAccount>> {
  const signed = signedHeaders({ kind: "me", visitor });
  if (!signed) return Promise.resolve(UNSIGNED);
  const init: RequestInit = body
    ? { method: "POST", headers: { "Content-Type": "application/json", ...signed }, body: JSON.stringify(body) }
    : { method: route === "me" ? "GET" : "POST", headers: signed };
  return call(`/api/web/${route}`, init, DASHBOARD_TIMEOUT_MS, isAccount);
}

export const getAccount = (visitor: WebVisitor) => accountCall(visitor, "me");
export const linkAccount = (visitor: WebVisitor, code: string) => accountCall(visitor, "link", { code });
export const forgetAccount = (visitor: WebVisitor) => accountCall(visitor, "forget");
