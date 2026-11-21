import { useEffect } from 'react';
import { Outlet, useMatches, useNavigate, useParams } from 'react-router';
import { catalogOf, catalogs } from '@/games/catalog';
import { AppShell } from '@/layout/AppShell/AppShell';
import { NavGroup, NavItem, Sidebar } from '@/layout/Sidebar/Sidebar';
import type { Crumb } from '@/layout/TopBar/TopBar';
import { UserMenu } from '@/layout/UserMenu/UserMenu';
import { Button } from '@/ui';
import { chooseOrgView, chooseStaffView } from './staffView';
import styles from './admin.module.css';

export type AdminHandle = { crumbs: Crumb[] };

function useAdminCrumbs(): Crumb[] {
  const matches = useMatches();
  const params = useParams();
  for (let i = matches.length - 1; i >= 0; i--) {
    const handle = matches[i]?.handle as AdminHandle | undefined;
    if (handle?.crumbs) {
      return handle.crumbs.map((c) =>
        c.label === ':id' ? { ...c, label: params.id ?? '' } : c.label === ':game' ? { ...c, label: catalogOf(params.id)?.name ?? params.id ?? '' } : c,
      );
    }
  }
  return [];
}

/** What staff see and never see, said on every page of the staff view. */
export function PrivacyNote() {
  return (
    <span className={styles.privacy}>
      Staff see account and usage metadata only: names, counts, plans and times. Never a customer’s precedents, cases, specs or uploaded files. Every
      page you open here is written to the audit log.
    </span>
  );
}

/** The staff view: its own sidebar, and a way back to the person's own org as anyone sees it. */
export function AdminLayout() {
  const navigate = useNavigate();
  useEffect(chooseStaffView, []); // here by choice: signing in opens the staff view again
  const toOrg = () => {
    chooseOrgView();
    navigate('/');
  };
  const footer = (
    <div className={styles.footer}>
      <Button variant="ghost" size="sm" icon="arrowLeft" onClick={toOrg}>
        Your org’s view
      </Button>
      <UserMenu />
    </div>
  );
  return (
    <AppShell crumbs={useAdminCrumbs()} sidebar={<Sidebar footer={footer}>{<AdminNav />}</Sidebar>}>
      <Outlet />
    </AppShell>
  );
}

function AdminNav() {
  return (
    <>
      <NavGroup label="Staff">
        <NavItem to="/admin" end icon="home">
          Dashboard
        </NavItem>
        <NavItem to="/admin/infra" icon="chip">
          Infrastructure
        </NavItem>
        <NavItem to="/admin/events" icon="alert">
          Log alerts
        </NavItem>
      </NavGroup>
      <NavGroup label="Customers">
        <NavItem to="/admin/orgs" icon="team">
          Organisations
        </NavItem>
        <NavItem to="/admin/users" icon="user">
          People
        </NavItem>
      </NavGroup>
      <NavGroup label="Business">
        <NavItem to="/admin/plans" icon="card">
          Plans
        </NavItem>
        <NavItem to="/admin/traffic" icon="eye">
          Traffic
        </NavItem>
        <NavItem to="/admin/marketing" icon="flag">
          Marketing links
        </NavItem>
        <NavItem to="/admin/ada-versions" icon="model">
          Ada versions
        </NavItem>
        <NavItem to="/admin/audit" icon="logs">
          Audit log
        </NavItem>
      </NavGroup>
      <NavGroup label="Games">
        <NavItem to="/admin/games" end icon="home">
          All games
        </NavItem>
        {catalogs.map((c) => (
          <NavItem key={c.id} to={`/admin/games/${c.id}`} icon="flag">
            {c.name}
          </NavItem>
        ))}
      </NavGroup>
    </>
  );
}
