import { createBrowserRouter, Navigate, useLocation, type RouteObject } from 'react-router';
import { adminRoutes } from '@/admin/routes';
import { StaffHome } from '@/admin/StaffGate';
import { AdaOnly, AdaOr, OffOnly } from '@/components/AdaGate';
import { HostedOnly } from '@/components/HostedOnly';
import { RequireSession } from '@/components/RequireSession';
import { AdaHome } from '@/pages/ada/AdaHome';
import { AdaKeysPage } from '@/pages/ada/AdaKeysPage';
import { AdaModelsPage } from '@/pages/ada/AdaModelsPage';
import { AdaReleasesPage } from '@/pages/ada/AdaReleasesPage';
import { AdaUsagePage } from '@/pages/ada/AdaUsagePage';
import { ModelPage } from '@/pages/ada/model/ModelPage';
import { NewModelPage } from '@/pages/ada/NewModelPage';
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
      // With Ada Cloud on (the server's ada_cloud), the platform is Ada's: Home, Models, API Keys and Usage are Ada's,
      // and nothing of runtimes, machines, the licence, rrotor's logs or self-hosting is reached (each goes Home).
      // Getting started became the Add a runtime dialog on Runtimes (2026-10-20); old links open it there.
      {
        path: 'getting-started',
        element: (
          <OffOnly>
            <Navigate to="/?add=1" replace />
          </OffOnly>
        ),
      },
      {
        path: 'machines',
        element: (
          <OffOnly>
            <HostedOnly>
              <MachinesPage />
            </HostedOnly>
          </OffOnly>
        ),
        handle: { crumbs: [{ label: 'Machines' }] },
      },
      {
        index: true,
        element: (
          <StaffHome>
            <AdaOr ada={<AdaHome />} off={<HomePage />} />
          </StaffHome>
        ),
        handle: { crumbs: [{ label: 'Runtime' }, { label: 'Runtimes' }], adaCrumbs: [{ label: 'Ada' }, { label: 'Home' }] },
      },
      {
        path: 'keys',
        element: <AdaOr ada={<AdaKeysPage />} off={<KeysPage />} />,
        handle: { crumbs: [{ label: 'Runtime' }, { label: 'API Keys' }], adaCrumbs: [{ label: 'Ada' }, { label: 'API Keys' }] },
      },
      {
        path: 'models',
        element: <AdaOr ada={<AdaModelsPage />} off={<ModelsPage />} />,
        handle: { crumbs: [{ label: 'Ada' }, { label: 'Models' }] },
      },
      {
        path: 'models/new',
        element: (
          <AdaOnly otherwise="/models">
            <NewModelPage />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Ada' }, { label: 'Models', to: '/models' }, { label: 'New model' }] },
      },
      {
        path: 'models/:name',
        element: (
          <AdaOnly otherwise="/models">
            <ModelPage />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Ada' }, { label: 'Models', to: '/models' }, { label: ':name' }] },
      },
      {
        path: 'ada',
        element: (
          <AdaOnly otherwise="/">
            <AdaReleasesPage />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Ada' }, { label: 'Ada versions' }] },
      },
      {
        path: 'usage',
        element: <AdaOr ada={<AdaUsagePage />} off={<UsagePage />} />,
        handle: { crumbs: [{ label: 'Runtime' }, { label: 'Usage' }], adaCrumbs: [{ label: 'Ada' }, { label: 'Usage' }] },
      },
      {
        path: 'logs',
        element: (
          <OffOnly>
            <LogsPage />
          </OffOnly>
        ),
        handle: { crumbs: [{ label: 'Runtime' }, { label: 'Logs' }] },
      },
      {
        path: 'licence',
        element: (
          <OffOnly>
            <LicencePage />
          </OffOnly>
        ),
        handle: { crumbs: [{ label: 'Runtime' }, { label: 'Licence' }] },
      },
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
      // Licence, usage and logs moved to the main sidebar (2026-10-20).
      { path: 'licence', element: <Moved to="/licence" /> },
      { path: 'usage', element: <Moved to="/usage" /> },
      { path: 'logs', element: <Moved to="/logs" /> },
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
  // Glyphh's staff view (his order, 2026-10-23): staff open it when they sign in.
  adminRoutes,
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
