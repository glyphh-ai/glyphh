import { useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Logo } from '@/ui';
import { TopBar, type Crumb } from '../TopBar/TopBar';
import styles from './AppShell.module.css';

type AppShellProps = {
  sidebar: ReactNode;
  crumbs: Crumb[];
  children: ReactNode;
};

/** The signed-in frame: the sidebar, the breadcrumb bar, and the page. */
export function AppShell({ sidebar, crumbs, children }: AppShellProps) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // On a phone the sidebar is a drawer; moving to another page closes it.
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className={styles.shell} data-sidebar={open ? 'open' : 'closed'}>
      <aside className={styles.sidebar} aria-label="Main">
        <div className={styles.logo}>
          <Logo />
        </div>
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
