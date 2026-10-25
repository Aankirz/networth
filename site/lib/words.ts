/** Card labels end with the footer; the footer is shown once per answer, so it comes off here. */
export function withoutFooter(label: string | null | undefined, footer: string): string | null {
  if (!label) return null;
  const trimmed = label.endsWith(footer) ? label.slice(0, -footer.length).trim() : label;
  return trimmed || null;
}
