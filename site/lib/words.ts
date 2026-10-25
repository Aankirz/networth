/** Card labels may still end with the server's old footer line; it is never shown, so it comes off here. */
export function withoutFooter(label: string | null | undefined, footer: string): string | null {
  if (!label) return null;
  const trimmed = footer && label.endsWith(footer) ? label.slice(0, -footer.length).trim() : label;
  return trimmed || null;
}
