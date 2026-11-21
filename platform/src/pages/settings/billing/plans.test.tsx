import { adaPlans, onFree, plans } from '@/test/fixtures';
import { factText, machinesText, planFacts, precedentsText, priceText } from './plans';

describe('plan wording with Ada Cloud on', () => {
  it('shows each plan’s cloud caps in place of runtime nodes and precedents per node, and the price past a metered month', () => {
    const [free, basic, pro, , enterprise] = adaPlans;
    expect(planFacts(free!, true).map(factText)).toEqual(['1,000 precedents', '5,000 requests a month', '5 requests a second']);
    expect(planFacts(basic!, true).map(factText)).toEqual(['10,000 precedents', '50,000 requests a month', '10 requests a second', 'Then $1 per 10,000 requests']);
    expect(planFacts(pro!, true).map(factText)).toEqual(['100,000 precedents', '1,000,000 requests a month', '50 requests a second', 'Then $1 per 10,000 requests']);
    expect(planFacts(enterprise!, true).map(factText)).toEqual(['Unlimited precedents', 'Unlimited requests', 'Single sign-on', 'Roles', 'Audit logs']);
  });

  it('says nothing of the cloud with Ada Cloud off, or when an older server sends no cloud limits', () => {
    expect(planFacts(adaPlans[2]!).map(factText)).toEqual(['3 runtime nodes', '50,000 precedents per node', 'Sync across runtimes']);
    expect(planFacts(plans[0]!, true)).toEqual([]);
  });
});

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
    expect(plans.map(priceText)).toEqual(['Free', '$20 / month', '$99 / month', '$299 / month', 'By contract']);
  });

  it('says nothing of hosted machines on any plan', () => {
    expect(plans.flatMap((plan) => planFacts(plan)).map(factText).join(' ')).not.toMatch(/host|machine/i);
  });
});

describe('plan wording while sync is not built', () => {
  const [free, , pro, , enterprise] = onFree.plans;

  it('shows the runtime nodes and precedents per node, and marks sync as coming soon', () => {
    expect(planFacts(free!).map(factText)).toEqual(['1 runtime node', '5,000 precedents per node']);
    expect(planFacts(pro!).map(factText)).toEqual(['3 runtime nodes', '50,000 precedents per node', 'Coming soon: Sync across runtimes']);
  });

  it('shows only what is built as included', () => {
    const facts = planFacts(enterprise!);
    expect(facts.filter((fact) => !fact.soon).map((fact) => fact.text)).toEqual([
      'Unlimited runtime nodes',
      'Unlimited precedents per node',
      'Offline licences for air-gapped runtimes',
      'Single sign-on',
    ]);
    expect(facts.filter((fact) => fact.soon).map((fact) => fact.text)).toEqual(['Sync across runtimes', 'High availability', 'Roles', 'Audit logs']);
  });

  it('names a feature it has no words for as the server does', () => {
    expect(planFacts({ ...pro!, features: { ...pro!.features, sandbox: true } }).map(factText)).toContain('sandbox');
  });
});
