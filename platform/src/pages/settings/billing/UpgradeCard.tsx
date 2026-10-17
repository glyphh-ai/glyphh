import type { Plan } from '@/api/types';
import { money } from '@/lib/format';
import { Button, Card, CardEyebrow, Chip } from '@/ui';
import styles from './billing.module.css';

export function membersText(plan: Plan): string {
  const members = plan.limits.members;
  return members === null ? 'Unlimited members' : members === 1 ? '1 member' : `${members} members`;
}

export function UpgradeCard({ plan, isAdmin, onUpgrade }: { plan: Plan; isAdmin: boolean; onUpgrade: () => void }) {
  const installs = plan.limits.installs;
  return (
    <Card>
      <div className={styles.headLine}>
        <div className={styles.headText}>
          <CardEyebrow>{money(plan.seat_price_cents)} / seat / month</CardEyebrow>
          <h3 className={styles.itemName}>{plan.name}</h3>
        </div>
        {isAdmin && <Button onClick={onUpgrade}>Upgrade</Button>}
      </div>
      <div className={styles.chips}>
        <Chip tone="violet">{membersText(plan)}</Chip>
      </div>
      {installs !== null && <p className={styles.description}>Up to {installs} installs, and every add-on.</p>}
    </Card>
  );
}
