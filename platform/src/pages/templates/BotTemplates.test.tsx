import { screen, waitFor, within } from '@testing-library/react';
import { HttpResponse } from 'msw';
import { decidesLines, fromServer, needsRrotor, runsOnPills, type BotTemplate } from '@/api/botTemplates';
import { ApiError } from '@/api/client';
import { botsFake, folderTidy, gmail, look, slack } from '@/test/bots';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

const triage = (): BotTemplate => ({
  slug: 'inbox-triage',
  version: '1.2.0',
  name: 'Inbox triage',
  summary: 'Sorts the morning’s email.',
  description: 'Reads what came in overnight and files each email.',
  look,
  apps: [
    { app: 'gmail', name: 'Gmail', tools: ['gmail-find-email'] },
    { app: 'slack', name: 'Slack', tools: ['slack-send-message'] },
  ],
  decides: [{ name: 'urgency', question: 'How urgent is this email?', outcomes: ['urgent', 'normal', 'spam'] }],
  examples: ['What came in overnight?', 'Which emails need an answer today?', 'File the newsletters'],
  task: 'Sort the unread email.',
  schedule: null,
  runs_on: ['cloud', 'rrotor'],
});

const plain = (n: number): BotTemplate => ({ ...triage(), slug: `bot-${n}`, name: `Helper ${n}`, summary: `Does job ${n}.`, apps: [], decides: [], examples: [`Do job number ${n}`], runs_on: ['cloud'] });

/** Ada Cloud off (the default account), the org's bots and only Gmail connected (or both), and the Marketplace's bots. */
function on(templates: BotTemplate[] = [triage()], connections = [gmail()]) {
  const seen: string[] = [];
  server.use(
    ...botsFake({ connections }).handlers,
    http.get('*/api/v1/bot-templates', () => HttpResponse.json({ templates })),
    http.post('*/api/v1/bot-templates/:slug/install', ({ params }) => {
      seen.push(`add ${params.slug}`);
      return HttpResponse.json({ slug: 'inbox-triage', name: 'Inbox triage' });
    }),
  );
  return seen;
}

/** The pills that say where a bot can run, as their words. */
const pills = (within_: HTMLElement) => Array.from(within(within_).getAllByRole('group', { name: 'Where it can run' })[0]!.children).map((p) => p.textContent);

