import { screen, waitFor, within } from '@testing-library/react';
import * as fake from '@/test/admin';
import { staffHandlers, staffMe } from '@/test/admin';
import { renderApp } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';
import { taggedUrl } from './pages/MarketingPage';
import { bytes } from './parts';

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
  it('opens it for staff when they sign in, with its own sidebar', async () => {
    staff();
    const { router } = renderApp('/');
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe('/admin');
    const nav = screen.getByRole('complementary', { name: 'Main' });
    for (const name of ['Infrastructure', 'Log alerts', 'Organisations', 'People', 'Plans', 'Marketing links', 'Ada versions', 'Audit log']) {
      expect(within(nav).getByRole('link', { name })).toBeInTheDocument();
    }
    expect(screen.getByText(/Never a customer’s precedents, cases, specs or uploaded files/)).toBeInTheDocument();
  });

  it('lets staff switch to their own org, and back from its sidebar', async () => {
    staff();
    const { user, router } = renderApp('/admin');
    await user.click(await screen.findByRole('button', { name: 'Your org’s view' }));
    // Home, which with Ada Cloud off is Runtimes.
    await waitFor(() => expect(router.state.location.pathname).toBe('/runtimes'));
    expect(sessionStorage.getItem('glyphh.view')).toBe('org');
    await user.click(await screen.findByRole('link', { name: 'Staff view' }));
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(sessionStorage.getItem('glyphh.view')).toBeNull();
  });

  it('sends anyone else home', async () => {
    const { router } = renderApp('/admin/orgs');
    await waitFor(() => expect(router.state.location.pathname).toBe('/'));
    expect(screen.queryByRole('link', { name: 'Staff view' })).not.toBeInTheDocument();
  });
});

