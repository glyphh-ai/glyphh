import { Outlet, useMatches, useParams } from 'react-router';
import { StaffNav } from '@/admin/StaffGate';
import { useAdaCloud } from '@/api/ada';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar, SidebarBack } from '@/layout/Sidebar/Sidebar';
import type { Crumb } from '@/layout/TopBar/TopBar';
import { UserMenu } from '@/layout/UserMenu/UserMenu';

/**
 * Each route names its own crumbs in `handle.crumbs`, and in `adaCrumbs` where they differ with Ada Cloud on; the
 * deepest one wins. A crumb `:name` is the route's own `name`.
 */
export type RouteHandle = { crumbs: Crumb[]; adaCrumbs?: Crumb[] };

function useCrumbs(): Crumb[] {
  const matches = useMatches();
  const params = useParams();
  const ada = useAdaCloud();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as RouteHandle | undefined;
    if (handle?.crumbs) {
      const crumbs = (ada && handle.adaCrumbs) || handle.crumbs;
      return crumbs.map((crumb) => (crumb.label === ':name' ? { ...crumb, label: params.name ?? '' } : crumb));
    }
  }
  return [];
}

export function MainLayout() {
  // Ada Cloud on or off, as the server says: nothing until it is read, so neither flashes for the other.
  const ada = useAdaCloud();
  return (
    <AppShell
      crumbs={useCrumbs()}
      sidebar={
        <Sidebar footer={<UserMenu />}>
          {ada === undefined ? null : ada ? <AdaNav /> : <RuntimeNav />}
          <StaffNav />
        </Sidebar>
      }
    >
      <Outlet />
    </AppShell>
  );
}

/** With Ada Cloud on: Ada's pages, then Runtimes & licences. */
function AdaNav() {
  return (
    <>
      <NavGroup label="Ada">
        <NavItem to="/" end icon="home">
          Home
        </NavItem>
        <NavItem to="/models" icon="model">
          Models
        </NavItem>
        {/* Ada's own versions, after Models (his order, 2026-10-23). */}
        <NavItem to="/ada" icon="layers">
          Ada
        </NavItem>
        <NavItem to="/keys" icon="key">
          API Keys
        </NavItem>
        <NavItem to="/usage" icon="monitor">
          Usage
        </NavItem>
      </NavGroup>
      {/* The rrotors the org runs itself and the licence key they run on, beside Ada Cloud (2026-10-31). */}
      <NavGroup label="Runtimes & licences">
        <NavItem to="/runtimes" icon="chip">
          Runtimes
        </NavItem>
        <NavItem to="/licence" icon="card">
          Licence
        </NavItem>
        <NavItem to="/runtime-keys" icon="key">
          Runtime keys
        </NavItem>
      </NavGroup>
    </>
  );
}

/** With Ada Cloud off: Runtimes & licences, with the runtimes' keys and usage, then Ada's models. */
function RuntimeNav() {
  return (
    <>
      <NavGroup label="Runtimes & licences">
        <NavItem to="/runtimes" icon="chip">
          Runtimes
        </NavItem>
        <NavItem to="/licence" icon="card">
          Licence
        </NavItem>
        <NavItem to="/keys" icon="key">
          API Keys
        </NavItem>
        <NavItem to="/usage" icon="monitor">
          Usage
        </NavItem>
      </NavGroup>
      <NavGroup label="Ada">
        <NavItem to="/models" icon="model">
          Models
        </NavItem>
      </NavGroup>
    </>
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
