import styles from './Ring.module.css';

/**
 * How much of something is used, as a ring filling clockwise from the top (at most full), with the share in its middle;
 * a progress bar to a screen reader.
 */
export function Ring({ value, max, label, size = 64 }: { value: number; max: number; label: string; size?: number }) {
  const share = max > 0 ? Math.min(value / max, 1) : 0;
  const radius = 15.5;
  const around = 2 * Math.PI * radius;
  const over = max > 0 && value > max;
  return (
    <div
      className={styles.ring}
      style={{ width: size, height: size }}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={Math.min(value, max)}
    >
      <svg viewBox="0 0 36 36" width={size} height={size} aria-hidden="true">
        <circle className={styles.track} cx="18" cy="18" r={radius} />
        <circle
          className={over ? styles.over : styles.fill}
          cx="18"
          cy="18"
          r={radius}
          strokeDasharray={`${share * around} ${around}`}
          transform="rotate(-90 18 18)"
        />
      </svg>
      <span className={styles.share}>{`${Math.round((max > 0 ? value / max : 0) * 100)}%`}</span>
    </div>
  );
}
