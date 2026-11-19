import type { RouteObject } from 'react-router';
import { RequireSession } from '@/components/RequireSession';
import { GamePage } from '@/games/GamePage';
import { GamesPage } from '@/games/GamesPage';
import { AdminLayout, type AdminHandle } from './AdminLayout';
import { RequireStaff } from './StaffGate';
import { AuditPage } from './pages/AuditPage';
import { EventsPage } from './pages/EventsPage';
import { TrafficPage } from './pages/TrafficPage';

const crumbs = (...labels: Array<string | [string, string]>): AdminHandle => ({
  crumbs: [{ label: 'Staff', to: '/admin' }, ...labels.map((l) => (typeof l === 'string' ? { label: l } : { label: l[0], to: l[1] }))],
});

/**
 * The staff view (Glyphh's own staff only), under /admin: the games' admin first (his ruling, 2026-11-19: "one admin,
 * games keep their own DBs"), then Glyphh's own traffic, the server's errors and the audit log. The retired
 * products' screens (dashboard, infrastructure, organisations, people, plans, marketing links, Ada versions) are gone.
 */
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
    { index: true, element: <GamesPage />, handle: crumbs('Games') },
    { path: 'games/:id', element: <GamePage />, handle: crumbs(['Games', '/admin'], ':game') },
    { path: 'traffic', element: <TrafficPage />, handle: crumbs('Traffic') },
    { path: 'events', element: <EventsPage />, handle: crumbs('Log alerts') },
    { path: 'audit', element: <AuditPage />, handle: crumbs('Audit log') },
  ],
};
