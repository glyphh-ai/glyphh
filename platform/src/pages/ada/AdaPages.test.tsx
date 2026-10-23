import { screen, waitFor, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

function on(models = [tickets()]) {
  const fake = adaFake({ models });
  server.use(...fake.handlers);
  return fake;
}

describe('Ada Home', () => {
  it('shows the models, the precedents against the plan, and the connector URL to add in Claude', async () => {
    on();
    renderApp('/');
    const list = await screen.findByRole('list', { name: 'Models' });
    expect(within(list).getByRole('link', { name: 'tickets' })).toHaveAttribute('href', '/models/tickets');
    expect(within(list).getByText('1,240 precedents')).toBeInTheDocument();
    expect(screen.getByText('http://api.test/mcp')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy connector URL' })).toBeInTheDocument();
    expect(await screen.findByText('of 100,000 precedents')).toBeInTheDocument();
    expect(screen.getByRole('progressbar', { name: 'Precedents' })).toHaveAttribute('aria-valuenow', '1240');
    expect(screen.getByText('of 1,000,000 requests')).toBeInTheDocument();
    expect(await screen.findByText('Past 1,000,000, requests go on at $1 per 10,000. The count starts again on 1 Nov 2026.')).toBeInTheDocument();
  });

  it('starts a first model from the empty state', async () => {
    on([]);
    const { user, router } = renderApp('/');
    expect(await screen.findByText('No models yet')).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: 'New model' }).at(-1)!);
    expect(router.state.location.pathname).toBe('/models/new');
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
