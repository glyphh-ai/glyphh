import { useNavigate } from 'react-router';
import { usePortal } from '@/api/queries';
import type { Me, Runtime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { date, hours, money, plural } from '@/lib/format';
import { Button, Card, CardEyebrow, Chip, Menu, MenuItem, ProgressBar } from '@/ui';
import { isSubscribed, statusChip } from './billingStatus';
import styles from './billing.module.css';

type PlanCardProps = {
  me: Me;
  runtime: Runtime | undefined;
  isAdmin: boolean;
  onChangeSeats: () => void;
};

export function PlanCard({ me, runtime, isAdmin, onChangeSeats }: PlanCardProps) {
  const portal = usePortal();
  const navigate = useNavigate();
  const { plan, org } = me;
  const subscribed = isSubscribed(org.billing_status);
  const status = statusChip(org.billing_status);
  const price = plan.seat_price_cents > 0 ? `${money(plan.seat_price_cents)} / seat / month · ${plural(org.seats, 'seat')}` : 'Free';

  return (
    <Card>
      <CardEyebrow>{price}</CardEyebrow>
      <div className={styles.titleLine}>
        <h3 className={styles.planName}>{plan.name}</h3>
        {status ? <Chip tone={status.tone}>{status.label}</Chip> : org.renews_at && <Chip tone="green">Renews {date(org.renews_at)}</Chip>}
      </div>

      {runtime && runtime.hours_allowed !== null && (
        <div className={styles.usage}>
          <div className={styles.usageLine}>
            <span>Runtime hours</span>
            <span>
              {hours(runtime.seconds_used)} <span className={styles.muted}>of</span> {runtime.hours_allowed}
            </span>
          </div>
          <ProgressBar value={hours(runtime.seconds_used)} max={runtime.hours_allowed} label="Runtime hours used this month" />
        </div>
      )}

      {isAdmin && (
        <div className={styles.actions}>
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
              <MenuItem icon="team" onSelect={onChangeSeats}>
                Change seats
              </MenuItem>
            )}
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
