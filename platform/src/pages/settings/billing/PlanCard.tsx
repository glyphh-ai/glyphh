import { useNavigate } from 'react-router';
import { usePortal } from '@/api/queries';
import type { Me } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { date, money } from '@/lib/format';
import { Button, Card, CardEyebrow, Chip, Menu, MenuItem } from '@/ui';
import { isSubscribed, statusChip } from './billingStatus';
import { factText, hasHosting, planFacts, priceText } from './plans';
import { contractRates } from './HostingRates';
import styles from './billing.module.css';

/**
 * The org's plan: its price, renewal, what it includes, hosting so far this month, and the ways to change it. While
 * Glyphh hosts nothing (`hosting` false) it says nothing of hosting.
 */
export function PlanCard({ me, isAdmin, hosting }: { me: Me; isAdmin: boolean; hosting: boolean }) {
  const portal = usePortal();
  const navigate = useNavigate();
  const { plan, org } = me;
  const subscribed = isSubscribed(org.billing_status);
  const status = statusChip(org.billing_status);

  return (
    <Card>
      <CardEyebrow>{priceText(plan)}</CardEyebrow>
      <div className={styles.titleLine}>
        <h3 className={styles.planName}>{plan.name}</h3>
        {status ? <Chip tone={status.tone}>{status.label}</Chip> : org.renews_at && <Chip tone="green">Renews {date(org.renews_at)}</Chip>}
        {org.plan_until && <Chip>Until {date(org.plan_until)}</Chip>}
      </div>
      <div className={styles.chips}>
        {planFacts(plan, me.ada_cloud === true).map((fact) => (
          <Chip key={fact.text}>{factText(fact)}</Chip>
        ))}
      </div>
      {hosting && !plan.self_serve && <p className={styles.description}>Hosting rates: {contractRates.toLowerCase()}</p>}

      {/* With Ada Cloud on, the month's requests in place of hosting: the count, and what is past it on a metered plan. */}
      {me.ada_cloud === true && me.cloud && (
        <div className={styles.usageLine}>
          <span>Requests this month</span>
          <span>
            {me.cloud.requests.max === null
              ? me.cloud.requests.used.toLocaleString('en-GB')
              : `${me.cloud.requests.used.toLocaleString('en-GB')} of ${me.cloud.requests.max.toLocaleString('en-GB')}`}
            {me.cloud.requests.over > 0 && ` · ${me.cloud.requests.over.toLocaleString('en-GB')} over`}
          </span>
        </div>
      )}

      {hosting && hasHosting(plan) && (
        <div className={styles.usageLine}>
          <span>Hosting this month</span>
          <span>{money(me.hosting.month_to_date_cents)}</span>
        </div>
      )}

      {isAdmin && (
        <div className={styles.actions}>
          <Button onClick={() => navigate('/usage')}>Usage</Button>
          <Menu
            label="Manage billing"
            placement="bottom-end"
            trigger={({ open, toggle, id }) => (
              <Button iconEnd="chevronDown" onClick={toggle} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} loading={portal.isPending}>
                Manage
              </Button>
            )}
          >
            <MenuItem icon="card" onSelect={() => navigate('/settings/plans')}>
              Change plan
            </MenuItem>
            {subscribed && (
              <MenuItem icon="external" onSelect={() => portal.mutate(undefined, { onSuccess: ({ url }) => window.location.assign(url) })}>
                Invoices and payment
              </MenuItem>
            )}
          </Menu>
        </div>
      )}
      <ApiErrorNotice error={portal.error} />
    </Card>
  );
}
