import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { ApiError } from '@/api/client';
import { ErrorNotice } from '@/ui';

/** Where a refusal for an empty balance sends the person: Billing, with Add funds open. */
export const addFundsPath = '/settings/billing?add=1';

/** 402 E_BALANCE: the plan's tokens a month are used and the overage balance is empty. */
export const isBalanceRefusal = (error: unknown): error is ApiError => error instanceof ApiError && error.code === 'E_BALANCE';

/**
 * The server's own words for a refusal, with its trace id; anything else gets a plain line. An empty balance (402
 * E_BALANCE) comes with the way to add funds.
 */
export function ApiErrorNotice({ error, action }: { error: unknown; action?: ReactNode }) {
  if (!error) return null;
  if (isBalanceRefusal(error)) {
    const message = error.message || 'Your plan’s tokens this month are used and your overage balance is empty.';
    return <ErrorNotice message={message} traceId={error.traceId} action={action ?? <Link to={addFundsPath}>Add funds</Link>} />;
  }
  if (error instanceof ApiError) return <ErrorNotice message={error.message} traceId={error.traceId} action={action} />;
  return <ErrorNotice message="Glyphh could not be reached. Check your connection and try again." action={action} />;
}
