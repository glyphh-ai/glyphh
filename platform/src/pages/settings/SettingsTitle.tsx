import type { ReactNode } from 'react';
import styles from './settings.module.css';

export function SettingsTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div>
      <h1 className={styles.title}>{title}</h1>
      {children && <p className={styles.lede}>{children}</p>}
    </div>
  );
}

/** For people who are not their org's admin: what they see is read-only. */
export function AdminOnlyNote({ isAdmin }: { isAdmin: boolean }) {
  if (isAdmin) return null;
  return <p className={styles.note}>Only your org’s admin can change this.</p>;
}
