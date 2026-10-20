import { screen, within } from '@testing-library/react';
import { me, nodes, plans } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

const meter = (name: string) => screen.getByText(name, { selector: 'div' }).parentElement!;
const free = { ...me, plan: plans[0]!, precedents: { used: 3_200, limit: 5_000 }, hosting: { month: '2026-10', month_to_date_cents: 0, machines: [] } };

describe('Usage', () => {
  it('shows the fullest node’s precedents against the plan’s per node, and hosting this month so far', async () => {
    renderApp('/usage');
    expect(await screen.findByRole('heading', { name: 'Usage' })).toBeInTheDocument();
    expect(await screen.findByText('On Pro.')).toBeInTheDocument();
    expect(within(meter('Precedents')).getByText('18,240')).toBeInTheDocument();
    expect(within(meter('Precedents')).getByText('of 50,000 on the fullest node')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Precedents on the fullest node' })).toHaveAttribute('aria-valuemax', '50000');
    expect(within(meter('Hosting')).getByText('$12.17')).toBeInTheDocument();
    expect(within(meter('Hosting')).getByText('this month so far')).toBeInTheDocument();
  });

  it('lists each hosted machine’s cost this month, most first', async () => {
    renderApp('/usage');
    const list = await screen.findByRole('list', { name: 'Hosting by machine' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows.map((row) => row.textContent)).toEqual(['ExperimentsLarge$8.05', 'MainSmall$4.12']);
  });

  it('says there is no limit on a plan without one, and no machines this month', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3], precedents: { used: 2_500_000, limit: null }, hosting: { month: '2026-10', month_to_date_cents: 0, machines: [] } })));
    renderApp('/usage');
    expect(await screen.findByText('on the fullest node, no limit')).toBeInTheDocument();
    expect(screen.getByText('2,500,000')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar', { name: 'Precedents on the fullest node' })).not.toBeInTheDocument();
    expect(screen.getByText('No hosted machines this month')).toBeInTheDocument();
  });

  it('on Free, shows the fullest node against Community’s 5,000, and hosting is on Pro and Team', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json(free)));
    renderApp('/usage');
    expect(await screen.findByText('On Free.')).toBeInTheDocument();
    expect(within(meter('Precedents')).getByText('of 5,000 on the fullest node')).toBeInTheDocument();
    expect(await within(meter('Hosting')).findByText(/Hosting is on Pro and Team\./)).toBeInTheDocument();
    expect(within(meter('Hosting')).getByRole('link', { name: 'Billing' })).toHaveAttribute('href', '/settings/billing');
    expect(screen.queryByRole('list', { name: 'Hosting by machine' })).not.toBeInTheDocument();
  });

  it('shows the refusal when the usage cannot be read', async () => {
    server.use(
      http.get(v1('/me'), () => apiError(503, 'E_UNAVAILABLE', 'Usage is unavailable.')),
      http.get(v1('/runtime/keys'), () => apiError(503, 'E_UNAVAILABLE', 'Keys are unavailable.')),
    );
    renderApp('/usage');
    expect(await screen.findByText('Usage is unavailable.')).toBeInTheDocument();
    expect(await screen.findByText('Keys are unavailable.')).toBeInTheDocument();
  });

  it('shows the usage loading until it is known, and no keys yet', async () => {
    server.use(
      http.get(v1('/me'), () => new Promise<never>(() => {})),
      http.get(v1('/runtime/keys'), () => HttpResponse.json([])),
    );
    renderApp('/usage');
    expect(await screen.findByText('No API keys yet')).toBeInTheDocument();
    expect(screen.getAllByLabelText('Loading').length).toBeGreaterThan(0);
  });

  it('lists each API key’s calls, most first, with revoked and unused keys marked', async () => {
    renderApp('/usage');
    const list = await screen.findByRole('list', { name: 'API key calls' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows.map((row) => within(row).getByText(/calls?$/).textContent)).toEqual(['1,284 calls', '1 call', '0 calls']);
    expect(within(rows[2]!).getByText('Revoked')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Never used')).toBeInTheDocument();
    expect(within(rows[0]!).getByText(/^Last used /)).toBeInTheDocument();
  });

});

