import styles from "./Spinner.module.css";

export interface SpinnerProps {
  label?: string;
  size?: "sm" | "md";
}

/** Something is happening. Screen readers hear the label. */
export function Spinner({ label = "Loading", size = "md" }: SpinnerProps) {
  return <span className={styles.spinner} data-size={size} role="status" aria-label={label} />;
}
