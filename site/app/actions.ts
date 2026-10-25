"use server";

import { createHash } from "node:crypto";
import { headers } from "next/headers";

import { plausibleToken, postChat, postCommand, type Result, type Scope } from "@/lib/api";
import type { ChatRequest, ChatTurn, CommandName, CommandTurn, Lang } from "@/lib/contract";

const MAX_TEXT = 4096;
const LANGS: ReadonlySet<string> = new Set<Lang>(["en", "hi", "hinglish"]);
const COMMANDS: ReadonlySet<string> = new Set<CommandName>(["brief", "range", "plan", "holdings", "help"]);

export interface AskInput {
  token: string | null;
  text: string;
  lang?: Lang;
  forwarded?: boolean;
}

export interface CommandInput {
  token: string | null;
  name: CommandName;
  lang?: Lang;
}

/** The demo's per-visitor cap keys on this. A hash, so no raw IP leaves the site. */
async function visitor(): Promise<string | null> {
  const h = await headers();
  const ip = h.get("x-real-ip") ?? h.get("x-forwarded-for")?.split(",")[0]?.trim();
  return ip ? createHash("sha256").update(ip).digest("hex").slice(0, 32) : null;
}

/** Anyone can call a server action with any body, so every field is checked here. */
function scopeOf(token: unknown): Scope | null {
  if (token === null) return { kind: "demo" };
  return typeof token === "string" && plausibleToken(token) ? { kind: "user", token } : null;
}

function langOf(lang: unknown): Lang | undefined | false {
  if (lang === undefined) return undefined;
  return typeof lang === "string" && LANGS.has(lang) ? (lang as Lang) : false;
}

function parseAsk(input: unknown): { scope: Scope; request: ChatRequest } | null {
  const i = input as Partial<AskInput> | null;
  if (!i || typeof i.text !== "string" || !i.text.trim()) return null;
  const scope = scopeOf(i.token);
  const lang = langOf(i.lang);
  if (!scope || lang === false) return null;
  if (i.forwarded !== undefined && typeof i.forwarded !== "boolean") return null;
  // Longer text still goes to the server, which answers 413 in the reader's language.
  const text = i.text.length > MAX_TEXT + 1 ? i.text.slice(0, MAX_TEXT + 1) : i.text;
  return { scope, request: { text, ...(lang && { lang }), ...(i.forwarded && { forwarded: true }) } };
}

export async function ask(input: AskInput): Promise<Result<ChatTurn>> {
  const parsed = parseAsk(input);
  if (!parsed) return { ok: false, status: 400, error: null };
  return postChat(parsed.scope, parsed.request, parsed.scope.kind === "demo" ? await visitor() : null);
}

// Until the API serves /command, each command asks the chat the question it stands for.
const ASKS: Record<CommandName, string> = {
  brief: "What happened today?",
  range: "What could my plan become?",
  plan: "What is my plan?",
  holdings: "How are my holdings doing?",
  help: "What can you do?",
};

export async function command(input: CommandInput): Promise<Result<CommandTurn | ChatTurn>> {
  const i = input as Partial<CommandInput> | null;
  const scope = scopeOf(i?.token);
  const lang = langOf(i?.lang);
  if (!i || !scope || lang === false || typeof i.name !== "string" || !COMMANDS.has(i.name)) {
    return { ok: false, status: 400, error: null };
  }
  const name = i.name as CommandName;
  const who = scope.kind === "demo" ? await visitor() : null;
  const result = await postCommand(scope, { name, ...(lang && { lang }) }, who);
  if (result.ok || result.status !== 404 || result.error) return result;
  return postChat(scope, { text: ASKS[name], ...(lang && { lang }) }, who);
}
