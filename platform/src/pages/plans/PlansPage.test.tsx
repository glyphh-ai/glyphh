import { fireEvent, screen, within } from '@testing-library/react';
import { me, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, hostingOffHandlers, http, HttpResponse, server, v1 } from '@/test/server';

const card = (name: string) => screen.getByRole('region', { name });

describe('Choosing a plan', () => {
  it('covers the window with no sidebar: the person, the X, and every plan with what it includes', async () => {
    renderApp('/settings/plans');
    expect(await screen.findByRole('heading', { name: 'Choose a plan' })).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'Main' })).not.toBeInTheDocument();
    expect(await screen.findByText('chris@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
    expect(screen.getByText(/unlimited members, installs and self-hosted runtimes, with Ada included\. Never priced per seat\./)).toBeInTheDocument();

    const pro = await screen.findByRole('region', { name: 'Pro' });
    expect(within(pro).getByText('Current plan', { selector: 'span' })).toBeInTheDocument();
    expect(within(pro).getByRole('button', { name: 'Current plan' })).toBeDisabled();
    expect(within(pro).getByText('$99')).toBeInTheDocument();
    expect(within(pro).getByText('per month')).toBeInTheDocument();
    expect(within(pro).getByText('3 hosted machines')).toBeInTheDocument();
    expect(within(pro).getByText('100,000 precedents on hosted machines')).toBeInTheDocument();
    expect(within(pro).getByText('Sync across runtimes')).toBeInTheDocument();

    const free = card('Free');
    expect(within(free).getByText('$0')).toBeInTheDocument();
    expect(within(free).getByText('No hosted machines')).toBeInTheDocument();
    expect(within(free).queryByText(/precedents/)).not.toBeInTheDocument();
    expect(within(free).getByRole('button', { name: 'Switch to Free' })).toBeInTheDocument();

    const team = card('Team');
    expect(within(team).getByText('Recommended')).toBeInTheDocument();
    expect(within(team).getByText('$299')).toBeInTheDocument();
    expect(within(team).getByText('1,000,000 precedents on hosted machines')).toBeInTheDocument();
    expect(within(team).getByRole('button', { name: 'Upgrade to Team' })).toBeInTheDocument();

    const enterprise = card('Enterprise');
    expect(within(enterprise).getByText('By contract')).toBeInTheDocument();
    expect(within(enterprise).queryByText(/^per /)).not.toBeInTheDocument();
    expect(within(enterprise).getByText('Unlimited hosted machines')).toBeInTheDocument();
    expect(within(enterprise).getByText('Unlimited precedents on hosted machines')).toBeInTheDocument();
    expect(within(enterprise).getByText('High availability')).toBeInTheDocument();
    expect(within(enterprise).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(within(enterprise).queryByRole('button')).not.toBeInTheDocument();
  });

  it('shows the hosted machine rates of each plan with hosting, never Fly’s own, and Enterprise’s as set in the contract', async () => {
    renderApp('/settings/plans');
    const table = await screen.findByRole('table', { name: 'Hosted machine rates' });
    expect(within(table).getAllByRole('columnheader').map((th) => th.textContent)).toEqual(['Size', 'Pro', 'Team', 'Enterprise']);
    const medium = within(table).getByRole('row', { name: /^Medium/ });
    expect(within(medium).getAllByText('$33.01 / month')).toHaveLength(2);
    expect(within(medium).getByText('Set in your contract.')).toBeInTheDocument();
    expect(within(table).getAllByText('Set in your contract.')).toHaveLength(4);
    expect(within(table).queryByText('$25.39 / month')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Hosted machines' })).toBeInTheDocument();
  });

  it('shows a contract plan with a floor price as from that price a year, and a yearly self-serve plan', async () => {
    server.use(
      http.get(v1('/plans'), () =>
        HttpResponse.json([...plans.slice(0, 2), { ...plans[2], interval: 'year' }, { ...plans[3], price_cents: 1_000_000, interval: 'year' }]),
      ),
    );
    renderApp('/settings/plans');
    expect(within(await screen.findByRole('region', { name: 'Team' })).getByText('per year')).toBeInTheDocument();
    const enterprise = card('Enterprise');
    expect(within(enterprise).getByText('From $10,000')).toBeInTheDocument();
    expect(within(enterprise).getByText('per year')).toBeInTheDocument();
  });

  it('shows the server’s refusal when the rates cannot be read, and the plans still', async () => {
    server.use(http.get(v1('/rates'), () => apiError(503, 'E_UNAVAILABLE', 'Rates are unavailable.')));
    renderApp('/settings/plans');
    expect(await screen.findByText('Rates are unavailable.')).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Team' })).toBeInTheDocument();
  });

  it('closes with the X, and with Escape, back to billing', async () => {
    const { user, router } = renderApp('/settings/plans');
    await user.click(await screen.findByRole('button', { name: 'Close' }));
    expect(router.state.location.pathname).toBe('/settings/billing');
    await router.navigate('/settings/plans');
    await screen.findByRole('heading', { name: 'Choose a plan' });
    await user.keyboard('{Escape}');
    expect(router.state.location.pathname).toBe('/settings/billing');
  });

  it('switches at once with a subscription, after a confirm, and goes back to billing', async () => {
    let chosen: unknown;
    server.use(
      http.post(v1('/billing/plan'), async ({ request }) => {
        chosen = await request.json();
        return HttpResponse.json({});
      }),
    );
    const { user, router } = renderApp('/settings/plans');
    await user.click(await screen.findByRole('button', { name: 'Upgrade to Team' }));
    const dialog = screen.getByRole('dialog', { name: 'Switch to Team?' });
    await user.keyboard('{Escape}');
    expect(router.state.location.pathname).toBe('/settings/plans');
    await user.click(screen.getByRole('button', { name: 'Upgrade to Team' }));
    await user.click(within(dialog).getByRole('button', { name: 'Switch plan' }));
    await vi.waitFor(() => expect(chosen).toEqual({ plan: 'Team' }));
    await vi.waitFor(() => expect(router.state.location.pathname).toBe('/settings/billing'));
  });

  it('keeps the plan when the confirm is cancelled, and shows a refusal', async () => {
    let sent = 0;
    server.use(
      http.post(v1('/billing/plan'), () => {
        sent += 1;
        return apiError(409, 'E_CONFLICT', 'That plan cannot be chosen now.');
      }),
    );
    const { user } = renderApp('/settings/plans');
    await user.click(await screen.findByRole('button', { name: 'Switch to Free' }));
    const dialog = screen.getByRole('dialog', { name: 'Switch to Free?' });
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(sent).toBe(0);
    await user.click(screen.getByRole('button', { name: 'Switch to Free' }));
    await user.click(within(dialog).getByRole('button', { name: 'Switch plan' }));
    expect(await within(dialog).findByText('That plan cannot be chosen now.')).toBeInTheDocument();
    // Closed and opened again, the confirm starts clean.
    fireEvent.click(dialog);
    await user.click(screen.getByRole('button', { name: 'Switch to Free' }));
    expect(within(dialog).queryByText('That plan cannot be chosen now.')).not.toBeInTheDocument();
  });

  it('down to Free with hosted machines, says to delete them first, with the way to Machines', async () => {
    server.use(http.post(v1('/billing/plan'), () => apiError(409, 'E_CONFLICT', 'Delete your hosted machines first.', { reason: 'machines' })));
    const { user } = renderApp('/settings/plans');
    await user.click(await screen.findByRole('button', { name: 'Switch to Free' }));
    const dialog = screen.getByRole('dialog', { name: 'Switch to Free?' });
    await user.click(within(dialog).getByRole('button', { name: 'Switch plan' }));
    expect(await within(dialog).findByText('Delete your hosted machines first.')).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'Machines' })).toHaveAttribute('href', '/machines');
  });

  it('offers no move to Free without a subscription: there is nothing to cancel', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, billing_status: 'canceled', renews_at: null } })));
    renderApp('/settings/plans');
    expect(await within(await screen.findByRole('region', { name: 'Team' })).findByRole('button', { name: 'Upgrade to Team' })).toBeInTheDocument();
    expect(within(card('Free')).queryByRole('button')).not.toBeInTheDocument();
  });

  it('on a plan by contract, offers no change here: talk to us', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[3], org: { ...me.org, plan_until: '2027-10-01T00:00:00Z' } })));
    renderApp('/settings/plans');
    expect(await screen.findByText(/Your plan is by contract\. To change it,/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(screen.queryByRole('button', { name: /Switch to|Upgrade to/ })).not.toBeInTheDocument();
  });

  it('sends an org without a subscription to Stripe’s checkout', async () => {
    const location = stubLocation();
    let body: unknown;
    server.use(
      http.get(v1('/me'), () =>
        HttpResponse.json({ ...me, plan: plans[0], org: { ...me.org, billing_status: 'none', renews_at: null } }),
      ),
      http.post(v1('/billing/checkout'), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ url: 'https://checkout.stripe.test/c/1' });
      }),
    );
    try {
      const { user } = renderApp('/settings/plans');
      // The next plan up is the one recommended.
      expect(await within(await screen.findByRole('region', { name: 'Pro' })).findByText('Recommended')).toBeInTheDocument();
      expect(within(card('Team')).queryByText('Recommended')).not.toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Upgrade to Pro' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://checkout.stripe.test/c/1'));
      expect(body).toEqual({ plan: 'Pro' });
    } finally {
      location.restore();
    }
  });

  it('shows the checkout loading on the plan chosen, and a person with no name by their email', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, name: null, plan: plans[0], org: { ...me.org, billing_status: 'none', renews_at: null } })),
      http.post(v1('/billing/checkout'), () => new Promise<never>(() => {})),
    );
    const { user } = renderApp('/settings/plans');
    await user.click(await screen.findByRole('button', { name: 'Upgrade to Pro' }));
    await vi.waitFor(() => expect(within(card('Pro')).getByRole('button', { name: /Upgrade to Pro/ })).toBeDisabled());
    expect(within(card('Team')).getByRole('button', { name: 'Upgrade to Team' })).toBeEnabled();
    expect(screen.getByText('chris@example.com')).toBeInTheDocument();
  });

  it('is read-only for members who are not the admin', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })));
    renderApp('/settings/plans');
    expect(await screen.findByText('Only your org’s admin can change the plan.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Switch to|Upgrade to/ })).not.toBeInTheDocument();
  });

  it('shows the server’s refusal when the plans cannot be read', async () => {
    server.use(http.get(v1('/plans'), () => apiError(503, 'E_UNAVAILABLE', 'Plans are unavailable.')));
    renderApp('/settings/plans');
    expect(await screen.findByText('Plans are unavailable.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Pro' })).not.toBeInTheDocument();
  });
});

