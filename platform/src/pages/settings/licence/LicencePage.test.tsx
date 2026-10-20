import { screen, within } from '@testing-library/react';
import { licenceKeys } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';
import { masked, termsText } from './licence';

const live = licenceKeys.keys[0]!;

describe('the licence wording', () => {
  it('masks a key to its first 8 and last 6 characters', () => {
    expect(masked('abcdefgh0123456789uvwxyz')).toBe('abcdefgh…uvwxyz');
    expect(masked('short')).toBe('•••••');
  });

  it('names a key’s terms', () => {
    expect(termsText(live)).toEqual(['3 runtime nodes', '50,000 precedents per node', 'Sync across runtimes']);
    expect(termsText({ max_nodes: null, max_precedents: null, cluster_sync_enabled: false })).toEqual([
      'Unlimited runtime nodes',
      'Unlimited precedents per node',
      'No sync',
    ]);
  });
});

describe('Licence', () => {
  it('shows the current key masked, its terms and expiry; reveals and copies it whole', async () => {
    const { user } = renderApp('/licence');
    const card = await screen.findByRole('region', { name: 'Current licence key' });
    expect(within(card).getByText('Pro')).toBeInTheDocument();
    expect(within(card).getByText('Live')).toBeInTheDocument();
    expect(within(card).getByText('Expires 16 Nov 2026')).toBeInTheDocument();
    for (const text of ['3 runtime nodes', '50,000 precedents per node', 'Sync across runtimes']) expect(within(card).getByText(text)).toBeInTheDocument();
    expect(within(card).getByText(masked(live.key))).toBeInTheDocument();
    expect(within(card).queryByText(live.key)).not.toBeInTheDocument();

    await user.click(within(card).getByRole('button', { name: 'Reveal' }));
    expect(within(card).getByText(live.key)).toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Hide' }));
    expect(within(card).queryByText(live.key)).not.toBeInTheDocument();

    await user.click(within(card).getByRole('button', { name: 'Copy licence key' }));
    expect(await navigator.clipboard.readText()).toBe(live.key);
  });

  it('says the key reaches rrotor on its own, and how to paste it on an air-gapped node', async () => {
    renderApp('/licence');
    expect(await screen.findByRole('heading', { name: 'How it reaches rrotor' })).toBeInTheDocument();
    expect(screen.getByText(/picks up the newest key when it links to Glyphh, and again at its daily heartbeat/)).toBeInTheDocument();
    expect(screen.getByText('GLYPHH_LICENSE_KEY')).toBeInTheDocument();
    expect(screen.getByText('/etc/rrotor/license.key')).toBeInTheDocument();
  });

  it('lists the older keys with their state, masked, each to copy', async () => {
    const { user } = renderApp('/licence');
    const list = await screen.findByRole('list', { name: 'Older licence keys' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]!).getByText('Pro key')).toBeInTheDocument();
    expect(within(rows[0]!).getByText('Expired')).toBeInTheDocument();
    expect(within(rows[0]!).getByText('Issued 16 Sep 2026 · expired 16 Oct 2026')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Team key')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Revoked')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Issued 2 Aug 2026 · revoked 20 Aug 2026 · expired 2 Sep 2026')).toBeInTheDocument();
    expect(within(rows[1]!).getByText(masked(licenceKeys.keys[2]!.key))).toBeInTheDocument();
    await user.click(within(rows[1]!).getByRole('button', { name: /^Copy Team key/ }));
    expect(await navigator.clipboard.readText()).toBe(licenceKeys.keys[2]!.key);
  });

  it('on Free, says Community needs no key, with its limits, and nothing to paste', async () => {
    server.use(...hostingOffHandlers());
    renderApp('/licence');
    const card = await screen.findByRole('region', { name: 'Community' });
    expect(within(card).getByText('Community: no key needed')).toBeInTheDocument();
    for (const text of ['1 runtime node', '5,000 precedents per node', 'No sync']) expect(within(card).getByText(text)).toBeInTheDocument();
    expect(within(card).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
    expect(screen.queryByRole('heading', { name: 'How it reaches rrotor' })).not.toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Older licence keys' })).not.toBeInTheDocument();
  });

  it('on a paid plan with no live key yet, runs as Community until the payment goes through', async () => {
    server.use(http.get(v1('/license/keys'), () => HttpResponse.json({ license_key: null, keys: licenceKeys.keys.slice(1) })));
    renderApp('/licence');
    const card = await screen.findByRole('region', { name: 'Community' });
    expect(within(card).getByText('Running as Community')).toBeInTheDocument();
    expect(within(card).getByText(/issued once your plan’s payment goes through/)).toBeInTheDocument();
    expect(await screen.findByRole('list', { name: 'Older licence keys' })).toBeInTheDocument();
  });

  it('shows the refusal when the keys cannot be read', async () => {
    server.use(http.get(v1('/license/keys'), () => apiError(503, 'E_UNAVAILABLE', 'Keys are unavailable.')));
    renderApp('/licence');
    expect(await screen.findByText('Keys are unavailable.')).toBeInTheDocument();
  });

  it('opens from the main sidebar', async () => {
    renderApp('/');
    const rail = await screen.findByRole('complementary', { name: 'Main' });
    expect(within(rail).getByRole('link', { name: 'Licence' })).toHaveAttribute('href', '/licence');
  });
});
