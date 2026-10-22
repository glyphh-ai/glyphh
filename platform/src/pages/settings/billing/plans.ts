import { feature, featureNames } from '@/api/plans';
import type { FeatureName, Plan } from '@/api/types';
import { listText, money } from '@/lib/format';
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

/** Whether Glyphh hosts machines on the plan (while hosting is on): every plan but Free. */
export const hasHosting = (plan: Plan) => plan.price_cents !== 0;

/** The self-serve plans with hosting, as words: "Pro and Team". */
export function hostingPlansText(plans: Plan[] | undefined): string {
  const names = (plans ?? []).filter((plan) => plan.self_serve && hasHosting(plan)).map((plan) => plan.name);
  return names.length ? listText(names) : 'a paid plan';
}

/** A plan's runtime nodes (`limits.machines`): every runtime linked for the org, hosted or self-hosted. */
export function machinesText(machines: number | null): string {
  if (machines === null) return 'Unlimited runtime nodes';
  if (machines === 0) return 'No runtime nodes';
  return machines === 1 ? '1 runtime node' : `${machines} runtime nodes`;
}

/** What one node may hold, across its models, as the licence key carries it to every node, hosted or self-hosted. */
export function precedentsText(precedents: number | null): string | null {
  if (precedents === null) return 'Unlimited precedents per node';
  if (precedents === 0) return null;
  return `${precedents.toLocaleString('en-GB')} precedents per node`;
}

const featureText: Record<FeatureName, string> = {
  sync: 'Sync across runtimes',
  ha: 'High availability',
  offline: 'Offline licences for air-gapped runtimes',
  sso: 'SSO and SAML',
  rbac: 'Roles',
  audit: 'Audit logs',
};

/** What only a runtime does: sync across runtimes, high availability, offline licences. */
const runtimeFeatures = ['sync', 'ha', 'offline'];

/** One line of what a plan includes; `soon` when Glyphh has not built it yet, so it is never shown as included. */
export type PlanFact = { icon: IconName; text: string; soon?: boolean };

/** A fact as one line: "Sync across runtimes", or "Coming soon: Sync across runtimes". */
export const factText = (fact: PlanFact) => (fact.soon ? `Coming soon: ${fact.text}` : fact.text);

/**
 * What a plan includes, as the server states it: its runtime nodes and its precedents per node, and
 * what it turns on, each feature not yet built marked as coming soon. With Ada Cloud on (`ada`) there are no runtimes:
 * no nodes, no precedents per node and none of the runtimes' own features.
 */
export function planFacts(plan: Plan, ada = false): PlanFact[] {
  const facts: PlanFact[] = [];
  if (!ada) {
    facts.push({ icon: 'chip', text: machinesText(plan.limits.machines) });
    const precedents = precedentsText(plan.limits.precedents);
    if (precedents) facts.push({ icon: 'model', text: precedents });
  }
  const names = [...Object.keys(featureText), ...featureNames(plan).filter((name) => !(name in featureText))];
  for (const name of names) {
    if (ada && runtimeFeatures.includes(name)) continue;
    const { included, built } = feature(plan, name);
    if (included) facts.push({ icon: 'check', text: featureText[name as FeatureName] ?? name, soon: !built });
  }
  return facts;
}
