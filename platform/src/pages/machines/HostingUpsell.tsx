import { Link } from 'react-router';
import { useMe, usePlans, useRates } from '@/api/queries';
import type { SizeRate } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { HostingRates, ratesNote } from '@/pages/settings/billing/HostingRates';
import { hasHosting, hostingPlansText } from '@/pages/settings/billing/plans';
import { LoadingCard } from '@/ui';
import styles from './Machines.module.css';

/**
 * The size rates of the person's own plan, once both are read; none on a plan without hosting. A plan sold by
 * contract has its rates in the contract, so it is `contract` and has no rates here.
 */
export function usePlanRates(): SizeRate[] | 'contract' | undefined {
  const me = useMe();
  const rates = useRates();
  const plan = me.data?.plan;
  if (plan && !plan.self_serve) return 'contract';
  return plan && rates.data?.plans[plan.name]?.sizes;
}

/** What a hosted machine has cost so far this month, from the org's hosting; undefined until it is read. */
export function useMachineCents(id: string | null): number | undefined {
  const me = useMe();
  if (!me.data) return undefined;
  return me.data.hosting.machines.find((machine) => machine.id === id)?.cents ?? 0;
}

/** Whether the person's plan has no hosting (Free); false until the plan is known. */
export function useNoHosting(): boolean {
  const me = useMe();
  return me.data !== undefined && !hasHosting(me.data.plan);
}

/** On a plan without hosting: the plans that have it, their rates, and that running rrotor yourself is free. */
export function HostingUpsell({ isAdmin }: { isAdmin: boolean }) {
  const plans = usePlans();
  const rates = useRates();
  const offered = (plans.data ?? []).filter((plan) => plan.self_serve && hasHosting(plan));

  return (
    <div className={styles.upsell}>
      <p className={styles.upsellText}>
        Glyphh hosts machines on {hostingPlansText(plans.data)}. {isAdmin ? 'Upgrade to make one.' : 'Ask your admin to upgrade.'} Running rrotor
        yourself is free: <Link to="/getting-started">Getting started</Link> shows how.
      </p>
      {(plans.isPending || rates.isPending) && <LoadingCard lines={3} />}
      <ApiErrorNotice error={plans.error ?? rates.error} />
      {rates.data && offered.length > 0 && <HostingRates rates={rates.data} plans={offered} />}
      <span className={styles.meta}>{ratesNote}</span>
    </div>
  );
}
