import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router';
import { keys, useHosting, useMe, usePlans, useRates } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { LoadingCard, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from '../SettingsTitle';
import settings from '../settings.module.css';
import { contractRates, HostingRates, ratesNote } from './HostingRates';
import { PlanCard } from './PlanCard';
import { hasHosting, hostingPlansText } from './plans';
import { UpgradeCard } from './UpgradeCard';
import styles from './billing.module.css';

export function BillingPage() {
  const me = useMe();
  const plans = usePlans();
  const rates = useRates();
  const hosting = useHosting();
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
  // The rates of the plan in force, or, on a plan without hosting, of the self-serve plans that have it. A plan sold
  // by contract has its rates in the contract.
  const contract = current !== undefined && !current.self_serve;
  const ratePlans = current && hasHosting(current) ? [current] : list.filter((plan) => plan.self_serve && hasHosting(plan));

  return (
    <>
      <SettingsTitle title="Billing" />
      <SettingsSection title="Subscription" description="Your plan, and the plans above it. Members and installs are unlimited on every plan.">
        {(me.isPending || (me.data && hosting === undefined)) && <LoadingCard lines={4} />}
        <ApiErrorNotice error={me.error ?? plans.error} />
        {me.data && hosting !== undefined && (
          <div className={settings.cards}>
            <PlanCard me={me.data} isAdmin={isAdmin} hosting={hosting} />
            {upgrades.map((plan) => (
              <UpgradeCard key={plan.name} plan={plan} isAdmin={isAdmin} hosting={hosting} onUpgrade={() => navigate('/settings/plans')} />
            ))}
            <AdminOnlyNote isAdmin={isAdmin} />
          </div>
        )}
      </SettingsSection>

      {/* While Glyphh hosts nothing, there are no rates to show. */}
      {hosting && (
        <SettingsSection
          title="Hosted machines"
          description={
            current &&
            (contract
              ? `${current.name}’s rates: ${contractRates.toLowerCase()}`
              : hasHosting(current)
                ? `${current.name}’s rates.`
                : `Hosting is on ${hostingPlansText(plans.data)}. Running rrotor yourself is free.`)
          }
        >
          {!contract && rates.isPending && <LoadingCard lines={3} />}
          {!contract && <ApiErrorNotice error={rates.error} />}
          {!contract && rates.data && ratePlans.length > 0 && (
            <>
              <HostingRates rates={rates.data} plans={ratePlans} />
              <p className={styles.note}>{ratesNote}</p>
            </>
          )}
        </SettingsSection>
      )}
    </>
  );
}
