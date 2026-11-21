import { feature, featureNames } from '@/api/plans';
import type { CloudLimits, ConnectionPrice, FeatureName, Plan } from '@/api/types';
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

/** A plan's runtime nodes (`limits.machines`): every rrotor linked for the org, local or self-hosted. */
export function machinesText(machines: number | null): string {
  if (machines === null) return 'Unlimited runtime nodes';
  if (machines === 0) return 'No runtime nodes';
  return machines === 1 ? '1 runtime node' : `${machines} runtime nodes`;
}

/** What one node may hold, across its models, as the licence key carries it to every node, local or self-hosted. */
export function precedentsText(precedents: number | null): string | null {
  if (precedents === null) return 'Unlimited precedents per node';
  if (precedents === 0) return null;
  return `${precedents.toLocaleString('en-GB')} precedents per node`;
}

/**
 * A plan's tokens a month, the bots' and Glyphh's hosted models': "25,000,000 tokens a month"; null is by contract.
 * None from a server that leaves `llm_tokens` out.
 */
export function tokensText(tokens: number | null | undefined): string | null {
  if (tokens === undefined) return null;
  if (tokens === null) return 'Tokens a month by contract';
  return `${tokens.toLocaleString('en-GB')} tokens a month`;
}

/**
 * A plan's connections to other services as lines: "Unlimited connections", or "3 connections" and, once priced,
 * "Then $5 a connection a month". None from a server that leaves `connections` out.
 */
export function connectionFacts(price: ConnectionPrice | undefined): PlanFact[] {
  if (!price) return [];
  if (price.included === null) return [{ icon: 'external', text: 'Unlimited connections' }];
  const facts: PlanFact[] = [{ icon: 'external', text: price.included === 1 ? '1 connection' : `${count(price.included)} connections` }];
  if (price.cents_a_month !== null) facts.push({ icon: 'card', text: `Then ${money(price.cents_a_month)} a connection a month` });
  return facts;
}

const featureText: Record<FeatureName, string> = {
  sync: 'Sync across runtimes',
  ha: 'High availability',
  offline: 'Offline licences for air-gapped runtimes',
  sso: 'Single sign-on',
  rbac: 'Roles',
  audit: 'Audit logs',
};

/** What only a runtime does: sync across runtimes, high availability, offline licences. */
const runtimeFeatures = ['sync', 'ha', 'offline'];

/** One line of what a plan includes; `soon` when Glyphh has not built it yet, so it is never shown as included. */
export type PlanFact = { icon: IconName; text: string; soon?: boolean };

/** A fact as one line: "Sync across runtimes", or "Coming soon: Sync across runtimes". */
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
 * What a plan includes, as the server states it: its runtime nodes and its precedents per node, and
 * what it turns on, each feature not yet built marked as coming soon. With Ada Cloud on (`ada`) there are no runtimes:
 * no nodes, no precedents per node and none of the runtimes' own features; its cloud limits instead (the org's
 * precedents, requests a month and a second, and the price past the month on Basic, Pro and Team).
 */
export function planFacts(plan: Plan, ada = false): PlanFact[] {
  const facts: PlanFact[] = [];
  if (ada) {
    if (plan.cloud) facts.push(...cloudFacts(plan.cloud));
  } else {
    facts.push({ icon: 'chip', text: machinesText(plan.limits.machines) });
    const precedents = precedentsText(plan.limits.precedents);
    if (precedents) facts.push({ icon: 'model', text: precedents });
  }
  const tokens = tokensText(plan.llm_tokens);
  if (tokens) facts.push({ icon: 'layers', text: tokens });
  facts.push(...connectionFacts(plan.connections));
  const names = [...Object.keys(featureText), ...featureNames(plan).filter((name) => !(name in featureText))];
  for (const name of names) {
    if (ada && runtimeFeatures.includes(name)) continue;
    const { included, built } = feature(plan, name);
    if (included) facts.push({ icon: 'check', text: featureText[name as FeatureName] ?? name, soon: !built });
  }
  return facts;
}
