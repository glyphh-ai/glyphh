import { createBrowserRouter, type RouteObject } from 'react-router';
import { adminRoutes } from '@/admin/routes';
import { StaffHome } from '@/admin/StaffGate';
import { RequireSession } from '@/components/RequireSession';
import { AllowPage } from '@/pages/flows/AllowPage';
import { AuthorizePage } from '@/pages/flows/AuthorizePage';
import { LoginPage } from '@/pages/flows/LoginPage';
import { ErrorPage, NotFoundPage } from '@/pages/flows/ResultPages';
import { HomePage } from '@/pages/home/HomePage';
import { MainLayout, type RouteHandle } from './layouts';

/**
 * What is left of the platform since Glyphh's products were retired (2026-11-18): the sign-in, an empty Home in the
 * console's shell, and Glyphh's staff view. Ada Cloud, runtimes and licences, apps, templates, keys, usage, plans,
 * billing and every settings page are gone, with their calls; an address of theirs is "Page not found".
 */
export const routes: RouteObject[] = [
  // Signed-in pages.
  {
    element: (
      <RequireSession>
        <MainLayout />
      </RequireSession>
    ),
    children: [
      {
        index: true,
        element: (
          <StaffHome>
            <HomePage />
          </StaffHome>
        ),
        handle: { crumbs: [{ label: 'Home' }] } satisfies RouteHandle,
      },
    ],
  },
  // Glyphh's staff view (his order, 2026-10-23): staff open it when they sign in.
  adminRoutes,

  // Sign-in and consent: the routes the server sends a browser to.
  { path: 'login', element: <LoginPage /> },
  { path: 'authorize', element: <AuthorizePage /> },
  { path: 'allow', element: <AllowPage /> },
  { path: 'error', element: <ErrorPage /> },
  { path: '*', element: <NotFoundPage /> },
];

export const createRouter = () => createBrowserRouter(routes);
