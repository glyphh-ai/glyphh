import type { Plan } from '@/api/types';
import { adaPlans, llmPlans, onFree, plans } from '@/test/fixtures';
import { factText, planFacts, priceText } from './plans';

describe('plan wording', () => {
  it('shows each plan’s Ada Cloud limits, and the price past a metered month', () => {
    const [free, basic, pro, , enterprise] = adaPlans;
    expect(planFacts(free!).map(factText)).toEqual(['1,000 precedents', '5,000 requests a month', '5 requests a second']);
    expect(planFacts(basic!).map(factText)).toEqual(['10,000 precedents', '50,000 requests a month', '10 requests a second', 'Then $1 per 10,000 requests']);
    expect(planFacts(pro!).map(factText)).toEqual(['100,000 precedents', '1,000,000 requests a month', '50 requests a second', 'Then $1 per 10,000 requests']);
    expect(planFacts(enterprise!).map(factText)).toEqual(['Unlimited precedents', 'Unlimited requests', 'Single sign-on', 'Roles', 'Audit logs']);
  });

  it('says nothing of the cloud when the server sends no cloud limits', () => {
    expect(planFacts(plans[0]!)).toEqual([]);
  });

  it('adds a plan’s tokens a month when the server sends them', () => {
    expect(planFacts(llmPlans.plans[2]!).map(factText)).toEqual(['25,000,000 tokens a month']);
    expect(planFacts(llmPlans.plans[4]!).map(factText)).toContain('Tokens a month by contract');
  });

  it('prices each plan on one line', () => {
    expect(plans.map(priceText)).toEqual(['Free', '$20 / month', '$99 / month', '$299 / month', 'By contract']);
  });

  it('shows only what is built as included', () => {
    const facts = planFacts(onFree.plans[4]!);
    expect(facts.filter((fact) => !fact.soon).map((fact) => fact.text)).toEqual(['Single sign-on']);
    expect(facts.filter((fact) => fact.soon).map((fact) => fact.text)).toEqual(['Roles', 'Audit logs']);
  });

  it('says nothing of what Glyphh no longer sells, whatever a server still sends: no runtimes, nodes, sync or connections', () => {
    const old = {
      ...adaPlans[2]!,
      limits: { machines: 3, precedents: 50_000 },
      features: { sync: true, ha: true, offline: true, sso: false, sandbox: true },
      connections: { included: 3, cents_a_month: 500 },
    } as Plan;
    expect(planFacts(old).map(factText)).toEqual(['100,000 precedents', '1,000,000 requests a month', '50 requests a second', 'Then $1 per 10,000 requests']);
  });
});
