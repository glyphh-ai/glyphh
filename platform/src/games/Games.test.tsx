import { screen, waitFor, within } from '@testing-library/react';
import { staffHandlers } from '@/test/admin';
import { toolAnswers } from '@/test/games';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, server } from '@/test/server';
import { argsFrom } from './ActionDialog';
import { label } from './DataView';

function staff() {
  server.use(...staffHandlers());
}

/** The last call of one tool. */
const lastOf = (sent: Array<{ tool: string }>, tool: string) => sent.filter((s) => s.tool === tool).at(-1);

/** Every tool call the page makes: game, tool and arguments; answered from the fixtures unless `reply` says. */
function calls(reply?: (game: string, tool: string, args: Record<string, unknown>) => Response | undefined) {
  const sent: Array<{ game: string; tool: string; args: Record<string, unknown> }> = [];
  server.use(
    http.post('*/api/games/:game/tools/:tool', async ({ params, request }) => {
      const { arguments: args } = (await request.json()) as { arguments: Record<string, unknown> };
      const game = params.game as string;
      const tool = params.tool as string;
      sent.push({ game, tool, args });
      return reply?.(game, tool, args) ?? HttpResponse.json({ result: toolAnswers[`${game}/${tool}`] ?? { ok: true } });
    }),
  );
  return sent;
}

describe('All games', () => {
  it('shows each game’s health, players, revenue and what is waiting', async () => {
    staff();
    renderApp('/admin');
    const frank = await screen.findByRole('article', { name: 'Free Fall Frank' });
    expect(within(frank).getByText('Up')).toBeInTheDocument();
    expect(within(frank).getByText('Build 29d40a007e')).toBeInTheDocument();
    expect(within(frank).getByText('12,480')).toBeInTheDocument();
    const money = within(frank).getByRole('list', { name: 'Waiting' });
    expect(within(money).getByRole('link', { name: 'Levels to review' })).toHaveAttribute('href', '/admin/games/frank?tab=review');
    const revenue = within(frank).getByLabelText('Revenue');
    expect(within(revenue).getByText('$2.97')).toBeInTheDocument();
    expect(within(revenue).getByText('$483.12')).toBeInTheDocument();

    const crabby = screen.getByRole('article', { name: 'Crabby Knife Fight' });
    expect(within(crabby).getByText('Sells nothing.')).toBeInTheDocument();

    const mahj = screen.getByRole('article', { name: 'Bams & Brags' });
    expect(within(mahj).getByText('Down')).toBeInTheDocument();
    expect(within(mahj).getByText('Bams & Brags did not answer.')).toBeInTheDocument();

    const carol = screen.getByRole('article', { name: 'Send a Carol' });
    expect(within(carol).getByText('Not connected')).toBeInTheDocument();
    expect(within(carol).getByText('GAME_ADMIN_KEY_CAROL is not set on the platform.')).toBeInTheDocument();
  });

  it('shows the platform’s refusal', async () => {
    staff();
    server.use(http.get('*/api/games/overview', () => apiError(403, 'E_STAFF_ONLY', 'The games’ admin is for Glyphh’s staff.')));
    renderApp('/admin');
    expect(await screen.findByText('The games’ admin is for Glyphh’s staff.')).toBeInTheDocument();
  });
});

