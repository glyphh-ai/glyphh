import { screen, waitFor } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';
import { GONE_SETTINGS, GONE_TO_HOME, GONE_TO_MARKETPLACE } from './router';

// What Glyphh no longer has (2026-11-24): an old link or bookmark lands on a page that is there.
const toMarketplace = [
  ...GONE_TO_MARKETPLACE.map((path) => `/${path}`),
  '/bots/triage',
  '/bots?rail=connections&add=1',
  '/connections/slack?tab=catalog',
  '/projects/new',
  '/projects/launch?run=r1',
  '/swarms/launch',
  '/programs/p1/runs',
  '/templates/agentic-memory',
  '/marketplace/models/agentic-memory',
  '/marketplace/bots/resume-screener',
];
const toHome = [
  ...GONE_TO_HOME.map((path) => `/${path}`),
  ...GONE_SETTINGS.map((path) => `/settings/${path}`),
  '/runtimes?add=1',
  '/runtimes/rt-self-1',
  '/apps?state=draft',
  '/github?installed=chris-t',
  '/licence/keys',
];

describe('addresses of what is gone', () => {
  beforeEach(() => server.use(...adaFake({ models: [tickets()] }).handlers));

  it.each(toMarketplace)('%s goes to the Marketplace', async (path) => {
    const { router } = renderApp(path);
    expect(await screen.findByRole('heading', { name: 'Marketplace', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/marketplace');
    expect(router.state.location.search).toBe('');
  });

  it.each(toHome)('%s goes Home', async (path) => {
    const { router } = renderApp(path);
    expect(await screen.findByRole('heading', { name: /^Good (morning|afternoon|evening)/, level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/');
    expect(router.state.location.search).toBe('');
  });

  it('replaces the old address, so Back does not come back to it', async () => {
    const { router } = renderApp('/models');
    await screen.findByRole('heading', { name: 'Models', level: 1 });
    await router.navigate('/bots/triage');
    await waitFor(() => expect(router.state.location.pathname).toBe('/marketplace'));
    await router.navigate(-1);
    await waitFor(() => expect(router.state.location.pathname).toBe('/models'));
  });

  it('still opens a plugin, and still says so at an address that never was', async () => {
    const plugin = renderApp('/marketplace/resume-screener');
    expect(await screen.findByRole('heading', { name: 'resume-screener', level: 1 })).toBeInTheDocument();
    plugin.unmount();
    renderApp('/nope');
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
  });
});

describe('addresses of what is gone, with Ada Cloud off', () => {
  it.each(['/runtimes', '/licence', '/github', '/settings/claude-key', '/bots'])('%s ends at the Marketplace', async (path) => {
    const { router } = renderApp(path);
    expect(await screen.findByRole('heading', { name: 'Marketplace', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/marketplace');
  });
});
