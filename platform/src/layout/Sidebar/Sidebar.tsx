import type { ReactNode } from 'react';
import { NavLink } from 'react-router';
import { cx } from '@/lib/cx';
import { Icon, type IconName } from '@/ui';
import styles from './Sidebar.module.css';

type SidebarProps = {
  /** What sits under the logo, such as the way back out of settings. */
  heading?: ReactNode;
  footer: ReactNode;
  children: ReactNode;
};

export function Sidebar({ heading, footer, children }: SidebarProps) {
  return (
    <div className={styles.sidebar}>
      {heading}
      <nav className={styles.nav}>{children}</nav>
      <div className={styles.footer}>{footer}</div>
    </div>
  );
}

export function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.group} role="group" aria-label={label}>
      <div className={styles.groupLabel} aria-hidden="true">
        {label}
      </div>
      {children}
    </div>
  );
}

/** A page in the sidebar; `badge` is a count waiting there (none shown at 0). */
export function NavItem({ to, icon, end = false, badge, children }: { to: string; icon: IconName; end?: boolean; badge?: number; children: ReactNode }) {
  return (
    <NavLink to={to} end={end} title={typeof children === 'string' ? children : undefined} className={({ isActive }) => cx(styles.item, isActive && styles.active)}>
      <Icon name={icon} />
      {/* Its own element, so the sidebar can fold to icons beside a bare page (Bots). */}
      <span className={styles.text}>{children}</span>
      {badge ? (
        <span className={styles.badge} aria-label={`${badge} waiting`}>
          {badge > 99 ? '99+' : badge}
        </span>
      ) : null}
    </NavLink>
  );
}

export function SidebarBack({ to, children }: { to: string; children: ReactNode }) {
  return (
    <NavLink to={to} className={styles.back}>
      <Icon name="arrowLeft" size={18} />
      {children}
    </NavLink>
  );
}
