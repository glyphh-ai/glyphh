import { screen, within } from '@testing-library/react';
import { manyRuntimeKeys, runtimeKeys } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

const rows = () => within(screen.getByRole('list', { name: 'API keys' })).getAllByRole('listitem');

describe('API Keys, searched and paged', () => {
  it('searches by name once typing pauses, with the query in the URL, and says when nothing matches', async () => {
    const { user, router } = renderApp('/keys');
    await screen.findByRole('list', { name: 'API keys' });
    expect(rows()).toHaveLength(3);
    await user.type(screen.getByLabelText('Search'), 'bot');
    await vi.waitFor(() => expect(router.state.location.search).toBe('?q=bot'));
    await vi.waitFor(() => expect(rows()).toHaveLength(1));
    expect(within(rows()[0]!).getByText('Support bot')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing here');
    // The search settles after the last keystroke: wait for the whole query, not a partial one's empty state.
    expect(await screen.findByText('No key matches “nothing here”.')).toBeInTheDocument();
    expect(screen.getByText('Nothing matches')).toBeInTheDocument();
  });

  it('opens on the page the URL names, and pages through 24 at a time', async () => {
    server.use(http.get(v1('/runtime/keys'), () => HttpResponse.json(manyRuntimeKeys)));
    const { user, router } = renderApp('/keys?page=2');
    await screen.findByRole('list', { name: 'API keys' });
    expect(rows()).toHaveLength(6);
    expect(within(rows()[0]!).getByText('Worker 25')).toBeInTheDocument();
    const pager = screen.getByRole('navigation', { name: 'Pages' });
    expect(within(pager).getByText('25–30 of 30')).toBeInTheDocument();
    expect(within(pager).getByRole('button', { name: 'Next' })).toBeDisabled();
    await user.click(within(pager).getByRole('button', { name: 'Previous' }));
    await vi.waitFor(() => expect(rows()).toHaveLength(24));
    expect(router.state.location.search).toBe('?page=1');
    expect(within(screen.getByRole('navigation', { name: 'Pages' })).getByText('1–24 of 30')).toBeInTheDocument();
    expect(within(screen.getByRole('navigation', { name: 'Pages' })).getByRole('button', { name: 'Previous' })).toBeDisabled();
    // A search starts again at the first page, and narrows the count.
    await user.type(screen.getByLabelText('Search'), 'worker 3');
    await vi.waitFor(() => expect(rows()).toHaveLength(2));
    expect(router.state.location.search).toBe('?q=worker+3');
    expect(rows().map((row) => row.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('Worker 3'), expect.stringContaining('Worker 30')]));
  });
});

