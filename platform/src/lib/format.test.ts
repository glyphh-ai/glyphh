import { ago, date, listText, money, plural, usd, usdPerSecond } from './format';

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

  it('writes rates in dollars: to the cent a month, to two figures a second, from numbers or strings', () => {
    expect(usd(8.71)).toBe('$8.71');
    expect(usd('117.00')).toBe('$117');
    expect(usd(0.195)).toBe('$0.20');
    expect(usdPerSecond(8.71 / 2_592_000)).toBe('$0.0000034');
    expect(usdPerSecond('0.0000451')).toBe('$0.000045');
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
});
