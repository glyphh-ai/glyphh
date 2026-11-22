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
  it('opens on Overview: its gates in Ada, what waits on you, its decisions, what it watches and its tools in Claude', async () => {
    const decided = waiting({
      id: 'r-done',
      status: 'done',
      input: 'Morning',
      question: null,
      data: {
        _gates: { easy: { each: true, outcome: 'answer 1, leave 1', by: 'ada', asked: 1, decided: 1, defaulted: 0 } },
        decide: {
          decisions: [
            { n: 1, label: 'Lunch on Friday?', outcome: 'answer', by: 'ada', p: 0.92 },
            { n: 2, label: 'Invoice overdue', outcome: 'leave', by: 'person' },
          ],
        },
      },
      created_at: '2026-11-19T09:00:00Z',
    });
    const fake = on({ runs: [waiting(), decided] });
    const { user } = renderApp('/bots/inbox-helper');
    expect(await screen.findByRole('heading', { name: 'Inbox helper', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Botsinbox-helper');

    const gate = await screen.findByRole('link', { name: 'easy gate' });
    expect(gate).toHaveAttribute('href', '/bots/inbox-helper?tab=gates');
    expect(gate).toHaveTextContent('14precedents');
    expect(gate).toHaveTextContent('Ada decided 8 · you 6');
    expect(gate).toHaveTextContent('Asks you40%');
    expect(gate).toHaveTextContent('Right when it asked83% (5 of 6)');

    const asks = await screen.findByRole('region', { name: 'Waiting on you' });
    expect(within(asks).getByRole('region', { name: 'Question' })).toHaveTextContent('Answer these emails?');

    const latest = await screen.findByRole('list', { name: 'Latest runs' });
    const items = within(latest).getByRole('list', { name: 'easy items' });
    expect(within(items).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      expect.stringContaining('1. Lunch on Friday?answerAda · 92% sure'),
      expect.stringContaining('2. Invoice overdueleaveYou'),
    ]);
    await user.click(within(items).getByRole('button', { name: 'Wrong? easy item 2' }));
    const dialog = await screen.findByRole('dialog', { name: 'Mark as wrong' });
    expect(within(dialog).getByLabelText('Item (optional)')).toHaveValue('2');
    await user.type(within(dialog).getByLabelText('What should have happened'), 'answer');
    await user.click(within(dialog).getByRole('button', { name: 'Correct it' }));
    expect(await screen.findByText('The easy gate learned “answer”.')).toBeInTheDocument();
    expect(fake.state.bodies.at(-1)).toEqual({ outcome: 'answer', gate: 'easy', item: '2' });

    expect(screen.getByLabelText('What it watches')).toHaveTextContent('WatchesGmail · Find email');
    expect(screen.getByLabelText('What it watches')).toHaveTextContent('ThenGmail · Send email · asks you first');
    expect(within(screen.getByRole('list', { name: 'Tools in Claude' })).getAllByRole('listitem').map((li) => li.querySelector('code')?.textContent)).toEqual([
      'bot_run',
      'bot_runs',
      'bot_run_answer',
      'bot_run_wrong',
      'bot_gates',
      'bot_approvals',
    ]);
  });

  it('keeps the model, permission mode and voice under Advanced in Settings, and saves a change of name, instructions, model and cat', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper?tab=settings');
    const name = await screen.findByLabelText('Name');
    await user.clear(name);
    await user.type(name, 'Mail helper');
    await user.clear(screen.getByLabelText('Instructions'));
    await user.type(screen.getByLabelText('Instructions'), 'Answer every email.');
    const advanced = screen.getByText('Advanced', { exact: true }).closest('details')!;
    expect(advanced).not.toHaveAttribute('open');
    await user.click(screen.getByText('Advanced', { exact: true }));
    expect(advanced).toHaveAttribute('open');
    const model = within(advanced).getByRole('combobox', { name: 'Model' });
    await waitFor(() => expect(model).toHaveValue('claude-sonnet-5-5'));
    await user.selectOptions(model, 'claude-haiku-5-5');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Permission mode' }), 'auto');
    const voice = await screen.findByRole('combobox', { name: 'Voice' });
    await waitFor(() => expect(within(voice).getAllByRole('option')).toHaveLength(6));
    await user.selectOptions(voice, 'bm_george');
    const crew = screen.getByRole('list', { name: 'Glyphh cats' });
    await user.click(within(crew).getByRole('button', { name: 'Koda' }));
    expect(within(crew).getByRole('button', { name: 'Koda' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('Mail helper is saved.')).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/mail-helper'));
    expect(fake.state.bodies[0]).toMatchObject({
      name: 'Mail helper',
      instructions: 'Answer every email.',
      model: 'claude-haiku-5-5',
      permission_mode: 'auto',
      voice: 'bm_george',
      mascot: '',
      look: { head: 'folded', eye: 'sleepy', accessory: 'shades' },
    });
  });

  it('picks the model from a plain list of names, its price under it, the permission mode beside it and a voice', async () => {
    on();
    const { user } = renderApp('/bots/inbox-helper?tab=settings');
    await user.click(await screen.findByText('Advanced', { exact: true }));
    const model = await screen.findByRole('combobox', { name: 'Model' });
    await waitFor(() => expect(within(model).getAllByRole('option')).toHaveLength(12));
    expect(within(model).getAllByRole('option').slice(0, 3).map((o) => o.textContent)).toEqual(['Claude Sonnet 5.5 (default)', 'Claude Haiku 5.5', 'Claude Opus 5.5']);
    // Sonnet 5.5 on Glyphh's key: $3 + 20% = $3.60 in.
    expect(screen.getByText(/\$3\.60 in · \$18\.00 out per million tokens on Glyphh’s Claude key/)).toBeInTheDocument();
    expect(screen.getByText(/Every tool step waits for your yes/)).toBeInTheDocument();
    await user.selectOptions(screen.getByRole('combobox', { name: 'Permission mode' }), 'connection');
    expect(screen.getByText(/Only the tools a connection says to ask about/)).toBeInTheDocument();
    const voice = await screen.findByRole('combobox', { name: 'Voice' });
    await waitFor(() => expect(within(voice).getAllByRole('option').map((o) => o.textContent)).toContain('George · British male'));
    expect(screen.getByText('You can hear it once bots speak: samples are not out yet.')).toBeInTheDocument();
  });

  it('draws a mascot from words in Settings, and saves it', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=settings');
    const mascot = await screen.findByRole('group', { name: 'Mascot' });
    // Describe a new one sits beside Shuffle; the words and the drawing live in a modal, not under the cats.
    const buttons = within(mascot).getAllByRole('button').map((b) => b.textContent);
    expect(buttons.slice(-2)).toEqual(['Shuffle', 'Describe a new one']);
    expect(screen.queryByLabelText('Describe it')).not.toBeInTheDocument();
    await user.click(within(mascot).getByRole('button', { name: 'Describe a new one' }));
    const dialog = await screen.findByRole('dialog', { name: 'Describe a new mascot' });
    expect(within(dialog).getByRole('button', { name: 'Draw it' })).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Describe it'), 'a cat in a party hat');
    await user.click(within(dialog).getByRole('button', { name: 'Draw it' }));
    expect(await within(dialog).findByRole('img', { name: 'The new mascot' })).toBeInTheDocument();
    // Not on the bot until Use it; Try again draws once more from the same words.
    expect(screen.queryByRole('img', { name: 'Its own mascot' })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(fake.state.seen.filter((s) => s === 'mascot a cat in a party hat')).toHaveLength(2));
    await user.click(await within(dialog).findByRole('button', { name: 'Use it' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    const drawn = await screen.findByRole('img', { name: 'Its own mascot' });
    expect(drawn.getAttribute('src')).toMatch(/^data:image\/svg\+xml/);
    expect(fake.state.seen).toContain('mascot a cat in a party hat');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(fake.state.bodies[0]).toMatchObject({ mascot: expect.stringContaining('<svg') }));
  });

  it('scopes the tools per connection as claude.ai’s tool permissions: sections, switches, the approval hand, search, and saves', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?tab=tools');
    const gmail = await screen.findByRole('region', { name: 'Gmail · chris@example.com' });
    const tools = await within(gmail).findByRole('group', { name: 'Gmail · chris@example.com tools' });
    expect(gmail).toHaveTextContent('1 of 3 tools on');
    expect(within(gmail).getByRole('link', { name: 'All of Gmail’s permissions' })).toHaveAttribute('href', '/connections/gmail?tab=tools');
    // Sections fold; opened, a line per tool with a switch, no description or pill printed.
    const reads = within(tools).getByRole('region', { name: 'Read-only tools' });
    const writes = within(tools).getByRole('region', { name: 'Write/delete tools' });
    await user.click(within(reads).getByRole('button', { name: /Read-only tools/ }));
    await user.click(within(writes).getByRole('button', { name: /Write\/delete tools/ }));
    expect(within(reads).getByRole('switch', { name: 'Find email' })).toBeChecked();
    expect(within(writes).getByRole('switch', { name: 'Send email' })).not.toBeChecked();
    expect(gmail).not.toHaveTextContent('Sends an email.');
    expect(gmail).not.toHaveTextContent('Needs approval');
    // The org's permission is the small hand: Send email asks, Find email does not; off, it cannot be set.
    expect(within(reads).getByRole('button', { name: 'Approval for Find email' })).toHaveAttribute('aria-pressed', 'false');
    expect(within(writes).getByRole('button', { name: 'Approval for Send email' })).toBeDisabled();

    await user.type(within(gmail).getByLabelText('Search tools'), 'send');
    expect(within(tools).queryByRole('region', { name: 'Read-only tools' })).not.toBeInTheDocument();
    expect(within(tools).getAllByRole('switch').map((s) => s.getAttribute('aria-label'))).toEqual(['All write/delete tools', 'Send email']);
    await user.click(within(tools).getByRole('switch', { name: 'Send email' }));
    expect(gmail).toHaveTextContent('2 of 3 tools on');
    // Its approval is the connection's, saved at once for every bot.
    await user.click(within(tools).getByRole('button', { name: 'Approval for Send email' }));
    await waitFor(() => expect(within(tools).getByRole('button', { name: 'Approval for Send email' })).toHaveAttribute('aria-pressed', 'false'));
    expect(fake.state.bodies[0]).toEqual({ 'gmail-send-email': 'allow' });
    await user.clear(within(gmail).getByLabelText('Search tools'));
    await user.click(within(gmail).getByRole('button', { name: /Read-only tools/ }));
    await user.click(within(gmail).getByRole('switch', { name: 'Find email' }));
    expect(gmail).toHaveTextContent('1 of 3 tools on');

    // Slack is the one connection not on the bot yet; added, every tool of it is on.
    const add = screen.getByLabelText('Add a connection');
    expect(within(add).getAllByRole('option').map((o) => o.textContent)).toEqual(['Slack']);
    await user.click(screen.getByRole('button', { name: 'Add' }));
    const slack = await screen.findByRole('region', { name: 'Slack' });
    expect(screen.queryByLabelText('Add a connection')).not.toBeInTheDocument();
    await waitFor(() => expect(slack).toHaveTextContent('1 of 1 tool on'));
    // The section's switch turns the whole section off and on.
    await user.click(within(slack).getByRole('switch', { name: 'All write/delete tools' }));
    expect(slack).toHaveTextContent('0 of 1 tool on');
    await user.click(within(slack).getByRole('switch', { name: 'All write/delete tools' }));
    expect(slack).toHaveTextContent('1 of 1 tool on');
    expect(screen.queryByRole('button', { name: /Select (all|none)/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save tools' }));
    expect(await screen.findByText('Inbox helper’s tools are saved.')).toBeInTheDocument();
    expect(fake.state.bodies.at(-1)).toEqual([
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
    expect(within(gate).getByLabelText('Outcomes')).toHaveTextContent('answerleave');
    expect(gate).toHaveTextContent('14precedents');
    expect(gate).toHaveTextContent('Asks you40%');
    expect(gate).toHaveTextContent('Right when it asked83% (5 of 6)');
    expect(gate).toHaveTextContent('Corrected1 time');
    expect(within(gate).getByText('No decisions in its recent runs.')).toBeInTheDocument();
  });

  it('opens the loop as JSON from an old link (?tab=loop) in Settings, Advanced open', async () => {
    on();
    renderApp('/bots/inbox-helper?tab=loop');
    expect(await screen.findByRole('tab', { name: 'Settings' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByLabelText('Spec').closest('details')).toHaveAttribute('open');
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
