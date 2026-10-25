"use client";

import { useEffect, useRef, type ReactNode } from "react";

const FIRST_MS = 700;
const TYPING_MS = 1100;
const READ_MS = 1500;
const HOLD_MS = 6000;

/**
 * Plays a mock the way the real thing happens: each `[data-at]` child arrives in turn, a reply
 * from the bot is preceded by "typing…" (`data-bot`), and after a pause it starts over. It plays
 * only while on screen. Under reduced motion, or without script, the whole exchange just shows.
 * A child's `data-wait` overrides how long to read it before the next one.
 */
export function Playback({ children, className, label }: { children: ReactNode; className?: string; label: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const items = [...root.querySelectorAll<HTMLElement>("[data-at]")];
    let shown = 0;
    let timer: number | undefined;
    const show = (n: number) => items.forEach((el, i) => el.toggleAttribute("data-off", i >= n));
    const next = () => {
      root.removeAttribute("data-typing");
      if (shown >= items.length) {
        shown = 0;
        show(0);
        timer = window.setTimeout(next, FIRST_MS);
        return;
      }
      const item = items[shown];
      if (item.hasAttribute("data-bot") && !item.hasAttribute("data-typed")) {
        item.setAttribute("data-typed", "");
        root.setAttribute("data-typing", "");
        timer = window.setTimeout(next, TYPING_MS);
        return;
      }
      item.removeAttribute("data-typed");
      show(++shown);
      const wait = shown >= items.length ? HOLD_MS : Number(item.dataset.wait ?? READ_MS);
      timer = window.setTimeout(next, wait);
    };
    const watch = new IntersectionObserver(([entry]) => {
      window.clearTimeout(timer);
      if (!entry.isIntersecting) return;
      if (!root.hasAttribute("data-play")) {
        root.setAttribute("data-play", "");
        show(0);
      }
      timer = window.setTimeout(next, FIRST_MS);
    }, { rootMargin: "0px 0px 15% 0px" });
    watch.observe(root);
    return () => {
      watch.disconnect();
      window.clearTimeout(timer);
    };
  }, []);
  return (
    <div ref={ref} className={className} role="group" aria-label={label}>
      {children}
    </div>
  );
}