describe('Choosing a plan while Glyphh hosts nothing and some features are not built', () => {
  it('offers the plans as before, with each feature not built marked coming soon', async () => {
    server.use(...hostingOffHandlers());
    renderApp('/settings/plans');
    const pro = await screen.findByRole('region', { name: 'Pro' });
    expect(within(pro).getByText('$99')).toBeInTheDocument();
    expect(within(pro).getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument();
    expect(within(pro).getByText('Sync across runtimes').closest('li')).toHaveTextContent('Sync across runtimesComing soon');
    const enterprise = card('Enterprise');
    expect(within(enterprise).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(within(enterprise).getByText('Offline licences for air-gapped runtimes').closest('li')).not.toHaveTextContent('Coming soon');
    expect(within(enterprise).getByText('Audit logs').closest('li')).toHaveTextContent('Coming soon');
  });

  it('says nothing of hosted machines and shows no rates, and the rates refused is no error', async () => {
    server.use(...hostingOffHandlers());
    renderApp('/settings/plans');
    await screen.findByRole('region', { name: 'Enterprise' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText('Hosting is off.')).not.toBeInTheDocument();
    expect(screen.queryByText(/hosted machine/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Hosted machines' })).not.toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Hosted machine rates' })).not.toBeInTheDocument();
  });
});
