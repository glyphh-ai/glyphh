import { feature } from '@/api/plans';
import type { CloudLimits, FeatureName, Plan } from '@/api/types';
import { money } from '@/lib/format';
import type { IconName } from '@/ui';

/** A plan's price in two parts, for the plan picker: "$99" "month", "From $10,000" "year", or "By contract". */
export function priceParts(plan: Plan): { amount: string; per: string | null } {
  if (plan.price_cents === null) return { amount: 'By contract', per: null };
  const amount = money(plan.price_cents);
  return { amount: plan.self_serve ? amount : `From ${amount}`, per: plan.interval === 'year' ? 'year' : 'month' };
}

/** A plan's price on one line: "Free", "$99 / month", "From $10,000 / year". */
export function priceText(plan: Plan): string {
  if (plan.price_cents === 0) return 'Free';
  const { amount, per } = priceParts(plan);
  return per ? `${amount} / ${per}` : amount;
}

/**
 * A plan's tokens a month on Glyphh's hosted models: "25,000,000 tokens a month"; null is by contract. None from a
 * server that leaves `llm_tokens` out.
 */
export function tokensText(tokens: number | null | undefined): string | null {
  if (tokens === undefined) return null;
  if (tokens === null) return 'Tokens a month by contract';
  return `${tokens.toLocaleString('en-GB')} tokens a month`;
}

/** The features the platform has words for. Any other the server names is one it no longer sells, and is not shown. */
const featureText: Partial<Record<FeatureName, string>> = {
  sso: 'Single sign-on',
  rbac: 'Roles',
  audit: 'Audit logs',
};

/** One line of what a plan includes; `soon` when Glyphh has not built it yet, so it is never shown as included. */
export type PlanFact = { icon: IconName; text: string; soon?: boolean };

/** A fact as one line: "Single sign-on", or "Coming soon: Roles". */
export const factText = (fact: PlanFact) => (fact.soon ? `Coming soon: ${fact.text}` : fact.text);

const count = (value: number) => value.toLocaleString('en-GB');

/**
 * A plan's Ada Cloud limits as lines: its precedents, its requests a month and a second, and on a metered plan what
 * requests past the month cost ("Then $1 per 10,000 requests"). Null is by contract: unlimited (Enterprise), and no
 * line for the calls a second.
 */
export function cloudFacts(cloud: CloudLimits): PlanFact[] {
  const facts: PlanFact[] = [
    { icon: 'model', text: cloud.precedents === null ? 'Unlimited precedents' : `${count(cloud.precedents)} precedents` },
    { icon: 'monitor', text: cloud.requests_per_month === null ? 'Unlimited requests' : `${count(cloud.requests_per_month)} requests a month` },
  ];
  if (cloud.requests_per_second !== null) facts.push({ icon: 'monitor', text: `${count(cloud.requests_per_second)} requests a second` });
  if (cloud.overage && cloud.requests_per_month !== null && cloud.overage_cents_per_10k) {
    facts.push({ icon: 'card', text: `Then ${money(cloud.overage_cents_per_10k)} per 10,000 requests` });
  }
  return facts;
}

/**
 * What a plan includes, as the server states it: its Ada Cloud limits (the org's precedents, requests a month and a
 * second, and the price past the month on Basic, Pro and Team), its tokens a month on hosted models, and what it turns
 * on, each feature not yet built marked as coming soon.
 */
export function planFacts(plan: Plan): PlanFact[] {
  const facts: PlanFact[] = [];
  if (plan.cloud) facts.push(...cloudFacts(plan.cloud));
  const tokens = tokensText(plan.llm_tokens);
  if (tokens) facts.push({ icon: 'layers', text: tokens });
  for (const name of Object.keys(featureText) as FeatureName[]) {
    const { included, built } = feature(plan, name);
    if (included) facts.push({ icon: 'check', text: featureText[name]!, soon: !built });
  }
  return facts;
}
