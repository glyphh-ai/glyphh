import { Outlet, useMatches, useParams } from 'react-router';
import { catalogOf, catalogs } from '@/games/catalog';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar } from '@/layout/Sidebar/Sidebar';
import type { Crumb } from '@/layout/TopBar/TopBar';
import { UserMenu } from '@/layout/UserMenu/UserMenu';

/** Each route names its own crumbs in `handle.crumbs`; the deepest one wins. `:game` is the game's name. */
export type RouteHandle = { crumbs: Crumb[] };

function useCrumbs(): Crumb[] {
  const matches = useMatches();
  const params = useParams();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as RouteHandle | undefined;
    if (handle?.crumbs) return handle.crumbs.map((c) => (c.label === ':game' ? { ...c, label: catalogOf(params.id)?.name ?? params.id ?? '' } : c));
  }
  return [];
}

/** The console's shell: the games, each with its admin, then Glyphh's own pages, and the person's menu. */
export function ConsoleLayout() {
  return (
    <AppShell crumbs={useCrumbs()} sidebar={<Sidebar footer={<UserMenu />}>{<ConsoleNav />}</Sidebar>}>
      <Outlet />
    </AppShell>
  );
}

function ConsoleNav() {
  return (
    <>
      <NavGroup label="Games">
        <NavItem to="/" end icon="home">
          All games
        </NavItem>
        {catalogs.map((c) => (
          <NavItem key={c.id} to={`/games/${c.id}`} icon="flag">
            {c.name}
          </NavItem>
        ))}
      </NavGroup>
      <NavGroup label="Glyphh">
        <NavItem to="/traffic" icon="eye">
          Traffic
        </NavItem>
        <NavItem to="/events" icon="alert">
          Log alerts
        </NavItem>
        <NavItem to="/audit" icon="logs">
          Audit log
        </NavItem>
      </NavGroup>
    </>
  );
}
