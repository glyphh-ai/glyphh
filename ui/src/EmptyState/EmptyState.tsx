import type { ReactNode } from "react";
import { Heading } from "../Heading/Heading";
import styles from "./EmptyState.module.css";

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  /** A cat or an icon above the title. */
  art?: ReactNode;
  /** What to do about it: the one next step. */
  action?: ReactNode;
}

/** Nothing here yet, and what to do next. */
export function EmptyState({ title, description, art, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      {art}
      <Heading level={3}>{title}</Heading>
      {description && <p className={styles.description}>{description}</p>}
      {action}
    </div>
  );
}
