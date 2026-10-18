import { fireEvent, screen, within } from '@testing-library/react';
import { me, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, server, v1 } from '@/test/server';

const card = (name: string) => screen.getByRole('region', { name });

describe('Choosing a plan', () => {
  it('covers the window with no sidebar: the person, the X, and every plan with what it includes', async () => {
    renderApp('/settings/plans');
    expect(await screen.findByRole('heading', { name: 'Choose a plan' })).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'Main' })).not.toBeInTheDocument();
    expect(await screen.findByText('chris@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();

    const pro = await screen.findByRole('region', { name: 'Pro' });
    expect(within(pro).getByText('Current plan', { selector: 'span' })).toBeInTheDocument();
    expect(within(pro).getByRole('button', { name: 'Current plan' })).toBeDisabled();
    expect(within(pro).getByText('$8')).toBeInTheDocument();
    expect(within(pro).getByText('per seat / month')).toBeInTheDocument();
    expect(within(pro).getByText('1 member')).toBeInTheDocument();
    expect(within(pro).getByText('Up to 5 installs per person')).toBeInTheDocument();
    expect(within(pro).getByText('Ada: 3 models, 10,000 precedents')).toBeInTheDocument();

    expect(within(card('Free')).getByText('per month')).toBeInTheDocument();
    expect(within(card('Free')).getByText('Up to 1 install per person')).toBeInTheDocument();
    expect(within(card('Free')).getByRole('button', { name: 'Switch to Free' })).toBeInTheDocument();

    const team = card('Team');
    expect(within(team).getByText('Recommended')).toBeInTheDocument();
    expect(within(team).getByText('Unlimited members')).toBeInTheDocument();
    expect(within(team).getByText('Ada: unlimited models, unlimited precedents')).toBeInTheDocument();
    expect(within(team).getByRole('button', { name: 'Upgrade to Team' })).toBeInTheDocument();
  });

  it('names a mod with no limits, and unlimited installs', async () => {
    server.use(
      http.get(v1('/plans'), () =>
        HttpResponse.json([...plans.slice(0, 2), { ...plans[2], limits: { members: 5, installs: null }, mods: { ada: { limits: {} } } }]),
      ),
    );
    renderApp('/settings/plans');
    const team = await screen.findByRole('region', { name: 'Team' });
    expect(within(team).getByText('5 members')).toBeInTheDocument();
    expect(within(team).getByText('Unlimited installs per person')).toBeInTheDocument();
    expect(within(team).getByText('Ada')).toBeInTheDocument();
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

  it('sends an org without a subscription to Stripe’s checkout', async () => {
    const location = stubLocation();
    let body: unknown;
    server.use(
      http.get(v1('/me'), () =>
        HttpResponse.json({ ...me, plan: plans[0], org: { ...me.org, billing_status: 'none', renews_at: null }, used: { ...me.used, seats: 0 } }),
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
      expect(body).toEqual({ plan: 'Pro', seats: 1, addons: [] });
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
