import type { ReactNode } from "react";
import { Heading } from "../Heading/Heading";
import styles from "./Page.module.css";

export interface PageProps {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  width?: "narrow" | "normal" | "wide";
  children: ReactNode;
}

/** One screen: its title, what it is for, its actions, then its content. */
export function Page({ title, description, actions, width = "normal", children }: PageProps) {
  return (
    <main className={styles.page} data-width={width}>
      <header className={styles.header}>
        <div>
          <Heading level={1}>{title}</Heading>
          {description && <p className={styles.description}>{description}</p>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </header>
      {children}
    </main>
  );
}
