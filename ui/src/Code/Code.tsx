import type { ReactNode } from "react";
import styles from "./Code.module.css";

/** A short piece of code, an id or a value, inside a sentence. */
export function Code({ children }: { children: ReactNode }) {
  return <code className={styles.code}>{children}</code>;
}
