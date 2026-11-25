import { useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Logo } from '@/ui';
import { TopBar, type Crumb } from '../TopBar/TopBar';
import styles from './AppShell.module.css';

type AppShellProps = {
  sidebar: ReactNode;
  crumbs: Crumb[];
  /** The logo at the top of the sidebar; settings has none, its way back sits there instead. */
  logo?: boolean;
  children: ReactNode;
};

/** The signed-in frame: the sidebar, the breadcrumb bar, and the page. */
export function AppShell({ sidebar, crumbs, logo = true, children }: AppShellProps) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // On a phone the sidebar is a drawer; moving to another page closes it.
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className={styles.shell} data-sidebar={open ? 'open' : 'closed'}>
      <aside className={styles.sidebar} aria-label="Main">
        {logo && (
          <div className={styles.logo}>
            <Logo />
          </div>
        )}
        {sidebar}
      </aside>
      {open && <button type="button" className={styles.scrim} aria-label="Close menu" onClick={() => setOpen(false)} />}
      <div className={styles.main}>
        <TopBar crumbs={crumbs} onToggleSidebar={() => setOpen((o) => !o)} />
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}
