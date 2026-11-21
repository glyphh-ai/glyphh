import type { CSSProperties } from 'react';
import styles from './Logo.module.css';

/**
 * The Glyphh wordmark alone (his order, 2026-10-25): the cat is the mascot, not the logo. The theme picks the
 * dark or the light file (tokens.css: --logo), its aspect ratio (--logo-ratio) and a scale (--logo-scale) that
 * makes the two files, which are cut with different padding, show the letters at the same size.
 */
export function Logo({ height = 40 }: { height?: number }) {
  return <span className={styles.logo} style={{ '--logo-h': `${height}px` } as CSSProperties} role="img" aria-label="Glyphh" />;
}
