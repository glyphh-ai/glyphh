import { autoSummary, changeLabel, changeText, learnedText, valueText } from './versions';

describe('a version’s changes in words', () => {
  it('names where a change is', () => {
    expect(changeLabel('settings.k')).toEqual({ kind: null, label: 'k' });
    expect(changeLabel('seed')).toEqual({ kind: null, label: 'seed' });
    expect(changeLabel('layers[a].segments[s].roles[color].similarity_weight')).toEqual({ kind: null, label: 'a.s.color similarity_weight' });
    expect(changeLabel('layers[a].segments[s].roles[size]')).toEqual({ kind: 'role', label: 'a.s.size' });
    expect(changeLabel('interactions[cs]')).toEqual({ kind: 'pair', label: 'cs' });
    expect(changeLabel('things[x]')).toEqual({ kind: null, label: 'x' });
  });

  it('writes values short', () => {
    expect([null, undefined, true, false, 3, 'cost'].map(valueText)).toEqual(['none', 'none', 'on', 'off', '3', 'cost']);
    expect(valueText({ good: { bad: 1 } })).toBe('{"good":{"bad":1}}');
    expect(valueText({ long: 'x'.repeat(60) })).toHaveLength(40);
  });

  it('says what a change did', () => {
    expect(changeText({ path: 'settings.k', from: 15, to: 20, restates: false })).toBe('k 15 → 20');
    expect(changeText({ path: 'layers[a].segments[s].roles[size]', from: null, to: { name: 'size' }, restates: true })).toBe('role a.s.size added');
    expect(changeText({ path: 'interactions[cs]', from: {}, to: null, restates: true })).toBe('pair cs taken away');
    expect(changeText({ path: 'output.ask_below', from: null, to: 0.6, restates: false })).toBe('output.ask_below set to 0.6');
    expect(changeText({ path: 'output.ask_below', from: 0.6, to: null, restates: false })).toBe('output.ask_below removed');
  });

  it('sums a version up when no one wrote why', () => {
    const k = { path: 'settings.k', from: 15, to: 20, restates: false };
    expect(autoSummary({ changes: null, new_store: false })).toBe('First version');
    expect(autoSummary({ changes: [], new_store: false })).toBe('No change to the spec or settings');
    expect(autoSummary({ changes: [k], new_store: true })).toBe('Re-encoded: k 15 → 20');
    expect(autoSummary({ changes: [k, k, k, k, k], new_store: false })).toBe('k 15 → 20; k 15 → 20; k 15 → 20 and 2 more');
  });

  it('says what a store learned', () => {
    expect(learnedText({ roles: { a: 1 }, words: { t: 1 }, pairs: [], tau: 0.5 })).toBe('1 role weighed, 1 word, 0 pairs, tau 0.5');
    expect(learnedText({ tau: 1.2 })).toBe('tau 1.2');
    expect(learnedText({})).toBe('Nothing learned');
  });
});