describe('Usage’s runtime nodes', () => {
  it('counts the runtime nodes against the plan’s', async () => {
    renderApp('/usage');
    const count = await screen.findByText('Runtime nodes', { selector: 'div' });
    expect(within(count.parentElement!).getByText('3')).toBeInTheDocument();
    expect(within(count.parentElement!).getByText('of 3')).toBeInTheDocument();
    expect(within(count.parentElement!).queryByText('Over the plan')).not.toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Runtime nodes' })).toHaveAttribute('aria-valuemax', '3');
  });

  it('lists each node: its name or its runtime’s, role, runtime, version, last seen and precedents against the plan’s per node', async () => {
    renderApp('/usage');
    const list = await screen.findByRole('list', { name: 'Runtime nodes' });
    const rows = within(list).getAllByRole('listitem');
    expect(rows).toHaveLength(3);
    expect(within(rows[0]!).getByText('rrotor-1')).toBeInTheDocument();
    expect(within(rows[0]!).getByText('Head')).toBeInTheDocument();
    expect(within(rows[0]!).getByText(/^Acme production · 1\.4\.2 · last seen /)).toBeInTheDocument();
    expect(within(rows[0]!).getByText('12,050 of 50,000 precedents')).toBeInTheDocument();
    expect(within(rows[1]!).getByText('Follower')).toBeInTheDocument();
    expect(within(rows[2]!).getByText('Main')).toBeInTheDocument();
    expect(within(rows[2]!).getByText(/^Hosted · 1\.4\.2 · last seen /)).toBeInTheDocument();
    expect(within(rows[2]!).getByText('18,240 of 50,000 precedents')).toBeInTheDocument();
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });

  it('says when the org is over the plan, never blocking, and marks a full node', async () => {
    const extra = { ...nodes.nodes[0]!, node_id: 'rrotor-3', role: 'follower' as const, precedents: 50_000 };
    server.use(http.get(v1('/license/nodes'), () => HttpResponse.json({ count: 4, max_nodes: 3, over: true, nodes: [...nodes.nodes, extra] })));
    renderApp('/usage');
    const note = await screen.findByRole('note');
    expect(note).toHaveTextContent('4 nodes on a plan with 3 runtime nodes: over the plan. Nothing is stopped; remove a node or change plan.');
    expect(within(note).getByRole('link', { name: 'change plan' })).toHaveAttribute('href', '/settings/plans');
    expect(within(screen.getByText('Runtime nodes', { selector: 'div' }).parentElement!).getByText('Over the plan')).toBeInTheDocument();
    const rows = within(screen.getByRole('list', { name: 'Runtime nodes' })).getAllByRole('listitem');
    expect(within(rows[3]!).getByText('Full')).toBeInTheDocument();
    expect(within(rows[0]!).queryByText('Full')).not.toBeInTheDocument();
  });

  it('on a plan without a limit, says so; a node with no precedents reported says that', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3], precedents: { used: 10, limit: null } })),
      http.get(v1('/license/nodes'), () => HttpResponse.json({ count: 1, max_nodes: null, over: false, nodes: [{ ...nodes.nodes[0]!, precedents: null }] })),
    );
    renderApp('/usage');
    expect(await screen.findByText('no limit')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar', { name: 'Runtime nodes' })).not.toBeInTheDocument();
    expect(await screen.findByText('No precedents reported')).toBeInTheDocument();
  });

  it('says there are none yet, and shows a refusal', async () => {
    server.use(http.get(v1('/license/nodes'), () => HttpResponse.json({ count: 0, max_nodes: 3, over: false, nodes: [] })));
    renderApp('/usage');
    expect(await screen.findByText('No runtime nodes yet')).toBeInTheDocument();
    server.use(http.get(v1('/license/nodes'), () => apiError(503, 'E_UNAVAILABLE', 'Nodes are unavailable.')));
    renderApp('/usage');
    expect(await screen.findByText('Nodes are unavailable.')).toBeInTheDocument();
  });

  it('on Free, one node of 1 against Community’s 5,000 precedents', async () => {
    server.use(...hostingOffHandlers());
    renderApp('/usage');
    const list = await screen.findByRole('list', { name: 'Runtime nodes' });
    expect(within(list).getByText('Acme production')).toBeInTheDocument();
    expect(within(list).getByText('3,200 of 5,000 precedents')).toBeInTheDocument();
    expect(within(screen.getByText('Runtime nodes', { selector: 'div' }).parentElement!).getByText('of 1')).toBeInTheDocument();
  });
});

describe('Usage from Billing and the settings rail', () => {
  it('opens from the plan card’s Usage button and the rail', async () => {
    const { user, router } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Usage' }));
    expect(router.state.location.pathname).toBe('/usage');
    const rail = screen.getByRole('complementary', { name: 'Main' });
    expect(within(rail).getByRole('link', { name: 'Usage' })).toHaveAttribute('href', '/usage');
  });
});

describe('Usage while Glyphh hosts nothing', () => {
  it('has no hosting cost: precedents per node and the API keys only', async () => {
    server.use(...hostingOffHandlers());
    renderApp('/usage');
    expect(await screen.findByText('On Free.')).toBeInTheDocument();
    expect(await screen.findByText('of 5,000 on the fullest node')).toBeInTheDocument();
    expect(screen.queryByText('Hosting', { selector: 'div' })).not.toBeInTheDocument();
    expect(screen.queryByText(/hosting/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Hosted machines' })).not.toBeInTheDocument();
    expect(await screen.findByRole('list', { name: 'API key calls' })).toBeInTheDocument();
  });
});
