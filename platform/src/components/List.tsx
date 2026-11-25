import type { ReactNode } from 'react';
import styles from './List.module.css';

/** A bordered list of rows, as on API Keys, Members and Installs. */
export function List({ label, children }: { label: string; children: ReactNode }) {
  return (
    <ul className={styles.list} aria-label={label}>
      {children}
    </ul>
  );
}

type RowProps = {
  /** The leading part: a name, an address or an avatar with a name. */
  title: ReactNode;
  /** The grey line under the title. */
  meta?: ReactNode;
  /** Chips beside the title. */
  badges?: ReactNode;
  actions?: ReactNode;
};

export function Row({ title, meta, badges, actions }: RowProps) {
  return (
    <li className={styles.row}>
      <div className={styles.main}>
        <div className={styles.titleLine}>
          <span className={styles.title}>{title}</span>
          {badges}
        </div>
        {meta && <div className={styles.meta}>{meta}</div>}
      </div>
      {actions && <div className={styles.actions}>{actions}</div>}
    </li>
  );
}
