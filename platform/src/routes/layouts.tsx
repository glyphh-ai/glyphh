import { Outlet, useMatches, useParams } from 'react-router';
import { useAdaCloud } from '@/api/ada';
import { useHosting } from '@/api/queries';
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
    <AppShell crumbs={useCrumbs()} sidebar={<Sidebar footer={<UserMenu />}>{ada === undefined ? null : ada ? <AdaNav /> : <RuntimeNav />}</Sidebar>}>
      <Outlet />
    </AppShell>
  );
}

/** With Ada Cloud on: Ada's pages only, no runtimes. */
function AdaNav() {
  return (
    <NavGroup label="Ada">
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
    </NavGroup>
  );
}

/** With Ada Cloud off: the runtimes, as before. */
function RuntimeNav() {
  // Machines are Glyphh's hosted ones: shown only once the server says it hosts any.
  const hosting = useHosting();
  return (
    <>
      {hosting && (
        <NavItem to="/machines" icon="chip">
          Machines
        </NavItem>
      )}
      <NavGroup label="Runtime">
        <NavItem to="/" end icon="home">
          Runtimes
        </NavItem>
        <NavItem to="/keys" icon="key">
          API Keys
        </NavItem>
        <NavItem to="/usage" icon="monitor">
          Usage
        </NavItem>
        <NavItem to="/logs" icon="logs">
          Logs
        </NavItem>
        <NavItem to="/licence" icon="card">
          Licence
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
