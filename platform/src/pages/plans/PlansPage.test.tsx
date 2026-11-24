import { fireEvent, screen, within } from '@testing-library/react';
import { adaPlans, llmModels, llmPlans, me, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, llmHandlers, onFreeHandlers, server, v1 } from '@/test/server';

const card = (name: string) => screen.getByRole('region', { name });

describe('Plans with Glyphh’s hosted models', () => {
  it('shows each plan’s tokens a month and the models’ rates in dollars per million tokens', async () => {
    server.use(...llmHandlers());
    renderApp('/settings/plans');
    expect(await within(await screen.findByRole('region', { name: 'Free' })).findByText('250,000 tokens a month')).toBeInTheDocument();
    expect(within(card('Pro')).getByText('25,000,000 tokens a month')).toBeInTheDocument();
    expect(within(card('Team')).getByText('100,000,000 tokens a month')).toBeInTheDocument();
    expect(within(card('Enterprise')).getByText('Tokens a month by contract')).toBeInTheDocument();

    const rates = screen.getByRole('table', { name: 'Model rates' });
    const row = within(rates).getByText('adaL 34B 1.0').closest('tr')!;
    expect(within(row).getAllByRole('cell').slice(1).map((cell) => cell.textContent)).toEqual(['32,768 tokens', '$0.60', '$2.40']);
    expect(within(row).getByText('Beta')).toBeInTheDocument();
    expect(screen.queryByText(/credit/i)).not.toBeInTheDocument();
  });

  it('reads the rates from the registry when the plans do not carry them', async () => {
    server.use(
      http.get(v1('/plans'), () => HttpResponse.json(llmPlans.plans)),
      http.get(v1('/llm/models'), () => HttpResponse.json({ models: llmModels })),
    );
    renderApp('/settings/plans');
    expect(await screen.findByRole('table', { name: 'Model rates' })).toBeInTheDocument();
  });

  it('shows no tokens or rates while hosted models are off', async () => {
    renderApp('/settings/plans');
    expect(await screen.findByRole('region', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.queryByText(/tokens a month/)).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Hosted model rates' })).not.toBeInTheDocument();
  });
});

describe('Choosing a plan', () => {
  it('covers the window with no sidebar: the person, the X, and every plan with what it includes', async () => {
    server.use(http.get(v1('/plans'), () => HttpResponse.json(adaPlans)));
    renderApp('/settings/plans');
    expect(await screen.findByRole('heading', { name: 'Choose a plan' })).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'Main' })).not.toBeInTheDocument();
    expect(await screen.findByText('chris@example.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
    expect(screen.getByText('Every plan has unlimited members, installs, models and keys. Never priced per seat.')).toBeInTheDocument();

    const pro = await screen.findByRole('region', { name: 'Pro' });
    expect(within(pro).getByText('Current plan', { selector: 'span' })).toBeInTheDocument();
    expect(within(pro).getByRole('button', { name: 'Current plan' })).toBeDisabled();
    expect(within(pro).getByText('$99')).toBeInTheDocument();
    expect(within(pro).getByText('per month')).toBeInTheDocument();
    expect(within(pro).getByText('100,000 precedents')).toBeInTheDocument();
    expect(within(pro).getByText('1,000,000 requests a month')).toBeInTheDocument();

    const free = card('Free');
    expect(within(free).getByText('$0')).toBeInTheDocument();
    expect(within(free).getByText('1,000 precedents')).toBeInTheDocument();
    expect(within(free).getByRole('button', { name: 'Switch to Free' })).toBeInTheDocument();

    const basic = card('Basic');
    expect(within(basic).getByText('$20')).toBeInTheDocument();
    expect(within(basic).getByText('per month')).toBeInTheDocument();
    expect(within(basic).getByRole('button', { name: 'Switch to Basic' })).toBeInTheDocument();

    const team = card('Team');
    expect(within(team).getByText('Recommended')).toBeInTheDocument();
    expect(within(team).getByText('$299')).toBeInTheDocument();
    expect(within(team).getByText('1,000,000 precedents')).toBeInTheDocument();
    expect(within(team).getByRole('button', { name: 'Upgrade to Team' })).toBeInTheDocument();

    const enterprise = card('Enterprise');
    expect(within(enterprise).getByText('By contract')).toBeInTheDocument();
    expect(within(enterprise).queryByText(/^per /)).not.toBeInTheDocument();
    expect(within(enterprise).getByText('Unlimited precedents')).toBeInTheDocument();
    expect(within(enterprise).getByText('Single sign-on')).toBeInTheDocument();
    expect(within(enterprise).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(within(enterprise).queryByRole('button')).not.toBeInTheDocument();
  });

  it('says nothing of runtimes, nodes or hosting, and shows no rates', async () => {
    renderApp('/settings/plans');
    await screen.findByRole('region', { name: 'Enterprise' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText(/hosted machine|hosting|runtime|per node|licence/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows a contract plan with a floor price as from that price a year, and a yearly self-serve plan', async () => {
    server.use(
      http.get(v1('/plans'), () =>
        HttpResponse.json([...plans.slice(0, 3), { ...plans[3], interval: 'year' }, { ...plans[4], price_cents: 1_000_000, interval: 'year' }]),
      ),
    );
    renderApp('/settings/plans');
    expect(within(await screen.findByRole('region', { name: 'Team' })).getByText('per year')).toBeInTheDocument();
    const enterprise = card('Enterprise');
    expect(within(enterprise).getByText('From $10,000')).toBeInTheDocument();
    expect(within(enterprise).getByText('per year')).toBeInTheDocument();
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

  it('offers no move to Free without a subscription: there is nothing to cancel', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, org: { ...me.org, billing_status: 'canceled', renews_at: null } })));
    renderApp('/settings/plans');
    expect(await within(await screen.findByRole('region', { name: 'Team' })).findByRole('button', { name: 'Upgrade to Team' })).toBeInTheDocument();
    expect(within(card('Free')).queryByRole('button')).not.toBeInTheDocument();
  });

  it('on a plan by contract, offers no change here: talk to us', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: plans[4], org: { ...me.org, plan_until: '2027-10-01T00:00:00Z' } })));
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
      // The next plan up is the one recommended: from Free, Basic.
      expect(await within(await screen.findByRole('region', { name: 'Basic' })).findByText('Recommended')).toBeInTheDocument();
      expect(within(card('Pro')).queryByText('Recommended')).not.toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: 'Upgrade to Basic' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://checkout.stripe.test/c/1'));
      expect(body).toEqual({ plan: 'Basic' });
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

describe('Choosing a plan while some features are not built', () => {
  it('offers the plans as before, with each feature not built marked coming soon', async () => {
    server.use(...onFreeHandlers());
    renderApp('/settings/plans');
    const pro = await screen.findByRole('region', { name: 'Pro' });
    expect(within(pro).getByText('$99')).toBeInTheDocument();
    expect(within(pro).getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument();
    const enterprise = card('Enterprise');
    expect(within(enterprise).getByRole('link', { name: 'Talk to us' })).toHaveAttribute('href', 'mailto:sales@glyphh.ai');
    expect(within(enterprise).getByText('Single sign-on').closest('li')).not.toHaveTextContent('Coming soon');
    expect(within(enterprise).getByText('Audit logs').closest('li')).toHaveTextContent('Audit logsComing soon');
  });
});
