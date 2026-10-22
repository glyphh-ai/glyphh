import { screen, waitFor, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

function on(jobSteps = 2) {
  const fake = adaFake({ models: [tickets()], jobSteps });
  server.use(...fake.handlers);
  return fake;
}

describe('a model’s page', () => {
  it('shows the live version, its precedents and its spec, with the name in the crumbs', async () => {
    on();
    renderApp('/models/tickets');
    expect(await screen.findByText('Version 2 is live · 1,240 precedents')).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('AdaModelstickets');
    expect(screen.getByText(/"bag_of_words"/)).toBeInTheDocument();
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Spec', 'Settings', 'Import', 'Try it', 'Backtest', 'Export']);
  });

  it('says so when there is no such model', async () => {
    on();
    renderApp('/models/nope');
    expect(await screen.findByText('No model nope in this org.')).toBeInTheDocument();
  });

  it('saves an edited spec as a new version, live at once when it reads the cases as they are', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets');
    await user.click(await screen.findByRole('button', { name: 'Edit spec' }));
    const editor = screen.getByRole('textbox', { name: 'Spec' });
    const spec = JSON.parse((editor as HTMLTextAreaElement).value);
    spec.output = { ask_below: 0.7 };
    await user.clear(editor);
    await user.click(editor);
    await user.paste(JSON.stringify(spec));
    await user.type(screen.getByRole('textbox', { name: 'Why' }), 'Ask more');
    await user.click(screen.getByRole('button', { name: 'Save as a new version' }));
    expect(await screen.findByText('Version 3 is live.')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'PUT')!.body).toMatchObject({ note: 'Ask more', spec: { output: { ask_below: 0.7 } } });
    const versions = screen.getAllByRole('row').map((r) => r.textContent);
    expect(versions.some((text) => text?.startsWith('v3Ask more'))).toBe(true);
  });

  it('follows a re-encode’s job until the new version is live', async () => {
    on(3);
    const { user } = renderApp('/models/tickets');
    await user.click(await screen.findByRole('button', { name: 'Edit spec' }));
    const editor = screen.getByRole('textbox', { name: 'Spec' });
    const spec = JSON.parse((editor as HTMLTextAreaElement).value);
    spec.layers[0].segments[0].roles.push({ name: 'channel' });
    await user.clear(editor);
    await user.click(editor);
    await user.paste(JSON.stringify(spec));
    await user.click(screen.getByRole('button', { name: 'Save as a new version' }));
    expect(await screen.findByRole('progressbar', { name: 'Rewriting the cases for version 3' })).toBeInTheDocument();
    expect(await screen.findByText('Version 3 is live.', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(await screen.findByText('Version 3 is live · 1,240 precedents')).toBeInTheDocument();
  });

  it('makes an older version live again: a rollback', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=settings');
    // A settings change makes version 3, so version 2 can be made live again.
    const k = await screen.findByRole('spinbutton', { name: 'Precedents that vote' });
    await user.clear(k);
    await user.type(k, '25');
    await user.click(screen.getByRole('button', { name: 'Save 1 change as a new version' }));
    expect(await screen.findByText('Version 3 is live.')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Spec' }));
    const row = (await screen.findByText('v2')).closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Make live' }));
    expect(await screen.findByText('Version 2 is live.')).toBeInTheDocument();
    expect(fake.state.seen.some((s) => s.path === '/models/tickets/versions/2/activate')).toBe(true);
  });

  it('deletes the model once its name is typed', async () => {
    const fake = on();
    const { user, router } = renderApp('/models/tickets');
    await user.click(await screen.findByRole('button', { name: 'Delete' }));
    const dialog = await screen.findByRole('dialog', { name: 'Delete this model?' });
    const remove = within(dialog).getByRole('button', { name: 'Delete' });
    expect(remove).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox', { name: 'Type the model’s name' }), 'tickets');
    await user.click(remove);
    await waitFor(() => expect(router.state.location.pathname).toBe('/models'));
    expect(fake.state.seen.some((s) => s.method === 'DELETE' && s.path === '/models/tickets')).toBe(true);
  });
});

describe('Settings', () => {
  it('shows every lever with what a change does, refuses one out of range, and saves the changes as a new version', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=settings');
    const k = await screen.findByRole('spinbutton', { name: 'Precedents that vote' });
    expect(k).toHaveValue(15);
    expect(screen.getByRole('button', { name: 'Save as a new version' })).toBeDisabled();
    expect(screen.getAllByText('Rewrites the cases').length).toBeGreaterThan(0);
    await user.clear(k);
    await user.type(k, '500');
    expect(screen.getByText('From 1 to 200.')).toBeInTheDocument();
    await user.clear(k);
    await user.type(k, '25');
    await user.click(screen.getByRole('switch', { name: 'Lexicon' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Calibrate by' }), 'cost');
    await user.type(screen.getByRole('textbox', { name: 'Why' }), 'Fewer mistakes');
    await user.click(screen.getByRole('button', { name: 'Save 3 changes as a new version' }));
    expect(await screen.findByText('Version 3 is live.')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'PATCH')!.body).toEqual({ changes: { k: 25, lexicon: false, calibrate_by: 'cost' }, note: 'Fewer mistakes' });
  });

  it('leaves Learn again every empty for never, and shows the server’s refusal', async () => {
    on();
    server.use(http.patch('*/api/ada/v1/models/tickets/settings', () => apiError(409, 'E_BUSY', 'This model has a import job open: wait for it to end.')));
    const { user } = renderApp('/models/tickets?tab=settings');
    const every = await screen.findByRole('spinbutton', { name: 'Learn again every' });
    expect(every).toHaveValue(null);
    await user.type(every, '500');
    await user.click(screen.getByRole('button', { name: 'Save 1 change as a new version' }));
    expect(await screen.findByText('This model has a import job open: wait for it to end.')).toBeInTheDocument();
  });
});

describe('Import', () => {
  it('maps a CSV’s columns to the spec, sends the file to its upload link and follows the job to its result', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=import');
    const csv = 'subject,product,plan,outcome,notes\nCannot pay,web,pro,billing,x\nLocked out,app,team,auth,y\nSlow search,web,???,search,z\n';
    await user.upload(await screen.findByLabelText('File'), new File([csv], 'history.csv', { type: 'text/csv' }));
    const columns = await screen.findByRole('table', { name: 'Columns' });
    expect(within(columns).getByRole('combobox', { name: 'Where subject goes' })).toHaveValue('ticket.about.subject');
    expect(within(columns).getByRole('combobox', { name: 'Where outcome goes' })).toHaveValue('outcome');
    expect(within(columns).getByRole('combobox', { name: 'Where notes goes' })).toHaveValue('');
    await user.selectOptions(within(columns).getByRole('combobox', { name: 'Where notes goes' }), 'ticket.about.product');
    await user.selectOptions(within(columns).getByRole('combobox', { name: 'Where notes goes' }), '');
    await user.click(screen.getByRole('button', { name: 'Import' }));

    expect(await screen.findByText('3 rows: 2 recorded (2 new, 0 replaced), 1 refused.', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Refused rows' })).getByText('not a value the spec takes')).toBeInTheDocument();
    const started = fake.state.seen.find((s) => s.path === '/models/tickets/imports')!;
    expect(started.body).toEqual({
      format: 'csv',
      mapping: { subject: 'ticket.about.subject', product: 'ticket.about.product', plan: 'ticket.about.plan', outcome: 'outcome', notes: null },
    });
    expect(fake.state.seen.find((s) => s.method === 'PUT')!.path).toBe('/uploads/job-1.signed');
    expect(await screen.findByText('Version 2 is live · 1,242 precedents')).toBeInTheDocument();
  });

  it('takes JSON Lines as they are', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=import');
    await user.upload(await screen.findByLabelText('File'), new File(['{"data":{},"outcome":"billing"}\n'], 'cases.jsonl'));
    expect(screen.getByRole('combobox', { name: 'Format' })).toHaveValue('jsonl');
    expect(screen.queryByRole('table', { name: 'Columns' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Import' }));
    await waitFor(() => expect(fake.state.seen.find((s) => s.path === '/models/tickets/imports')?.body).toEqual({ format: 'jsonl' }));
  });

  it('shows the refusal when the upload fails', async () => {
    on();
    server.use(http.put('*/api/ada/v1/uploads/:link', () => apiError(410, 'E_LINK', 'This upload link has expired.')));
    const { user } = renderApp('/models/tickets?tab=import');
    await user.upload(await screen.findByLabelText('File'), new File(['{"data":{}}\n'], 'cases.jsonl'));
    await user.click(screen.getByRole('button', { name: 'Import' }));
    expect(await screen.findByText('This upload link has expired.')).toBeInTheDocument();
  });

  it('shows a failed import’s error', async () => {
    on();
    server.use(
      http.get('*/api/ada/v1/jobs/:id', () =>
        Response.json({ id: 'job-1', model: 'tickets', kind: 'import', state: 'failed', percent: 10, error: { code: 'E_MAPPING', message: 'The spec has no role notes.' } }),
      ),
    );
    const { user } = renderApp('/models/tickets?tab=import');
    await user.upload(await screen.findByLabelText('File'), new File(['{"data":{}}\n'], 'cases.jsonl'));
    await user.click(screen.getByRole('button', { name: 'Import' }));
    expect(await screen.findByText('The spec has no role notes.')).toBeInTheDocument();
  });
});

describe('Try it', () => {
  it('builds a form from the spec, decides, and shows the answer, its confidence and its precedents', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=try');
    expect(await screen.findByRole('textbox', { name: 'subject' })).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'id' })).not.toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: 'subject' }), 'Card was charged twice');
    await user.type(screen.getByRole('textbox', { name: 'product' }), 'web');
    await user.click(screen.getByRole('button', { name: 'Decide' }));
    const answer = await screen.findByRole('region', { name: 'Answer' });
    expect(within(answer).getAllByText('billing')[0]).toHaveClass('big');
    expect(within(answer).getByText('Confidence 82%')).toBeInTheDocument();
    expect(within(answer).queryByText('A person should decide')).not.toBeInTheDocument();
    expect(within(answer).getByRole('progressbar', { name: 'Probability of auth' })).toHaveAttribute('aria-valuenow', '0.12');
    const precedents = within(answer).getByRole('table', { name: 'Precedents' });
    expect(within(precedents).getAllByRole('row').map((r) => r.textContent)).toEqual(['CaseOutcomeSimilarity', 'c1a2b3billing91%', 'd4e5f6auth77%']);
    expect(fake.state.seen.find((s) => s.path === '/decide')!.body).toEqual({
      model: 'tickets',
      data: { ticket: { about: { subject: 'Card was charged twice', product: 'web' } } },
    });
  });

  it('says when a person should decide, and when nothing is known', async () => {
    on();
    server.use(http.post('*/api/ada/v1/decide', () => Response.json({ outcome: 'bad', expected_cost: 0.7, probabilities: { bad: 0.55, good: 0.45 }, ask: true, receipts: [], model: 'tickets', version: 2 })));
    const { user } = renderApp('/models/tickets?tab=try');
    await user.click(await screen.findByRole('button', { name: 'Decide' }));
    expect(await screen.findByText('A person should decide')).toBeInTheDocument();
    server.use(http.post('*/api/ada/v1/decide', () => Response.json({ outcome: null, expected_cost: null, probabilities: {}, ask: true, receipts: [], model: 'tickets', version: 2 })));
    await user.click(screen.getByRole('button', { name: 'Decide' }));
    expect(await screen.findByText(/Nothing is known yet/)).toBeInTheDocument();
  });
});

