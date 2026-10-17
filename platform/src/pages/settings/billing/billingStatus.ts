import type { ChipTone } from '@/ui';

/** Stripe's subscription states, as the server keeps them on the org. */
export type BillingStatus = 'none' | 'active' | 'trialing' | 'past_due' | 'unpaid' | 'canceled' | 'incomplete' | 'incomplete_expired' | 'paused';

/** Whether the org has a live Stripe subscription that plan, seat and add-on changes apply to. */
export function isSubscribed(status: string): boolean {
  return !['none', 'canceled', 'incomplete_expired'].includes(status);
}

/** A chip for a state that needs the person's attention; none when all is well. */
export function statusChip(status: string): { label: string; tone: ChipTone } | null {
  switch (status as BillingStatus) {
    case 'past_due':
    case 'unpaid':
      return { label: 'Payment due', tone: 'amber' };
    case 'incomplete':
      return { label: 'Payment not finished', tone: 'amber' };
    case 'paused':
      return { label: 'Paused', tone: 'amber' };
    case 'canceled':
      return { label: 'Cancelled', tone: 'red' };
    default:
      return null;
  }
}