describe('the Marketplace’s bots', () => {
  it('is in the Bots group with Ada Cloud off, with only the Bots tab, each template a card', async () => {
    on();
    const { user, router } = renderApp('/bots');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    await user.click(await within(sidebar).findByRole('link', { name: 'Marketplace' }));
    expect(router.state.location.pathname).toBe('/marketplace/bots');
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Bots']);
    const card = await screen.findByRole('link', { name: 'Inbox triage' });
    // What it does, the apps it needs, what it decides, things to ask it.
    expect(card).toHaveTextContent('Sorts the morning’s email.');
    expect(card).toHaveTextContent('NeedsGmailSlack');
    expect(card).toHaveTextContent('Decidesurgency (urgent, normal, spam)');
    expect(within(within(card).getByRole('list', { name: 'Things to ask Inbox triage' })).getAllByRole('listitem').map((l) => l.textContent)).toEqual(['“What came in overnight?”', '“Which emails need an answer today?”']);
    expect(pills(card)).toEqual(['Cloud', 'rrotor']);
    await user.click(card);
    expect(router.state.location.pathname).toBe('/marketplace/bots/inbox-triage');
  });

  it('says where each bot can run with a pill: Cloud, rrotor, or both; one that needs a rrotor shows rrotor alone', async () => {
    on([triage(), plain(1), folderTidy()]);
    renderApp('/marketplace/bots');
    expect(pills(await screen.findByRole('link', { name: 'Inbox triage' }))).toEqual(['Cloud', 'rrotor']);
    expect(pills(screen.getByRole('link', { name: 'Helper 1' }))).toEqual(['Cloud']);
    const tidy = screen.getByRole('link', { name: 'Folder tidy' });
    expect(pills(tidy)).toEqual(['rrotor']);
    expect(tidy).toHaveTextContent('NeedsNo apps');
    expect(tidy).toHaveTextContent('Decideswhere it goes (invoices, contracts, bin)');
    // A card with nothing to decide and nothing to ask has neither line.
    on([{ ...plain(2), examples: [] }]);
    const bare = renderApp('/marketplace/bots');
    const card = await within(bare.container).findByRole('link', { name: 'Helper 2' });
    expect(card).not.toHaveTextContent('Decides');
    expect(within(card).queryByRole('list')).toBeNull();
    expect([runsOnPills(['rrotor', 'cloud']), runsOnPills(['rrotor']), runsOnPills(['cloud'])]).toEqual([['Cloud', 'rrotor'], ['rrotor'], ['Cloud']]);
  });

  it('reads a template as the server sends it: a list may be missing, an app may come without its name', () => {
    const read = fromServer({ slug: 'x', name: 'X', apps: [{ app: 'google_sheets' }], decides: [{ name: 'needs_reply', question: '', outcomes: [] }] });
    expect(read.apps).toEqual([{ app: 'google_sheets', name: 'Google Sheets', tools: [] }]);
    expect(read.runs_on).toEqual(['cloud', 'rrotor']);
    expect([read.summary, read.examples, read.task]).toEqual(['', [], '']);
    expect(decidesLines(read.decides)).toEqual(['needs reply']);
    expect(fromServer({ slug: 'y', name: 'Y', runs_on: ['rrotor'] }).runs_on).toEqual(['rrotor']);
  });

  it('sends the Models tab and a model’s page to the bots with Ada Cloud off', async () => {
    on();
    const { router } = renderApp('/marketplace/models');
    await screen.findByRole('link', { name: 'Inbox triage' });
    expect(router.state.location.pathname).toBe('/marketplace/bots');
    const off = renderApp('/marketplace');
    await waitFor(() => expect(off.router.state.location.pathname).toBe('/marketplace/bots'));
    const model = renderApp('/marketplace/models/agentic-memory');
    await waitFor(() => expect(model.router.state.location.pathname).toBe('/marketplace/bots'));
  });

  it('searches the bots and pages them', async () => {
    on([triage(), ...Array.from({ length: 30 }, (_, i) => plain(i + 1))]);
    const { user } = renderApp('/marketplace/bots');
    const grid = await screen.findByRole('list', { name: 'Bot templates' });
    expect(within(grid).getAllByRole('link')).toHaveLength(24);
    await user.type(screen.getByLabelText('Search'), 'slack');
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Helper 1' })).not.toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'Inbox triage' })).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'job number 9');
    expect(await screen.findByRole('link', { name: 'Helper 9' })).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'spam');
    expect(await screen.findByRole('link', { name: 'Inbox triage' })).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing like it');
    expect(await screen.findByText('No bot matches “nothing like it”.')).toBeInTheDocument();
  });

  it('shows a bot’s details: what it does, the apps it needs, what it decides, things to ask it, where it can run', async () => {
    on();
    renderApp('/marketplace/bots/inbox-triage');
    expect(await screen.findByRole('heading', { name: 'Inbox triage', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Reads what came in overnight and files each email.')).toBeInTheDocument();
    const needs = screen.getByRole('list', { name: 'Apps it needs' });
    expect(await within(needs).findByText('Connected', { selector: 'span' })).toBeInTheDocument();
    // Slack is connected in the Bots area's CONNECTIONS, the one place for it; Add waits for it.
    expect(within(needs).getByRole('link', { name: 'Connect it in Bots' })).toHaveAttribute('href', '/bots?rail=connections&add=1');
    expect(screen.getByRole('button', { name: 'Add to my bots' })).toBeDisabled();
    expect(screen.getByText('Connect Slack first')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'What it decides' })).toBeInTheDocument();
    const decides = screen.getByRole('list', { name: 'What it decides' });
    expect(decides).toHaveTextContent('Decides: urgency (urgent, normal, spam)');
    expect(decides).toHaveTextContent('How urgent is this email?');
    expect(within(screen.getByRole('list', { name: 'Things to ask it' })).getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByRole('heading', { name: 'Where it can run' })).toBeInTheDocument();
    expect(screen.getByText('On Glyphh cloud with nothing to install, or on a rrotor of your own.')).toBeInTheDocument();
    expect(pills(document.body)).toEqual(['Cloud', 'rrotor']);
    const facts = screen.getByLabelText('About this bot', { selector: 'div' });
    expect(facts).toHaveTextContent('Runs onCloud, rrotor');
    expect(facts).toHaveTextContent('AppsGmail, Slack');
    expect(facts).toHaveTextContent('Decidesurgency');
    expect(facts).toHaveTextContent('Version1.2.0');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Marketplaceinbox-triage');
    // What it is allowed to call in each app is not a list on this page.
    expect(screen.queryByRole('tab', { name: 'Tools' })).toBeNull();
    expect(document.body.textContent).not.toMatch(/gmail-find-email|slack-send-message/);
  });

  it('says no word of how a bot works inside, on the list and on a bot’s page', async () => {
    const said = () => {
      const named = Array.from(document.body.querySelectorAll('[aria-label], [title], [placeholder], [alt]')).flatMap((el) => ['aria-label', 'title', 'placeholder', 'alt'].map((a) => el.getAttribute(a) ?? ''));
      return [document.body.textContent ?? '', ...named].join('\n');
    };
    const clean = () => expect(said().match(/\b(gates?|loop|spec|skills?|plugins?|json|swarms?|projects?)\b/gi) ?? []).toEqual([]);
    on([triage(), folderTidy()]);
    const list = renderApp('/marketplace/bots');
    expect(await screen.findByRole('link', { name: /Inbox triage/ })).toHaveTextContent('Decidesurgency (urgent, normal, spam)');
    clean();
    list.unmount();
    const page = renderApp('/marketplace/bots/inbox-triage');
    await screen.findByRole('list', { name: 'What it decides' });
    clean();
    page.unmount();
    renderApp('/marketplace/bots/folder-tidy');
    await screen.findByText(/Only on a rrotor of your own/);
    clean();
  });

  it('says what a bot that needs no app, decides nothing and has nothing to ask has', async () => {
    on([{ ...plain(1), examples: [] }]);
    renderApp('/marketplace/bots/bot-1');
    expect(await screen.findByText('It needs no app.')).toBeInTheDocument();
    expect(screen.getByText('It decides nothing on its own.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Things to ask it' })).toBeNull();
    expect(screen.getByText('On Glyphh cloud. Nothing to install.')).toBeInTheDocument();
    const facts = screen.getByLabelText('About this bot', { selector: 'div' });
    expect(facts).toHaveTextContent('AppsNone');
    expect(facts).toHaveTextContent('DecidesNothing');
    expect(facts).toHaveTextContent('Runs onCloud');
  });

  it('adds a bot to the org, then opens the copy in Bots', async () => {
    const seen = on([triage()], [gmail(), slack()]);
    const { user, router } = renderApp('/marketplace/bots/inbox-triage');
    await user.click(await screen.findByRole('button', { name: 'Add to my bots' }));
    expect(await screen.findByText('Inbox triage is yours: it’s in Bots.')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/bots/inbox-triage');
    expect(seen).toEqual(['add inbox-triage']);
  });

  it('adding a bot that needs a rrotor with none linked says the server’s sentence, with the way to set one up', async () => {
    const fake = botsFake({ templates: [folderTidy()], rrotors: false });
    server.use(...fake.handlers);
    const { user } = renderApp('/marketplace/bots/folder-tidy');
    expect(await screen.findByRole('heading', { name: 'Folder tidy', level: 1 })).toBeInTheDocument();
    expect(pills(document.body)).toEqual(['rrotor']);
    await user.click(await screen.findByRole('button', { name: 'Add to my bots' }));
    expect(await screen.findByText('Folder tidy runs on a rrotor, and you have none linked yet. Set one up, then add it.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Set up a rrotor' })).toHaveAttribute('href', '/runtimes?add=1');
    expect(fake.state.seen).not.toContain('install folder-tidy');
    // A setup address on another site opens there; any other refusal is not this one.
    const refused = (detail: Record<string, unknown>, status = 422) => new ApiError(status, { code: 'E_INVALID', message: 'No rrotor yet.', ...detail });
    expect(needsRrotor(refused({ reason: 'rrotor', setup_url: 'https://docs.glyphh.ai/rrotor' }))).toEqual({ message: 'No rrotor yet.', setupUrl: 'https://docs.glyphh.ai/rrotor' });
    expect(needsRrotor(refused({ reason: 'rrotor' }))).toEqual({ message: 'No rrotor yet.', setupUrl: '' });
    expect([needsRrotor(refused({ reason: 'connections', apps: ['slack'] })), needsRrotor(refused({ reason: 'rrotor' }, 409)), needsRrotor(new Error('x'))]).toEqual([null, null, null]);
  });

  it('adds a bot that needs a rrotor once one is linked: it runs there', async () => {
    const fake = botsFake({ templates: [folderTidy()] });
    server.use(...fake.handlers);
    const { user, router } = renderApp('/marketplace/bots/folder-tidy');
    await user.click(await screen.findByRole('button', { name: 'Add to my bots' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/bots/folder-tidy'));
    expect(fake.state.bots.at(-1)).toMatchObject({ slug: 'folder-tidy', can_run_on: ['rrotor'], runs_on: 'rr-studio', task: 'Tidy the folder.', examples: ['Tidy my Downloads folder'] });
  });

  it('says what the server refused, a bot that is not there, and an empty Marketplace', async () => {
    on([triage()], [gmail(), slack()]);
    server.use(http.post('*/api/v1/bot-templates/:slug/install', () => apiError(409, 'E_BOT_EXISTS', 'You have a bot named inbox-triage.')));
    const { user } = renderApp('/marketplace/bots/inbox-triage');
    await user.click(await screen.findByRole('button', { name: 'Add to my bots' }));
    expect(await screen.findByText(/You have a bot named inbox-triage/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Set up a rrotor' })).toBeNull();
    renderApp('/marketplace/bots/nope');
    expect(await screen.findByText('There is no such bot in the Marketplace')).toBeInTheDocument();
    server.use(http.get('*/api/v1/bot-templates', () => HttpResponse.json({ templates: [] })));
    renderApp('/marketplace/bots');
    expect(await screen.findByText('No bots yet')).toBeInTheDocument();
  });
});
