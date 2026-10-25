"use client";

import dynamic from "next/dynamic";

// A2UI's core reaches for HTMLElement when it loads, so the surface renders in the browser only.
// The skeleton holds the card's height so nothing jumps when it arrives.
export const AnswerSurface = dynamic(() => import("@/components/a2ui/a2ui-answer").then((m) => m.A2uiAnswer), {
  ssr: false,
  loading: () => <div className="h-[34rem] animate-pulse rounded-xl bg-hover" aria-label="Drawing the answer" />,
});
