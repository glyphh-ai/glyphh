import { createBrowserRouter, Navigate, useLocation, type RouteObject } from 'react-router';
import { HostedOnly } from '@/components/HostedOnly';
import { RequireSession } from '@/components/RequireSession';
import { GettingStartedPage } from '@/pages/getting-started/GettingStartedPage';
import { HomePage } from '@/pages/home/HomePage';
import { KeysPage } from '@/pages/keys/KeysPage';
import { MachinesPage } from '@/pages/machines/MachinesPage';
import { ModelsPage } from '@/pages/models/ModelsPage';
import { PlansPage } from '@/pages/plans/PlansPage';
import { AllowPage } from '@/pages/flows/AllowPage';
import { AuthorizePage } from '@/pages/flows/AuthorizePage';
import { DeviceApprovePage } from '@/pages/flows/DeviceApprovePage';
import { DevicePage } from '@/pages/flows/DevicePage';
import { LoginPage } from '@/pages/flows/LoginPage';
import { DeviceDonePage, ErrorPage, GitHubInstalledPage, NotFoundPage } from '@/pages/flows/ResultPages';
import { BillingPage } from '@/pages/settings/billing/BillingPage';
import { GeneralPage } from '@/pages/settings/GeneralPage';
import { InstallsPage } from '@/pages/settings/InstallsPage';
import { LicencePage } from '@/pages/settings/licence/LicencePage';
import { LogsPage } from '@/pages/settings/logs/LogsPage';
import { MembersPage } from '@/pages/settings/MembersPage';
import { ProfilePage } from '@/pages/settings/ProfilePage';
import { UsagePage } from '@/pages/settings/UsagePage';
import { MainLayout, SettingsLayout, type RouteHandle } from './layouts';

const crumbs = (...labels: string[]): RouteHandle => ({
  crumbs: labels.map((label, i) => ({ label, to: i === 0 && labels.length > 1 ? '/settings/general' : undefined })),
});

/** Paths the server sends a browser to that live under Settings here; the query string comes along. */
function Moved({ to }: { to: string }) {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
}

export const routes: RouteObject[] = [
  // Signed-in pages.
  {
    element: (
      <RequireSession>
        <MainLayout />
      </RequireSession>
    ),
    children: [
      { path: 'getting-started', element: <GettingStartedPage />, handle: { crumbs: [{ label: 'Getting started' }] } },
      {
        path: 'machines',
        element: (
          <HostedOnly>
            <MachinesPage />
          </HostedOnly>
        ),
        handle: { crumbs: [{ label: 'Machines' }] },
      },
      { index: true, element: <HomePage />, handle: { crumbs: [{ label: 'Runtime' }, { label: 'Home' }] } },
      { path: 'keys', element: <KeysPage />, handle: { crumbs: [{ label: 'Runtime' }, { label: 'API Keys' }] } },
      { path: 'models', element: <ModelsPage />, handle: { crumbs: [{ label: 'Ada' }, { label: 'Models' }] } },
    ],
  },
  {
    path: 'settings',
    element: (
      <RequireSession>
        <SettingsLayout />
      </RequireSession>
    ),
    children: [
      { index: true, element: <Navigate to="general" replace /> },
      { path: 'general', element: <GeneralPage />, handle: crumbs('Settings', 'General') },
      { path: 'billing', element: <BillingPage />, handle: crumbs('Settings', 'Billing') },
      { path: 'licence', element: <LicencePage />, handle: crumbs('Settings', 'Licence') },
      { path: 'usage', element: <UsagePage />, handle: crumbs('Settings', 'Usage') },
      { path: 'logs', element: <LogsPage />, handle: crumbs('Settings', 'Logs') },
      { path: 'members', element: <MembersPage />, handle: crumbs('Settings', 'Members') },
      { path: 'profile', element: <ProfilePage />, handle: crumbs('Settings', 'Profile') },
      { path: 'installs', element: <InstallsPage />, handle: crumbs('Settings', 'Installs') },
    ],
  },
  // Choosing a plan: over the whole window, no sidebar.
  {
    path: 'settings/plans',
    element: (
      <RequireSession>
        <PlansPage />
      </RequireSession>
    ),
  },
  { path: 'account', element: <Moved to="/settings/profile" /> },
  { path: 'billing', element: <Moved to="/settings/billing" /> },

  // Sign-in and consent: the routes the server sends a browser to.
  { path: 'login', element: <LoginPage /> },
  { path: 'device', element: <DevicePage /> },
  { path: 'device/approve', element: <DeviceApprovePage /> },
  { path: 'device/done', element: <DeviceDonePage /> },
  { path: 'authorize', element: <AuthorizePage /> },
  { path: 'allow', element: <AllowPage /> },
  { path: 'github', element: <GitHubInstalledPage /> },
  { path: 'error', element: <ErrorPage /> },
  { path: '*', element: <NotFoundPage /> },
];

export const createRouter = () => createBrowserRouter(routes);
