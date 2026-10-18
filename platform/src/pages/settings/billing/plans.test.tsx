import { render, screen, within } from '@testing-library/react';
import { plans, rates } from '@/test/fixtures';
import { HostingRates } from './HostingRates';
import { machinesText, precedentsText, priceText } from './plans';

describe('plan wording', () => {
  it.each([
    [null, 'Unlimited hosted machines'],
    [0, 'No hosted machines'],
    [1, '1 hosted machine'],
    [3, '3 hosted machines'],
  ])('%s machines read %s', (machines, text) => expect(machinesText(machines)).toBe(text));

  it('names the managed bucket, and none on a plan without hosting', () => {
    expect(precedentsText(0)).toBeNull();
    expect(precedentsText(null)).toBe('Unlimited precedents on hosted machines');
    expect(precedentsText(100_000)).toBe('100,000 precedents on hosted machines');
  });

  it('prices each plan on one line', () => {
    expect(plans.map(priceText)).toEqual(['Free', '$99 / month', '$299 / month', 'By contract']);
  });
});

describe('the hosted machine rates', () => {
  it('shows a dash for a self-serve plan the server gives no rates, and the contract for one sold by contract', () => {
    render(<HostingRates rates={{ ...rates, plans: {} }} plans={[plans[1]!, plans[3]!]} />);
    const table = screen.getByRole('table', { name: 'Hosted machine rates' });
    expect(within(table).getAllByText('—')).toHaveLength(4);
    expect(within(table).getAllByText('Set in your contract.')).toHaveLength(4);
  });
});
