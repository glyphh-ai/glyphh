import { screen, waitFor, within } from '@testing-library/react';
import { adaFake, tickets } from '@/test/ada';
import { botsFake, inbox } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

describe('a bot’s page', () => {
  it('opens on Overview with its cat, and saves a change of name, instructions, model and cat', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper');
    expect(await screen.findByRole('heading', { name: 'Inbox helper', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Botsinbox-helper');
    const name = screen.getByLabelText('Name');
    await user.clear(name);
    await user.type(name, 'Mail helper');
    await user.clear(screen.getByLabelText('Instructions'));
    await user.type(screen.getByLabelText('Instructions'), 'Answer every email.');
    await user.selectOptions(await screen.findByLabelText('Model'), 'claude-haiku-5-5');
    await user.click(screen.getByRole('button', { name: 'Shuffle' }));
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Mail helper is saved.')).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/mail-helper'));
    expect(fake.state.bodies[0]).toMatchObject({ name: 'Mail helper', instructions: 'Answer every email.', model: 'claude-haiku-5-5' });
  });

  it('scopes the tools per connection: adds a connection, ticks its tools with search and all or none, and saves', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=tools');
    const gmail = await screen.findByRole('region', { name: 'Gmail · chris@example.com' });
    const list = await within(gmail).findByRole('list', { name: 'Gmail · chris@example.com tools' });
    expect(within(list).getByRole('checkbox', { name: /Find email/ })).toBeChecked();
    expect(within(list).getByRole('checkbox', { name: /Send email/ })).not.toBeChecked();
    expect(gmail).toHaveTextContent('1 of 3 tools allowed');

    await user.type(within(gmail).getByLabelText('Search tools'), 'send');
    expect(within(list).getAllByRole('checkbox')).toHaveLength(1);
    await user.click(within(gmail).getByRole('button', { name: 'Select all' }));
    expect(gmail).toHaveTextContent('2 of 3 tools allowed');
    await user.clear(within(gmail).getByLabelText('Search tools'));
    await user.click(within(gmail).getByRole('checkbox', { name: /Find email/ }));
    expect(gmail).toHaveTextContent('1 of 3 tools allowed');

    // Slack is the one connection not on the bot yet.
    const add = screen.getByLabelText('Add a connection');
    expect(within(add).getAllByRole('option').map((o) => o.textContent)).toEqual(['Slack']);
    await user.click(screen.getByRole('button', { name: 'Add' }));
    const slack = await screen.findByRole('region', { name: 'Slack' });
    expect(screen.queryByLabelText('Add a connection')).not.toBeInTheDocument();
    await user.click(await within(slack).findByRole('button', { name: 'Select all' }));
    await user.click(within(slack).getByRole('button', { name: 'Select none' }));
    await user.click(within(slack).getByRole('checkbox', { name: /Send message/ }));

    await user.click(screen.getByRole('button', { name: 'Save tools' }));
    expect(await screen.findByText('Inbox helper’s tools are saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toEqual([
      { connection_id: 'c-gmail', tools: ['gmail-send-email'] },
      { connection_id: 'c-slack', tools: ['slack-send-message'] },
    ]);
    expect(fake.state.bots[0]!.connections.map((c) => c.app_name)).toEqual(['Gmail', 'Slack']);
  });

  it('takes a connection off the bot', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=tools');
    const gmail = await screen.findByRole('region', { name: 'Gmail · chris@example.com' });
    await user.click(within(gmail).getByRole('button', { name: 'Take off' }));
    expect(screen.queryByRole('region', { name: 'Gmail · chris@example.com' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save tools' }));
    await waitFor(() => expect(fake.state.bodies[0]).toEqual([]));
  });

  it('sends to Connections when the org has none, and says when Pipedream is not set up', async () => {
    on({ bots: [inbox({ connections: [] })], connections: [] });
    const { user, router } = renderApp('/bots/inbox-helper?tab=tools');
    await user.click(await screen.findByRole('link', { name: 'Connect an app' }));
    expect(router.state.location.pathname).toBe('/connections');
    on({ off: true });
    renderApp('/bots/inbox-helper?tab=tools');
    expect(await screen.findByText('Connections are not set up')).toBeInTheDocument();
  });

  it('lets the bot ask the org’s Ada models', async () => {
    server.use(...adaFake({ models: [tickets()] }).handlers);
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=models');
    const box = await screen.findByRole('checkbox', { name: /tickets/ });
    expect(box).not.toBeChecked();
    expect(screen.getByRole('list', { name: 'Ada models' })).toHaveTextContent('1,240 precedents');
    await user.click(box);
    await user.click(screen.getByRole('button', { name: 'Save models' }));
    expect(await screen.findByText('Inbox helper’s Ada models are saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toEqual({ models: ['tickets'] });
  });

  it('runs the bot and follows the run until it is done, with its steps, answer, tokens and cost', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=runs');
    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
    const run = screen.getByRole('button', { name: 'Run' });
    expect(run).toBeDisabled();
    await user.type(screen.getByLabelText('What to do'), 'Clear the inbox.');
    await user.click(run);
    const detail = await screen.findByRole('region', { name: 'Run' });
    expect(within(detail).getByText('Clear the inbox.')).toBeInTheDocument();
    await waitFor(() => expect(within(detail).getByText('Answered 2 emails.')).toBeInTheDocument(), { timeout: 6000 });
    expect(detail).toHaveTextContent('Done');
    expect(detail).toHaveTextContent('1,500 tokens');
    expect(detail).toHaveTextContent('Tool · gmail-find-email');
    expect(detail).toHaveTextContent('Both are easy.');
    expect(screen.getByRole('list', { name: 'Runs' })).toHaveTextContent('Clear the inbox.');
    expect(fake.state.seen).toContain('run inbox-helper');
  }, 10_000);

  it('saves its limits, and deletes it once asked', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper?tab=settings');
    const turns = await screen.findByLabelText('Most turns a run may take');
    await user.clear(turns);
    await user.type(turns, '5');
    const usd = screen.getByLabelText('Most a run may cost, in dollars');
    await user.clear(usd);
    await user.type(usd, '0.5');
    await user.click(screen.getByRole('button', { name: 'Save limits' }));
    expect(await screen.findByText('Inbox helper’s limits are saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toEqual({ limits: { max_turns: 5, usd_per_run: 0.5 } });

    const again = screen.getByLabelText('Most turns a run may take');
    await user.clear(again);
    await user.type(again, '1.5');
    expect(screen.getByRole('button', { name: 'Save limits' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Delete bot' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots'));
    expect(fake.state.seen).toContain('delete inbox-helper');
    expect(await screen.findByText('No bots yet')).toBeInTheDocument();
  });

  it('says when there is no such bot', async () => {
    on();
    renderApp('/bots/nope');
    expect(await screen.findByText(/There is no such bot/)).toBeInTheDocument();
  });
});
