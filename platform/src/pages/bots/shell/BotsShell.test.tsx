import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { decision, decisionsFake } from '@/test/botDecisions';
import { botsFake, drafted, drawnMascot, gmail, inbox, orchestrator, slack, waiting, weekdays } from '@/test/bots';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server } from '@/test/server';
import { closing, crewFake, picking, projectRun, siteCrew, turn } from '@/test/projects';
import { CLOUD_NOTE } from './bits';
import { safeHref, md } from './md';

const digest = () => inbox({ id: 'b-digest', slug: 'digest', name: 'Digest', summary: 'Sums up the day.', gate_models: [] });
const twoBots = { bots: [inbox(), digest()] };

/** The org's bots and connections, and the crew's workspaces with Recents over both (one workspace unless given). */
function on(given?: Parameters<typeof botsFake>[0], given2: Parameters<typeof crewFake>[0] = {}) {
  const fake = botsFake(given);
  const crew = crewFake({ botRuns: () => fake.state.runs, botNames: { 'inbox-helper': 'Inbox helper', digest: 'Digest' }, ...given2 });
  server.use(...fake.handlers, ...crew.handlers);
  return Object.assign(fake, { crew });
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
      easy: {
        decisions: [
          { n: 1, label: 'Lunch on Friday?', outcome: 'answer', by: 'ada', p: 0.97 },
          { n: 2, label: 'Invoice overdue', outcome: 'leave', by: 'person' },
        ],
      },
    },
    finished_at: '2026-11-20T09:01:00Z',
  });

const rail = () => screen.findByRole('complementary', { name: 'Bots and connections' });
const pills = () => within(screen.getByRole('group', { name: 'For this chat' })).getAllByRole('combobox');

