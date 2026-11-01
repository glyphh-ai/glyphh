import { createBrowserRouter, Navigate, useLocation, type RouteObject } from 'react-router';
import { adminRoutes } from '@/admin/routes';
import { StaffHome } from '@/admin/StaffGate';
import { AdaOnly, AdaOr } from '@/components/AdaGate';
import { RequireSession } from '@/components/RequireSession';
import { AdaHome } from '@/pages/ada/AdaHome';
import { AdaKeysPage } from '@/pages/ada/AdaKeysPage';
import { AdaModelsPage } from '@/pages/ada/AdaModelsPage';
import { ArtifactsPage } from '@/pages/artifacts/ArtifactsPage';
import { AdaReleasesPage } from '@/pages/ada/AdaReleasesPage';
import { AdaUsagePage } from '@/pages/ada/AdaUsagePage';
import { ModelPage } from '@/pages/ada/model/ModelPage';
import { NewModelPage } from '@/pages/ada/NewModelPage';
import { KeysPage } from '@/pages/keys/KeysPage';
import { RuntimesPage } from '@/pages/runtimes/RuntimesPage';
import { PlansPage } from '@/pages/plans/PlansPage';
import { AllowPage } from '@/pages/flows/AllowPage';
import { AuthorizePage } from '@/pages/flows/AuthorizePage';
import { DeviceApprovePage } from '@/pages/flows/DeviceApprovePage';
import { DevicePage } from '@/pages/flows/DevicePage';
import { LoginPage } from '@/pages/flows/LoginPage';
import { DeviceDonePage, ErrorPage, GitHubInstalledPage, NotFoundPage } from '@/pages/flows/ResultPages';
import { AuthPage } from '@/pages/settings/AuthPage';
import { BillingPage } from '@/pages/settings/billing/BillingPage';
import { GeneralPage } from '@/pages/settings/GeneralPage';
import { InstallsPage } from '@/pages/settings/InstallsPage';
import { LicencePage } from '@/pages/settings/licence/LicencePage';
import { MembersPage } from '@/pages/settings/MembersPage';
import { ProfilePage } from '@/pages/settings/ProfilePage';
import { UsagePage } from '@/pages/settings/UsagePage';
import { MainLayout, SettingsLayout, type RouteHandle } from './layouts';

const crumbs = (...labels: string[]): RouteHandle => ({
  crumbs: labels.map((label, i) => ({ label, to: i === 0 && labels.length > 1 ? '/settings/general' : undefined })),
});

/** Paths that moved (some the server sends a browser to); the query string comes along. */
function Moved({ to }: { to: string }) {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
}

/** The crumbs of a page in Runtimes & licences. */
const runtimeCrumbs = (label: string): RouteHandle => ({ crumbs: [{ label: 'Runtimes & licences' }, { label }] });

export const routes: RouteObject[] = [
  // Signed-in pages.
  {
    element: (
      <RequireSession>
        <MainLayout />
      </RequireSession>
    ),
    children: [
      // With Ada Cloud on (the server's ada_cloud), Home, Models, API Keys and Usage are Ada's. Runtimes & licences sits
      // beside it in both: the rrotors a person runs themselves and the licence key they run on. Glyphh hosts no
      // runtime (2026-10-31): the old Machines and Logs pages go to Runtimes, and Getting started to its Add a runtime.
      { path: 'runtimes', element: <RuntimesPage />, handle: runtimeCrumbs('Runtimes') },
      { path: 'licence', element: <LicencePage />, handle: runtimeCrumbs('Licence') },
      { path: 'artifacts', element: <ArtifactsPage />, handle: runtimeCrumbs('Artifacts') },
      {
        path: 'runtime-keys',
        element: <AdaOr ada={<KeysPage />} off={<Moved to="/keys" />} />,
        handle: runtimeCrumbs('Runtime keys'),
      },
      { path: 'getting-started', element: <Navigate to="/runtimes?add=1" replace /> },
      { path: 'machines', element: <Navigate to="/runtimes" replace /> },
      { path: 'logs', element: <Navigate to="/runtimes" replace /> },
      {
        index: true,
        element: (
          <StaffHome>
            <AdaOr ada={<AdaHome />} off={<Moved to="/runtimes" />} />
          </StaffHome>
        ),
        handle: { crumbs: [{ label: 'Runtimes & licences' }, { label: 'Runtimes' }], adaCrumbs: [{ label: 'Ada' }, { label: 'Home' }] },
      },
      {
        path: 'keys',
        element: <AdaOr ada={<AdaKeysPage />} off={<KeysPage />} />,
        handle: { crumbs: [{ label: 'Runtimes & licences' }, { label: 'API Keys' }], adaCrumbs:[{ label: 'Ada' }, { label: 'API Keys' }] },
      },
      // Models are Ada Cloud's only: with it off the server serves none, so they go to Runtimes (2026-10-31).
      {
        path: 'models',
        element: (
          <AdaOnly otherwise="/runtimes">
            <AdaModelsPage />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Ada' }, { label: 'Models' }] },
      },
      {
        path: 'models/new',
        element: (
          <AdaOnly otherwise="/runtimes">
            <NewModelPage />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Ada' }, { label: 'Models', to: '/models' }, { label: 'New model' }] },
      },
      {
        path: 'models/:name',
        element: (
          <AdaOnly otherwise="/runtimes">
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
        handle: { crumbs: [{ label: 'Runtimes & licences' }, { label: 'Usage' }], adaCrumbs:[{ label: 'Ada' }, { label: 'Usage' }] },
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
      // Licence and usage moved to the main sidebar (2026-10-20); rrotor's logs are no more (2026-10-31).
      { path: 'licence', element: <Moved to="/licence" /> },
      { path: 'usage', element: <Moved to="/usage" /> },
      { path: 'logs', element: <Navigate to="/runtimes" replace /> },
      { path: 'members', element: <MembersPage />, handle: crumbs('Settings', 'Members') },
      { path: 'auth', element: <AuthPage />, handle: crumbs('Settings', 'Auth') },
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