describe('Backtest', () => {
  it('scores candidates on held-out cases and makes the winner live, keeping the backtest with the version', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=backtest');
    const first = await screen.findByRole('group', { name: 'Candidate 1' });
    await user.selectOptions(within(first).getByRole('combobox', { name: 'Change a lever' }), 'word_evidence');
    const evidence = within(first).getByRole('spinbutton', { name: 'Word evidence' });
    await user.clear(evidence);
    await user.type(evidence, '1');
    await user.click(screen.getByRole('button', { name: 'Add a candidate' }));
    const second = screen.getByRole('group', { name: 'Candidate 2' });
    await user.click(within(second).getByRole('button', { name: 'Remove' }));
    await user.click(screen.getByRole('button', { name: 'Run backtest' }));
    expect(fake.state.seen.find((s) => s.path === '/models/tickets/backtest')!.body).toEqual({ candidates: [{ settings: { word_evidence: 1 } }], holdout: { newest: 200 } });

    const results = await screen.findByRole('table', { name: 'Backtest results' }, { timeout: 4000 });
    expect(screen.getByText('Learned from 800 cases, scored on the newest 200.')).toBeInTheDocument();
    const rows = within(results).getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Live, version 2');
    expect(rows[2]).toHaveTextContent('word_evidence 1');
    expect(within(rows[2]!).getByText('Best')).toBeInTheDocument();
    expect(rows[2]).toHaveTextContent('84.0%+3.0 pts');
    expect(rows[3]).toHaveTextContent('Version 1 reads subject differently.');
    await user.click(within(rows[2]!).getByRole('button', { name: 'Make live' }));
    expect(await screen.findByText('Version 3 is live.')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'PATCH')!.body).toEqual({ changes: { word_evidence: 1 }, note: 'Backtest: word_evidence 1', backtest: 'job-1' });
  });

  it('asks for a lever to change before it runs', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=backtest');
    await user.click(await screen.findByRole('button', { name: 'Run backtest' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Add a lever to change.');
    expect(fake.state.seen.some((s) => s.path.endsWith('/backtest'))).toBe(false);
  });
});

describe('Export', () => {
  it('exports as a job and offers the download link', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=export');
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Format' }), 'ada_sqlite');
    await user.click(screen.getByRole('button', { name: 'Export' }));
    const link = await screen.findByRole('link', { name: 'Download' }, { timeout: 4000 });
    expect(link).toHaveAttribute('href', 'https://ada.test/v1/downloads/tickets.signed');
    expect(fake.state.seen.find((s) => s.path === '/models/tickets/export')!.body).toEqual({ format: 'ada_sqlite' });
  });
});
