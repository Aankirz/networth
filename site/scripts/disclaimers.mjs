// The owner removed every "not advice" style disclaimer and the answer footer, in every language.
// check-build.mjs scans the site's source and build with this list; e2e/no-disclaimer.spec.ts
// scans every reply fixture and the rendered pages.
export const DISCLAIMERS = [
  /not (financial )?advice/i,
  /advice nahi/i,
  /सलाह नहीं/u,
  /your call\b/i,
  /won'?t say yes or no/i,
  /haan ya na/i,
  /is your choice/i,
  /stays your choice/i,
  /aapki pasand/i,
  /आपकी पसंद/u,
  /faisla aapka/i,
];
