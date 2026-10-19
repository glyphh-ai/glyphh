const locale = 'en-GB';

/** Whole dollars when the amount is round, cents otherwise: $8, $4.50. */
export function money(cents: number, currency = 'usd'): string {
  const value = cents / 100;
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: currency.toUpperCase(),
    currencyDisplay: 'narrowSymbol',
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
  }).format(value);
}

/** A rate in dollars, to the cent: $8.71. The server may send a decimal as a string. */
export function usd(dollars: number | string): string {
  return money(Math.round(Number(dollars) * 100));
}

/** A per-second rate, to two significant figures: $0.0000034. */
export function usdPerSecond(dollars: number | string): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', currencyDisplay: 'narrowSymbol', maximumSignificantDigits: 2 }).format(Number(dollars));
}

/** Names as a sentence: "Pro", "Pro and Team", "Pro, Team and Enterprise". */
export function listText(names: string[]): string {
  return names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`;
}

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** 16 Nov 2026, in UTC so a date reads the same everywhere. */
export function date(iso: string): string {
  const d = new Date(iso);
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** 5 min ago, 3 h ago, 2 days ago, or the date once it is more than a month old. */
export function ago(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, (now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  const days = Math.floor(seconds / 86400);
  if (days < 31) return `${days} ${days === 1 ? 'day' : 'days'} ago`;
  return date(iso);
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count.toLocaleString(locale)} ${count === 1 ? one : many}`;
}

const two = (n: number) => String(n).padStart(2, '0');

/** A moment to the second, in UTC as dates are: 16 Oct 13:58:12. */
export function stamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getUTCDate()} ${months[d.getUTCMonth()]} ${two(d.getUTCHours())}:${two(d.getUTCMinutes())}:${two(d.getUTCSeconds())}`;
}

/** A length of time, to its two largest units: 45 s, 1 min 30 s, 2 h 5 min, 3 days 4 h. */
export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const units: Array<[number, (n: number) => string]> = [
    [86_400, (n) => (n === 1 ? '1 day' : `${n.toLocaleString(locale)} days`)],
    [3_600, (n) => `${n} h`],
    [60, (n) => `${n} min`],
    [1, (n) => `${n} s`],
  ];
  const first = units.findIndex(([size]) => s >= size);
  if (first === -1) return '0 s';
  const [size, text] = units[first]!;
  const parts = [text(Math.floor(s / size))];
  const next = units[first + 1];
  const rest = next ? Math.floor((s % size) / next[0]) : 0;
  if (next && rest > 0) parts.push(next[1](rest));
  return parts.join(' ');
}
