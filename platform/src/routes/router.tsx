import { createBrowserRouter, Navigate, useLocation, type RouteObject } from 'react-router';
import { AuditPage } from '@/admin/pages/AuditPage';
import { EventsPage } from '@/admin/pages/EventsPage';
import { TrafficPage } from '@/admin/pages/TrafficPage';
import { RequireStaff } from '@/admin/StaffGate';
import { RequireSession } from '@/components/RequireSession';
import { GamePage } from '@/games/GamePage';
import { GamesPage } from '@/games/GamesPage';
import { AllowPage } from '@/pages/flows/AllowPage';
import { AuthorizePage } from '@/pages/flows/AuthorizePage';
import { LoginPage } from '@/pages/flows/LoginPage';
import { ErrorPage, NotFoundPage } from '@/pages/flows/ResultPages';
import { ConsoleLayout, type RouteHandle } from './layouts';

const crumbs = (...labels: Array<string | [string, string]>): RouteHandle => ({
  crumbs: labels.map((l) => (typeof l === 'string' ? { label: l } : { label: l[0], to: l[1] })),
});

/** The old staff view's addresses (/admin, /admin/...) go to the same page at the root. */
export function OldAdminRedirect() {
  const { pathname, search, hash } = useLocation();
  return <Navigate to={`${pathname.replace(/^\/admin/, '') || '/'}${search}${hash}`} replace />;
}

/**
 * The platform is Glyphh's staff console, the games' admin at the root (his yes, 2026-11-19: "platform.glyphh.ai opens
 * straight to the games admin"). Game players never come here: their accounts live on each game's site. The sign-in
 * routes stay where the server sends a browser (/authorize, /allow, /error; the tokens come back to /auth/callback).
 */
export const routes: RouteObject[] = [
  {
    element: (
      <RequireSession>
        <RequireStaff>
          <ConsoleLayout />
        </RequireStaff>
      </RequireSession>
    ),
    children: [
      { index: true, element: <GamesPage />, handle: crumbs('Games') },
      { path: 'games/:id', element: <GamePage />, handle: crumbs(['Games', '/'], ':game') },
      { path: 'traffic', element: <TrafficPage />, handle: crumbs('Traffic') },
      { path: 'events', element: <EventsPage />, handle: crumbs('Log alerts') },
      { path: 'audit', element: <AuditPage />, handle: crumbs('Audit log') },
    ],
  },
  { path: 'admin/*', element: <OldAdminRedirect /> },

  // Sign-in and consent: the routes the server sends a browser to.
  { path: 'login', element: <LoginPage /> },
  { path: 'authorize', element: <AuthorizePage /> },
  { path: 'allow', element: <AllowPage /> },
  { path: 'error', element: <ErrorPage /> },
  { path: '*', element: <NotFoundPage /> },
];

export const createRouter = () => createBrowserRouter(routes);
