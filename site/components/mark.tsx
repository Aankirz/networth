/** The Networth mark: a pencilled tick on a ledger line, drawn once by hand and kept still. */
export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M3.2 17.6c5.6.3 11.9-.2 17.6.1" strokeWidth="1.4" opacity="0.55" />
      <path d="M5.1 11.9c1.2 1.1 2.3 2.4 3.3 3.6 2.9-4.2 6.3-8 10.4-10.9" strokeWidth="2" />
    </svg>
  );
}
