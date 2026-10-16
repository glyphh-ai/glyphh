import { useState } from 'react';
import { useChangePlan, useCheckout } from '@/api/queries';
import type { Me, Plan } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { money } from '@/lib/format';
import { Button, Dialog } from '@/ui';
import { isSubscribed } from './billingStatus';
import { membersText } from './UpgradeCard';
import styles from './billing.module.css';

type ChangePlanDialogProps = {
  me: Me;
  plans: Plan[];
  initial?: Plan;
  onClose: () => void;
};

/**
 * Picks a plan. With a subscription the change applies at once (Stripe prorates it);
 * without one, the person pays in Stripe's checkout first.
 */
export function ChangePlanDialog({ me, plans, initial, onClose }: ChangePlanDialogProps) {
  const [chosen, setChosen] = useState(initial?.name ?? me.plan.name);
  const change = useChangePlan();
  const checkout = useCheckout();
  const subscribed = isSubscribed(me.org.billing_status);
  const plan = plans.find((p) => p.name === chosen);
  const pending = change.isPending || checkout.isPending;

  // The button stays disabled until a plan other than the current one is chosen.
  const confirm = () => {
    const { name } = plan!;
    if (subscribed) {
      change.mutate(name, { onSuccess: onClose });
    } else {
      checkout.mutate({ plan: name, seats: Math.max(1, me.used.seats), addons: [] }, { onSuccess: ({ url }) => window.location.assign(url) });
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Change plan"
      description={subscribed ? 'The change applies now. Stripe prorates the difference on your next invoice.' : 'You’ll pay in Stripe, then come back here.'}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={pending} disabled={!plan || plan.name === me.plan.name} onClick={confirm}>
            {subscribed ? 'Change plan' : 'Continue to Stripe'}
          </Button>
        </>
      }
    >
      <fieldset className={styles.choices}>
        <legend className="visually-hidden">Plan</legend>
        {plans.map((option) => (
          <label key={option.name} className={styles.choice}>
            <input type="radio" name="plan" value={option.name} checked={chosen === option.name} onChange={() => setChosen(option.name)} />
            <span className={styles.choiceText}>
              <span className={styles.choiceName}>
                {option.name}
                {option.name === me.plan.name && <span className={styles.muted}> · your plan</span>}
              </span>
              <span className={styles.muted}>
                {option.seat_price_cents > 0 ? `${money(option.seat_price_cents)} / seat / month` : 'Free'} · {membersText(option)}
              </span>
            </span>
          </label>
        ))}
      </fieldset>
      <ApiErrorNotice error={change.error ?? checkout.error} />
    </Dialog>
  );
}
