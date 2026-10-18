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
