import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { following, type Program, type Step } from '@/api/programs';
import { botsFake, inbox, weekdays } from '@/test/bots';
import { crewFake } from '@/test/projects';
import { digestFlow, program, programsFake } from '@/test/programs';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

// The file view's editor stands in as its plain text box: Monaco does not load here.
vi.mock('@/pages/bots/shell/work/monaco', () => ({ loadMonaco: () => Promise.reject(new Error('no monaco here')) }));

const digestBot = () => inbox({ id: 'b-digest', slug: 'digest', name: 'Digest', summary: 'Sums up the day.', gate_models: [] });

function on(programs?: Parameters<typeof programsFake>[0]) {
  const bots = botsFake({ bots: [inbox(), digestBot()] });
  const crew = crewFake({ projects: [], botRuns: () => bots.state.runs, botNames: { 'inbox-helper': 'Inbox helper', digest: 'Digest' } });
  const fake = programsFake(programs);
  server.use(...bots.handlers, ...crew.handlers, ...fake.handlers);
  return fake;
}

beforeAll(() => {
  following.every = 25;
});
afterAll(() => {
  following.every = 1500;
});

const rail = () => screen.findByRole('complementary', { name: 'Bots and connections' });
const card = (name: RegExp | string) => screen.findByRole('group', { name });
const saves = (fake: ReturnType<typeof programsFake>) => fake.state.bodies.filter((b) => b.method === 'PATCH').map((b) => b.body as { flow?: Step[]; source?: string });
/** Words never on a Programs screen: the engine's, and a tool's key where it has a name. */
const ENGINE = /\b(JSON|loop|gates?|skills?|plugin|billing)\b|github-search-issues-and-pull-requests|slack-send-message/i;

