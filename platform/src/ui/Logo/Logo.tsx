import styles from './Logo.module.css';

/** The glyphh wordmark. The theme picks the white or the black file. */
export function Logo({ height = 34 }: { height?: number }) {
  return <span className={styles.logo} style={{ height, width: height * 3.21 }} role="img" aria-label="Glyphh" />;
}
