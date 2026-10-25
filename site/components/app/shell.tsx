"use client";

import { useCallback, useEffect, useReducer, useRef, useState, useSyncExternalStore } from "react";
import { Menu, PanelRight, X } from "lucide-react";

import { command as runCommand, ask as askChat } from "@/app/actions";
import { Canvas, type Section } from "@/components/app/canvas";
import { Composer } from "@/components/app/composer";
import { Sidebar } from "@/components/app/sidebar";
import { Thread, WORDS } from "@/components/app/thread";
import { Mark } from "@/components/mark";
import { COMMANDS, MAX_TEXT, announcement, composeText, newChat, reduce, type Action, type Asked, type Chat, type CommandSpec, type Entry, type Outcome } from "@/lib/chat";
import type { ApiError, Card, CommandName, Dashboard, Lang, Mention, Message } from "@/lib/contract";
import { forgetChat, loadChats, saveChats, withChat } from "@/lib/library";

const WIDE = "(min-width: 1280px)";
const PIN_KEY = "nw-canvas-pinned";
const FORWARDED_TIP = "Big news coming for Suzlon tomorrow, insiders are loading up. Share fast!";

type Starter = { label: string } & ({ text: string; forwarded?: boolean } | { command: CommandName });
const STARTERS: Starter[] = [
  { label: "What happened today?", text: "What happened today?" },
  { label: "My brief", command: "brief" },
  { label: "My range", command: "range" },
  { label: "Check a tip", text: FORWARDED_TIP, forwarded: true },
];

function useWide(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const query = matchMedia(WIDE);
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => matchMedia(WIDE).matches,
    () => true,
  );
}

function readPinned(): boolean {
  try {
    return localStorage.getItem(PIN_KEY) === "1";
  } catch {
    return false;
  }
}

type Settled =
  | { ok: true; data: { message: Message; text: string; card: Card } }
  | { ok: false; status: number; error: ApiError | null };

function settle(result: Settled | null): Outcome {
  if (result?.ok) return { kind: "answer", answer: { message: result.data.message, text: result.data.text, card: result.data.card } };
  return { kind: "failed", status: result?.status ?? 0, error: result?.error ?? null };
}

export interface ShellProps {
  board: Dashboard;
  token: string | null;
  /** A question to ask on arrival, from the landing page. */
  ask?: string | null;
}

const ARRIVAL = "arrival";

/** The chat to open with: empty, or already asking the question the visitor brought. */
function opening(ask: string | null): Chat {
  if (!ask) return newChat();
  const asked: Asked = { kind: "text", text: ask.slice(0, MAX_TEXT), chips: [], forwarded: false };
  return reduce(newChat(), { type: "asked", entry: { id: ARRIVAL, asked, outcome: { kind: "waiting" } } });
}

