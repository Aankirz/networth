import Link from "next/link";
import { Suspense } from "react";
import { notFound } from "next/navigation";

import { Shell } from "@/components/app/shell";
import { MarketStrip, MarketStripLoading } from "@/components/market-strip";
import { Mark } from "@/components/mark";
import { MessageView } from "@/components/message";
import { getDashboard, type Scope } from "@/lib/api";
import { ME_TOKEN } from "@/lib/chat";
import { accountKey } from "@/lib/session";

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

function tokenOf(scope: Scope): string | null {
  if (scope.kind === "me") return ME_TOKEN;
  return scope.kind === "user" ? scope.token : null;
}

/** One page for every route: the chat is home, and the dashboard opens from it. */
export async function Workspace({ scope, ask = null }: { scope: Scope; ask?: string | null }) {
  const result = await getDashboard(scope);
  if (!result.ok && result.status === 404) notFound();
  if (!result.ok) {
    return (
      <Unavailable>
        {result.error ? <MessageView message={result.error.message} /> : <p>Networth can&apos;t load this page right now. Try again in a minute.</p>}
      </Unavailable>
    );
  }
  const account = scope.kind === "me" ? accountKey(scope.visitor) : null;
  const strip = (
    <Suspense fallback={<MarketStripLoading />}>
      <MarketStrip scope={scope} />
    </Suspense>
  );
  return <Shell board={result.data} token={tokenOf(scope)} ask={ask} account={account} dashboardFirst={scope.kind === "me"} strip={strip} />;
}
