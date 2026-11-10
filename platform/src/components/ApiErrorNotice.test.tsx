import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { ApiError } from '@/api/client';
import { ApiErrorNotice } from './ApiErrorNotice';

function show(error: unknown) {
  const router = createMemoryRouter(
    [
      { path: '/', element: <ApiErrorNotice error={error} /> },
      { path: '/settings/billing', element: <p>Billing</p> },
    ],
    { initialEntries: ['/'] },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe('A refusal for an empty balance', () => {
  it('says so in the server’s words, with the way to add funds', async () => {
    const error = new ApiError(402, {
      code: 'E_BALANCE',
      message: 'Your plan’s tokens this month are used and your balance is empty.',
      trace_id: 't-1',
      reason: 'tokens',
      used: 25_000_000,
      max: 25_000_000,
      balance_cents: 0,
    });
    const router = show(error);
    expect(screen.getByRole('alert')).toHaveTextContent('Your plan’s tokens this month are used and your balance is empty.');
    expect(screen.getByText('Trace t-1')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('link', { name: 'Add funds' }));
    expect(router.state.location.pathname).toBe('/settings/billing');
    expect(router.state.location.search).toBe('?add=1');
  });

  it('has words of its own when the server sends none', () => {
    show(new ApiError(402, { code: 'E_BALANCE', message: '' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Your plan’s tokens this month are used and your overage balance is empty.');
  });

  it('leaves any other refusal as it was', () => {
    show(new ApiError(403, { code: 'E_FORBIDDEN', message: 'Not yours.' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Not yours.');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });
});
