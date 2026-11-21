import { screen, within } from '@testing-library/react';
import { botsFake, inbox } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

describe('the Bots page', () => {
  it('is in the sidebar under Bots and shows each bot as a card with its cat and last run', async () => {
    on({ bots: [inbox({ last_run: { id: 'r-1', status: 'failed', created_at: '2026-11-20T09:00:00Z' } })] });
    const { user, router } = renderApp('/usage');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    expect(await within(sidebar).findByRole('link', { name: 'Connections' })).toHaveAttribute('href', '/connections');
    await user.click(within(sidebar).getByRole('link', { name: 'Bots' }));
    expect(router.state.location.pathname).toBe('/bots');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent(/^Bots$/);
    const card = await screen.findByRole('link', { name: 'Inbox helper' });
    expect(card).toHaveTextContent('Answers the easy emails.');
    expect(card).toHaveTextContent('1 tool · 0 Ada models');
    expect(card).toHaveTextContent('Failed');
    expect(card.querySelector('svg.cat-svg')).not.toBeNull();
    expect(card).toHaveAttribute('href', '/bots/inbox-helper');
  });

  it('says when there are no bots, and makes one with a shuffled cat and a chosen model', async () => {
    const fake = on({ bots: [] });
    const { user, router } = renderApp('/bots');
    expect(await screen.findByText('No bots yet')).toBeInTheDocument();
    await user.click(screen.getAllByRole('button', { name: 'New bot' })[0]!);
    const dialog = await screen.findByRole('dialog');
    const make = within(dialog).getByRole('button', { name: 'Make bot' });
    expect(make).toBeDisabled();
    const before = dialog.querySelector('svg')!.innerHTML;
    let shuffled = false;
    for (let i = 0; i < 10 && !shuffled; i++) {
      await user.click(within(dialog).getByRole('button', { name: 'Shuffle' }));
      shuffled = dialog.querySelector('svg')!.innerHTML !== before;
    }
    expect(shuffled).toBe(true);
    await user.type(within(dialog).getByLabelText('Name'), 'Lead sorter');
    await user.type(within(dialog).getByLabelText('What it is for'), 'Sorts new leads.');
    await user.type(within(dialog).getByLabelText('Instructions'), 'Sort each lead.');
    const model = await within(dialog).findByLabelText('Model');
    expect(model).toHaveValue('claude-sonnet-5-5');
    await user.selectOptions(model, 'claude-haiku-5-5');
    await user.click(make);
    expect(await screen.findByRole('heading', { name: 'Lead sorter', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/bots/lead-sorter');
    expect(fake.state.bodies[0]).toMatchObject({ name: 'Lead sorter', summary: 'Sorts new leads.', instructions: 'Sort each lead.', model: 'claude-haiku-5-5' });
    expect(Object.keys((fake.state.bodies[0] as { look: object }).look).sort()).toEqual(['accessory', 'extra', 'eye', 'head', 'pose', 'tail']);
  });

  it('says when the name is taken', async () => {
    on();
    const { user } = renderApp('/bots');
    await user.click(await screen.findByRole('button', { name: 'New bot' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText('Name'), 'Inbox helper');
    await user.type(within(dialog).getByLabelText('Instructions'), 'Again.');
    await user.click(within(dialog).getByRole('button', { name: 'Make bot' }));
    expect(await within(dialog).findByText(/A bot has that name already/)).toBeInTheDocument();
  });
});
