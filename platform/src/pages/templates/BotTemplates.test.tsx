import { screen, waitFor, within } from '@testing-library/react';
import { HttpResponse } from 'msw';
import type { BotTemplate } from '@/api/botTemplates';
import { botsFake, gmail, look } from '@/test/bots';
import { renderApp } from '@/test/render';
import { apiError, http, server } from '@/test/server';

const triage = (): BotTemplate => ({
  slug: 'inbox-triage',
  name: 'Inbox triage',
  summary: 'Sorts the morning’s email.',
  description: 'Reads what came in overnight and files each email.',
  look,
  model: 'claude-sonnet-5-5',
  spec: {},
  skills: { 'sorting.md': 'How to sort.' },
  required_apps: [
    { slug: 'gmail', name: 'Gmail', icon: null },
    { slug: 'slack', name: 'Slack', icon: null },
  ],
  tools: ['gmail-find-email', 'slack-send-message'],
  gates: ['file_it'],
});

const plain = (n: number): BotTemplate => ({ ...triage(), slug: `bot-${n}`, name: `Helper ${n}`, required_apps: [], tools: [`tool_${n}`], gates: [], skills: {} });

/** Ada Cloud off (the default account), the org's bots and only Gmail connected, and the Marketplace's bots. */
function on(templates: BotTemplate[] = [triage()]) {
  const seen: string[] = [];
  server.use(
    ...botsFake({ connections: [gmail()] }).handlers,
    http.get('*/api/v1/bot-templates', () => HttpResponse.json({ templates })),
    http.post('*/api/v1/bot-templates/:slug/install', ({ params }) => {
      seen.push(`add ${params.slug}`);
      return HttpResponse.json({ slug: 'inbox-triage', name: 'Inbox triage' });
    }),
  );
  return seen;
}

describe('the Marketplace’s bots', () => {
  it('is in the Bots group with Ada Cloud off, with only the Bots tab, each template a card', async () => {
    on();
    const { user, router } = renderApp('/bots');
    const sidebar = await screen.findByRole('complementary', { name: 'Main' });
    await user.click(await within(sidebar).findByRole('link', { name: 'Marketplace' }));
    expect(router.state.location.pathname).toBe('/marketplace/bots');
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Bots']);
    const card = await screen.findByRole('link', { name: 'Inbox triage' });
    expect(card).toHaveTextContent('Sorts the morning’s email.');
    expect(card).toHaveTextContent('GmailSlack');
    expect(card).toHaveTextContent('2 tools · 1 gate');
    await user.click(card);
    expect(router.state.location.pathname).toBe('/marketplace/bots/inbox-triage');
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
    await user.type(screen.getByLabelText('Search'), 'tool_9');
    expect(await screen.findByRole('link', { name: 'Helper 9' })).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing like it');
    expect(await screen.findByText('No bot matches “nothing like it”.')).toBeInTheDocument();
  });

  it('shows a bot’s details: what it does, the connections it needs, its gates, tools and facts', async () => {
    on();
    const { user } = renderApp('/marketplace/bots/inbox-triage');
    expect(await screen.findByRole('heading', { name: 'Inbox triage', level: 1 })).toBeInTheDocument();
    expect(screen.getByText('Reads what came in overnight and files each email.')).toBeInTheDocument();
    const needs = screen.getByRole('list', { name: 'Connections it needs' });
    expect(await within(needs).findByText('Connected', { selector: 'span' })).toBeInTheDocument();
    expect(within(needs).getByRole('link', { name: /Connect/ })).toHaveAttribute('href', '/connections/slack');
    expect(screen.getByRole('list', { name: 'Its gates' })).toHaveTextContent('file_it');
    const facts = screen.getByLabelText('About this bot', { selector: 'div' });
    expect(facts).toHaveTextContent('Runs onclaude-sonnet-5-5');
    expect(facts).toHaveTextContent('ConnectionsGmail, Slack');
    expect(facts).toHaveTextContent('Skills1');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Marketplaceinbox-triage');
    await user.click(screen.getByRole('tab', { name: 'Tools' }));
    expect(screen.getByRole('list', { name: "Inbox triage's tools" })).toHaveTextContent('gmail-find-emailslack-send-message');
  });

  it('says what a bot without needs, gates or tools has', async () => {
    on([{ ...plain(1), tools: [] }]);
    const { user } = renderApp('/marketplace/bots/bot-1');
    expect(await screen.findByText('It needs no connection.')).toBeInTheDocument();
    expect(screen.getByText('It has no gates.')).toBeInTheDocument();
    expect(screen.getByLabelText('About this bot', { selector: 'div' })).toHaveTextContent('ConnectionsNone');
    await user.click(screen.getByRole('tab', { name: 'Tools' }));
    expect(screen.getByText('It uses no tools')).toBeInTheDocument();
  });

  it('adds a bot to the org, then opens the copy in Bots', async () => {
    const seen = on();
    const { user, router } = renderApp('/marketplace/bots/inbox-triage');
    await user.click(await screen.findByRole('button', { name: 'Add to my bots' }));
    expect(await screen.findByText('Inbox triage is yours: it’s in Bots.')).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/bots/inbox-triage');
    expect(seen).toEqual(['add inbox-triage']);
  });

  it('says what the server refused, a bot that is not there, and an empty Marketplace', async () => {
    on();
    server.use(http.post('*/api/v1/bot-templates/:slug/install', () => apiError(409, 'E_BOT_EXISTS', 'You have a bot named inbox-triage.')));
    const { user } = renderApp('/marketplace/bots/inbox-triage');
    await user.click(await screen.findByRole('button', { name: 'Add to my bots' }));
    expect(await screen.findByText(/You have a bot named inbox-triage/)).toBeInTheDocument();
    renderApp('/marketplace/bots/nope');
    expect(await screen.findByText('There is no such bot in the Marketplace')).toBeInTheDocument();
    server.use(http.get('*/api/v1/bot-templates', () => HttpResponse.json({ templates: [] })));
    renderApp('/marketplace/bots');
    expect(await screen.findByText('No bots yet')).toBeInTheDocument();
  });
});
