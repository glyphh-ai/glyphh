import type { ReactNode } from 'react';
import styles from './SettingsSection.module.css';

type SettingsSectionProps = {
  title: string;
  description?: ReactNode;
  children: ReactNode;
};

/** A settings row: what it is on the left, the controls on the right. */
export function SettingsSection({ title, description, children }: SettingsSectionProps) {
  return (
    <section className={styles.section}>
      <div className={styles.about}>
        <h2 className={styles.title}>{title}</h2>
        {description && <p className={styles.description}>{description}</p>}
      </div>
      <div className={styles.body}>{children}</div>
    </section>
  );
}
