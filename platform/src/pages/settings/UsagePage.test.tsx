import { screen, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { llmBilling, me, nodes, plans, tokenUsage } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, llmHandlers, onFreeHandlers, server, v1 } from '@/test/server';

const meter = (name: string) => screen.getByText(name, { selector: 'div' }).parentElement!;
const free = { ...me, plan: plans[0]!, precedents: { used: 3_200, limit: 5_000 } };

describe('Usage', () => {
  it('shows the fullest node’s precedents against the plan’s per node, and nothing of hosting', async () => {
    renderApp('/usage');
    expect(await screen.findByRole('heading', { name: 'Usage' })).toBeInTheDocument();
    expect(await screen.findByText('On Pro.')).toBeInTheDocument();
    expect(within(meter('Precedents')).getByText('18,240')).toBeInTheDocument();
    expect(within(meter('Precedents')).getByText('of 50,000 on the fullest node')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Precedents on the fullest node' })).toHaveAttribute('aria-valuemax', '50000');
    expect(screen.queryByText(/hosting|hosted machine/i)).not.toBeInTheDocument();
  });

  it('says there is no limit on a plan without one', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[4], precedents: { used: 2_500_000, limit: null } })));
    renderApp('/usage');
    expect(await screen.findByText('on the fullest node, no limit')).toBeInTheDocument();
    expect(screen.getByText('2,500,000')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar', { name: 'Precedents on the fullest node' })).not.toBeInTheDocument();
  });

  it('on Free, shows the fullest node against Community’s 5,000', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json(free)));
    renderApp('/usage');
    expect(await screen.findByText('On Free.')).toBeInTheDocument();
    expect(await screen.findByText('of 5,000 on the fullest node')).toBeInTheDocument();
    expect(within(meter('Precedents')).getByText('of 5,000 on the fullest node')).toBeInTheDocument();
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
      http.get(v1('/license/nodes'), () => new Promise<never>(() => {})),
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
    expect(within(rows[2]!).getByText('studio-mac')).toBeInTheDocument();
    expect(within(rows[2]!).getByText(/^Local · 1\.4\.2 · last seen /)).toBeInTheDocument();
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
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[4], precedents: { used: 10, limit: null } })),
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
    server.use(...onFreeHandlers());
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

