import type { ReactNode } from "react";
import styles from "./Badge.module.css";

export type Tone = "neutral" | "accent" | "ok" | "warn" | "danger";

/** A short label: a plan, a role, a state. */
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return <span className={styles.badge} data-tone={tone}>{children}</span>;
}
