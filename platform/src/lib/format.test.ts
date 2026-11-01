import { ago, date, duration, listText, money, plural, stamp } from './format';

describe('format', () => {
  it.each([
    [800, '$8'],
    [450, '$4.50'],
    [207, '$2.07'],
    [0, '$0'],
  ])('money(%i) is %s', (cents, text) => expect(money(cents)).toBe(text));

  it('writes dates as 16 Nov 2026, the same in every time zone', () => {
    expect(date('2026-11-16T00:00:00Z')).toBe('16 Nov 2026');
    expect(date('2026-09-20T23:30:00Z')).toBe('20 Sep 2026');
  });

  it('lists names as a sentence', () => {
    expect(listText([])).toBe('');
    expect(listText(['Pro'])).toBe('Pro');
    expect(listText(['Pro', 'Team'])).toBe('Pro and Team');
    expect(listText(['Pro', 'Team', 'Enterprise'])).toBe('Pro, Team and Enterprise');
  });

  it('says how long ago, then the date after a month', () => {
    const now = new Date('2026-10-16T12:00:00Z');
    expect(ago('2026-10-16T11:59:30Z', now)).toBe('just now');
    expect(ago('2026-10-16T11:40:00Z', now)).toBe('20 min ago');
    expect(ago('2026-10-16T06:00:00Z', now)).toBe('6 h ago');
    expect(ago('2026-10-15T12:00:00Z', now)).toBe('1 day ago');
    expect(ago('2026-10-10T12:00:00Z', now)).toBe('6 days ago');
    expect(ago('2026-08-01T12:00:00Z', now)).toBe('1 Aug 2026');
  });

  it('pluralises', () => {
    expect(plural(1, 'machine')).toBe('1 machine');
    expect(plural(3, 'machine')).toBe('3 machines');
    expect(plural(10_000, 'precedent')).toBe('10,000 precedents');
  });

  it('writes a moment to the second in UTC, and passes on what is not a date', () => {
    expect(stamp('2026-10-16T13:58:12Z')).toBe('16 Oct 13:58:12');
    expect(stamp('2026-01-02T03:04:05.678Z')).toBe('2 Jan 03:04:05');
    expect(stamp('soon')).toBe('soon');
  });

  it.each([
    [0, '0 s'],
    [45, '45 s'],
    [90, '1 min 30 s'],
    [3_600, '1 h'],
    [5_400, '1 h 30 min'],
    [3_661, '1 h 1 min'],
    [86_400 + 4 * 3_600, '1 day 4 h'],
    [3 * 86_400 + 59, '3 days'],
  ])('duration(%i) is %s', (seconds, text) => expect(duration(seconds)).toBe(text));
});
