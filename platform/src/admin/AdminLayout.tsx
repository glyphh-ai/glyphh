import { useEffect } from 'react';
import { Outlet, useMatches, useParams } from 'react-router';
import { catalogOf, catalogs } from '@/games/catalog';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar } from '@/layout/Sidebar/Sidebar';
import type { Crumb } from '@/layout/TopBar/TopBar';
import { UserMenu } from '@/layout/UserMenu/UserMenu';
import { chooseStaffView } from './staffView';

export type AdminHandle = { crumbs: Crumb[] };

function useAdminCrumbs(): Crumb[] {
  const matches = useMatches();
  const params = useParams();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as AdminHandle | undefined;
    if (handle?.crumbs) return handle.crumbs.map((c) => (c.label === ':game' ? { ...c, label: catalogOf(params.id)?.name ?? params.id ?? '' } : c));
  }
  return [];
}

/** The staff view: the games, each with its admin, then Glyphh's own pages. */
export function AdminLayout() {
  useEffect(chooseStaffView, []);
  return (
    <AppShell crumbs={useAdminCrumbs()} sidebar={<Sidebar footer={<UserMenu />}>{<AdminNav />}</Sidebar>}>
      <Outlet />
    </AppShell>
  );
}

function AdminNav() {
  return (
    <>
      <NavGroup label="Games">
        <NavItem to="/admin" end icon="home">
          All games
        </NavItem>
        {catalogs.map((c) => (
          <NavItem key={c.id} to={`/admin/games/${c.id}`} icon="flag">
            {c.name}
          </NavItem>
        ))}
      </NavGroup>
      <NavGroup label="Glyphh">
        <NavItem to="/admin/traffic" icon="eye">
          Traffic
        </NavItem>
        <NavItem to="/admin/events" icon="alert">
          Log alerts
        </NavItem>
        <NavItem to="/admin/audit" icon="logs">
          Audit log
        </NavItem>
      </NavGroup>
    </>
  );
}
