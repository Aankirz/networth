"use client";

import { useId, useReducer, useRef, useTransition } from "react";
import { ArrowUp, Check, Copy } from "lucide-react";

import { ask } from "@/app/actions";
import { AnswerCard } from "@/components/answer-card";
import { Footer, MessageView } from "@/components/message";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ApiError, ChatTurn, Lang } from "@/lib/contract";

const MAX_TEXT = 4096;
const STARTERS: { text: string; forwarded?: boolean }[] = [
  { text: "What happened today?" },
  { text: "Explain OFS in plain words" },
  { text: "What could my plan become?" },
  { text: "Big news coming for Suzlon tomorrow, insiders are loading up. Share fast!", forwarded: true },
];
const LANGS: { value: Lang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "hinglish", label: "Hinglish" },
];

type Outcome =
  | { kind: "waiting" }
  | { kind: "answer"; turn: ChatTurn }
  | { kind: "error"; error: ApiError | null };

interface Entry {
  id: number;
  question: string;
  forwarded: boolean;
  outcome: Outcome;
}

interface State {
  entries: Entry[];
  draft: string;
  forwarded: boolean;
  lang: Lang;
}

type Action =
  | { type: "draft"; text: string }
  | { type: "forwarded"; on: boolean }
  | { type: "lang"; lang: Lang }
  | { type: "sent"; id: number; question: string; forwarded: boolean }
  | { type: "settled"; id: number; outcome: Outcome };

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case "draft":
      return { ...state, draft: action.text };
    case "forwarded":
      return { ...state, forwarded: action.on };
    case "lang":
      return { ...state, lang: action.lang };
    case "sent":
      return {
        ...state,
        draft: "",
        forwarded: false,
        entries: [
          ...state.entries,
          { id: action.id, question: action.question, forwarded: action.forwarded, outcome: { kind: "waiting" } },
        ],
      };
    case "settled":
      return {
        ...state,
        entries: state.entries.map((e) => (e.id === action.id ? { ...e, outcome: action.outcome } : e)),
      };
  }
}

function Thinking() {
  return (
    <div className="flex items-center gap-3 text-graphite">
      <svg width="96" height="12" viewBox="0 0 96 12" aria-hidden="true">
        <path d="M2 7 Q 24 3, 48 6 T 94 5" className="pencil-draw" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" filter="url(#pencil)" />
      </svg>
      <span className="text-note">Checking</span>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useReducer((_: boolean, next: boolean) => next, false);
  return (
    <Button
      variant="ghost"
      size="sm"
      className="opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 max-sm:opacity-100"
      onClick={() => {
        navigator.clipboard.writeText(text).then(
          () => setCopied(true),
          () => setCopied(false),
        );
      }}
    >
      {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function Failure({ error }: { error: ApiError | null }) {
  if (error) {
    return (
      <div className="grid gap-3 rounded-lg bg-sheet p-4" role="alert" data-error={error.error}>
        <MessageView message={error.message} />
        <Footer text={error.message.footer} />
      </div>
    );
  }
  return (
    <p className="rounded-lg bg-sheet p-4" role="alert">
      Networth didn&apos;t answer just now. Check your connection and ask again.
    </p>
  );
}

function EntryView({ entry }: { entry: Entry }) {
  const { outcome } = entry;
  return (
    <li className="arrive group grid gap-3">
      <div className="grid justify-items-end gap-1">
        {entry.forwarded && <span className="text-note text-graphite">Forwarded to me</span>}
        <p className="max-w-[85%] whitespace-pre-line rounded-lg bg-paper px-3 py-2">{entry.question}</p>
      </div>
      {outcome.kind === "waiting" && <Thinking />}
      {outcome.kind === "answer" && (
        <div className="grid gap-1">
          <AnswerCard turn={outcome.turn} />
          <div className="flex justify-end">
            <CopyButton text={outcome.turn.text} />
          </div>
        </div>
      )}
      {outcome.kind === "error" && <Failure error={outcome.error} />}
    </li>
  );
}

export interface ChatProps {
  token: string | null;
  lang: Lang;
}

export function Chat({ token, lang }: ChatProps) {
  const [state, dispatch] = useReducer(reduce, { entries: [], draft: "", forwarded: false, lang });
  const [pending, startTransition] = useTransition();
  const nextId = useRef(1);
  const ids = { field: useId(), forwarded: useId(), lang: useId() };

  const send = (text: string, forwarded: boolean) => {
    const question = text.trim();
    if (!question || pending) return;
    const id = nextId.current++;
    dispatch({ type: "sent", id, question, forwarded });
    startTransition(async () => {
      const result = await ask({ token, text: question, lang: state.lang, forwarded }).catch(() => null);
      const outcome: Outcome = result?.ok
        ? { kind: "answer", turn: result.data }
        : { kind: "error", error: result?.error ?? null };
      dispatch({ type: "settled", id, outcome });
    });
  };

  return (
    <section aria-labelledby="chat-title" className="flex min-h-[70dvh] flex-col gap-4 lg:h-full lg:min-h-0">
      <header className="grid gap-1">
        <h2 id="chat-title" className="text-head">Ask</h2>
        <p className="text-note text-graphite">Anything you would send the Networth bot on Telegram. The answer is the same.</p>
      </header>

      <ol aria-live="polite" aria-relevant="additions text" className="grid flex-1 content-start gap-6 overflow-y-auto overscroll-contain">
        {state.entries.map((entry) => (
          <EntryView key={entry.id} entry={entry} />
        ))}
      </ol>

      {state.entries.length === 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Questions to start with">
          {STARTERS.map((s) => (
            <li key={s.text}>
              <Button variant="outline" className="h-auto max-w-full whitespace-normal py-2 text-left" onClick={() => send(s.text, !!s.forwarded)}>
                {s.forwarded ? `Forwarded: ${s.text}` : s.text}
              </Button>
            </li>
          ))}
        </ul>
      )}

      <form
        className="grid gap-2 pt-1"
        onSubmit={(e) => {
          e.preventDefault();
          send(state.draft, state.forwarded);
        }}
      >
        <label htmlFor={ids.field} className="sr-only">Your question</label>
        <div className="flex items-end gap-2">
          <Textarea
            id={ids.field}
            value={state.draft}
            maxLength={MAX_TEXT}
            rows={2}
            placeholder="Ask, or paste what you were sent"
            className="max-h-48 min-h-11 resize-none bg-paper text-base"
            onChange={(e) => dispatch({ type: "draft", text: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                send(state.draft, state.forwarded);
              }
            }}
          />
          <Button type="submit" size="icon-lg" className="size-11" disabled={pending || !state.draft.trim()} aria-label="Send">
            <ArrowUp aria-hidden="true" />
          </Button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 text-note">
          <label htmlFor={ids.forwarded} className="flex items-center gap-2">
            <Switch id={ids.forwarded} checked={state.forwarded} onCheckedChange={(on) => dispatch({ type: "forwarded", on })} />
            This was forwarded to me
          </label>
          <label htmlFor={ids.lang} className="flex items-center gap-2 text-graphite">
            Reply in
            <select
              id={ids.lang}
              value={state.lang}
              onChange={(e) => dispatch({ type: "lang", lang: e.target.value as Lang })}
              className="rounded-md border border-rule bg-paper px-2 py-1 text-ink"
            >
              {LANGS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </label>
        </div>
      </form>
    </section>
  );
}
