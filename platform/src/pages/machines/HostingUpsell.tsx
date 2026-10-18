import { Link } from 'react-router';
import { useMe, usePlans, useRates } from '@/api/queries';
import type { SizeRate } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { HostingRates, ratesNote } from '@/pages/settings/billing/HostingRates';
import { hasHosting, hostingPlansText } from '@/pages/settings/billing/plans';
import { LoadingCard } from '@/ui';
import styles from './Machines.module.css';

/** The size rates of the person's own plan, once both are read; none on a plan without hosting. */
export function usePlanRates(): SizeRate[] | undefined {
  const me = useMe();
  const rates = useRates();
  const plan = me.data?.plan;
  return plan && rates.data?.plans[plan.name]?.sizes;
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
  const names = (plans.data ?? []).filter((plan) => plan.self_serve && hasHosting(plan)).map((plan) => plan.name);

  return (
    <div className={styles.upsell}>
      <p className={styles.upsellText}>
        Glyphh hosts machines on {hostingPlansText(plans.data)}. {isAdmin ? 'Upgrade to make one.' : 'Ask your admin to upgrade.'} Running rrotor
        yourself is free: <Link to="/getting-started">Getting started</Link> shows how.
      </p>
      {(plans.isPending || rates.isPending) && <LoadingCard lines={3} />}
      <ApiErrorNotice error={plans.error ?? rates.error} />
      {rates.data && names.length > 0 && <HostingRates rates={rates.data} plans={names} />}
      <span className={styles.meta}>{ratesNote}</span>
    </div>
  );
}
