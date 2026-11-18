import { Outlet, useMatches } from 'react-router';
import { StaffNav } from '@/admin/StaffGate';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar } from '@/layout/Sidebar/Sidebar';
import type { Crumb } from '@/layout/TopBar/TopBar';
import { UserMenu } from '@/layout/UserMenu/UserMenu';

/** Each route names its own crumbs in `handle.crumbs`; the deepest one wins. */
export type RouteHandle = { crumbs: Crumb[] };

function useCrumbs(): Crumb[] {
  const matches = useMatches();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as RouteHandle | undefined;
    if (handle?.crumbs) return handle.crumbs;
  }
  return [];
}

/** The console's shell: the logo, Home, the staff view's way in for staff, and the person's menu. */
export function MainLayout() {
  return (
    <AppShell
      crumbs={useCrumbs()}
      sidebar={
        <Sidebar footer={<UserMenu />}>
          <NavGroup label="Glyphh">
            <NavItem to="/" end icon="home">
              Home
            </NavItem>
          </NavGroup>
          <StaffNav />
        </Sidebar>
      }
    >
      <Outlet />
    </AppShell>
  );
}