export function Shell({ board, token, ask = null }: ShellProps) {
  const scope = token ? "user" : "demo";
  const [chat, dispatch] = useReducer(reduce, ask, opening);
  const [stored, setStored] = useState<Chat[]>([]);
  const [lang, setLang] = useState<Lang>(board.lang);
  const [drawer, setDrawer] = useState(false);
  const [canvas, setCanvas] = useState<{ open: boolean; focus: Section | null }>({ open: false, focus: null });
  const [pinned, setPinned] = useState(false);
  const wide = useWide();
  const field = useRef<HTMLTextAreaElement>(null);
  const newest = useRef<HTMLLIElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const busy = chat.entries.some((e) => e.outcome.kind === "waiting");
  const docked = canvas.open && pinned && wide;
  const overlay = canvas.open && !docked;
  const last = chat.entries.at(-1);
  const chats = withChat(chat, stored);

  // localStorage only exists in the browser, so the saved chats and the pin arrive after hydration.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reading browser storage once on mount
    setStored(loadChats(scope));
    setPinned(readPinned());
  }, [scope]);

  useEffect(() => {
    if (chat.entries.some((e) => e.outcome.kind !== "waiting")) saveChats(scope, withChat(chat, stored));
  }, [chat, stored, scope]);

  const switchTo = (action: Action) => {
    setStored((all) => withChat(chat, all));
    dispatch(action);
  };

  // The newest turn's top comes into view when it is asked and again when its answer lands.
  const stage = last ? `${last.id}:${last.outcome.kind}` : "";
  useEffect(() => {
    if (!stage) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    newest.current?.scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
  }, [stage]);

  const sheet = useRef<HTMLElement>(null);
  useEffect(() => {
    if (overlay) sheet.current?.querySelector<HTMLElement>("button[aria-label='Close the dashboard']")?.focus();
  }, [overlay]);

  const openCanvas = useCallback((focus: Section | null = null) => {
    opener.current = document.activeElement as HTMLElement | null;
    setDrawer(false);
    setCanvas({ open: true, focus });
  }, []);

  const closeCanvas = useCallback(() => {
    setCanvas({ open: false, focus: null });
    requestAnimationFrame(() => (opener.current ?? field.current)?.focus());
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setDrawer(false);
        field.current?.focus();
      } else if (e.key === "Escape" && overlay) {
        closeCanvas();
      } else if (e.key === "Escape" && drawer) {
        setDrawer(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [overlay, drawer, closeCanvas]);

  const send = useCallback(
    (id: string, asked: Asked) => {
      const call =
        asked.kind === "command"
          ? runCommand({ token, name: asked.name as CommandName, lang })
          : askChat({ token, text: composeText(asked.chips, asked.text), lang, forwarded: asked.forwarded });
      call.catch(() => null).then((result) => dispatch({ type: "settled", id, outcome: settle(result) }));
    },
    [token, lang],
  );

  const run = (asked: Asked, existing?: string) => {
    const id = existing ?? crypto.randomUUID();
    if (existing) dispatch({ type: "settled", id, outcome: { kind: "waiting" } });
    else dispatch({ type: "asked", entry: { id, asked, outcome: { kind: "waiting" } } });
    send(id, asked);
  };

  // The question from the landing page is already on screen as waiting; send it once and drop
  // ?q= so a reload doesn't ask it again.
  const arrived = useRef(false);
  useEffect(() => {
    const first = chat.entries[0];
    if (arrived.current || first?.id !== ARRIVAL || first.outcome.kind !== "waiting") return;
    arrived.current = true;
    history.replaceState(null, "", location.pathname);
    send(first.id, first.asked);
  }, [chat.entries, send]);

  const onCommand = (spec: CommandSpec) => {
    const id = crypto.randomUUID();
    const asked: Asked = { kind: "command", name: spec.name };
    if (spec.run.kind === "server") return run(asked);
    if (spec.run.kind === "canvas") openCanvas();
    const outcome: Outcome = spec.run.kind === "canvas" ? { kind: "opened" } : { kind: "telegram", name: spec.name };
    dispatch({ type: "asked", entry: { id, asked, outcome } });
  };

  const onSend = (typed: string, chips: Mention[], forwarded: boolean) => {
    if (busy) return;
    run({ kind: "text", text: typed.trim(), chips, forwarded });
  };

  const onStarter = (s: Starter) => {
    if ("command" in s) return onCommand(COMMANDS.find((c) => c.name === s.command)!);
    run({ kind: "text", text: s.text, chips: [], forwarded: !!s.forwarded });
  };

  const empty = chat.entries.length === 0;
  const composer = (
    <Composer
      mentions={board.mentions}
      busy={busy}
      lang={lang}
      onLang={setLang}
      onSend={onSend}
      onCommand={onCommand}
      fieldRef={field}
      placeholder={empty ? "Ask about your money, @ to mention, / for commands" : "Ask a follow-up"}
    />
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside
        aria-label="Chats and dashboard"
        className={`w-64 shrink-0 border-r border-line bg-bg max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-40 max-md:w-[min(18rem,85vw)] max-md:transition-transform max-md:duration-200 ${drawer ? "" : "max-md:-translate-x-full max-md:invisible"}`}
        inert={overlay}
      >
        <Sidebar
          chats={chats}
          current={chat.id}
          hasHoldings={!!board.holdings}
          onNew={() => {
            switchTo({ type: "new" });
            setDrawer(false);
            requestAnimationFrame(() => field.current?.focus());
          }}
          onSearch={() => {
            setDrawer(false);
            field.current?.focus();
          }}
          onOpenChat={(c) => {
            switchTo({ type: "open", chat: c });
            setDrawer(false);
          }}
          onForget={(id) => {
            setStored((all) => forgetChat(scope, id, withChat(chat, all)));
            if (id === chat.id) dispatch({ type: "new" });
          }}
          onSection={(s) => openCanvas(s)}
        />
      </aside>
      {drawer && <div className="fixed inset-0 z-30 bg-[var(--scrim)] md:hidden" aria-hidden="true" onClick={() => setDrawer(false)} />}

      <div className="flex min-w-0 flex-1 flex-col" inert={overlay || drawer ? true : undefined}>
        <header className="flex h-13 shrink-0 items-center gap-2 px-3 sm:px-4">
          <button type="button" className="btn btn-ghost btn-icon md:hidden" aria-label="Open chats and dashboard links" aria-expanded={drawer} onClick={() => setDrawer(true)}>
            <Menu aria-hidden="true" />
          </button>
          <p className="flex min-w-0 items-center gap-2 text-sm">
            <span className="truncate font-medium max-sm:hidden">{board.sample ? "Networth" : "Your Networth"}</span>
            {board.sample && <span className="shrink-0 rounded-full border border-line px-2 py-0.5 text-xs text-ink-2">Sample profile</span>}
          </p>
          <button
            type="button"
            className="btn ml-auto"
            aria-expanded={canvas.open}
            onClick={() => (canvas.open ? closeCanvas() : openCanvas())}
          >
            <PanelRight aria-hidden="true" /> Dashboard
          </button>
        </header>

        <main className="relative flex min-h-0 flex-1 flex-col">
          {empty ? (
            <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-4 pb-[12vh]">
              <div className="grid w-full max-w-[44rem] gap-7">
                <div className="grid justify-items-center gap-4 text-center">
                  <Mark className="size-9 text-ink-2" />
                  <h1 className="text-2xl font-semibold tracking-tight sm:text-[2.125rem]">What would you like to know about your money?</h1>
                </div>
                {composer}
                <ul className="flex flex-wrap justify-center gap-2" aria-label="Questions to start with">
                  {STARTERS.map((s) => (
                    <li key={s.label}>
                      <button type="button" className="chip" onClick={() => onStarter(s)}>{s.label}</button>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-y-auto overscroll-contain px-4">
                <div className="mx-auto w-full max-w-[44rem] py-6">
                  <Thread entries={chat.entries} newestRef={newest} onRetry={(e: Entry) => run(e.asked, e.id)} onOpenCanvas={() => openCanvas()} />
                </div>
              </div>
              <div className="shrink-0 px-4 pt-2 pb-4">
                <div className="mx-auto w-full max-w-[44rem]">{composer}</div>
              </div>
            </>
          )}
          <p role="status" aria-live="polite" className="sr-only" data-testid="chat-status">
            {announcement(last, WORDS)}
          </p>
        </main>
      </div>

      {canvas.open && (
        <>
          {overlay && <div className="fixed inset-0 z-40 bg-[var(--scrim)] max-sm:hidden" aria-hidden="true" onClick={closeCanvas} />}
          <aside
            ref={sheet}
            aria-label="Dashboard"
            role={overlay ? "dialog" : undefined}
            aria-modal={overlay ? true : undefined}
            className={
              docked
                ? "w-[min(38rem,42vw)] shrink-0 border-l border-line bg-bg"
                : "canvas-in fixed inset-y-0 right-0 z-50 w-full border-l border-line bg-bg sm:w-[min(40rem,92vw)]"
            }
          >
            <Canvas
              board={board}
              pinned={pinned}
              focus={canvas.focus}
              onPin={(p) => {
                setPinned(p);
                try {
                  localStorage.setItem(PIN_KEY, p ? "1" : "0");
                } catch {
                  // The pin still holds for this visit.
                }
              }}
              onClose={closeCanvas}
            />
          </aside>
        </>
      )}
      {drawer && (
        <button type="button" className="btn btn-ghost btn-icon fixed top-2 right-2 z-50 md:hidden" aria-label="Close the menu" onClick={() => setDrawer(false)}>
          <X aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
