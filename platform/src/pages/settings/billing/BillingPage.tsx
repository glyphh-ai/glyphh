import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router';
import { keys, useMe, usePlans, useRates } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { LoadingCard, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from '../SettingsTitle';
import settings from '../settings.module.css';
import { HostingRates, ratesNote } from './HostingRates';
import { PlanCard } from './PlanCard';
import { hasHosting, hostingPlansText } from './plans';
import { UpgradeCard } from './UpgradeCard';
import styles from './billing.module.css';

export function BillingPage() {
  const me = useMe();
  const plans = usePlans();
  const rates = useRates();
  const toast = useToast();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();

  // Stripe's checkout and portal send the browser back with ?done=1: read everything afresh.
  const done = params.get('done');
  useEffect(() => {
    if (!done) return;
    for (const queryKey of [keys.me, keys.org]) void client.invalidateQueries({ queryKey });
    toast.show('Billing is up to date.');
    setParams({}, { replace: true });
  }, [done, client, setParams, toast]);

  const isAdmin = me.data?.role === 'admin';
  const current = me.data?.plan;
  const list = plans.data ?? [];
  const at = list.findIndex((plan) => plan.name === current?.name);
  // The plans after this one in the server's order; all of them when this one is not listed.
  const upgrades = current ? list.slice(at + 1) : [];
  // The rates of the plan in force, or, on a plan without hosting, of the self-serve plans that have it.
  const ratePlans = current && hasHosting(current) ? [current.name] : list.filter((plan) => plan.self_serve && hasHosting(plan)).map((plan) => plan.name);

  return (
    <>
      <SettingsTitle title="Billing" />
      <SettingsSection title="Subscription" description="Your plan, and the plans above it. Members and installs are unlimited on every plan.">
        {me.isPending && <LoadingCard lines={4} />}
        <ApiErrorNotice error={me.error ?? plans.error} />
        {me.data && (
          <div className={settings.cards}>
            <PlanCard me={me.data} isAdmin={isAdmin} />
            {upgrades.map((plan) => (
              <UpgradeCard key={plan.name} plan={plan} isAdmin={isAdmin} onUpgrade={() => navigate('/settings/plans')} />
            ))}
            <AdminOnlyNote isAdmin={isAdmin} />
          </div>
        )}
      </SettingsSection>

      <SettingsSection
        title="Hosted machines"
        description={
          current && (hasHosting(current) ? `${current.name}’s rates.` : `Hosting is on ${hostingPlansText(plans.data)}. Running rrotor yourself is free.`)
        }
      >
        {rates.isPending && <LoadingCard lines={3} />}
        <ApiErrorNotice error={rates.error} />
        {rates.data && ratePlans.length > 0 && (
          <>
            <HostingRates rates={rates.data} plans={ratePlans} />
            <p className={styles.note}>{ratesNote}</p>
          </>
        )}
      </SettingsSection>
    </>
  );
}
