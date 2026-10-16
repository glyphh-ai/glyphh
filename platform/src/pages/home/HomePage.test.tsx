import { screen, within } from '@testing-library/react';
import { runtime } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

describe('Home', () => {
  it('shows the runtime: address, state, plan, connector URL and this month’s hours', async () => {
    renderApp('/');
    expect(await screen.findByText('https://chris-7f3a.glyphh.app')).toBeInTheDocument();
    expect(screen.getByText('Running')).toBeInTheDocument();
    expect(await screen.findByText('Pro')).toBeInTheDocument();
    expect(screen.getByText('https://chris-7f3a.glyphh.app/mcp')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('of 50 hours')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Runtime hours used this month' })).toHaveAttribute('aria-valuenow', '12');
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

  it('says when the month’s hours are used up, and cannot start', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, state: 'stopped', paused: true })));
    renderApp('/');
    expect(await screen.findByText('Paused: this month’s hours are used up.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start' })).toBeDisabled();
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

  it('shows the hours without a bar when the plan has no limit', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.json({ ...runtime, hours_allowed: null })));
    renderApp('/');
    expect(await screen.findByText('hours, no limit')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('says so when Glyphh cannot be reached', async () => {
    server.use(http.get(v1('/runtime'), () => HttpResponse.error()));
    renderApp('/');
    expect(await screen.findByText('Glyphh could not be reached. Check your connection and try again.')).toBeInTheDocument();
  });
});
