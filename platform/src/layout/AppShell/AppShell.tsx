import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useLocation } from 'react-router';
import { Logo } from '@/ui';
import { TopBar, type Crumb } from '../TopBar/TopBar';
import styles from './AppShell.module.css';

type AppShellProps = {
  sidebar: ReactNode;
  crumbs: Crumb[];
  /** The logo at the top of the sidebar; settings has none, its way back sits there instead. */
  logo?: boolean;
  /**
   * The page is an app of its own and fills the screen (Bots, which is the Glyphh Bot app's interface): no breadcrumb
   * bar and no padding, and the sidebar folds to its icons so the page has the room. On a phone the sidebar is the
   * drawer it always is, opened by the page with `useShellNav`.
   */
  bare?: boolean;
  children: ReactNode;
};

const ShellNav = createContext<{ toggleSidebar: () => void }>({ toggleSidebar: () => undefined });
/** For a bare page: its own button opens the sidebar on a phone. */
export const useShellNav = () => useContext(ShellNav);

/** The signed-in frame: the sidebar, the breadcrumb bar, and the page. */
export function AppShell({ sidebar, crumbs, logo = true, bare = false, children }: AppShellProps) {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // On a phone the sidebar is a drawer; moving to another page closes it.
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className={styles.shell} data-sidebar={open ? 'open' : 'closed'} data-bare={bare || undefined}>
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
        {bare ? (
          <ShellNav.Provider value={{ toggleSidebar: () => setOpen((o) => !o) }}>
            <div className={styles.bare}>{children}</div>
          </ShellNav.Provider>
        ) : (
          <>
            <TopBar crumbs={crumbs} onToggleSidebar={() => setOpen((o) => !o)} />
            <main className={styles.content}>{children}</main>
          </>
        )}
      </div>
    </div>
  );
}
