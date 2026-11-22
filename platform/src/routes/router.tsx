import type { ReactNode } from 'react';
import { createBrowserRouter, Navigate, useLocation, useParams, type RouteObject } from 'react-router';
import { RROTOR_SHOWN } from '@/lib/shelved';
import { adminRoutes } from '@/admin/routes';
import { StaffHome } from '@/admin/StaffGate';
import { AdaOnly, AdaOr } from '@/components/AdaGate';
import { RequireSession } from '@/components/RequireSession';
import { AdaHome } from '@/pages/ada/AdaHome';
import { AdaKeysPage } from '@/pages/ada/AdaKeysPage';
import { AdaModelsPage } from '@/pages/ada/AdaModelsPage';
import { AppsPage } from '@/pages/apps/AppsPage';
import { ApprovalsPage } from '@/pages/bots/ApprovalsPage';
import { BotPage } from '@/pages/bots/BotPage';
import { BotsPage } from '@/pages/bots/BotsPage';
import { SwarmPage } from '@/pages/swarms/SwarmPage';
import { NewSwarmPage, SwarmsPage } from '@/pages/swarms/SwarmsPage';
import { GitHubTokenPage } from '@/pages/settings/GitHubTokenPage';
import { ConnectionPage } from '@/pages/connections/ConnectionPage';
import { ConnectionsPage } from '@/pages/connections/ConnectionsPage';
import { AdaReleasesPage } from '@/pages/ada/AdaReleasesPage';
import { AdaUsagePage } from '@/pages/ada/AdaUsagePage';
import { ModelPage } from '@/pages/ada/model/ModelPage';
import { NewModelPage } from '@/pages/ada/NewModelPage';
import { BotTemplatePage } from '@/pages/templates/BotTemplatePage';
import { MarketplacePage } from '@/pages/templates/MarketplacePage';
import { TemplatePage } from '@/pages/templates/TemplatePage';
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
import { ClaudeKeyPage } from '@/pages/settings/ClaudeKeyPage';
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

/** A path that moved, a link into the page (`#ada-1-1`) kept. */
function MovedWithHash({ to }: { to: string }) {
  const { search, hash } = useLocation();
  return <Navigate to={`${to}${search}${hash}`} replace />;
}

/** A template's old page, at its place in the Marketplace. */
function MovedTemplate() {
  const { name = '' } = useParams();
  return <Navigate to={`/marketplace/models/${encodeURIComponent(name)}`} replace />;
}

/** The crumbs of a page in Runtimes & licences. */
const runtimeCrumbs = (label: string): RouteHandle => ({ crumbs: [{ label: 'Runtimes & licences' }, { label }] });

/**
 * A page of rrotor's. With rrotor switched off (lib/shelved) and Ada Cloud on it lands on Home; with Ada Cloud off
 * the runtimes' pages are all there is, so they stay.
 */
function Shelved({ page }: { page: ReactNode }) {
  return RROTOR_SHOWN ? <>{page}</> : <AdaOr ada={<Navigate to="/" replace />} off={page} />;
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
      // With Ada Cloud on (the server's ada_cloud), Home, Models, API Keys and Usage are Ada's. Runtimes & licences sits
      // beside it in both: the rrotors a person runs themselves and the licence key they run on. Glyphh hosts no
      // runtime (2026-10-31): the old Machines and Logs pages go to Runtimes, and Getting started to its Add a runtime.
      { path: 'runtimes', element: <Shelved page={<RuntimesPage />} />, handle: runtimeCrumbs('Runtimes') },
      { path: 'licence', element: <Shelved page={<LicencePage />} />, handle: runtimeCrumbs('Licence') },
      { path: 'apps', element: <Shelved page={<AppsPage />} />, handle: runtimeCrumbs('Apps') },
      // The first cut's path (2026-11-01); the search (q, type, state, page) comes along.
      { path: 'artifacts', element: <Moved to="/apps" /> },
      {
        path: 'runtime-keys',
        element: <AdaOr ada={RROTOR_SHOWN ? <KeysPage /> : <Navigate to="/" replace />} off={<Moved to="/keys" />} />,
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
      // Ada's versions moved to Settings as Releases (2026-11-21); the hash (a version's notes) comes along.
      { path: 'ada', element: <MovedWithHash to="/settings/releases" /> },
      // The Marketplace (2026-11-21, was Templates): Models (Ada model templates) and Bots (bot templates).
      { path: 'marketplace', element: <AdaOr ada={<Navigate to="models" replace />} off={<Navigate to="bots" replace />} /> },
      {
        path: 'marketplace/models',
        element: (
          <AdaOnly otherwise="/marketplace/bots">
            <MarketplacePage kind="models" />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Marketplace' }, { label: 'Models' }] },
      },
      {
        path: 'marketplace/models/:name',
        element: (
          <AdaOnly otherwise="/marketplace/bots">
            <TemplatePage />
          </AdaOnly>
        ),
        handle: { crumbs: [{ label: 'Marketplace', to: '/marketplace/models' }, { label: ':name' }] },
      },
      { path: 'marketplace/bots', element: <MarketplacePage kind="bots" />, handle: { crumbs: [{ label: 'Marketplace' }, { label: 'Bots' }] } },
      {
        path: 'marketplace/bots/:name',
        element: <BotTemplatePage />,
        handle: { crumbs: [{ label: 'Marketplace', to: '/marketplace/bots' }, { label: ':name' }] },
      },
      { path: 'templates', element: <Moved to="/marketplace/models" /> },
      { path: 'templates/:name', element: <MovedTemplate /> },
      // Bots and the connections they use: every signed-in person's, Ada Cloud on or off (2026-11-21).
      { path: 'bots', element: <BotsPage />, handle: { crumbs: [{ label: 'Bots' }] } },
      { path: 'bots/:name', element: <BotPage />, handle: { crumbs: [{ label: 'Bots', to: '/bots' }, { label: ':name' }] } },
      { path: 'approvals', element: <ApprovalsPage />, handle: { crumbs: [{ label: 'Bots' }, { label: 'Approvals' }] } },
      { path: 'swarms', element: <SwarmsPage />, handle: { crumbs: [{ label: 'Bots' }, { label: 'Swarms' }] } },
      { path: 'swarms/new', element: <NewSwarmPage />, handle: { crumbs: [{ label: 'Swarms', to: '/swarms' }, { label: 'New swarm' }] } },
      { path: 'swarms/:name', element: <SwarmPage />, handle: { crumbs: [{ label: 'Swarms', to: '/swarms' }, { label: ':name' }] } },
      { path: 'connections', element: <ConnectionsPage />, handle: { crumbs: [{ label: 'Bots' }, { label: 'Connections' }] } },
      {
        path: 'connections/:name',
        element: <ConnectionPage />,
        handle: { crumbs: [{ label: 'Bots' }, { label: 'Connections', to: '/connections' }, { label: ':name' }] },
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
      { path: 'claude-key', element: <ClaudeKeyPage />, handle: crumbs('Settings', 'Claude key') },
      { path: 'github-token', element: <GitHubTokenPage />, handle: crumbs('Settings', 'GitHub token') },
      { path: 'profile', element: <ProfilePage />, handle: crumbs('Settings', 'Profile') },
      { path: 'installs', element: <InstallsPage />, handle: crumbs('Settings', 'Installs') },
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
