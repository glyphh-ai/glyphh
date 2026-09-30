/**
 * Python-compatible text: json.dumps separators and escaping, round()
 * semantics, and code-point ordering. The kernel stores and prints the
 * same bytes the Python kernel does, so either can read the other's files
 * and hook output compares equal.
 */

/** Python's str ordering: by code point, not UTF-16 unit. */
export function cmpCodePoints(a: string, b: string): number {
  const ia = a[Symbol.iterator]();
  const ib = b[Symbol.iterator]();
  for (;;) {
    const x = ia.next();
    const y = ib.next();
    if (x.done || y.done) return x.done === y.done ? 0 : x.done ? -1 : 1;
    const cx = x.value.codePointAt(0)!;
    const cy = y.value.codePointAt(0)!;
    if (cx !== cy) return cx < cy ? -1 : 1;
  }
}

function pyString(s: string, ensureAscii: boolean): string {
  const out = JSON.stringify(s);
  if (!ensureAscii) return out;
  let r = "";
  for (let i = 0; i < out.length; i++) {
    const c = out.charCodeAt(i);
    r += c > 0x7e ? "\\u" + c.toString(16).padStart(4, "0") : out[i];
  }
  return r;
}

/** json.dumps(value, sort_keys=?, ensure_ascii=?) with Python's default
 *  ", " / ": " separators. Numbers use JS formatting (1.0 prints as 1). */
export function pyDumps(value: unknown, opts: { sortKeys?: boolean; ensureAscii?: boolean } = {}): string {
  const ea = opts.ensureAscii ?? true;
  const go = (v: unknown): string => {
    if (v === null || v === undefined) return "null";
    if (typeof v === "string") return pyString(v, ea);
    if (typeof v === "number") return Number.isFinite(v) ? String(v) : v > 0 ? "Infinity" : v < 0 ? "-Infinity" : "NaN";
    if (typeof v === "boolean") return v ? "true" : "false";
    if (Array.isArray(v)) return "[" + v.map(go).join(", ") + "]";
    const entries = Object.entries(v as Record<string, unknown>);
    if (opts.sortKeys) entries.sort(([a], [b]) => cmpCodePoints(a, b));
    return "{" + entries.map(([k, x]) => pyString(k, ea) + ": " + go(x)).join(", ") + "}";
  };
  return go(value);
}

/** Python's round(x, n): round-half-even on the EXACT binary value. */
export function pyRound(x: number, n: number): number {
  if (!Number.isFinite(x)) return x;
  const neg = x < 0;
  const exact = Math.abs(x).toFixed(100); // exact decimal expansion
  const [intPart, frac] = exact.split(".");
  const keep = frac.slice(0, n);
  const rest = frac.slice(n);
  let digits = (intPart + keep).split("").map(Number);
  const first = Number(rest[0] ?? "0");
  const tail = rest.slice(1).replace(/0+$/, "");
  const last = digits[digits.length - 1] ?? 0;
  const up = first > 5 || (first === 5 && (tail.length > 0 || last % 2 === 1));
  if (up) {
    let i = digits.length - 1;
    while (i >= 0) {
      if (digits[i] === 9) { digits[i] = 0; i--; } else { digits[i]++; break; }
    }
    if (i < 0) digits = [1, ...digits];
  }
  const s = digits.join("");
  const whole = s.slice(0, s.length - n) || "0";
  const value = Number(n > 0 ? `${whole}.${s.slice(s.length - n)}` : whole);
  return neg ? -value : value;
}
