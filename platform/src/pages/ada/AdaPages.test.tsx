import { screen, waitFor, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, llmHandlers, server } from '@/test/server';

function on(models = [tickets()]) {
  const fake = adaFake({ models });
  server.use(...fake.handlers);
  return fake;
}

describe('Ada Home', () => {
  it('greets the person, and shows the month against the plan without listing the models', async () => {
    on();
    server.use(...llmHandlers());
    renderApp('/');
    expect(await screen.findByRole('heading', { name: /^Good (morning|afternoon|evening), Chris$/, level: 1 })).toBeInTheDocument();
    const balance = await screen.findByRole('region', { name: 'Balance' });
    expect(within(balance).getByText('$18.70')).toBeInTheDocument();
    expect(within(balance).getByRole('button', { name: 'Add funds' })).toBeInTheDocument();
    const tokens = screen.getByRole('region', { name: 'Tokens this month' });
    // The allowance used and the tokens past it, together.
    expect(within(tokens).getByText('27,400,000')).toBeInTheDocument();
    expect(within(tokens).getByRole('progressbar', { name: 'Tokens this month' })).toHaveAttribute('aria-valuemax', '25000000');
    expect(within(tokens).getByText('$11.30 charged past the plan.')).toBeInTheDocument();
    const requests = await screen.findByRole('region', { name: 'Requests this month' });
    expect(within(requests).getByText('of 1,000,000 in your plan')).toBeInTheDocument();
    expect(screen.queryByRole('list', { name: 'Models' })).not.toBeInTheDocument();
  });

  it('charts the week, and shows what is new in Ada and where to go next', async () => {
    on();
    server.use(...llmHandlers());
    renderApp('/');
    const week = await screen.findByRole('table', { name: 'Token volume by day, last 7 days' });
    const rows = within(week).getAllByRole('row').slice(1).map((row) => row.textContent);
    expect(rows).toEqual(['3 Nov00', '4 Nov00', '5 Nov00', '6 Nov00', '7 Nov1,200,000400,000', '8 Nov00', '9 Nov2,000,000900,000']);
    expect(screen.getByText('4,500,000 tokens')).toBeInTheDocument();

    const ada = await screen.findByRole('region', { name: 'New in Ada' });
    expect(await within(ada).findByRole('link', { name: 'ada-1-2-beta' })).toHaveAttribute('href', '/settings/releases#ada-1-2-beta');
    expect(within(ada).getByText('Pairs it never learned weigh nothing.')).toBeInTheDocument();
    // Home asks for nothing of the Marketplace's: its one card there is a link.
    expect(screen.queryByRole('region', { name: /Marketplace/ })).not.toBeInTheDocument();
    expect(within(screen.getByRole('main')).getByRole('link', { name: /Marketplace/ })).toHaveAttribute('href', '/marketplace');

    expect(screen.getByText('http://api.test/mcp')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy pip command' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Docs/ })).toHaveAttribute('href', 'https://docs.glyphh.ai');
  });

  it('shows the plan and Ada’s requests by day where hosted models are off, and starts a model', async () => {
    on([]);
    const { user, router } = renderApp('/');
    const plan = await screen.findByRole('region', { name: 'Plan' });
    expect(within(plan).getByText('Pro')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Tokens this month' })).not.toBeInTheDocument();
    const week = await screen.findByRole('table', { name: 'Requests by day, last 7 days' });
    expect(within(week).getAllByRole('row').at(-1)).toHaveTextContent('9 Nov840');
    await user.click(screen.getByRole('button', { name: 'New model' }));
    expect(router.state.location.pathname).toBe('/models/new');
  });
});

describe('Ada Models, searched and paged', () => {
  const many = () => Array.from({ length: 30 }, (_, i) => ({ ...tickets(), name: `model-${i + 1}`, id: `m-${i + 1}` }));
  const links = () => within(screen.getByRole('table')).getAllByRole('link');

  it('searches by name or Ada once typing pauses, with the query in the URL, and says when nothing matches', async () => {
    on([tickets(), { ...tickets(), name: 'triage', id: 'm-triage', ada: 'ada-1-2-beta' }]);
    const { user, router } = renderApp('/models');
    await screen.findByRole('table');
    expect(links()).toHaveLength(2);
    await user.type(screen.getByLabelText('Search'), 'beta');
    await vi.waitFor(() => expect(router.state.location.search).toBe('?q=beta'));
    await vi.waitFor(() => expect(links()).toHaveLength(1));
    expect(links()[0]).toHaveTextContent('triage');
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing here');
    // The search settles after the last keystroke: wait for the whole query, not a partial one's empty state.
    expect(await screen.findByText('No model matches “nothing here”.')).toBeInTheDocument();
    expect(screen.getByText('Nothing matches')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('opens on the page the URL names, and pages through 24 at a time', async () => {
    on(many());
    const { user, router } = renderApp('/models?page=2');
    await screen.findByRole('table');
    expect(links()).toHaveLength(6);
    expect(links()[0]).toHaveTextContent('model-25');
    const pager = screen.getByRole('navigation', { name: 'Pages' });
    expect(within(pager).getByText('25–30 of 30')).toBeInTheDocument();
    expect(within(pager).getByRole('button', { name: 'Next' })).toBeDisabled();
    await user.click(within(pager).getByRole('button', { name: 'Previous' }));
    await vi.waitFor(() => expect(links()).toHaveLength(24));
    expect(router.state.location.search).toBe('?page=1');
    expect(within(screen.getByRole('navigation', { name: 'Pages' })).getByText('1–24 of 30')).toBeInTheDocument();
  });
});

describe('Ada Models', () => {
  it('lists each model with its version and precedents', async () => {
    on();
    renderApp('/models');
    const row = (await screen.findByRole('link', { name: 'tickets' })).closest('tr')!;
    expect(row).toHaveTextContent('v2');
    expect(row).toHaveTextContent('1,240');
  });

  it('shows the Ada each model runs, a beta labelled Beta', async () => {
    on([tickets(), { ...tickets(), name: 'triage', id: 'm-triage', ada: 'ada-1-2-beta' }]);
    renderApp('/models');
    const table = await screen.findByRole('table');
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Model', 'Version', 'Ada', 'Precedents', 'Made', 'Actions']);
    expect((await screen.findByRole('link', { name: 'tickets' })).closest('tr')).toHaveTextContent('ada-1-0');
    const triage = screen.getByRole('link', { name: 'triage' }).closest('tr')!;
    expect(triage).toHaveTextContent('ada-1-2-beta');
    expect(await within(triage).findByText('Beta')).toBeInTheDocument();
  });

  it('opens the model from anywhere on its row', async () => {
    on();
    const { user, router } = renderApp('/models');
    const row = (await screen.findByRole('link', { name: 'tickets' })).closest('tr')!;
    await user.click(within(row).getByText('1,240'));
    expect(router.state.location.pathname).toBe('/models/tickets');
  });

  it('offers Edit and Delete in each row’s menu, without opening the row', async () => {
    on();
    const { user, router } = renderApp('/models');
    const actions = await screen.findByRole('button', { name: 'Actions for tickets' });
    expect(actions).toHaveAttribute('aria-expanded', 'false');
    await user.click(actions);
    expect(router.state.location.pathname).toBe('/models');
    const menu = screen.getByRole('menu', { name: 'Actions for tickets' });
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual(['Edit', 'Delete']);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('edits the model from its Dashboard', async () => {
    on();
    const { user, router } = renderApp('/models');
    await user.click(await screen.findByRole('button', { name: 'Actions for tickets' }));
    await user.click(screen.getByRole('menuitem', { name: 'Edit' }));
    expect(router.state.location.pathname).toBe('/models/tickets');
    expect(router.state.location.search).toBe('');
    expect(await screen.findByRole('tab', { name: 'Dashboard' })).toHaveAttribute('aria-selected', 'true');
  });

  it('deletes the model once its name is typed, then lists the rest and says so', async () => {
    const fake = on();
    const { user, router } = renderApp('/models');
    await user.click(await screen.findByRole('button', { name: 'Actions for tickets' }));
    await user.click(screen.getByRole('menuitem', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: 'Delete this model?' });
    const remove = within(dialog).getByRole('button', { name: 'Delete' });
    expect(within(dialog).getAllByRole('button').map((b) => b.textContent).slice(-2)).toEqual(['Cancel', 'Delete']);
    expect(remove).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox', { name: 'Type the model’s name' }), 'tickets');
    await user.click(remove);
    expect(await screen.findByText('tickets is deleted.')).toBeInTheDocument();
    expect(await screen.findByText('No models yet')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/models');
    expect(fake.state.seen.some((s) => s.method === 'DELETE' && s.path === '/models/tickets')).toBe(true);
  });
});

describe('New model', () => {
  it('checks the spec as it is typed, and makes the model from an example', async () => {
    const fake = on([]);
    const { user, router } = renderApp('/models/new');
    const editor = await screen.findByRole('textbox', { name: 'Spec' });
    await user.clear(editor);
    await user.type(editor, '{{"name": "x",');
    expect(screen.getByRole('list', { name: 'Problems' })).toHaveTextContent(/Not valid JSON at line 1/);
    expect(screen.getByRole('button', { name: 'Make model' })).toBeDisabled();

    await user.selectOptions(screen.getByRole('combobox', { name: 'Start from' }), 'tickets');
    expect(screen.getByText(/Looks right: 4 roles in 1 layer/)).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveValue('tickets');

    await user.clear(screen.getByRole('textbox', { name: 'Name' }));
    await user.type(screen.getByRole('textbox', { name: 'Name' }), 'Tickets!');
    expect(screen.getByText(/Lower case letters, digits/)).toBeInTheDocument();
    await user.clear(screen.getByRole('textbox', { name: 'Name' }));
    await user.type(screen.getByRole('textbox', { name: 'Name' }), 'support');
    await user.click(screen.getByRole('button', { name: 'Make model' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/models/support'));
    expect(fake.state.seen.find((s) => s.method === 'POST' && s.path === '/models')!.body).toMatchObject({ name: 'support', spec: { name: 'tickets' } });
  });

  it('names a role’s problem by its path', async () => {
    on([]);
    const { user } = renderApp('/models/new');
    const editor = await screen.findByRole('textbox', { name: 'Spec' });
    await user.clear(editor);
    await user.click(editor);
    await user.paste(JSON.stringify({ name: 'x', dimension: 99999, layers: [{ name: 'a', segments: [{ name: 's', roles: [{ name: 'n', numeric_config: { min_value: 5, max_value: 1, bin_width: 1 } }, { name: 'n' }] }] }], settings: { k: 500 } }));
    const problems = screen.getByRole('list', { name: 'Problems' });
    expect(problems).toHaveTextContent('dimension A whole number from 256 to 8,192.');
    expect(problems).toHaveTextContent('layers[0].segments[0].roles[0].numeric_config Needs min_value below max_value');
    expect(problems).toHaveTextContent('“n” is named twice.');
    expect(problems).toHaveTextContent('settings.k From 1 to 200.');
  });

  it('shows the server’s refusal', async () => {
    on([tickets()]);
    const { user } = renderApp('/models/new');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Start from' }), 'tickets');
    await user.click(screen.getByRole('button', { name: 'Make model' }));
    expect(await screen.findByText('This org has a model named tickets already.')).toBeInTheDocument();
  });

  it('goes back to Models on Cancel', async () => {
    on([]);
    const { user, router } = renderApp('/models/new');
    await user.click(await screen.findByRole('button', { name: 'Cancel' }));
    expect(router.state.location.pathname).toBe('/models');
  });

  it('makes the model on the latest stable Ada, or on another chosen; betas labelled, deprecated and retired not offered', async () => {
    const fake = on([]);
    const { user, router } = renderApp('/models/new');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Start from' }), 'tickets');
    const ada = await screen.findByRole('combobox', { name: 'Ada' });
    expect(ada).toHaveValue('ada-1-1');
    expect(within(ada).getAllByRole('option').map((o) => o.textContent)).toEqual(['ada-1-2-beta (Beta)', 'ada-1-1 (latest stable)']);
    await user.click(screen.getByRole('button', { name: 'Make model' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/models/tickets'));
    expect(fake.state.seen.find((s) => s.method === 'POST' && s.path === '/models')!.body).toMatchObject({ name: 'tickets', ada: 'ada-1-1' });
    expect((await screen.findByText('Runs on')).parentElement).toHaveTextContent('Runs on ada-1-1');
  });

  it('makes a model on a beta, labelled Beta on its page', async () => {
    const fake = on([]);
    const { user } = renderApp('/models/new');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Start from' }), 'tickets');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Ada' }), 'ada-1-2-beta');
    await user.click(screen.getByRole('button', { name: 'Make model' }));
    const line = (await screen.findByText('Runs on')).parentElement!;
    expect(line).toHaveTextContent('ada-1-2-beta');
    expect(within(line).getByText('Beta')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'POST' && s.path === '/models')!.body).toMatchObject({ ada: 'ada-1-2-beta' });
  });

  it('offers the latest stable when the version chosen is refused', async () => {
    on([]);
    server.use(http.post('*/api/ada/v1/models', () => apiError(422, 'E_ADA_BETA', 'ada-1-2-beta is closed to new models.', { ada: 'ada-1-2-beta', latest: 'ada-1-1' })));
    const { user } = renderApp('/models/new');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Start from' }), 'tickets');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Ada' }), 'ada-1-2-beta');
    await user.click(screen.getByRole('button', { name: 'Make model' }));
    const refusal = await screen.findByRole('alert');
    expect(refusal).toHaveTextContent('ada-1-2-beta is closed to new models.');
    await user.click(within(refusal).getByRole('button', { name: 'Choose ada-1-1' }));
    expect(screen.getByRole('combobox', { name: 'Ada' })).toHaveValue('ada-1-1');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('Ada API Keys, searched and paged', () => {
  const rows = () => within(screen.getByRole('list', { name: 'API keys' })).getAllByRole('listitem');
  const manyKeys = () =>
    Array.from({ length: 30 }, (_, i) => ({ id: `ak-${i + 1}`, name: `App ${i + 1}`, clearance: 1, created_at: '2026-10-02T09:00:00Z', expires_at: null, revoked_at: null }));

  it('searches by name, with the query in the URL, and pages through 24 at a time', async () => {
    const fake = on();
    fake.state.keys.push(...manyKeys());
    const { user, router } = renderApp('/keys?page=2');
    await screen.findByRole('list', { name: 'API keys' });
    expect(rows()).toHaveLength(6);
    expect(within(rows()[0]!).getByText('App 25')).toBeInTheDocument();
    const pager = screen.getByRole('navigation', { name: 'Pages' });
    expect(within(pager).getByText('25–30 of 30')).toBeInTheDocument();
    await user.click(within(pager).getByRole('button', { name: 'Previous' }));
    await vi.waitFor(() => expect(rows()).toHaveLength(24));
    expect(router.state.location.search).toBe('?page=1');
    await user.type(screen.getByLabelText('Search'), 'app 1');
    await vi.waitFor(() => expect(rows()).toHaveLength(11)); // App 1 and App 10 to App 19
    expect(router.state.location.search).toBe('?q=app+1');
    expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing here');
    expect(await screen.findByText('No key matches “nothing here”.')).toBeInTheDocument();
  });
});

describe('Ada API Keys', () => {
  it('makes a key with a clearance, shows it once, and revokes it', async () => {
    const fake = on();
    const { user } = renderApp('/keys');
    expect(await screen.findByText(/Your apps call https:\/\/ada\.test|Your apps call Ada/)).toBeInTheDocument();
    await user.click((await screen.findAllByRole('button', { name: 'New API key' }))[0]!);
    const dialog = await screen.findByRole('dialog', { name: 'New API key' });
    await user.type(within(dialog).getByRole('textbox', { name: 'Name' }), 'Support bot');
    const clearance = within(dialog).getByRole('spinbutton', { name: 'Clearance' });
    await user.clear(clearance);
    await user.type(clearance, '2');
    expect(within(dialog).getByText('A number from 0 to 1.')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Make key' })).toBeDisabled();
    await user.clear(clearance);
    await user.type(clearance, '0.5');
    await user.click(within(dialog).getByRole('button', { name: 'Make key' }));
    expect(await screen.findByText('glyphh_ak_secret123')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'POST' && s.path === '/keys')!.body).toEqual({ name: 'Support bot', expires_in_days: 30, clearance: 0.5 });
    await user.click(screen.getByRole('button', { name: 'Done' }));

    const list = await screen.findByRole('list', { name: 'API keys' });
    expect(within(list).getByText(/Clearance 0.5/)).toBeInTheDocument();
    await user.click(within(list).getByRole('button', { name: 'Revoke' }));
    await user.click(within(await screen.findByRole('dialog', { name: 'Revoke this API key?' })).getByRole('button', { name: 'Revoke' }));
    expect(await within(list).findByText('Revoked')).toBeInTheDocument();

    await user.click(within(list).getByRole('button', { name: 'Delete' }));
    await user.click(within(await screen.findByRole('dialog', { name: 'Delete this API key?' })).getByRole('button', { name: 'Delete' }));
    expect(await screen.findByText('No API keys yet')).toBeInTheDocument();
    expect(fake.state.seen.some((s) => s.method === 'DELETE' && s.path.endsWith('/forever'))).toBe(true);
  });

  it('makes a key that never expires without an expiry', async () => {
    const fake = on();
    const { user } = renderApp('/keys');
    await user.click((await screen.findAllByRole('button', { name: 'New API key' }))[0]!);
    const dialog = await screen.findByRole('dialog', { name: 'New API key' });
    await user.type(within(dialog).getByRole('textbox', { name: 'Name' }), 'Forever');
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Expires after' }), 'never');
    await user.click(within(dialog).getByRole('button', { name: 'Make key' }));
    expect(await screen.findByText(/It never expires\./)).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.path === '/keys' && s.method === 'POST')!.body).toEqual({ name: 'Forever', clearance: 1 });
  });
});

describe('Ada Usage', () => {
  it('shows precedents and requests against the plan, the month counted, its price past it, and each model’s precedents', async () => {
    const fake = adaFake({ models: [tickets()], requests: 4_200 });
    server.use(...fake.handlers);
    renderApp('/usage');
    expect(await screen.findByText('On Pro. October 2026, counted in UTC: requests start again on 1 Nov 2026.')).toBeInTheDocument();
    expect(screen.getByText('of 100,000 precedents')).toBeInTheDocument();
    expect(screen.getByText('Across 1 model.')).toBeInTheDocument();
    expect(screen.getByText('of 1,000,000 requests')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Requests this month' })).toHaveAttribute('aria-valuenow', '4200');
    expect(await screen.findByText('Past 1,000,000, requests go on at $1 per 10,000. The count starts again on 1 Nov 2026.')).toBeInTheDocument();
    expect(screen.getByText('Up to 50 calls a second.')).toBeInTheDocument();
    expect(within(await screen.findByRole('list', { name: 'Precedents by model' })).getByText('1,240 precedents')).toBeInTheDocument();
  });

  it('shows the requests past a metered month, as billed', async () => {
    server.use(...adaFake({ models: [tickets()], plan: 'Team', requests: 5_012_345 }).handlers);
    renderApp('/usage');
    expect(await screen.findByText('12,345 past the month, billed at $1 per 10,000. The count starts again on 1 Nov 2026.')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Requests this month' })).toHaveAttribute('aria-valuenow', '5000000');
  });

  it('says when Free’s requests stop, and once they are used, the way to more', async () => {
    server.use(...adaFake({ models: [tickets()], plan: 'Free', requests: 2_000 }).handlers);
    const first = renderApp('/usage');
    expect(await screen.findByText('Past 5,000, requests stop until 1 Nov 2026.')).toBeInTheDocument();
    first.unmount();

    server.use(...adaFake({ models: [tickets()], plan: 'Free', requests: 5_000 }).handlers);
    const { user, router } = renderApp('/usage');
    expect(await screen.findByText(/This month’s requests are used: they start again on 1 Nov 2026\./)).toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: 'Upgrade for more' }));
    expect(router.state.location.pathname).toBe('/settings/plans');
  });

  it('shows no cap when the plan has none (by contract)', async () => {
    server.use(...adaFake({ models: [tickets()], plan: 'Enterprise', requests: 4_200 }).handlers);
    renderApp('/usage');
    expect(await screen.findByText('requests, no limit')).toBeInTheDocument();
    expect(screen.getByText('precedents, no limit')).toBeInTheDocument();
    expect(screen.queryByRole('progressbar', { name: 'Requests this month' })).not.toBeInTheDocument();
    expect(screen.queryByText(/calls a second/)).not.toBeInTheDocument();
  });

  it('shows the refusal when usage cannot be read', async () => {
    on();
    server.use(http.get('*/api/ada/v1/usage', () => apiError(503, 'E_UNAVAILABLE', 'Ada is unreachable for a moment: try again.')));
    renderApp('/usage');
    expect(await screen.findByText('Ada is unreachable for a moment: try again.')).toBeInTheDocument();
  });
});