describe('API Keys', () => {
  it('lists keys, live and revoked', async () => {
    renderApp('/keys');
    const list = await screen.findByRole('list', { name: 'API keys' });
    expect(within(list).getByText('Billing worker')).toBeInTheDocument();
    expect(within(list).getByText(/^Made 2 Oct 2026 · expires 2 Oct 2027 · 1,284 calls · last used /)).toBeInTheDocument();
    expect(within(list).getByText('Expired')).toBeInTheDocument();
    expect(within(list).getByText(/^Made 9 Oct 2026 · expired 12 Oct 2026 · 1 call · last used /)).toBeInTheDocument();
    expect(within(list).getByText('Made 12 Sep 2026 · revoked 1 Oct 2026 · not used yet')).toBeInTheDocument();
    expect(within(list).getByText('Revoked')).toBeInTheDocument();
    // Only a live key can be revoked: the expired and the revoked ones already stopped working.
    expect(within(list).getAllByRole('button', { name: 'Revoke' })).toHaveLength(1);
    expect(within(list).getAllByRole('button', { name: 'Delete' })).toHaveLength(2);
  });

  it('makes a key and shows it once', async () => {
    let sent: unknown;
    server.use(
      http.post(v1('/runtime/keys'), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json(
          { id: 'k-9', name: 'Deploy bot', created_at: '2026-10-16T10:00:00Z', expires_at: '2027-01-14T10:00:00Z', revoked_at: null, key: 'glyphh_rk_abc123' },
          { status: 201 },
        );
      }),
    );
    const { user } = renderApp('/keys');
    await user.click(await screen.findByRole('button', { name: 'New API key' }));
    const dialog = screen.getByRole('dialog', { name: 'New API key' });
    expect(within(dialog).getByRole('button', { name: 'Make key' })).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Name'), 'Deploy bot');
    const expiry = within(dialog).getByLabelText('Expires after');
    expect(expiry).toHaveValue('30');
    await user.selectOptions(expiry, '90 days');
    // The self-hosted runtime it calls: the first, until another is chosen.
    const runtime = within(dialog).getByLabelText('Runtime');
    expect(runtime).toHaveValue('rt-self-1');
    await user.selectOptions(runtime, 'Lab');
    await user.click(within(dialog).getByRole('button', { name: 'Make key' }));

    const made = await screen.findByRole('dialog', { name: 'Your new API key' });
    expect(sent).toEqual({ name: 'Deploy bot', runtime_id: 'rt-self-2', expires_in_days: 90 });
    expect(within(made).getByText('glyphh_rk_abc123')).toBeInTheDocument();
    expect(within(made).getByText('Copy it now and keep it somewhere safe. You won’t see it again. It expires 14 Jan 2027.')).toBeInTheDocument();
    await user.click(within(made).getByRole('button', { name: 'Done' }));
    expect(screen.queryByText('glyphh_rk_abc123')).not.toBeInTheDocument();
  });

  it('shows why a key could not be made', async () => {
    server.use(http.post(v1('/runtime/keys'), () => apiError(404, 'E_NOT_FOUND', 'Start your runtime first.')));
    const { user } = renderApp('/keys');
    await user.click(await screen.findByRole('button', { name: 'New API key' }));
    await user.type(screen.getByLabelText('Name'), 'x');
    await user.click(screen.getByRole('button', { name: 'Make key' }));
    expect(await screen.findByText('Start your runtime first.')).toBeInTheDocument();
  });

  it('revokes a key after asking', async () => {
    let revoked = '';
    server.use(
      http.delete(v1('/runtime/keys/:id'), ({ params }) => {
        revoked = String(params.id);
        return HttpResponse.json({ ...runtimeKeys[0], revoked_at: '2026-10-16T10:00:00Z' });
      }),
    );
    const { user } = renderApp('/keys');
    const list = await screen.findByRole('list', { name: 'API keys' });
    await user.click(within(list).getAllByRole('button', { name: 'Revoke' })[0]!);
    const confirm = screen.getByRole('dialog', { name: 'Revoke this API key?' });
    await user.click(within(confirm).getByRole('button', { name: 'Revoke' }));
    await vi.waitFor(() => expect(revoked).toBe('k-1'));
  });

  it('explains what keys are for when there are none', async () => {
    server.use(http.get(v1('/runtime/keys'), () => HttpResponse.json([])));
    renderApp('/keys');
    expect(await screen.findByText('No API keys yet')).toBeInTheDocument();
  });

  it('leaves the key alone when the person cancels, and forgets the last refusal', async () => {
    let calls = 0;
    server.use(
      http.delete(v1('/runtime/keys/:id'), () => {
        calls += 1;
        return apiError(409, 'E_CONFLICT', 'That key is in use.');
      }),
    );
    const { user } = renderApp('/keys');
    const list = await screen.findByRole('list', { name: 'API keys' });
    await user.click(within(list).getAllByRole('button', { name: 'Revoke' })[0]!);
    const confirm = screen.getByRole('dialog', { name: 'Revoke this API key?' });
    await user.click(within(confirm).getByRole('button', { name: 'Revoke' }));
    expect(await within(confirm).findByText('That key is in use.')).toBeInTheDocument();
    await user.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(within(list).getAllByRole('button', { name: 'Revoke' })[0]!);
    expect(screen.getByRole('dialog', { name: 'Revoke this API key?' })).toBeInTheDocument();
    expect(screen.queryByText('That key is in use.')).not.toBeInTheDocument();
    expect(calls).toBe(1);
  });

  it('shows the server’s refusal when the keys cannot be read', async () => {
    server.use(http.get(v1('/runtime/keys'), () => apiError(404, 'E_NOT_FOUND', 'Start your runtime first.')));
    renderApp('/keys');
    expect(await screen.findByText('Start your runtime first.')).toBeInTheDocument();
  });
});

