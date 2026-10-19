import { Outlet, useMatches } from 'react-router';
import { useHosting } from '@/api/queries';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar, SidebarBack } from '@/layout/Sidebar/Sidebar';
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

export function MainLayout() {
  // Machines are Glyphh's hosted ones: shown only once the server says it hosts any.
  const hosting = useHosting();
  return (
    <AppShell
      crumbs={useCrumbs()}
      sidebar={
        <Sidebar footer={<UserMenu />}>
          <NavItem to="/getting-started" icon="flag">
            Getting started
          </NavItem>
          {hosting && (
            <NavItem to="/machines" icon="chip">
              Machines
            </NavItem>
          )}
          <NavGroup label="Runtime">
            <NavItem to="/" end icon="home">
              Home
            </NavItem>
            <NavItem to="/keys" icon="key">
              API Keys
            </NavItem>
          </NavGroup>
          <NavGroup label="Ada">
            <NavItem to="/models" icon="model">
              Models
            </NavItem>
          </NavGroup>
        </Sidebar>
      }
    >
      <Outlet />
    </AppShell>
  );
}

export function SettingsLayout() {
  return (
    <AppShell
      crumbs={useCrumbs()}
      logo={false}
      sidebar={
        <Sidebar heading={<SidebarBack to="/">Settings</SidebarBack>} footer={<UserMenu />}>
          <NavGroup label="Organisation">
            <NavItem to="/settings/general" icon="settings">
              General
            </NavItem>
            <NavItem to="/settings/billing" icon="card">
              Billing
            </NavItem>
            <NavItem to="/settings/licence" icon="key">
              Licence
            </NavItem>
            <NavItem to="/settings/usage" icon="monitor">
              Usage
            </NavItem>
            <NavItem to="/settings/members" icon="team">
              Members
            </NavItem>
          </NavGroup>
          <NavGroup label="Personal">
            <NavItem to="/settings/profile" icon="user">
              Profile
            </NavItem>
            <NavItem to="/settings/installs" icon="laptop">
              Installs
            </NavItem>
          </NavGroup>
        </Sidebar>
      }
    >
      <Outlet />
    </AppShell>
  );
}
