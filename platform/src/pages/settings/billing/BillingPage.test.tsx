import { screen, within } from '@testing-library/react';
import { hostingOff, me, plans, rates } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

const free = { ...me, plan: plans[0]!, org: { ...me.org, billing_status: 'none', renews_at: null }, precedents: { used: 0, limit: 0 }, hosting: { month: '2026-10', month_to_date_cents: 0, machines: [] } };
const card = (name: string) => screen.findByRole('region', { name });

describe('Billing', () => {
  it('shows the plan: its flat price, renewal, what it includes and hosting this month', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByText('$99 / month')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.getByText('Renews 16 Nov 2026')).toBeInTheDocument();
    expect(screen.getAllByText('3 hosted machines')[0]).toBeInTheDocument();
    expect(screen.getAllByText('100,000 precedents on hosted machines')[0]).toBeInTheDocument();
    expect(screen.getByText('Hosting this month')).toBeInTheDocument();
    expect(screen.getByText('$12.17')).toBeInTheDocument();
    expect(screen.getByText(/Members and installs are unlimited on every plan/)).toBeInTheDocument();
    expect(screen.queryByText(/seat/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/add-on/i)).not.toBeInTheDocument();
  });

  it('offers the plans above this one: Upgrade for Team, Talk to us for Enterprise', async () => {
    const { user, router } = renderApp('/settings/billing');
    const team = await card('Team');
    expect(within(team).getByText('$299 / month')).toBeInTheDocument();
    expect(within(team).getByText('10 hosted machines')).toBeInTheDocument();
    expect(within(team).getByText('1,000,000 precedents on hosted machines')).toBeInTheDocument();
    const enterprise = await card('Enterprise');
    expect(within(enterprise).getByText('By contract')).toBeInTheDocument();
    expect(within(enterprise).getByText('Hosting rates: set in your contract.')).toBeInTheDocument();
    expect(within(enterprise).getByText('Unlimited hosted machines')).toBeInTheDocument();
    expect(within(enterprise).getByText('Offline licences for air-gapped runtimes')).toBeInTheDocument();
    for (const text of ['SSO and SAML', 'Roles', 'Audit logs']) expect(within(enterprise).getByText(text)).toBeInTheDocument();
    expect(within(enterprise).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(screen.queryByRole('region', { name: 'Free' })).not.toBeInTheDocument();
    await user.click(within(team).getByRole('button', { name: 'Upgrade' }));
    expect(router.state.location.pathname).toBe('/settings/plans');
  });

  it('shows the hosted machine rates of the plan in force, a month and a second', async () => {
    renderApp('/settings/billing');
    const table = await screen.findByRole('table', { name: 'Hosted machine rates' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Size', 'Pro']);
    const small = within(table).getByRole('row', { name: /^Small/ });
    expect(within(small).getByText('$8.71 / month')).toBeInTheDocument();
    expect(within(small).getByText('$0.0000034 / second')).toBeInTheDocument();
    expect(within(table).getByText('$117 / month')).toBeInTheDocument();
    expect(within(table).getByText('$0.20 / GB / month')).toBeInTheDocument();
    expect(await screen.findByText('Pro’s rates.')).toBeInTheDocument();
    expect(screen.getByText(/billed by the second while it runs/)).toBeInTheDocument();
    // Fly's own rates are never shown.
    expect(within(table).queryByText('$6.70 / month')).not.toBeInTheDocument();
  });

  it('on Free, offers every paid plan, shows Pro and Team’s rates, and says hosting is on them', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json(free)));
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Free' })).toBeInTheDocument();
    expect(screen.getAllByText('Free')).toHaveLength(2);
    expect(screen.getByText('No hosted machines')).toBeInTheDocument();
    expect(screen.queryByText('Hosting this month')).not.toBeInTheDocument();
    expect(await card('Pro')).toBeInTheDocument();
    expect(await screen.findByText('Hosting is on Pro and Team. Running rrotor yourself is free.')).toBeInTheDocument();
    const table = await screen.findByRole('table', { name: 'Hosted machine rates' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Size', 'Pro', 'Team']);
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

  it('is read-only for members who are not the admin, but anyone can talk to sales', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })));
    renderApp('/settings/billing');
    expect(await screen.findByText('Only your org’s admin can change this.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Manage' })).not.toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'Talk to us' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Upgrade' })).not.toBeInTheDocument();
  });

  it('on Enterprise, offers no plan above, and never shows a rate: the contract sets them', async () => {
    server.use(
      http.get(v1('/me'), () =>
        HttpResponse.json({ ...me, plan: plans[3], org: { ...me.org, renews_at: null, plan_until: '2027-10-01T00:00:00Z' }, precedents: { used: 5, limit: null } }),
      ),
    );
    renderApp('/settings/billing');
    expect(await screen.findByText('By contract')).toBeInTheDocument();
    expect(screen.getByText('Until 1 Oct 2027')).toBeInTheDocument();
    expect(screen.getByText('Hosting rates: set in your contract.')).toBeInTheDocument();
    expect(await screen.findByText('Enterprise’s rates: set in your contract.')).toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Hosted machine rates' })).not.toBeInTheDocument();
    expect(screen.queryByText(/\/ month/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Team' })).not.toBeInTheDocument();
  });

  it('offers every plan when the org’s plan is not among those listed, and a dash for a size without a rate', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: { ...plans[1], name: 'Legacy', interval: 'year' } })),
      http.get(v1('/rates'), () => HttpResponse.json({ ...rates, plans: { Legacy: { sizes: [rates.plans.Pro!.sizes[0]], volume_usd_per_gb_month: '0.20' } } })),
    );
    renderApp('/settings/billing');
    expect(await screen.findByText('$99 / year')).toBeInTheDocument();
    expect(await card('Free')).toBeInTheDocument();
    const table = await screen.findByRole('table', { name: 'Hosted machine rates' });
    expect(within(table).getAllByText('—')).toHaveLength(2);
    expect(within(table).getByText('$0.20 / GB / month')).toBeInTheDocument();
  });

  it('says so when Stripe sends the person back', async () => {
    renderApp('/billing?done=1');
    expect(await screen.findByText('Billing is up to date.')).toBeInTheDocument();
  });

  it('shows a refusal from the server', async () => {
    server.use(
      http.get(v1('/plans'), () => apiError(503, 'E_UNAVAILABLE', 'Billing is off.')),
      http.get(v1('/rates'), () => apiError(503, 'E_UNAVAILABLE', 'Rates are unavailable.')),
    );
    renderApp('/settings/billing');
    expect(await screen.findByText('Billing is off.')).toBeInTheDocument();
    expect(await screen.findByText('Rates are unavailable.')).toBeInTheDocument();
  });

  it('shows a payment that needs attention in place of the renewal', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, billing_status: 'past_due' } })));
    renderApp('/settings/billing');
    expect(await screen.findByText('Payment due')).toBeInTheDocument();
    expect(screen.queryByText(/^Renews/)).not.toBeInTheDocument();
  });
});

