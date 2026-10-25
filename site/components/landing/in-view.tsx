"use client";

import { useEffect, useRef, type ReactNode } from "react";

/**
 * Marks its block `data-inview` the first time it scrolls into view, so CSS can play an entrance
 * or a pencil draw. Only a block that starts below the fold is held back first, so nothing on the
 * first screen flickers, and without script everything simply shows.
 */
export function InView({ children, className, as: Tag = "div" }: { children: ReactNode; className?: string; as?: "div" | "ol" | "ul" }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || el.getBoundingClientRect().top < window.innerHeight) return;
    el.setAttribute("data-armed", "");
    const watch = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        el.setAttribute("data-inview", "");
        watch.disconnect();
      },
      { rootMargin: "0px 0px -12% 0px" },
    );
    watch.observe(el);
    return () => watch.disconnect();
  }, []);
  return (
    <Tag ref={ref as never} className={className}>
      {children}
    </Tag>
  );
}
