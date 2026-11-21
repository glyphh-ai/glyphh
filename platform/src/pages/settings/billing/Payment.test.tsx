import { screen, within } from '@testing-library/react';
import { cloudLimits, llmBilling, me } from '@/test/fixtures';
import { renderApp, stubLocation } from '@/test/render';
import { apiError, http, HttpResponse, llmHandlers, server, v1 } from '@/test/server';
import { brandName } from './PaymentSection';

describe('The card on file and the invoices on Billing', () => {
  it('shows the card Stripe has, and replaces it in Stripe’s page', async () => {
    const location = stubLocation();
    let asked = 0;
    server.use(
      http.post(v1('/billing/card'), () => {
        asked += 1;
        return HttpResponse.json({ url: 'https://billing.stripe.test/p/card' });
      }),
    );
    try {
      const { user } = renderApp('/settings/billing');
      const card = await screen.findByRole('region', { name: 'Card on file' });
      expect(within(card).getByText('Visa ending 4242')).toBeInTheDocument();
      expect(within(card).getByText('Expires 04/29')).toBeInTheDocument();
      await user.click(within(card).getByRole('button', { name: 'Replace card' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://billing.stripe.test/p/card'));
      expect(asked).toBe(1);
    } finally {
      location.restore();
    }
  });

  it('offers to add a card when there is none, and shows Stripe’s refusal', async () => {
    server.use(
      http.get(v1('/billing/payment'), () => HttpResponse.json({ card: null, invoices: [] })),
      http.post(v1('/billing/card'), () => apiError(503, 'E_UNAVAILABLE', 'Stripe didn’t answer. Try again.')),
    );
    const { user } = renderApp('/settings/billing');
    const card = await screen.findByRole('region', { name: 'Card on file' });
    expect(within(card).getByText('No card on file')).toBeInTheDocument();
    await user.click(within(card).getByRole('button', { name: 'Add a card' }));
    expect(await within(card).findByText('Stripe didn’t answer. Try again.')).toBeInTheDocument();
    expect(screen.getByText('No invoices yet')).toBeInTheDocument();
  });

  it('lists the invoices, each with Stripe’s page, and opens them all in Stripe', async () => {
    const location = stubLocation();
    server.use(http.post(v1('/billing/portal'), () => HttpResponse.json({ url: 'https://billing.stripe.test/p/1' })));
    try {
      const { user } = renderApp('/settings/billing');
      const table = await screen.findByRole('table', { name: 'Invoices' });
      const rows = within(table).getAllByRole('row').slice(1);
      expect(rows.map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent))).toEqual([
        ['1 Nov 2026', 'GLY-0002', 'Paid', '$99', 'View · PDF'],
        ['1 Oct 2026', 'GLY-0001', 'Due', '$49.50', 'View'],
      ]);
      expect(within(table).getByRole('link', { name: 'View invoice GLY-0002' })).toHaveAttribute('href', 'https://invoice.stripe.test/in_2');
      expect(within(table).getByRole('link', { name: 'Invoice GLY-0002 as a PDF' })).toHaveAttribute('href', 'https://invoice.stripe.test/in_2.pdf');
      await user.click(screen.getByRole('button', { name: 'All in Stripe' }));
      await vi.waitFor(() => expect(location.assign).toHaveBeenCalledWith('https://billing.stripe.test/p/1'));
    } finally {
      location.restore();
    }
  });

  it('is not asked for, nor shown, for a member', async () => {
    let asked = false;
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, role: 'member' })),
      http.get(v1('/billing/payment'), () => {
        asked = true;
        return HttpResponse.json({ card: null, invoices: [] });
      }),
    );
    renderApp('/settings/billing');
    expect(await screen.findByText('Only your org’s admin can change this.')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Card on file' })).not.toBeInTheDocument();
    expect(asked).toBe(false);
  });

  it('shows the server’s refusal, as a server without Stripe answers', async () => {
    server.use(http.get(v1('/billing/payment'), () => apiError(503, 'E_UNAVAILABLE', 'Billing isn’t set up on this server.')));
    renderApp('/settings/billing');
    expect(await screen.findByText('Billing isn’t set up on this server.')).toBeInTheDocument();
  });

  it('names the card brands', () => {
    expect(brandName('amex')).toBe('American Express');
    expect(brandName('link')).toBe('Link');
  });
});

describe('Buying more usage and the overages on Billing', () => {
  it('offers a one-time top-up of the balance, and says what happens past each limit', async () => {
    // The first handler that matches answers.
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, ada_cloud: true, plan: { ...me.plan, cloud: cloudLimits.Pro } })),
      http.get(v1('/billing'), () =>
        HttpResponse.json({ ...llmBilling, connections: { used: 3, included: 2, over: 1, cents_a_month: 500, due_cents: 500 } }),
      ),
      ...llmHandlers(),
    );
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Buy more usage' })).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Overage balance' })).getByRole('button', { name: 'Add funds' })).toBeInTheDocument();
    const overages = await screen.findByRole('region', { name: 'Overages' });
    expect(overages).toHaveTextContent('Your plan has 25,000,000 tokens a month for bots and hosted models.');
    expect(overages).toHaveTextContent('Past 1,000,000 a month, requests go on at $1 per 10,000, on your next invoice.');
    expect(overages).toHaveTextContent('2 included, then $5 a connection a month.');
    expect(within(overages).getByRole('link', { name: 'Change plan' })).toHaveAttribute('href', '/settings/plans');
  });

  it('says Free’s requests stop, a cap not priced is not charged, and leaves out what the server does not send', async () => {
    server.use(
      http.get(v1('/me'), () => HttpResponse.json({ ...me, ada_cloud: true, plan: { ...me.plan, cloud: cloudLimits.Free } })),
      http.get(v1('/billing'), () =>
        HttpResponse.json({ ...llmBilling, tokens: null, balance: null, connections: { used: 1, included: 3, over: 0, cents_a_month: null, due_cents: null } }),
      ),
    );
    renderApp('/settings/billing');
    const overages = await screen.findByRole('region', { name: 'Overages' });
    expect(overages).toHaveTextContent('Past 5,000 a month, requests stop until the month turns.');
    expect(overages).toHaveTextContent('3 included. Past them, connections are not charged yet.');
    expect(overages).not.toHaveTextContent('tokens');
    expect(screen.queryByRole('heading', { name: 'Buy more usage' })).not.toBeInTheDocument();
  });

  it('has no overages to show from a server that sends no limits', async () => {
    renderApp('/settings/billing');
    expect(await screen.findByRole('heading', { name: 'Pro' })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Overages' })).not.toBeInTheDocument();
  });
});