describe('Billing while Glyphh hosts nothing and some features are not built', () => {
  it('lists the plans as before, each feature not built as coming soon, never as included', async () => {
    server.use(...hostingOffHandlers());
    const { user, router } = renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Free' })).toBeInTheDocument();
    const pro = await card('Pro');
    expect(within(pro).getByText('$99 / month')).toBeInTheDocument();
    expect(within(pro).getByText('Coming soon: Sync across runtimes')).toBeInTheDocument();
    expect(within(pro).queryByText('Sync across runtimes')).not.toBeInTheDocument();
    expect(within(pro).getByText('Coming soon: 100,000 precedents in the synced store')).toBeInTheDocument();
    const enterprise = await card('Enterprise');
    expect(within(enterprise).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(within(enterprise).getByText('Offline licences for air-gapped runtimes')).toBeInTheDocument();
    for (const text of ['SSO and SAML', 'Roles', 'Audit logs', 'High availability']) {
      expect(within(enterprise).getByText(`Coming soon: ${text}`)).toBeInTheDocument();
      expect(within(enterprise).queryByText(text)).not.toBeInTheDocument();
    }
    await user.click(within(pro).getByRole('button', { name: 'Upgrade' }));
    expect(router.state.location.pathname).toBe('/settings/plans');
  });

  it('says nothing of hosting: no machines, no rates, no hosting this month', async () => {
    server.use(...hostingOffHandlers('empty'));
    renderApp('/settings/billing');
    await card('Enterprise');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText(/hosted machine/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/hosting/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Hosted machine rates' })).not.toBeInTheDocument();
  });

  it('shows an org on Pro no hosting this month', async () => {
    const pro = hostingOff.plans[1]!;
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: pro })), ...hostingOffHandlers());
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    await card('Team');
    expect(screen.queryByText('Hosting this month')).not.toBeInTheDocument();
  });
});
