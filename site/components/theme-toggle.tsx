"use client";

import { Moon, Sun } from "lucide-react";

const COOKIE = "nw-theme";
const YEAR = 60 * 60 * 24 * 365;

/** Flips between the dark default and light, and remembers it in a cookie so the server renders it with no flash. */
export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  return (
    <button
      type="button"
      className={compact ? "btn btn-ghost btn-icon" : "side-item"}
      aria-label="Switch between light and dark"
      onClick={() => {
        const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
        document.documentElement.dataset.theme = next;
        document.cookie = `${COOKIE}=${next}; path=/; max-age=${YEAR}; samesite=lax; secure`;
      }}
    >
      <Sun aria-hidden="true" className="light:hidden" />
      <Moon aria-hidden="true" className="hidden light:block" />
      {!compact && <span>Light or dark</span>}
    </button>
  );
}
