import styles from './Logo.module.css';

/** The Glyphh logo, mascot and wordmark. The theme picks the dark or the light file. */
export function Logo({ height = 40 }: { height?: number }) {
  return <span className={styles.logo} style={{ height, width: height * 3.02 }} role="img" aria-label="Glyphh" />;
}
