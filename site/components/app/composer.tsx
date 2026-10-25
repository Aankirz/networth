"use client";

import { useId, useState, type KeyboardEvent, type RefObject } from "react";
import { ArrowUp, AtSign, Forward, ImageIcon, Plus, Slash, X } from "lucide-react";

import { BOT_URL, COMMANDS, MAX_TEXT, findCommand, type CommandSpec } from "@/lib/chat";
import type { Lang, Mention } from "@/lib/contract";

const WARN_AT = MAX_TEXT - 400;
const LANGS: { value: Lang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "hinglish", label: "Hinglish" },
];
const KIND_WORD: Record<Mention["kind"], string> = {
  news: "This month's news",
  story: "A story",
  history: "A history count",
  plan: "Your plan",
  range: "Your plan's range",
  holdings: "Your holdings",
  holding: "A holding",
};

type Picker =
  | { kind: "mention"; query: string; start: number; options: Mention[] }
  | { kind: "command"; query: string; options: CommandSpec[] };

/** Which picker the text before the caret opens, if any: `@word` anywhere, `/word` as the whole message. */
function pickerFor(draft: string, caret: number, mentions: Mention[], chips: Mention[]): Picker | null {
  const before = draft.slice(0, caret);
  const at = before.match(/(^|\s)@([^\s@]*)$/);
  if (at) {
    const query = at[2].toLowerCase();
    const options = mentions
      .filter((m) => !chips.some((c) => c.id === m.id))
      .filter((m) => !query || m.label.toLowerCase().includes(query) || m.kind.startsWith(query));
    return { kind: "mention", query, start: before.length - at[2].length - 1, options: options.slice(0, 8) };
  }
  const slash = draft.match(/^\/(\S*)$/);
  if (slash && caret === draft.length) {
    const query = slash[1].toLowerCase();
    return { kind: "command", query, options: COMMANDS.filter((c) => c.name.startsWith(query)) };
  }
  return null;
}

export interface ComposerProps {
  mentions: Mention[];
  busy: boolean;
  lang: Lang;
  onLang: (lang: Lang) => void;
  onSend: (typed: string, chips: Mention[], forwarded: boolean) => void;
  onCommand: (spec: CommandSpec) => void;
  fieldRef: RefObject<HTMLTextAreaElement | null>;
  placeholder: string;
}