describe('the Programs tab under Bots', () => {
  it('sits between Bots and Connections, lists the org’s programs and says what a program is', async () => {
    on({ programs: [program({ last_run: { id: 'pr-0', status: 'done', created_at: new Date().toISOString() }, schedule_summary: 'Weekdays at 9:00' }), program({ slug: 'tidy', name: 'Tidy files', summary: 'Files what lands.', bot: 'digest', can_run_on: ['rrotor'], runs_on: 'rr-studio' })] });
    const { user } = renderApp('/bots/inbox-helper');
    const side = await rail();
    expect(within(side).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Bots', 'Programs', 'Connections']);
    await user.click(within(side).getByRole('tab', { name: 'Programs' }));
    const list = await within(side).findByRole('navigation', { name: 'Your programs' });
    await waitFor(() => expect(within(list).getAllByRole('button')).toHaveLength(2));
    const [digest, tidy] = within(list).getAllByRole('button');
    expect(digest).toHaveTextContent('PR review digest');
    expect(digest).toHaveTextContent('The pull requests waiting on my review, posted to Slack.');
    expect(digest).toHaveTextContent('Inbox helper');
    expect(within(digest!).getByRole('group', { name: 'Where it can run' })).toHaveTextContent('Cloudrrotor');
    expect(digest).toHaveTextContent('Weekdays at 9:00');
    expect(digest).toHaveTextContent('Done · just now');
    expect(tidy).toHaveTextContent('Digest');
    expect(within(tidy!).getByRole('group', { name: 'Where it can run' })).toHaveTextContent(/^rrotor$/);
    expect(tidy).toHaveTextContent('When you run itNever run');
    // The centre says what a program is, and offers to make one; the bot's chat is not there.
    expect(await screen.findByRole('heading', { name: 'Programs' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Inbox helper' })).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Programs' })).getByRole('button', { name: '+ New program' })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(ENGINE);
  });

  it('makes a new program with its bot and opens its empty canvas', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots?rail=programs');
    await user.click(await within(await rail()).findByRole('button', { name: '+ New program' }));
    const dialog = await screen.findByRole('dialog', { name: 'New program' });
    await user.type(within(dialog).getByRole('textbox', { name: 'Name' }), 'Morning check');
    await user.type(within(dialog).getByRole('textbox', { name: 'What it is for' }), 'Looks at the day.');
    await user.click(within(dialog).getByRole('radio', { name: 'Digest' }));
    await user.click(within(dialog).getByRole('button', { name: 'Make program' }));
    await waitFor(() => expect(router.state.location.search).toContain('program=morning-check'));
    expect(fake.state.bodies[0]).toEqual({ method: 'POST', path: '/programs', body: { name: 'Morning check', summary: 'Looks at the day.', bot: 'digest', flow: [] } });
    expect(await screen.findByRole('heading', { name: 'Morning check' })).toBeInTheDocument();
    expect(await screen.findByText('No steps yet')).toBeInTheDocument();
  });

  it('draws each step as a card of its kind, with the bot that does it and its action by name, and the arrows between', async () => {
    on();
    renderApp('/bots?rail=programs&program=pr-digest');
    expect(await screen.findByRole('heading', { name: 'PR review digest' })).toBeInTheDocument();
    const find = await card('App: Search issues and pull requests');
    expect(find).toHaveTextContent('Starts here');
    expect(find).toHaveTextContent('Inbox helper');
    expect(find).toHaveTextContent('GitHub');
    const pick = await card(/^Bot: Which of these need my review today\?/);
    expect(pick).toHaveTextContent('Digest');
    const ok = await card('Ask: Post the digest?');
    expect(ok).toHaveTextContent('yes · no');
    expect(await card('App: Post to Slack')).toHaveTextContent('Slack');
    // The arrows are drawn once the cards are measured, which jsdom never does: flow.test.ts has them.
    // The palette: the five kinds of step, in words.
    const palette = screen.getByRole('toolbar', { name: 'Add a step' });
    const kinds = ['Use an app', 'Ask a bot', 'Ask a person', 'Choose the way', 'Run code'];
    expect(within(palette).getAllByRole('button').map((b, i) => b.textContent?.endsWith(kinds[i]!))).toEqual(kinds.map(() => true));
    // With no step picked, the right rail is the program's own settings.
    expect(screen.getByRole('complementary', { name: 'Program settings' })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(ENGINE);
  });

  it('adds a step from the palette, edits it on the right, connects it, and saves the steps', async () => {
    const fake = on();
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    await card('Ask: Post the digest?');
    expect(screen.getByRole('button', { name: 'Saved' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Ask a person/ }));
    const step = await screen.findByRole('complementary', { name: 'Step' });
    await user.type(within(step).getByRole('textbox', { name: /^The question/ }), 'Also tell the team?');
    await user.click(within(step).getByRole('button', { name: 'Remove the answer no' }));
    await user.selectOptions(within(step).getByRole('combobox', { name: 'Then, for yes' }), 'Post to Slack');
    expect(await card('Ask: Also tell the team?')).toHaveTextContent('yes');
    // The last step now goes on to the new one.
    await user.click(within(step).getByRole('button', { name: 'Close the step' }));
    fireEvent.click(await card('App: Post to Slack'));
    const post = await screen.findByRole('complementary', { name: 'Step' });
    await user.selectOptions(within(post).getByRole('combobox', { name: 'Then' }), 'Also tell the team?');

    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(saves(fake)).toHaveLength(1));
    const flow = saves(fake)[0]!.flow!;
    expect(flow.map((s) => s.id)).toEqual(['find', 'pick', 'ok', 'post', 'ask']);
    expect(flow[4]).toMatchObject({ kind: 'ask', question: 'Also tell the team?', options: ['yes'], next: { yes: 'post' } });
    expect(flow[4]!.at).toHaveLength(2);
    expect(flow[3]!.next).toBe('ask');
    // Everything it did not touch is as it was, places and all.
    expect(flow.slice(0, 3)).toEqual(digestFlow().slice(0, 3));
    // The canvas is read back from the server's answer.
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toBeDisabled());
    expect(await card('Ask: Also tell the team?')).toBeInTheDocument();
  });

  it('picks the bot a step includes by its cat, renames a step everywhere, and deletes one with its arrows', async () => {
    const fake = on();
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    fireEvent.click(await card(/^Bot: Which of these/));
    const step = await screen.findByRole('complementary', { name: 'Step' });
    const who = within(step).getByRole('radiogroup', { name: 'The bot it asks' });
    expect(within(who).getByRole('radio', { name: 'Digest' })).toHaveAttribute('aria-checked', 'true');
    await user.click(within(who).getByRole('radio', { name: 'Inbox helper (the program’s)' }));
    const id = within(step).getByRole('textbox', { name: 'Short name' });
    await user.clear(id);
    await user.type(id, 'choose{Enter}');
    await waitFor(() => expect(within(screen.getByRole('complementary', { name: 'Step' })).getByText('Later steps use its result as {choose}.')).toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Close the step' }));
    fireEvent.click(await card('Ask: Post the digest?'));
    await user.click(within(await screen.findByRole('complementary', { name: 'Step' })).getByRole('button', { name: 'Delete step' }));
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Ask: Post the digest?' })).not.toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(saves(fake)).toHaveLength(1));
    const flow = saves(fake)[0]!.flow!;
    expect(flow.map((s) => s.id)).toEqual(['find', 'choose', 'post']);
    expect(flow[0]!.next).toBe('choose');
    expect(flow[1]).not.toHaveProperty('bot');
    expect(flow[1]).not.toHaveProperty('next');
    expect(flow[2]!.input).toEqual({ channel: '@me', text: '{choose}' });
  });

  it('finds an action for a step among the org’s apps, and adds it to the bot when it has not got it', async () => {
    const fake = on({ programs: [program({ flow: [{ id: 'use', kind: 'tool', tool: '', input: {}, at: [0, 0] }] })] });
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    fireEvent.click(await card('App: Pick an action'));
    const step = await screen.findByRole('complementary', { name: 'Step' });
    expect(within(step).getByText('None yet. Find one below.')).toBeInTheDocument();
    await user.type(within(step).getByRole('textbox', { name: 'Find an action' }), 'email');
    await user.click(await within(step).findByRole('button', { name: 'Use Find email (Gmail)' }));
    await waitFor(() => expect(fake.state.added).toEqual([{ bot: 'inbox-helper', connection_id: 'c-gmail', tool: 'gmail-find-email' }]));
    await waitFor(() => expect(within(step).getByText('Find email')).toBeInTheDocument());
    await user.click(within(step).getByRole('button', { name: '+ Add a value' }));
    await user.type(within(step).getByRole('textbox', { name: 'Name 1' }), 'q');
    await user.type(within(step).getByRole('textbox', { name: 'Value 1' }), 'is:unread');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(saves(fake)).toHaveLength(1));
    expect(saves(fake)[0]!.flow![0]).toMatchObject({ id: 'use', kind: 'tool', tool: 'gmail-find-email', title: 'Find email', input: { q: 'is:unread' } });
    expect(document.body.textContent).not.toMatch(/gmail-find-email/);
  });

  it('shows the server’s problems plainly, and a refusal’s too', async () => {
    on({ programs: [program({ problems: ['Step ok goes to gone, which is not there'] })] });
    renderApp('/bots?rail=programs&program=pr-digest');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('It cannot run yet.');
    expect(within(alert).getByRole('list', { name: 'Problems' })).toHaveTextContent('Step ok goes to gone, which is not there.');
    expect(screen.getByRole('button', { name: '▶ Run' })).toBeDisabled();
  });

  it('shows the file and saves it: the canvas is read back from the server', async () => {
    const fake = on();
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    await card('Ask: Post the digest?');
    await user.click(screen.getByRole('tab', { name: 'Code' }));
    const file = await screen.findByRole('textbox', { name: 'program.py' });
    expect((file as HTMLTextAreaElement).value).toContain('"""PR review digest');
    fireEvent.change(file, { target: { value: (file as HTMLTextAreaElement).value.replace('Post the digest?', 'Post it now?') } });
    await user.click(screen.getByRole('tab', { name: 'Canvas' }));
    expect(screen.getByRole('textbox', { name: 'program.py' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(saves(fake)).toHaveLength(1));
    expect(saves(fake)[0]!.source).toContain('Post it now?');
    expect(saves(fake)[0]).not.toHaveProperty('flow');
    await user.click(screen.getByRole('tab', { name: 'Canvas' }));
    expect(await card('Ask: Post it now?')).toBeInTheDocument();
  });

  it('runs it with what it is given, lights the step it is at, logs who did what, and takes the answer', async () => {
    const fake = on();
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    await card('Ask: Post the digest?');
    await user.click(screen.getByRole('button', { name: '▶ Run' }));
    await user.type(screen.getByRole('textbox', { name: 'What to give it' }), 'today');
    await user.click(screen.getByRole('button', { name: 'Run now' }));
    expect(fake.state.bodies.find((b) => b.path === '/programs/pr-digest/runs')?.body).toEqual({ input: 'today' });
    const runBox = await screen.findByRole('region', { name: 'The run' });
    const asks = await within(runBox).findByRole('group', { name: 'It asks you' });
    expect(asks).toHaveTextContent('Post the digest?');
    expect(within(runBox).getByRole('status')).toHaveTextContent('Needs you');
    // The step it is at, lit on the canvas.
    await waitFor(() => expect(screen.getByRole('group', { name: 'Ask: Post the digest?' })).toHaveAttribute('aria-current', 'step'));
    expect(screen.getByRole('group', { name: 'App: Search issues and pull requests' })).toHaveTextContent('✓ Done');
    // Who started it, and which bot did each step.
    const log = within(runBox).getByRole('list', { name: 'What happened' });
    await waitFor(() => expect(within(log).getAllByRole('listitem').length).toBeGreaterThanOrEqual(4));
    const lines = within(log).getAllByRole('listitem').map((li) => li.textContent);
    expect(lines[0]).toMatch(/Started by chris@example.com/);
    expect(lines[1]).toMatch(/Inbox helper.*find/);
    expect(lines[2]).toMatch(/Digest.*pick/);
    expect(lines[3]).toMatch(/Asked: Post the digest\?/);

    await user.click(within(asks).getByRole('button', { name: 'yes' }));
    expect(fake.state.bodies.find((b) => b.path.endsWith('/answer'))?.body).toEqual({ answer: 'yes' });
    await waitFor(() => expect(within(runBox).getByRole('status')).toHaveTextContent('Done'));
    await waitFor(() => expect(within(log).getAllByRole('listitem').map((li) => li.textContent).join('\n')).toMatch(/answered “yes”[\s\S]*Finished/));
    expect(within(runBox).queryByRole('button', { name: 'Cancel run' })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(ENGINE);
  });

  it('cancels a run and answers in words when there are no options', async () => {
    const flow: Step[] = [{ id: 'why', kind: 'ask', question: 'Why?', options: [], next: {}, at: [0, 0] }];
    const fake = on({ programs: [program({ flow })] });
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    await user.click(await screen.findByRole('button', { name: '▶ Run' }));
    await user.click(screen.getByRole('button', { name: 'Run now' }));
    const runBox = await screen.findByRole('region', { name: 'The run' });
    const asks = await within(runBox).findByRole('group', { name: 'It asks you' });
    expect(within(asks).getByRole('button', { name: 'Answer' })).toBeDisabled();
    await user.click(within(runBox).getByRole('button', { name: 'Cancel run' }));
    await waitFor(() => expect(within(runBox).getByRole('status')).toHaveTextContent('Cancelled'));
    expect(fake.state.runs[0]!.status).toBe('cancelled');
  });

  it('sets when it runs with the bots’ own schedule choices', async () => {
    const fake = on();
    const { user } = renderApp('/bots?rail=programs&program=pr-digest');
    const settings = await screen.findByRole('complementary', { name: 'Program settings' });
    expect(within(settings).getByRole('status')).toHaveTextContent('It runs only when you run it.');
    await user.selectOptions(within(settings).getByRole('combobox', { name: 'When it runs' }), 'Weekdays');
    await user.selectOptions(within(settings).getByRole('combobox', { name: 'Time zone' }), 'America/Chicago');
    expect(within(settings).getByRole('status')).toHaveTextContent('Runs on weekdays at 9:00 (America/Chicago time).');
    await user.click(within(settings).getByRole('button', { name: 'Save settings' }));
    await waitFor(() => expect(saves(fake)).toHaveLength(1));
    expect((saves(fake)[0] as Partial<Program>).schedule).toEqual(weekdays({ input: '' }));
    expect(saves(fake)[0]).not.toHaveProperty('flow');
    expect(await screen.findByText(/Weekdays at 9:00/, { selector: '.pchip' })).toBeInTheDocument();
  });
});
