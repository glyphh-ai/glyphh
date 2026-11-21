import { act, screen, waitFor, within } from '@testing-library/react';
import { botsFake } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

afterEach(() => vi.restoreAllMocks());

describe('the Connections page', () => {
  it('lists the org’s connections with their app, label and date', async () => {
    on();
    renderApp('/connections');
    const list = await screen.findByRole('list', { name: 'Connections' });
    expect(list).toHaveTextContent('Gmail');
    expect(list).toHaveTextContent('chris@example.com · Connected');
    expect(list).toHaveTextContent('Slack');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('BotsConnections');
  });

  it('finds an app, opens its sign-in in a popup and syncs when the popup closes', async () => {
    const fake = on({ connections: [] });
    const popup = { closed: false };
    const open = vi.spyOn(window, 'open').mockReturnValue(popup as Window);
    const { user } = renderApp('/connections');
    expect(await screen.findByText('No connections yet')).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: 'Add connection' })[0]!);
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText('Search apps'), 'not');
    await waitFor(() => expect(within(dialog).getAllByRole('listitem')).toHaveLength(1));
    await user.click(within(dialog).getByRole('button', { name: 'Connect Notion' }));
    await waitFor(() => expect(open).toHaveBeenCalledWith('https://pipedream.test/connect/notion', 'glyphh-connect', expect.any(String)));
    expect(within(dialog).getByRole('status')).toHaveTextContent('Sign in to Notion in the window that opened');
    popup.closed = true;
    await waitFor(() => expect(fake.state.seen).toContain('sync'));
    await user.click(within(dialog).getByRole('button', { name: 'Done' }));
    expect(await screen.findByRole('list', { name: 'Connections' })).toHaveTextContent('Notion');
    expect(fake.state.seen).toEqual(['link notion', 'sync']);
  });

  it('syncs when the window has the focus again, and gives a link when the popup is stopped', async () => {
    const fake = on({ connections: [] });
    vi.spyOn(window, 'open').mockReturnValue(null);
    const { user } = renderApp('/connections');
    await user.click((await screen.findAllByRole('button', { name: 'Add connection' }))[0]!);
    const dialog = await screen.findByRole('dialog');
    await user.click(await within(dialog).findByRole('button', { name: 'Connect Slack' }));
    expect(await within(dialog).findByRole('link', { name: 'Open Slack’s sign-in' })).toHaveAttribute('href', 'https://pipedream.test/connect/slack');
    act(() => {
      window.dispatchEvent(new Event('focus'));
    });
    await waitFor(() => expect(fake.state.seen).toContain('sync'));
    expect(await within(dialog).findByText(/Your connections are up to date/)).toBeInTheDocument();
  });

  it('removes a connection once asked', async () => {
    const fake = on();
    const { user } = renderApp('/connections');
    await user.click(await screen.findByRole('button', { name: 'Remove Slack' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Bots that use it lose its tools.');
    await user.click(within(dialog).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('Slack is removed.')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('list', { name: 'Connections' })).not.toHaveTextContent('Slack'));
    expect(fake.state.seen).toEqual(['remove c-slack']);
  });

  it('says plainly when Pipedream is not set up', async () => {
    on({ off: true });
    renderApp('/connections');
    expect(await screen.findByText('Connections are not set up')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add connection' })).toBeDisabled();
  });
});
