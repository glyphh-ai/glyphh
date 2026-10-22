/**
 * The 3D view's layout, ported from the old GlyphViewer (ada-private 5caefc4, web/static/js/viewer.js): each
 * precedent pulled toward its nearest by springs whose rest length grows as their similarity falls, every pair pushed
 * apart, started in rings by outcome (the old viewer's clusters by type), and kept centred. Plain arrays, no three.js,
 * so it is tested on its own.
 */

/** The old viewer's numbers (CORTEX_LAYOUT and LAYOUT_PARAMS). */
export const LAYOUT = { springK: 0.12, dMin: 2.5, dMaxScale: 1.2, easePower: 2, repulsion: 14 * 1.25, damping: 0.9, maxStep: 0.55, dt: 0.02 };
export const EXPLODE_SCALE = 2.4;

export function layoutRadius(n: number): number {
  if (n < 20) return 22;
  if (n < 50) return 32;
  if (n < 100) return 42;
  if (n < 200) return 52;
  return 64 + Math.log(n) * 10;
}

/** A rest length from a similarity: dMin when the same, dMax when nothing is shared, eased between. */
export function restLength(sim: number, dMax: number): number {
  const t = 1 - Math.max(0, Math.min(1, sim));
  return LAYOUT.dMin + Math.pow(t, LAYOUT.easePower) * (dMax - LAYOUT.dMin);
}

/** A small seeded random, so a model is laid out the same way each time it is opened. */
export function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Adds (x, y, z) to point i's three numbers. */
function push(values: Float32Array, i: number, x: number, y: number, z: number): void {
  values[i * 3] = values[i * 3]! + x;
  values[i * 3 + 1] = values[i * 3 + 1]! + y;
  values[i * 3 + 2] = values[i * 3 + 2]! + z;
}

export type Spring ={ a: number; b: number; rest: number; weight: number };

export class Layout {
  readonly n: number;
  /** x, y, z of each point, in turn. */
  readonly positions: Float32Array;
  private readonly velocities: Float32Array;
  private readonly forces: Float32Array;
  readonly springs: Spring[];
  /** How far the points moved, on average, in the last step. */
  moved = Infinity;

  /** `groups`: each point's outcome, by place among the outcomes; `edges`: [i, j, similarity]. */
  constructor(groups: number[], edges: Array<[number, number, number]>, random: () => number = seeded(7)) {
    const n = (this.n = groups.length);
    this.positions = new Float32Array(n * 3);
    this.velocities = new Float32Array(n * 3);
    this.forces = new Float32Array(n * 3);
    const radius = layoutRadius(n);
    const dMax = Math.max(LAYOUT.dMin + 1, radius * LAYOUT.dMaxScale);
    this.springs = edges.map(([a, b, sim]) => ({ a, b, rest: restLength(sim, dMax), weight: 0.15 + sim * 0.85 }));
    const count = Math.max(1, Math.max(-1, ...groups) + 1);
    groups.forEach((group, i) => {
      const angle = (2 * Math.PI * group) / count;
      this.positions[i * 3] = (count > 1 ? Math.cos(angle) * radius : 0) + (random() - 0.5) * 4;
      this.positions[i * 3 + 1] = (random() - 0.5) * 3;
      this.positions[i * 3 + 2] = (count > 1 ? Math.sin(angle) * radius : 0) + (random() - 0.5) * 4;
    });
    this.centre();
  }

  /** One step: springs, repulsion between every pair, damping, a cap on each move, then centred again. */
  step(dt = LAYOUT.dt): void {
    const { positions: p, velocities: v, forces: f, n } = this;
    f.fill(0);
    for (const { a, b, rest, weight } of this.springs) {
      const dx = p[b * 3]! - p[a * 3]!;
      const dy = p[b * 3 + 1]! - p[a * 3 + 1]!;
      const dz = p[b * 3 + 2]! - p[a * 3 + 2]!;
      const dist = Math.hypot(dx, dy, dz) + 1e-4;
      const k = (LAYOUT.springK * weight * (dist - rest)) / dist;
      push(f, a, k * dx, k * dy, k * dz);
      push(f, b, -k * dx, -k * dy, -k * dz);
    }
    for (let i = 0; i < n; i++) {
      const xi = p[i * 3]!;
      const yi = p[i * 3 + 1]!;
      const zi = p[i * 3 + 2]!;
      for (let j = i + 1; j < n; j++) {
        const dx = p[j * 3]! - xi;
        const dy = p[j * 3 + 1]! - yi;
        const dz = p[j * 3 + 2]! - zi;
        const d2 = dx * dx + dy * dy + dz * dz + 1e-4;
        const k = LAYOUT.repulsion / (d2 * Math.sqrt(d2));
        push(f, i, -k * dx, -k * dy, -k * dz);
        push(f, j, k * dx, k * dy, k * dz);
      }
    }
    let moved = 0;
    for (let i = 0; i < n * 3; i += 3) {
      let sx = (v[i] = (v[i]! + f[i]! * dt) * LAYOUT.damping) * dt;
      let sy = (v[i + 1] = (v[i + 1]! + f[i + 1]! * dt) * LAYOUT.damping) * dt;
      let sz = (v[i + 2] = (v[i + 2]! + f[i + 2]! * dt) * LAYOUT.damping) * dt;
      const len = Math.hypot(sx, sy, sz);
      if (len > LAYOUT.maxStep) {
        sx *= LAYOUT.maxStep / len;
        sy *= LAYOUT.maxStep / len;
        sz *= LAYOUT.maxStep / len;
      }
      push(p, i / 3, sx, sy, sz);
      moved += Math.min(len, LAYOUT.maxStep);
    }
    this.moved = n ? moved / n : 0;
    this.centre();
  }

  private centre(): void {
    const { positions: p, n } = this;
    if (!n) return;
    for (let axis = 0; axis < 3; axis++) {
      let sum = 0;
      for (let i = axis; i < n * 3; i += 3) sum += p[i]!;
      const mean = sum / n;
      for (let i = axis; i < n * 3; i += 3) p[i] = p[i]! - mean;
    }
  }
}
