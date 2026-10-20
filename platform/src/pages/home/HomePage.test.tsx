import { screen, within } from '@testing-library/react';
import { runtime } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

describe('Home', () => {
  // The hosted runtime alone: the self-hosted list is tested with Getting started.
  beforeEach(() => server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([]))));

  it('shows the runtime: address, state, plan, connector URL and its hosting cost this month', async () => {
    renderApp('/');
    expect(await screen.findByText('https://chris-7f3a.glyphh.app')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(await screen.findByText('Pro')).toBeInTheDocument();
    expect(screen.getByText('https://chris-7f3a.glyphh.app/mcp')).toBeInTheDocument();
    expect(await screen.findByText('$4.12')).toBeInTheDocument();
    expect(screen.getByText('hosting so far')).toBeInTheDocument();
    expect(screen.queryByText(/hours/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
  });

  it('copies the connector URL', async () => {
    const { user } = renderApp('/');
    const [headerButton] = await screen.findAllByRole('button', { name: 'Copy connector URL' });
    await user.click(headerButton!);
    expect(await navigator.clipboard.readText()).toBe('https://chris-7f3a.glyphh.app/mcp');
    expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
  });

  it('stops a running runtime and shows it stopped', async () => {
    let state = 'online';
    server.use(
      http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state })),
      http.post(v1('/runtime/stop'), () => {
        state = 'stopped';
        return HttpResponse.json({ ...runtime, state });
      }),
    );
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Stop' }));
    expect(await screen.findByText('Stopped')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument();
  });

  it('offers to start when there is no runtime yet', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state: 'none', address: null, runtime_id: null })));
    renderApp('/');
    expect(await screen.findByText('No runtime yet')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start your runtime' })).toBeInTheDocument();
    expect(screen.queryByText('Connect Claude')).not.toBeInTheDocument();
  });

  it('shows the server’s refusal when starting fails', async () => {
    server.use(
      http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state: 'stopped' })),
      http.post(v1('/runtime/start'), () => apiError(503, 'E_UNAVAILABLE', 'Hosting is off right now.')),
    );
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Start' }));
    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText('Hosting is off right now.')).toBeInTheDocument();
    expect(within(alert).getByText('Trace trace-123')).toBeInTheDocument();
  });

  it('says plainly when the plan has no room for the runtime to start, with the way to Billing', async () => {
    server.use(
      http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state: 'stopped' })),
      http.post(v1('/runtime/start'), () => apiError(403, 'E_LIMIT', 'Free has no hosted machines.', { reason: 'machines' })),
    );
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Start' }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Your plan has no room for this machine, so it stays stopped.');
    expect(within(alert).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
  });

  it('starts a runtime for the first time', async () => {
    let started = false;
    server.use(
      http.get(v1('/runtime'), () => HttpResponse.json(started ? runtime : { ...runtime, state: 'none', address: null, runtime_id: null })),
      http.post(v1('/runtime/start'), () => {
        started = true;
        return HttpResponse.json(runtime);
      }),
    );
    const { user } = renderApp('/');
    await user.click(await screen.findByRole('button', { name: 'Start your runtime' }));
    expect(await screen.findByText('Running')).toBeInTheDocument();
    expect(started).toBe(true);
  });

  it('says the address is not ready while the runtime is still being made', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state: 'stopped', address: null })));
    renderApp('/');
    expect(await screen.findByText('Address not ready yet')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy address' })).not.toBeInTheDocument();
    expect(screen.queryByText('Connect Claude')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy connector URL' })).not.toBeInTheDocument();
  });

  it('shows a dash for the cost until the hosting is read', async () => {
    server.use(http.get(v1('/me'), () => new Promise<never>(() => {})));
    renderApp('/');
    expect(await screen.findByText('hosting so far')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('says so when Glyphh cannot be reached', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.error()));
    renderApp('/');
    expect(await screen.findByText('Glyphh could not be reached. Check your connection and try again.')).toBeInTheDocument();
  });
});

describe('Home while Glyphh hosts nothing', () => {
  // The hosted runtime alone: the self-hosted list is tested with Getting started.
  beforeEach(() => server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([]))));

  it('offers no hosted runtime to start: running rrotor yourself, from Getting started', async () => {
    server.use(...hostingOffHandlers());
    const { user, router } = renderApp('/');
    expect(await screen.findByText('No runtime yet')).toBeInTheDocument();
    expect(screen.getByText(/Run it with Docker Compose, Helm or Terraform, free on every plan\./)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start your runtime' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('main')).queryByRole('link', { name: 'Machines' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Run rrotor yourself' }));
    expect(router.state.location.pathname).toBe('/getting-started');
  });

  it('shows a machine made before hosting went off without its cost, and no Start', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state: 'stopped' })), ...hostingOffHandlers());
    renderApp('/');
    expect(await screen.findByText('Stopped')).toBeInTheDocument();
    await screen.findByText('Free');
    expect(screen.queryByText('hosting so far')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('main')).queryByRole('link', { name: 'Machines' })).not.toBeInTheDocument();
  });
});
