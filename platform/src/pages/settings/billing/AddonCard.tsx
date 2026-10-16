import type { Addon } from '@/api/types';
import { money } from '@/lib/format';
import { Card, CardEyebrow, Chip, Switch } from '@/ui';
import styles from './billing.module.css';

type AddonCardProps = {
  addon: Addon;
  planName: string;
  isAdmin: boolean;
  onToggle: () => void;
};

/** Each limit as words: "3 models · 10,000 precedents", unlimited ones as "unlimited models". */
export function limitsText(limits: Addon['limits']): string | null {
  if (!limits) return null;
  const parts = Object.entries(limits).map(([name, value]) => (value === null ? `unlimited ${name}` : `${value.toLocaleString('en-GB')} ${name}`));
  return parts.length ? parts.join(' · ') : null;
}

export function AddonCard({ addon, planName, isAdmin, onToggle }: AddonCardProps) {
  const limits = limitsText(addon.limits);
  return (
    <Card>
      <div className={styles.headLine}>
        <div className={styles.headText}>
          <CardEyebrow>
            {money(addon.price_cents)} {addon.per_seat ? '/ seat / month' : '/ month'}
          </CardEyebrow>
          <h3 className={styles.itemName}>{addon.name}</h3>
        </div>
        <Switch checked={addon.added} onChange={onToggle} label={`${addon.name} add-on`} disabled={!isAdmin || (!addon.added && !addon.allowed)} />
      </div>
      <div className={styles.chips}>
        {limits && <Chip>{`${limits} on ${planName}`}</Chip>}
        {!addon.allowed && !addon.added && <Chip tone="amber">{`Not available on ${planName}`}</Chip>}
      </div>
      <p className={styles.description}>{addon.description}</p>
    </Card>
  );
}
