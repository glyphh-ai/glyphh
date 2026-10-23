import { screen, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

/** Tickets at version 2 on ada-1-0, deprecated now that ada-1-1 is the latest stable. */
function on(jobSteps = 2) {
  const fake = adaFake({ models: [tickets()], jobSteps });
  server.use(...fake.handlers);
  return fake;
}

async function openUpgrade(user: ReturnType<typeof renderApp>['user']) {
  await user.click(await screen.findByRole('button', { name: 'Upgrade Ada' }));
  return screen.findByRole('dialog', { name: 'Upgrade Ada' });
}

describe('Upgrade Ada', () => {
  it('offers the latest stable first and betas labelled; never a deprecated or retired version', async () => {
    on();
    const { user, router } = renderApp('/models/tickets?tab=versions');
    const dialog = await openUpgrade(user);
    expect(router.state.location.search).toBe('?tab=versions&upgrade=');
    expect(dialog).toHaveTextContent('tickets runs on ada-1-0.');
    const select = await within(dialog).findByRole('combobox', { name: 'Move to' });
    expect(select).toHaveValue('ada-1-1');
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['ada-1-2-beta (Beta)', 'ada-1-1 (latest stable)']);
    expect(dialog).toHaveTextContent('Better calibrated answers.');
    expect(dialog).toHaveTextContent('It can answer differently from ada-1-0: backtest it on your cases first.');
    expect(within(dialog).getByRole('link', { name: 'Read its release notes' })).toHaveAttribute('href', '/ada#ada-1-1');
    await user.selectOptions(select, 'ada-1-2-beta');
    expect(dialog).toHaveTextContent('A beta: never the default, chosen only by name.');
    expect(within(dialog).getByRole('button', { name: 'Upgrade to ada-1-2-beta' })).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(router.state.location.search).toBe('?tab=versions');
  });

  it('opens from the live version’s menu too', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=versions');
    const row = (await screen.findByText('v2')).closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Actions for version 2' }));
    await user.click(screen.getByRole('menuitem', { name: 'Upgrade Ada' }));
    expect(await screen.findByRole('dialog', { name: 'Upgrade Ada' })).toBeInTheDocument();
  });

  it('backtests the live spec on the version chosen, shows the score change, then upgrades and follows the job until it is live', async () => {
    const fake = on(3);
    const { user } = renderApp('/models/tickets?tab=versions');
    const dialog = await openUpgrade(user);
    await user.click(await within(dialog).findByRole('button', { name: 'Backtest against ada-1-1' }));
    expect(fake.state.seen.find((s) => s.method === 'POST' && s.path === '/models/tickets/backtest')!.body).toEqual({ ada: 'ada-1-1', holdout: { newest: 200 } });
    const table = await within(dialog).findByRole('table', { name: 'Backtest results' }, { timeout: 4000 });
    const rows = within(table).getAllByRole('row').slice(1);
    expect(rows[0]).toHaveTextContent('Live, version 2 on ada-1-0');
    expect(rows[1]).toHaveTextContent('The live spec on ada-1-1');
    expect(rows[1]).toHaveTextContent('+2.0 pts');
    expect(within(rows[1]!).getByText('Best')).toBeInTheDocument();
    expect(within(table).queryByRole('button', { name: 'Make live' })).not.toBeInTheDocument();
    expect(dialog).toHaveTextContent('On your newest 200 cases, ada-1-1 was right 83.0% of the time, against 81.0% on ada-1-0.');
    expect(dialog).toHaveTextContent('To go back, make version 2 live again from this tab: it runs on ada-1-0, as it does now.');

    await user.click(within(dialog).getByRole('button', { name: 'Upgrade to ada-1-1' }));
    expect(fake.state.seen.find((s) => s.path === '/models/tickets/upgrade')!.body).toEqual({ ada: 'ada-1-1', backtest: 'job-1' });
    expect(await within(dialog).findByRole('progressbar', { name: 'Rewriting the cases for version 3' })).toBeInTheDocument();
    expect(await within(dialog).findByText('Version 3 is live.', {}, { timeout: 4000 })).toBeInTheDocument();
    // The way back still names the version it came from.
    expect(dialog).toHaveTextContent('To go back, make version 2 live again from this tab: it runs on ada-1-0, as it does now.');
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    const table2 = await screen.findByRole('table', { name: 'Versions' });
    expect(await within(table2).findByText(/^v3/)).toBeInTheDocument();
    expect(within(table2).getAllByRole('row')[1]).toHaveTextContent(/^v3Liveada-1-1/);
    expect(await screen.findByText('Version 3 is live · 1,240 precedents')).toBeInTheDocument();
    const line = (await screen.findByText('Runs on')).parentElement!;
    expect(line).toHaveTextContent('Runs on ada-1-1');
  });

  it('rolls back by making the version before live, on its own Ada', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=versions');
    const dialog = await openUpgrade(user);
    await user.click(await within(dialog).findByRole('button', { name: 'Upgrade to ada-1-1' }));
    expect(await within(dialog).findByText('Version 3 is live.', {}, { timeout: 4000 })).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Close' }));
    const row = (await screen.findByText('v2')).closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Actions for version 2' }));
    await user.click(screen.getByRole('menuitem', { name: 'Make live' }));
    const back = await screen.findByRole('dialog', { name: 'Make version 2 live?' });
    expect(back).toHaveTextContent('It answers on ada-1-0, the Ada it was made with, in place of ada-1-1.');
  });

  it('shows the Ada of a version in its View', async () => {
    on();
    const { user } = renderApp('/models/tickets?tab=versions');
    const row = (await screen.findByText('v2')).closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Actions for version 2' }));
    await user.click(screen.getByRole('menuitem', { name: 'View' }));
    expect(await screen.findByRole('dialog', { name: 'Version 2 (live)' })).toHaveTextContent('Adaada-1-0kernel 3.12.2');
  });

  it('shows a refusal with the latest stable as the way on', async () => {
    on();
    server.use(
      http.post('*/api/ada/v1/models/tickets/upgrade', () =>
        apiError(422, 'E_ADA_BETA', 'ada-1-2-beta is closed to new models.', { ada: 'ada-1-2-beta', latest: 'ada-1-1' }),
      ),
    );
    const { user } = renderApp('/models/tickets?tab=versions&upgrade=ada-1-2-beta');
    const dialog = await screen.findByRole('dialog', { name: 'Upgrade Ada' });
    expect(await within(dialog).findByRole('combobox', { name: 'Move to' })).toHaveValue('ada-1-2-beta');
    await user.click(within(dialog).getByRole('button', { name: 'Upgrade to ada-1-2-beta' }));
    const refusal = await within(dialog).findByRole('alert');
    expect(refusal).toHaveTextContent('ada-1-2-beta is closed to new models.');
    expect(refusal).toHaveTextContent('Trace trace-123');
    await user.click(within(refusal).getByRole('button', { name: 'Choose ada-1-1' }));
    expect(within(dialog).getByRole('combobox', { name: 'Move to' })).toHaveValue('ada-1-1');
    expect(within(dialog).queryByRole('alert')).not.toBeInTheDocument();
  });

  it('says so when the model runs the version already, or its Ada is unavailable', async () => {
    on();
    server.use(http.post('*/api/ada/v1/models/tickets/upgrade', () => apiError(409, 'E_NO_CHANGE', 'tickets runs on ada-1-1 already.', { ada: 'ada-1-1' })));
    server.use(http.post('*/api/ada/v1/models/tickets/backtest', () => apiError(503, 'E_ADA_UNAVAILABLE', 'ada-1-1 is not installed on this deploy.')));
    const { user } = renderApp('/models/tickets?tab=versions');
    const dialog = await openUpgrade(user);
    await user.click(await within(dialog).findByRole('button', { name: 'Backtest against ada-1-1' }));
    expect(await within(dialog).findByText('ada-1-1 is not installed on this deploy.')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Upgrade to ada-1-1' }));
    expect(await within(dialog).findByText('tickets runs on ada-1-1 already.')).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: /^Choose/ })).not.toBeInTheDocument();
  });

  it('checks the cases held out', async () => {
    const fake = on();
    const { user } = renderApp('/models/tickets?tab=versions');
    const dialog = await openUpgrade(user);
    const held = await within(dialog).findByRole('spinbutton', { name: 'Hold out the newest' });
    await user.clear(held);
    await user.type(held, '0');
    await user.click(within(dialog).getByRole('button', { name: 'Backtest against ada-1-1' }));
    expect(held).toBeInvalid();
    expect(fake.state.seen.some((s) => s.path.endsWith('/backtest'))).toBe(false);
  });

  it('says when there is no other version to move to', async () => {
    const fake = adaFake({ models: [{ ...tickets(), ada: 'ada-1-1' }] });
    fake.state.releases.versions[0]!.open = false;
    server.use(...fake.handlers);
    const { user } = renderApp('/models/tickets?tab=versions');
    const dialog = await openUpgrade(user);
    expect(await within(dialog).findByText('There is no other Ada version to move to.')).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: /^Upgrade to/ })).not.toBeInTheDocument();
  });
});
