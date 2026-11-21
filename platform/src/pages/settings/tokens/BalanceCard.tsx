import { useState } from 'react';
import type { Balance } from '@/api/types';
import { cx } from '@/lib/cx';
import { dollars, micros } from '@/lib/format';
import { Button, Card, Chip, Icon } from '@/ui';
import usageStyles from '../UsagePage.module.css';
import { AddFundsDialog } from './AddFundsDialog';
import styles from './tokens.module.css';

/** The balance in microdollars, exact when the server sends micros. */
export const balanceMicros = (balance: Balance) => micros(balance.cents, balance.micros);

/**
 * The overage balance in dollars, what draws on it, and for the admin Add funds (`adding` opens it at once, as a link
 * from a refusal does). It may be a little below nothing: a reply is charged after it is sent.
 */
export function BalanceCard({ balance, isAdmin, adding = false }: { balance: Balance; isAdmin: boolean; adding?: boolean }) {
  const [open, setOpen] = useState(adding && isAdmin);
  const amount = balanceMicros(balance);
  return (
    <Card aria-label="Overage balance">
      <div className={usageStyles.meterHead}>
        <Icon name="card" />
        Overage balance
      </div>
      <div className={styles.line}>
        <span className={cx(styles.balance, amount < 0 && styles.negative)}>{dollars(amount)}</span>
        {amount <= 0 ? <Chip tone="red">Empty</Chip> : balance.low && <Chip tone="amber">Running low</Chip>}
      </div>
      <p className={styles.meta}>
        {amount <= 0
          ? 'Past your plan’s tokens a month, hosted models stop until you add funds.'
          : 'Past your plan’s tokens a month, hosted models are charged here in dollars.'}
      </p>
      {isAdmin ? (
        <div className={styles.actions}>
          <Button variant="primary" icon="plus" onClick={() => setOpen(true)}>
            Add funds
          </Button>
        </div>
      ) : (
        <p className={styles.meta}>Only your org’s admin can add funds.</p>
      )}
      {isAdmin && <AddFundsDialog open={open} onClose={() => setOpen(false)} />}
    </Card>
  );
}
