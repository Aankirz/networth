/** The one #pencil filter: a drawn edge for counts, the invested line and empty states. */
export function PencilDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" className="absolute">
      <filter id="pencil" x="-5%" y="-20%" width="110%" height="140%">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" />
        <feDisplacementMap in="SourceGraphic" scale="1.2" />
      </filter>
    </svg>
  );
}

/** Ledger lines beside a server note when there is nothing to count yet. */
export function EmptyLedger({ note }: { note: string }) {
  return (
    <div className="flex items-start gap-4">
      <svg width="56" height="40" viewBox="0 0 56 40" aria-hidden="true" className="shrink-0 text-graphite">
        <g filter="url(#pencil)" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" fill="none">
          <path d="M2 8h52M2 20h52M2 32h34" />
          <path d="M14 2v36" opacity="0.5" />
        </g>
      </svg>
      <p className="max-w-[60ch] text-graphite">{note}</p>
    </div>
  );
}