describe('Dashboard', () => {
  it('shows the alerts first, then totals, revenue and the plan mix', async () => {
    staff();
    renderApp('/admin');
    const alerts = await screen.findByRole('list', { name: 'Alerts' });
    expect(within(alerts).getByText('The minute tick last ran 9 minutes ago.')).toBeInTheDocument();
    expect(within(alerts).getByText('Critical')).toBeInTheDocument();
    expect(await screen.findByText('$12,345')).toBeInTheDocument();
    expect(screen.getByText('41 paying, 3 on contract')).toBeInTheDocument();
    expect(screen.getByText('1,234,567')).toBeInTheDocument();
    const mix = screen.getByRole('table', { name: 'Plan mix' });
    expect(within(mix).getByText('$3,762')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Sign-ups by day' })).toBeInTheDocument();
  });

  it('asks again for another period, and says when every threshold is clear', async () => {
    staff();
    const asked: string[] = [];
    server.use(
      http.get(v1('/admin/dashboard'), ({ request }) => {
        asked.push(new URL(request.url).searchParams.get('days')!);
        return HttpResponse.json(fake.dashboard);
      }),
      http.get(v1('/admin/infra'), () => HttpResponse.json({ ...fake.infra, alerts: [] })),
    );
    const { user } = renderApp('/admin');
    expect(await screen.findByText('No alerts: every threshold is clear.')).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Period'), '7');
    await waitFor(() => expect(asked).toEqual(['30', '7']));
  });

  it('shows the server’s refusal', async () => {
    staff();
    server.use(http.get(v1('/admin/dashboard'), () => apiError(403, 'E_FORBIDDEN', 'This is for Glyphh’s staff, signed in on the platform.')));
    renderApp('/admin');
    expect(await screen.findByText('This is for Glyphh’s staff, signed in on the platform.')).toBeInTheDocument();
  });
});

describe('Infrastructure', () => {
  it('shows queues, workers, latency, routes, jobs and Postgres', async () => {
    staff();
    renderApp('/admin/infra');
    const queues = await screen.findByRole('table', { name: 'Queues' });
    expect(within(queues).getByText('0 of 2')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Requests by route' })).getByText('POST /v1/models/{name}/decide')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Jobs' })).getByText('5 min')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Largest tables' })).getByText('500 MB')).toBeInTheDocument();
    expect(screen.getByText('48 ms')).toBeInTheDocument();
    expect(screen.getByText('1.0% 5xx')).toBeInTheDocument();
    expect(screen.getByText('12 of 100 connections')).toBeInTheDocument();
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

describe('Organisations', () => {
  it('lists orgs with their plan, use and source; searches and pages', async () => {
    staff();
    const asked: string[] = [];
    server.use(
      http.get(v1('/admin/orgs'), ({ request }) => {
        asked.push(new URL(request.url).search);
        return HttpResponse.json({ ...fake.orgs, offset: Number(new URL(request.url).searchParams.get('offset') ?? 0) });
      }),
    );
    const { user } = renderApp('/admin/orgs');
    const table = await screen.findByRole('table', { name: 'Organisations' });
    expect(within(table).getByRole('link', { name: 'Acme' })).toHaveAttribute('href', '/admin/orgs/o-acme');
    expect(within(table).getByText('reddit / cpc')).toBeInTheDocument();
    expect(within(table).getByText('Suspended')).toBeInTheDocument();
    expect(within(table).getByText('Untagged')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Search'), 'acme');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(asked.at(-1)).toBe('?q=acme&offset=0&limit=50'));
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(asked.at(-1)).toBe('?q=acme&offset=50&limit=50'));
    expect(screen.getByText('51 to 100 of 120')).toBeInTheDocument();
  });
});

describe('One organisation', () => {
  it('shows its account, members, use and models as metadata', async () => {
    staff();
    renderApp('/admin/orgs/o-acme');
    expect(await screen.findByRole('heading', { name: 'Acme' })).toBeInTheDocument();
    expect(screen.getByText('utm_source=reddit, utm_medium=cpc')).toBeInTheDocument();
    expect(screen.getByText('sub_acme')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Members' })).getByText('ada@acme.test')).toBeInTheDocument();
    const models = screen.getByRole('table', { name: 'Models' });
    expect(within(models).getByText('ada-1-0 (kernel 3.12.2)')).toBeInTheDocument();
    expect(within(models).getByText('Deleted')).toBeInTheDocument();
    expect(screen.getByText('1 jobs in the last 7 days, 1 failed.')).toBeInTheDocument();
    expect(screen.getByText(/support@glyphh.ai: adminOrg \(ok\)/)).toBeInTheDocument();
  });

  it('changes its plan version', async () => {
    staff();
    const sent = recording('post', '/admin/orgs/o-acme/plan', { message: 'Moved from Pro v2 to Pro v1.' });
    const { user } = renderApp('/admin/orgs/o-acme');
    await user.click(await screen.findByRole('button', { name: 'Change plan version' }));
    const dialog = screen.getByRole('dialog', { name: 'Change plan version' });
    await user.selectOptions(within(dialog).getByLabelText('Plan version'), 'pv-pro-1');
    await user.click(within(dialog).getByRole('button', { name: 'Change' }));
    await waitFor(() => expect(sent).toEqual([{ plan_version_id: 'pv-pro-1' }]));
    expect(await screen.findByText('Moved from Pro v2 to Pro v1.')).toBeInTheDocument();
  });

  it('suspends it with a reason, and shows a refusal', async () => {
    staff();
    server.use(http.post(v1('/admin/orgs/o-acme/suspend'), () => apiError(409, 'E_CONFLICT', 'You can’t suspend your own org.')));
    const { user } = renderApp('/admin/orgs/o-acme');
    await user.click(await screen.findByRole('button', { name: 'Suspend' }));
    const dialog = screen.getByRole('dialog', { name: 'Suspend Acme' });
    const confirm = within(dialog).getByRole('button', { name: 'Suspend' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText('Reason'), 'card fraud');
    await user.click(confirm);
    expect(await within(dialog).findByText('You can’t suspend your own org.')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('grants Enterprise on a deal’s subscription', async () => {
    staff();
    const sent = recording('post', '/admin/orgs/o-acme/enterprise', { message: 'Acme is on Enterprise through 2027-10-31.' });
    const { user } = renderApp('/admin/orgs/o-acme');
    await user.click(await screen.findByRole('button', { name: 'Grant Enterprise' }));
    const dialog = screen.getByRole('dialog', { name: 'Grant Enterprise' });
    await user.type(within(dialog).getByLabelText('Last day'), '2027-10-31');
    await user.type(within(dialog).getByLabelText('Stripe subscription'), 'sub_deal');
    await user.click(within(dialog).getByRole('button', { name: 'Grant' }));
    await waitFor(() => expect(sent).toEqual([{ until: '2027-10-31', subscription: 'sub_deal' }]));
    expect(await screen.findByText('Acme is on Enterprise through 2027-10-31.')).toBeInTheDocument();
  });

  it('revokes Enterprise and lifts a suspension', async () => {
    staff();
    const ent = fake.org;
    server.use(
      http.get(v1('/admin/orgs/:id'), () =>
        HttpResponse.json({ ...ent, account: { ...ent.account, plan: 'Enterprise', suspended_at: '2026-10-22T00:00:00Z', suspended_reason: 'fraud' } }),
      ),
    );
    const revoked = recording('delete', '/admin/orgs/o-acme/enterprise', { message: 'Acme is on Free.' });
    const lifted = recording('delete', '/admin/orgs/o-acme/suspend', null);
    const { user } = renderApp('/admin/orgs/o-acme');
    expect(await screen.findByText('fraud')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Revoke Enterprise' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Revoke Enterprise' })).getByRole('button', { name: 'Revoke' }));
    await waitFor(() => expect(revoked).toHaveLength(1));
    await user.click(await screen.findByRole('button', { name: 'Lift suspension' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Lift the suspension' })).getByRole('button', { name: 'Lift' }));
    await waitFor(() => expect(lifted).toHaveLength(1));
    expect(await screen.findByText('Acme is no longer suspended.')).toBeInTheDocument();
  });
});

describe('People, plans, marketing, Ada versions and the audit log', () => {
  it('lists people with their org and sign-in', async () => {
    staff();
    renderApp('/admin/users');
    const table = await screen.findByRole('table', { name: 'People' });
    expect(within(table).getByRole('link', { name: 'Acme' })).toHaveAttribute('href', '/admin/orgs/o-acme');
    expect(within(table).getByText('Never')).toBeInTheDocument();
  });

  it('lists each plan’s versions with their caps, prices and orgs', async () => {
    staff();
    renderApp('/admin/plans');
    const pro = await screen.findByRole('table', { name: 'Pro versions' });
    expect(within(pro).getByText('price_pro_2')).toBeInTheDocument();
    expect(within(pro).getByText('Newest')).toBeInTheDocument();
    expect(within(screen.getByRole('table', { name: 'Enterprise versions' })).getByText('By contract')).toBeInTheDocument();
  });

  it('shows sign-ups by source and builds a tagged link', async () => {
    staff();
    const { user } = renderApp('/admin/marketing');
    const table = await screen.findByRole('table', { name: 'Sign-ups by source' });
    expect(within(table).getByText('17%')).toBeInTheDocument();
    await user.type(screen.getByLabelText('Source'), 'Reddit');
    await user.type(screen.getByLabelText('Campaign'), 'Launch Week');
    expect(screen.getByText('https://glyphh.ai/?utm_source=reddit&utm_campaign=launch-week')).toBeInTheDocument();
  });

  it('shows models by Ada version, before Ada versions too', async () => {
    staff();
    renderApp('/admin/ada-versions');
    expect(await screen.findByText('Before Ada versions')).toBeInTheDocument();
    expect(screen.getByText(/No model names its Ada version yet/)).toBeInTheDocument();
  });

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
  it('makes tagged glyphh.ai links', () => {
    expect(taggedUrl({ path: 'code', source: ' Google ', medium: 'cpc', campaign: '', content: '' })).toBe('https://glyphh.ai/code?utm_source=google&utm_medium=cpc');
    expect(taggedUrl({ path: '/', source: '', medium: '', campaign: '', content: '' })).toBe('https://glyphh.ai/');
  });

  it('writes sizes short', () => {
    expect([bytes(512), bytes(1536), bytes(52_428_800)]).toEqual(['512 B', '1.5 KB', '50 MB']);
  });

  it('keeps the staff flag on /v1/me', () => {
    expect(staffMe.staff).toBe(true);
  });
});
