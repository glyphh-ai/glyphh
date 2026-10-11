import styles from "./StatusDot.module.css";

export type Status = "online" | "offline" | "working" | "waiting" | "failed";

const WORDS: Record<Status, string> = {
  online: "Online", offline: "Offline", working: "Working", waiting: "Waiting for you", failed: "Failed",
};

/** A machine's or a super power's state: a dot, and its word for screen readers (or shown, with `showLabel`). */
export function StatusDot({ status, showLabel = false }: { status: Status; showLabel?: boolean }) {
  return (
    <span className={styles.status} data-status={status}>
      <span className={styles.dot} aria-hidden="true" />
      <span className={showLabel ? styles.label : styles.hidden}>{WORDS[status]}</span>
    </span>
  );
}
