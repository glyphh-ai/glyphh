import { screen, within } from '@testing-library/react';
import { cloudLimits, me, plans } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, llmHandlers, onFreeHandlers, server, v1 } from '@/test/server';
import { dollarsToCents } from '../tokens/AddFundsDialog';

/** Records each top-up asked for, answering with Stripe's checkout page. */
function topUps() {
  const sent: unknown[] = [];
  server.use(
    http.post(v1('/billing/topup'), async ({ request }) => {
      sent.push(await request.json());
      return HttpResponse.json({ url: 'https://checkout.stripe.test/c/topup' });
    }),
  );
  return sent;
}

describe('The overage balance on Billing', () => {
  it('is not there while hosted models are off', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Overage balance' })).not.toBeInTheDocument();
  });

  it('shows the balance in dollars, its history, and the plan’s tokens a month', async () => {
    server.use(...llmHandlers(), http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: { ...me.plan, llm_tokens: 25_000_000 } })));
    renderApp('/settings/billing');
    const balance = await screen.findByRole('region', { name: 'Overage balance' });
    expect(within(balance).getByText('$18.70')).toBeInTheDocument();
    expect(screen.getByText('25,000,000 tokens a month')).toBeInTheDocument();

    const history = await screen.findByRole('table', { name: 'Balance history' });
    const rows = within(history).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent))).toEqual([
      ['9 Nov 2026', 'Charge', '-$11.30', 'adaL 34B 1.0'],
      ['5 Nov 2026', 'Grant', '+$5.00', 'Launch credit for testing'],
      ['2 Nov 2026', 'Top-up', '+$25.00', '–'],
    ]);
  });

  it('adds funds: a preset or another amount from $10 to $1,000, paid in Stripe’s checkout', async () => {
    server.use(...llmHandlers());
    const sent = topUps();
    const location = stubLocation();
    try {
      const { user } = renderApp('/settings/billing');
      await user.click(within(await screen.findByRole('region', { name: 'Overage balance' })).getByRole('button', { name: 'Add funds' }));
      const dialog = screen.getByRole('dialog', { name: 'Add funds' });
      const amounts = within(dialog).getByRole('group', { name: 'Amount' });
      expect(within(amounts).getAllByRole('button').map((b) => b.textContent)).toEqual(['$10', '$25', '$50', '$100']);
      expect(within(amounts).getByRole('button', { name: '$25' })).toHaveAttribute('aria-pressed', 'true');

      const other = within(dialog).getByLabelText('Another amount');
      await user.type(other, '5');
      expect(within(dialog).getByText('Between $10 and $1,000, in dollars and cents.')).toBeInTheDocument();
      expect(within(dialog).getByRole('button', { name: 'Add funds' })).toBeDisabled();
      await user.clear(other);
      await user.type(other, '1001');
      expect(within(dialog).getByRole('button', { name: 'Add funds' })).toBeDisabled();
      await user.clear(other);
      await user.type(other, '120.50');
      await user.click(within(dialog).getByRole('button', { name: 'Add $120.50' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://checkout.stripe.test/c/topup'));

      await user.click(within(amounts).getByRole('button', { name: '$50' }));
      expect(other).toHaveValue('');
      await user.click(within(dialog).getByRole('button', { name: 'Add $50' }));
      await vi.waitFor(() => expect(sent).toEqual([{ amount_cents: 12_050 }, { amount_cents: 5_000 }]));
    } finally {
      location.restore();
    }
  });

  it('shows a refusal in the dialog', async () => {
    server.use(http.post(v1('/billing/topup'), () => apiError(503, 'E_UNAVAILABLE', 'Payments are paused.')), ...llmHandlers());
    const { user } = renderApp('/settings/billing');
    await user.click(within(await screen.findByRole('region', { name: 'Overage balance' })).getByRole('button', { name: 'Add funds' }));
    const dialog = screen.getByRole('dialog', { name: 'Add funds' });
    await user.click(within(dialog).getByRole('button', { name: 'Add $25' }));
    expect(await within(dialog).findByText('Payments are paused.')).toBeInTheDocument();
  });

  it('says so when Stripe sends the person back from a top-up', async () => {
    server.use(...llmHandlers());
    const { router } = renderApp('/settings/billing?topup=1');
    expect(await screen.findByText(/Your funds are added once the payment clears/)).toBeInTheDocument();
    await vi.waitFor(() => expect(router.state.location.search).toBe(''));
  });

  it('opens Add funds from a link with ?add=1', async () => {
    server.use(...llmHandlers());
    renderApp('/settings/billing?add=1');
    expect(await screen.findByRole('dialog', { name: 'Add funds' })).toBeInTheDocument();
  });

  it('reads amounts in dollars', () => {
    expect(dollarsToCents('25')).toBe(2_500);
    expect(dollarsToCents('$1,000')).toBe(100_000);
    expect(dollarsToCents('12.5')).toBe(1_250);
    expect(dollarsToCents('12.555')).toBeNull();
    expect(dollarsToCents('ten')).toBeNull();
  });
});

const free = { ...me, plan: { ...plans[0]!, cloud: cloudLimits.Free }, org: { ...me.org, billing_status: 'none', renews_at: null } };

describe('Billing', () => {
  it('shows the plan: its flat price, renewal and what it includes', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: { ...me.plan, cloud: cloudLimits.Pro } })));
    renderApp('/settings/billing');
    expect(await screen.findByText('$99 / month')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.getByText('Renews 16 Nov 2026')).toBeInTheDocument();
    expect(screen.getByText('100,000 precedents')).toBeInTheDocument();
    expect(screen.getByText('1,000,000 requests a month')).toBeInTheDocument();
    expect(screen.queryByText(/runtime|per node|licence/i)).not.toBeInTheDocument();
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

  it('on Free, shows the plan and what it includes', async () => {
    server.use(http.get(v1('/me'), () => HttpResponse.json(free)));
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Free' })).toBeInTheDocument();
    expect(screen.getByText('1,000 precedents')).toBeInTheDocument();
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
