import { createBrowserRouter, Navigate, useLocation, type RouteObject } from 'react-router';
import { adminRoutes } from '@/admin/routes';
import { StaffHome } from '@/admin/StaffGate';
import { AdaOnly, AdaOr } from '@/components/AdaGate';
import { RequireSession } from '@/components/RequireSession';
import { AdaHome } from '@/pages/ada/AdaHome';
import { AdaKeysPage } from '@/pages/ada/AdaKeysPage';
import { AdaModelsPage } from '@/pages/ada/AdaModelsPage';
import { AdaReleasesPage } from '@/pages/ada/AdaReleasesPage';
import { AdaUsagePage } from '@/pages/ada/AdaUsagePage';
import { ModelPage } from '@/pages/ada/model/ModelPage';
import { NewModelPage } from '@/pages/ada/NewModelPage';
import { MarketplacePage } from '@/pages/marketplace/MarketplacePage';
import { PluginPage } from '@/pages/marketplace/PluginPage';
import { PlansPage } from '@/pages/plans/PlansPage';
import { AllowPage } from '@/pages/flows/AllowPage';
import { AuthorizePage } from '@/pages/flows/AuthorizePage';
import { DeviceApprovePage } from '@/pages/flows/DeviceApprovePage';
import { DevicePage } from '@/pages/flows/DevicePage';
import { LoginPage } from '@/pages/flows/LoginPage';
import { DeviceDonePage, ErrorPage, NotFoundPage } from '@/pages/flows/ResultPages';
import { AuthPage } from '@/pages/settings/AuthPage';
import { BillingPage } from '@/pages/settings/billing/BillingPage';
import { GeneralPage } from '@/pages/settings/GeneralPage';
import { InstallsPage } from '@/pages/settings/InstallsPage';
import { MembersPage } from '@/pages/settings/MembersPage';
import { ProfilePage } from '@/pages/settings/ProfilePage';
import { MainLayout, SettingsLayout, type RouteHandle } from './layouts';

const crumbs = (...labels: string[]): RouteHandle => ({
  crumbs: labels.map((label, i) => ({ label, to: i === 0 && labels.length > 1 ? '/settings/general' : undefined })),
});

/** The crumbs of one of Ada's pages. */
const adaCrumbs = (...rest: RouteHandle['crumbs']): RouteHandle => ({ crumbs: [{ label: 'Ada' }, ...rest] });

/** Paths that moved (some the server sends a browser to); the query string comes along. */
function Moved({ to }: { to: string }) {
  const { search } = useLocation();
  return <Navigate to={`${to}${search}`} replace />;
}

/** A path that moved, a link into the page (`#ada-1-1`) kept. */
function MovedWithHash({ to }: { to: string }) {
  const { search, hash } = useLocation();
  return <Navigate to={`${to}${search}${hash}`} replace />;
}

/** Where a page of Ada's goes while Ada Cloud is off: the one page that needs none of it. */
const WITHOUT_ADA = '/marketplace';

/**
 * Addresses of what Glyphh no longer has (2026-11-24), each with everything under it, so an old link or bookmark
 * lands somewhere. The old Marketplace, the template and bot libraries and the Bots area go to the Marketplace; a
 * plugin can therefore not be opened at /marketplace/models or /marketplace/bots.
 */
export const GONE_TO_MARKETPLACE = ['bots', 'approvals', 'connections', 'projects', 'swarms', 'programs', 'templates', 'marketplace/models', 'marketplace/bots'];
/** rrotor's pages and the GitHub App's go Home (which is the Marketplace while Ada Cloud is off). */
export const GONE_TO_HOME = ['runtimes', 'runtime-keys', 'licence', 'apps', 'artifacts', 'github', 'getting-started', 'machines', 'logs'];
/** Settings pages that are gone, to Home too. */
export const GONE_SETTINGS = ['claude-key', 'github-token', 'licence', 'logs'];

const gone = (paths: string[], to: string): RouteObject[] => paths.map((path) => ({ path: `${path}/*`, element: <Navigate to={to} replace /> }));

