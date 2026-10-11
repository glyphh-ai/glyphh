import type { ReactNode } from "react";
import styles from "./Alert.module.css";

export interface AlertProps {
  tone?: "info" | "ok" | "warn" | "danger";
  title?: string;
  children?: ReactNode;
  /** The error's code and trace id, shown so the person can quote them. */
  code?: string;
  traceId?: string;
}

/** Something the person should know now. Warnings and dangers interrupt screen readers; the rest wait. */
export function Alert({ tone = "info", title, children, code, traceId }: AlertProps) {
  const urgent = tone === "warn" || tone === "danger";
  const trace = [code, traceId && `trace ${traceId}`].filter(Boolean).join(" · ");
  return (
    <div className={styles.alert} data-tone={tone} role={urgent ? "alert" : "status"}>
      {title && <p className={styles.title}>{title}</p>}
      {children && <div className={styles.body}>{children}</div>}
      {trace && <p className={styles.trace}>{trace}</p>}
    </div>
  );
}
