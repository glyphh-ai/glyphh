import type { ReactNode } from 'react';
import { Logo } from '@/ui';
import styles from './AuthLayout.module.css';

type AuthLayoutProps = {
  title: string;
  children: ReactNode;
  /** The line under the card's body, such as the terms. */
  footer?: ReactNode;
};

/**
 * The sign-in and consent pages: one centred card under the logo.
 * They are always high-visibility dark, the site's black and white, whatever theme the platform is in.
 */
export function AuthLayout({ title, children, footer }: AuthLayoutProps) {
  return (
    <div className={styles.page} data-theme="dark-hc">
      <Logo height={44} />
      <div className={styles.card}>
        <div className={styles.body}>
          <h1 className={styles.title}>{title}</h1>
          {children}
        </div>
        {footer && <div className={styles.footer}>{footer}</div>}
      </div>
    </div>
  );
}
