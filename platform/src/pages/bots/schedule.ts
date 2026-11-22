import type { Every, Schedule } from '@/api/bots';

/**
 * A bot's schedule in plain words, as the server keeps it (never cron): how often, the time of day in the person's
 * time zone, and what each run is given. The server works out the next run; these are the editor's choices and its
 * one-line summary.
 */
export const EVERY: ReadonlyArray<{ value: Every; label: string }> = [
  { value: 'off', label: 'Off' },
  { value: 'hour', label: 'Every hour' },
  { value: 'day', label: 'Every day' },
  { value: 'weekdays', label: 'Weekdays' },
  { value: 'week', label: 'Every week' },
  { value: 'month', label: 'Every month' },
];
export const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] as const;

/** The person's time zone, as the browser says it. */
export const browserZone = (): string => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';

/** Every time zone the browser knows, with UTC and the one given among them. */
export const zones = (given: string): string[] => {
  const known = Intl.supportedValuesOf('timeZone');
  return [...new Set(['UTC', given, ...known])].sort((a, b) => (a === 'UTC' ? -1 : b === 'UTC' ? 1 : a.localeCompare(b)));
};

/** The bot's schedule to edit: what it keeps, or off at 9:00 in the person's zone; an unused one takes their zone. */
export const scheduleOf = (kept: Schedule | undefined): Schedule => {
  const off = { every: 'off', at: '09:00', weekday: 0, day: 1, timezone: browserZone(), input: '' } as const;
  if (!kept) return { ...off };
  return kept.every === 'off' ? { ...kept, timezone: off.timezone } : { ...kept };
};

/** 09:05 as 9:05. */
export const clock = (at: string) => at.replace(/^0(\d)/, '$1');

/** The schedule in one plain line: `Weekdays at 9:00`. */
export const summary = (s: Schedule): string => {
  const at = clock(s.at);
  switch (s.every) {
    case 'off':
      return 'Off';
    case 'hour':
      return 'Every hour';
    case 'day':
      return `Every day at ${at}`;
    case 'weekdays':
      return `Weekdays at ${at}`;
    case 'week':
      return `Every ${DAYS[s.weekday] ?? 'Monday'} at ${at}`;
    case 'month':
      return `Every month on day ${s.day} at ${at}`;
  }
};

/** What the editor says under the schedule: when it runs, in whose time, and its next run once saved. */
export const sentence = (s: Schedule, next?: string): string => {
  if (s.every === 'off') return 'It runs only when you run it.';
  const when = s.every === 'hour' ? 'Runs every hour, on the hour' : `Runs ${summary(s).replace(/^Every/, 'every').replace(/^Weekdays/, 'on weekdays')}`;
  const zone = s.every === 'hour' ? '' : ` (${s.timezone.replace(/_/g, ' ')} time)`;
  const short = s.every === 'month' && s.day > 28 ? ' In shorter months, on their last day.' : '';
  return `${when}${zone}.${short}${next ? ` Next run ${next}.` : ''}`;
};

/** Two schedules the same. */
export const same = (a: Schedule, b: Schedule) => (Object.keys(a) as (keyof Schedule)[]).every((k) => a[k] === b[k]);
