import type { CSSProperties } from "react";
import styles from "./Skeleton.module.css";

export interface SkeletonProps {
  lines?: number;
  /** A box instead of lines: a card or an avatar while it loads. */
  height?: number;
}

/** Where content will be once it loads. Screen readers hear "Loading" once, not the shapes. */
export function Skeleton({ lines = 3, height }: SkeletonProps) {
  return (
    <div className={styles.skeleton} role="status" aria-label="Loading">
      {height ? <span className={styles.box} style={{ "--skeleton-h": `${height}px` } as CSSProperties} />
        : Array.from({ length: lines }, (_, i) => <span key={i} className={styles.line} />)}
    </div>
  );
}
