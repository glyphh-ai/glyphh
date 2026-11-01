import { screen, within } from '@testing-library/react';
import { me, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, onFreeHandlers, server, v1 } from '@/test/server';

const free = { ...me, plan: plans[0]!, org: { ...me.org, billing_status: 'none', renews_at: null }, precedents: { used: 0, limit: 0 } };

describe('Billing', () => {
  it('shows the plan: its flat price, renewal and what it includes', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByText('$99 / month')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.getByText('Renews 16 Nov 2026')).toBeInTheDocument();
    expect(screen.getAllByText('3 runtime nodes')[0]).toBeInTheDocument();
    expect(screen.getAllByText('50,000 precedents per node')[0]).toBeInTheDocument();
    expect(screen.getByText(/Members and installs are unlimited on every plan/)).toBeInTheDocument();
    expect(screen.queryByText(/seat/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/add-on/i)).not.toBeInTheDocument();
  });

  it('says nothing of hosting: Glyphh hosts no runtime, so no machines, rates or hosting this month', async () => {
    renderApp('/settings/billing');
    await screen.findByRole('heading', { name: 'Pro' });
    expect(screen.queryByText(/hosting|hosted machine/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('lists no other plan: they are on Manage, Change plan', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    for (const name of ['Free', 'Team', 'Enterprise']) expect(screen.queryByRole('region', { name })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upgrade' })).not.toBeInTheDocument();
    expect(screen.queryByText('$299 / month')).not.toBeInTheDocument();
  });

  it('on Free, shows the plan and its one runtime node', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json(free)));
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Free' })).toBeInTheDocument();
    expect(screen.getByText('1 runtime node')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Pro' })).not.toBeInTheDocument();
  });

  it('opens the plans from Manage', async () => {
    const { user, router } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Manage' }));
    await user.click(screen.getByRole('menuitem', { name: 'Change plan' }));
    expect(router.state.location.pathname).toBe('/settings/plans');
  });

  it('offers only Change plan in Manage on Free, without a subscription', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json(free)));
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Manage' }));
    const menu = screen.getByRole('menu', { name: 'Manage billing' });
    expect(within(menu).getAllByRole('menuitem').map((item) => item.textContent)).toEqual(['Change plan']);
  });

  it('opens the billing portal from Manage', async () => {
    const location = stubLocation();
    server.use(http.post(v1('/billing/portal'), () => HttpResponse.json({ url: 'https://billing.stripe.test/p/1' })));
    try {
      const { user } = renderApp('/settings/billing');
      await user.click(await screen.findByRole('button', { name: 'Manage' }));
      await user.click(screen.getByRole('menuitem', { name: 'Invoices and payment' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://billing.stripe.test/p/1'));
    } finally {
      location.restore();
    }
  });

  it('is read-only for members who are not the admin', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })));
    renderApp('/settings/billing');
    expect(await screen.findByText('Only your org’s admin can change this.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Manage' })).not.toBeInTheDocument();
  });

  it('on Enterprise, shows the contract’s end and no price', async () => {
    server.use(
      http.get(v1('/me'), () =>
        HttpResponse.json({ ...me, plan: plans[4], org: { ...me.org, renews_at: null, plan_until: '2027-10-01T00:00:00Z' }, precedents: { used: 5, limit: null } }),
      ),
    );
    renderApp('/settings/billing');
    expect(await screen.findByText('By contract')).toBeInTheDocument();
    expect(screen.getByText('Until 1 Oct 2027')).toBeInTheDocument();
    expect(screen.queryByText(/\/ month/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Team' })).not.toBeInTheDocument();
  });

  it('shows a plan not among those listed', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: { ...plans[2], name: 'Legacy', interval: 'year' } })));
    renderApp('/settings/billing');
    expect(await screen.findByText('$99 / year')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Legacy' })).toBeInTheDocument();
  });

  it('says so when Stripe sends the person back', async () => {
    renderApp('/billing?done=1');
    expect(await screen.findByText('Billing is up to date.')).toBeInTheDocument();
  });

  it('shows a refusal from the server', async () => {
    server.use(http.get(v1('/plans'), () => apiError(503, 'E_UNAVAILABLE', 'Billing is off.')));
    renderApp('/settings/billing');
    expect(await screen.findByText('Billing is off.')).toBeInTheDocument();
  });

  it('shows a payment that needs attention in place of the renewal', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, billing_status: 'past_due' } })));
    renderApp('/settings/billing');
    expect(await screen.findByText('Payment due')).toBeInTheDocument();
    expect(screen.queryByText(/^Renews/)).not.toBeInTheDocument();
  });
});

describe('Billing on Free while some features are not built', () => {
  it('shows the plan alone, and the plans from Manage, Change plan', async () => {
    server.use(...onFreeHandlers());
    const { user, router } = renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Free' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Pro' })).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Manage' }));
    await user.click(screen.getByRole('menuitem', { name: 'Change plan' }));
    expect(router.state.location.pathname).toBe('/settings/plans');
  });
});
