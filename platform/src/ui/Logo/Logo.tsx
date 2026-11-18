import type { CSSProperties } from 'react';
import styles from './Logo.module.css';

/**
 * Glyphh's logo, the file glyphh.ai's header shows (public/glyphh-logo-black.png, from glyphh-ai/web: the cat and
 * the name in black with a white outline, so one file reads on a dark and on a light theme), at the 38px high it is
 * there. Never typed: the brand is the file.
 */
export function Logo({ height = 38 }: { height?: number }) {
  return <span className={styles.logo} style={{ '--logo-h': `${height}px` } as CSSProperties} role="img" aria-label="Glyphh" />;
}
