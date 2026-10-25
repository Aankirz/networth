"use server";

import { createHash } from "node:crypto";
import { headers } from "next/headers";

import { plausibleToken, postChat, type Result } from "@/lib/api";
import type { ChatRequest, ChatTurn, Lang } from "@/lib/contract";

const MAX_TEXT = 4096;
const LANGS: ReadonlySet<string> = new Set<Lang>(["en", "hi", "hinglish"]);

export interface AskInput {
  token: string | null;
  text: string;
  lang?: Lang;
  forwarded?: boolean;
}

/** The demo's per-visitor cap keys on this. A hash, so no raw IP leaves the site. */
async function visitor(): Promise<string | null> {
  const h = await headers();
  const ip = h.get("x-real-ip") ?? h.get("x-forwarded-for")?.split(",")[0]?.trim();
  return ip ? createHash("sha256").update(ip).digest("hex").slice(0, 32) : null;
}

/** Anyone can call a server action with any body, so every field is checked here. */
function parse(input: unknown): { token: string | null; request: ChatRequest } | null {
  const i = input as Partial<AskInput> | null;
  if (!i || typeof i.text !== "string" || !i.text.trim()) return null;
  if (i.token !== null && (typeof i.token !== "string" || !plausibleToken(i.token))) return null;
  if (i.lang !== undefined && !LANGS.has(i.lang)) return null;
  if (i.forwarded !== undefined && typeof i.forwarded !== "boolean") return null;
  // Longer text still goes to the server, which answers 413 in the reader's language.
  const text = i.text.length > MAX_TEXT + 1 ? i.text.slice(0, MAX_TEXT + 1) : i.text;
  return {
    token: i.token,
    request: { text, ...(i.lang && { lang: i.lang }), ...(i.forwarded && { forwarded: true }) },
  };
}

export async function ask(input: AskInput): Promise<Result<ChatTurn>> {
  const parsed = parse(input);
  if (!parsed) return { ok: false, status: 400, error: null };
  const scope = parsed.token ? { kind: "user" as const, token: parsed.token } : { kind: "demo" as const };
  return postChat(scope, parsed.request, scope.kind === "demo" ? await visitor() : null);
}
