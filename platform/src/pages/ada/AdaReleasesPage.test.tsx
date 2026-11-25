import { screen, waitFor, within } from '@testing-library/react';
import type { UserEvent } from '@testing-library/user-event';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

/** Tickets on ada-1-0 (deprecated), claims on ada-1-1 (the latest stable), triage on the beta. */
function on() {
  const models = [tickets(), { ...tickets(), name: 'claims', id: 'm-claims', version: 4, precedents: 90, ada: 'ada-1-1' }, { ...tickets(), name: 'triage', id: 'm-triage', version: 1, ada: 'ada-1-2-beta' }];
  const fake = adaFake({ models });
  server.use(...fake.handlers);
  return fake;
}

const card = async (name: string) => screen.findByRole('region', { name });

/** Opens a version's card from its head, and gives the card back. */
async function open(user: UserEvent, name: string) {
  const region = await card(name);
  await user.click(within(region).getByRole('button', { expanded: false }));
  return region;
}

describe('the Releases page', () => {
  it('is in Settings, and the old Ada page and its links come to it', async () => {
    on();
    const { user, router } = renderApp('/settings/general');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    await user.click(await within(sidebar).findByRole('link', { name: 'Releases' }));
    expect(router.state.location.pathname).toBe('/settings/releases');
    expect(await screen.findByRole('heading', { name: 'Releases', level: 1 })).toBeInTheDocument();
    expect(within(sidebar).getByRole('link', { name: 'Releases' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('SettingsReleases');

    const moved = renderApp('/ada#ada-1-1');
    await waitFor(() => expect(moved.router.state.location.pathname).toBe('/settings/releases'));
    expect(moved.router.state.location.hash).toBe('#ada-1-1');
  });

  it('is gone from the main sidebar', async () => {
    on();
    renderApp('/models');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    await within(sidebar).findByRole('link', { name: 'Models' });
    expect(within(sidebar).queryByRole('link', { name: 'Ada' })).not.toBeInTheDocument();
  });

  it('lists every version newest first, all collapsed to name, status and date, each opening and closing', async () => {
    on();
    const { user } = renderApp('/settings/releases');
    await card('ada-1-1');
    expect(screen.getAllByRole('region').map((r) => r.getAttribute('id'))).toEqual(['ada-1-2-beta', 'ada-1-1', 'ada-1-0', 'ada-0-9']);
    for (const region of screen.getAllByRole('region')) expect(within(region).getByRole('button')).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByText('Better calibrated answers.')).not.toBeInTheDocument();

    const beta = await card('ada-1-2-beta');
    expect(within(beta).getByText('Beta')).toBeInTheDocument();
    expect(beta).toHaveTextContent('Released 23 Oct 2026');
    const stable = await card('ada-1-1');
    expect(within(stable).getByText('Stable')).toBeInTheDocument();
    expect(within(stable).getByText('Default for new models')).toBeInTheDocument();
    expect(within(beta).queryByText('Default for new models')).not.toBeInTheDocument();
    expect(within(await card('ada-1-0')).getByText('Deprecated, ends 18 Apr 2027')).toBeInTheDocument();
    expect(within(await card('ada-0-9')).getByText('Retired')).toBeInTheDocument();

    await open(user, 'ada-1-2-beta');
    expect(beta).toHaveTextContent('Changes answers from ada-1-1: backtest a model before you move it.');
    expect(beta).toHaveTextContent('A beta is never the default');
    await user.click(within(beta).getByRole('button', { expanded: true }));
    expect(beta).not.toHaveTextContent('A beta is never the default');

    const old = await open(user, 'ada-1-0');
    expect(old).toHaveTextContent('On 18 Apr 2027, Glyphh moves any model still on it to the latest stable.');
    expect(await open(user, 'ada-0-9')).toHaveTextContent('The first version.');
  });

  it('opens the version a link names', async () => {
    on();
    renderApp('/settings/releases#ada-1-1');
    const stable = await card('ada-1-1');
    expect(within(stable).getByRole('button')).toHaveAttribute('aria-expanded', 'true');
    expect(within(stable).getByText('Better calibrated answers.')).toBeInTheDocument();
    expect(within(await card('ada-1-0')).getByRole('button')).toHaveAttribute('aria-expanded', 'false');
  });

  it('shows the release notes as prose, the kernel only in its details line', async () => {
    on();
    const { user } = renderApp('/settings/releases');
    const stable = await open(user, 'ada-1-1');
    expect(within(stable).getByText('Better calibrated answers.')).toBeInTheDocument();
    expect(within(stable).getByText('how sure').tagName).toBe('STRONG');
    expect(within(stable).getByText('calibrate_by').tagName).toBe('CODE');
    const beta = await open(user, 'ada-1-2-beta');
    expect(within(within(beta).getAllByRole('list')[0]!).getAllByRole('listitem').map((li) => li.textContent)).toEqual(['Within noise on German Credit', 'Try it on your own backtest first']);
    expect(within(stable).getByText(/^Kernel 3\.13\.0/)).toBeInTheDocument();
    expect(screen.getAllByText(/3\.13\.0/)).toHaveLength(1);
    expect(await open(user, 'ada-1-0')).toHaveTextContent('Kernel 3.12.2 · also named ada-1-0-beta · deprecated 20 Oct 2026 · ends 18 Apr 2027');
  });

  it('counts the org’s models on each, and links each to its backtest and upgrade', async () => {
    on();
    const { user } = renderApp('/settings/releases');
    const old = await open(user, 'ada-1-0');
    expect(await within(old).findByRole('heading', { name: '1 of your models runs it' })).toBeInTheDocument();
    const list = within(old).getByRole('list', { name: 'Models on ada-1-0' });
    expect(within(list).getByRole('link', { name: 'tickets' })).toHaveAttribute('href', '/models/tickets');
    expect(within(list).getByRole('link', { name: 'Backtest and upgrade' })).toHaveAttribute('href', '/models/tickets?tab=versions&upgrade=');
    expect(within(await open(user, 'ada-0-9')).getByRole('heading', { name: 'None of your models run it' })).toBeInTheDocument();
    expect(within(await open(user, 'ada-1-2-beta')).getByRole('link', { name: 'triage' })).toBeInTheDocument();
  });

  it('opens a model’s upgrade flow from its link', async () => {
    on();
    const { user, router } = renderApp('/settings/releases');
    const old = await open(user, 'ada-1-0');
    await user.click(await within(old).findByRole('link', { name: 'Backtest and upgrade' }));
    expect(router.state.location.pathname).toBe('/models/tickets');
    expect(await screen.findByRole('dialog', { name: 'Upgrade Ada' })).toBeInTheDocument();
  });

  it('shows the server’s refusal', async () => {
    on();
    server.use(http.get('*/api/ada/v1/ada', () => apiError(503, 'E_UNAVAILABLE', 'Ada is restarting.')));
    renderApp('/settings/releases');
    expect(await screen.findByText('Ada is restarting.')).toBeInTheDocument();
  });
});
