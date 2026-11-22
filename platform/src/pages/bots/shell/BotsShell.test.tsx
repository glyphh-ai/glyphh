import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { botsFake, drawnMascot, inbox, waiting, weekdays } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';
import { swarmsFake } from '@/test/swarms';
import { safeHref, md } from './md';

/** The org's bots and connections, and its projects (none unless given). */
function on(given?: Parameters<typeof botsFake>[0], projects: Parameters<typeof swarmsFake>[0] = { swarms: [] }) {
  const fake = botsFake(given);
  const swarms = swarmsFake(projects);
  server.use(...fake.handlers, ...swarms.handlers);
  return Object.assign(fake, { swarms });
}

const decided = () =>
  waiting({
    id: 'r-done',
    status: 'done',
    input: 'Morning',
    output: 'Answered **1** email.',
    question: null,
    data: {
      _gates: { easy: { each: true, outcome: 'answer 1, leave 1', by: 'ada', asked: 1, decided: 1, defaulted: 0 } },
      decide: {
        decisions: [
          { n: 1, label: 'Lunch on Friday?', outcome: 'answer', by: 'ada', p: 0.97 },
          { n: 2, label: 'Invoice overdue', outcome: 'leave', by: 'person' },
        ],
      },
    },
    finished_at: '2026-11-20T09:01:00Z',
  });

