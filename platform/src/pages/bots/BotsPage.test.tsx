import { act, screen, waitFor, within } from '@testing-library/react';
import { botsFake, digest, inbox, triage } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';

function on(given?: Parameters<typeof botsFake>[0]) {
  const fake = botsFake(given);
  server.use(...fake.handlers);
  return fake;
}

afterEach(() => vi.restoreAllMocks());

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
    expect(card).toHaveTextContent('1 tool · 1 gate · 1 skill');
    expect(card).toHaveTextContent('Failed');
    expect(card.querySelector('svg.cat-svg')).not.toBeNull();
    expect(card).toHaveAttribute('href', '/bots/inbox-helper');
  });

  it('searches your bots on the server', async () => {
    const fake = on({ bots: [inbox(), inbox({ id: 'b-2', slug: 'lead-sorter', name: 'Lead sorter', summary: 'Sorts leads.' })] });
    const { user } = renderApp('/bots');
    const list = await screen.findByRole('list', { name: 'Your bots' });
    expect(within(list).getAllByRole('link')).toHaveLength(2);
    await user.type(screen.getByLabelText('Search'), 'lead');
    await waitFor(() => expect(within(screen.getByRole('list', { name: 'Your bots' })).getAllByRole('link').map((l) => l.getAttribute('href'))).toEqual(['/bots/lead-sorter']));
    expect(fake.state.seen).toContain('search lead');
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'zzz');
    expect(await screen.findByText('Nothing matches')).toBeInTheDocument();
    expect(screen.queryByText('No bots yet')).not.toBeInTheDocument();
  });

  it('browses the Marketplace’s bots, searched, and marks one already added', async () => {
    on({ bots: [inbox({ name: 'Daily digest', slug: 'daily-digest' })], templates: [triage(), digest()] });
    const { user, router } = renderApp('/bots');
    await user.click(await screen.findByRole('tab', { name: 'Browse' }));
    expect(router.state.location.search).toBe('?tab=browse');
    const list = await screen.findByRole('list', { name: 'Bots to add' });
    const card = await within(list).findByRole('link', { name: 'Support triage' });
    expect(card).toHaveTextContent('Needs Gmail, Notion · 1 gate');
    expect(card).toHaveAttribute('href', '/marketplace/bots/support-triage');
    expect(screen.getByRole('link', { name: 'Open the Marketplace' })).toHaveAttribute('href', '/marketplace/bots');
    expect(within(list).getByRole('link', { name: 'Daily digest' })).toHaveTextContent('Added');
    await user.type(screen.getByLabelText('Search'), 'morning');
    await waitFor(() =>
      expect(within(screen.getByRole('list', { name: 'Bots to add' })).getAllByRole('link').map((l) => l.textContent)).toEqual([expect.stringContaining('Daily digest')]),
    );
  });

  it('connects what a Marketplace bot needs in place, and adds it only once all of it is connected', async () => {
    const fake = on({ templates: [triage(), digest()] });
    const popup = { closed: false, close: vi.fn() };
    vi.spyOn(window, 'open').mockReturnValue(popup as unknown as Window);
    const { user, router } = renderApp('/marketplace/bots/support-triage');
    expect(await screen.findByRole('heading', { name: 'Support triage', level: 1 })).toBeInTheDocument();
    const needs = await screen.findByRole('list', { name: 'Connections it needs' });
    const add = screen.getByRole('button', { name: 'Add to my bots' });
    expect(await screen.findByText('Connect Notion first')).toBeInTheDocument();
    expect(add).toBeDisabled();
    const notion = within(needs).getByText('Notion').closest('li')!;
    await user.click(within(notion).getByRole('button', { name: 'Connect' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('status')).toHaveTextContent('Connecting Notion…');
    act(() => {
      window.dispatchEvent(new Event('focus'));
    });
    expect(await screen.findByText('Notion is connected.')).toBeInTheDocument();
    await waitFor(() => expect(add).toBeEnabled());
    expect(router.state.location.pathname).toBe('/marketplace/bots/support-triage');
    await user.click(add);
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/support-triage'));
    expect(fake.state.seen).toEqual(['link notion', 'sync', 'install support-triage']);
    // The server scoped its tools to the org's connection of each app.
    expect(fake.state.bots.at(-1)!.connections.map((c) => [c.app, c.tools])).toEqual([
      ['gmail', ['gmail-find-email']],
      ['notion', []],
    ]);
  });

  it('says when there are no bots, and makes one with a shuffled cat and a chosen model', async () => {
    const fake = on({ bots: [] });
    const { user, router } = renderApp('/bots');
    expect(await screen.findByText('No bots yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Browse bots' })).toHaveAttribute('href', '/bots?tab=browse');
    await user.click(screen.getAllByRole('button', { name: 'New bot' })[0]!);
    const dialog = await screen.findByRole('dialog');
    const make = within(dialog).getByRole('button', { name: 'Make bot' });
    expect(make).toBeDisabled();
    const mascot = within(dialog).getByRole('group', { name: 'Mascot' });
    const tile = () => mascot.querySelector('svg.cat-svg')!.innerHTML;
    const before = tile();
    let shuffled = false;
    for (let i = 0; i < 10 && !shuffled; i++) {
      await user.click(within(mascot).getByRole('button', { name: 'Shuffle' }));
      shuffled = tile() !== before;
    }
    expect(shuffled).toBe(true);
    await user.type(within(dialog).getByLabelText('Name'), 'Lead sorter');
    await user.type(within(dialog).getByLabelText('What it is for'), 'Sorts new leads.');
    await user.type(within(dialog).getByLabelText('Instructions'), 'Sort each lead.');
    const model = within(dialog).getByRole('combobox', { name: 'Model' });
    await waitFor(() => expect(model).toHaveValue('claude-sonnet-5-5'));
    await user.selectOptions(model, 'claude-haiku-5-5');
    await user.click(make);
    expect(await screen.findByRole('heading', { name: 'Lead sorter', level: 1 })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/bots/lead-sorter');
    expect(fake.state.bodies[0]).toMatchObject({
      name: 'Lead sorter',
      summary: 'Sorts new leads.',
      instructions: 'Sort each lead.',
      model: 'claude-haiku-5-5',
      permission_mode: 'ask',
      voice: '',
      spec: { loop: [{ id: 'work' }] },
    });
    expect(Object.keys((fake.state.bodies[0] as { look: object }).look).sort()).toEqual(['accessory', 'extra', 'eye', 'head', 'pose', 'tail']);
  });

  it('creates a bot with AI: a chat that asks, drafts the bot as a card, connects what it needs and makes it', async () => {
    const fake = on({ bots: [], connections: [] });
    const { user, router } = renderApp('/bots');
    await user.click(await screen.findByRole('button', { name: 'Create with AI' }));
    const dialog = await screen.findByRole('dialog', { name: 'Create with AI' });
    const chat = within(dialog).getByRole('list', { name: 'Conversation' });
    expect(chat).toHaveTextContent('Tell me what you want a bot to do');
    const create = within(dialog).getByRole('button', { name: 'Create bot' });
    expect(create).toBeDisabled();
    const box = within(dialog).getByRole('textbox', { name: 'Message' });
    await user.type(box, 'Post urgent support email to Slack{Enter}');
    expect(within(chat).getByText('Post urgent support email to Slack')).toBeInTheDocument();
    expect(await within(chat).findByText('Which Slack channel should the urgent ones go to?')).toBeInTheDocument();
    expect(box).toHaveValue('');
    await user.type(box, '#support');
    await user.click(within(dialog).getByRole('button', { name: 'Send' }));
    const card = await within(chat).findByRole('listitem', { name: 'Draft: Support triage' });
    expect(card).toHaveTextContent('Posts the urgent support email to Slack.');
    expect(card).toHaveTextContent('Claude Sonnet 5.5 · 4 steps · 1 gate · 1 skill');
    expect(fake.state.bodies.at(-1)).toMatchObject({ messages: [{ role: 'user' }, { role: 'assistant' }, { role: 'user', content: '#support' }] });
    // Neither app is connected: Create waits until both are.
    const apps = within(card).getByRole('list', { name: 'Apps it needs' });
    expect(within(apps).getAllByRole('button', { name: 'Connect' })).toHaveLength(2);
    expect(create).toBeDisabled();

    vi.spyOn(window, 'open').mockReturnValue({ closed: false, close: () => undefined } as unknown as Window);
    for (const n of [1, 2]) {
      await user.click(within(apps).getAllByRole('button', { name: 'Connect' })[0]!);
      await waitFor(() => expect(within(apps).getAllByText('Connected')).toHaveLength(n), { timeout: 5000 });
    }
    expect(fake.state.seen).toEqual(expect.arrayContaining(['link gmail', 'link slack']));
    await user.click(within(within(card).getByRole('list', { name: 'Glyphh cats' })).getByRole('button', { name: 'Rio' }));
    await user.click(create);
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/support-triage'));
    expect(fake.state.bodies.at(-1)).toMatchObject({
      name: 'Support triage',
      look: { head: 'round', accessory: 'glasses' },
      connections: [
        { connection_id: 'c-gmail', tools: ['gmail-find-email'] },
        { connection_id: 'c-slack', tools: ['slack-send-message'] },
      ],
    });
    expect(fake.state.bodies.at(-1)).not.toHaveProperty('apps');
  }, 15_000);

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
