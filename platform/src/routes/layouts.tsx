import { Outlet, useMatches, useParams } from 'react-router';
import { StaffNav } from '@/admin/StaffGate';
import { useAdaCloud } from '@/api/ada';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar, SidebarBack } from '@/layout/Sidebar/Sidebar';
import type { Crumb } from '@/layout/TopBar/TopBar';
import { UserMenu } from '@/layout/UserMenu/UserMenu';

/** Each route names its own crumbs in `handle.crumbs`; the deepest one wins. A crumb `:name` is the route's own `name`. */
export type RouteHandle = { crumbs: Crumb[] };

function useCrumbs(): Crumb[] {
  const matches = useMatches();
  const params = useParams();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as RouteHandle | undefined;
    if (handle?.crumbs) {
      return handle.crumbs.map((crumb) => (crumb.label.startsWith(':') ? { ...crumb, label: params[crumb.label.slice(1)] ?? '' } : crumb));
    }
  }
  return [];
}

export function MainLayout() {
  // Ada Cloud on or off, as the server says: Ada's pages wait until it is read, so they never flash and go.
  const ada = useAdaCloud();
  return (
    <AppShell
      crumbs={useCrumbs()}
      sidebar={
        <Sidebar footer={<UserMenu />}>
          {ada === undefined ? null : (
            <NavGroup label="Ada">
              {ada && (
                <>
                  <NavItem to="/" end icon="home">
                    Home
                  </NavItem>
                  <NavItem to="/models" icon="model">
                    Models
                  </NavItem>
                  <NavItem to="/keys" icon="key">
                    API Keys
                  </NavItem>
                  <NavItem to="/usage" icon="monitor">
                    Usage
                  </NavItem>
                </>
              )}
              {/* The plugins in github.com/glyphh-ai/plugins; Ada's versions are Settings' Releases. */}
              <NavItem to="/marketplace" icon="layers">
                Marketplace
              </NavItem>
            </NavGroup>
          )}
          <StaffNav />
        </Sidebar>
      }
    >
      <Outlet />
    </AppShell>
  );
}

export function SettingsLayout() {
  const ada = useAdaCloud();
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
            <NavItem to="/settings/members" icon="team">
              Members
            </NavItem>
            <NavItem to="/settings/auth" icon="key">
              Auth
            </NavItem>
            {/* Ada's versions (2026-11-21, was the Ada page in the main sidebar). */}
            {ada && (
              <NavItem to="/settings/releases" icon="layers">
                Releases
              </NavItem>
            )}
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
