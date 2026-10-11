import type { ReactNode } from "react";
import { Heading } from "../Heading/Heading";
import styles from "./Section.module.css";

export interface SectionProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}

/** A titled part of a page. */
export function Section({ title, description, actions, children }: SectionProps) {
  return (
    <section className={styles.section} aria-label={title}>
      <header className={styles.header}>
        <div>
          <Heading level={2}>{title}</Heading>
          {description && <p className={styles.description}>{description}</p>}
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}
