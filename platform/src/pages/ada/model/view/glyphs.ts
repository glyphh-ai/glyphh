import type { MapPoint, ModelMap, Spec } from '@/api/ada';

/** A glyph's bits from the server's base64 (+1 as 1, first bit highest), `dim` of them, as 0 and 1. */
export function decodeBits(b64: string, dim: number): Uint8Array {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const bits = new Uint8Array(dim);
  for (let i = 0; i < dim; i++) bits[i] = (bytes[i >> 3]! >> (7 - (i & 7))) & 1;
  return bits;
}

/**
 * Each set bit's place in the old viewer's cortex cube (buildPointCloud): the bits laid out in a cube of side
 * ⌈∛dim⌉, centred, `scale` across. x, y, z in turn.
 */
export function cloud(bits: Uint8Array, scale: number): Float32Array {
  const side = Math.ceil(Math.cbrt(bits.length));
  const out: number[] = [];
  bits.forEach((bit, i) => {
    if (!bit) return;
    const at = (k: number) => (k - side / 2) * (3 / side) * scale;
    out.push(at(i % side), at(Math.floor(i / side) % side), at(Math.floor(i / (side * side))));
  });
  return Float32Array.from(out);
}

/** The output the view colours by: the default one when the spec has it, else its first named output. */
export function colourOutput(spec: Spec): string | null {
  const named = Object.keys(spec.outputs ?? {});
  return spec.output || !named.length ? null : named[0]!;
}

export function outcomeOf(point: MapPoint, output: string | null): string | null {
  return output === null ? point.outcome : (point.outcomes[output] ?? null);
}

export const UNGRADED = 'Ungraded';
export const OTHER = 'Other';
/** How many outcomes get a colour of their own; the rest are Other. */
export const COLOURED = 5;

export type Legend = Array<{ name: string; count: number; colour: string }>;

/**
 * The outcomes in the sample, most common first, each with its colour: the first COLOURED from the theme's series,
 * the rest together as Other, and ungraded cases last, in the muted line colour.
 */
export function legendOf(map: ModelMap, output: string | null, series: string[], other: string, ungraded: string): { legend: Legend; colourOf: (outcome: string | null) => string; group: (outcome: string | null) => number } {
  const counts = new Map<string, number>();
  for (const p of map.points) {
    const o = outcomeOf(p, output);
    if (o !== null) counts.set(o, (counts.get(o) ?? 0) + 1);
  }
  const ranked = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const colour = new Map(ranked.slice(0, COLOURED).map(([name], i) => [name, series[i % series.length]!]));
  const legend: Legend = ranked.slice(0, COLOURED).map(([name, count]) => ({ name, count, colour: colour.get(name)! }));
  const rest = ranked.slice(COLOURED).reduce((sum, [, count]) => sum + count, 0);
  if (rest) legend.push({ name: OTHER, count: rest, colour: other });
  const none = map.points.filter((p) => outcomeOf(p, output) === null).length;
  if (none) legend.push({ name: UNGRADED, count: none, colour: ungraded });
  const place = new Map(ranked.map(([name], i) => [name, i]));
  return {
    legend,
    colourOf: (outcome) => (outcome === null ? ungraded : (colour.get(outcome) ?? other)),
    group: (outcome) => (outcome === null ? ranked.length : place.get(outcome)!),
  };
}

/** The points joined to `at` by an edge shown, and `at` itself. */
export function neighbourhood(edges: ModelMap['edges'], shown: (e: number) => boolean, at: number): Set<number> {
  const near = new Set([at]);
  edges.forEach(([a, b], e) => {
    if (!shown(e)) return;
    if (a === at) near.add(b);
    if (b === at) near.add(a);
  });
  return near;
}

/** The first point whose id is the text, else the first whose id starts with it (the old viewer's search). */
export function findPoint(points: MapPoint[], text: string): number | null {
  const q = text.trim().toLowerCase();
  if (!q) return null;
  const exact = points.findIndex((p) => p.id.toLowerCase() === q);
  if (exact >= 0) return exact;
  const prefix = points.findIndex((p) => p.id.toLowerCase().startsWith(q));
  return prefix >= 0 ? prefix : null;
}

/** The nearest of the points on screen to (x, y), within `radius` pixels; null when none is. */
export function nearestOnScreen(screen: Float32Array, x: number, y: number, radius: number): number | null {
  let best: number | null = null;
  let bestD = radius * radius;
  for (let i = 0; i < screen.length / 3; i++) {
    if (screen[i * 3 + 2]! > 1) continue; // behind the camera
    const dx = screen[i * 3]! - x;
    const dy = screen[i * 3 + 1]! - y;
    const d = dx * dx + dy * dy;
    if (d <= bestD) {
      bestD = d;
      best = i;
    }
  }
  return best;
}

/** A stored value in a line: a bag of weighted words as its words, a set as its values, a number's bins as the last. */
export function valueText(value: unknown): string {
  if (Array.isArray(value)) {
    if (value.every((v) => Array.isArray(v) && v.length === 2 && typeof v[1] === 'number')) return value.map((v) => String((v as unknown[])[0])).join(' ');
    return value.map((v) => (typeof v === 'object' ? JSON.stringify(v) : String(v))).join(', ');
  }
  return typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value);
}

/** A stored case's roles, in a list: layer.segment.role and its value. */
export function rolesOfCase(situation: Record<string, unknown>): Array<{ path: string; value: string }> {
  const out: Array<{ path: string; value: string }> = [];
  for (const [layer, segments] of Object.entries(situation)) {
    for (const [segment, roles] of Object.entries((segments ?? {}) as Record<string, unknown>)) {
      for (const [role, value] of Object.entries((roles ?? {}) as Record<string, unknown>)) out.push({ path: `${layer}.${segment}.${role}`, value: valueText(value) });
    }
  }
  return out;
}
