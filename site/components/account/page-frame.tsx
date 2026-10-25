import Link from "next/link";
import type { ReactNode } from "react";

import { AccountButton } from "@/components/account/account-button";
import { Mark } from "@/components/mark";
import { ThemeToggle } from "@/components/theme-toggle";

/** The small pages around sign-in: the site's header, one centred column, the privacy link. */
export function PageFrame({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh grid-cols-[minmax(0,1fr)] grid-rows-[auto_1fr_auto]">
      <header className="border-b border-line">
        <nav aria-label="Main" className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
          <Link href="/" className="mr-auto flex items-center gap-2 text-sm font-semibold no-underline">
            <Mark className="size-5" /> Networth
          </Link>
          <ThemeToggle compact />
          <AccountButton />
        </nav>
      </header>
      <main className="mx-auto grid w-full max-w-[560px] grid-cols-[minmax(0,1fr)] content-center gap-6 px-4 py-16 [overflow-wrap:anywhere]">{children}</main>
      <footer className="border-t border-line px-4 py-8 text-center text-sm text-ink-3">
        <Link href="/privacy" className="underline">Privacy</Link>
      </footer>
    </div>
  );
}
