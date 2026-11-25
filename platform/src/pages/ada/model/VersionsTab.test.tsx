import { screen, within } from '@testing-library/react';
import { adaFake, ticketHistory, tickets, versionOf } from '@/test/ada';
import { storeText } from './VersionDialogs';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

/** Tickets at version 3, with a dropped first version and a re-encoded second kept apart. */
function on(jobSteps = 2) {
  const fake = adaFake({ models: [{ ...tickets(), version: 3 }], jobSteps, history: { tickets: ticketHistory() } });
  server.use(...fake.handlers);
  return fake;
}

async function menuFor(user: ReturnType<typeof renderApp>['user'], version: number) {
  const row = (await screen.findByText(`v${version}`)).closest('tr')!;
  await user.click(within(row).getByRole('button', { name: `Actions for version ${version}` }));
  return screen.getByRole('menu', { name: `Actions for version ${version}` });
}

describe('Versions', () => {
  it('lists every version newest first: its number with the live badge, its notes or what it changed, its date', async () => {
    on();
    renderApp('/models/tickets?tab=versions');
    const table = await screen.findByRole('table', { name: 'Versions' });
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Version', 'Ada', 'Description', 'Date', 'Actions']);
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      'v3Liveada-1-0More voters20 Oct 2026',
      'v2ada-1-0Re-encoded: seed 5 → 1110 Oct 2026',
      'v1Droppedada-1-0made1 Oct 2026',
    ]);
  });

  it('offers on each row what that version can do: the live one is not made live or compared with itself', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=versions');
    const live = await menuFor(user, 3);
    expect(within(live).getAllByRole('menuitem').map((i) => i.textContent)).toEqual(['View', 'Upgrade Ada', 'Edit notes', 'Copy spec']);
    await user.keyboard('{Escape}');
    const old = await menuFor(user, 2);
    expect(within(old).getAllByRole('menuitem').map((i) => i.textContent)).toEqual(['View', 'Make live', 'Edit notes', 'Compare with live', 'Copy spec']);
  });

  it('views a version whole: who made it, the precedents then and now, its store, why it re-encoded, what it learned, its backtest, its spec', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'View' }));
    const dialog = await screen.findByRole('dialog', { name: 'Version 2' });
    expect(dialog).toHaveTextContent('Made10 Oct 09:00:00 UTC, by Chris Timmerman');
    expect(dialog).toHaveTextContent('Precedents900 when it was made · 1,240 now');
    expect(dialog).toHaveTextContent('Its stored cases are kept apart');
    expect(dialog).toHaveTextContent('Re-encodedIts cases were rewritten into a store of its own, for: seed 5 → 11.');
    expect(dialog).toHaveTextContent('Learned2 roles weighed, 120 words, 1 pair, tau 0.81');
    expect(dialog).toHaveTextContent('BacktestAccuracy 81.0% · log-loss 0.520 · asks 10.0% · on 200 held-out cases · 19 Oct 2026');
    expect(dialog).toHaveTextContent('Changes from version 1');
    expect(within(dialog).getByText('Rewrites the cases')).toBeInTheDocument();
    expect(await within(dialog).findByRole('button', { name: 'Copy version 2’s spec' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Copy version 2’s settings' })).toBeInTheDocument();
    expect(fake.state.seen.some((s) => s.path === '/models/tickets/versions/2')).toBe(true);
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('says what little it knows of a version made before more was kept', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 1)).getByRole('menuitem', { name: 'View' }));
    const dialog = await screen.findByRole('dialog', { name: 'Version 1' });
    expect(dialog).toHaveTextContent('Its stored cases were dropped: it can’t be made live again.');
    expect(dialog).toHaveTextContent('LearnedNothing learned yet');
    expect(dialog).toHaveTextContent('BacktestNot backtested');
    expect(dialog).toHaveTextContent('The first version.');
  });

  it('makes a version kept apart live by a job that brings its cases up to date, shown as it runs', async () => {
    const fake = on(3);
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'Make live' }));
    const dialog = await screen.findByRole('dialog', { name: 'Make version 2 live?' });
    expect(dialog).toHaveTextContent('Version 2’s spec, settings and learned weights become live, in place of version 3.');
    expect(dialog).toHaveTextContent('Precedents recorded since stay in the model: cases are not versioned.');
    expect(dialog).toHaveTextContent('Its cases are stored apart, so a job first brings them up to date with every write made since. Version 3 answers until it is done.');
    const buttons = within(dialog).getAllByRole('button');
    expect(buttons.map((b) => b.textContent)).toEqual(['Cancel', 'Make live']);
    await user.click(within(dialog).getByRole('button', { name: 'Make live' }));
    expect(await within(dialog).findByRole('progressbar', { name: 'Rewriting the cases for version 2' })).toBeInTheDocument();
    expect(await within(dialog).findByText('Version 2 is live.', {}, { timeout: 4000 })).toBeInTheDocument();
    expect(fake.state.seen.some((s) => s.method === 'POST' && s.path === '/models/tickets/versions/2/activate')).toBe(true);
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(await screen.findByText('Version 2 is live · 1,240 precedents')).toBeInTheDocument();
  });

  it('says a version whose cases were dropped can’t be made live, and saves its spec as a new version instead', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 1)).getByRole('menuitem', { name: 'Make live' }));
    const dialog = await screen.findByRole('dialog', { name: 'Version 1 can’t be made live' });
    expect(dialog).toHaveTextContent('Its stored cases were dropped after 7 days unused');
    const save = within(dialog).getByRole('button', { name: 'Save as a new version' });
    await user.click(save);
    expect(await within(dialog).findByText('Version 4 is live.')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'PUT')!.body).toMatchObject({ note: 'From version 1', spec: { name: 'tickets' } });
    expect(fake.state.seen.some((s) => s.path.endsWith('/activate'))).toBe(false);
  });

  it('shows the server’s refusal of a rollback', async () => {
    on();
    server.use(http.post('*/api/ada/v1/models/tickets/versions/2/activate', () => apiError(409, 'E_BUSY', 'This model has a reencode job open: wait for it to end.')));
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'Make live' }));
    const dialog = await screen.findByRole('dialog', { name: 'Make version 2 live?' });
    await user.click(within(dialog).getByRole('button', { name: 'Make live' }));
    expect(await within(dialog).findByText('This model has a reencode job open: wait for it to end.')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('edits a version’s notes; emptied, the list shows what it changed again', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'Edit notes' }));
    const dialog = await screen.findByRole('dialog', { name: 'Version 2’s notes' });
    const notes = within(dialog).getByRole('textbox', { name: 'Release notes' });
    expect(notes).toHaveAttribute('placeholder', 'Re-encoded: seed 5 → 11');
    await user.type(notes, '  New seed  ');
    await user.click(within(dialog).getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('New seed')).toBeInTheDocument();
    expect(fake.state.seen.find((s) => s.method === 'PATCH')).toMatchObject({ path: '/models/tickets/versions/2', body: { note: 'New seed' } });
    await user.click(within(await menuFor(user, 3)).getByRole('menuitem', { name: 'Edit notes' }));
    const again = await screen.findByRole('dialog', { name: 'Version 3’s notes' });
    await user.clear(within(again).getByRole('textbox', { name: 'Release notes' }));
    await user.click(within(again).getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('k 15 → 20')).toBeInTheDocument();
  });

  it('compares a version with the live one', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=settings');
    // A settings change makes version 4 from 3: comparing 3 with it shows the lever moved back.
    const k = await screen.findByRole('spinbutton', { name: 'Precedents that vote' });
    await user.clear(k);
    await user.type(k, '25');
    await user.click(screen.getByRole('button', { name: 'Save 1 change as a new version' }));
    expect(await screen.findByText('Version 4 is live.')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Versions' }));
    expect(await screen.findByText('k 15 → 25')).toBeInTheDocument();
    await user.click(within(await menuFor(user, 3)).getByRole('menuitem', { name: 'Compare with live' }));
    const dialog = await screen.findByRole('dialog', { name: 'Version 3 against live version 4' });
    expect(await within(dialog).findByText('k 25 → 15')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    await user.click(within(await menuFor(user, 4)).getByRole('menuitem', { name: 'View' }));
    const live = await screen.findByRole('dialog', { name: 'Version 4 (live)' });
    expect(live).toHaveTextContent('Stored casesThe live stored cases.');
    await user.click(within(live).getByRole('button', { name: 'Close' }));
    await user.click(within(await menuFor(user, 3)).getByRole('menuitem', { name: 'View' }));
    expect(await screen.findByRole('dialog', { name: 'Version 3' })).toHaveTextContent('It reads the live stored cases: making it live is at once.');
  });

  it('says when a version has the live one’s spec and settings', async () => {
    on();
    server.use(http.get('*/api/ada/v1/models/tickets/versions/2/diff', () => Response.json({ version: 2, against: 3, changes: [] })));
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'Compare with live' }));
    expect(await screen.findByText('The same spec and settings as the live version.')).toBeInTheDocument();
  });

  it('says from when cases kept apart may be dropped', () => {
    const kept = (after: string | null) => storeText(versionOf({ version: 2, store: { status: 'kept', drop_after: after } }));
    expect(kept(null)).toBe('Its stored cases are kept apart, for a rollback.');
    expect(kept('2000-01-01T00:00:00Z')).toBe('Its stored cases are kept apart; the next re-encode may drop them.');
    expect(kept('2999-01-08T00:00:00Z')).toBe('Its stored cases are kept apart until at least 8 Jan 2999; the next re-encode after that drops them.');
    expect(storeText(versionOf({ version: 5, store: { status: 'making', drop_after: null } }))).toMatch(/^Its stored cases are being written/);
  });

  it('copies a version’s spec', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'Copy spec' }));
    expect(await screen.findByText('Version 2’s spec is copied.')).toBeInTheDocument();
    expect(JSON.parse(await navigator.clipboard.readText())).toMatchObject({ name: 'tickets' });
  });

  it('says so when a spec could not be copied', async () => {
    on();
    server.use(http.get('*/api/ada/v1/models/tickets/versions/2', () => apiError(404, 'E_VERSION_MISSING', 'This model has no version 2.')));
    const { user } = renderApp('/models/tickets?tab=versions');
    await user.click(within(await menuFor(user, 2)).getByRole('menuitem', { name: 'Copy spec' }));
    expect(await screen.findByText('Version 2’s spec could not be copied.')).toBeInTheDocument();
  });
});
