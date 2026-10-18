import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { ApiError } from '@/api/client';
import { useChangePlan, useCheckout, useMe, usePlans, useRates } from '@/api/queries';
import type { Plan } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { cx } from '@/lib/cx';
import { salesUrl } from '@/lib/links';
import { isSubscribed } from '@/pages/settings/billing/billingStatus';
import { HostingRates, ratesNote } from '@/pages/settings/billing/HostingRates';
import { hasHosting, planFacts, priceParts } from '@/pages/settings/billing/plans';
import { Avatar, Button, ButtonLink, Chip, Dialog, Icon, LoadingCard } from '@/ui';
import styles from './PlansPage.module.css';

const BILLING = '/settings/billing';

/**
 * Choosing a plan, over the whole window: no sidebar, closed with the X (or Escape) back to Billing. Each plan shows
 * what the server says it includes, and below them the hosted machine rates of each plan with hosting. With a
 * subscription a change applies at once (Stripe prorates it), after a confirm; without one, the person pays in
 * Stripe's checkout first. A plan sold by contract is Talk to us.
 */
export function PlansPage() {
  const navigate = useNavigate();
  const me = useMe();
  const plans = usePlans();
  const rates = useRates();
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
  const list = plans.data ?? [];
  const at = list.findIndex((plan) => plan.name === current?.name);
  // The next self-serve plan up is the one recommended.
  const recommended = list.find((plan, index) => index > at && plan.self_serve);
  const hosting = list.filter(hasHosting);
  const machinesInTheWay = change.error instanceof ApiError && change.error.code === 'E_CONFLICT' && change.error.detail.reason === 'machines';

  const closeConfirm = () => {
    change.reset();
    setSwitching(null);
  };

  const subscribed = me.data !== undefined && isSubscribed(me.data.org.billing_status);
  // A plan by contract changes with Glyphh, not here.
  const contract = current !== undefined && !current.self_serve;
  const choose = (plan: Plan) => {
    if (subscribed) setSwitching(plan);
    else checkout.mutate(plan.name, { onSuccess: ({ url }) => window.location.assign(url) });
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
        <p className={styles.subtitle}>Every plan has unlimited members, installs and self-hosted runtimes, with Ada included. Never priced per seat.</p>

        <ApiErrorNotice error={me.error ?? plans.error ?? checkout.error} />
        {(me.isPending || plans.isPending) && <LoadingCard lines={6} />}
        {me.data && plans.data && (
          <div className={styles.grid}>
            {plans.data.map((plan, index) => (
              <PlanOption
                key={plan.name}
                plan={plan}
                isCurrent={index === at}
                upgrade={index > at}
                // Without a subscription there is nothing to move down to Free from, and a contract plan moves with Glyphh.
                canChoose={isAdmin && !contract && (subscribed || plan.price_cents !== 0)}
                recommended={plan.name === recommended?.name}
                pending={checkout.isPending && checkout.variables === plan.name}
                onChoose={() => choose(plan)}
              />
            ))}
          </div>
        )}
        {me.data && !isAdmin && <p className={styles.note}>Only your org’s admin can change the plan.</p>}
        {me.data && isAdmin && contract && (
          <p className={styles.note}>
            Your plan is by contract. To change it, <a href={salesUrl}>talk to us</a>.
          </p>
        )}

        {rates.data && hosting.length > 0 && (
          <section className={styles.rates} aria-labelledby="rates-title">
            <h2 id="rates-title" className={styles.ratesTitle}>
              Hosted machines
            </h2>
            <p className={styles.note}>{ratesNote}</p>
            <HostingRates rates={rates.data} plans={hosting} />
          </section>
        )}
        <ApiErrorNotice error={rates.error} />
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
        <ApiErrorNotice error={change.error} action={machinesInTheWay ? <Link to="/machines">Machines</Link> : undefined} />
      </Dialog>
    </div>
  );
}

type PlanOptionProps = { plan: Plan; isCurrent: boolean; upgrade: boolean; canChoose: boolean; recommended: boolean; pending: boolean; onChoose: () => void };

function PlanOption({ plan, isCurrent, upgrade, canChoose, recommended, pending, onChoose }: PlanOptionProps) {
  const { amount, per } = priceParts(plan);

  return (
    <section className={cx(styles.card, recommended && styles.recommended)} aria-label={plan.name}>
      {recommended && <span className={styles.flag}>Recommended</span>}
      <div className={styles.nameLine}>
        <h2 className={styles.name}>{plan.name}</h2>
        {isCurrent && <Chip tone="green">Current plan</Chip>}
      </div>
      <p className={styles.price}>
        <span className={styles.amount}>{amount}</span>
        {per && <span className={styles.per}>per {per}</span>}
      </p>

      <ul className={styles.features}>
        {planFacts(plan).map((fact) => (
          <li key={fact.text}>
            <Icon name={fact.icon} />
            {fact.text}
          </li>
        ))}
      </ul>

      {isCurrent ? (
        <Button className={styles.choose} disabled>
          Current plan
        </Button>
      ) : !plan.self_serve ? (
        <ButtonLink className={styles.choose} href={salesUrl}>
          Talk to us
        </ButtonLink>
      ) : (
        canChoose && (
          <Button className={styles.choose} variant={recommended ? 'primary' : 'secondary'} loading={pending} onClick={onChoose}>
            {upgrade ? `Upgrade to ${plan.name}` : `Switch to ${plan.name}`}
          </Button>
        )
      )}
    </section>
  );
}
