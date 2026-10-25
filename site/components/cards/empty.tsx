/** A server note where there is nothing to draw yet. */
export function EmptyNote({ note }: { note: string }) {
  return <p className="max-w-[60ch] text-sm text-ink-3">{note}</p>;
}
