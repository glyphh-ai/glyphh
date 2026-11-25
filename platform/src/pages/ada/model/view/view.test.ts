import type { Spec } from '@/api/ada';
import { modelMap } from '@/test/ada';
import { cloud, colourOutput, decodeBits, findPoint, legendOf, nearestOnScreen, neighbourhood, OTHER, rolesOfCase, UNGRADED, valueText } from './glyphs';
import { Layout, layoutRadius, restLength, seeded } from './layout';

describe('the 3D view’s glyphs', () => {
  it('reads a glyph’s bits, first bit highest, and lays them in the old viewer’s cube', () => {
    expect([...decodeBits(btoa('\xa0\x01'), 16)]).toEqual([1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]);
    const points = cloud(Uint8Array.from([1, 0, 0, 0, 0, 0, 0, 1]), 1);
    expect(points).toHaveLength(6); // two bits set, x y z each, in a cube of side 2
    expect([...points.slice(0, 3)]).toEqual([-1.5, -1.5, -1.5]);
  });

  it('colours by the default output, else the first named one, the most common first, the rest Other', () => {
    const spec = { name: 's', layers: [] } as Spec;
    expect(colourOutput(spec)).toBeNull();
    expect(colourOutput({ ...spec, outputs: { team: {}, urgent: {} } })).toBe('team');
    expect(colourOutput({ ...spec, output: {}, outputs: { team: {} } })).toBeNull();
    const map = modelMap(null);
    const many = { ...map, points: [...map.points, ...'abcdef'.split('').map((o) => ({ id: o, outcome: o, outcomes: {}, bits: null }))] };
    const { legend, colourOf, group } = legendOf(many, null, ['s1', 's2', 's3', 's4', 's5'], 'other', 'none');
    expect(legend.map((l) => [l.name, l.count, l.colour])).toEqual([
      ['billing', 2, 's1'],
      ['a', 1, 's2'],
      ['auth', 1, 's3'],
      ['b', 1, 's4'],
      ['c', 1, 's5'],
      [OTHER, 3, 'other'],
      [UNGRADED, 1, 'none'],
    ]);
    expect([colourOf('f'), colourOf(null), colourOf('billing')]).toEqual(['other', 'none', 's1']);
    expect([group('billing'), group(null)]).toEqual([0, 8]);
    const named = { ...map, points: [{ id: 'x', outcome: null, outcomes: { team: 'tech' }, bits: null }] };
    expect(legendOf(named, 'team', ['s1'], 'o', 'n').legend).toEqual([{ name: 'tech', count: 1, colour: 's1' }]);
  });

  it('finds the neighbourhood, a point by id, and the point under a click', () => {
    const { edges, points } = modelMap(null);
    expect([...neighbourhood(edges, () => true, 1)].sort()).toEqual([0, 1, 2]);
    expect([...neighbourhood(edges, (e) => e === 0, 1)].sort()).toEqual([0, 1]);
    expect(findPoint(points, 'D4E5F6')).toBe(1);
    expect(findPoint(points, 'e1')).toBe(3);
    expect(findPoint(points, 'zz')).toBeNull();
    expect(findPoint(points, '  ')).toBeNull();
    const screen = Float32Array.from([10, 10, 0.5, 100, 100, 0.5, 12, 12, 2]);
    expect(nearestOnScreen(screen, 13, 13, 14)).toBe(0); // the nearer one is behind the camera
    expect(nearestOnScreen(screen, 300, 300, 14)).toBeNull();
  });

  it('says a stored case’s values in a line', () => {
    expect(valueText([['refund', 1], ['twice', 0.4]])).toBe('refund twice');
    expect(valueText(['a', 'b', { c: 1 }])).toBe('a, b, {"c":1}');
    expect(valueText({ x: 1 })).toBe('{"x":1}');
    expect(valueText(3)).toBe('3');
    expect(rolesOfCase({ l: { s: { r: 'v', n: [1, 2] } }, e: null })).toEqual([
      { path: 'l.s.r', value: 'v' },
      { path: 'l.s.n', value: '1, 2' },
    ]);
  });
});

describe('the 3D view’s layout', () => {
  it('keeps the old viewer’s radius and rest lengths', () => {
    expect([layoutRadius(10), layoutRadius(30), layoutRadius(60), layoutRadius(150)]).toEqual([22, 32, 42, 52]);
    expect(layoutRadius(1000)).toBeCloseTo(64 + Math.log(1000) * 10);
    expect(restLength(1, 50)).toBe(2.5);
    expect(restLength(0, 50)).toBe(50);
    expect(restLength(2, 50)).toBe(2.5);
    expect(seeded(1)()).toBe(seeded(1)());
  });

  it('pulls neighbours together, pushes the rest apart, stays centred and settles', () => {
    const layout = new Layout([0, 0, 1, 1], [[0, 1, 0.9]]);
    const gap = (a: number, b: number) => Math.hypot(...[0, 1, 2].map((k) => layout.positions[a * 3 + k]! - layout.positions[b * 3 + k]!));
    for (let i = 0; i < 3000; i++) layout.step();
    expect(gap(0, 1)).toBeLessThan(gap(0, 2));
    const mean = [0, 1, 2].map((k) => [0, 1, 2, 3].reduce((s, i) => s + layout.positions[i * 3 + k]!, 0) / 4);
    for (const m of mean) expect(Math.abs(m)).toBeLessThan(1e-3);
    expect(layout.moved).toBeLessThan(0.01);
    const one = new Layout([0], []);
    one.step(5);
    expect([...one.positions]).toEqual([0, 0, 0]);
    expect(new Layout([], []).moved).toBe(Infinity);
    new Layout([], []).step();
  });

  it('caps each move', () => {
    const layout = new Layout([0, 0], [], () => 0.5);
    layout.step(100);
    expect(layout.moved).toBeLessThanOrEqual(0.55);
  });
});
