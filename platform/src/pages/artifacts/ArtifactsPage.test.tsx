import { screen, within } from '@testing-library/react';
import { artifacts, manyArtifacts, me } from '@/test/fixtures';
import { renderApp } from '@/test/render';
import { apiError, artifactsHandler, http, HttpResponse, server, v1 } from '@/test/server';

const asReviewer = () => http.get(v1('/me'), () => HttpResponse.json({ ...me, reviewer: true }));
const cards = () => within(screen.getByRole('list', { name: 'Artifacts' })).getAllByRole('listitem');

describe('Artifacts', () => {
  it('is in the sidebar under Runtimes & licences, and lists the published ones as cards with Open', async () => {
    renderApp('/artifacts');
    expect(await screen.findByRole('heading', { name: 'Artifacts', level: 1 })).toBeInTheDocument();
    const main = screen.getByRole('complementary', { name: 'Main' });
    expect(await within(main).findByRole('link', { name: 'Artifacts' })).toHaveAttribute('href', '/artifacts');
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Runtimes & licencesArtifacts');
    const list = await screen.findByRole('list', { name: 'Artifacts' });
    const [failures, prs, onCall] = within(list).getAllByRole('listitem');
    expect(within(list).getAllByRole('listitem')).toHaveLength(3);
    expect(within(failures!).getByText('Deploy failures')).toBeInTheDocument();
    expect(within(failures!).getByText("Last week's deploy failures by service, from the deploy log and GitHub.")).toBeInTheDocument();
    expect(within(failures!).getByText('Acme production · v1')).toBeInTheDocument();
    expect(within(failures!).getByText('Everyone')).toBeInTheDocument();
    expect(within(failures!).getByText('Published by Chris Timmerman · 28 Oct 2026')).toBeInTheDocument();
    const open = within(failures!).getByRole('link', { name: 'Open' });
    expect(open).toHaveAttribute('href', 'https://rrotor.acme.com/apps/deploy-failures/');
    expect(open).toHaveAttribute('target', '_blank');
    expect(within(prs!).getByText('sre')).toBeInTheDocument();
    expect(within(prs!).getByText('admin')).toBeInTheDocument();
    expect(within(prs!).getByText('Published by Sam Rivera · 28 Oct 2026')).toBeInTheDocument();
    expect(within(onCall!).getByRole('link', { name: 'Open' })).toHaveAttribute('href', 'https://rrotor.lab.acme.com/apps/on-call/');
    // A member sees no tabs and no review buttons.
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Retire' })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Pages' })).not.toBeInTheDocument();
  });

  it('searches once typing pauses, with the query in the URL', async () => {
    const asked: string[] = [];
    server.use(
      http.get(v1('/artifacts'), ({ request }) => {
        const url = new URL(request.url);
        asked.push(url.search);
        const q = (url.searchParams.get('q') ?? '').toLowerCase();
        const found = artifacts.filter((a) => a.state === 'approved' && a.title.toLowerCase().includes(q));
        return HttpResponse.json({ artifacts: found, page: 1, per_page: 24, total: found.length });
      }),
    );
    const { user, router } = renderApp('/artifacts');
    await screen.findByRole('list', { name: 'Artifacts' });
    await user.type(screen.getByLabelText('Search'), 'on-call');
    await vi.waitFor(() => expect(router.state.location.search).toBe('?q=on-call'));
    await vi.waitFor(() => expect(cards()).toHaveLength(1));
    expect(within(cards()[0]!).getByText('On-call handover')).toBeInTheDocument();
    expect(asked.at(-1)).toBe('?page=1&per_page=24&state=approved&q=on-call');
    await user.clear(screen.getByLabelText('Search'));
    await user.type(screen.getByLabelText('Search'), 'nothing here');
    expect(await screen.findByText('No artifact matches “nothing here”.')).toBeInTheDocument();
    expect(screen.getByText('Nothing matches')).toBeInTheDocument();
  });

  it('opens on the page the URL names, and pages through 24 at a time', async () => {
    server.use(artifactsHandler(manyArtifacts));
    const { user, router } = renderApp('/artifacts?q=report&page=2');
    const search = await screen.findByLabelText('Search');
    expect(search).toHaveValue('report');
    await vi.waitFor(() => expect(cards()).toHaveLength(6));
    const pager = screen.getByRole('navigation', { name: 'Pages' });
    expect(within(pager).getByText('25–30 of 30')).toBeInTheDocument();
    expect(within(pager).getByRole('button', { name: 'Next' })).toBeDisabled();
    await user.click(within(pager).getByRole('button', { name: 'Previous' }));
    await vi.waitFor(() => expect(router.state.location.search).toBe('?q=report&page=1'));
    await vi.waitFor(() => expect(cards()).toHaveLength(24));
    expect(within(screen.getByRole('navigation', { name: 'Pages' })).getByText('1–24 of 30')).toBeInTheDocument();
    expect(within(screen.getByRole('navigation', { name: 'Pages' })).getByRole('button', { name: 'Previous' })).toBeDisabled();
  });

  it('says so when nothing is published, and shows the server’s refusal', async () => {
    server.use(http.get(v1('/artifacts'), () => HttpResponse.json({ artifacts: [], page: 1, per_page: 24, total: 0 })));
    renderApp('/artifacts');
    expect(await screen.findByText('Nothing published yet')).toBeInTheDocument();
    expect(screen.getByText('Ask Claude to publish an artifact to your org.')).toBeInTheDocument();
    server.use(http.get(v1('/artifacts'), () => apiError(503, 'E_UNAVAILABLE', 'The catalogue is unavailable.')));
    renderApp('/artifacts');
    expect(await screen.findByText('The catalogue is unavailable.')).toBeInTheDocument();
  });

  describe('for a reviewer', () => {
    it('has the tabs, and approves one awaiting review', async () => {
      const calls: string[] = [];
      server.use(
        asReviewer(),
        http.post(v1('/artifacts/:id/approve'), ({ params }) => {
          calls.push(`approve ${params.id}`);
          return HttpResponse.json({ ...artifacts[3], state: 'approved' });
        }),
      );
      const { user, router } = renderApp('/artifacts');
      await screen.findByRole('list', { name: 'Artifacts' });
      expect(screen.getAllByRole('button', { name: 'Retire' })).toHaveLength(3);
      await user.click(await screen.findByRole('tab', { name: 'Awaiting review' }));
      expect(router.state.location.search).toBe('?state=draft');
      await vi.waitFor(() => expect(cards()).toHaveLength(1));
      const card = cards()[0]!;
      expect(within(card).getByText('Cloud cost board')).toBeInTheDocument();
      expect(within(card).getByText('Published by Sam Rivera · 31 Oct 2026')).toBeInTheDocument();
      await user.click(within(card).getByRole('button', { name: 'Approve' }));
      await vi.waitFor(() => expect(calls).toEqual(['approve art-4']));
      expect(await screen.findByText('Cloud cost board is published.')).toBeInTheDocument();
    });

    it('rejects one with a reason, which the Rejected tab then shows', async () => {
      let sent: unknown;
      server.use(
        asReviewer(),
        http.post(v1('/artifacts/:id/reject'), async ({ request }) => {
          sent = await request.json();
          return HttpResponse.json({ ...artifacts[3], state: 'rejected', reason: 'Too wide.' });
        }),
      );
      const { user } = renderApp('/artifacts?state=draft');
      await screen.findByRole('list', { name: 'Artifacts' });
      // The published cards stand in while the drafts load (placeholder data): wait for the draft's own button.
      await user.click(await screen.findByRole('button', { name: 'Reject' }));
      const dialog = await screen.findByRole('dialog', { name: 'Reject Cloud cost board?' });
      expect(within(dialog).getByRole('button', { name: 'Reject' })).toBeDisabled();
      await user.type(within(dialog).getByLabelText('Reason'), 'Too wide.');
      await user.click(within(dialog).getByRole('button', { name: 'Reject' }));
      await vi.waitFor(() => expect(sent).toEqual({ reason: 'Too wide.' }));
      expect(await screen.findByText('Cloud cost board is rejected.')).toBeInTheDocument();
      await user.click(screen.getByRole('tab', { name: 'Rejected' }));
      await vi.waitFor(() => expect(cards()).toHaveLength(1));
      expect(within(cards()[0]!).getByText('Rejected by Chris Timmerman: Names customers; use account ids.')).toBeInTheDocument();
    });

    it('retires a published one after confirming', async () => {
      const calls: string[] = [];
      server.use(
        asReviewer(),
        http.post(v1('/artifacts/:id/retire'), ({ params }) => {
          calls.push(`retire ${params.id}`);
          return HttpResponse.json({ ...artifacts[0], state: 'retired' });
        }),
      );
      const { user } = renderApp('/artifacts');
      await screen.findByRole('list', { name: 'Artifacts' });
      await user.click(within(cards()[0]!).getByRole('button', { name: 'Retire' }));
      const dialog = await screen.findByRole('dialog', { name: 'Retire Deploy failures?' });
      await user.click(within(dialog).getByRole('button', { name: 'Retire' }));
      await vi.waitFor(() => expect(calls).toEqual(['retire art-1']));
      expect(await screen.findByText('Deploy failures is retired.')).toBeInTheDocument();
    });

    it('shows the server’s refusal of a review', async () => {
      server.use(asReviewer(), http.post(v1('/artifacts/:id/approve'), () => apiError(409, 'E_CONFLICT', 'Cloud cost board is approved already.')));
      const { user } = renderApp('/artifacts?state=draft');
      await screen.findByRole('list', { name: 'Artifacts' });
      await user.click(await screen.findByRole('button', { name: 'Approve' }));
      expect(await screen.findByText('Cloud cost board is approved already.')).toBeInTheDocument();
    });

    it('ignores a review tab in the URL for a member', async () => {
      const asked: string[] = [];
      server.use(
        http.get(v1('/artifacts'), ({ request }) => {
          asked.push(new URL(request.url).searchParams.get('state') ?? '');
          return HttpResponse.json({ artifacts: [], page: 1, per_page: 24, total: 0 });
        }),
      );
      renderApp('/artifacts?state=draft');
      expect(await screen.findByText('Nothing published yet')).toBeInTheDocument();
      expect(asked).toEqual(['approved']);
    });
  });
});
