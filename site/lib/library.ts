import type { Chat } from "@/lib/chat";

// Past chats live only in this browser's localStorage, never on a server. Storage can be missing
// or full (private windows, blocked site data), so every read and write is allowed to fail and
// the chat still works without it.

const MAX_CHATS = 20;
const MAX_ENTRIES = 40;

const keyOf = (scope: "demo" | "user"): string => `nw-chats:${scope}`;

function isChat(value: unknown): value is Chat {
  const c = value as Chat | null;
  return !!c && typeof c.id === "string" && typeof c.title === "string" && Array.isArray(c.entries);
}

export function loadChats(scope: "demo" | "user"): Chat[] {
  try {
    const raw = localStorage.getItem(keyOf(scope));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isChat) : [];
  } catch {
    return [];
  }
}

/** The list with this chat on top if it has a settled turn, newest first. A turn still waiting is not kept. */
export function withChat(chat: Chat, all: Chat[]): Chat[] {
  const settled = chat.entries.filter((e) => e.outcome.kind !== "waiting").slice(-MAX_ENTRIES);
  const others = all.filter((c) => c.id !== chat.id);
  return settled.length ? [{ ...chat, entries: settled }, ...others].slice(0, MAX_CHATS) : others;
}

export function saveChats(scope: "demo" | "user", chats: Chat[]): void {
  try {
    localStorage.setItem(keyOf(scope), JSON.stringify(chats));
  } catch {
    // Full or blocked storage: the list still holds for this visit.
  }
}

export function forgetChat(scope: "demo" | "user", id: string, all: Chat[]): Chat[] {
  const next = all.filter((c) => c.id !== id);
  saveChats(scope, next);
  return next;
}
