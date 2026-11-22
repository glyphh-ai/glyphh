import { screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import type { BotRun } from '@/api/bots';
import { botsFake, inbox, waiting } from '@/test/bots';
import { renderApp } from '@/test/render';
import { server } from '@/test/server';
import { siteCrew, swarmRun, swarmsFake, turn } from '@/test/swarms';

const bots = [inbox(), inbox({ id: 'b-digest', slug: 'digest', name: 'Digest' }), inbox({ id: 'b-third', slug: 'third', name: 'Third' })];

/** The bots and swarms fakes; the swarms' first, so its approvals queue (theirs and the bots' runs) is the one answered. */
function on(given: Parameters<typeof swarmsFake>[0] = {}, botRuns: BotRun[] = []) {
  const b = botsFake({ bots, runs: botRuns });
  const s = swarmsFake({ botRuns: () => b.state.runs, ...given });
  server.use(...s.handlers, ...b.handlers);
  return s;
}

describe('swarms', () => {
  it('lists the org’s swarms with their repo, crew in order and machine', async () => {
    on({ swarms: [siteCrew(), siteCrew({ id: 's-2', slug: 'docs', name: 'Docs crew', review: 'auto', rounds: 2, runs_on: 'rr-acme' })] });
    const { user, router } = renderApp('/bots');
    await user.click(await within(await screen.findByRole('complementary', { name: 'Main' })).findByRole('link', { name: 'Swarms' }));
    expect(router.state.location.pathname).toBe('/swarms');
    const site = await screen.findByRole('link', { name: 'Site crew' });
    expect(site).toHaveTextContent('acme/site · main');
    expect(site).toHaveTextContent('Inbox helper → Digest');
    expect(site).toHaveTextContent('1 round · you review each turn');
    expect(await within(site).findByText('On Studio Mac')).toBeInTheDocument();
    const docs = screen.getByRole('link', { name: 'Docs crew' });
    expect(docs).toHaveTextContent('2 rounds · merged as they open');
    expect(await within(docs).findByText('On Acme')).toBeInTheDocument();
  });

  it('says what a swarm is when there is none', async () => {
    on({ swarms: [] });
    renderApp('/swarms');
    expect(await screen.findByText('No swarms yet')).toBeInTheDocument();
  });

  it('makes a swarm: its repo, its crew in speaking order and the rrotor it runs on', async () => {
    const fake = on({ swarms: [], key: { set: false, hint: '', login: '', set_at: null } });
    const { user, router } = renderApp('/swarms');
    await user.click(await screen.findByRole('button', { name: 'New swarm' }));
    expect(router.state.location.pathname).toBe('/swarms/new');
    expect(await screen.findByRole('link', { name: 'set it' })).toHaveAttribute('href', '/settings/github-token');
    const make = screen.getByRole('button', { name: 'Make swarm' });
    expect(make).toBeDisabled();
    await user.type(screen.getByLabelText('Name'), 'Site crew');
    await user.type(screen.getByLabelText('GitHub repo'), 'https://github.com/acme/site');
    const add = screen.getByRole('combobox', { name: 'Add a bot' });
    await waitFor(() => expect(within(add).getAllByRole('option')).toHaveLength(4));
    await user.selectOptions(add, 'b-inbox');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Add a bot' }), 'b-digest');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Add a bot' }), 'b-third');
    const order = () => within(screen.getByRole('list', { name: 'Crew' })).getAllByRole('listitem').map((li) => li.textContent);
    expect(order()).toEqual([expect.stringContaining('Inbox helper'), expect.stringContaining('Digest'), expect.stringContaining('Third')]);
    expect(screen.getByRole('combobox', { name: 'Add a bot' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Move Digest up' }));
    await user.click(screen.getByRole('button', { name: 'Move Inbox helper down' }));
    await user.click(screen.getByRole('button', { name: 'Take Third out' }));
    expect(order()).toEqual([expect.stringContaining('Digest'), expect.stringContaining('Inbox helper')]);
    const where = screen.getByRole('combobox', { name: 'Runs on' });
    const options = within(where).getAllByRole('option') as HTMLOptionElement[];
    expect(options.map((o) => o.textContent)).toEqual(['Choose a rrotor…', 'Studio Mac', 'Acme (offline)']); // never Glyphh cloud
    expect(options[2]).toBeDisabled();
    await user.selectOptions(where, 'rr-studio');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Rounds' }), '2');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Review' }), 'auto');
    expect(screen.getByText(/merged as it opens/)).toBeInTheDocument();
    await user.click(make);
    await waitFor(() => expect(router.state.location.pathname).toBe('/swarms/site-crew'));
    expect(fake.state.bodies[0]).toEqual({
      name: 'Site crew',
      repo_url: 'https://github.com/acme/site',
      base_branch: 'main',
      members: ['b-digest', 'b-inbox'],
      runs_on: 'rr-studio',
      rounds: 2,
      review: 'auto',
    });
  });

  it('says a swarm needs a rrotor when the org has none', async () => {
    on({ swarms: [] });
    server.use(http.get('*/api/v1/bots/places', () => HttpResponse.json({ places: [{ id: null, name: 'Glyphh cloud', mode: 'cloud', linked: true }] })));
    renderApp('/swarms/new');
    expect(await screen.findByText(/none is linked to Glyphh yet/)).toBeInTheDocument();
  });

  it('runs a swarm: each turn on the timeline, its pull request merged or rejected, then done', async () => {
    const fake = on();
    const { user } = renderApp('/swarms/site-crew');
    expect(await screen.findByRole('heading', { name: 'Site crew' })).toBeInTheDocument();
    expect(await screen.findByText(/on Studio Mac/)).toBeInTheDocument();
    expect(await screen.findByText('No runs yet')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Task'), 'Make the home page.');
    await user.click(screen.getByRole('button', { name: 'Start' }));
    const view = await screen.findByRole('region', { name: 'Swarm run' });
    expect(within(view).getByText('Make the home page.')).toBeInTheDocument();
    const turns = await within(view).findByRole('list', { name: 'Turns' });
    const first = await within(turns).findByRole('listitem', { name: 'Turn 1: Inbox helper' });
    expect(await within(first).findByText('Waits for you', {}, { timeout: 5000 })).toBeInTheDocument();
    const pr = within(first).getByRole('region', { name: 'Pull request #41' });
    expect(within(pr).getByRole('link', { name: /#41 Inbox helper: I made the home page/ })).toHaveAttribute('href', 'https://github.com/acme/site/pull/41');
    expect(within(pr).getByText('src/pages/Home.tsx')).toBeInTheDocument();
    expect(within(pr).getByText('+84')).toBeInTheDocument();
    expect(within(pr).getByText('turn-1-inbox-helper-k3x9')).toBeInTheDocument();
    expect(screen.getByText('A run is going: answer its pull request or cancel it first.')).toBeInTheDocument();
    await user.click(within(pr).getByRole('button', { name: 'Merge' }));
    const second = await within(turns).findByRole('listitem', { name: 'Turn 2: Digest' });
    expect(within(first).getByText('Merged')).toBeInTheDocument();
    expect(within(second).getByText('said DONE')).toBeInTheDocument();
    await user.click(within(second).getByRole('button', { name: 'Reject' }));
    expect(await within(view).findByText('Done')).toBeInTheDocument();
    expect(within(second).getByText('Rejected')).toBeInTheDocument();
    expect(fake.state.bodies).toEqual(['merge', 'reject']);
    expect(screen.getByRole('list', { name: 'Runs' })).toHaveTextContent('2 turns');
  });

  it('cancels a run and shows why one failed', async () => {
    const fake = on({ runs: [swarmRun({ id: 'sr-old', status: 'failed', error: 'Digest’s turn 2 failed: the clone failed', turns: [turn(1, { status: 'merged' }), turn(2, { status: 'failed', pr_url: null, files: [], said: '', error: 'the clone failed' })] })] });
    const { user } = renderApp('/swarms/site-crew?run=sr-old');
    const view = await screen.findByRole('region', { name: 'Swarm run' });
    expect(within(view).getAllByText(/the clone failed/)).toHaveLength(2);
    expect(within(view).queryByRole('button', { name: 'Cancel run' })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText('Task'), 'Again.');
    await user.click(screen.getByRole('button', { name: 'Start' }));
    await user.click(await screen.findByRole('button', { name: 'Cancel run' }));
    expect(await screen.findByText('cancelled')).toBeInTheDocument();
    expect(fake.state.seen).toEqual(['run site-crew', 'cancel sr-1']);
  });

  it('shows a swarm’s pull request in Approvals beside the bots’ runs, merged there', async () => {
    const fake = on({ runs: [swarmRun()] }, [waiting()]);
    const { user } = renderApp('/approvals');
    const queue = await screen.findByRole('list', { name: 'Waiting runs' });
    const items = await within(queue).findAllByRole('article');
    expect(items).toHaveLength(2);
    const swarm = within(queue).getByRole('article', { name: 'site-crew: Merge PR #41 by Inbox helper?' });
    expect(within(swarm).getByRole('link', { name: 'site-crew' })).toHaveAttribute('href', '/swarms/site-crew?run=sr-1');
    expect(within(swarm).getByText(/Swarm · “Make the home page/)).toBeInTheDocument();
    await user.click(within(swarm).getByRole('button', { name: 'Merge' }));
    // Merged, the next bot's pull request waits in its place.
    expect(await within(queue).findByRole('article', { name: 'site-crew: Merge PR #42 by Digest?' })).toBeInTheDocument();
    expect(within(queue).getAllByRole('article')).toHaveLength(2);
    expect(fake.state.bodies).toEqual(['merge']);
  });

  it('changes and deletes a swarm in its settings', async () => {
    const fake = on();
    const { user, router } = renderApp('/swarms/site-crew?tab=settings');
    const name = await screen.findByLabelText('Name');
    await user.clear(name);
    await user.type(name, 'The crew');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(fake.state.seen).toEqual(['update site-crew']));
    expect(fake.state.bodies[0]).toMatchObject({ name: 'The crew', members: ['b-inbox', 'b-digest'] });
    await user.click(await screen.findByRole('button', { name: 'Delete swarm' }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(router.state.location.pathname).toBe('/swarms'));
    expect(fake.state.seen).toEqual(['update site-crew', 'delete site-crew']);
  });
});

describe('the GitHub token', () => {
  it('is saved, tried by the server, shown by its last characters and removed', async () => {
    const fake = on({ key: { set: false, hint: '', login: '', set_at: null } });
    const { user } = renderApp('/settings/github-token');
    const field = await screen.findByLabelText('GitHub token');
    await user.type(field, 'github_pat_bad');
    await user.click(screen.getByRole('button', { name: 'Save token' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('GitHub does not take that token.');
    await user.clear(field);
    await user.type(field, 'github_pat_goodAB12');
    await user.click(screen.getByRole('button', { name: 'Save token' }));
    expect(await screen.findByText('Token ending AB12 · acme-bot')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Make one on GitHub' })).toHaveAttribute('href', expect.stringContaining('github.com/settings/personal-access-tokens'));
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(screen.queryByText(/Token ending/)).not.toBeInTheDocument());
    expect(fake.state.seen).toEqual(['github key', 'github key removed']);
  });
});
