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

/** Whether Glyphh hosts machines on the plan. */
export const hasHosting = (plan: Plan) => plan.limits.machines !== 0;

/** The self-serve plans with hosting, as words: "Pro and Team". */
export function hostingPlansText(plans: Plan[] | undefined): string {
  const names = (plans ?? []).filter((plan) => plan.self_serve && hasHosting(plan)).map((plan) => plan.name);
  return names.length ? listText(names) : 'a paid plan';
}

export function machinesText(machines: number | null): string {
  if (machines === null) return 'Unlimited hosted machines';
  if (machines === 0) return 'No hosted machines';
  return machines === 1 ? '1 hosted machine' : `${machines} hosted machines`;
}

/**
 * The precedent bucket; none on a plan without one. With hosting on it is managed on the hosted machines; with hosting
 * off it is the synced store's.
 */
export function precedentsText(precedents: number | null, hosting = true): string | null {
  const where = hosting ? 'on hosted machines' : 'in the synced store';
  if (precedents === null) return `Unlimited precedents ${where}`;
  if (precedents === 0) return null;
  return `${precedents.toLocaleString('en-GB')} precedents ${where}`;
}

const featureText: Record<FeatureName, string> = {
  sync: 'Sync across runtimes',
  ha: 'High availability',
  offline: 'Offline licences for air-gapped runtimes',
  sso: 'SSO and SAML',
  rbac: 'Roles',
  audit: 'Audit logs',
};

/** One line of what a plan includes; `soon` when Glyphh has not built it yet, so it is never shown as included. */
export type PlanFact = { icon: IconName; text: string; soon?: boolean };

/** A fact as one line: "Sync across runtimes", or "Coming soon: Sync across runtimes". */
export const factText = (fact: PlanFact) => (fact.soon ? `Coming soon: ${fact.text}` : fact.text);

/**
 * What a plan includes, as the server states it: its hosted machines (none said while Glyphh hosts nothing), its
 * precedents, and what it turns on, each feature not yet built marked as coming soon. The synced store's bucket is
 * coming soon until sync is built.
 */
export function planFacts(plan: Plan, hosting = true): PlanFact[] {
  const facts: PlanFact[] = hosting ? [{ icon: 'chip', text: machinesText(plan.limits.machines) }] : [];
  const precedents = precedentsText(plan.limits.precedents, hosting);
  if (precedents) facts.push({ icon: 'model', text: precedents, soon: !hosting && !feature(plan, 'sync').built });
  const names = [...Object.keys(featureText), ...featureNames(plan).filter((name) => !(name in featureText))];
  for (const name of names) {
    const { included, built } = feature(plan, name);
    if (included) facts.push({ icon: 'check', text: featureText[name as FeatureName] ?? name, soon: !built });
  }
  return facts;
}
