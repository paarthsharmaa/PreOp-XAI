export const fixed = (value: number, digits = 3) => value.toFixed(digits);

export const signed = (value: number, digits = 3) => `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(digits)}`;

export const count = (value: number | string) => (typeof value === "number" ? value.toLocaleString("en-US") : value);

export const percent = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;

/** Risks span several orders of magnitude, so small values keep two significant digits. */
export function risk(value: number): string {
  const pct = value * 100;
  if (pct < 0.01) return "<0.01%";
  if (pct < 1) return `${pct.toFixed(2)}%`;
  if (pct < 10) return `${pct.toFixed(1)}%`;
  return `${pct.toFixed(0)}%`;
}

export const interval = (lo: number, hi: number, digits = 3) => `${lo.toFixed(digits)} to ${hi.toFixed(digits)}`;

export const scientific = (value: number) => value.toExponential(1).replace("e-", "e−");

export const logit = (p: number) => Math.log(p / (1 - p));

export const ROMAN = ["", "I", "II", "III", "IV", "V"];
