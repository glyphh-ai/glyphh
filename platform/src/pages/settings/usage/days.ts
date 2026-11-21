import type { SeriesDay, TokenDay } from '@/api/types';

const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY = 86_400_000;

/** "2026-11-03" as "3 Nov". */
export function dayText(day: string): string {
  const d = new Date(`${day}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? day : `${d.getUTCDate()} ${months[d.getUTCMonth()]}`;
}

export type Range = '7' | '30' | 'month';

export const ranges: ReadonlyArray<{ value: Range; label: string }> = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: 'month', label: 'This month' },
];

/** The days a range covers, today's included: this month's are its days so far, UTC. */
export function rangeDays(range: Range, now: Date = new Date()): number {
  return range === 'month' ? now.getUTCDate() : Number(range);
}

/**
 * The days a chart runs over, oldest first: the series' own when the server sent it (its days are the server's),
 * else the last n days to today, UTC.
 */
export function axisDays(series: SeriesDay[] | undefined, n: number, now: Date = new Date()): string[] {
  if (series && series.length > 0) return series.map((d) => d.day);
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Array.from({ length: n }, (_, i) => new Date(today - (n - 1 - i) * DAY).toISOString().slice(0, 10));
}

export type TokenTotals = { input: number[]; output: number[]; charged: number[] };

/** Each day's input and output tokens and charges (in cents), of one model or of all ('all'); a day with none is 0. */
export function tokensOn(days: string[], rows: TokenDay[], model = 'all'): TokenTotals {
  const at = new Map(days.map((day, i) => [day, i]));
  const totals: TokenTotals = { input: days.map(() => 0), output: days.map(() => 0), charged: days.map(() => 0) };
  for (const row of rows) {
    const i = at.get(row.day);
    if (i === undefined || (model !== 'all' && row.model !== model)) continue;
    totals.input[i]! += row.input_tokens;
    totals.output[i]! += row.output_tokens;
    totals.charged[i]! += row.charged_cents;
  }
  return totals;
}

/** One series field on the axis' days; a day the series lacks is 0. */
export function field(days: string[], series: SeriesDay[] | undefined, key: 'reads' | 'decides' | 'bot_runs' | 'connections'): number[] {
  const by = new Map((series ?? []).map((d) => [d.day, d[key]]));
  return days.map((day) => by.get(day) ?? 0);
}

export const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);
