import { weekdays } from '@/test/bots';
import { browserZone, clock, scheduleOf, sentence, summary, zones } from './schedule';

// The schedule's words. Choosing it (in the bot editor, under Advanced, and the composer's Schedule pill) and where a
// bot runs are tested with the Bots shell (shell/BotsShell.test.tsx).
describe('a bot’s schedule, in plain words', () => {
  it('says each schedule in one line, in the person’s time', () => {
    const s = weekdays();
    expect(summary({ ...s, every: 'off' })).toBe('Off');
    expect(summary({ ...s, every: 'hour' })).toBe('Every hour');
    expect(summary({ ...s, every: 'day', at: '07:05' })).toBe('Every day at 7:05');
    expect(summary(s)).toBe('Weekdays at 9:00');
    expect(summary({ ...s, every: 'week', weekday: 4, at: '17:30' })).toBe('Every Friday at 17:30');
    expect(summary({ ...s, every: 'month', day: 15 })).toBe('Every month on day 15 at 9:00');
    expect(sentence(s, 'Mon 9:00')).toBe('Runs on weekdays at 9:00 (America/Chicago time). Next run Mon 9:00.');
    expect(sentence({ ...s, every: 'hour' })).toBe('Runs every hour, on the hour.');
    expect(sentence({ ...s, every: 'month', day: 31, timezone: 'America/New_York' })).toBe(
      'Runs every month on day 31 at 9:00 (America/New York time). In shorter months, on their last day.',
    );
    expect(sentence({ ...s, every: 'off' })).toBe('It runs only when you run it.');
    expect(clock('10:00')).toBe('10:00');
  });

  it('starts off in the browser’s time zone, and keeps a saved one', () => {
    expect(scheduleOf(undefined)).toEqual({ every: 'off', at: '09:00', weekday: 0, day: 1, timezone: browserZone(), input: '' });
    expect(scheduleOf({ ...weekdays(), every: 'off', timezone: 'UTC' }).timezone).toBe(browserZone());
    expect(scheduleOf(weekdays()).timezone).toBe('America/Chicago');
    const listed = zones('Mars/Olympus');
    expect(listed[0]).toBe('UTC');
    expect(listed).toContain('Mars/Olympus');
    expect(listed).toContain('Europe/London');
  });
});
