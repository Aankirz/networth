// A monthly SIP, compounded monthly, with the monthly amount raised once a year by the step-up.
// The server sends the starting values; the browser reruns this as sliders move.

export interface SipInput {
  monthly: number;
  returnPct: number;
  years: number;
  stepUpPct: number;
}

export interface SipYear {
  year: number;
  balance: number;
  invested: number;
}

export function project({ monthly, returnPct, years, stepUpPct }: SipInput): SipYear[] {
  const rate = returnPct / 1200;
  const rows: SipYear[] = [{ year: 0, balance: 0, invested: 0 }];
  let [balance, invested, amount] = [0, 0, monthly];
  for (let year = 1; year <= years; year++) {
    for (let month = 0; month < 12; month++) {
      balance = balance * (1 + rate) + amount;
      invested += amount;
    }
    rows.push({ year, balance, invested });
    amount *= 1 + stepUpPct / 100;
  }
  return rows;
}

/** The first year growth is larger than everything put in, or null if it never gets there. */
export function crossover(rows: SipYear[]): number | null {
  return rows.find((r) => r.year > 0 && r.balance - r.invested > r.invested)?.year ?? null;
}
