"use client";

import { useActionState } from "react";

import { linkWithCode, type LinkState } from "@/app/account-actions";

const START: LinkState = { error: null };

/** The /weblink code box. The server checks the code; a refusal is shown in its own words. */
export function LinkForm() {
  const [state, action, pending] = useActionState(linkWithCode, START);
  return (
    <form action={action} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <label htmlFor="weblink-code" className="text-sm font-medium text-ink">Code from the bot</label>
      <div className="flex gap-2">
        <input
          id="weblink-code"
          name="code"
          required
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={7}
          placeholder="123456"
          aria-describedby={state.error ? "weblink-error" : undefined}
          aria-invalid={state.error ? true : undefined}
          className="figure h-11 min-w-0 flex-1 rounded-lg border border-line bg-raised px-3 text-lg tracking-[0.2em] text-ink outline-none placeholder:text-ink-3 focus:border-line-strong"
        />
        <button type="submit" className="btn btn-primary h-11 px-5" disabled={pending}>
          {pending ? "Checking…" : "Link"}
        </button>
      </div>
      <p id="weblink-error" role="alert" className="min-h-5 text-sm text-ink">{state.error}</p>
    </form>
  );
}
