import Link from "next/link";
import { ArrowUp } from "lucide-react";

import { MAX_TEXT } from "@/lib/chat";

const STARTERS = ["What happened today?", "What could my plan become?", "Why does an RBI rate hike matter?"];

const demoAsking = (q: string): string => `/demo?q=${encodeURIComponent(q)}`;

/**
 * The hero's working piece: the real question box. A plain GET form, so it works before any
 * script loads, and /demo asks the question on arrival.
 */
export function LandingAsk() {
  return (
    <div className="grid gap-3">
      <form action="/demo" method="get" className="rounded-xl border border-line bg-raised transition-colors focus-within:border-line-strong">
        <label htmlFor="landing-q" className="sr-only">Ask the sample profile a question</label>
        <div className="flex items-end gap-2 p-2 pl-4">
          <input
            id="landing-q"
            name="q"
            required
            maxLength={MAX_TEXT}
            autoComplete="off"
            enterKeyHint="send"
            placeholder="Ask the sample profile"
            className="min-h-11 min-w-0 flex-1 bg-transparent text-base text-ink outline-none placeholder:text-ink-3"
          />
          <button type="submit" className="btn btn-primary btn-icon rounded-full" aria-label="Ask in the demo">
            <ArrowUp aria-hidden="true" />
          </button>
        </div>
      </form>
      <ul className="flex flex-wrap gap-2" aria-label="Or start with">
        {STARTERS.map((q) => (
          <li key={q}>
            <Link href={demoAsking(q)} className="chip no-underline" prefetch={false}>{q}</Link>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink-3">Opens a sample profile. No sign-up.</p>
    </div>
  );
}
