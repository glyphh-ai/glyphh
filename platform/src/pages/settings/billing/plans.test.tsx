import { render, screen, within } from '@testing-library/react';
import { hostingOff, plans, rates } from '@/test/fixtures';
import { HostingRates } from './HostingRates';
import { factText, machinesText, planFacts, precedentsText, priceText } from './plans';

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

describe('plan wording while Glyphh hosts nothing and sync is not built', () => {
  const [free, pro, , enterprise] = hostingOff.plans;

  it('says nothing of hosted machines, and marks the synced bucket and sync as coming soon', () => {
    expect(planFacts(free!, false)).toEqual([]);
    expect(planFacts(pro!, false).map(factText)).toEqual(['Coming soon: 100,000 precedents in the synced store', 'Coming soon: Sync across runtimes']);
  });

  it('shows only what is built as included', () => {
    const facts = planFacts(enterprise!, false);
    expect(facts.filter((fact) => !fact.soon).map((fact) => fact.text)).toEqual(['Offline licences for air-gapped runtimes']);
    expect(facts.filter((fact) => fact.soon).map((fact) => fact.text)).toEqual([
      'Unlimited precedents in the synced store',
      'Sync across runtimes',
      'High availability',
      'SSO and SAML',
      'Roles',
      'Audit logs',
    ]);
  });

  it('names a feature it has no words for as the server does', () => {
    expect(planFacts({ ...pro!, features: { ...pro!.features, sandbox: true } }, false).map(factText)).toContain('sandbox');
  });
});
