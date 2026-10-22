import { screen, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

const sidebar = () => screen.getByRole('complementary', { name: 'Main' });

describe('with Ada Cloud on', () => {
  beforeEach(() => server.use(...adaFake({ models: [tickets()] }).handlers));

  it('has Ada’s pages only in the sidebar: no runtimes, machines, logs or licence', async () => {
    renderApp('/');
    await within(await screen.findByRole('complementary', { name: 'Main' })).findByRole('link', { name: 'Home' });
    expect(within(sidebar()).getAllByRole('link').map((link) => link.textContent)).toEqual(['Home', 'Models', 'API Keys', 'Usage']);
    expect(await screen.findByRole('heading', { name: 'Home', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('AdaHome');
  });

  it.each(['/logs', '/licence', '/machines', '/getting-started', '/settings/logs', '/settings/licence'])('sends %s Home', async (path) => {
    const { router } = renderApp(path);
    expect(await screen.findByRole('heading', { name: 'Home', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/');
  });

  it('opens Home, not Add a runtime, from the old ?add=1 link', async () => {
    renderApp('/?add=1');
    expect(await screen.findByRole('heading', { name: 'Home', level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByText(/rrotor|runtime/i)).not.toBeInTheDocument();
  });

  it('keeps Billing, Members, Profile and Installs in Settings, and the plan says nothing of runtimes', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Billing' })).toBeInTheDocument();
    const rail = screen.getByRole('complementary', { name: 'Main' });
    for (const name of ['General', 'Billing', 'Members', 'Profile', 'Installs']) expect(within(rail).getByRole('link', { name })).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.queryByText(/runtime node|per node|Sync across runtimes/)).not.toBeInTheDocument();
    for (const fact of ['100,000 precedents', '1,000,000 requests a month', '50 requests a second', 'Then $1 per 10,000 requests']) {
      expect(screen.getByText(fact)).toBeInTheDocument();
    }
    expect(screen.getByText('Requests this month').nextElementSibling).toHaveTextContent('0 of 1,000,000');
  });

  it('chooses a plan by its cloud caps, with no runtimes in it', async () => {
    renderApp('/settings/plans');
    expect(await screen.findByText('Every plan has unlimited members, installs, models and keys. Never priced per seat.')).toBeInTheDocument();
    const facts = async (name: string) => within(await screen.findByRole('region', { name })).getAllByRole('listitem').map((li) => li.textContent);
    expect(await facts('Free')).toEqual(['5,000 precedents', '10,000 requests a month', '5 requests a second']);
    expect(await facts('Team')).toEqual(['1,000,000 precedents', '5,000,000 requests a month', '200 requests a second', 'Then $1 per 10,000 requests']);
    expect((await facts('Enterprise')).slice(0, 2)).toEqual(['Unlimited precedents', 'Unlimited requests']);
    const team = await screen.findByRole('region', { name: 'Team' });
    expect(within(team).queryByText(/runtime|per node/i)).not.toBeInTheDocument();
  });
});

describe('with Ada Cloud off', () => {
  it.each(['/models/new', '/models/tickets'])('has no %s: Models is today’s', async (path) => {
    const { router } = renderApp(path);
    expect(await screen.findByRole('heading', { name: 'Models' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/models');
  });
});