export const routes: RouteObject[] = [
  // Signed-in pages. Glyphh is Ada (2026-11-24): Home, Models, API Keys and Usage are Ada Cloud's, and the Marketplace
  // shows the plugins in github.com/glyphh-ai/plugins.
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
            <AdaOr ada={<AdaHome />} off={<Navigate to={WITHOUT_ADA} replace />} />
          </StaffHome>
        ),
        handle: adaCrumbs({ label: 'Home' }),
      },
      {
        path: 'models',
        element: (
          <AdaOnly otherwise={WITHOUT_ADA}>
            <AdaModelsPage />
          </AdaOnly>
        ),
        handle: adaCrumbs({ label: 'Models' }),
      },
      {
        path: 'models/new',
        element: (
          <AdaOnly otherwise={WITHOUT_ADA}>
            <NewModelPage />
          </AdaOnly>
        ),
        handle: adaCrumbs({ label: 'Models', to: '/models' }, { label: 'New model' }),
      },
      {
        path: 'models/:name',
        element: (
          <AdaOnly otherwise={WITHOUT_ADA}>
            <ModelPage />
          </AdaOnly>
        ),
        handle: adaCrumbs({ label: 'Models', to: '/models' }, { label: ':name' }),
      },
      {
        path: 'keys',
        element: (
          <AdaOnly otherwise={WITHOUT_ADA}>
            <AdaKeysPage />
          </AdaOnly>
        ),
        handle: adaCrumbs({ label: 'API Keys' }),
      },
      {
        path: 'usage',
        element: (
          <AdaOnly otherwise={WITHOUT_ADA}>
            <AdaUsagePage />
          </AdaOnly>
        ),
        handle: adaCrumbs({ label: 'Usage' }),
      },
      // Ada's versions moved to Settings as Releases (2026-11-21); the hash (a version's notes) comes along.
      { path: 'ada', element: <MovedWithHash to="/settings/releases" /> },
      // The Marketplace: the plugins in github.com/glyphh-ai/plugins, shown; a plugin is installed in Claude, not here.
      { path: 'marketplace', element: <MarketplacePage />, handle: { crumbs: [{ label: 'Marketplace' }] } },
      {
        path: 'marketplace/:plugin',
        element: <PluginPage />,
        handle: { crumbs: [{ label: 'Marketplace', to: '/marketplace' }, { label: ':plugin' }] },
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
      // Usage moved to the main sidebar (2026-10-20).
      { path: 'usage', element: <Moved to="/usage" /> },
      { path: 'members', element: <MembersPage />, handle: crumbs('Settings', 'Members') },
      { path: 'auth', element: <AuthPage />, handle: crumbs('Settings', 'Auth') },
      { path: 'profile', element: <ProfilePage />, handle: crumbs('Settings', 'Profile') },
      { path: 'installs', element: <InstallsPage />, handle: crumbs('Settings', 'Installs') },
      ...gone(GONE_SETTINGS, '/'),
      // Ada's versions (2026-11-21, was the Ada page in the main sidebar).
      {
        path: 'releases',
        element: (
          <AdaOnly otherwise="/settings/general">
            <AdaReleasesPage />
          </AdaOnly>
        ),
        handle: crumbs('Settings', 'Releases'),
      },
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
  ...gone(GONE_TO_MARKETPLACE, '/marketplace'),
  ...gone(GONE_TO_HOME, '/'),

  // Sign-in and consent: the routes the server sends a browser to.
  { path: 'login', element: <LoginPage /> },
  { path: 'device', element: <DevicePage /> },
  { path: 'device/approve', element: <DeviceApprovePage /> },
  { path: 'device/done', element: <DeviceDonePage /> },
  { path: 'authorize', element: <AuthorizePage /> },
  { path: 'allow', element: <AllowPage /> },
  { path: 'error', element: <ErrorPage /> },
  { path: '*', element: <NotFoundPage /> },
];

export const createRouter = () => createBrowserRouter(routes);
