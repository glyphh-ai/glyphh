import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { keys, useAddons, useMe, usePlans, useRuntime } from '@/api/queries';
import type { Addon, Plan } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { LoadingCard, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from '../SettingsTitle';
import settings from '../settings.module.css';
import { AddonCard } from './AddonCard';
import { AddonDialog } from './AddonDialog';
import { ChangePlanDialog } from './ChangePlanDialog';
import { PlanCard } from './PlanCard';
import { SeatsDialog } from './SeatsDialog';
import { UpgradeCard } from './UpgradeCard';

type Open = { kind: 'plan'; plan?: Plan } | { kind: 'seats' } | { kind: 'addon'; addon: Addon } | null;

export function BillingPage() {
  const me = useMe();
  const plans = usePlans();
  const addons = useAddons();
  const runtime = useRuntime();
  const toast = useToast();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState<Open>(null);

  // Stripe's checkout and portal send the browser back with ?done=1: read everything afresh.
  const done = params.get('done');
  useEffect(() => {
    if (!done) return;
    for (const queryKey of [keys.me, keys.org, keys.addons]) void client.invalidateQueries({ queryKey });
    toast.show('Billing is up to date.');
    setParams({}, { replace: true });
  }, [done, client, setParams, toast]);

  const isAdmin = me.data?.role === 'admin';
  const current = me.data?.plan;
  const upgrades = (plans.data ?? []).filter((plan) => current && plan.name !== current.name && plan.seat_price_cents > current.seat_price_cents);

  return (
    <>
      <SettingsTitle title="Billing" />
      <SettingsSection title="Subscription" description="Your plan, seats and add-ons.">
        {(me.isPending || addons.isPending) && <LoadingCard lines={4} />}
        <ApiErrorNotice error={me.error ?? addons.error ?? plans.error} />
        {me.data && (
          <div className={settings.cards}>
            <PlanCard
              me={me.data}
              runtime={runtime.data}
              isAdmin={isAdmin}
              onChangePlan={() => setOpen({ kind: 'plan' })}
              onChangeSeats={() => setOpen({ kind: 'seats' })}
            />
            {addons.data?.map((addon) => (
              <AddonCard key={addon.mod} addon={addon} planName={me.data.plan.name} isAdmin={isAdmin} onToggle={() => setOpen({ kind: 'addon', addon })} />
            ))}
            {upgrades.map((plan) => (
              <UpgradeCard key={plan.name} plan={plan} isAdmin={isAdmin} onUpgrade={() => setOpen({ kind: 'plan', plan })} />
            ))}
            <AdminOnlyNote isAdmin={isAdmin} />
          </div>
        )}
      </SettingsSection>

      {me.data && open?.kind === 'plan' && (
        <ChangePlanDialog me={me.data} plans={plans.data ?? []} initial={open.plan} onClose={() => setOpen(null)} />
      )}
      {me.data && open?.kind === 'seats' && <SeatsDialog me={me.data} onClose={() => setOpen(null)} />}
      {me.data && open?.kind === 'addon' && <AddonDialog me={me.data} addon={open.addon} onClose={() => setOpen(null)} />}
    </>
  );
}
