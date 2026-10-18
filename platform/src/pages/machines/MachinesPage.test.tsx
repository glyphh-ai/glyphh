import { screen, within } from '@testing-library/react';
import type { Machine } from '@/api/types';
import { me, machines, plans } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

const warning =
  'Deleting Experiments destroys the machine and its disk: every model, version, precedent and file on it. Fly keeps daily snapshots for 5 days; Glyphh keeps no other backup. Type Experiments to confirm.';

/** A fake server holding the list, so each write shows up on the next read. */
function liveMachines(start: Machine[] = machines) {
  let rows = structuredClone(start);
  const sent: Array<{ method: string; path: string; body?: unknown }> = [];
  const set = (id: string, state: Machine['state']) => {
    rows = rows.map((m) => (m.id === id ? { ...m, state } : m));
    return HttpResponse.json(rows.find((m) => m.id === id));
  };
  server.use(
    http.get(v1('/runtimes'), () => HttpResponse.json(rows)),
    http.post(v1('/runtimes'), async ({ request }) => {
      const body = (await request.json()) as { name: string; size: Machine['size'] };
      sent.push({ method: 'POST', path: '/runtimes', body });
      const made: Machine = { ...machines[0]!, id: 'rt-new', ...body, address: 'https://chris-new.glyphh.app', month_seconds: 0 };
      rows = [...rows, made];
      return HttpResponse.json(made, { status: 201 });
    }),
    http.post(v1('/runtimes/:id/:action'), ({ params }) => {
      sent.push({ method: 'POST', path: `/runtimes/${params.id}/${params.action}` });
      return set(String(params.id), params.action === 'stop' ? 'stopped' : 'online');
    }),
    http.delete(v1('/runtimes/:id'), ({ params, request }) => {
      sent.push({ method: 'DELETE', path: `/runtimes/${params.id}${new URL(request.url).search}` });
      rows = rows.filter((m) => m.id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return sent;
}

const card = (name: string) => screen.findByRole('listitem', { name });

describe('Machines', () => {
  it('comes after Getting started in the sidebar, and Home links to it', async () => {
    const { user } = renderApp('/');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    expect(within(sidebar).getAllByRole('link')[1]).toHaveAccessibleName('Machines');
    await user.click(await within(screen.getByRole('main')).findByRole('link', { name: 'Machines' }));
    expect(await screen.findByRole('heading', { name: 'Machines', level: 1 })).toBeInTheDocument();
    expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText('Machines')).toHaveAttribute('aria-current', 'page');
  });

  it('lists each machine: name, size, state, address, connector URL and this month’s hours', async () => {
    const { user } = renderApp('/machines');
    const main = await card('Main');
    expect(within(main).getByRole('heading', { name: 'Main' })).toBeInTheDocument();
    expect(within(main).getByText('Running')).toBeInTheDocument();
    expect(within(main).getByText('Small')).toBeInTheDocument();
    expect(within(main).getByText('https://chris-7f3a.glyphh.app')).toBeInTheDocument();
    expect(within(main).getByText('https://chris-7f3a.glyphh.app/mcp')).toBeInTheDocument();
    expect(within(main).getByText('12 hours this month · made 1 Aug 2026')).toBeInTheDocument();
    await user.click(within(main).getByRole('button', { name: 'Copy address' }));
    expect(await navigator.clipboard.readText()).toBe('https://chris-7f3a.glyphh.app');
    await user.click(within(main).getByRole('button', { name: 'Copy connector URL' }));
    expect(await navigator.clipboard.readText()).toBe('https://chris-7f3a.glyphh.app/mcp');

    const experiments = await card('Experiments');
    expect(within(experiments).getByText('Stopped')).toBeInTheDocument();
    expect(within(experiments).getByText('Large')).toBeInTheDocument();
    expect(within(experiments).getByRole('button', { name: 'Start' })).toBeEnabled();
    expect(within(experiments).queryByRole('button', { name: 'Restart' })).not.toBeInTheDocument();
  });

  it('starts, stops and restarts each machine by its id', async () => {
    const sent = liveMachines();
    const { user } = renderApp('/machines');
    const experiments = await card('Experiments');
    await user.click(within(experiments).getByRole('button', { name: 'Start' }));
    expect(await within(experiments).findByText('Running')).toBeInTheDocument();
    await user.click(within(experiments).getByRole('button', { name: 'Restart' }));
    await user.click(within(experiments).getByRole('button', { name: 'Stop' }));
    expect(await within(experiments).findByText('Stopped')).toBeInTheDocument();
    expect(sent.map((s) => s.path)).toEqual(['/runtimes/rt-2b8e41/start', '/runtimes/rt-2b8e41/restart', '/runtimes/rt-2b8e41/stop']);
  });

  it('cannot start a machine whose month’s hours are used up', async () => {
    server.use(http.get(v1('/runtimes'), () => HttpResponse.json([{ ...machines[1]!, paused: true }])));
    renderApp('/machines');
    const experiments = await card('Experiments');
    expect(within(experiments).getByRole('button', { name: 'Start' })).toBeDisabled();
    expect(within(experiments).getByText(/this month’s hours are used up/)).toBeInTheDocument();
    expect(within(experiments).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
  });

  it('shows the server’s refusal on the machine it was for', async () => {
    server.use(http.post(v1('/runtimes/:id/restart'), () => apiError(503, 'E_UNAVAILABLE', 'Fly is not answering.')));
    const { user } = renderApp('/machines');
    const main = await card('Main');
    await user.click(within(main).getByRole('button', { name: 'Restart' }));
    expect(await within(main).findByText('Fly is not answering.')).toBeInTheDocument();
  });

  it('makes a machine with a name and one of the three sizes', async () => {
    const sent = liveMachines();
    const { user } = renderApp('/machines');
    await user.click(await screen.findByRole('button', { name: 'New machine' }));
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    const make = within(dialog).getByRole('button', { name: 'Make machine' });
    expect(make).toBeDisabled();
    expect(within(dialog).getByRole('radio', { name: /^Small/ })).toBeChecked();
    expect(within(dialog).getByRole('radio', { name: /^Small/ })).toHaveAccessibleName(/1 shared CPU.*1 GB RAM.*3 GB disk/);
    expect(within(dialog).getByRole('radio', { name: /^Medium/ })).toHaveAccessibleName(/2 shared CPUs.*4 GB RAM.*10 GB disk/);
    expect(within(dialog).getByRole('radio', { name: /^Large/ })).toHaveAccessibleName(/2 performance CPUs.*8 GB RAM.*20 GB disk/);
    await user.type(within(dialog).getByLabelText('Name'), ' Staging ');
    await user.click(within(dialog).getByRole('radio', { name: /^Medium/ }));
    await user.click(make);
    expect(await card('Staging')).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'New machine' })).not.toBeInTheDocument();
    expect(sent).toEqual([{ method: 'POST', path: '/runtimes', body: { name: 'Staging', size: 'medium' } }]);
  });

  it('shows the plan’s rate on each size card', async () => {
    const { user } = renderApp('/machines');
    await user.click(await screen.findByRole('button', { name: 'New machine' }));
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    expect(await within(dialog).findByText('$8.71 / month')).toBeInTheDocument();
    expect(within(dialog).getByRole('radio', { name: /^Medium/ })).toHaveAccessibleName(/\$33\.01 \/ month/);
    expect(within(dialog).getByRole('radio', { name: /^Large/ })).toHaveAccessibleName(/\$117 \/ month/);
    expect(dialog).toHaveAccessibleDescription(/billed by the second while it runs/);
  });

  it('on Enterprise, each size card says its rate is set in the contract', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3] })));
    const { user, client } = renderApp('/machines');
    await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
    await user.click(await screen.findByRole('button', { name: 'New machine' }));
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    expect(within(dialog).getAllByText('Set in your contract.')).toHaveLength(3);
    expect(within(dialog).queryByText(/\$/)).not.toBeInTheDocument();
  });

  it('on Free, New machine says hosting is on Pro and Team, with their rates and Upgrade', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[0] })), http.get(v1('/runtimes'), () => HttpResponse.json([])));
    const { user, router, client } = renderApp('/machines');
    expect(await screen.findByText('No machines yet')).toBeInTheDocument();
    await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
    await user.click(within(screen.getByRole('main')).getAllByRole('button', { name: 'New machine' })[0]!);
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    expect(await within(dialog).findByText(/Glyphh hosts machines on Pro and Team\. Upgrade to make one\./)).toBeInTheDocument();
    expect(within(dialog).queryByLabelText('Name')).not.toBeInTheDocument();
    const table = await within(dialog).findByRole('table', { name: 'Hosted machine rates' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Size', 'Pro', 'Team']);
    expect(within(dialog).getByRole('link', { name: 'Getting started' })).toHaveAttribute('href', '/getting-started');
    await user.click(within(dialog).getByRole('button', { name: 'Upgrade' }));
    expect(router.state.location.pathname).toBe('/settings/plans');
  });

  it('on Free, asks a member to ask their admin, with no Upgrade', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member', plan: plans[0] })),
      http.get(v1('/rates'), () => apiError(503, 'E_UNAVAILABLE', 'Rates are unavailable.')),
    );
    const { user, client } = renderApp('/machines');
    await vi.waitFor(() => expect(client.getQueryData(['me'])).toBeDefined());
    await user.click(screen.getByRole('button', { name: 'New machine' }));
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    expect(await within(dialog).findByText(/Ask your admin to upgrade\./)).toBeInTheDocument();
    expect(await within(dialog).findByText('Rates are unavailable.')).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: 'Upgrade' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog', { name: 'New machine' })).not.toBeInTheDocument();
  });

  it('says plainly when the plan has no room for another machine, with the way to Billing', async () => {
    server.use(http.post(v1('/runtimes'), () => apiError(403, 'E_LIMIT', 'Pro allows 3 machines.', { reason: 'machines' })));
    const { user } = renderApp('/machines');
    await user.click(await screen.findByRole('button', { name: 'New machine' }));
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    await user.type(within(dialog).getByLabelText('Name'), 'Fourth');
    await user.click(within(dialog).getByRole('button', { name: 'Make machine' }));
    const alert = await within(dialog).findByRole('alert');
    expect(alert).toHaveTextContent('Your plan has no room for another machine. Delete one, or move to a bigger plan.');
    expect(within(alert).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
  });

  it('shows any other refusal in the server’s words', async () => {
    server.use(http.post(v1('/runtimes'), () => apiError(403, 'E_LIMIT', 'Pro allows 5 installs.', { reason: 'installs' })));
    const { user } = renderApp('/machines');
    await user.click(await screen.findByRole('button', { name: 'New machine' }));
    const dialog = screen.getByRole('dialog', { name: 'New machine' });
    await user.type(within(dialog).getByLabelText('Name'), 'Fourth');
    await user.click(within(dialog).getByRole('button', { name: 'Make machine' }));
    expect(await within(dialog).findByText('Pro allows 5 installs.')).toBeInTheDocument();
    expect(within(dialog).queryByRole('link', { name: 'Billing' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: 'New machine' })).not.toBeInTheDocument();
  });

  it('deletes a machine only once its name is typed, warning that the disk goes with it', async () => {
    const sent = liveMachines();
    const { user } = renderApp('/machines');
    await user.click(within(await card('Experiments')).getByRole('button', { name: 'Delete' }));
    const dialog = screen.getByRole('dialog', { name: 'Delete this machine?' });
    expect(dialog).toHaveAccessibleDescription(warning);
    const confirm = within(dialog).getByRole('button', { name: 'Delete machine' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Machine name'), 'experiments{Enter}');
    expect(confirm).toBeDisabled();
    expect(sent).toEqual([]);
    await user.clear(within(dialog).getByLabelText('Machine name'));
    await user.type(within(dialog).getByLabelText('Machine name'), 'Experiments');
    await user.click(confirm);
    await vi.waitFor(() => expect(screen.queryByRole('listitem', { name: 'Experiments' })).not.toBeInTheDocument());
    expect(sent).toEqual([{ method: 'DELETE', path: '/runtimes/rt-2b8e41?confirm=Experiments' }]);
    expect(screen.queryByRole('dialog', { name: 'Delete this machine?' })).not.toBeInTheDocument();
  });

  it('shows why a machine was not deleted, and forgets it on cancel', async () => {
    server.use(http.delete(v1('/runtimes/:id'), () => apiError(422, 'E_INVALID', 'The name does not match.', { reason: 'confirm' })));
    const { user } = renderApp('/machines');
    await user.click(within(await card('Main')).getByRole('button', { name: 'Delete' }));
    const dialog = screen.getByRole('dialog', { name: 'Delete this machine?' });
    await user.type(within(dialog).getByLabelText('Machine name'), 'Main');
    await user.click(within(dialog).getByRole('button', { name: 'Delete machine' }));
    expect(await within(dialog).findByText('The name does not match.')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog', { name: 'Delete this machine?' })).not.toBeInTheDocument();
    expect(screen.getByRole('listitem', { name: 'Main' })).toBeInTheDocument();
  });

  it('offers to make the first one when there are none', async () => {
    server.use(http.get(v1('/runtimes'), () => HttpResponse.json([])));
    const { user } = renderApp('/machines');
    expect(await screen.findByText('No machines yet')).toBeInTheDocument();
    expect(within(screen.getByRole('main')).getByRole('link', { name: 'Getting started' })).toHaveAttribute('href', '/getting-started');
    await user.click(within(screen.getByRole('main')).getAllByRole('button', { name: 'New machine' })[1]!);
    expect(screen.getByRole('dialog', { name: 'New machine' })).toBeInTheDocument();
  });

  it('shows a machine with no address yet, and says so when the list cannot be read', async () => {
    server.use(http.get(v1('/runtimes'), () => HttpResponse.json([{ ...machines[0]!, address: null, state: 'offline' }])));
    renderApp('/machines');
    const main = await card('Main');
    expect(within(main).getByText('Address not ready yet')).toBeInTheDocument();
    expect(within(main).getByText('Offline')).toBeInTheDocument();
    expect(within(main).queryByRole('button', { name: 'Copy connector URL' })).not.toBeInTheDocument();
  });

  it('says so when the machines cannot be read', async () => {
    server.use(http.get(v1('/runtimes'), () => apiError(500, 'E_INTERNAL', 'The machines could not be read.')));
    renderApp('/machines');
    expect(await screen.findByText('The machines could not be read.')).toBeInTheDocument();
  });
});
