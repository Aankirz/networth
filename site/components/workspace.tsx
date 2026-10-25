import { notFound } from "next/navigation";

import { Chat } from "@/components/chat";
import { Ledger } from "@/components/ledger";
import { PencilDefs } from "@/components/pencil";
import { ThemeToggle } from "@/components/theme-toggle";
import { getDashboard, type Scope } from "@/lib/api";
import { MessageView } from "@/components/message";

function Unreachable() {
  return (
    <main className="mx-auto grid min-h-dvh max-w-xl content-center gap-3 px-4">
      <h1 className="text-display">Networth</h1>
      <p>Networth can&apos;t load this page right now. Try again in a minute.</p>
    </main>
  );
}

/** One page for both routes. The demo puts the chat first on a phone; a user's own page puts their numbers first. */
export async function Workspace({ scope }: { scope: Scope }) {
  const result = await getDashboard(scope);
  if (!result.ok && result.status === 404) notFound();
  if (!result.ok) {
    return result.error ? (
      <main className="mx-auto grid min-h-dvh max-w-xl content-center gap-3 px-4">
        <MessageView message={result.error.message} />
      </main>
    ) : (
      <Unreachable />
    );
  }
  const board = result.data;
  const chatFirst = board.sample;
  const token = scope.kind === "user" ? scope.token : null;
  return (
    <>
      <PencilDefs />
      <div className="mx-auto flex min-h-dvh max-w-[90rem] flex-col">
        <nav aria-label="Networth" className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 sm:px-6">
          <div className="flex min-w-0 items-baseline gap-3">
            <span className="font-display text-head">Networth</span>
            {board.sample && <span className="whitespace-nowrap rounded-md border border-rule px-2 py-0.5 text-note text-graphite">Sample profile</span>}
          </div>
          <div className="flex items-center gap-1">
            <a href={chatFirst ? "#ledger" : "#ask"} className="whitespace-nowrap px-2 text-note lg:hidden">
              {chatFirst ? "The plan" : "Ask"}
            </a>
            <ThemeToggle />
          </div>
        </nav>
        <main className="grid flex-1 gap-8 px-4 pb-6 sm:px-6 lg:grid-cols-[minmax(0,58fr)_minmax(0,42fr)] lg:gap-10">
          <div id="ledger" className={`min-w-0 py-2 ${chatFirst ? "order-2 lg:order-1" : ""}`}>
            <Ledger board={board} />
          </div>
          <div id="ask" className={`min-w-0 ${chatFirst ? "order-1 lg:order-2" : ""}`}>
            <div className="rounded-xl bg-sheet p-4 sm:p-5 lg:sticky lg:top-4 lg:h-[calc(100dvh-5.5rem)]">
              <Chat token={token} lang={board.lang} />
            </div>
          </div>
        </main>
      </div>
    </>
  );
}
