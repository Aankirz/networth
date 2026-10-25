"use client";

import Link from "next/link";
import { MessageSquare, PanelRight, Search, Send, SquarePen, Trash2 } from "lucide-react";

import { SECTIONS, type Section } from "@/components/app/canvas";
import { Mark } from "@/components/mark";
import { ThemeToggle } from "@/components/theme-toggle";
import { BOT_URL, type Chat } from "@/lib/chat";

export interface SidebarProps {
  chats: Chat[];
  current: string;
  hasHoldings: boolean;
  onNew: () => void;
  onSearch: () => void;
  onOpenChat: (chat: Chat) => void;
  onForget: (id: string) => void;
  onSection: (section: Section) => void;
}

const QUICK: Record<Section, string> = {
  news: "News",
  history: "History",
  plan: "My plan",
  range: "My range",
  holdings: "Holdings",
};

export function Sidebar({ chats, current, hasHoldings, onNew, onSearch, onOpenChat, onForget, onSection }: SidebarProps) {
  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-3 py-3">
      <Link href="/" className="flex items-center gap-2 px-2 py-1 text-sm font-semibold no-underline">
        <Mark className="size-5" /> Networth
      </Link>

      <div className="grid gap-0.5">
        <button type="button" className="side-item" onClick={onSearch}>
          <Search aria-hidden="true" /> <span className="mr-auto">Search or ask</span>
          <kbd className="figure text-xs text-ink-3">⌘K</kbd>
        </button>
        <button type="button" className="side-item" onClick={onNew}>
          <SquarePen aria-hidden="true" /> New chat
        </button>
      </div>

      <nav aria-label="Dashboard" className="grid gap-0.5">
        <p className="px-2 pb-1 text-xs text-ink-3">Dashboard</p>
        <button type="button" className="side-item" onClick={() => onSection("news")}>
          <PanelRight aria-hidden="true" /> Open dashboard
        </button>
        {SECTIONS.filter((s) => s.id !== "holdings" || hasHoldings).map((s) => (
          <button key={s.id} type="button" className="side-item" onClick={() => onSection(s.id)}>
            <SectionIcon section={s.id} /> {QUICK[s.id]}
          </button>
        ))}
      </nav>

      <section aria-labelledby="library-title" className="grid min-h-0 gap-0.5">
        <h2 id="library-title" className="px-2 pb-1 text-xs font-normal text-ink-3">Your chats</h2>
        {chats.length === 0 && <p className="px-2 text-xs text-ink-3">Your chats stay in this browser.</p>}
        <ul className="grid gap-0.5">
          {chats.map((chat) => (
            <li key={chat.id} className="group relative">
              <button
                type="button"
                className={`side-item pr-9 ${chat.id === current ? "bg-hover text-ink" : ""}`}
                aria-current={chat.id === current ? "true" : undefined}
                onClick={() => onOpenChat(chat)}
              >
                <MessageSquare aria-hidden="true" /> <span className="truncate">{chat.title || "Untitled"}</span>
              </button>
              <button
                type="button"
                className="absolute top-1/2 right-1 -translate-y-1/2 rounded-sm p-1.5 text-ink-3 opacity-0 group-hover:opacity-100 hover:text-ink focus-visible:opacity-100 max-md:opacity-100"
                aria-label={`Forget "${chat.title || "Untitled"}"`}
                onClick={() => onForget(chat.id)}
              >
                <Trash2 aria-hidden="true" className="size-3.5" />
              </button>
            </li>
          ))}
        </ul>
      </section>

      <div className="mt-auto grid gap-1 pt-2">
        <a href={BOT_URL} rel="noopener" target="_blank" className="side-item no-underline">
          <Send aria-hidden="true" /> Message the bot
        </a>
        <ThemeToggle />
      </div>
    </div>
  );
}

function SectionIcon({ section }: { section: Section }) {
  const Icon = SECTIONS.find((s) => s.id === section)!.icon;
  return <Icon aria-hidden="true" />;
}