describe('the Bots area, as the Glyphh Bot app', () => {
  it('has the rail (BOTS | PROGRAMS | CONNECTIONS, the crew card, the bots, New bot, the account), the chat and the status bar, with the logo as the image', async () => {
    on({ bots: [inbox(), inbox({ id: 'b-2', slug: 'quiet', name: 'Quiet', summary: 'Says little.', gate_models: [] })], runs: [waiting()] }, { projects: [] });
    renderApp('/bots');
    const side = await rail();
    expect(within(side).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Bots', 'Programs', 'Connections']);
    expect(within(side).getByRole('tab', { name: 'Bots' })).toHaveAttribute('aria-selected', 'true');
    const bots = await within(side).findByRole('navigation', { name: 'Your bots' });
    await waitFor(() => expect(within(bots).getAllByRole('link')).toHaveLength(2));
    // A round cat, the name, and what it is for. No tag beside the name but "Needs you".
    await waitFor(() => expect(within(bots).getAllByRole('link').map((a) => a.textContent)).toEqual(['Inbox helper Needs youAnswers the easy emails.', 'Quiet Says little.']));
    // The crew is the room first: it is state, not a place of its own.
    const card = within(side).getByRole('link', { name: /The Crew/ });
    expect(card).toHaveTextContent('The Crew2 bots, taking turns');
    expect(card).toHaveAttribute('aria-current', 'page');
    expect(within(side).getByRole('button', { name: '+ New bot' })).toBeInTheDocument();
    expect(await within(side).findByRole('button', { name: 'Your account' })).toHaveTextContent('chris@example.com');
    expect(within(screen.getByRole('banner')).getByRole('img', { name: 'Glyphh' })).toHaveAttribute('src', '/glyphh-logo-text-white.png');
    // The status bar says that Glyphh answers, and repeats no setting.
    const status = screen.getByRole('contentinfo');
    await waitFor(() => expect(status).toHaveTextContent('Glyphh connected'));
    expect(status.textContent).not.toMatch(/Connectors|Permissions|Runs on/);
    // The product nav stays, with one entry for bots: none for connections, approvals or the crew.
    const main = screen.getByRole('complementary', { name: 'Main' });
    expect(within(main).getByRole('link', { name: 'Bots' })).toBeInTheDocument();
    for (const gone of ['Connections', 'Approvals', 'Projects', 'Swarms']) expect(within(main).queryByRole('link', { name: gone })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).not.toBeInTheDocument();
  });

  it('floats a bot that needs you to the top of the rail', async () => {
    on({ bots: [digest(), inbox()], runs: [waiting()] }, { projects: [] });
    renderApp('/bots/digest');
    const bots = await within(await rail()).findByRole('navigation', { name: 'Your bots' });
    await waitFor(() => expect(within(bots).getAllByRole('link').map((a) => a.textContent)).toEqual(['Inbox helper Needs youAnswers the easy emails.', 'Digest Sums up the day.']));
  });

  it('opens a bot with nothing said yet on its cat, a headline, ideas and the composer with exactly three pills', async () => {
    const examples = ['What needs an answer today?', 'Answer the easy ones', 'What needs an answer today?', '  '];
    const fake = on({ bots: [inbox({ runs_on: 'rr-acme', schedule: weekdays(), examples })] });
    const { user } = renderApp('/bots/inbox-helper');
    expect(await screen.findByRole('heading', { name: 'What should Inbox helper do?', level: 1 })).toBeInTheDocument();
    // Its ideas are its own examples, each once; nothing made up here, and nothing of its schedule.
    expect(within(screen.getByRole('group', { name: 'Things to ask' })).getAllByRole('button').map((b) => b.textContent)).toEqual(['What needs an answer today?', 'Answer the easy ones']);
    expect(screen.queryByRole('button', { name: 'is:unread' })).toBeNull();
    expect(screen.getByRole('textbox', { name: 'Give Inbox helper a task…' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    // Model, Effort, Permission mode: nothing else is under the composer (no schedule, no where it runs).
    expect(pills().map((p) => p.getAttribute('aria-label'))).toEqual(['Model', 'Effort', 'Permission mode']);
    expect(within(screen.getByRole('group', { name: 'For this chat' })).queryAllByRole('button')).toHaveLength(0);
    await waitFor(() => expect(within(screen.getByRole('combobox', { name: 'Model' })).getAllByRole('option').length).toBeGreaterThan(3));
    expect(screen.getByRole('combobox', { name: 'Model' })).toHaveValue('claude-sonnet-5-5');
    expect(within(screen.getByRole('combobox', { name: 'Effort' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Low effort', 'Medium effort', 'High effort']);
    expect(screen.getByRole('combobox', { name: 'Effort' })).toHaveValue('medium');
    expect(within(screen.getByRole('combobox', { name: 'Permission mode' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Ask me first', 'Follow each app’s settings', 'Act on its own']);
    expect(screen.getByText(/Acme is offline/)).toBeInTheDocument();
    // The server's refusal is said under the composer.
    await user.type(screen.getByRole('textbox', { name: 'Give Inbox helper a task…' }), 'Clear the inbox.{Enter}');
    expect(await screen.findByText(/Acme is not linked to Glyphh right now/)).toBeInTheDocument();
    // A pill changes the bot there and then.
    await user.selectOptions(screen.getByRole('combobox', { name: 'Permission mode' }), 'auto');
    await waitFor(() => expect(fake.state.bodies[0]).toEqual({ permission_mode: 'auto' }));
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Effort' })).toBeEnabled());
    await user.selectOptions(screen.getByRole('combobox', { name: 'Effort' }), 'high');
    await waitFor(() => expect(fake.state.bodies[1]).toEqual({ effort: 'high' }));
  });

  it('offers no ideas for a bot that has none, and sends the one that is clicked', async () => {
    const fake = on({ bots: [inbox(), inbox({ id: 'b-2', slug: 'asker', name: 'Asker', examples: ['What needs an answer today?'] })] });
    const { user, router } = renderApp('/bots/inbox-helper');
    expect(await screen.findByRole('heading', { name: 'What should Inbox helper do?', level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: 'Things to ask' })).toBeNull();
    await router.navigate('/bots/asker');
    await user.click(await screen.findByRole('button', { name: 'What needs an answer today?' }));
    await waitFor(() => expect(fake.state.seen).toContain('run asker'));
    expect(fake.state.runs[0]).toMatchObject({ bot_slug: 'asker', input: 'What needs an answer today?' });
    expect(await screen.findByRole('article', { name: /^Asker:/ })).toBeInTheDocument();
  });

  it('runs a bot as a conversation: the task on the right, the bot’s turn, and what it asks answered in place', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper');
    await user.type(await screen.findByRole('textbox', { name: 'Give Inbox helper a task…' }), 'Clear the inbox.');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    const turnEl = await screen.findByRole('article', { name: /^Inbox helper:/ });
    expect(screen.getByText('Clear the inbox.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'What should Inbox helper do?' })).not.toBeInTheDocument();
    const question = await screen.findByRole('region', { name: 'Question' }, { timeout: 6000 });
    expect(screen.getByRole('article', { name: 'Inbox helper: Needs you' })).toBeInTheDocument();
    expect(question).toHaveTextContent('Inbox helper asks');
    expect(question).toHaveTextContent('Answer these emails?');
    // Its steps fold into one line.
    await user.click(within(turnEl).getByRole('button', { name: 'Ran 1 step' }));
    expect(within(turnEl).getByLabelText('Steps')).toHaveTextContent('Searched the inboxGmail');
    const send = within(question).getByRole('button', { name: 'Send answers' });
    expect(send).toBeDisabled();
    await user.click(within(question).getByRole('button', { name: 'All answer' }));
    await user.click(within(within(question).getByRole('radiogroup', { name: 'Invoice overdue' })).getByRole('radio', { name: 'leave' }));
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
    await user.click(within(rows[1]!).getByRole('button', { name: 'Right: easy item 2' }));
    expect(rows[1]).toHaveTextContent('Kept');
    await user.click(within(rows[0]!).getByRole('button', { name: 'Wrong: easy item 1' }));
    await waitFor(() => expect(rows[0]).toHaveTextContent('1Lunch on Friday?leaveYouAda learned it'));
    expect(fake.state.bodies.at(-1)).toEqual({ outcome: 'leave', gate: 'easy', item: '1' });
  });

  it('shows the server’s decisions in the turn once it has them: Right keeps one in Ada, Wrong relabels it', async () => {
    on({ runs: [decided()] });
    const fake = decisionsFake({
      decisions: [decision(), decision({ id: 'd-2', key: 'm2', label: 'Invoice overdue', outcome: 'leave', now: 'leave', who: 'you', confidence: null })],
    });
    server.use(...fake.handlers);
    const { user } = renderApp('/bots/inbox-helper');
    await waitFor(() =>
      expect(within(screen.getByRole('table', { name: 'Decisions' })).getAllByRole('row').map((r) => r.textContent)).toEqual([
        'Lunch on Friday?answerAda · 97% sureRightWrong',
        'Invoice overdueleaveYouRightWrong',
      ]),
    );
    const table = screen.getByRole('table', { name: 'Decisions' });
    const rows = within(table).getAllByRole('row');
    expect(screen.getByRole('article', { name: 'Inbox helper: done' })).toHaveTextContent('1,020 tokens · $0.0042');
    await user.click(within(rows[1]!).getByRole('button', { name: 'Right: Invoice overdue' }));
    await waitFor(() => expect(within(table).getAllByRole('row')[1]).toHaveTextContent('Kept'));
    expect(fake.state.seen).toContain('confirm d-2');
    await user.click(within(within(table).getAllByRole('row')[0]!).getByRole('button', { name: 'Wrong: Lunch on Friday?' }));
    await waitFor(() => expect(within(table).getAllByRole('row')[0]).toHaveTextContent('Lunch on Friday?leaveYouAda learned it'));
    expect(fake.state.bodies.at(-1)).toEqual({ outcome: 'leave' });
  });

  it('has only edit and Decisions on the right of the top bar, and Decisions is one panel beside the chat with its summary line', async () => {
    on({ runs: [decided()] });
    const stat = { by: { ada: 111, you: 18, default: 0 }, corrected: 4, confirmed: 9, accuracy: 0.9, days: [] };
    server.use(
      ...decisionsFake({
        decisions: [decision(), decision({ id: 'd-2', key: 'm2', label: 'Invoice overdue', outcome: 'leave', now: 'leave', who: 'you' })],
        stats: [{ gate: 'easy', decisions: 129, ask_rate: 0.18, agreement: 0.87, ...stat }],
      }).handlers,
    );
    const { user, router } = renderApp('/bots/inbox-helper');
    const bar = await screen.findByRole('banner');
    await within(bar).findByRole('button', { name: 'Edit Inbox helper' });
    // After the spacer: edit, then Decisions. No "Ada gates", no Tools; no work panels on Glyphh cloud.
    const right = Array.from(bar.querySelectorAll('.spacer ~ *'));
    expect(right.map((el) => el.getAttribute('aria-label'))).toEqual(['Edit Inbox helper', 'Decisions']);
    expect(within(bar).queryByRole('toolbar', { name: 'Work panels' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Decisions' })).not.toBeInTheDocument();
    await user.click(within(bar).getByRole('button', { name: 'Decisions' }));
    const panel = await screen.findByRole('region', { name: 'Decisions' });
    expect(router.state.location.search).toBe('?panel=decisions');
    expect(await within(panel).findByRole('list', { name: 'What it decides' })).toHaveTextContent('Easydecided 129 timesasks you 18%right 87% when it asked');
    const every = within(panel).getByRole('table', { name: 'Every decision' });
    await waitFor(() => expect(within(every).getAllByRole('row')).toHaveLength(3));
    expect(within(every).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['', 'Item', 'Outcome', 'Who', 'Confidence', 'Time↓', 'Train']);
    // The chat is still there beside it; closing it leaves only the chat.
    expect(screen.getByRole('textbox', { name: 'Give Inbox helper a task…' })).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: 'Close Decisions' }));
    expect(screen.queryByRole('region', { name: 'Decisions' })).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /gates|Tools/i })).not.toBeInTheDocument();
  });

  it('has the work panels’ icons in the top bar for a bot on a rrotor only, and no panel until one is opened', async () => {
    on({ bots: [inbox({ runs_on: 'rr-studio' })] });
    renderApp('/bots/inbox-helper');
    const bar = await screen.findByRole('banner');
    await within(bar).findByRole('button', { name: 'Edit Inbox helper' });
    // The work panels (shell/work) mount here: Files, Preview, Terminal, Editor, Diff, then the layouts.
    const tools = await within(bar).findByRole('toolbar', { name: 'Work panels' });
    expect(within(tools).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual(['Files', 'Preview', 'Terminal', 'Editor', 'Diff', 'Layouts']);
    for (const name of ['Files', 'Preview', 'Terminal', 'Editor', 'Diff']) expect(screen.queryByRole('region', { name })).not.toBeInTheDocument();
  });

  it('lands an old link to a bot’s tab: what it learned as Decisions, its settings as the editor', async () => {
    on();
    const first = renderApp('/bots/inbox-helper?tab=gates');
    expect(await screen.findByRole('region', { name: 'Decisions' })).toBeInTheDocument();
    first.unmount();
    for (const old of ['?tab=loop', '?edit=advanced', '?tab=settings']) {
      const view = renderApp(`/bots/inbox-helper${old}`);
      const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
      expect(within(editor).getByLabelText('Instructions')).toBeVisible();
      expect(editor.querySelector('details')).toBeNull();
      view.unmount();
    }
  });

  it('says when there is no such bot, and what a bot is when the org has none', async () => {
    on();
    const first = renderApp('/bots/nope');
    expect(await screen.findByText('There is no such bot')).toBeInTheDocument();
    first.unmount();
    server.resetHandlers();
    on({ bots: [] }, { projects: [] });
    const { user } = renderApp('/bots');
    expect(await screen.findByRole('heading', { name: 'Make your first bot' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Add a ready-made one' })).toHaveAttribute('href', '/marketplace/bots');
    await user.click(screen.getAllByRole('button', { name: '+ New bot' })[0]!);
    expect(await screen.findByRole('dialog', { name: 'New bot' })).toBeInTheDocument();
  });
});

describe('Recents and "Needs you" in the top bar', () => {
  const runs = () => [
    waiting({ id: 'r-wait', input: 'Check the inbox', created_at: '2026-11-21T09:00:00Z' }),
    waiting({ id: 'r-press', status: 'done', input: 'Write the press release for Friday\nwith the quotes', question: null, created_at: '2026-11-20T09:00:00Z' }),
    waiting({ id: 'r-old', status: 'done', input: 'Yesterday', question: null, created_at: '2026-11-19T09:00:00Z' }),
    waiting({ id: 'r-gone', status: 'done', input: 'Put away', question: null, created_at: '2026-11-18T09:00:00Z' }),
  ];
  const crewRuns = () => [projectRun({ id: 'pr-game', status: 'done', ended: 'done', task: 'Make a tiny browser game with a high score', created_at: '2026-11-21T08:00:00Z', turns: [turn(1, { status: 'merged' })] })];
  const open = async (user: ReturnType<typeof renderApp>['user']) => {
    await user.click(await screen.findByRole('button', { name: /^Recents/ }));
    return screen.findByRole('dialog', { name: 'Recents' });
  };
  const titles = (el: HTMLElement) => Array.from(el.querySelectorAll('.rtitle')).map((t) => t.textContent);

  it('lists every past run, a bot’s or the crew’s: pinned first, then by workspace, with a dot on one that waits', async () => {
    on({ ...twoBots, runs: runs() }, { runs: crewRuns(), pinned: ['r-press'], archived: ['r-gone'] });
    const { user, router } = renderApp('/bots');
    const panel = await open(user);
    await waitFor(() => expect(within(panel).getAllByRole('group').map((g) => g.getAttribute('aria-label'))).toEqual(['Pinned', 'Bots', 'site']));
    const [pinned, bots, site] = within(panel).getAllByRole('group');
    expect(titles(pinned!)).toEqual(['Write the press release for Friday']);
    expect(titles(bots!)).toEqual(['Check the inbox', 'Yesterday']);
    expect(titles(site!)).toEqual(['Make a tiny browser game with a high score']);
    // Who and how long ago: "Crew · 12m", "Juno · 50m".
    expect(within(site!).getByRole('button', { name: /^Make a tiny browser game/ })).toHaveTextContent(/Crew · \d+[mhd]$/);
    expect(within(pinned!).getByRole('button', { name: /^Write the press release/ })).toHaveTextContent(/Inbox helper · \d+[mhd]$/);
    expect(within(bots!).getAllByRole('img', { name: 'Needs you' })).toHaveLength(1);
    expect(within(panel).getByRole('button', { name: 'Archived 1' })).toBeInTheDocument();
    // A row opens its run in its own chat: a bot's in the bot's, the crew's in the crew's.
    await user.click(within(bots!).getByRole('button', { name: /^Yesterday/ }));
    expect(router.state.location.pathname + router.state.location.search).toBe('/bots/inbox-helper?run=r-old');
    expect(screen.queryByRole('dialog', { name: 'Recents' })).not.toBeInTheDocument();
    await user.click(await within(await open(user)).findByRole('button', { name: /^Make a tiny browser game/ }));
    expect(router.state.location.pathname + router.state.location.search).toBe('/bots?room=crew&run=pr-game');
    expect(await screen.findByRole('article', { name: 'Inbox helper: turn 1' })).toBeInTheDocument();
  });

  it('searches, pins, archives, restores and deletes from a row’s menu, and starts a new chat', async () => {
    const fake = on({ ...twoBots, runs: runs() }, { runs: crewRuns(), archived: ['r-gone'] });
    const { user } = renderApp('/bots/inbox-helper');
    const panel = await open(user);
    await waitFor(() => expect(titles(panel)).toHaveLength(4));
    await user.type(within(panel).getByRole('searchbox', { name: 'Search recents' }), 'press');
    await waitFor(() => expect(titles(panel)).toEqual(['Write the press release for Friday']));
    await user.clear(within(panel).getByRole('searchbox', { name: 'Search recents' }));
    await waitFor(() => expect(titles(panel)).toHaveLength(4));
    // "…" on a row: Pin, Archive, Delete…
    await user.click(within(panel).getByRole('button', { name: 'More: Yesterday' }));
    expect(within(screen.getByRole('menu')).getAllByRole('menuitem').map((m) => m.textContent)).toEqual(['Pin', 'Archive', 'Delete…']);
    await user.click(screen.getByRole('menuitem', { name: 'Pin' }));
    await waitFor(() => expect(within(within(panel).getByRole('group', { name: 'Pinned' })).getByRole('button', { name: /^Yesterday/ })).toBeInTheDocument());
    await user.click(within(panel).getByRole('button', { name: 'More: Yesterday' }));
    expect(screen.getByRole('menuitem', { name: 'Unpin' })).toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'Archive' }));
    await waitFor(() => expect(titles(panel)).not.toContain('Yesterday'));
    await user.click(await within(panel).findByRole('button', { name: 'Archived 2' }));
    await waitFor(() => expect(titles(panel)).toEqual(['Yesterday', 'Put away']));
    await user.click(within(panel).getByRole('button', { name: 'More: Put away' }));
    expect(within(screen.getByRole('menu')).getAllByRole('menuitem').map((m) => m.textContent)).toEqual(['Restore', 'Delete…']);
    await user.click(screen.getByRole('menuitem', { name: 'Delete…' }));
    const sure = await screen.findByRole('dialog', { name: 'Delete this chat?' });
    await user.click(within(sure).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(fake.crew.state.seen).toContain('delete r-gone'));
    await waitFor(() => expect(titles(panel)).toEqual(['Yesterday']));
    await user.click(within(panel).getByRole('button', { name: 'More: Yesterday' }));
    await user.click(screen.getByRole('menuitem', { name: 'Restore' }));
    await waitFor(() => expect(fake.crew.state.seen).toContain('unarchive r-old'));
    await user.click(within(panel).getByRole('button', { name: '‹ Recents' }));
    await user.click(within(panel).getByRole('button', { name: 'New chat' }));
    expect(await screen.findByRole('heading', { name: 'What should Inbox helper do?' })).toBeInTheDocument();
  });

  it('shows "Needs you · N" only while runs wait, and opens Recents on those alone', async () => {
    on({ ...twoBots, runs: runs() }, { runs: [projectRun({ id: 'pr-wait', created_at: '2026-11-21T08:00:00Z' })] });
    const first = renderApp('/bots');
    const chip = await screen.findByRole('button', { name: 'Needs you · 2' });
    await first.user.click(chip);
    const panel = await screen.findByRole('dialog', { name: 'Needs you' });
    await waitFor(() => expect(titles(panel)).toEqual(['Check the inbox', 'Make the home page: a hero and the three plans.']));
    expect(within(panel).queryByRole('button', { name: /Archived/ })).not.toBeInTheDocument();
    first.unmount();
    server.resetHandlers();
    on({ ...twoBots, runs: [] }, { projects: [] });
    renderApp('/bots/digest');
    await waitFor(async () => expect(within(await within(await rail()).findByRole('navigation', { name: 'Your bots' })).getAllByRole('link')).toHaveLength(2));
    expect(screen.queryByRole('button', { name: /Needs you/ })).not.toBeInTheDocument();
  });
});

describe('CONNECTIONS in the rail, the one place for them', () => {
  it('lists the org’s connections with refresh and Add connectors, and nothing else: no Claude key, no tools list', async () => {
    const fake = on();
    const { user } = renderApp('/bots');
    await user.click(await screen.findByRole('tab', { name: 'Connections' }));
    const side = await rail();
    const gmailRow = await within(side).findByRole('button', { name: /Gmail/ });
    // The server says nothing yet of how a connection stands, so the row claims nothing: no ON.
    expect(gmailRow.textContent).toBe('GGmail');
    expect(gmailRow.querySelector('.dot')).toBeNull();
    expect(within(side).getByRole('button', { name: /Slack/ })).toBeInTheDocument();
    expect(side.textContent).not.toMatch(/Claude|key/i);
    expect(within(side).queryByRole('link', { name: /Add connectors/ })).not.toBeInTheDocument(); // it opens here, it does not leave
    await user.click(within(side).getByRole('button', { name: 'refresh' }));
    await waitFor(() => expect(fake.state.seen.some((s) => s.startsWith('sync'))).toBe(true));
  });

  it('says how a connection stands only when the server does: ON, SIGN IN or FAILED', async () => {
    on({ connections: [{ ...gmail(), status: 'ok' }, { ...slack(), status: 'sign_in' }, { ...gmail(), id: 'c-hub', app: 'hubspot', app_name: 'HubSpot', status: 'failed' }, { ...gmail(), id: 'c-notion', app: 'notion', app_name: 'Notion' }] });
    renderApp('/bots?rail=connections');
    const side = await rail();
    await within(side).findByRole('button', { name: /Gmail/ });
    expect(Array.from(side.querySelectorAll('button.conn')).map((b) => [b.querySelector('b')!.textContent, b.querySelector('small')?.textContent ?? null])).toEqual([
      ['Gmail', 'On'],
      ['Slack', 'Sign in'],
      ['HubSpot', 'Failed'],
      ['Notion', null],
    ]);
  });

  it('pages Recents by the server’s cursor: Show more reads the next page', async () => {
    const many = Array.from({ length: 34 }, (_, i) => waiting({ id: `r-${i}`, status: 'done', input: `Task ${i}`, question: null, created_at: new Date(Date.parse('2026-11-20T09:00:00Z') - i * 60_000).toISOString() }));
    const fake = on({ runs: many }, { projects: [] });
    const { user } = renderApp('/bots/inbox-helper');
    await user.click(await screen.findByRole('button', { name: /^Recents/ }));
    const panel = await screen.findByRole('dialog', { name: 'Recents' });
    await waitFor(() => expect(panel.querySelectorAll('.rtitle')).toHaveLength(30));
    await user.click(within(panel).getByRole('button', { name: 'Show more' }));
    await waitFor(() => expect(panel.querySelectorAll('.rtitle')).toHaveLength(34));
    expect(fake.crew.state.seen.some((s) => s.includes('cursor=30'))).toBe(true);
    expect(within(panel).queryByRole('button', { name: 'Show more' })).not.toBeInTheDocument();
  });

  it('opens one modal for a connection: its account, its tools’ permissions, Disconnect', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots?rail=connections');
    await user.click(await within(await rail()).findByRole('button', { name: /Gmail/ }));
    const modal = await screen.findByRole('dialog', { name: 'Gmail' });
    expect(router.state.location.search).toBe('?rail=connections&conn=c-gmail');
    expect(modal).toHaveTextContent('Accountchris@example.com');
    const writes = await within(modal).findByRole('region', { name: 'Write/delete tools' });
    expect(within(modal).getByRole('region', { name: 'Read-only tools' })).toBeInTheDocument();
    await user.click(within(writes).getByRole('button', { name: /Write\/delete tools/ }));
    await user.click(within(writes).getByRole('switch', { name: 'Send email' }));
    await waitFor(() => expect(fake.state.bodies.at(-1)).toEqual({ 'gmail-send-email': 'deny' }));
    // No panel of tools opens anywhere else.
    expect(document.querySelector('.gb .panel')).toBeNull();
    await user.click(within(modal).getByRole('button', { name: 'Disconnect' }));
    await user.click(within(modal).getByRole('button', { name: 'Disconnect Gmail' }));
    await waitFor(() => expect(fake.state.seen.some((s) => s.includes('c-gmail') && /remove|delete|disconnect/.test(s))).toBe(true));
    expect(await screen.findByText('Gmail is disconnected.')).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Gmail' })).not.toBeInTheDocument();
  });

  it('opens the catalog from "+ Add connectors": each app a card with a "+"', async () => {
    on();
    const { user } = renderApp('/bots?rail=connections');
    await user.click(await within(await rail()).findByRole('button', { name: '+ Add connectors' }));
    const catalog = await screen.findByRole('dialog', { name: 'Add connectors' });
    const apps = within(catalog).getByRole('list', { name: 'Apps' });
    await waitFor(() => expect(within(apps).getAllByRole('listitem').length).toBeGreaterThan(2));
    for (const card of within(apps).getAllByRole('listitem')) expect(within(card).getByRole('button')).toHaveTextContent('+');
    expect(within(apps).getByRole('button', { name: 'Add another Gmail account' })).toBeInTheDocument();
    await user.type(within(catalog).getByRole('searchbox', { name: 'Search apps' }), 'zzz');
    expect(await within(catalog).findByText('No app matches “zzz”.')).toBeInTheDocument();
  });
});

describe('the crew: state, not a place', () => {
  it('ticks the cats on the crew card to say who is in it', async () => {
    const fake = on(twoBots);
    const { user } = renderApp('/bots/inbox-helper');
    const cats = await within(await rail()).findByRole('group', { name: 'In the crew' });
    await waitFor(() => expect(within(cats).getAllByRole('button').map((b) => [b.getAttribute('aria-label'), b.getAttribute('aria-pressed')])).toEqual([['Inbox helper', 'true'], ['Digest', 'true']]));
    await user.click(within(cats).getByRole('button', { name: 'Digest' }));
    await waitFor(() => expect(fake.crew.state.bodies[0]).toEqual({ repo: 'acme/site', branch: 'main', members: ['b-inbox'] }));
    await waitFor(() => expect(within(cats).getByRole('button', { name: 'Digest' })).toHaveAttribute('aria-pressed', 'false'));
    expect(within(await rail()).getByRole('link', { name: /The Crew/ })).toHaveTextContent('The Crew1 bot, taking turns');
    // The last one in stays.
    expect(within(cats).getByRole('button', { name: 'Inbox helper' })).toBeDisabled();
  });

  it('keeps how the crew works in one "Crew settings" modal, opened from the card’s edit or the top bar’s', async () => {
    const fake = on(twoBots, { projects: [siteCrew({ runs_on: null })] });
    const { user } = renderApp('/bots');
    await user.click(await within(await rail()).findByRole('button', { name: 'Crew settings' }));
    const modal = await screen.findByRole('dialog', { name: 'Crew settings' });
    expect(within(within(modal).getByRole('group', { name: 'Bots in the crew' })).getAllByRole('button').map((b) => [b.textContent, b.getAttribute('aria-pressed')])).toEqual([['Inbox helper', 'true'], ['Digest', 'true']]);
    // Where it runs, with what Glyphh cloud cannot do.
    const where = within(modal).getByRole('combobox', { name: 'Where the crew runs' });
    await waitFor(() => expect(within(where).getAllByRole('option').map((o) => o.textContent)).toEqual(['Glyphh cloud', 'Studio Mac', 'Acme (offline)']));
    expect(within(modal).getByText(CLOUD_NOTE)).toBeInTheDocument();
    expect(CLOUD_NOTE).toBe(
      "Glyphh cloud has fewer tools than a rrotor: bots can read and change files and open pull requests, but can't run commands, tests or a browser. Choose a rrotor for those.",
    );
    await user.selectOptions(where, 'rr-studio');
    expect(within(modal).queryByText(CLOUD_NOTE)).not.toBeInTheDocument();
    // How turns are taken; no speaking order, no rounds.
    expect(within(within(modal).getByRole('radiogroup', { name: 'How turns are taken' })).getAllByRole('radio').map((r) => r.querySelector('b')!.textContent)).toEqual(['Wait your turn', 'The orchestrator picks who goes next']);
    expect(modal.textContent).not.toMatch(/round|order/i);
    await user.click(within(modal).getByRole('radio', { name: /The orchestrator picks who goes next/ }));
    // Who orchestrates is not a setting: the org's orchestrator always does. No picker of a bot or a model.
    expect(within(modal).queryByRole('combobox', { name: 'Who picks' })).toBeNull();
    expect(within(modal).getAllByRole('combobox').map((c) => c.getAttribute('aria-label'))).toEqual(['Where the crew runs']);
    expect(modal.textContent).not.toMatch(/Who picks|Claude/);
    expect(within(within(modal).getByRole('radiogroup', { name: 'How pull requests are reviewed' })).getAllByRole('radio').map((r) => r.querySelector('b')!.textContent)).toEqual(['Each turn', 'At the end']);
    await user.click(within(modal).getByRole('radio', { name: /At the end/ }));
    await user.click(within(modal).getByRole('switch', { name: 'Narrate when watched' }));
    const caps = within(modal).getByRole('group', { name: 'Safety caps' });
    await user.clear(within(caps).getByLabelText(/Most turns/));
    await user.type(within(caps).getByLabelText(/Most turns/), '12');
    await user.type(within(caps).getByLabelText(/Most spend/), '5');
    await user.click(within(modal).getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(fake.crew.state.bodies[0]).toEqual({
        repo: 'acme/site',
        branch: 'main',
        members: ['b-inbox', 'b-digest'],
        runs_on: 'rr-studio',
        turn_mode: 'orchestrator',
        review: 'end',
        narrate: true,
        max_turns: 12,
        max_spend_cents: 500,
      }),
    );
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Crew settings' })).not.toBeInTheDocument());
    expect(within(await rail()).getByRole('link', { name: /The Crew/ })).toHaveTextContent('2 bots, led by the orchestrator');
    // The top bar's edit opens the same modal.
    await user.click(within(screen.getByRole('banner')).getByRole('button', { name: 'Edit the crew' }));
    expect(await screen.findByRole('dialog', { name: 'Crew settings' })).toBeInTheDocument();
  });

  it('opens on "What are we making?", gives the crew a task with the same three pills, and runs as turns with their pull requests', async () => {
    const fake = on(twoBots);
    const { user } = renderApp('/bots');
    expect(await screen.findByRole('heading', { name: 'What are we making?', level: 1 })).toBeInTheDocument();
    expect(within(screen.getByLabelText('The crew')).getAllByText(/Inbox helper|Digest/).map((s) => s.textContent)).toEqual(['Inbox helper', 'Digest']);
    expect(pills().map((p) => p.getAttribute('aria-label'))).toEqual(['Model', 'Effort', 'Permission mode']);
    expect(within(screen.getByRole('group', { name: 'For this chat' })).queryAllByRole('button')).toHaveLength(0);
    expect(within(screen.getByRole('combobox', { name: 'Permission mode' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Ask me at each pull request', 'One review at the end']);
    await waitFor(() => expect(within(screen.getByRole('combobox', { name: 'Model' })).getAllByRole('option').length).toBeGreaterThan(3));
    expect(screen.getByRole('combobox', { name: 'Model' })).toHaveValue('');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Model' }), 'claude-haiku-5-5');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Effort' }), 'high');
    await user.type(screen.getByRole('textbox', { name: 'Give the crew a task…' }), 'Make the home page.{Enter}');
    const turnEl = await screen.findByRole('article', { name: 'Inbox helper: turn 1' });
    expect(fake.crew.state.bodies[0]).toEqual({ task: 'Make the home page.', model: 'claude-haiku-5-5', effort: 'high' });
    const merge = await within(turnEl).findByRole('button', { name: 'Merge' }, { timeout: 8000 });
    expect(turnEl).toHaveTextContent('PR #41');
    expect(within(screen.getByLabelText('Turns')).getByRole('button')).toHaveTextContent('1 Inbox helper #41 open');
    await user.click(merge);
    await waitFor(() => expect(fake.crew.state.bodies.at(-1)).toBe('merge'));
    await waitFor(() => expect(within(screen.getByLabelText('Turns')).getAllByRole('button')[0]).toHaveTextContent('#41 merged'));
    // The permission-mode pill is when its pull requests wait for you.
    await user.selectOptions(screen.getByRole('combobox', { name: 'Permission mode' }), 'end');
    await waitFor(() => expect(fake.crew.state.bodies.at(-1)).toEqual({ repo: 'acme/site', branch: 'main', members: ['b-inbox', 'b-digest'], review: 'end' }));
  }, 15_000);

  it('shows who the orchestrator chose and why, and that it is choosing the next', async () => {
    on(twoBots, {
      projects: [siteCrew({ turn_mode: 'orchestrator' })],
      runs: [projectRun({ status: 'running', turn_mode: 'orchestrator', turns: [turn(1, { status: 'merged', picked_by: 'orchestrator', why: 'The home page comes first.' }), picking(2)] })],
    });
    renderApp('/bots');
    expect(await screen.findByText('Orchestrator chose Inbox helper · The home page comes first.')).toBeInTheDocument();
    expect(screen.getByText('Choosing who goes next…')).toHaveAttribute('role', 'status');
    expect(within(screen.getByLabelText('Turns')).getAllByRole('button').map((b) => b.textContent)).toEqual(['1 Inbox helper #41 merged']);
  });

  it('with review at the end, shows the run’s one pull request of it all and merges it', async () => {
    const fake = on(twoBots, {
      projects: [siteCrew({ review: 'end' })],
      runs: [projectRun({ review: 'end', work_branch: 'run-pr-1-k3x9', pr_url: 'https://github.com/acme/site/pull/50', number: 50, turns: [turn(1, { status: 'merged' }), turn(2, { status: 'merged' })] })],
    });
    const { user } = renderApp('/bots');
    const whole = await screen.findByRole('region', { name: 'The run’s pull request' });
    expect(whole).toHaveTextContent('PR #50');
    expect(within(screen.getByRole('article', { name: 'Inbox helper: turn 1' })).queryByRole('button', { name: 'Merge' })).not.toBeInTheDocument();
    await user.click(within(whole).getByRole('button', { name: 'Merge' }));
    expect(await screen.findByText("The crew said it's done")).toBeInTheDocument();
    expect(fake.crew.state.bodies).toEqual(['merge']);
  });

  it('shows the orchestrator’s closing turn, a turn with no changes and why the run ended, and starts a run with no task', async () => {
    const fake = on(twoBots, {
      projects: [siteCrew({ runs_on: null, turn_mode: 'orchestrator' })],
      runs: [
        projectRun({
          task: '',
          status: 'done',
          ended: 'orchestrator',
          runs_on: null,
          turn_mode: 'orchestrator',
          turns: [
            turn(1, { status: 'merged', picked_by: 'orchestrator' }),
            turn(2, { status: 'unchanged', picked_by: 'orchestrator', said: '', pr_url: null, number: null, files: [], done: false }),
            closing(3, 'Everything asked for is built.'),
          ],
        }),
      ],
    });
    const { user } = renderApp('/bots');
    expect(await screen.findByText('(from the instructions)')).toBeInTheDocument();
    expect(screen.getByRole('article', { name: 'Digest: turn 2' })).toHaveTextContent('passed · no changes');
    expect(screen.getByRole('article', { name: 'Orchestrator: turn 3' })).toHaveTextContent('Everything asked for is built.');
    expect(screen.getByText("The orchestrator said it's done")).toBeInTheDocument();
    // Nothing typed: Send starts a run from the repository's own instructions.
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await waitFor(() => expect(fake.crew.state.bodies).toEqual([{ task: '', model: null, effort: null }]));
  });
});

describe('the workspace pill: the repository and branch the crew works in', () => {
  it('with no workspace yet says so, offers Connect GitHub (never a token), and takes no task', async () => {
    const fake = on(twoBots, { projects: [], github: null });
    const { user } = renderApp('/bots');
    const pill = await screen.findByRole('button', { name: 'Workspace' });
    expect(pill).toHaveTextContent('Choose a workspace');
    expect(await screen.findByText(/Choose a workspace in the top bar first/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    await user.click(pill);
    const menu = await screen.findByRole('dialog', { name: 'Workspace' });
    const connect = await within(menu).findByRole('button', { name: 'Connect GitHub' });
    expect(menu.textContent).not.toMatch(/token/i);
    expect(within(menu).queryByRole('textbox', { name: 'Find a repository' })).not.toBeInTheDocument();
    const opened = vi.spyOn(window, 'open').mockReturnValue(null);
    await user.click(connect);
    await waitFor(() => expect(fake.crew.state.seen).toContain('install link'));
    opened.mockRestore();
  });

  it('picks a repository from the GitHub App’s, and the crew as it is ticked goes with it', async () => {
    const fake = on(twoBots, { projects: [] });
    const { user } = renderApp('/bots');
    // Ticked before there is a workspace: kept, and sent with the first one picked.
    const cats = await within(await rail()).findByRole('group', { name: 'In the crew' });
    await user.click(await within(cats).findByRole('button', { name: 'Digest' }));
    expect(within(cats).getByRole('button', { name: 'Digest' })).toHaveAttribute('aria-pressed', 'false');
    await user.click(screen.getByRole('button', { name: 'Workspace' }));
    const menu = await screen.findByRole('dialog', { name: 'Workspace' });
    expect(await within(menu).findByText('acme')).toBeInTheDocument();
    expect(within(menu).getByRole('link', { name: 'Change repositories' })).toHaveAttribute('href', 'https://github.com/settings/installations/4242');
    const list = within(menu).getByRole('listbox', { name: 'Repositories' });
    expect(within(list).getAllByRole('option').map((o) => o.textContent)).toEqual(['acme/sitepublic', 'acme/docsprivate', 'acme/apiprivate']);
    await user.type(within(menu).getByRole('textbox', { name: 'Find a repository' }), 'doc');
    expect(within(list).getAllByRole('option').map((o) => o.textContent)).toEqual(['acme/docsprivate']);
    await user.click(within(list).getByRole('option', { name: /acme\/docs/ }));
    await waitFor(() => expect(fake.crew.state.bodies[0]).toMatchObject({ repo: 'acme/docs', branch: 'trunk', members: ['b-inbox'], turn_mode: 'wait', review: 'each_turn' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' })).toHaveTextContent('docstrunk'));
    expect(screen.queryByRole('dialog', { name: 'Workspace' })).not.toBeInTheDocument();
    expect(screen.queryByText(/Choose a workspace in the top bar first/)).not.toBeInTheDocument();
  });

  it('lists the workspaces used before, changes the branch, and takes a typed owner/name the list does not have', async () => {
    const fake = on(twoBots, { projects: [siteCrew(), siteCrew({ id: 'p-docs', slug: 'acme-docs-trunk', name: 'acme/docs', repo_url: 'https://github.com/acme/docs', base_branch: 'trunk', members: [{ id: 'b-inbox', slug: 'inbox-helper', name: 'Inbox helper' }], updated_at: '2026-11-20T10:00:00Z' })] });
    const { user } = renderApp('/bots');
    const pill = await screen.findByRole('button', { name: 'Workspace' });
    await waitFor(() => expect(pill).toHaveTextContent('sitemain'));
    await user.click(pill);
    let menu = await screen.findByRole('dialog', { name: 'Workspace' });
    expect(within(menu).getAllByRole('button', { name: /acme\/(site|docs)/ }).filter((b) => b.getAttribute('role') !== 'option').map((b) => b.textContent)).toEqual([' acme/site main', ' acme/docs trunk']);
    // Another workspace: its own crew comes with it, and nothing is written.
    await user.click(within(menu).getAllByRole('button', { name: /acme\/docs/ })[0]!);
    await waitFor(() => expect(pill).toHaveTextContent('docstrunk'));
    expect(within(await rail()).getByRole('link', { name: /The Crew/ })).toHaveTextContent('The Crew1 bot, taking turns');
    expect(fake.crew.state.bodies).toEqual([]);
    // The branch field, with the repository's branches to choose from.
    await user.click(pill);
    menu = await screen.findByRole('dialog', { name: 'Workspace' });
    const branch = within(menu).getByRole('combobox', { name: 'Branch' });
    expect(branch).toHaveValue('trunk');
    await user.clear(branch);
    await user.type(branch, 'dev{Enter}');
    await waitFor(() => expect(fake.crew.state.bodies[0]).toMatchObject({ repo: 'acme/docs', branch: 'dev', members: ['b-inbox'] }));
    await waitFor(() => expect(pill).toHaveTextContent('docsdev'));
    // An organisation's repository is not in the list: its owner/name is typed.
    await user.click(pill);
    menu = await screen.findByRole('dialog', { name: 'Workspace' });
    await user.type(within(menu).getByRole('textbox', { name: 'Find a repository' }), 'acme-org/billing');
    await user.click(within(menu).getByRole('option', { name: 'Use acme-org/billing' }));
    await waitFor(() => expect(fake.crew.state.bodies[1]).toMatchObject({ repo: 'acme-org/billing' }));
    await waitFor(() => expect(pill).toHaveTextContent('billingmain'));
  });

  it('says the server’s refusal with Connect GitHub when the App is not on the repository', async () => {
    on(twoBots, { projects: [] });
    const { user } = renderApp('/bots');
    await user.click(await screen.findByRole('button', { name: 'Workspace' }));
    const menu = await screen.findByRole('dialog', { name: 'Workspace' });
    await user.type(await within(menu).findByRole('textbox', { name: 'Find a repository' }), 'other/thing{Enter}');
    const alert = await within(menu).findByRole('alert');
    expect(alert).toHaveTextContent('Glyphh’s GitHub App is not installed on other/thing.');
    expect(within(alert).getByRole('link', { name: 'Connect GitHub' })).toHaveAttribute('href', 'https://api.glyphh.test/v1/github/install?link=signed');
  });
});

describe('the pages that are gone land in the Bots area', () => {
  it.each([
    ['/connections', '/bots', '?rail=connections'],
    ['/connections/gmail?tab=tools', '/bots', '?rail=connections'],
    ['/connections?tab=catalog', '/bots', '?rail=connections&add=1'],
    ['/approvals', '/bots', ''],
    ['/projects', '/bots', ''],
    ['/projects/new', '/bots', ''],
    ['/swarms', '/bots', ''],
    ['/settings/github-token', '/bots', ''],
  ])('%s', async (from, path, search) => {
    on(twoBots);
    const { router } = renderApp(from);
    await waitFor(() => expect(router.state.location.pathname).toBe(path));
    expect(router.state.location.search).toBe(search);
    expect(await screen.findByRole('complementary', { name: 'Bots and connections' })).toBeInTheDocument();
  });

  it('opens an old link to one crew on its workspace', async () => {
    on(twoBots, { projects: [siteCrew(), siteCrew({ id: 'p-docs', slug: 'acme-docs-trunk', name: 'acme/docs', repo_url: 'https://github.com/acme/docs', base_branch: 'trunk', updated_at: '2026-11-20T10:00:00Z' })] });
    const { router } = renderApp('/projects/acme-docs-trunk?run=pr-9');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Workspace' })).toHaveTextContent('docstrunk'));
    expect(router.state.location.pathname + router.state.location.search).toBe('/bots?run=pr-9&room=crew');
  });

  it('has no GitHub token page in Settings', async () => {
    on();
    renderApp('/settings/general');
    const nav = await screen.findByRole('complementary', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'Claude key' })).toBeInTheDocument();
    expect(within(nav).queryByRole('link', { name: /GitHub/ })).not.toBeInTheDocument();
  });
});

describe('the bot editor, a modal as the Glyphh Bot app’s', () => {
  it('edits a bot in plain fields, in the order of its settings, with nothing of how it works inside', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper');
    await user.click(await within(await screen.findByRole('banner')).findByRole('button', { name: 'Edit Inbox helper' }));
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    // The card: the cat, Shuffle (one of the cats there are) and Describe a new one. Nothing else about the look.
    expect(within(editor).getByRole('button', { name: 'Shuffle the cat' })).toBeInTheDocument();
    expect(within(editor).getByRole('button', { name: 'Describe a new one' })).toBeInTheDocument();
    expect(within(editor).queryByLabelText(/^Look/)).not.toBeInTheDocument();
    for (const label of ['Tell Claude what to change', 'Name', 'What it is for', 'Instructions', 'When it runs', 'What it does when it runs on its own', 'Where it runs', 'Voice', 'Model', 'Effort']) expect(within(editor).getByLabelText(label)).toBeVisible();
    // Its standing task sits under When it runs, before Where it runs.
    const order = [within(editor).getByRole('combobox', { name: 'When it runs' }), within(editor).getByLabelText('What it does when it runs on its own'), within(editor).getByRole('combobox', { name: 'Where it runs' })];
    expect(order[0]!.compareDocumentPosition(order[1]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(order[1]!.compareDocumentPosition(order[2]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(editor).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Access', 'When it runs', 'Where it runs', 'Voice, model and effort']);
    // Access: its apps, its folders, and when it must ask, in that order.
    const access = ['Apps it can use', 'Folders it can use', 'Before it acts'].map((t) => within(editor).getByText(t));
    expect(access[0]!.compareDocumentPosition(access[1]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(access[1]!.compareDocumentPosition(access[2]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Nothing is folded away, and none of the words of its insides are said.
    expect(editor.querySelector('details')).toBeNull();
    expect(within(editor).queryByText(/Advanced/)).not.toBeInTheDocument();
    expect(editor.querySelector('textarea.mono')).toBeNull();
    expect(editor.textContent).not.toMatch(/\bloop|\bgates?\b|\bspec\b|\bskills?\b|JSON|bot\.json/i);
    const name = within(editor).getByLabelText('Name');
    await user.clear(name);
    await user.type(name, 'Mail helper');
    await user.clear(within(editor).getByLabelText('What it is for'));
    await user.type(within(editor).getByLabelText('What it is for'), 'Answers the post.');
    await user.type(within(editor).getByLabelText('Instructions'), ' Be brief.');
    await waitFor(() => expect(within(within(editor).getByLabelText('Model')).getAllByRole('option').length).toBeGreaterThan(3));
    await user.selectOptions(within(editor).getByLabelText('Model'), 'claude-haiku-5-5');
    expect(within(within(editor).getByLabelText('Effort')).getAllByRole('option').map((o) => o.textContent)).toEqual(['Low', 'Medium', 'High']);
    await user.selectOptions(within(editor).getByLabelText('Effort'), 'high');
    await user.selectOptions(within(editor).getByLabelText('Voice'), 'bf_emma');
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Mail helper is saved.')).toBeInTheDocument();
    // How it works inside goes back exactly as it came.
    expect(fake.state.bodies[0]).toEqual({
      name: 'Mail helper',
      summary: 'Answers the post.',
      instructions: 'Read new emails and answer the easy ones. Be brief.',
      task: '',
      look: inbox().look,
      mascot: '',
      voice: 'bf_emma',
      model: 'claude-haiku-5-5',
      permission_mode: 'ask',
      effort: 'high',
      schedule: expect.objectContaining({ every: 'off' }),
      runs_on: null,
      folders: [],
      spec: inbox().spec,
      skills: inbox().skills,
    });
    expect(fake.state.bodies).toHaveLength(1); // its apps were not touched, so not saved again
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/mail-helper'));
  });

  it('shuffles among the cats there are', async () => {
    const fake = on({ bots: [inbox({ mascot: drawnMascot })] });
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await user.click(within(editor).getByRole('button', { name: 'Shuffle the cat' }));
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(fake.state.bodies[0]).toMatchObject({ mascot: '', look: { head: expect.any(String), tail: expect.any(String), pose: expect.any(String) } }));
  });

  it('gives a bot its apps as on/off pills; which tools an app allows is the connection’s own, in the rail', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    const apps = within(editor).getByRole('group', { name: 'Apps it can use' });
    await waitFor(() => expect(within(apps).getAllByRole('button').map((b) => [b.lastChild!.textContent, b.getAttribute('aria-pressed')])).toEqual([['Gmail', 'true'], ['Slack', 'false'], ['+ Connect an app', null]]));
    expect(within(editor).queryByRole('button', { name: /Choose tools/ })).not.toBeInTheDocument();
    await user.click(within(apps).getByRole('button', { name: 'Slack' }));
    await waitFor(() => expect(within(apps).getByRole('button', { name: 'Slack' })).toHaveAttribute('aria-pressed', 'true'));
    await user.click(within(apps).getByRole('button', { name: 'Gmail' }));
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Inbox helper is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[1]).toEqual([{ connection_id: 'c-slack', tools: ['slack-send-message'] }]);
  });

  it('connects another app from the editor in the rail’s catalog, the one place apps are connected', async () => {
    on();
    const { user, router } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await user.click(await within(editor).findByRole('button', { name: '+ Connect an app' }));
    expect(await screen.findByRole('dialog', { name: 'Add connectors' })).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search).toContain('rail=connections'));
    // The editor is still there under it, with what was typed.
    expect(screen.getByRole('dialog', { name: 'Edit Inbox helper' })).toBeInTheDocument();
  });

  it('gives a bot on a rrotor the folders that machine shares, to read or to change, and none on Glyphh cloud', async () => {
    const fake = on({ bots: [inbox({ runs_on: 'rr-studio', folders: [{ path: '/Users/chris/Desktop', access: 'write' }] })] });
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    const where = within(editor).getByRole('combobox', { name: 'Where it runs' });
    await waitFor(() => expect(within(where).getAllByRole('option')).toHaveLength(3));
    expect(within(where).getByRole('option', { name: 'Acme (offline)' })).toBeDisabled();
    const folders = within(editor).getByRole('list', { name: 'Folders it can use' });
    expect(within(folders).getByRole('combobox', { name: 'Access to /Users/chris/Desktop' })).toHaveValue('write');
    // Add a folder: read from the machine itself, with a ticket for it, opened one by one.
    await user.click(within(editor).getByRole('button', { name: '+ Add a folder' }));
    const picker = await screen.findByRole('dialog', { name: 'Folders on Studio Mac' });
    expect(await within(picker).findByRole('button', { name: 'Add Desktop' })).toBeDisabled(); // it has it already
    await user.click(within(picker).getByRole('button', { name: 'Open Documents' }));
    await user.click(await within(picker).findByRole('button', { name: 'Add Invoices' }));
    expect(fake.state.seen).toEqual(expect.arrayContaining(['ticket rr-studio', 'folders ', 'folders /Users/chris/Documents']));
    expect(within(folders).getByRole('combobox', { name: 'Access to /Users/chris/Documents/Invoices' })).toHaveValue('read');
    await user.selectOptions(within(folders).getByRole('combobox', { name: 'Access to /Users/chris/Documents/Invoices' }), 'Read and change');
    await user.click(within(folders).getByRole('button', { name: 'Remove /Users/chris/Desktop' }));
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(fake.state.bodies[0]).toMatchObject({ runs_on: 'rr-studio', folders: [{ path: '/Users/chris/Documents/Invoices', access: 'write' }] }));
    // On Glyphh cloud there are none to give: one line says so.
    const again = renderApp('/bots/inbox-helper?edit=1');
    const cloud = (await screen.findAllByRole('dialog', { name: 'Edit Inbox helper' })).at(-1)!;
    await waitFor(() => expect(within(within(cloud).getByRole('combobox', { name: 'Where it runs' })).getAllByRole('option')).toHaveLength(3));
    await again.user.selectOptions(within(cloud).getByRole('combobox', { name: 'Where it runs' }), '');
    expect(within(cloud).getByText('Glyphh cloud has no folders. To give it files, choose a rrotor under Where it runs.')).toBeInTheDocument();
    expect(within(cloud).queryByRole('button', { name: '+ Add a folder' })).not.toBeInTheDocument();
    await again.user.click(within(cloud).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(fake.state.bodies.at(-1)).toMatchObject({ runs_on: null, folders: [] }));
  });

  it('lets a folder’s path be typed when the machine cannot show its folders', async () => {
    const fake = on({ bots: [inbox({ runs_on: 'rr-acme' })] });
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await waitFor(() => expect(within(within(editor).getByRole('combobox', { name: 'Where it runs' })).getAllByRole('option')).toHaveLength(3));
    server.use(http.get('https://rrotor.acme.test/v1/folders', () => HttpResponse.error()));
    await user.click(within(editor).getByRole('button', { name: '+ Add a folder' }));
    const picker = await screen.findByRole('dialog', { name: 'Folders on Acme' });
    expect(await within(picker).findByText(/That machine did not answer/)).toBeInTheDocument();
    await user.type(within(picker).getByLabelText('Type the folder’s path instead'), '/srv/invoices{Enter}');
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(fake.state.bodies[0]).toMatchObject({ folders: [{ path: '/srv/invoices', access: 'read' }] }));
  });

  it('says when it must ask as a choice of three, and when it runs in plain words', async () => {
    const fake = on();
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    const asks = within(editor).getByRole('radiogroup', { name: 'Before it acts' });
    expect(within(asks).getAllByRole('radio').map((r) => r.textContent)).toEqual([
      'Ask me firstIt waits for your yes before every action.',
      'Follow each app’s settingsIt asks only where an app is set to ask.',
      'Act on its ownIt does not ask. What you blocked still never happens.',
    ]);
    expect(within(asks).getByRole('radio', { name: /Ask me first/ })).toBeChecked();
    await user.click(within(asks).getByRole('radio', { name: /Follow each app’s settings/ }));
    const runs = within(editor).getByRole('combobox', { name: 'When it runs' });
    expect(runs).toHaveValue('off');
    expect(within(editor).getByText('It runs only when you run it.')).toBeInTheDocument();
    await user.selectOptions(runs, 'weekdays');
    await user.selectOptions(within(editor).getByRole('combobox', { name: 'Time zone' }), 'America/Chicago');
    const time = within(editor).getByLabelText('At');
    fireEvent.change(time, { target: { value: '' } }); // a cleared picker keeps its time
    fireEvent.change(time, { target: { value: '07:30' } });
    // What it does on its own is its standing task, in one place: no second field for what a schedule gives it.
    expect(within(editor).queryByLabelText('What it looks at each time')).toBeNull();
    const task = within(editor).getByLabelText('What it does when it runs on its own');
    expect(task).toHaveAttribute('maxlength', '4000');
    await user.type(task, ' Go through my unread email and say what needs an answer. ');
    expect(within(editor).getByText('Runs on weekdays at 7:30 (America/Chicago time).')).toBeInTheDocument();
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Inbox helper is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toMatchObject({
      permission_mode: 'connection',
      effort: 'medium',
      task: 'Go through my unread email and say what needs an answer.',
      schedule: { every: 'weekdays', at: '07:30', timezone: 'America/Chicago' },
      spec: inbox().spec,
      skills: { tone: 'Write short, warm replies.' },
    });
  });

  it('changes an existing bot from plain words: Claude is sent the bot as it stands, and what it decides comes back with it', async () => {
    const changed = drafted({ name: 'Inbox helper', summary: 'Answers the easy emails.', instructions: 'Read new emails, answer the easy ones and flag the angry ones.', look: inbox().look, spec: { ...inbox().spec, gates: { easy: { options: ['answer', 'leave'] }, mood: { outcomes: ['angry', 'calm'] } } }, skills: { tone: 'Write short, warm replies.', mood: 'Angry means capitals.' }, apps: [{ app: 'gmail', tools: ['gmail-find-email'] }] });
    const fake = on({ maker: [{ reply: 'It now flags the angry ones too.', draft: changed, problems: [], missing_apps: [] }] });
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    expect(within(editor).queryByLabelText('Describe your bot and Claude makes it')).not.toBeInTheDocument();
    await waitFor(() => expect(within(within(editor).getByLabelText('Model')).getAllByRole('option').length).toBeGreaterThan(3));
    await waitFor(() => expect(within(within(editor).getByRole('group', { name: 'Apps it can use' })).getAllByRole('button')).toHaveLength(3));
    await user.type(within(editor).getByLabelText('Tell Claude what to change'), 'also flag the angry ones');
    await user.click(within(editor).getByRole('button', { name: 'Change it' }));
    expect(await within(editor).findByText('It now flags the angry ones too.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toEqual({
      messages: [{ role: 'user', content: 'also flag the angry ones' }],
      draft: {
        name: 'Inbox helper',
        summary: 'Answers the easy emails.',
        look: inbox().look,
        mascot: '',
        instructions: 'Read new emails and answer the easy ones.',
        model: 'claude-sonnet-5-5',
        spec: inbox().spec,
        skills: inbox().skills,
        apps: [{ app: 'gmail', tools: ['gmail-find-email'] }],
        connections: [{ connection_id: 'c-gmail', tools: ['gmail-find-email'] }],
      },
    });
    expect(within(editor).getByLabelText('Instructions')).toHaveValue('Read new emails, answer the easy ones and flag the angry ones.');
    expect(within(editor).getByText(/Decides: easy \(answer, leave\), mood \(angry, calm\) · learned from your answers/)).toBeInTheDocument();
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Inbox helper is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[1]).toMatchObject({ spec: changed.spec, skills: changed.skills });
  });

  it('says what a bot decides in one quiet line that opens the Decisions panel; no line when it decides nothing', async () => {
    on({ bots: [inbox(), inbox({ id: 'b-2', slug: 'quiet', name: 'Quiet', spec: { touches: 'read_only' }, gate_models: [] })] });
    const { user, router } = renderApp('/bots/quiet?edit=1');
    const quiet = await screen.findByRole('dialog', { name: 'Edit Quiet' });
    expect(within(quiet).queryByText(/Decides:/)).not.toBeInTheDocument();
    await user.click(within(quiet).getByRole('button', { name: 'Close' }));
    await router.navigate('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    expect(within(editor).getByText(/Decides: easy \(answer, leave\) · learned from your answers/)).toBeInTheDocument();
    await user.click(within(editor).getByRole('button', { name: 'See its decisions' }));
    expect(await screen.findByRole('region', { name: 'Decisions' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Edit Inbox helper' })).not.toBeInTheDocument();
  });

  it('says the problems the server finds on save as plain sentences under Save', async () => {
    on({ problems: ['limits.turns: no such tool gmail-send', 'gates.easy: needs options', 'The schedule needs a time'] });
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    const problems = await within(editor).findByRole('list', { name: 'Problems' });
    expect(within(problems).getAllByRole('listitem').map((p) => p.textContent)).toEqual(['No such tool gmail-send.', 'Needs options.', 'The schedule needs a time.']);
    expect(within(editor).getByRole('alert')).toHaveTextContent('It was not saved.');
  });

  it('makes a new bot from a description: Claude asks, then drafts it into the fields, and Save makes it', async () => {
    const fake = on();
    const { user, router } = renderApp('/bots/inbox-helper');
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
    expect(fake.state.bodies[0]).toMatchObject({ draft: null }); // a new bot starts from nothing
    expect(within(editor).getByText(/Decides: urgency · learned from your answers/)).toBeInTheDocument();
    expect(within(editor).queryByRole('button', { name: 'See its decisions' })).not.toBeInTheDocument();
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/support-triage'));
    expect(fake.state.bodies.at(-1)).toMatchObject({
      name: 'Support triage',
      effort: 'medium',
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

describe('the orchestrator: always there, first, and where /bots opens', () => {
  const withIt = { bots: [inbox(), digest(), orchestrator()] };

  it('is pinned first in the rail with its tag, above a bot that needs you; no other bot has a tag', async () => {
    on({ ...withIt, runs: [waiting()] }, { projects: [] });
    renderApp('/bots/digest');
    const bots = await within(await rail()).findByRole('navigation', { name: 'Your bots' });
    await waitFor(() =>
      expect(within(bots).getAllByRole('link').map((a) => a.textContent)).toEqual([
        'Orchestrator OrchestratorLeads the crew and asks the right bot.',
        'Inbox helper Needs youAnswers the easy emails.',
        'Digest Sums up the day.',
      ]),
    );
    expect(Array.from(bots.querySelectorAll('i')).map((i) => [i.className, i.textContent])).toEqual([['role', 'Orchestrator'], ['needs', 'Needs you']]);
  });

  it('wears both tags when a run of its own waits on you', async () => {
    on({ ...withIt, runs: [waiting({ bot_slug: 'orchestrator' })] }, { projects: [] });
    renderApp('/bots/digest');
    const bots = await within(await rail()).findByRole('navigation', { name: 'Your bots' });
    await waitFor(() => expect(within(bots).getAllByRole('link')[0]).toHaveTextContent('Orchestrator Orchestrator Needs youLeads the crew and asks the right bot.'));
  });

  it('is the chat /bots opens on with nothing chosen, keeping what the address asked for; the crew is one click away', async () => {
    on(withIt);
    const { user, router } = renderApp('/bots?rail=connections');
    await waitFor(() => expect(router.state.location.pathname + router.state.location.search).toBe('/bots/orchestrator?rail=connections'));
    await router.navigate('/bots');
    expect(await screen.findByRole('heading', { name: 'What should Orchestrator do?', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/bots/orchestrator');
    expect(screen.queryByRole('heading', { name: 'Make your first bot' })).toBeNull();
    // Its ideas are its own examples.
    expect(within(screen.getByRole('group', { name: 'Things to ask' })).getAllByRole('button').map((b) => b.textContent)).toEqual(['What can my bots do?', 'Ask the right bot to sort my inbox']);
    const side = await rail();
    expect(within(side).getByRole('link', { name: /^Orchestrator/ })).toHaveAttribute('aria-current', 'page');
    const card = within(side).getByRole('link', { name: /The Crew/ });
    expect(card).not.toHaveAttribute('aria-current');
    await user.click(card);
    expect(await screen.findByRole('heading', { name: 'What are we making?', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe('/bots?room=crew');
    expect(within(side).getByRole('link', { name: /The Crew/ })).toHaveAttribute('aria-current', 'page');
  });

  it('keeps the crew’s room the crew’s: a crew’s run, and a new chat from it', async () => {
    on(withIt, { runs: [projectRun()] });
    const { user, router } = renderApp('/bots?run=pr-1');
    expect(await screen.findByRole('article', { name: 'Inbox helper: turn 1' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/bots');
    await user.click(screen.getByRole('button', { name: /^Recents/ }));
    await user.click(within(await screen.findByRole('dialog', { name: 'Recents' })).getByRole('button', { name: 'New chat' }));
    expect(await screen.findByRole('heading', { name: 'What are we making?', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname + router.state.location.search).toBe('/bots?room=crew');
  });

  it('is edited in the same modal as any bot, without Delete bot', async () => {
    const fake = on(withIt);
    const { user } = renderApp('/bots/orchestrator?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Orchestrator' });
    for (const label of ['Tell Claude what to change', 'Name', 'What it is for', 'Instructions', 'When it runs', 'What it does when it runs on its own', 'Where it runs', 'Voice', 'Model', 'Effort']) expect(within(editor).getByLabelText(label)).toBeVisible();
    expect(within(editor).queryByRole('button', { name: 'Delete bot' })).toBeNull();
    await user.type(within(editor).getByLabelText('Instructions'), ' Be brief.');
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    expect(await screen.findByText('Orchestrator is saved.')).toBeInTheDocument();
    expect(fake.state.bodies[0]).toMatchObject({ instructions: 'Work out which bot should do a task, and ask it. Be brief.' });
    // Its role is not part of what is sent, and the server keeps it whatever is asked.
    expect(fake.state.bodies[0]).not.toHaveProperty('role');
    expect(fake.state.bots.find((b) => b.slug === 'orchestrator')).toMatchObject({ role: 'orchestrator' });
    // Any other bot keeps Delete bot.
    const other = renderApp('/bots/digest?edit=1');
    expect(await within(await within(other.container).findByRole('dialog', { name: 'Edit Digest' })).findByRole('button', { name: 'Delete bot' })).toBeInTheDocument();
  });
});

describe('where a bot may run', () => {
  const where = async () => {
    const editor = await screen.findByRole('dialog', { name: /^Edit / });
    const select = within(editor).getByRole('combobox', { name: 'Where it runs' });
    await waitFor(() => expect(within(select).getAllByRole('option').length).toBeGreaterThan(1));
    return { editor, select, options: within(select).getAllByRole('option').map((o) => o.textContent) };
  };

  it('offers Glyphh cloud and the rrotors to a bot that can run on both, and to one whose server does not say', async () => {
    on({ bots: [inbox({ can_run_on: ['cloud', 'rrotor'] }), digest()] });
    const first = renderApp('/bots/inbox-helper?edit=1');
    expect((await where()).options).toEqual(['Glyphh cloud', 'Studio Mac', 'Acme (offline)']);
    first.unmount();
    renderApp('/bots/digest?edit=1');
    expect((await where()).options).toEqual(['Glyphh cloud', 'Studio Mac', 'Acme (offline)']);
  });

  it('does not offer Glyphh cloud to a bot that needs a rrotor, and says so', async () => {
    const fake = on({ bots: [inbox({ can_run_on: ['rrotor'], runs_on: 'rr-studio' })] });
    const { user } = renderApp('/bots/inbox-helper?edit=1');
    const { editor, select, options } = await where();
    expect(options).toEqual(['Studio Mac', 'Acme (offline)']);
    expect(select).toHaveValue('rr-studio');
    expect(within(editor).getByText(/It needs a rrotor: it cannot run on Glyphh cloud\./)).toBeInTheDocument();
    await user.click(within(editor).getByRole('button', { name: 'Save bot' }));
    await waitFor(() => expect(fake.state.bodies[0]).toMatchObject({ runs_on: 'rr-studio' }));
  });

  it('asks a bot that needs a rrotor and has none yet to choose one', async () => {
    on({ bots: [inbox({ can_run_on: ['rrotor'], runs_on: null })] });
    renderApp('/bots/inbox-helper?edit=1');
    const { select, options } = await where();
    expect(options).toEqual(['Choose a rrotor', 'Studio Mac', 'Acme (offline)']);
    expect(within(select).getByRole('option', { name: 'Choose a rrotor' })).toBeDisabled();
  });

  it('offers only Glyphh cloud to a bot that runs there alone', async () => {
    on({ bots: [inbox({ can_run_on: ['cloud'] })] });
    renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await waitFor(() => expect(within(within(editor).getByLabelText('Model')).getAllByRole('option').length).toBeGreaterThan(3));
    expect(within(within(editor).getByRole('combobox', { name: 'Where it runs' })).getAllByRole('option').map((o) => o.textContent)).toEqual(['Glyphh cloud']);
  });
});

describe('no word of how a bot works inside is on the screen', () => {
  // The words a business never needs: a person's own bot or repository can be called anything, the screen never is.
  // "Orchestrator" is a product word and is allowed.
  const ENGINE = /\b(gates?|loop|spec|skills?|plugins?|json|swarms?|projects?)\b/i;
  const shell = () => document.querySelector('.gb')!;
  const said = () => {
    // Everything a person can read or hear: the text, and what buttons, fields and pictures are called.
    const named = Array.from(shell().querySelectorAll('[aria-label], [title], [placeholder], [alt]')).flatMap((el) => ['aria-label', 'title', 'placeholder', 'alt'].map((a) => el.getAttribute(a) ?? ''));
    return [shell().textContent ?? '', ...named].join('\n');
  };
  const clean = () => {
    const found = said().match(new RegExp(ENGINE.source, 'gi'));
    expect(found ?? []).toEqual([]);
  };
  const stat = { by: { ada: 111, you: 18, default: 0 }, corrected: 4, confirmed: 9, accuracy: 0.9, days: [] };
  const all = () => {
    // A turn that used things (one of them failed), a question that is an approval, a bot with examples and a task.
    const used = [
      { tool: 'gmail-find-email', title: 'Searched the inbox', app: 'Gmail', ok: true },
      { tool: 'decide', title: 'Decided easy for 2 items', app: '', ok: true },
      { tool: 'gmail-send-email', title: 'Sent an email', app: 'Gmail', ok: false },
    ];
    const asks = { question: 'Send this reply?', options: ['Yes', 'No'], batch: null, answer_with: null, approval: true, tool: 'gmail-send-email', detail: 'Send an email in Gmail to pat@example.com.' };
    const helper = inbox({ runs_on: 'rr-studio', can_run_on: ['rrotor'], task: 'Answer the easy emails.', examples: ['What needs an answer today?'], folders: [{ path: '/Users/chris/Desktop', access: 'read' }] });
    const fake = on({ bots: [helper, digest(), orchestrator()], runs: [{ ...decided(), steps: used }, waiting({ question: asks })] }, { runs: [projectRun()] });
    server.use(
      ...decisionsFake({
        decisions: [decision(), decision({ id: 'd-2', key: 'm2', label: 'Invoice overdue', outcome: 'leave', now: 'leave', who: 'you' })],
        stats: [{ gate: 'easy', decisions: 129, ask_rate: 0.18, agreement: 0.87, ...stat }],
      }).handlers,
    );
    return fake;
  };

  it('with a bot selected, and its Decisions open', async () => {
    all();
    const { user } = renderApp('/bots/inbox-helper');
    await screen.findByRole('article', { name: 'Inbox helper: done' });
    expect(await screen.findByRole('region', { name: 'Question' })).toHaveTextContent('Send an email in Gmail to pat@example.com.');
    await waitFor(() => expect(within(screen.getByRole('combobox', { name: 'Model' })).getAllByRole('option').length).toBeGreaterThan(3));
    await within(await rail()).findByRole('link', { name: /^Orchestrator/ });
    // What it used, unfolded: plain words, never a tool's own name.
    await user.click(screen.getByRole('button', { name: 'Ran 3 steps' }));
    expect(screen.getByRole('list', { name: 'Steps' })).toHaveTextContent('Sent an emailGmaildid not work');
    expect(said()).not.toMatch(/gmail-find-email|gmail-send-email/);
    clean();
    await user.click(screen.getByRole('button', { name: 'Decisions' }));
    const panel = await screen.findByRole('region', { name: 'Decisions' });
    await within(panel).findByRole('list', { name: 'What it decides' });
    await waitFor(() => expect(within(within(panel).getByRole('table', { name: 'Every decision' })).getAllByRole('row')).toHaveLength(3));
    await user.click(within(panel).getByRole('button', { name: 'Invoice overdue' }));
    await screen.findByRole('list', { name: 'Cases it matched' }).catch(() => screen.findByText(/None yet: nothing it has seen/));
    clean();
    // Recents and the workspace's menu, open.
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: /^Recents/ }));
    await waitFor(() => expect(document.querySelectorAll('.rtitle').length).toBeGreaterThan(1));
    clean();
    await user.keyboard('{Escape}');
    await user.click(screen.getByRole('button', { name: 'Workspace' }));
    await within(await screen.findByRole('dialog', { name: 'Workspace' })).findByRole('listbox', { name: 'Repositories' });
    clean();
  });

  it('with the crew selected, and its settings open', async () => {
    all();
    const { user } = renderApp('/bots?room=crew');
    await screen.findByRole('article', { name: 'Inbox helper: turn 1' });
    await within(await rail()).findByRole('group', { name: 'In the crew' });
    clean();
    await user.click(within(await rail()).getByRole('button', { name: 'Crew settings' }));
    await screen.findByRole('dialog', { name: 'Crew settings' });
    clean();
  });

  it('with the editor open, for a bot on a rrotor and for a new one', async () => {
    all();
    const { user, router } = renderApp('/bots/inbox-helper?edit=1');
    const editor = await screen.findByRole('dialog', { name: 'Edit Inbox helper' });
    await waitFor(() => expect(within(within(editor).getByRole('group', { name: 'Apps it can use' })).getAllByRole('button')).toHaveLength(3));
    await within(editor).findByRole('combobox', { name: 'Access to /Users/chris/Desktop' });
    clean();
    await user.click(within(editor).getByRole('button', { name: '+ Add a folder' }));
    await within(await screen.findByRole('dialog', { name: 'Folders on Studio Mac' })).findByRole('button', { name: 'Open Documents' });
    clean();
    await router.navigate('/bots/inbox-helper?new=1');
    await screen.findByRole('dialog', { name: 'New bot' });
    clean();
    await router.navigate('/bots/orchestrator?edit=1');
    await screen.findByRole('dialog', { name: 'Edit Orchestrator' });
    clean();
    await router.navigate('/bots/orchestrator');
    await screen.findByRole('group', { name: 'Things to ask' });
    clean();
  });

  it('on the connections tab, with a connection’s modal and the catalog open', async () => {
    all();
    const { router } = renderApp('/bots?rail=connections&conn=c-gmail');
    const modal = await screen.findByRole('dialog', { name: 'Gmail' });
    await within(modal).findByRole('region', { name: 'Read-only tools' });
    clean();
    await router.navigate('/bots?rail=connections&add=1');
    const catalog = await screen.findByRole('dialog', { name: 'Add connectors' });
    await waitFor(() => expect(within(within(catalog).getByRole('list', { name: 'Apps' })).getAllByRole('listitem').length).toBeGreaterThan(2));
    clean();
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
