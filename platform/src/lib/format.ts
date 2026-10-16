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

/** Seconds as whole hours, rounded down: 43200 → 12. */
export function hours(seconds: number): number {
  return Math.floor(seconds / 3600);
}

export function plural(count: number, one: string, many = `${one}s`): string {
  return `${count.toLocaleString(locale)} ${count === 1 ? one : many}`;
}
