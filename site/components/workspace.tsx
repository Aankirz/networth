import Link from "next/link";
import { notFound } from "next/navigation";

import { Shell } from "@/components/app/shell";
import { Mark } from "@/components/mark";
import { MessageView } from "@/components/message";
import { getDashboard, type Scope } from "@/lib/api";

function Unavailable({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto grid min-h-dvh max-w-xl content-center gap-4 px-4">
      <Mark className="size-8 text-ink-2" />
      {children}
      <p className="text-sm text-ink-3">
        <Link href="/" className="underline">Back to Networth</Link>
      </p>
    </main>
  );
}

/** One page for both routes: the chat is home, and the dashboard opens from it. */
export async function Workspace({ scope }: { scope: Scope }) {
  const result = await getDashboard(scope);
  if (!result.ok && result.status === 404) notFound();
  if (!result.ok) {
    return (
      <Unavailable>
        {result.error ? <MessageView message={result.error.message} /> : <p>Networth can&apos;t load this page right now. Try again in a minute.</p>}
      </Unavailable>
    );
  }
  return <Shell board={result.data} token={scope.kind === "user" ? scope.token : null} />;
}
