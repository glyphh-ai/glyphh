import { screen, within } from '@testing-library/react';
import { me, runtime } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

const meter = (name: string) => screen.getByText(name, { selector: 'div' }).parentElement!;

describe('Usage', () => {
  it('shows this month’s runtime hours, installs and models against the plan', async () => {
    renderApp('/settings/usage');
    expect(await screen.findByRole('heading', { name: 'Usage' })).toBeInTheDocument();
    expect(await screen.findByText('On Pro.')).toBeInTheDocument();
    await vi.waitFor(() => expect(within(meter('Runtime hours')).getByText('of 50 hours')).toBeInTheDocument());
    expect(within(meter('Runtime hours')).getByText('12')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Runtime hours used' })).toHaveAttribute('aria-valuemax', '50');
    expect(within(meter('Installs')).getByText('of 5 installs')).toBeInTheDocument();
    expect(within(meter('Installs')).getByText('2')).toBeInTheDocument();
    await vi.waitFor(() => expect(within(meter('Models')).getByText('of 3 models')).toBeInTheDocument());
    expect(within(meter('Models')).getByText('1')).toBeInTheDocument();
  });

  it('lists each API key’s calls, most first, with revoked and unused keys marked', async () => {
    renderApp('/settings/usage');
    const list = await screen.findByRole('list', { name: 'API key calls' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows.map((row) => within(row).getByText(/calls?$/).textContent)).toEqual(['1,284 calls', '1 call', '0 calls']);
    expect(within(rows[2]!).getByText('Revoked')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Never used')).toBeInTheDocument();
    expect(within(rows[0]!).getByText(/^Last used /)).toBeInTheDocument();
  });

  it('says there is no limit where the plan sets none', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: { ...me.plan, limits: { members: null, installs: null }, mods: {} } })),
      http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, hours_allowed: null })),
    );
    renderApp('/settings/usage');
    await vi.waitFor(() => expect(within(meter('Runtime hours')).getByText('hours, no limit')).toBeInTheDocument());
    expect(within(meter('Installs')).getByText('installs, no limit')).toBeInTheDocument();
    await vi.waitFor(() => expect(within(meter('Models')).getByText('models, no limit')).toBeInTheDocument());
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('says a count is unavailable when it cannot be read, and shows the refusal', async () => {
    server.use(
      http.get(v1('/runtime'), () => apiError(503, 'E_UNAVAILABLE', 'The runtime is unavailable.')),
      http.get(v1('/runtime/keys'), () => apiError(503, 'E_UNAVAILABLE', 'Keys are unavailable.')),
    );
    renderApp('/settings/usage');
    expect(await screen.findByText('The runtime is unavailable.')).toBeInTheDocument();
    expect(within(meter('Runtime hours')).getByText('Unavailable')).toBeInTheDocument();
    expect(await screen.findByText('Keys are unavailable.')).toBeInTheDocument();
  });

  it('shows each count loading until it is known, and no keys yet', async () => {
    server.use(
      http.get(v1('/models'), () => new Promise<never>(() => {})),
      http.get(v1('/runtime/keys'), () => HttpResponse.json([])),
    );
    renderApp('/settings/usage');
    expect(await screen.findByText('No API keys yet')).toBeInTheDocument();
    expect(within(meter('Models')).getByText('Loading')).toHaveAttribute('aria-busy', 'true');
  });
});

describe('Usage from Billing and the settings rail', () => {
  it('opens from the plan card’s Usage button and the rail', async () => {
    const { user, router } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Usage' }));
    expect(router.state.location.pathname).toBe('/settings/usage');
    const rail = screen.getByRole('complementary', { name: 'Main' });
    expect(within(rail).getByRole('link', { name: 'Usage' })).toHaveAttribute('href', '/settings/usage');
  });
});
