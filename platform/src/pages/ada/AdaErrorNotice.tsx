import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { adaRefusal } from '@/api/ada';
import { ApiError } from '@/api/client';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { date } from '@/lib/format';
import { salesUrl } from '@/lib/links';
import { ErrorNotice } from '@/ui';

const PLANS = '/settings/plans';

const seconds = (n: number) => `${n} second${n === 1 ? '' : 's'}`;

/**
 * A refusal from Ada, in the server's own words, with the way on beside a plan refusal: past the plan's calls a second
 * (429 E_RATE), when to try again; the month's requests used on a plan that is not metered (403 E_LIMIT `requests`),
 * when they start again and the plan to upgrade to (Talk to us when none reads more); past the plan's precedents
 * (403 E_LIMIT `precedents`), the plans. Anything else is ApiErrorNotice's. `error` may be a failed job's error.
 */
export function AdaErrorNotice({ error, action }: { error: unknown; action?: ReactNode }) {
  const refusal = adaRefusal(error);
  if (!refusal) {
    if (error && !(error instanceof ApiError) && typeof error === 'object' && 'message' in error) {
      return <ErrorNotice message={String((error as { message: unknown }).message)} action={action} />;
    }
    return <ApiErrorNotice error={error} action={action} />;
  }
  const said = error instanceof ApiError ? error.message : String((error as { message?: unknown }).message ?? '');
  const traceId = error instanceof ApiError ? error.traceId : undefined;

  if (refusal.kind === 'rate') {
    const wait = refusal.retryAfter ?? 1;
    const message = said || `Too many calls a second for your plan. Try again in ${seconds(wait)}.`;
    return <ErrorNotice message={message} traceId={traceId} action={action} />;
  }

  if (refusal.kind === 'requests') {
    const fallback = `Your plan’s requests this month are used${refusal.resetsAt ? `: they start again on ${date(refusal.resetsAt)}` : ''}.`;
    const way = refusal.upgrade ? (
      <Link to={PLANS}>Upgrade to {refusal.upgrade}</Link>
    ) : (
      <a href={salesUrl}>Talk to us</a>
    );
    return <ErrorNotice message={said || fallback} traceId={traceId} action={action ?? way} />;
  }

  const fallback = 'This would take your models past your plan’s precedents.';
  return <ErrorNotice message={said || fallback} traceId={traceId} action={action ?? <Link to={PLANS}>See plans</Link>} />;
}
