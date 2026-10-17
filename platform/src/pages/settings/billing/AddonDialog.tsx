import { useEffect } from 'react';
import { useAddAddon, useCheckout, usePreviewAddon, useRemoveAddon } from '@/api/queries';
import type { Addon, Me } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { money } from '@/lib/format';
import { Button, Dialog, Skeleton } from '@/ui';
import { isSubscribed } from './billingStatus';
import styles from './billing.module.css';

/**
 * Adds or removes an add-on. With a subscription, the server first quotes the prorated amount,
 * and the change is made at that same proration date. Without one, adding goes through Stripe's checkout.
 */
export function AddonDialog({ me, addon, onClose }: { me: Me; addon: Addon; onClose: () => void }) {
  const action = addon.added ? 'remove' : 'add';
  const subscribed = isSubscribed(me.org.billing_status);
  const preview = usePreviewAddon();
  const add = useAddAddon();
  const remove = useRemoveAddon();
  const checkout = useCheckout();

  const { mutate: quote } = preview;
  useEffect(() => {
    if (subscribed) quote({ mod: addon.mod, action });
  }, [subscribed, quote, addon.mod, action]);

  const quoteData = preview.data;
  const pending = add.isPending || remove.isPending || checkout.isPending;

  const confirm = () => {
    if (!subscribed) {
      checkout.mutate(
        { plan: me.plan.name, seats: Math.max(1, me.org.seats), addons: [addon.mod] },
        { onSuccess: ({ url }) => window.location.assign(url) },
      );
      return;
    }
    // With a subscription the button stays disabled until the quote is in.
    const body = { mod: addon.mod, proration_date: quoteData!.proration_date };
    (action === 'add' ? add : remove).mutate(body, { onSuccess: onClose });
  };

  const title = action === 'add' ? `Add ${addon.name}` : `Remove ${addon.name}`;

  return (
    <Dialog
      open
      onClose={onClose}
      title={title}
      description={addon.description}
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant={action === 'add' ? 'primary' : 'danger'} loading={pending} disabled={subscribed && !quoteData} onClick={confirm}>
            {!subscribed ? 'Continue to Stripe' : action === 'add' ? 'Add' : 'Remove'}
          </Button>
        </>
      }
    >
      {subscribed && (
        <dl className={styles.quote}>
          <div>
            <dt>Now</dt>
            <dd>
              {quoteData ? (
                quoteData.prorated_cents < 0 ? (
                  `${money(-quoteData.prorated_cents, quoteData.currency)} credit`
                ) : (
                  money(quoteData.prorated_cents, quoteData.currency)
                )
              ) : (
                <Skeleton width={64} />
              )}
            </dd>
          </div>
          <div>
            <dt>Then</dt>
            <dd>{quoteData ? `${money(quoteData.monthly_cents, quoteData.currency)} a month` : <Skeleton width={96} />}</dd>
          </div>
        </dl>
      )}
      <ApiErrorNotice error={preview.error ?? add.error ?? remove.error ?? checkout.error} />
    </Dialog>
  );
}
