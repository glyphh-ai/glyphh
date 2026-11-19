import { screen, waitFor, within } from '@testing-library/react';
import * as fake from '@/test/admin';
import { staffHandlers, staffMe } from '@/test/admin';
import { renderApp } from '@/test/render';
import { http, HttpResponse, server, v1 } from '@/test/server';

function staff() {
  server.use(...staffHandlers());
}

/** Records what each matching write was sent, answering with `reply`. */
function recording(method: 'post' | 'delete', path: string, reply: unknown = { message: 'Done.' }) {
  const sent: unknown[] = [];
  server.use(
    http[method](v1(path), async ({ request }) => {
      sent.push(method === 'post' ? await request.json() : null);
      return reply === null ? new HttpResponse(null, { status: 204 }) : HttpResponse.json(reply);
    }),
  );
  return sent;
}

describe('Who sees the staff view', () => {
  it('opens it on the games for staff when they sign in, with its own sidebar', async () => {
    staff();
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Games' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/admin');
    const nav = screen.getByRole('complementary', { name: 'Main' });
    for (const name of ['All games', 'Free Fall Frank', 'Crabby Knife Fight', 'Bams & Brags', 'Send a Carol', 'Traffic', 'Log alerts', 'Audit log']) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument();
    }
    for (const name of ['Organisations', 'People', 'Plans', 'Marketing links', 'Ada versions', 'Infrastructure', 'Dashboard']) {
      expect(within(nav).queryByRole('link', { name })).not.toBeInTheDocument();
    }
    expect(screen.queryByText(/precedents/)).not.toBeInTheDocument();
  });

  it('sends anyone else home', async () => {
    const { router } = renderApp('/admin/games/frank');
    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
    expect(screen.queryByRole('link', { name: 'Staff view' })).not.toBeInTheDocument();
  });

  it('answers the retired screens’ addresses with Page not found', async () => {
    staff();
    renderApp('/admin/orgs');
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
  });
});

describe('Log alerts', () => {
  it('lists events, acknowledges one and every one shown', async () => {
    staff();
    const one = recording('post', '/admin/events/e1/ack', { acknowledged: 1 });
    const all = recording('post', '/admin/events/ack', { acknowledged: 4 });
    const { user } = renderApp('/admin/events');
    const table = await screen.findByRole('table', { name: 'Events' });
    expect(within(table).getByText('stripe call failed')).toBeInTheDocument();
    expect(within(table).getByText('Seen by support@glyphh.ai')).toBeInTheDocument();
    await user.click(within(table).getByRole('button', { name: 'Acknowledge' }));
    await waitFor(() => expect(one).toHaveLength(1));
    await user.selectOptions(screen.getByLabelText('Severity'), 'error');
    await user.click(screen.getByRole('button', { name: 'Acknowledge all shown' }));
    await waitFor(() => expect(all).toEqual([{ severity: 'error' }]));
    expect(await screen.findByText('4 acknowledged.')).toBeInTheDocument();
  });

  it('filters by kind and open only', async () => {
    staff();
    const asked: string[] = [];
    server.use(
      http.get(v1('/admin/events'), ({ request }) => {
        asked.push(new URL(request.url).search);
        return HttpResponse.json({ events: [], next_before: null });
      }),
    );
    const { user } = renderApp('/admin/events');
    expect(await screen.findByText('Nothing here')).toBeInTheDocument();
    await user.click(screen.getByRole('switch', { name: 'Open only' }));
    await user.type(screen.getByLabelText('Kind'), 'job');
    await waitFor(() => expect(asked.at(-1)).toBe('?kind=job'));
    expect(asked[0]).toBe('?open_only=true');
  });
});


describe('Audit log', () => {
  it('shows the audit log, filtered and paged', async () => {
    staff();
    const asked: string[] = [];
    server.use(
      http.get(v1('/admin/audit'), ({ request }) => {
        asked.push(new URL(request.url).search);
        return HttpResponse.json(fake.audit);
      }),
    );
    const { user } = renderApp('/admin/audit');
    expect(await screen.findByRole('table', { name: 'Audit log' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('Staff member'), 'support@glyphh.ai');
    await user.click(screen.getByRole('button', { name: 'Filter' }));
    await user.click(await screen.findByRole('button', { name: 'Older' }));
    await waitFor(() => expect(asked.at(-1)).toBe('?by=support%40glyphh.ai&before=2026-10-23T09%3A00%3A00Z'));
  });
});

describe('helpers', () => {
  it('keeps the staff flag on /v1/me', () => {
    expect(staffMe.staff).toBe(true);
  });
});
