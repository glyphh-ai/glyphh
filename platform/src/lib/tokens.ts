import { useMemo } from 'react';
import { useTheme } from '@/theme/ThemeProvider';

/**
 * The theme's colours as the canvas needs them (charts, the 3D view): read from the CSS tokens on the page, again
 * whenever the theme changes, so a canvas follows light, dark and high-visibility as the rest of the page does.
 */
export type Ink = {
  bg: string;
  surface: string;
  text: string;
  secondary: string;
  muted: string;
  line: string;
  lineStrong: string;
  accent: string;
  /** Outcomes and other categories, in a fixed order: the same outcome keeps its colour while the page is open. */
  series: string[];
  font: string;
  mono: string;
};

/** Categorical order: violet, amber, blue, red, green, apart enough for colour-blind readers (checked in light). */
const seriesTokens = ['--violet-text', '--amber-text', '--blue-text', '--red-text', '--green-text'];

export function readInk(root: Element = document.documentElement): Ink {
  const style = getComputedStyle(root);
  const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    bg: token('--bg', '#000000'),
    surface: token('--surface', '#111111'),
    text: token('--text', '#ffffff'),
    secondary: token('--text-secondary', '#bdbdbd'),
    muted: token('--text-muted', '#a0a0a0'),
    line: token('--line', '#2e2e2e'),
    lineStrong: token('--line-strong', '#444444'),
    accent: token('--accent', '#b066ff'),
    series: seriesTokens.map((name, i) => token(name, ['#c68cff', '#fbbf24', '#60a5fa', '#f87171', '#34d399'][i]!)),
    font: token('--font-sans', 'sans-serif'),
    mono: token('--font-mono', 'monospace'),
  };
}

/**
 * The ink of the theme in use, read again when it changes: from an element of its own carrying the theme, since the
 * page's root takes the new theme only after this renders.
 */
export function useInk(): Ink {
  const { resolved } = useTheme();
  return useMemo(() => {
    const probe = document.createElement('div');
    probe.dataset.theme = resolved;
    probe.hidden = true;
    document.body.append(probe);
    try {
      return readInk(probe);
    } finally {
      probe.remove();
    }
  }, [resolved]);
}

/** Whether the person asked for less motion. */
export function reducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}
