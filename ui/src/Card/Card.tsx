import type { ReactNode } from "react";
import { Heading } from "../Heading/Heading";
import styles from "./Card.module.css";

export interface CardProps {
  title?: string;
  description?: ReactNode;
  /** Something beside the title: an avatar, a status. */
  leading?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}

/** A box for one thing: a machine, a super power, a plan. */
export function Card({ title, description, leading, actions, children }: CardProps) {
  return (
    <article className={styles.card} aria-label={title}>
      {(title || leading || actions) && (
        <header className={styles.header}>
          {leading}
          <div className={styles.titles}>
            {title && <Heading level={3}>{title}</Heading>}
            {description && <p className={styles.description}>{description}</p>}
          </div>
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      {children}
    </article>
  );
}
