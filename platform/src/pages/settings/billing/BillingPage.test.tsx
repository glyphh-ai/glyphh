import { fireEvent, screen, within } from '@testing-library/react';
import { addons, me, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

describe('Billing', () => {
  it('shows the plan, seats, renewal and runtime hours', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByText('$8 / seat / month · 1 seat')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.getByText('Renews 16 Nov 2026')).toBeInTheDocument();
    expect(await screen.findByRole('progressbar', { name: 'Runtime hours used this month' })).toHaveAttribute('aria-valuemax', '50');
  });

  it('shows each add-on with its price, limits on this plan and whether it is on', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByText('$4 / seat / month')).toBeInTheDocument();
    expect(screen.getByText('3 models · 10,000 precedents on Pro')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Ada add-on' })).toBeChecked();
  });

  it('offers the plans above this one', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByText('$16 / seat / month')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Team' })).toBeInTheDocument();
    expect(screen.getByText('Unlimited members')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Free' })).not.toBeInTheDocument();
  });

  it('quotes the prorated amount before removing an add-on, then removes it at that date', async () => {
    let removed = '';
    server.use(
      http.post(v1('/billing/addons/preview'), async ({ request }) => {
        expect(await request.json()).toEqual({ mod: 'ada', action: 'remove' });
        return HttpResponse.json({ mod: 'ada', action: 'remove', prorated_cents: -207, currency: 'usd', monthly_cents: 0, proration_date: 1792000000 });
      }),
      http.delete(v1('/billing/addons/:mod'), ({ request, params }) => {
        removed = `${params.mod}@${new URL(request.url).searchParams.get('proration_date')}`;
        return HttpResponse.json([{ ...addons[0], added: false }]);
      }),
    );
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('switch', { name: 'Ada add-on' }));
    const dialog = screen.getByRole('dialog', { name: 'Remove Ada' });
    expect(await within(dialog).findByText('$2.07 credit')).toBeInTheDocument();
    expect(within(dialog).getByText('$0 a month')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Remove' }));
    await vi.waitFor(() => expect(removed).toBe('ada@1792000000'));
  });

  it('changes plan at once with a subscription', async () => {
    let chosen: unknown;
    server.use(
      http.post(v1('/billing/plan'), async ({ request }) => {
        chosen = await request.json();
        return HttpResponse.json({});
      }),
    );
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Upgrade' }));
    const dialog = screen.getByRole('dialog', { name: 'Change plan' });
    expect(within(dialog).getByRole('radio', { name: /Team/ })).toBeChecked();
    await user.click(within(dialog).getByRole('button', { name: 'Change plan' }));
    await vi.waitFor(() => expect(chosen).toEqual({ plan: 'Team' }));
  });

  it('sends a Free org to Stripe’s checkout to upgrade', async () => {
    const location = stubLocation();
    let body: unknown;
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: { ...me.plan, name: 'Free', seat_price_cents: 0 }, org: { ...me.org, billing_status: 'none', renews_at: null } })),
      http.post(v1('/billing/checkout'), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ url: 'https://checkout.stripe.test/c/1' });
      }),
    );
    try {
      const { user } = renderApp('/settings/billing');
      expect(await screen.findByRole('heading', { name: 'Free' })).toBeInTheDocument();
      await user.click(screen.getAllByRole('button', { name: 'Upgrade' })[0]!);
      await user.click(within(screen.getByRole('dialog', { name: 'Change plan' })).getByRole('button', { name: 'Continue to Stripe' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://checkout.stripe.test/c/1'));
      expect(body).toEqual({ plan: 'Pro', seats: 1, addons: [] });
    } finally {
      location.restore();
    }
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

  it('changes seats, never below those taken', async () => {
    let seats: unknown;
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, seats: 3 }, used: { ...me.used, seats: 2 } })),
      http.post(v1('/billing/seats'), async ({ request }) => {
        seats = await request.json();
        return HttpResponse.json({});
      }),
    );
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Manage' }));
    await user.click(screen.getByRole('menuitem', { name: 'Change seats' }));
    const dialog = screen.getByRole('dialog', { name: 'Change seats' });
    const field = within(dialog).getByLabelText('Seats');
    await user.clear(field);
    await user.type(field, '1');
    expect(within(dialog).getByText('At least 2, the seats already taken.')).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Save' })).toBeDisabled();
    await user.clear(field);
    await user.type(field, '5');
    await user.click(within(dialog).getByRole('button', { name: 'Save' }));
    await vi.waitFor(() => expect(seats).toEqual({ seats: 5 }));
  });

  it('is read-only for members who are not the admin', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })));
    renderApp('/settings/billing');
    expect(await screen.findByText('Only your org’s admin can change this.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Change plan' })).not.toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Ada add-on' })).toBeDisabled();
  });

  it('says so when Stripe sends the person back', async () => {
    renderApp('/billing?done=1');
    expect(await screen.findByText('Billing is up to date.')).toBeInTheDocument();
  });

  it('shows a refusal from the server', async () => {
    server.use(http.get(v1('/addons'), () => apiError(503, 'E_UNAVAILABLE', 'Billing is off.')));
    renderApp('/settings/billing');
    expect(await screen.findByText('Billing is off.')).toBeInTheDocument();
  });

  it('shows a payment that needs attention in place of the renewal', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, billing_status: 'past_due' } })));
    renderApp('/settings/billing');
    expect(await screen.findByText('Payment due')).toBeInTheDocument();
    expect(screen.queryByText(/^Renews/)).not.toBeInTheDocument();
  });

  it('describes each add-on’s price and limits as the server gives them', async () => {
    server.use(
      http.get(v1('/addons'), () =>
        HttpResponse.json([
          { ...addons[0], mod: 'ada', name: 'Ada', limits: { models: null, precedents: 10000 } },
          { ...addons[0], mod: 'drip', name: 'Drip', per_seat: false, price_cents: 200, limits: null, added: false },
          { ...addons[0], mod: 'games', name: 'Games', limits: {}, added: false, allowed: false },
        ]),
      ),
    );
    renderApp('/settings/billing');
    expect(await screen.findByText('unlimited models · 10,000 precedents on Pro')).toBeInTheDocument();
    expect(screen.getByText('$2 / month')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Drip add-on' })).toBeEnabled();
    expect(screen.getByText('Not available on Pro')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: 'Games add-on' })).toBeDisabled();
    expect(screen.getAllByText(/ on Pro$/)).toHaveLength(2);
  });

  it('quotes the prorated amount before adding an add-on, then adds it at that date', async () => {
    let added: unknown;
    server.use(
      http.get(v1('/addons'), () => HttpResponse.json([{ ...addons[0], added: false }])),
      http.post(v1('/billing/addons/preview'), async ({ request }) => {
        expect(await request.json()).toEqual({ mod: 'ada', action: 'add' });
        return HttpResponse.json({ mod: 'ada', action: 'add', prorated_cents: 207, currency: 'usd', monthly_cents: 400, proration_date: 1792000000 });
      }),
      http.post(v1('/billing/addons'), async ({ request }) => {
        added = await request.json();
        return HttpResponse.json([{ ...addons[0], added: true }]);
      }),
    );
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('switch', { name: 'Ada add-on' }));
    const dialog = screen.getByRole('dialog', { name: 'Add Ada' });
    expect(await within(dialog).findByText('$2.07')).toBeInTheDocument();
    expect(within(dialog).getByText('$4 a month')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Add' }));
    await vi.waitFor(() => expect(added).toEqual({ mod: 'ada', proration_date: 1792000000 }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('sends an org without a subscription to Stripe’s checkout to add an add-on', async () => {
    const location = stubLocation();
    let body: unknown;
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, billing_status: 'canceled', seats: 0 } })),
      http.get(v1('/addons'), () => HttpResponse.json([{ ...addons[0], added: false }])),
      http.post(v1('/billing/checkout'), async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ url: 'https://checkout.stripe.test/c/2' });
      }),
    );
    try {
      const { user } = renderApp('/settings/billing');
      await user.click(await screen.findByRole('switch', { name: 'Ada add-on' }));
      const dialog = screen.getByRole('dialog', { name: 'Add Ada' });
      expect(within(dialog).queryByText('Now')).not.toBeInTheDocument();
      await user.click(within(dialog).getByRole('button', { name: 'Continue to Stripe' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://checkout.stripe.test/c/2'));
      expect(body).toEqual({ plan: 'Pro', seats: 1, addons: ['ada'] });
    } finally {
      location.restore();
    }
  });

  it('closes the add-on dialog on Cancel without changing anything', async () => {
    server.use(http.post(v1('/billing/addons/preview'), () => HttpResponse.json({ mod: 'ada', action: 'remove', prorated_cents: -207, currency: 'usd', monthly_cents: 0, proration_date: 1 })));
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('switch', { name: 'Ada add-on' }));
    await user.click(within(screen.getByRole('dialog', { name: 'Remove Ada' })).getByRole('button', { name: 'Cancel' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('changes plan from the plan card, starting on the current plan', async () => {
    let chosen: unknown;
    server.use(
      http.get(v1('/plans'), () => HttpResponse.json([...plans.slice(0, 2), { ...plans[2], limits: { members: 5, installs: 10 } }])),
      http.post(v1('/billing/plan'), async ({ request }) => {
        chosen = await request.json();
        return HttpResponse.json({});
      }),
    );
    const { user } = renderApp('/settings/billing');
    expect(await screen.findByText('5 members')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Change plan' }));
    const dialog = screen.getByRole('dialog', { name: 'Change plan' });
    expect(within(dialog).getByRole('radio', { name: /^Pro\s*· your plan/ })).toBeChecked();
    expect(within(dialog).getByRole('button', { name: 'Change plan' })).toBeDisabled();
    await user.click(within(dialog).getByRole('radio', { name: /^Free/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Change plan' }));
    await vi.waitFor(() => expect(chosen).toEqual({ plan: 'Free' }));
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('cannot change plan while the plans cannot be read', async () => {
    server.use(http.get(v1('/plans'), () => apiError(503, 'E_UNAVAILABLE', 'Plans are unavailable.')));
    const { user } = renderApp('/settings/billing');
    expect(await screen.findByText('Plans are unavailable.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Change plan' }));
    const dialog = screen.getByRole('dialog', { name: 'Change plan' });
    expect(within(dialog).queryByRole('radio')).not.toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Change plan' })).toBeDisabled();
  });

  it('does not send too few seats, even if the form is submitted', async () => {
    let sent = false;
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, seats: 3 }, used: { ...me.used, seats: 2 } })),
      http.post(v1('/billing/seats'), () => {
        sent = true;
        return HttpResponse.json({});
      }),
    );
    const { user } = renderApp('/settings/billing');
    await user.click(await screen.findByRole('button', { name: 'Manage' }));
    await user.click(screen.getByRole('menuitem', { name: 'Change seats' }));
    const field = within(screen.getByRole('dialog', { name: 'Change seats' })).getByLabelText('Seats');
    await user.clear(field);
    await user.type(field, '1');
    fireEvent.submit(field.closest('form')!);
    expect(screen.getByRole('dialog', { name: 'Change seats' })).toBeInTheDocument();
    expect(sent).toBe(false);
  });
});