describe('Tokens on Glyphh’s hosted models', () => {
  it('shows nothing of tokens while hosted models are off', async () => {
    renderApp('/usage');
    expect(await screen.findByText('On Pro.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Tokens' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Overage balance' })).not.toBeInTheDocument();
  });

  it('shows the month against the allowance, the balance in dollars, tokens by day and by model', async () => {
    server.use(...llmHandlers());
    renderApp('/usage');
    expect(await screen.findByRole('heading', { name: 'Tokens' })).toBeInTheDocument();
    expect(screen.getByText(/the allowance starts again on 1 Dec 2026/)).toBeInTheDocument();

    const month = screen.getByRole('region', { name: 'Tokens this month' });
    expect(within(month).getByText('26,200,000')).toBeInTheDocument();
    expect(within(month).getByText('of 25,000,000 tokens')).toBeInTheDocument();
    expect(within(month).getByRole('progressbar', { name: 'Tokens this month' })).toHaveAttribute('aria-valuenow', '25000000');
    expect(within(month).getByText('1,200,000 past the allowance, charged to the balance.')).toBeInTheDocument();

    const balance = screen.getByRole('region', { name: 'Overage balance' });
    expect(within(balance).getByText('$18.70')).toBeInTheDocument();
    expect(within(balance).getByRole('button', { name: 'Add funds' })).toBeInTheDocument();

    // The chart's table: input and output each day, a day with none filled in between.
    const byDay = await screen.findByRole('table', { name: 'Input and output tokens by day, last 30 days' });
    const rows = within(byDay).getAllByRole('row').slice(1).map((row) => row.textContent);
    expect(rows).toEqual(['7 Nov1,200,000400,000', '8 Nov00', '9 Nov2,000,000900,000']);

    const byModel = screen.getByRole('table', { name: 'Tokens by model' });
    const row = within(byModel).getByText('adaL 34B 1.0').closest('tr')!;
    expect(within(row).getByText('20,000,000')).toBeInTheDocument();
    expect(within(row).getByText('6,200,000')).toBeInTheDocument();
    expect(within(row).getByText('4,210')).toBeInTheDocument();
    expect(within(row).getByText('$11.30')).toBeInTheDocument();
    expect(screen.queryByText(/credit/i)).not.toBeInTheDocument();
  });

  it('within the allowance, says what happens past it; with none used, says so', async () => {
    // The first handler that matches answers.
    server.use(
      http.get(v1('/billing'), () => HttpResponse.json({ ...llmBilling, tokens: { ...tokenUsage, used: 1_000, over_used: 0, models: [] } })),
      http.get(v1('/llm/usage'), () => HttpResponse.json({ days: [] })),
      ...llmHandlers(),
    );
    renderApp('/usage');
    expect(await screen.findByText('Past 25,000,000, tokens are charged to the balance.')).toBeInTheDocument();
    expect(await screen.findByText('No tokens in the last 30 days.')).toBeInTheDocument();
    expect(screen.getByText('No model used this month.')).toBeInTheDocument();
  });

  it('marks a bot’s model, lists each bot’s month, and says when no bot ran', async () => {
    const sonnet = { id: 'claude-sonnet-5-5', name: 'Claude Sonnet 5.5', kind: 'bot' as const, input_tokens: 1_000, output_tokens: 200, requests: 3, charged_cents: 2.5 };
    const bots = [{ slug: 'inbox', name: 'Inbox triage', runs: 2, input_tokens: 150, output_tokens: 30, charged_cents: 3 }];
    server.use(
      http.get(v1('/billing'), () => HttpResponse.json({ ...llmBilling, tokens: { ...tokenUsage, models: [...tokenUsage.models, sonnet] }, bots })),
      ...llmHandlers(),
    );
    const { unmount } = renderApp('/usage');
    const byModel = await screen.findByRole('table', { name: 'Tokens by model' });
    expect(within(byModel).getByText('Claude Sonnet 5.5').closest('tr')).toHaveTextContent('Bots');
    expect(within(byModel).getByText('adaL 34B 1.0').closest('tr')).not.toHaveTextContent('Bots');
    const byBot = screen.getByRole('table', { name: 'Tokens by bot' });
    const row = within(byBot).getByRole('link', { name: 'Inbox triage' });
    expect(row).toHaveAttribute('href', '/bots/inbox');
    expect(row.closest('tr')).toHaveTextContent('Inbox triage215030$0.03');
    unmount();
    server.use(http.get(v1('/billing'), () => HttpResponse.json({ ...llmBilling, bots: [] })));
    renderApp('/usage');
    expect(await screen.findByText('No bot has run this month.')).toBeInTheDocument();
  });

  it('an empty balance says requests stop; a member cannot add funds', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })),
      http.get(v1('/billing'), () => HttpResponse.json({ ...llmBilling, balance: { cents: -0.42, micros: -4_200, low: true } })),
      ...llmHandlers(),
    );
    renderApp('/usage');
    const balance = await screen.findByRole('region', { name: 'Overage balance' });
    expect(within(balance).getByText('-$0.0042')).toBeInTheDocument();
    expect(within(balance).getByText('Empty')).toBeInTheDocument();
    expect(within(balance).getByText(/hosted models stop until you add funds/)).toBeInTheDocument();
    expect(within(balance).queryByRole('button', { name: 'Add funds' })).not.toBeInTheDocument();
    expect(within(balance).getByText('Only your org’s admin can add funds.')).toBeInTheDocument();
  });

  it('shows the tokens on Ada Cloud’s Usage too', async () => {
    server.use(...adaFake({ models: [tickets()], requests: 10 }).handlers, ...llmHandlers());
    renderApp('/usage');
    expect(await screen.findByText('of 1,000,000 requests')).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Tokens this month' })).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Tokens by model' })).toBeInTheDocument();
  });
});
