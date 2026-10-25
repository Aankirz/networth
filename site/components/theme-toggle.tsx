"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

const COOKIE = "nw-theme";
const YEAR = 60 * 60 * 24 * 365;

function current(): "light" | "dark" {
  const picked = document.documentElement.dataset.theme;
  if (picked === "light" || picked === "dark") return picked;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/** Flips the theme and remembers it in a cookie, so the server renders it with no flash. */
export function ThemeToggle() {
  return (
    <Button
      variant="ghost"
      size="icon-lg"
      className="size-11"
      aria-label="Switch between light and dark"
      onClick={() => {
        const next = current() === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        document.cookie = `${COOKIE}=${next}; path=/; max-age=${YEAR}; samesite=lax; secure`;
      }}
    >
      <Sun aria-hidden="true" className="hidden dark:block" />
      <Moon aria-hidden="true" className="dark:hidden" />
    </Button>
  );
}
