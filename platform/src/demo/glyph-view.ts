import type { ModelMap } from '@/api/ada';
import type { Ink } from '@/lib/tokens';
import { reducedMotion } from '@/lib/tokens';
import { GlyphScene } from '@/pages/ada/model/view/scene';

/**
 * The platform's 3D view (pages/ada/model/view/scene.ts) for the demos' plain pages, built on its own
 * (vite.demo.config.ts → dist/demo/glyph-view.js): each precedent its glyph's cloud of bits, laid out by its
 * nearest, coloured by its outcome; the visitor's own takes bright, the newest picked out.
 */

/** The platform's dark-hc ink (styles/tokens.css), which the demos wear. */
export const INK: Ink = {
  bg: '#000000',
  surface: '#0d0d0d',
  text: '#ffffff',
  secondary: '#eaeaea',
  muted: '#c8c8c8',
  line: '#5a5a5a',
  lineStrong: '#7a7a7a',
  accent: '#b066ff',
  series: ['#d2a8ff', '#fcd34d', '#93c5fd', '#fca5a5', '#6ee7b7'],
  font: 'Geist, sans-serif',
  mono: 'JetBrains Mono, monospace',
};

export type Shown = {
  map: ModelMap;
  /** Each outcome's colour; an outcome not named is drawn in the muted ink. */
  colours: Record<string, string>;
  /** The ids drawn bright; the rest are dimmed. None: every point bright. */
  bright?: Set<string>;
};

export class GlyphView {
  private scene: GlyphScene | null = null;
  private readonly watch: ResizeObserver;

  constructor(private readonly canvas: HTMLCanvasElement) {
    this.watch = new ResizeObserver(() => this.fit());
    this.watch.observe(canvas);
  }

  /** Draws this map, laid out afresh; false when the browser cannot draw WebGL. */
  show({ map, colours, bright }: Shown): boolean {
    this.scene?.dispose();
    this.scene = null;
    const outcomes = [...new Set(map.points.map((p) => p.outcome ?? ''))];
    const group = (p: ModelMap['points'][number]) => outcomes.indexOf(p.outcome ?? '');
    try {
      this.scene = new GlyphScene(this.canvas, map, map.points.map(group), reducedMotion());
    } catch {
      return false;
    }
    const highlight = bright && bright.size ? new Set(map.points.flatMap((p, i) => (bright.has(p.id) ? [i] : []))) : null;
    this.scene.setLook({
      colours: map.points.map((p) => colours[p.outcome ?? ''] ?? INK.muted),
      same: map.edges.map(([a, b]) => map.points[a]?.outcome === map.points[b]?.outcome),
      showSame: true,
      showDifferent: false,
      highlight,
      explode: false,
      ink: INK,
    });
    this.fit();
    this.scene.start();
    return true;
  }

  private fit() {
    this.scene?.resize(this.canvas.clientWidth, this.canvas.clientHeight);
  }

  dispose() {
    this.watch.disconnect();
    this.scene?.dispose();
    this.scene = null;
  }
}