export function Composer({ mentions, busy, lang, onLang, onSend, onCommand, fieldRef, placeholder }: ComposerProps) {
  const [draft, setDraft] = useState("");
  const [chips, setChips] = useState<Mention[]>([]);
  const [forwarded, setForwarded] = useState(false);
  const [picker, setPicker] = useState<Picker | null>(null);
  const [active, setActive] = useState(0);
  const [menu, setMenu] = useState(false);
  const [note, setNote] = useState<"screenshot" | null>(null);
  const field = fieldRef;
  const ids = { field: useId(), list: useId(), menu: useId(), lang: useId() };
  const tooLong = draft.length > MAX_TEXT;
  const canSend = !busy && !tooLong && (draft.trim().length > 0 || chips.length > 0);

  const refresh = (text: string, caret: number, nextChips = chips) => {
    const next = pickerFor(text, caret, mentions, nextChips);
    setPicker(next);
    setActive(0);
  };

  const reset = () => {
    setDraft("");
    setChips([]);
    setForwarded(false);
    setPicker(null);
  };

  const pick = (index: number) => {
    if (!picker) return;
    if (picker.kind === "command") {
      const spec = picker.options[index];
      if (!spec) return;
      reset();
      onCommand(spec);
      return;
    }
    const mention = picker.options[index];
    if (!mention) return;
    const caret = field.current?.selectionStart ?? draft.length;
    const text = (draft.slice(0, picker.start) + draft.slice(caret)).replace(/\s{2,}/g, " ");
    const nextChips = [...chips, mention];
    setChips(nextChips);
    setDraft(text);
    setPicker(null);
    requestAnimationFrame(() => {
      field.current?.focus();
      field.current?.setSelectionRange(picker.start, picker.start);
    });
  };

  const submit = () => {
    if (!canSend) return;
    const command = chips.length === 0 ? findCommand(draft) : null;
    if (command) {
      reset();
      onCommand(command);
      return;
    }
    onSend(draft, chips, forwarded);
    reset();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
    const open = picker && picker.options.length > 0;
    if (open && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + picker.options.length) % picker.options.length);
      return;
    }
    if (open && (e.key === "Enter" || e.key === "Tab")) {
      e.preventDefault();
      pick(active);
      return;
    }
    if (picker && e.key === "Escape") {
      e.preventDefault();
      setPicker(null);
      return;
    }
    if (e.key === "Backspace" && chips.length && field.current?.selectionStart === 0 && field.current.selectionEnd === 0) {
      setChips(chips.slice(0, -1));
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const listOpen = !!picker;
  const optionId = (i: number) => `${ids.list}-${i}`;

  return (
    <form
      className="relative"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      {listOpen && (
        <div className="absolute inset-x-0 bottom-full z-20 mb-2 overflow-hidden rounded-lg border border-line bg-raised shadow-2xl">
          <p className="flex items-center gap-1.5 px-3 pt-2.5 pb-1 text-xs text-ink-3">
            {picker.kind === "mention" ? <AtSign aria-hidden="true" className="size-3.5" /> : <Slash aria-hidden="true" className="size-3.5" />}
            {picker.kind === "mention" ? "Point at something on your dashboard" : "Commands, the same as in the Telegram bot"}
          </p>
          <ul id={ids.list} role="listbox" aria-label={picker.kind === "mention" ? "Things to mention" : "Commands"} className="max-h-72 overflow-y-auto p-1">
            {picker.options.length === 0 && <li className="px-3 py-2 text-sm text-ink-3">Nothing matches</li>}
            {picker.options.map((option, i) => {
              const selected = i === active;
              const [head, tail] =
                picker.kind === "mention"
                  ? [`@${(option as Mention).label}`, KIND_WORD[(option as Mention).kind]]
                  : [`/${(option as CommandSpec).name}`, (option as CommandSpec).hint];
              return (
                <li
                  key={head}
                  id={optionId(i)}
                  role="option"
                  aria-selected={selected}
                  className={`flex cursor-pointer items-baseline justify-between gap-3 rounded-md px-3 py-2 text-sm ${selected ? "bg-hover text-ink" : "text-ink-2"}`}
                  onMouseDown={(e) => e.preventDefault()}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(i)}
                >
                  <span className="min-w-0 truncate font-medium">{head}</span>
                  <span className="shrink-0 text-xs text-ink-3">{tail}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="rounded-xl border border-line bg-raised transition-colors focus-within:border-line-strong">
        {(chips.length > 0 || forwarded) && (
          <ul className="flex flex-wrap gap-1.5 px-3 pt-3" aria-label="Attached to this question">
            {forwarded && (
              <li className="mark flex items-center gap-1 text-sm">
                <Forward aria-hidden="true" className="size-3.5" /> Forwarded to me
                <button type="button" className="ml-0.5 rounded-sm text-ink-3 hover:text-ink" aria-label="Not forwarded" onClick={() => setForwarded(false)}>
                  <X aria-hidden="true" className="size-3.5" />
                </button>
              </li>
            )}
            {chips.map((chip) => (
              <li key={chip.id} className="mark flex max-w-full items-center gap-1 text-sm" data-chip={chip.kind}>
                <span className="truncate">@{chip.label}</span>
                <button type="button" className="ml-0.5 shrink-0 rounded-sm text-ink-3 hover:text-ink" aria-label={`Remove @${chip.label}`} onClick={() => setChips(chips.filter((c) => c.id !== chip.id))}>
                  <X aria-hidden="true" className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <label htmlFor={ids.field} className="sr-only">Your question</label>
        <textarea
          id={ids.field}
          ref={field}
          value={draft}
          rows={1}
          placeholder={forwarded ? "Paste what you were sent" : placeholder}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={listOpen}
          aria-controls={listOpen ? ids.list : undefined}
          aria-activedescendant={listOpen && picker.options.length ? optionId(active) : undefined}
          aria-describedby={tooLong ? `${ids.field}-long` : undefined}
          className="field-sizing-content block max-h-60 min-h-[3.25rem] w-full resize-none bg-transparent px-4 pt-3.5 pb-2 text-base leading-relaxed text-ink outline-none placeholder:text-ink-3"
          onChange={(e) => {
            setDraft(e.target.value);
            refresh(e.target.value, e.target.selectionStart);
          }}
          onSelect={(e) => refresh(e.currentTarget.value, e.currentTarget.selectionStart)}
          onKeyDown={onKeyDown}
          onBlur={() => setPicker(null)}
        />

        <div className="flex items-center gap-1 px-2 pb-2">
          <div className="relative">
            <button
              type="button"
              className="btn btn-ghost btn-icon rounded-full"
              aria-label="Add to your question"
              aria-expanded={menu}
              aria-controls={ids.menu}
              onClick={() => setMenu((m) => !m)}
            >
              <Plus aria-hidden="true" />
            </button>
            {menu && (
              <div id={ids.menu} className="absolute bottom-full left-0 z-20 mb-2 grid w-64 gap-0.5 rounded-lg border border-line bg-raised p-1 shadow-2xl">
                <button
                  type="button"
                  className="flex items-start gap-2.5 rounded-md px-2.5 py-2 text-left text-sm hover:bg-hover"
                  onClick={() => {
                    setForwarded(true);
                    setMenu(false);
                    field.current?.focus();
                  }}
                >
                  <Forward aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-2" />
                  <span>Paste a link or a tip<span className="block text-xs text-ink-3">Something you were sent, checked and explained</span></span>
                </button>
                <button
                  type="button"
                  className="flex items-start gap-2.5 rounded-md px-2.5 py-2 text-left text-sm hover:bg-hover"
                  onClick={() => {
                    setNote("screenshot");
                    setMenu(false);
                  }}
                >
                  <ImageIcon aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-2" />
                  <span>Attach a screenshot<span className="block text-xs text-ink-3">Explained in plain words, in the bot</span></span>
                </button>
                <button
                  type="button"
                  className="flex items-start gap-2.5 rounded-md px-2.5 py-2 text-left text-sm hover:bg-hover"
                  onClick={() => {
                    setDraft((d) => (d.endsWith("@") ? d : `${d}${d && !d.endsWith(" ") ? " " : ""}@`));
                    setMenu(false);
                    requestAnimationFrame(() => {
                      const el = field.current;
                      if (!el) return;
                      el.focus();
                      el.setSelectionRange(el.value.length, el.value.length);
                      refresh(el.value, el.value.length);
                    });
                  }}
                >
                  <AtSign aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-2" />
                  <span>Mention your dashboard<span className="block text-xs text-ink-3">Your plan, range, news or holdings</span></span>
                </button>
              </div>
            )}
          </div>

          <label htmlFor={ids.lang} className="ml-auto flex items-center gap-1 text-xs text-ink-3">
            <span className="hidden sm:inline">Reply in</span>
            <select
              id={ids.lang}
              value={lang}
              onChange={(e) => onLang(e.target.value as Lang)}
              className="cursor-pointer rounded-md bg-transparent px-1.5 py-1 text-xs text-ink-2 hover:bg-hover hover:text-ink"
            >
              {LANGS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </label>
          <button type="submit" className="btn btn-primary btn-icon rounded-full" disabled={!canSend} aria-label="Send">
            <ArrowUp aria-hidden="true" />
          </button>
        </div>
      </div>

      {tooLong && (
        <p id={`${ids.field}-long`} role="alert" className="mt-2 px-1 text-sm text-ink-2">
          {/* The server's own TOO_LONG words, shown before the send so nothing is lost. */}
          That&apos;s longer than one message can be. A shorter piece works.{" "}
          <span className="figure text-ink-3">{draft.length.toLocaleString("en-IN")} / {MAX_TEXT.toLocaleString("en-IN")}</span>
        </p>
      )}
      {!tooLong && draft.length > WARN_AT && (
        <p className="mt-2 px-1 text-xs text-ink-3">
          <span className="figure">{draft.length.toLocaleString("en-IN")} / {MAX_TEXT.toLocaleString("en-IN")}</span>
        </p>
      )}
      {note === "screenshot" && (
        <p className="mt-2 flex items-start justify-between gap-3 px-1 text-sm text-ink-2" role="status">
          <span>
            Screenshots are read in the Telegram bot for now.{" "}
            <a href={BOT_URL} rel="noopener" target="_blank" className="underline">Send it there</a>, and the answer comes back in plain words.
          </span>
          <button type="button" className="shrink-0 text-ink-3 hover:text-ink" aria-label="Dismiss" onClick={() => setNote(null)}>
            <X aria-hidden="true" className="size-4" />
          </button>
        </p>
      )}
    </form>
  );
}
