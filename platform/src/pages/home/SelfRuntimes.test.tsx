import { screen, within } from '@testing-library/react';
import { me, plans, selfRuntimes } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

describe('the self-hosted runtimes on Runtimes', () => {
  it('lists each with its state, version and last heartbeat', async () => {
    renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    const [acme, lab] = within(list).getAllByRole('listitem');
    expect(within(acme!).getByText('Acme production')).toBeInTheDocument();
    expect(within(acme!).getByText('Running')).toBeInTheDocument();
    expect(within(acme!).getByText(/^rrotor\.acme\.com · 1\.4\.2 · last heartbeat /)).toBeInTheDocument();
    expect(within(lab!).getByText('Not seen yet')).toBeInTheDocument();
    expect(within(lab!).getByText('rrotor.lab.acme.com · no heartbeat yet')).toBeInTheDocument();
  });

  it('shows nothing when there are none', async () => {
    server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([])));
    renderApp('/');
    await screen.findByText('https://chris-7f3a.glyphh.app');
    expect(screen.queryByText('Your self-hosted runtimes')).not.toBeInTheDocument();
  });

  it('says so when the list cannot be read', async () => {
    server.use(http.get(v1('/runtimes/self'), () => apiError(500, 'E_INTERNAL', 'The runtimes could not be read.')));
    renderApp('/');
    expect(await screen.findByText('The runtimes could not be read.')).toBeInTheDocument();
  });

  it('rotates a token after asking and shows the new one once', async () => {
    let rotated = '';
    server.use(
      http.post(v1('/runtimes/self/:id/token'), ({ params }) => {
        rotated = String(params.id);
        return HttpResponse.json({ token: 'glyphh_rt_new' });
      }),
    );
    const { user } = renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    await user.click(within(list).getAllByRole('button', { name: 'Rotate token' })[0]!);
    const confirm = screen.getByRole('dialog', { name: 'Rotate this runtime’s token?' });
    await user.click(within(confirm).getByRole('button', { name: 'Rotate' }));
    const shown = await screen.findByRole('dialog', { name: 'The new runtime token' });
    expect(rotated).toBe('rt-self-1');
    expect(within(shown).getByText('glyphh_rt_new')).toBeInTheDocument();
    expect(within(shown).getByText(/set it as RROTOR_RUNTIME_TOKEN for Acme production/)).toBeInTheDocument();
    await user.click(within(shown).getByRole('button', { name: 'Done' }));
    expect(screen.queryByText('glyphh_rt_new')).not.toBeInTheDocument();
  });

  it('shows why a token could not be rotated, and forgets it on cancel', async () => {
    server.use(http.post(v1('/runtimes/self/:id/token'), () => apiError(404, 'E_NOT_FOUND', 'No such runtime.')));
    const { user } = renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    await user.click(within(list).getAllByRole('button', { name: 'Rotate token' })[0]!);
    const confirm = screen.getByRole('dialog', { name: 'Rotate this runtime’s token?' });
    await user.click(within(confirm).getByRole('button', { name: 'Rotate' }));
    expect(await within(confirm).findByText('No such runtime.')).toBeInTheDocument();
    await user.click(within(confirm).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByText('No such runtime.')).not.toBeInTheDocument();
  });

  it('deletes a runtime after asking', async () => {
    let rows = selfRuntimes;
    server.use(
      http.get(v1('/runtimes/self'), () => HttpResponse.json(rows)),
      http.delete(v1('/runtimes/self/:id'), ({ params }) => {
        rows = rows.filter((r) => r.id !== params.id);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { user } = renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    await user.click(within(list).getAllByRole('button', { name: 'Delete' })[1]!);
    const confirm = screen.getByRole('dialog', { name: 'Delete this runtime?' });
    expect(within(confirm).getByText('Lab')).toBeInTheDocument();
    await user.click(within(confirm).getByRole('button', { name: 'Delete' }));
    await vi.waitFor(() => expect(within(list).queryByText('Lab')).not.toBeInTheDocument());
    await user.click(within(list).getByRole('button', { name: 'Delete' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Delete this runtime?' })).getByRole('button', { name: 'Cancel' }));
    expect(within(list).getByText('Acme production')).toBeInTheDocument();
  });

  it('issues an offline licence on Enterprise, for a year by default, and says where it goes', async () => {
    let sent: unknown;
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[4] })),
      http.post(v1('/runtimes/:id/offline-licence'), async ({ request }) => {
        sent = await request.json();
        return HttpResponse.json({ token: 'eyJwYXlsb2FkIjp7fX0', expires_at: '2027-10-18T00:00:00Z' });
      }),
    );
    const { user, client } = renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
    await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[0]!);
    const dialog = screen.getByRole('dialog', { name: 'Issue an offline licence' });
    expect(within(dialog).getByLabelText('Days')).toHaveValue(365);
    await user.click(within(dialog).getByRole('button', { name: 'Issue licence' }));
    const shown = await screen.findByRole('dialog', { name: 'The offline licence' });
    expect(sent).toEqual({ days: 365 });
    expect(within(shown).getByText('eyJwYXlsb2FkIjp7fX0')).toBeInTheDocument();
    expect(within(shown).getByText(/Set it as RROTOR_LICENCE for Acme production.*It expires 18 Oct 2027\./)).toBeInTheDocument();
    await user.click(within(shown).getByRole('button', { name: 'Copy licence' }));
    expect(await navigator.clipboard.readText()).toBe('eyJwYXlsb2FkIjp7fX0');
    await user.click(within(shown).getByRole('button', { name: 'Done' }));
    expect(screen.queryByRole('dialog', { name: 'The offline licence' })).not.toBeInTheDocument();
  });

  it('takes from 1 to 365 days, and shows a refusal', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[4] })),
      http.post(v1('/runtimes/:id/offline-licence'), () => apiError(403, 'E_NOT_IN_PLAN', 'Offline licences are on Enterprise.', { reason: 'offline' })),
    );
    const { user, client } = renderApp('/');
    await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[1]!);
    const dialog = screen.getByRole('dialog', { name: 'Issue an offline licence' });
    const days = within(dialog).getByLabelText('Days');
    await user.clear(days);
    await user.type(days, '400');
    expect(within(dialog).getByText('From 1 to 365 days.')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Issue licence' })).toBeDisabled();
    await user.clear(days);
    await user.type(days, '30');
    await user.click(within(dialog).getByRole('button', { name: 'Issue licence' }));
    expect(await within(dialog).findByText('Offline licences are on Enterprise.')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: 'Issue an offline licence' })).not.toBeInTheDocument();
  });

  it('says offline licences are on Enterprise on other plans, with Talk to us', async () => {
    const { user, client } = renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
    await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[0]!);
    const dialog = screen.getByRole('dialog', { name: 'Offline licences are on Enterprise' });
    expect(within(dialog).queryByLabelText('Days')).not.toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('lists them while Glyphh hosts nothing, and offline licences stay on Enterprise', async () => {
    server.use(...hostingOffHandlers());
    const { user } = renderApp('/');
    const list = await screen.findByRole('list', { name: 'Self-hosted runtimes' });
    expect(within(list).getByText('Acme production')).toBeInTheDocument();
    await user.click(within(list).getAllByRole('button', { name: 'Offline licence' })[0]!);
    expect(await screen.findByRole('dialog', { name: 'Offline licences are on Enterprise' })).toBeInTheDocument();
  });
});