describe('One game', () => {
  it('opens on its first tab, a list from the game, and approves a level at once', async () => {
    staff();
    const sent = calls();
    const { user } = renderApp('/admin/games/frank');
    expect(await screen.findByRole('heading', { name: 'Free Fall Frank' })).toBeInTheDocument();
    const table = await screen.findByRole('table', { name: 'To review' });
    const row = within(table).getByText('Rooftops').closest('tr')!;
    await user.click(within(row).getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(lastOf(sent, 'admin_review')).toEqual({ game: 'frank', tool: 'admin_review', args: { id: 'lv1', decision: 'approve' } }));
    expect(await screen.findByText('Approve: done.')).toBeInTheDocument();
  });

  it('asks why before declining, in a red dialog, and sends it', async () => {
    staff();
    const sent = calls();
    const { user } = renderApp('/admin/games/frank?tab=review');
    const table = await screen.findByRole('table', { name: 'To review' });
    await user.click(within(within(table).getByText('Sewer run').closest('tr')!).getByRole('button', { name: 'Decline' }));
    const dialog = await screen.findByRole('dialog', { name: 'Decline: Sewer run' });
    expect(within(dialog).getByText('This can’t quietly be taken back.')).toBeInTheDocument();
    const confirm = within(dialog).getByRole('button', { name: 'Decline' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Why, for its maker'), 'The gaps are too tight.');
    await user.click(confirm);
    await waitFor(() => expect(lastOf(sent, 'admin_review')).toEqual({ game: 'frank', tool: 'admin_review', args: { id: 'lv2', decision: 'decline', note: 'The gaps are too tight.' } }));
  });

  it('shows a whole answer as facts and its lists as tables', async () => {
    staff();
    renderApp('/admin/games/frank?tab=stats');
    expect(await screen.findByText('Times are seconds, money is cents.')).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Ad links' })).toBeInTheDocument();
    expect(screen.getByText('Players, 24h')).toBeInTheDocument();
  });

  it('opens a player in a dialog', async () => {
    staff();
    const sent = calls();
    const { user } = renderApp('/admin/games/frank?tab=players');
    const table = await screen.findByRole('table', { name: 'Players' });
    await user.click(within(table).getByRole('button', { name: 'Open' }));
    const dialog = await screen.findByRole('dialog', { name: 'Details' });
    expect(await within(dialog).findByText('pack:1')).toBeInTheDocument();
    expect(sent.at(-1)).toEqual({ game: 'frank', tool: 'admin_player', args: { did: 'd1' } });
  });

  it('searches, narrows and pages a list', async () => {
    staff();
    const sent = calls();
    const { user } = renderApp('/admin/games/crabby?tab=players');
    await screen.findByRole('table', { name: 'Players' });
    expect(sent[0]).toEqual({ game: 'crabby', tool: 'admin_list', args: { what: 'players', page: 0 } });
    await user.type(screen.getByLabelText('Search'), 'pinch');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(sent.at(-1)?.args).toEqual({ what: 'players', q: 'pinch', page: 0 }));
    await user.selectOptions(screen.getByLabelText('Show'), 'banned');
    await waitFor(() => expect(sent.at(-1)?.args).toEqual({ what: 'players', state: 'banned', q: 'pinch', page: 0 }));
    expect(await screen.findByText('Page 1 of 2, 2 in all')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(sent.at(-1)?.args.page).toBe(1));
  });

  it('offers each row only the actions that fit it, and shows what the game said when it could not', async () => {
    staff();
    const sent = calls((_game, tool) => (tool === 'admin_ban' ? apiError(422, 'E_GAME_SAID', 'There is no such player.') : undefined));
    const { user } = renderApp('/admin/games/crabby?tab=players');
    const table = await screen.findByRole('table', { name: 'Players' });
    const banned = within(table).getByText('Clawd').closest('tr')!;
    expect(within(banned).queryByRole('button', { name: 'Ban' })).not.toBeInTheDocument();
    expect(within(banned).getByRole('button', { name: 'Lift ban' })).toBeInTheDocument();
    await user.click(within(within(table).getByText('Pinchy').closest('tr')!).getByRole('button', { name: 'Ban' }));
    const dialog = await screen.findByRole('dialog', { name: 'Ban: Pinchy' });
    await user.type(within(dialog).getByLabelText('Why'), 'cheating');
    await user.click(within(dialog).getByRole('button', { name: 'Ban' }));
    expect(await within(dialog).findByText('There is no such player.')).toBeInTheDocument();
    expect(lastOf(sent, 'admin_ban')).toEqual({ game: 'crabby', tool: 'admin_ban', args: { uid: 'google:7', why: 'cheating' } });
  });

  it('shows what would happen before a ban the game asks to confirm, then confirms it', async () => {
    staff();
    const sent = calls((_game, tool, args) =>
      tool === 'admin_ban' ? HttpResponse.json({ result: args.confirm ? { done: true } : { would: 'Ann leaves her table and can’t sit with others.' } }) : undefined,
    );
    const { user } = renderApp('/admin/games/mahj?tab=players');
    const table = await screen.findByRole('table', { name: 'Players' });
    await user.click(within(table).getByRole('button', { name: 'Ban' }));
    const dialog = await screen.findByRole('dialog', { name: 'Ban: Ann' });
    const reason = within(dialog).getByLabelText('Reason');
    await user.type(reason, 'no');
    expect(within(dialog).getByRole('button', { name: 'Show what happens' })).toBeDisabled();
    await user.type(reason, 'pe, abuse at the table');
    await user.click(within(dialog).getByRole('button', { name: 'Show what happens' }));
    expect(await within(dialog).findByText('Ann leaves her table and can’t sit with others.')).toBeInTheDocument();
    expect(sent.filter((s) => s.tool === 'admin_ban').map((s) => s.args)).toEqual([{ uid: 'email:ann@example.com', reason: 'nope, abuse at the table' }]);
    await user.click(within(dialog).getByRole('button', { name: 'Ban' }));
    await waitFor(() => expect(lastOf(sent, 'admin_ban')).toMatchObject({ args: { uid: 'email:ann@example.com', reason: 'nope, abuse at the table', confirm: true } }));
    expect(await screen.findByText('Ban: done.')).toBeInTheDocument();
  });

  it('shows what a player wrote as plain text', async () => {
    staff();
    renderApp('/admin/games/carol?tab=carols');
    const table = await screen.findByRole('table', { name: 'Carols' });
    expect(within(table).getByText('For Mum')).toBeInTheDocument();
    expect(within(table).getByRole('button', { name: 'Take down' })).toBeInTheDocument();
    expect(within(table).queryByRole('button', { name: 'Put back' })).not.toBeInTheDocument();
  });

  it('answers a game it does not know with Page not found', async () => {
    staff();
    renderApp('/admin/games/pong');
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });
});

describe('helpers', () => {
  it('turns typed fields into arguments', () => {
    const fields = [
      { name: 'credits', label: 'Credits', kind: 'number' as const },
      { name: 'reset', label: 'Reset', kind: 'check' as const },
      { name: 'reason', label: 'Reason' },
      { name: 'note', label: 'Note' },
    ];
    expect(argsFrom(fields, { credits: '5', reset: true, reason: ' gift ', note: '  ' })).toEqual({ credits: 5, reset: true, reason: 'gift' });
  });

  it('words a game’s keys plainly', () => {
    expect([label('players24'), label('reportsOpen'), label('revenue_usd'), label('players7')]).toEqual(['Players, 24h', 'Reports open', 'Revenue usd', 'Players, 7 days']);
  });
});
