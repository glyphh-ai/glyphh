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

export function NavItem({ to, icon, end = false, children }: { to: string; icon: IconName; end?: boolean; children: ReactNode }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => cx(styles.item, isActive && styles.active)}>
      <Icon name={icon} />
      {children}
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
