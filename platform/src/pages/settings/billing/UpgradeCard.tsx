import type { Plan } from '@/api/types';
import { salesUrl } from '@/lib/links';
import { Button, ButtonLink, Card, CardEyebrow, Chip } from '@/ui';
import { factText, planFacts, priceText } from './plans';
import { contractRates } from './HostingRates';
import styles from './billing.module.css';

/**
 * A plan above this one: its price and what it adds, a feature not yet built as coming soon. Upgrade for a self-serve
 * plan, Talk to us for one by contract.
 */
export function UpgradeCard({ plan, isAdmin, hosting, onUpgrade }: { plan: Plan; isAdmin: boolean; hosting: boolean; onUpgrade: () => void }) {
  return (
    <Card aria-label={plan.name}>
      <div className={styles.headLine}>
        <div className={styles.headText}>
          <CardEyebrow>{priceText(plan)}</CardEyebrow>
          <h3 className={styles.itemName}>{plan.name}</h3>
        </div>
        {plan.self_serve ? isAdmin && <Button onClick={onUpgrade}>Upgrade</Button> : <ButtonLink href={salesUrl}>Talk to us</ButtonLink>}
      </div>
      <div className={styles.chips}>
        {planFacts(plan).map((fact) => (
          <Chip key={fact.text} tone={fact.icon === 'check' && !fact.soon ? 'violet' : 'neutral'}>
            {factText(fact)}
          </Chip>
        ))}
      </div>
      {hosting && !plan.self_serve && <p className={styles.description}>Hosting rates: {contractRates.toLowerCase()}</p>}
    </Card>
  );
}
