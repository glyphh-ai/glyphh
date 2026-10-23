import type { RouteObject } from 'react-router';
import { RequireSession } from '@/components/RequireSession';
import { AdminLayout, type AdminHandle } from './AdminLayout';
import { RequireStaff } from './StaffGate';
import { AdaVersionsPage } from './pages/AdaVersionsPage';
import { AuditPage } from './pages/AuditPage';
import { DashboardPage } from './pages/DashboardPage';
import { EventsPage } from './pages/EventsPage';
import { InfraPage } from './pages/InfraPage';
import { MarketingPage } from './pages/MarketingPage';
import { OrgPage } from './pages/OrgPage';
import { OrgsPage } from './pages/OrgsPage';
import { PlansPage } from './pages/PlansPage';
import { UsersPage } from './pages/UsersPage';

const crumbs = (...labels: Array<string | [string, string]>): AdminHandle => ({
  crumbs: [{ label: 'Staff', to: '/admin' }, ...labels.map((l) => (typeof l === 'string' ? { label: l } : { label: l[0], to: l[1] }))],
});

/** The staff view (Glyphh's own staff only): its own layout and sidebar under /admin. */
export const adminRoutes: RouteObject = {
  path: 'admin',
  element: (
    <RequireSession>
      <RequireStaff>
        <AdminLayout />
      </RequireStaff>
    </RequireSession>
  ),
  children: [
    { index: true, element: <DashboardPage />, handle: crumbs('Dashboard') },
    { path: 'infra', element: <InfraPage />, handle: crumbs('Infrastructure') },
    { path: 'events', element: <EventsPage />, handle: crumbs('Log alerts') },
    { path: 'orgs', element: <OrgsPage />, handle: crumbs('Organisations') },
    { path: 'orgs/:id', element: <OrgPage />, handle: crumbs(['Organisations', '/admin/orgs'], 'Organisation') },
    { path: 'users', element: <UsersPage />, handle: crumbs('People') },
    { path: 'plans', element: <PlansPage />, handle: crumbs('Plans') },
    { path: 'marketing', element: <MarketingPage />, handle: crumbs('Marketing links') },
    { path: 'ada-versions', element: <AdaVersionsPage />, handle: crumbs('Ada versions') },
    { path: 'audit', element: <AuditPage />, handle: crumbs('Audit log') },
  ],
};
