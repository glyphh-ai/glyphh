import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router';
import { keys, useBilling, useLedger, useLlmModels, useMe, usePlans } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { SettingsSection } from '@/layout/SettingsSection/SettingsSection';
import { EmptyState, LoadingCard, useToast } from '@/ui';
import { AdminOnlyNote, SettingsTitle } from '../SettingsTitle';
import settings from '../settings.module.css';
import { BalanceCard } from '../tokens/BalanceCard';
import { LedgerTable } from '../tokens/Ledger';
import { PlanCard } from './PlanCard';

export function BillingPage() {
  const me = useMe();
  const plans = usePlans();
  const billing = useBilling();
  const balance = billing.data?.balance ?? null;
  const ledger = useLedger(balance !== null);
  const models = useLlmModels();
  const toast = useToast();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  // ?add=1 (a refusal's Add funds link) opens Add funds; read once, as the page opens.
  const [adding] = useState(() => params.get('add') === '1');

  // Stripe's checkout and portal send the browser back with ?done=1: read everything afresh.
  const done = params.get('done');
  useEffect(() => {
    if (!done) return;
    for (const queryKey of [keys.me, keys.org, keys.licenceKeys, keys.billing]) void client.invalidateQueries({ queryKey });
    toast.show('Billing is up to date.');
    setParams({}, { replace: true });
  }, [done, client, setParams, toast]);

  // A top-up's checkout sends it back with ?topup=1: the funds land once Stripe tells the server it is paid.
  const topup = params.get('topup');
  useEffect(() => {
    if (!topup) return;
    void client.invalidateQueries({ queryKey: keys.billing });
    toast.show('Thanks. Your funds are added once the payment clears, usually within a minute.');
    setParams({}, { replace: true });
  }, [topup, client, setParams, toast]);

  useEffect(() => {
    if (params.get('add')) setParams({}, { replace: true });
  }, [params, setParams]);

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

      {/* Hosted models on: the prepaid balance tokens past the plan's month are charged to, in dollars. */}
      {balance && me.data && (
        <>
          <SettingsSection
            title="Overage balance"
            description="Glyphh’s hosted models draw on your plan’s tokens a month first. Past them, each request is charged here at the model’s rates."
          >
            <BalanceCard balance={balance} isAdmin={isAdmin} adding={adding} />
          </SettingsSection>
          <SettingsSection title="Balance history" description="Top-ups, grants, refunds and charges, newest first.">
            {ledger.isPending && <LoadingCard lines={3} />}
            <ApiErrorNotice error={ledger.error} />
            {ledger.data?.length === 0 && <EmptyState icon="card" title="Nothing yet" />}
            {ledger.data && ledger.data.length > 0 && <LedgerTable entries={ledger.data} models={models} />}
          </SettingsSection>
        </>
      )}
    </>
  );
}
