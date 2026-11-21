import { screen, within } from '@testing-library/react';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server, v1 } from '@/test/server';
import { composeGuideUrl, localCompose } from './InstallRrotor';

const install = () => screen.getByRole('region', { name: 'Install rrotor' });

describe('Runtimes', () => {
  // The page alone: the self-hosted list is tested in SelfRuntimes.test.tsx.
  beforeEach(() => server.use(http.get(v1('/runtimes/self'), () => HttpResponse.json([]))));

  it('is where Home goes with Ada Cloud off, under Runtimes & licences', async () => {
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Runtimes', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/runtimes');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Runtimes & licencesRuntimes');
    expect(screen.getByText(/Glyphh hosts none: it grants their/)).toBeInTheDocument();
  });

  it('says how to install rrotor: the plugin’s rrotor skill, or Docker Compose, and where its licence key goes', async () => {
    const { user } = renderApp('/runtimes');
    await screen.findByRole('heading', { name: 'Install rrotor' });
    const panel = install();
    expect(within(panel).getByText(/ask Claude to “install rrotor”/)).toBeInTheDocument();
    expect(within(panel).getByText('/plugin marketplace add glyphh-ai/glyphh')).toBeInTheDocument();
    expect(within(panel).getByText('/plugin install glyphh@glyphh')).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: 'Docker Compose guide' })).toHaveAttribute('href', composeGuideUrl);
    expect(within(panel).getByText('GLYPHH_LICENSE_KEY')).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: 'Licence' })).toHaveAttribute('href', '/licence');
    await user.click(within(panel).getByRole('button', { name: 'Copy Docker Compose commands' }));
    expect(await navigator.clipboard.readText()).toBe(localCompose);
  });

  it('pastes the compose commands into zsh as they are: no comment lines, the token kept out of the container', () => {
    const lines = localCompose.split('\n');
    expect(lines.some((line) => line.trim().startsWith('#'))).toBe(false);
    expect(lines[0]).toBe('curl -fsSLO https://raw.githubusercontent.com/glyphh-ai/glyphh/main/deploy/compose/docker-compose.local.yml');
    expect(localCompose).toContain('RROTOR_LOCAL_TOKEN_SHA256=');
    expect(localCompose).toContain("tr -d ' \\n'");
    expect(localCompose).toContain('docker compose -f docker-compose.local.yml up -d');
    expect(localCompose).toContain('http://127.0.0.1:7777/mcp');
  });

  it('lists the rrotors linked from the organisation’s own machines, named after the machine', async () => {
    renderApp('/runtimes');
    const list = await screen.findByRole('list', { name: 'Local runtimes' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(1);
    expect(within(list).getByText('studio-mac')).toBeInTheDocument();
    expect(within(list).getByText('Away')).toBeInTheDocument();
    expect(within(list).getByText(/rrotor 1\.4\.2 · last seen .* · 18,240 precedents/)).toBeInTheDocument();
    expect(screen.queryByText('Acme production')).not.toBeInTheDocument(); // self-hosted nodes are listed below
  });

  it('says how to link a local rrotor when none is linked, and shows one online as it links', async () => {
    const { nodes } = await import('@/test/fixtures');
    server.use(http.get(v1('/license/nodes'), () => HttpResponse.json({ ...nodes, count: 0, nodes: [] })));
    renderApp('/runtimes');
    expect(await screen.findByText(/None linked yet/)).toBeInTheDocument();
    expect(screen.getByText('/glyphh link')).toBeInTheDocument();
    const fresh = { ...nodes.nodes[2]!, seen_at: new Date().toISOString() };
    server.use(http.get(v1('/license/nodes'), () => HttpResponse.json({ ...nodes, nodes: [fresh] })));
    renderApp('/runtimes');
    const list = await screen.findByRole('list', { name: 'Local runtimes' });
    expect(within(list).getByText('Online')).toBeInTheDocument();
  });

  it('offers to run rrotor on a server when none is registered, in Add a runtime', async () => {
    const { user, router } = renderApp('/runtimes');
    expect(await screen.findByText('No self-hosted runtime yet')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Run rrotor on a server' }));
    expect(await screen.findByRole('dialog', { name: 'Add a runtime' })).toBeInTheDocument();
    expect(router.state.location.search).toBe('?add=1');
  });

  it('opens Add a runtime from the header, and reads the runtimes again when it closes', async () => {
    let reads = 0;
    server.use(
      http.get(v1('/runtimes/self'), () => {
        reads += 1;
        return HttpResponse.json([]);
      }),
    );
    const { user, router } = renderApp('/runtimes');
    await user.click(await screen.findByRole('button', { name: 'Add a runtime' }));
    const dialog = await screen.findByRole('dialog', { name: 'Add a runtime' });
    expect(within(dialog).queryByText(/Glyphh hosted/)).not.toBeInTheDocument();
    const before = reads;
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(router.state.location.search).toBe('');
    await vi.waitFor(() => expect(reads).toBeGreaterThan(before));
  });

  it.each([
    ['/?add=1', '/runtimes', '?add=1'],
    ['/getting-started', '/runtimes', '?add=1'],
    ['/machines', '/runtimes', ''],
    ['/logs', '/runtimes', ''],
    ['/settings/logs', '/runtimes', ''],
  ])('sends the old %s to %s%s', async (from, path, search) => {
    const { router } = renderApp(from);
    expect(await screen.findByRole('heading', { name: 'Runtimes', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(path);
    expect(router.state.location.search).toBe(search);
    if (search) expect(await screen.findByRole('dialog', { name: 'Add a runtime' })).toBeInTheDocument();
  });

  it('waits for the account, which says whether Ada Cloud is on, before showing either Home', async () => {
    server.use(http.get(v1('/me'), () => new Promise<never>(() => {})));
    renderApp('/');
    expect(await screen.findByLabelText('Loading')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Runtimes' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Home' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('complementary', { name: 'Main' })).queryAllByRole('link')).toHaveLength(0);
  });

  it('says so when Glyphh cannot be reached', async () => {
    server.use(http.get(v1('/runtimes/self'), () => HttpResponse.error()));
    renderApp('/runtimes');
    expect(await screen.findByText('Glyphh could not be reached. Check your connection and try again.')).toBeInTheDocument();
  });
});