describe('the Bots area, as the Glyphh Bot app', () => {
  it('has the rail (BOTS | CONNECTIONS, the bots, New bot, the account), the chat and the status bar, with the logo as the image', async () => {
    on({ bots: [inbox(), inbox({ id: 'b-2', slug: 'quiet', name: 'Quiet', summary: 'Says little.', gate_models: [] })], runs: [waiting()] });
    renderApp('/bots');
    const rail = await screen.findByRole('complementary', { name: 'Bots and connections' });
    expect(within(rail).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Bots', 'Connections']);
    expect(within(rail).getByRole('tab', { name: 'Bots' })).toHaveAttribute('aria-selected', 'true');
    const bots = await within(rail).findByRole('navigation', { name: 'Your bots' });
    await waitFor(() => expect(within(bots).getAllByRole('link')).toHaveLength(2));
    const [helper, quiet] = within(bots).getAllByRole('link');
    // A round cat, the name with its small tag, and a line: what it is for, or that it needs you.
    expect(helper).toHaveTextContent('Inbox helper 1 gate');
    await waitFor(() => expect(helper).toHaveTextContent('Needs you'));
    expect(quiet).toHaveTextContent('Quiet Says little.');
    // With no project, the first bot is the room.
    expect(helper).toHaveAttribute('aria-current', 'page');
    expect(within(rail).getByRole('button', { name: '+ New bot' })).toBeInTheDocument();
    expect(await within(rail).findByRole('button', { name: 'Your account' })).toHaveTextContent('chris@example.com');
    expect(within(screen.getByRole('banner')).getByRole('img', { name: 'Glyphh' })).toHaveAttribute('src', '/glyphh-logo-text-white.png');
    const status = screen.getByRole('contentinfo');
    await waitFor(() => expect(status).toHaveTextContent('Connectors 2'));
    expect(status).toHaveTextContent('Glyphh connected');
    expect(status).toHaveTextContent('Permissions Ask first');
    expect(status).toHaveTextContent('Runs on Glyphh cloud');
    // The product nav stays, with Bots in it; no breadcrumb bar, no page tabs.
    expect(within(screen.getByRole('complementary', { name: 'Main' })).getByRole('link', { name: 'Bots' })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Overview' })).not.toBeInTheDocument();
  });

  it('opens a bot with nothing said yet on its cat, a headline, ideas and the composer with its pills', async () => {
    const fake = on({ bots: [inbox({ runs_on: 'rr-acme', schedule: weekdays() })] });
    const { user } = renderApp('/bots/inbox-helper');
    expect(await screen.findByRole('heading', { name: 'What should Inbox helper do?', level: 1 })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'is:unread' })).toBeInTheDocument(); // an idea: what its schedule gives it
    expect(screen.getByRole('textbox', { name: 'Give Inbox helper a task…' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    // The pills: Ada, runs on, model, permission mode, schedule. No rounds.
    expect(screen.getByRole('button', { name: /Ada · 1 gate/ })).toBeInTheDocument();
    const where = screen.getByRole('combobox', { name: 'Runs on' });
    await waitFor(() => expect(within(where).getAllByRole('option')).toHaveLength(3));
    expect(within(where).getAllByRole('option').map((o) => o.textContent)).toEqual(['Glyphh cloud', 'Studio Mac', 'Acme (offline)']);
    expect(where).toHaveValue('rr-acme');
    expect(screen.getByText(/Acme is offline/)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Schedule' })).toHaveValue('weekdays');
    expect(screen.queryByText(/round/i)).not.toBeInTheDocument();
    await waitFor(() => expect(within(screen.getByRole('combobox', { name: 'Model' })).getAllByRole('option').length).toBeGreaterThan(3));
    expect(screen.getByRole('combobox', { name: 'Model' })).toHaveValue('claude-sonnet-5-5');
    // The server's refusal is said under the composer.
    await user.type(screen.getByRole('textbox', { name: 'Give Inbox helper a task…' }), 'Clear the inbox.{Enter}');
    expect(await screen.findByText(/Acme is not linked to Glyphh right now/)).toBeInTheDocument();
    // A pill changes the bot there and then.
    await user.selectOptions(screen.getByRole('combobox', { name: 'Permission mode' }), 'auto');
    await waitFor(() => expect(fake.state.bodies[0]).toEqual({ permission_mode: 'auto' }));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Runs on' }), '');
    await waitFor(() => expect(fake.state.bodies[1]).toEqual({ runs_on: null }));
  });

  it('runs a bot as a conversation: the task on the right, the bot’s turn, and what it asks answered in place', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper');
    await user.type(await screen.findByRole('textbox', { name: 'Give Inbox helper a task…' }), 'Clear the inbox.');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    const turn = await screen.findByRole('article', { name: /^Inbox helper:/ });
    expect(screen.getByText('Clear the inbox.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'What should Inbox helper do?' })).not.toBeInTheDocument();
    const question = await screen.findByRole('region', { name: 'Question' }, { timeout: 6000 });
    expect(screen.getByRole('article', { name: 'Inbox helper: Needs you' })).toBeInTheDocument();
    expect(question).toHaveTextContent('Inbox helper asks');
    expect(question).toHaveTextContent('Answer these emails?');
    // Its steps fold into one line.
    await user.click(within(turn).getByRole('button', { name: 'Ran 2 steps' }));
    expect(within(turn).getByLabelText('Steps')).toHaveTextContent('Found 2 emails.');
    const send = within(question).getByRole('button', { name: 'Send answers' });
    expect(send).toBeDisabled();
    await user.click(within(question).getByRole('button', { name: 'All answer' }));
    await user.click(within(within(question).getByRole('radiogroup', { name: 'Invoice overdue' })).getByRole('radio', { name: 'leave' }));
    expect(within(within(question).getByRole('radiogroup', { name: 'Lunch on Friday?' })).getByRole('radio', { name: 'answer' })).toHaveAttribute('aria-checked', 'true');
    await user.click(send);
    await waitFor(() => expect(screen.getByRole('article', { name: 'Inbox helper: done' })).toHaveTextContent('Answered 1 email.'));
    expect(fake.state.bodies.at(-1)).toEqual({ '1': 'answer', '2': 'leave' });
    expect(fake.state.seen).toContain('run inbox-helper');
  }, 12_000);

  it('answers a one-option question with a button, and cancels a waiting run', async () => {
    const fake = on({
      runs: [
        waiting({ id: 'r-1', question: { question: 'Send the reply?', options: ['yes', 'no'], batch: null, answer_with: null } }),
        waiting({ id: 'r-2', input: 'Second', created_at: '2026-11-19T09:00:00Z' }),
      ],
    });
    const { user } = renderApp('/bots/inbox-helper');
    const questions = await screen.findAllByRole('region', { name: 'Question' });
    // Oldest first, as a chat reads: the newest run is the last turn.
    expect(questions.map((q) => q.querySelector('.ask-q')!.textContent)).toEqual(['Answer these emails?', 'Send the reply?']);
    await user.click(within(questions[1]!).getByRole('button', { name: 'yes' }));
    await waitFor(() => expect(fake.state.seen).toContain('answer r-1'));
    expect(fake.state.bodies.at(-1)).toBe('yes');
    await user.click(within(screen.getByRole('region', { name: 'Question' })).getByRole('button', { name: 'Cancel run' }));
    await waitFor(() => expect(fake.state.seen).toContain('cancel r-2'));
    expect(await screen.findByRole('article', { name: 'Inbox helper: cancelled' })).toBeInTheDocument();
  });

  it('shows what Ada decided as rows in the bot’s turn: the item, the outcome, who decided, Right or Wrong', async () => {
    const fake = on({ runs: [decided()] });
    const { user } = renderApp('/bots/inbox-helper');
    const table = await screen.findByRole('table', { name: 'Decisions' });
    const rows = within(table).getAllByRole('row');
    expect(rows.map((r) => r.textContent)).toEqual(['1Lunch on Friday?answerAda · 97% sureRightWrong', '2Invoice overdueleaveYouRightWrong']);
    expect(screen.getByRole('article', { name: 'Inbox helper: done' })).toHaveTextContent('Answered 1 email.');
    // Right keeps it; Wrong, with one other outcome, says that one, and the gate learns it.
    await user.click(within(rows[1]!).getByRole('button', { name: 'Right: easy item 2' }));
    expect(rows[1]).toHaveTextContent('Kept');
    await user.click(within(rows[0]!).getByRole('button', { name: 'Wrong: easy item 1' }));
    await waitFor(() => expect(rows[0]).toHaveTextContent('1Lunch on Friday?leaveYouAda learned it'));
    expect(fake.state.bodies.at(-1)).toEqual({ outcome: 'leave', gate: 'easy', item: '1' });
  });

  it('opens Decisions, Ada gates and Tools as panels beside the chat from the top bar’s icons, not as tabs', async () => {
    on({ runs: [decided()] });
    const { user, router } = renderApp('/bots/inbox-helper');
    const panels = await screen.findByRole('toolbar', { name: 'Panels' });
    expect(within(panels).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual(['Decisions', 'Ada gates', 'Tools']);
    expect(screen.queryByRole('region', { name: 'Decisions' })).not.toBeInTheDocument();
    await user.click(within(panels).getByRole('button', { name: 'Decisions' }));
    const decisions = await screen.findByRole('region', { name: 'Decisions' });
    expect(within(within(decisions).getByRole('table', { name: 'Every decision' })).getAllByRole('row')).toHaveLength(3);
    await user.click(within(panels).getByRole('button', { name: 'Ada gates' }));
    const gates = await screen.findByRole('region', { name: 'Ada gates' });
    expect(await within(gates).findByText('precedents')).toBeInTheDocument();
    expect(gates).toHaveTextContent('Ada decided 8 · you 6');
    expect(router.state.location.search).toBe('?panel=decisions%2Cgates');
    // The chat is still there beside them.
    expect(screen.getByRole('textbox', { name: 'Give Inbox helper a task…' })).toBeInTheDocument();
    await user.click(within(decisions).getByRole('button', { name: 'Close Decisions' }));
    expect(screen.queryByRole('region', { name: 'Decisions' })).not.toBeInTheDocument();
    await user.click(within(panels).getByRole('button', { name: 'Tools' }));
    const tools = await screen.findByRole('region', { name: 'Tools' });
    expect(within(tools).getByText('bot_run_wrong')).toBeInTheDocument();
    expect(await within(tools).findByRole('heading', { name: 'Gmail · chris@example.com' })).toBeInTheDocument();
  });

  it('lands an old link to a bot’s tab: its gates as a panel, its settings as the editor', async () => {
    on();
    renderApp('/bots/inbox-helper?tab=gates');
    expect(await screen.findByRole('region', { name: 'Ada gates' })).toBeInTheDocument();
    renderApp('/bots/inbox-helper?tab=loop');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    expect(within(editor).getByLabelText('The loop as JSON')).toBeVisible();
  });

  it('lists past runs under Recents, shows one in the chat, and starts a new chat from the empty state', async () => {
    on({ runs: [decided(), waiting({ id: 'r-old', status: 'done', input: 'Yesterday', question: null, created_at: '2026-11-19T09:00:00Z' })] });
    const { user, router } = renderApp('/bots/inbox-helper');
    await user.click(await screen.findByRole('button', { name: /Recents/ }));
    const recents = screen.getByRole('dialog', { name: 'Recents' });
    await waitFor(() => expect(within(recents).getAllByRole('button').map((b) => b.textContent)).toEqual([' New chat', expect.stringMatching(/^MorningInbox helper · /), expect.stringMatching(/^YesterdayInbox helper · /)]));
    await user.click(within(recents).getByRole('button', { name: /Yesterday/ }));
    expect(router.state.location.search).toBe('?run=r-old');
    await user.click(screen.getByRole('button', { name: /Recents/ }));
    await user.click(screen.getByRole('button', { name: 'New chat' }));
    expect(await screen.findByRole('heading', { name: 'What should Inbox helper do?' })).toBeInTheDocument();
  });

  it('shows the org’s connections under CONNECTIONS, and a connection’s tools as a panel', async () => {
    const fake = on();
    const { user } = renderApp('/bots');
    await user.click(await screen.findByRole('tab', { name: 'Connections' }));
    const rail = screen.getByRole('complementary', { name: 'Bots and connections' });
    const gmail = await within(rail).findByRole('button', { name: /Gmail/ });
    expect(gmail).toHaveTextContent('Gmailon');
    expect(within(rail).getByRole('button', { name: /Slack/ })).toBeInTheDocument();
    expect(within(rail).getByRole('link', { name: '+ Add connectors' })).toHaveAttribute('href', '/connections');
    expect(within(rail).getByText('Glyphh’s key')).toBeInTheDocument();
    await user.click(within(rail).getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(fake.state.seen.some((s) => s.startsWith('sync'))).toBe(true));
    await user.click(gmail);
    const tools = await screen.findByRole('region', { name: 'Gmail · tools' });
    expect(await within(tools).findByText(/Read-only tools/)).toBeInTheDocument();
  });

  it('says when there is no such bot, and what a bot is when the org has none', async () => {
    on();
    renderApp('/bots/nope');
    expect(await screen.findByText('There is no such bot')).toBeInTheDocument();
    server.resetHandlers();
    on({ bots: [] });
    const { user } = renderApp('/bots');
    expect(await screen.findByRole('heading', { name: 'Make your first bot' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add a ready-made one' })).toHaveAttribute('href', '/marketplace/bots');
    await user.click(screen.getAllByRole('button', { name: '+ New bot' })[0]!);
    expect(await screen.findByRole('dialog', { name: 'New bot' })).toBeInTheDocument();
  });
});

describe('a project’s crew in the Bots area', () => {
  it('is a crew card in the rail, opens on "What are we making?", and runs as turns with their pull requests', async () => {
    const fake = on({ bots: [inbox(), inbox({ id: 'b-digest', slug: 'digest', name: 'Digest' })] }, {});
    const { user } = renderApp('/bots');
    const rail = await screen.findByRole('complementary', { name: 'Bots and connections' });
    const card = await within(rail).findByRole('link', { name: /Site crew/ });
    expect(card).toHaveTextContent('Site crew2 bots, taking turns');
    expect(card).toHaveAttribute('aria-current', 'page'); // a project's crew is the room first
    expect(await screen.findByRole('heading', { name: 'What are we making?', level: 1 })).toBeInTheDocument();
    // The crew strip on top: the cats with their names.
    expect(within(screen.getByLabelText('The crew')).getAllByText(/Inbox helper|Digest/).map((s) => s.textContent)).toEqual(['Inbox helper', 'Digest']);
    expect(screen.getByTitle('The project’s repo')).toHaveTextContent('sitemain');
    expect(screen.queryByRole('combobox', { name: /round/i })).not.toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: 'Give the crew a task…' }), 'Make the home page.{Enter}');
    const turn = await screen.findByRole('article', { name: 'Inbox helper: turn 1' });
    expect(screen.getByText('Make the home page.')).toBeInTheDocument();
    const merge = await within(turn).findByRole('button', { name: 'Merge' }, { timeout: 8000 });
    expect(turn).toHaveTextContent('PR #41');
    expect(within(screen.getByLabelText('Turns')).getByRole('button')).toHaveTextContent('1 Inbox helper #41 open');
    await user.click(merge);
    await waitFor(() => expect(fake.swarms.state.bodies.at(-1)).toBe('merge'));
    await waitFor(() => expect(within(screen.getByLabelText('Turns')).getAllByRole('button')[0]).toHaveTextContent('#41 merged'));
  }, 15_000);
});

describe('the bot editor, a modal as the Glyphh Bot app’s', () => {
  it('edits a bot: the card with its cat, the fields, its connectors as pills, saved together', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper');
    await user.click(await within(await screen.findByRole('banner')).findByRole('button', { name: 'Edit Inbox helper' }));
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    expect(within(editor).getByRole('button', { name: 'Shuffle the cat' })).toBeInTheDocument();
    expect(within(editor).getByRole('button', { name: 'Describe a new one' })).toBeInTheDocument();
    for (const label of ['Describe your bot and Claude makes it', 'Name', 'Tagline', 'Instructions', 'Voice', 'Model']) expect(within(editor).getByLabelText(label)).toBeInTheDocument();
    expect(within(editor).getByRole('button', { name: 'Play the voice' })).toBeDisabled(); // no samples yet
    const name = within(editor).getByLabelText('Name');
    await user.clear(name);
    await user.type(name, 'Mail helper');
    await user.selectOptions(within(editor).getByLabelText('Look: head'), 'round');
    await waitFor(() => expect(within(within(editor).getByLabelText('Model')).getAllByRole('option').length).toBeGreaterThan(3));
    await user.selectOptions(within(editor).getByLabelText('Model'), 'claude-haiku-5-5');
    await user.selectOptions(within(editor).getByLabelText('Voice'), 'bf_emma');
    // Its connectors: Gmail is on; Slack turned on gives it Slack's tools.
    const pills = within(editor).getByRole('group', { name: 'Connectors this bot can use' });
    expect(await within(pills).findByRole('button', { name: 'Gmail' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(within(pills).getByRole('button', { name: 'Slack' }));
    await waitFor(() => expect(within(pills).getByRole('button', { name: 'Slack' })).toHaveAttribute('aria-pressed', 'true'));
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Mail helper is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toMatchObject({ name: 'Mail helper', model: 'claude-haiku-5-5', voice: 'bf_emma', look: { head: 'round' }, mascot: '', permission_mode: 'ask', runs_on: null });
    expect(fake.state.bodies[1]).toEqual([
      { connection_id: 'c-gmail', tools: ['gmail-find-email'] },
      { connection_id: 'c-slack', tools: ['slack-send-message'] },
    ]);
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/mail-helper'));
    expect(screen.queryByRole('dialog', { name: 'Edit Inbox helper' })).not.toBeInTheDocument();
  });

  it('keeps what only the platform has under Advanced: permission mode, where it runs, the schedule, Ada gates, the loop and skills', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    const advanced = editor.querySelector('details')!;
    expect(advanced).not.toHaveAttribute('open');
    await user.click(within(editor).getByText('Advanced', { exact: true }));
    const where = within(editor).getByRole('combobox', { name: 'Runs on' });
    await waitFor(() => expect(within(where).getAllByRole('option')).toHaveLength(3));
    expect(within(where).getByRole('option', { name: 'Acme (offline)' })).toBeDisabled();
    await user.selectOptions(where, 'rr-studio');
    await user.selectOptions(within(editor).getByRole('combobox', { name: 'Permission mode' }), 'connection');
    // The schedule, in plain words.
    const runs = within(editor).getByRole('combobox', { name: 'Runs' });
    expect(runs).toHaveValue('off');
    expect(within(editor).getByText('It runs only when you run it.')).toBeInTheDocument();
    await user.selectOptions(runs, 'weekdays');
    await user.selectOptions(within(editor).getByRole('combobox', { name: 'Time zone' }), 'America/Chicago');
    const time = within(editor).getByLabelText('At');
    fireEvent.change(time, { target: { value: '' } }); // a cleared picker keeps its time
    fireEvent.change(time, { target: { value: '07:30' } });
    await user.type(within(editor).getByLabelText('What each run is given'), 'is:unread');
    expect(within(editor).getByText('Runs on weekdays at 7:30 (America/Chicago time).')).toBeInTheDocument();
    // Its gates in Ada, and the loop and skills.
    expect(within(editor).getByRole('list', { name: 'Ada gates' })).toHaveTextContent('easyanswerleave');
    await user.click(within(editor).getByRole('button', { name: '+ Add skill' }));
    await user.type(within(editor).getAllByLabelText('Skill name').at(-1)!, 'urgency');
    await user.type(within(editor).getAllByLabelText('What it says').at(-1)!, 'Urgent means down.');
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Inbox helper is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toMatchObject({
      permission_mode: 'connection',
      runs_on: 'rr-studio',
      schedule: { every: 'weekdays', at: '07:30', timezone: 'America/Chicago', input: 'is:unread' },
      skills: { tone: 'Write short, warm replies.', urgency: 'Urgent means down.' },
    });
    expect(fake.state.bodies).toHaveLength(1); // its connectors were not touched, so not saved again
  });

  it('lists the problems the server finds in the loop, and says when the JSON is not JSON', async () => {
    on({ problems: ['loop[2]: no such tool gmail-send', 'gates.easy: needs options'] });
    const { user } = renderApp('/bots/inbox-helper?edit=advanced');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    const spec = within(editor).getByLabelText('The loop as JSON');
    fireEvent.change(spec, { target: { value: '{ "loop": ' } });
    expect(within(editor).getByText(/Not JSON yet/)).toBeInTheDocument();
    expect(within(editor).getByRole('button', { name: 'Save bot' })).toBeDisabled();
    fireEvent.change(spec, { target: { value: '{ "loop": [{ "step": "fetch" }] }' } });
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    const problems = await within(editor).findByRole('list', { name: 'Problems' });
    expect(within(problems).getAllByRole('listitem').map((p) => p.textContent)).toEqual(['loop[2]: no such tool gmail-send', 'gates.easy: needs options']);
  });

  it('makes a new bot from a description: Claude asks, then drafts it into the fields, and Save makes it', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots');
    await user.click(await screen.findByRole('button', { name: '+ New bot' }));
    const editor = await screen.findByRole('dialog', { name: 'New bot' });
    expect(within(editor).getByRole('button', { name: 'Save bot' })).toBeDisabled();
    expect(within(editor).queryByRole('button', { name: 'Delete bot' })).not.toBeInTheDocument();
    const idea = within(editor).getByLabelText('Describe your bot and Claude makes it');
    await user.type(idea, 'post urgent support email to Slack{Enter}');
    expect(await within(editor).findByText('Which Slack channel should the urgent ones go to?')).toBeInTheDocument();
    await user.type(idea, '#support');
    await user.click(within(editor).getByRole('button', { name: 'Make it' }));
    await waitFor(() => expect(within(editor).getByLabelText('Name')).toHaveValue('Support triage'));
    expect(within(editor).getByLabelText('Tagline')).toHaveValue('Posts the urgent support email to Slack.');
    expect(fake.state.seen).toEqual(expect.arrayContaining(['draft 1', 'draft 3']));
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/support-triage'));
    expect(fake.state.bodies.at(-1)).toMatchObject({
      name: 'Support triage',
      look: { head: 'spiky' },
      spec: { touches: 'sends' },
      skills: { 'urgent-post': 'One block per ticket.' },
      connections: [
        { connection_id: 'c-gmail', tools: ['gmail-find-email'] },
        { connection_id: 'c-slack', tools: ['slack-send-message'] },
      ],
    });
    expect(await screen.findByText('Support triage is made.')).toBeInTheDocument();
  });

  it('draws a new mascot from words in its own modal, beside Shuffle, and saves it', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await user.click(within(editor).getByRole('button', { name: 'Describe a new one' }));
    const modal = await screen.findByRole('dialog', { name: 'Describe a new mascot' });
    await user.type(within(modal).getByLabelText('Describe it'), 'a sleepy cat in a chef’s hat');
    await user.click(within(modal).getByRole('button', { name: 'Draw it' }));
    await user.click(await within(modal).findByRole('button', { name: 'Use it' }));
    expect(fake.state.seen).toContain('mascot a sleepy cat in a chef’s hat');
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(fake.state.bodies.at(-1)).toMatchObject({ mascot: drawnMascot }));
  });

  it('deletes a bot once asked', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await user.click(within(editor).getByRole('button', { name: 'Delete bot' }));
    const sure = await screen.findByRole('dialog', { name: 'Delete Inbox helper?' });
    await user.click(within(sure).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(fake.state.seen).toContain('delete inbox-helper'));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots'));
    expect(await screen.findByText('Inbox helper is deleted.')).toBeInTheDocument();
  });
});

describe('a bot’s words as markdown', () => {
  it('renders tables, checklists and code with Copy, and lets a link go only to the web', () => {
    const html = md('| A | B |\n| - | - |\n| 1 | 2 |\n\n- [x] done\n\n```js\nlet a = 1\n```\n\n[ok](https://glyphh.ai) [bad](javascript:alert(1)) <img src=x onerror=alert(1)>');
    expect(html).toContain('<div class="mdtable"><table>');
    expect(html).toContain('<li class="task"><input type="checkbox" disabled checked/> done');
    expect(html).toContain('<button type="button" data-act="copy">Copy</button>');
    expect(html).toContain('<a href="https://glyphh.ai" target="_blank" rel="noopener noreferrer">ok</a>');
    expect(html).not.toContain('javascript:');
    expect(html).not.toContain('<img');
    expect(html).toContain('&lt;img src=x onerror=alert(1)&gt;');
    expect(safeHref('mailto:support@glyphh.ai')).toBe(true);
    expect(safeHref('data:text/html,x')).toBe(false);
  });
});