describe('API key expiry', () => {
  it('offers a week to a year, or never', async () => {
    const { user } = renderApp('/keys');
    await user.click(await screen.findByRole('button', { name: 'New API key' }));
    const options = within(screen.getByLabelText('Expires after')).getAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(['7 days', '30 days', '60 days', '90 days', '1 year', 'Never']);
  });

  it('warns before making a key that never expires, and makes it with no expiry', async () => {
    let sent: unknown;
    server.use(
      http.post(v1('/runtime/keys'), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ id: 'k-8', name: 'Forever', created_at: '2026-10-16T10:00:00Z', expires_at: null, revoked_at: null, key: 'glyphh_rk_never' }, { status: 201 });
      }),
    );
    const { user } = renderApp('/keys');
    await user.click(await screen.findByRole('button', { name: 'New API key' }));
    await user.type(screen.getByLabelText('Name'), 'Forever');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Expires after'), 'Never');
    expect(screen.getByRole('alert')).toHaveTextContent('This key never expires. If it leaks, it works until you revoke it.');
    await user.click(screen.getByRole('button', { name: 'Make key' }));
    expect(await screen.findByText('Copy it now and keep it somewhere safe. You won’t see it again. It never expires.')).toBeInTheDocument();
    expect(sent).toEqual({ name: 'Forever', runtime_id: 'rt-self-1' });
  });

  it('asks for a self-hosted runtime first when there is none: a key calls one', async () => {
    server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([])));
    const { user } = renderApp('/keys');
    await user.click(await screen.findByRole('button', { name: 'New API key' }));
    const dialog = screen.getByRole('dialog', { name: 'New API key' });
    expect(await within(dialog).findByText(/A key calls a self-hosted runtime at its address/)).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'Runtimes' })).toHaveAttribute('href', '/runtimes');
    await user.type(within(dialog).getByLabelText('Name'), 'Deploy bot');
    expect(within(dialog).getByRole('button', { name: 'Make key' })).toBeDisabled();
  });

  it('marks a key that never expires', async () => {
    server.use(
      http.get(v1('/runtime/keys'), () =>
        HttpResponse.json([{ id: 'k-8', name: 'Forever', created_at: '2026-10-16T10:00:00Z', expires_at: null, revoked_at: null, calls: 0, last_used_at: null }]),
      ),
    );
    renderApp('/keys');
    expect(await screen.findByText('Never expires')).toBeInTheDocument();
    expect(screen.getByText('Made 16 Oct 2026 · not used yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Revoke' })).toBeInTheDocument();
  });

  it('deletes a revoked key after asking', async () => {
    let deleted = '';
    server.use(
      http.delete(v1('/runtime/keys/:id/record'), ({ params }) => {
        deleted = String(params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderApp('/keys');
    const list = await screen.findByRole('list', { name: 'API keys' });
    await user.click(within(list).getAllByRole('button', { name: 'Delete' })[1]!);
    const confirm = screen.getByRole('dialog', { name: 'Delete this API key?' });
    expect(within(confirm).getByText('Old script')).toBeInTheDocument();
    await user.click(within(confirm).getByRole('button', { name: 'Delete' }));
    await vi.waitFor(() => expect(deleted).toBe('k-3'));
  });

  it('keeps the key when the person cancels the delete', async () => {
    const { user } = renderApp('/keys');
    const list = await screen.findByRole('list', { name: 'API keys' });
    await user.click(within(list).getAllByRole('button', { name: 'Delete' })[0]!);
    await user.click(within(screen.getByRole('dialog', { name: 'Delete this API key?' })).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
