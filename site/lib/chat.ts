import type { ApiError, Card, CommandName, Mention, Message } from "@/lib/contract";

export const MAX_TEXT = 4096;
export const BOT_URL = "https://t.me/networth_professor_bot";

/** What `/` can run. Server commands answer exactly as Telegram does; the rest are handled here. */
export type CommandRun =
  | { kind: "server"; name: CommandName }
  | { kind: "canvas" }
  | { kind: "telegram" };

export interface CommandSpec {
  name: string;
  hint: string;
  run: CommandRun;
}

export const COMMANDS: readonly CommandSpec[] = [
  { name: "brief", hint: "This month's brief", run: { kind: "server", name: "brief" } },
  { name: "range", hint: "What your plan could become", run: { kind: "server", name: "range" } },
  { name: "plan", hint: "Your plan, as you set it", run: { kind: "server", name: "plan" } },
  { name: "holdings", hint: "What you hold", run: { kind: "server", name: "holdings" } },
  { name: "dashboard", hint: "Open the dashboard", run: { kind: "canvas" } },
  { name: "help", hint: "What Networth can do", run: { kind: "server", name: "help" } },
];

/** Commands that change a Telegram chat, so the web points to the bot instead of running them. */
const TELEGRAM_ONLY = new Set(["start", "stop", "pause", "resume", "link", "link_broker", "sendto", "watch", "watches", "unwatch"]);

export function findCommand(text: string): CommandSpec | null {
  const name = text.trim().split(/\s+/)[0]?.replace(/^\//, "").split("@")[0]?.toLowerCase() ?? "";
  if (!text.trim().startsWith("/") || !name) return null;
  const known = COMMANDS.find((c) => c.name === name);
  if (known) return known;
  return { name, hint: "", run: { kind: "telegram" } };
}

export const isTelegramOnly = (name: string): boolean => TELEGRAM_ONLY.has(name);

/** The plain text a question with mention chips sends: each chip's own server text, then the typed words. */
export function composeText(chips: readonly Mention[], typed: string): string {
  return [...chips.map((c) => c.text), typed.trim()].filter(Boolean).join(" ");
}

export interface Answer {
  message: Message;
  text: string;
  card: Card;
}

export type Asked =
  | { kind: "text"; text: string; chips: Mention[]; forwarded: boolean }
  | { kind: "command"; name: string };

export type Outcome =
  | { kind: "waiting" }
  | { kind: "answer"; answer: Answer }
  | { kind: "failed"; status: number; error: ApiError | null }
  | { kind: "telegram"; name: string }
  | { kind: "opened" };

export interface Entry {
  id: string;
  asked: Asked;
  outcome: Outcome;
}

export interface Chat {
  id: string;
  title: string;
  updated: number;
  entries: Entry[];
}

export type Action =
  | { type: "asked"; entry: Entry }
  | { type: "settled"; id: string; outcome: Outcome }
  | { type: "open"; chat: Chat }
  | { type: "new" };

export const newChat = (): Chat => ({ id: crypto.randomUUID(), title: "", updated: Date.now(), entries: [] });

export function titleOf(asked: Asked): string {
  if (asked.kind === "command") return COMMANDS.find((c) => c.name === asked.name)?.hint || `/${asked.name}`;
  const words = asked.chips.map((c) => `@${c.label}`).concat(asked.text ? [asked.text] : []).join(" ");
  return words.length > 60 ? `${words.slice(0, 57)}…` : words;
}

export function reduce(chat: Chat, action: Action): Chat {
  switch (action.type) {
    case "asked":
      return {
        ...chat,
        title: chat.title || titleOf(action.entry.asked),
        updated: Date.now(),
        entries: [...chat.entries, action.entry],
      };
    case "settled":
      return {
        ...chat,
        updated: Date.now(),
        entries: chat.entries.map((e) => (e.id === action.id ? { ...e, outcome: action.outcome } : e)),
      };
    case "open":
      return action.chat;
    case "new":
      return newChat();
  }
}

/** What a screen reader hears for the newest turn: the server's plain text, never the whole card. */
export function announcement(entry: Entry | undefined, words: { thinking: string; unreachable: string; telegram: (n: string) => string; opened: string }): string {
  if (!entry) return "";
  const { outcome } = entry;
  switch (outcome.kind) {
    case "waiting":
      return words.thinking;
    case "answer":
      return outcome.answer.text;
    case "failed":
      return outcome.error ? plainOf(outcome.error.message) : words.unreachable;
    case "telegram":
      return words.telegram(outcome.name);
    case "opened":
      return words.opened;
  }
}

export function plainOf(message: Message): string {
  return [message.title, message.body.map((b) => (b.kind === "text" ? b.text : b.label)).join("")].filter(Boolean).join("\n");
}
