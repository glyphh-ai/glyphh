import { act, screen, waitFor, within } from '@testing-library/react';
import { botsFake } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  localStorage.clear();
});

describe('an app’s page', () => {
  it('connects an app from the catalog, waits with a spinner and lands on its tools', async () => {
    const fake = on();
    const popup = { closed: false, close: vi.fn() };
    const open = vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
    const { user, router } = renderApp('/connections?tab=catalog');
    await user.click(await screen.findByRole('link', { name: /Notion/ }));
    expect(await screen.findByRole('heading', { name: 'Notion' })).toBeInTheDocument();
    expect(screen.getByText('Notion is not connected')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Tools' })).toHaveAttribute('aria-selected', 'false');
    await user.click(screen.getAllByRole('button', { name: 'Connect' })[0]!);
    await waitFor(() => expect(open).toHaveBeenCalledWith('https://pipedream.test/connect/notion', 'glyphh-connect', expect.any(String)));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('status')).toHaveTextContent('Connecting Notion…');
    act(() => {
      window.dispatchEvent(new Event('focus'));
    });
    expect(await screen.findByText('Notion is connected.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(router.state.location.search).toBe('?tab=tools');
    // The Tools tab opens once the connections read again holds Notion; that read lands a moment after the dialog closes.
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Tools' })).toHaveAttribute('aria-selected', 'true'));
    expect(fake.state.seen).toEqual(['link notion', 'sync']);
  });

  it('gives a link when the popup is stopped, and says so when the sign-in closes unfinished', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fake = on({ connections: [] });
    const popup = { closed: false, close: vi.fn() };
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    const { user } = renderApp('/connections/slack');
    await user.click((await screen.findAllByRole('button', { name: 'Connect' }))[0]!);
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByRole('link', { name: 'Open Slack’s sign-in' })).toHaveAttribute('href', 'https://pipedream.test/connect/slack');
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    open.mockReturnValue(popup as unknown as Window);
    await user.click(screen.getAllByRole('button', { name: 'Connect' })[0]!);
    await waitFor(() => expect(fake.state.seen.filter((s) => s === 'link slack')).toHaveLength(2));
    fake.state.pending.length = 0; // the person closes the sign-in without finishing it
    popup.closed = true;
    await act(() => vi.advanceTimersByTimeAsync(6000));
    expect(await screen.findByText(/Slack was not connected/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(fake.state.seen.filter((s) => s === 'link slack')).toHaveLength(3));
  });

  it('shows a connected app’s accounts and its tools, read-only apart, each always allowed, needing approval or blocked on the server', async () => {
    const fake = on();
    const { user } = renderApp('/connections/gmail');
    expect(await screen.findByRole('heading', { name: 'Gmail' })).toBeInTheDocument();
    expect(screen.getByText('Added')).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Accounts' })).toHaveTextContent('chris@example.com');
    expect(screen.getByRole('button', { name: 'Add another account' })).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Tools' }));
    const reads = await screen.findByRole('region', { name: 'Read-only tools' });
    const writes = screen.getByRole('region', { name: 'Write/delete tools' });
    expect(within(reads).getAllByRole('listitem').map((t) => t.textContent)).toEqual([expect.stringContaining('Find email')]);
    expect(within(writes).getAllByRole('listitem')).toHaveLength(2);
    expect(within(reads).getByLabelText('Find email')).toHaveValue('allow');
    // Never set: it needs approval.
    expect(within(writes).getByLabelText('Send email')).toHaveValue('ask');
    expect(within(writes).getByLabelText('All write/delete tools')).toHaveValue('ask');
    await user.selectOptions(within(writes).getByLabelText('Delete email'), 'deny');
    await waitFor(() => expect(within(writes).getByLabelText('All write/delete tools')).toHaveValue('mixed'));
    await waitFor(() => expect(within(writes).getByLabelText('All write/delete tools')).toBeEnabled());
    await user.selectOptions(within(writes).getByLabelText('All write/delete tools'), 'deny');
    await waitFor(() => expect(within(writes).getByLabelText('Send email')).toHaveValue('deny'));
    expect(fake.state.bodies).toEqual([{ 'gmail-delete-email': 'deny' }, { 'gmail-send-email': 'deny', 'gmail-delete-email': 'deny' }]);
    expect(fake.state.connections[0]!.permissions).toEqual({ 'gmail-find-email': 'allow', 'gmail-delete-email': 'deny', 'gmail-send-email': 'deny' });
    expect(screen.queryByText(/kept in this browser/)).not.toBeInTheDocument();
    await user.click(within(writes).getByRole('button', { name: /Write\/delete tools/ }));
    expect(within(writes).queryByRole('listitem')).not.toBeInTheDocument();
  });

  it('removes the last account and goes back to Connections', async () => {
    const fake = on();
    const { user, router } = renderApp('/connections/slack');
    await user.click(await screen.findByRole('button', { name: 'Remove Slack' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Remove' }));
    expect(await screen.findByText('Slack is removed.')).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/connections'));
    expect(fake.state.seen).toEqual(['remove c-slack']);
  });

  it('says when the catalog has no such app, and when connections are off', async () => {
    on();
    renderApp('/connections/nope');
    expect(await screen.findByText('No such app')).toBeInTheDocument();
  });

  it('says when connections are not set up', async () => {
    on({ off: true });
    renderApp('/connections/gmail');
    expect(await screen.findByText(/Connections are not set up/)).toBeInTheDocument();
  });
});
