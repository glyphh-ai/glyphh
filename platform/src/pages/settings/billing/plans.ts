import type { Plan } from '@/api/types';
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

/** The managed bucket; none on a plan without hosting, where precedents live on your own runtimes. */
export function precedentsText(precedents: number | null): string | null {
  if (precedents === null) return 'Unlimited precedents on hosted machines';
  if (precedents === 0) return null;
  return `${precedents.toLocaleString('en-GB')} precedents on hosted machines`;
}

const featureText: Record<keyof Plan['features'], string> = {
  sync: 'Sync across runtimes',
  ha: 'High availability',
  offline: 'Offline licences for air-gapped runtimes',
  sso: 'SSO and SAML, roles and audit logs',
};

/** What a plan includes, as the server states it: its hosted machines, its precedents, and what it turns on. */
export function planFacts(plan: Plan): Array<{ icon: IconName; text: string }> {
  const facts: Array<{ icon: IconName; text: string }> = [{ icon: 'chip', text: machinesText(plan.limits.machines) }];
  const precedents = precedentsText(plan.limits.precedents);
  if (precedents) facts.push({ icon: 'model', text: precedents });
  for (const [feature, text] of Object.entries(featureText)) {
    if (plan.features[feature as keyof Plan['features']]) facts.push({ icon: 'check', text });
  }
  return facts;
}
