"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { forgetMe, signOutNow } from "@/app/account-actions";

/** The signed-in avatar: the first letter of the Google display name, never a picture from Google. */
function Initial({ name }: { name: string }) {
  const letter = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <span aria-hidden="true" className="grid size-8 place-items-center rounded-full bg-[var(--accent)] text-sm font-semibold text-[var(--accent-ink)]">
      {letter}
    </span>
  );
}

const ITEM = "flex w-full items-center rounded-md px-3 py-2 text-left text-sm text-ink no-underline hover:bg-hover focus-visible:bg-hover";

export function AccountMenu({ name }: { name: string }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const menu = useId();

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        className="btn btn-ghost btn-icon rounded-full p-0"
        aria-expanded={open}
        aria-controls={menu}
        aria-label={`Account: ${name || "signed in"}`}
        onClick={() => setOpen((o) => !o)}
      >
        <Initial name={name} />
      </button>
      {open && (
        <div id={menu} className="absolute right-0 z-40 mt-2 grid w-56 gap-0.5 rounded-xl border border-line bg-raised p-1.5 shadow-[0_16px_40px_-16px_var(--scrim)]">
          {name && <p className="truncate px-3 pt-1.5 pb-2 text-xs text-ink-3">Signed in as {name}</p>}
          <Link href="/dashboard" className={ITEM} onClick={() => setOpen(false)}>Dashboard</Link>
          <form action={signOutNow}>
            <button type="submit" className={ITEM}>Sign out</button>
          </form>
          <form action={forgetMe} className="border-t border-line pt-0.5">
            <button type="submit" className={ITEM}>Forget me on the web</button>
          </form>
        </div>
      )}
    </div>
  );
}
