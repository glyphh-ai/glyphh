import { screen, waitFor, within } from '@testing-library/react';
import { botsFake, waiting } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

describe('the approvals queue', () => {
  it('counts the waiting runs in the sidebar and answers them in place', async () => {
    const fake = on({
      runs: [
        waiting(),
        waiting({ id: 'r-2', input: 'Post it', question: { question: 'Post in #general?', options: ['yes', 'no'], batch: null, answer_with: null } }),
      ],
    });
    const { user, router } = renderApp('/bots');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    const link = await within(sidebar).findByRole('link', { name: /^Approvals\s*2 waiting$/ });
    await user.click(link);
    expect(router.state.location.pathname).toBe('/approvals');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('BotsApprovals');

    const queue = await screen.findByRole('list', { name: 'Waiting runs' });
    const items = within(queue).getAllByRole('article');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveAccessibleName('Inbox helper: Answer these emails?');
    expect(within(items[0]!).getByRole('link', { name: 'Inbox helper' })).toHaveAttribute('href', '/bots/inbox-helper?tab=runs&run=r-wait');

    await user.click(within(items[1]!).getByRole('button', { name: 'yes' }));
    await waitFor(() => expect(within(queue).getAllByRole('article')).toHaveLength(1));
    expect(await within(sidebar).findByRole('link', { name: /^Approvals\s*1 waiting$/ })).toBeInTheDocument();

    const batch = within(queue).getByRole('article');
    await user.click(within(batch).getByRole('button', { name: 'leave' }));
    await user.click(within(batch).getByRole('button', { name: 'Send answers' }));
    expect(await screen.findByText('Nothing is waiting on you')).toBeInTheDocument();
    expect(within(sidebar).getByRole('link', { name: 'Approvals' })).toBeInTheDocument();
    expect(fake.state.bodies).toEqual(['yes', { '1': 'leave', '2': 'leave' }]);
  });

  it('cancels a waiting run', async () => {
    const fake = on({ runs: [waiting()] });
    const { user } = renderApp('/approvals');
    await user.click(await screen.findByRole('button', { name: 'Cancel run' }));
    expect(await screen.findByText('Nothing is waiting on you')).toBeInTheDocument();
    expect(fake.state.seen).toEqual(['cancel r-wait']);
  });
});
