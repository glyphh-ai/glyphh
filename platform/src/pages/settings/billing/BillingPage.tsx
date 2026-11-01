import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { keys, useMe, usePlans } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { LoadingCard, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from '../SettingsTitle';
import settings from '../settings.module.css';
import { PlanCard } from './PlanCard';

export function BillingPage() {
  const me = useMe();
  const plans = usePlans();
  const toast = useToast();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();

  // Stripe's checkout and portal send the browser back with ?done=1: read everything afresh.
  const done = params.get('done');
  useEffect(() => {
    if (!done) return;
    for (const queryKey of [keys.me, keys.org, keys.licenceKeys]) void client.invalidateQueries({ queryKey });
    toast.show('Billing is up to date.');
    setParams({}, { replace: true });
  }, [done, client, setParams, toast]);

  const isAdmin = me.data?.role === 'admin';

  return (
    <>
      <SettingsTitle title="Billing" />
      {/* The other plans are on Manage, Change plan (his order, 2026-10-20), not listed here. */}
      <SettingsSection title="Subscription" description="Your plan. Members and installs are unlimited on every plan.">
        {me.isPending && <LoadingCard lines={4} />}
        <ApiErrorNotice error={me.error ?? plans.error} />
        {me.data && (
          <div className={settings.cards}>
            <PlanCard me={me.data} isAdmin={isAdmin} />
            <AdminOnlyNote isAdmin={isAdmin} />
          </div>
        )}
      </SettingsSection>
    </>
  );
}
