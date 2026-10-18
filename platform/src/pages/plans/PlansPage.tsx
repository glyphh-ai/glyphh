import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { useChangePlan, useCheckout, useMe, usePlans } from '@/api/queries';
import type { Me, Plan } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { cx } from '@/lib/cx';
import { money } from '@/lib/format';
import { isSubscribed } from '@/pages/settings/billing/billingStatus';
import { membersText } from '@/pages/settings/billing/UpgradeCard';
import { Avatar, Button, Chip, Dialog, Icon, LoadingCard, type IconName } from '@/ui';
import styles from './PlansPage.module.css';

const BILLING = '/settings/billing';

/**
 * Choosing a plan, over the whole window: no sidebar, closed with the X (or Escape) back to Billing. Each plan shows
 * what the server says it includes. With a subscription a change applies at once (Stripe prorates it), after a
 * confirm; without one, the person pays in Stripe's checkout first.
 */
export function PlansPage() {
  const navigate = useNavigate();
  const me = useMe();
  const plans = usePlans();
  const [switching, setSwitching] = useState<Plan | null>(null);
  const change = useChangePlan();
  const checkout = useCheckout();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !document.querySelector('dialog[open]')) navigate(BILLING);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navigate]);

  const current = me.data?.plan;
  const isAdmin = me.data?.role === 'admin';
  const recommended = (plans.data ?? []).find((plan) => current && plan.seat_price_cents > current.seat_price_cents);

  const closeConfirm = () => {
    change.reset();
    setSwitching(null);
  };

  const choose = (plan: Plan) => {
    const { org, used } = me.data!;
    if (isSubscribed(org.billing_status)) setSwitching(plan);
    else checkout.mutate({ plan: plan.name, seats: Math.max(1, used.seats), addons: [] }, { onSuccess: ({ url }) => window.location.assign(url) });
  };

  return (
    <div className={styles.overlay}>
      <header className={styles.bar}>
        <span className={styles.who}>
          {me.data && (
            <>
              <Avatar name={me.data.name ?? me.data.email} />
              {me.data.email}
            </>
          )}
        </span>
        <button type="button" className={styles.close} aria-label="Close" onClick={() => navigate(BILLING)}>
          <Icon name="close" size={18} />
        </button>
      </header>

      <main className={styles.page}>
        <h1 className={styles.title}>Choose a plan</h1>
        <p className={styles.subtitle}>Prices are per seat, per month.</p>

        <ApiErrorNotice error={me.error ?? plans.error ?? checkout.error} />
        {(me.isPending || plans.isPending) && <LoadingCard lines={6} />}
        {me.data && plans.data && (
          <div className={styles.grid}>
            {plans.data.map((plan) => (
              <PlanOption
                key={plan.name}
                plan={plan}
                me={me.data}
                isAdmin={isAdmin}
                recommended={plan.name === recommended?.name}
                pending={checkout.isPending && checkout.variables?.plan === plan.name}
                onChoose={() => choose(plan)}
              />
            ))}
          </div>
        )}
        {me.data && !isAdmin && <p className={styles.note}>Only your org’s admin can change the plan.</p>}
      </main>

      <Dialog
        open={switching !== null}
        onClose={closeConfirm}
        title={`Switch to ${switching?.name ?? ''}?`}
        description="The change applies now. Stripe prorates the difference on your next invoice."
        actions={
          <>
            <Button variant="ghost" onClick={closeConfirm}>
              Cancel
            </Button>
            <Button variant="primary" loading={change.isPending} onClick={() => switching && change.mutate(switching.name, { onSuccess: () => navigate(BILLING) })}>
              Switch plan
            </Button>
          </>
        }
      >
        <ApiErrorNotice error={change.error} />
      </Dialog>
    </div>
  );
}

type PlanOptionProps = { plan: Plan; me: Me; isAdmin: boolean; recommended: boolean; pending: boolean; onChoose: () => void };

function PlanOption({ plan, me, isAdmin, recommended, pending, onChoose }: PlanOptionProps) {
  const isCurrent = plan.name === me.plan.name;
  const upgrade = plan.seat_price_cents > me.plan.seat_price_cents;

  return (
    <section className={cx(styles.card, recommended && styles.recommended)} aria-label={plan.name}>
      {recommended && <span className={styles.flag}>Recommended</span>}
      <div className={styles.nameLine}>
        <h2 className={styles.name}>{plan.name}</h2>
        {isCurrent && <Chip tone="green">Current plan</Chip>}
      </div>
      <p className={styles.price}>
        <span className={styles.amount}>{money(plan.seat_price_cents)}</span>
        <span className={styles.per}>{plan.seat_price_cents > 0 ? 'per seat / month' : 'per month'}</span>
      </p>

      <ul className={styles.features}>
        {features(plan).map((feature) => (
          <li key={feature.text}>
            <Icon name={feature.icon} />
            {feature.text}
          </li>
        ))}
      </ul>

      {isCurrent ? (
        <Button className={styles.choose} disabled>
          Current plan
        </Button>
      ) : (
        isAdmin && (
          <Button className={styles.choose} variant={recommended ? 'primary' : 'secondary'} loading={pending} onClick={onChoose}>
            {upgrade ? `Upgrade to ${plan.name}` : `Switch to ${plan.name}`}
          </Button>
        )
      )}
    </section>
  );
}

/** What a plan includes, as the server states it: its members, its installs, and each mod's limits. */
function features(plan: Plan): Array<{ icon: IconName; text: string }> {
  const installs = plan.limits.installs;
  const list: Array<{ icon: IconName; text: string }> = [
    { icon: plan.limits.members === 1 ? 'user' : 'team', text: membersText(plan) },
    { icon: 'laptop', text: installs === null ? 'Unlimited installs per person' : `Up to ${installs} ${installs === 1 ? 'install' : 'installs'} per person` },
  ];
  for (const [mod, { limits }] of Object.entries(plan.mods)) {
    const parts = Object.entries(limits).map(([name, value]) => (value === null ? `unlimited ${name}` : `${value.toLocaleString()} ${name}`));
    list.push({ icon: 'model', text: parts.length ? `${mod[0]!.toUpperCase()}${mod.slice(1)}: ${parts.join(', ')}` : `${mod[0]!.toUpperCase()}${mod.slice(1)}` });
  }
  return list;
}
