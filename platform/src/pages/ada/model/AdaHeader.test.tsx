import { screen, within } from '@testing-library/react';
import type { AdaNotice } from '@/api/ada';
import { adaFake, tickets } from '@/test/ada';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(notice: AdaNotice | null, ada = 'ada-1-0') {
  const fake = adaFake({ models: [{ ...tickets(), ada }], notices: { tickets: notice } });
  server.use(...fake.handlers);
  return fake;
}

describe('a model’s Ada in its header', () => {
  it('names the Ada it runs, with its notes a link away, and says nothing more without a notice', async () => {
    on(null, 'ada-1-1');
    renderApp('/models/tickets');
    const line = (await screen.findByText('Runs on')).parentElement!;
    expect(line).toHaveTextContent('Runs on ada-1-1 About this version');
    expect(within(line).queryByText('Beta')).not.toBeInTheDocument();
    expect(within(line).getByRole('link', { name: 'About this version' })).toHaveAttribute('href', '/settings/releases#ada-1-1');
    expect(screen.queryByRole('status', { name: 'Ada version' })).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('labels a beta Beta', async () => {
    on(null, 'ada-1-2-beta');
    renderApp('/models/tickets');
    const line = (await screen.findByText('Runs on')).parentElement!;
    expect(await within(line).findByText('Beta')).toBeInTheDocument();
  });

  it('says when a newer stable is out, with what changes and the way to upgrade', async () => {
    on({ kind: 'upgrade', message: 'ada-1-1 is available: see what changes.', to: 'ada-1-1' }, 'ada-1-0');
    const { user, router } = renderApp('/models/tickets');
    const notice = await screen.findByRole('status', { name: 'Ada version' });
    expect(notice).toHaveTextContent('ada-1-1 is available: see what changes.');
    expect(within(notice).getByRole('link', { name: 'See what changes' })).toHaveAttribute('href', '/settings/releases#ada-1-1');
    await user.click(within(notice).getByRole('link', { name: 'Backtest and upgrade' }));
    expect(router.state.location.search).toBe('?tab=versions&upgrade=ada-1-1');
    const dialog = await screen.findByRole('dialog', { name: 'Upgrade Ada' });
    expect(within(dialog).getByRole('combobox', { name: 'Move to' })).toHaveValue('ada-1-1');
  });

  it('mentions a beta quietly, as a line and not a warning', async () => {
    on({ kind: 'beta', message: 'ada-1-2-beta is in beta: try it on a backtest.', to: 'ada-1-2-beta' }, 'ada-1-1');
    const { user } = renderApp('/models/tickets');
    const notice = await screen.findByRole('status', { name: 'Ada version' });
    expect(notice).toHaveTextContent('ada-1-2-beta is in beta: try it on a backtest.');
    expect(notice.className).toMatch(/noticeQuiet/);
    await user.click(within(notice).getByRole('link', { name: 'Try it in a backtest' }));
    const dialog = await screen.findByRole('dialog', { name: 'Upgrade Ada' });
    expect(within(dialog).getByRole('combobox', { name: 'Move to' })).toHaveValue('ada-1-2-beta');
  });

  it('warns while its version is deprecated, with the end date', async () => {
    on({ kind: 'deprecated', message: 'ada-1-0 is deprecated.', to: 'ada-1-1', ends: '2027-04-18' });
    renderApp('/models/tickets');
    const notice = await screen.findByRole('alert', { name: 'Ada version' });
    expect(notice).toHaveTextContent('ada-1-0 is deprecated. It ends on 18 Apr 2027.');
    expect(notice.className).toMatch(/noticeWarn/);
    expect(within(notice).getByRole('link', { name: 'Choose a version to move to' })).toHaveAttribute('href', '/models/tickets?tab=versions&upgrade=ada-1-1');
  });

  it('says Glyphh moved it off a retired version', async () => {
    on({ kind: 'moved', message: 'Moved from ada-0-9 (retired) to ada-1-1.', to: 'ada-1-1' }, 'ada-1-1');
    renderApp('/models/tickets');
    const notice = await screen.findByRole('status', { name: 'Ada version' });
    expect(notice).toHaveTextContent('Moved from ada-0-9 (retired) to ada-1-1.');
    expect(notice.className).toMatch(/noticeInfo/);
    expect(within(notice).getByRole('link', { name: 'See what changes' })).toHaveAttribute('href', '/settings/releases#ada-1-1');
    expect(within(notice).queryByRole('link', { name: /upgrade/i })).not.toBeInTheDocument();
  });
});
