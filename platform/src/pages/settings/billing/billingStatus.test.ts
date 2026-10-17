import { isSubscribed, statusChip } from './billingStatus';

describe('billing status', () => {
  it.each([
    ['past_due', { label: 'Payment due', tone: 'amber' }],
    ['unpaid', { label: 'Payment due', tone: 'amber' }],
    ['incomplete', { label: 'Payment not finished', tone: 'amber' }],
    ['paused', { label: 'Paused', tone: 'amber' }],
    ['canceled', { label: 'Cancelled', tone: 'red' }],
    ['active', null],
    ['trialing', null],
    ['none', null],
  ])('%s shows %o', (status, chip) => expect(statusChip(status)).toEqual(chip));

  it.each([
    ['active', true],
    ['past_due', true],
    ['paused', true],
    ['none', false],
    ['canceled', false],
    ['incomplete_expired', false],
  ])('%s is subscribed: %s', (status, subscribed) => expect(isSubscribed(status)).toBe(subscribed));
});
