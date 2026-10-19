import { render, screen, within } from '@testing-library/react';
import { hostingOff, plans, rates } from '@/test/fixtures';
import { HostingRates } from './HostingRates';
import { factText, machinesText, planFacts, precedentsText, priceText } from './plans';

describe('plan wording', () => {
  it.each([
    [null, 'Unlimited runtime nodes'],
    [0, 'No runtime nodes'],
    [1, '1 runtime node'],
    [3, '3 runtime nodes'],
  ])('%s runtime nodes read %s', (machines, text) => expect(machinesText(machines)).toBe(text));

  it('names the precedents one node may hold, and none when the plan says 0', () => {
    expect(precedentsText(0)).toBeNull();
    expect(precedentsText(null)).toBe('Unlimited precedents per node');
    expect(precedentsText(50_000)).toBe('50,000 precedents per node');
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

  it('shows the runtime nodes and precedents per node as with hosting on, and marks sync as coming soon', () => {
    expect(planFacts(free!).map(factText)).toEqual(['1 runtime node', '5,000 precedents per node']);
    expect(planFacts(pro!).map(factText)).toEqual(['3 runtime nodes', '50,000 precedents per node', 'Coming soon: Sync across runtimes']);
  });

  it('shows only what is built as included', () => {
    const facts = planFacts(enterprise!);
    expect(facts.filter((fact) => !fact.soon).map((fact) => fact.text)).toEqual(['Unlimited runtime nodes', 'Unlimited precedents per node', 'Offline licences for air-gapped runtimes']);
    expect(facts.filter((fact) => fact.soon).map((fact) => fact.text)).toEqual([
      'Sync across runtimes',
      'High availability',
      'SSO and SAML',
      'Roles',
      'Audit logs',
    ]);
  });

  it('names a feature it has no words for as the server does', () => {
    expect(planFacts({ ...pro!, features: { ...pro!.features, sandbox: true } }).map(factText)).toContain('sandbox');
  });
});
