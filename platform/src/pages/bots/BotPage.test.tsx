import { screen, waitFor, within } from '@testing-library/react';
import { botsFake, inbox, waiting } from '@/test/bots';
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
    expect(await screen.findByRole('radio', { name: 'Claude Sonnet 5.5' })).toBeChecked();
    await user.click(screen.getByRole('radio', { name: 'Claude Haiku 5.5' }));
    await user.click(screen.getByRole('button', { name: 'Shuffle' }));
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Mail helper is saved.')).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/mail-helper'));
    expect(fake.state.bodies[0]).toMatchObject({ name: 'Mail helper', instructions: 'Answer every email.', model: 'claude-haiku-5-5' });
  });

  it('picks the model out of a searched, paged list with both prices', async () => {
    on();
    const { user } = renderApp('/bots/inbox-helper');
    const models = await screen.findByRole('list', { name: 'Models' });
    await waitFor(() => expect(within(models).getAllByRole('radio')).toHaveLength(6));
    const picker = screen.getByRole('group', { name: 'Model' });
    expect(picker).toHaveTextContent('1–6 of 12');
    expect(picker).toHaveTextContent('20% markup');
    // Sonnet 5.5 on Glyphh's key: $3 + 20% = $3.60 in; on the org's own key: the 20% only, $0.60.
    const sonnet = within(models).getByRole('radio', { name: 'Claude Sonnet 5.5' }).closest('label');
    expect(sonnet).toHaveTextContent('Glyphh’s key: $3.60 in · $18.00 out');
    expect(sonnet).toHaveTextContent('Your key: $0.60 in · $3.00 out');
    expect(within(picker).getByRole('button', { name: 'Previous' })).toBeDisabled();
    await user.click(within(picker).getByRole('button', { name: 'Next' }));
    expect(picker).toHaveTextContent('7–12 of 12');
    expect(within(models).getByRole('radio', { name: /Haiku 4\.5/ })).toBeInTheDocument();
    expect(within(picker).getByRole('button', { name: 'Next' })).toBeDisabled();
    await user.type(within(picker).getByLabelText('Search models'), 'opus');
    expect(within(models).getAllByRole('radio').map((r) => r.getAttribute('aria-label'))).toEqual([
      'Claude Opus 5.5',
      'Claude Opus 5',
      'Claude Opus 4.6',
    ]);
    expect(picker).toHaveTextContent('1–3 of 3');
    await user.clear(within(picker).getByLabelText('Search models'));
    await user.type(within(picker).getByLabelText('Search models'), 'zzz');
    expect(within(models).getByText('No model matches “zzz”.')).toBeInTheDocument();
  });

  it('scopes the tools per connection: adds a connection, ticks its tools with search and all or none, and saves', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=tools');
    const gmail = await screen.findByRole('region', { name: 'Gmail · chris@example.com' });
    const list = await within(gmail).findByRole('list', { name: 'Gmail · chris@example.com tools' });
    expect(within(list).getByRole('checkbox', { name: /Find email/ })).toBeChecked();
    expect(within(list).getByRole('checkbox', { name: /Send email/ })).not.toBeChecked();
    // The org's own permission for each tool shows beside it.
    expect(within(list).getByRole('checkbox', { name: /Send email/ }).closest('label')).toHaveTextContent('Needs approval');
    expect(within(list).getByRole('checkbox', { name: /Find email/ }).closest('label')).not.toHaveTextContent('Needs approval');
    expect(within(gmail).getByRole('link', { name: 'Change Gmail’s permissions' })).toHaveAttribute('href', '/connections/gmail?tab=tools');
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

  it('edits the loop as JSON and the skills, and lists the problems the server finds', async () => {
    const fake = on({ problems: ['loop[2]: no such tool gmail-send', 'gates.easy: needs options'] });
    const { user } = renderApp('/bots/inbox-helper?tab=loop');
    const spec = await screen.findByLabelText('Spec');
    expect(screen.getByRole('list', { name: 'Steps' })).toHaveTextContent('3. reply · uses Send email · waits for your approval');
    await user.clear(spec);
    await user.type(spec, '{{"loop": [[');
    expect(screen.getByText(/Not JSON yet/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save loop and skills' })).toBeDisabled();
    await user.clear(spec);
    await user.type(spec, '{{"loop": [[{{"step": "fetch"}]}');
    expect(screen.getByRole('list', { name: 'Steps' })).toHaveTextContent('1. fetch');

    expect(screen.getByLabelText('Skill name')).toHaveValue('tone');
    await user.click(screen.getByRole('button', { name: 'Add skill' }));
    const names = screen.getAllByLabelText('Skill name');
    await user.type(names[1]!, 'tone');
    expect(screen.getByText('Another skill has this name.')).toBeInTheDocument();
    await user.clear(names[1]!);
    await user.type(names[1]!, 'urgency');
    await user.type(screen.getAllByLabelText('What it says')[1]!, 'Urgent means down.');

    await user.click(screen.getByRole('button', { name: 'Save loop and skills' }));
    const problems = await screen.findByRole('list', { name: 'Problems' });
    expect(within(problems).getAllByRole('listitem').map((p) => p.textContent)).toEqual(['loop[2]: no such tool gmail-send', 'gates.easy: needs options']);
    expect(fake.state.bodies[0]).toEqual({ spec: { loop: [{ step: 'fetch' }] }, skills: { tone: 'Write short, warm replies.', urgency: 'Urgent means down.' } });
  });

  it('saves a loop the server takes', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=loop');
    await user.click(await screen.findByRole('button', { name: 'Remove tone' }));
    await user.click(screen.getByRole('button', { name: 'Save loop and skills' }));
    expect(await screen.findByText('Inbox helper’s loop is saved.')).toBeInTheDocument();
    expect(fake.state.bots[0]!.skills).toEqual({});
  });

  it('runs the bot, follows the run until it asks, and answers its batch', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=runs');
    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
    const run = screen.getByRole('button', { name: 'Run' });
    expect(run).toBeDisabled();
    await user.type(screen.getByLabelText('What to do'), 'Clear the inbox.');
    await user.click(run);
    const detail = await screen.findByRole('region', { name: 'Run' });
    expect(within(detail).getByText('Clear the inbox.')).toBeInTheDocument();
    const question = await within(detail).findByRole('region', { name: 'Question' }, { timeout: 6000 });
    expect(detail).toHaveTextContent('Needs you');
    expect(within(detail).getByLabelText('Log')).toHaveTextContent('Found 2 emails.');
    expect(within(detail).getByLabelText('Data')).toHaveTextContent('"emails": 2');
    expect(detail).toHaveTextContent('1,020 tokens');
    expect(question).toHaveTextContent('Answer these emails?');
    const send = within(question).getByRole('button', { name: 'Send answers' });
    expect(send).toBeDisabled();
    await user.click(within(question).getByRole('button', { name: 'answer' }));
    await user.click(within(within(question).getByRole('radiogroup', { name: 'Invoice overdue' })).getByRole('radio', { name: 'leave' }));
    expect(within(within(question).getByRole('radiogroup', { name: 'Lunch on Friday?' })).getByRole('radio', { name: 'answer' })).toHaveAttribute('aria-checked', 'true');
    await user.click(send);
    await waitFor(() => expect(detail).toHaveTextContent('Answered 1 email.'));
    expect(fake.state.bodies.at(-1)).toEqual({ '1': 'answer', '2': 'leave' });
    expect(fake.state.seen).toContain('run inbox-helper');
  }, 10_000);

  it('answers a one-option question with a button, and cancels a waiting run', async () => {
    const fake = on({
      runs: [
        waiting({ id: 'r-1', question: { question: 'Send the reply?', options: ['yes', 'no'], batch: null, answer_with: null } }),
        waiting({ id: 'r-2', input: 'Second', created_at: '2026-11-19T09:00:00Z' }),
      ],
    });
    const { user, router } = renderApp('/bots/inbox-helper?tab=runs');
    const question = await screen.findByRole('region', { name: 'Question' });
    await user.click(within(question).getByRole('button', { name: 'yes' }));
    await waitFor(() => expect(fake.state.seen).toContain('answer r-1'));
    expect(fake.state.bodies.at(-1)).toBe('yes');

    await user.click(within(screen.getByRole('list', { name: 'Runs' })).getByRole('button', { name: /Second/ }));
    expect(router.state.location.search).toContain('run=r-2');
    const other = await screen.findByRole('region', { name: 'Question' });
    await user.click(within(other).getByRole('button', { name: 'Cancel run' }));
    await waitFor(() => expect(fake.state.seen).toContain('cancel r-2'));
    expect(await screen.findAllByText('Cancelled')).not.toHaveLength(0);
  });

  it('marks a finished run as wrong for its gate', async () => {
    const fake = on({ runs: [waiting({ id: 'r-done', status: 'done', question: null, output: 'Answered 2 emails.' })] });
    const { user } = renderApp('/bots/inbox-helper?tab=runs&run=r-done');
    await user.click(await screen.findByRole('button', { name: 'Mark as wrong' }));
    const dialog = await screen.findByRole('dialog');
    const correct = within(dialog).getByRole('button', { name: 'Correct it' });
    expect(correct).toBeDisabled();
    await user.type(within(dialog).getByLabelText('What should have happened'), 'leave');
    await user.type(within(dialog).getByLabelText('Item (optional)'), '2');
    await user.click(correct);
    expect(await screen.findByText('The easy gate learned “leave”.')).toBeInTheDocument();
    expect(fake.state.bodies.at(-1)).toEqual({ outcome: 'leave', gate: 'easy', item: '2' });
  });

  it('shows what each gate learned', async () => {
    on();
    renderApp('/bots/inbox-helper?tab=gates');
    const gate = await screen.findByRole('listitem', { name: 'easy' });
    expect(gate).toHaveTextContent('14');
    expect(gate).toHaveTextContent('Asked you: 6');
    expect(gate).toHaveTextContent('Right on its own: 5');
  });

  it('says when a bot has no gates', async () => {
    on({ bots: [inbox({ gate_models: [] })] });
    renderApp('/bots/inbox-helper?tab=gates');
    expect(await screen.findByText('No gates')).toBeInTheDocument();
  });

  it('deletes it once asked', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper?tab=settings');
    await user.click(await screen.findByRole('button', { name: 'Delete bot' }));
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
