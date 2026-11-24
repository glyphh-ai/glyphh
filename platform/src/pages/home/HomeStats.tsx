import { useState, type ReactNode } from 'react';
import { Link } from 'react-router';
import type { AdaUsage } from '@/api/ada';
import type { Balance, Billing, TokenUsage } from '@/api/types';
import { Ring } from '@/components/Ring';
import { cx } from '@/lib/cx';
import { date, dollars, micros } from '@/lib/format';
import { Button, Card, Chip, Icon, type IconName } from '@/ui';
import { AddFundsDialog } from '@/pages/settings/tokens/AddFundsDialog';
import { balanceMicros } from '@/pages/settings/tokens/BalanceCard';
import { priceText } from '@/pages/settings/billing/plans';
import styles from './home.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

function Stat({ icon, label, children }: { icon: IconName; label: string; children: ReactNode }) {
  return (
    <Card aria-label={label}>
      <div className={styles.stat}>
        <div className={styles.label}>
          <Icon name={icon} />
          {label}
        </div>
        {children}
      </div>
    </Card>
  );
}

/** The overage balance, with Add funds for the admin: what hosted models draw on past the plan's tokens. */
function BalanceStat({ balance, isAdmin }: { balance: Balance; isAdmin: boolean }) {
  const [open, setOpen] = useState(false);
  const amount = balanceMicros(balance);
  return (
    <Stat icon="card" label="Balance">
      <div className={styles.figure}>
        <span className={cx(styles.big, amount < 0 && styles.negative)}>{dollars(amount)}</span>
        {amount <= 0 ? <Chip tone="red">Empty</Chip> : balance.low && <Chip tone="amber">Running low</Chip>}
      </div>
      <p className={styles.meta}>For hosted models past your plan’s tokens.</p>
      <div className={styles.foot}>
        <Link to="/settings/billing" className={styles.link}>
          Billing
        </Link>
        {isAdmin && (
          <Button size="sm" variant="primary" icon="plus" onClick={() => setOpen(true)}>
            Add funds
          </Button>
        )}
      </div>
      {isAdmin && <AddFundsDialog open={open} onClose={() => setOpen(false)} />}
    </Stat>
  );
}

/** The plan, where there is no balance to show: its name, price and renewal. */
function PlanStat({ billing }: { billing: Billing }) {
  return (
    <Stat icon="card" label="Plan">
      <span className={styles.big}>{billing.plan.name}</span>
      <p className={styles.meta}>{billing.renews_at ? `${priceText(billing.plan)} · renews ${date(billing.renews_at)}` : priceText(billing.plan)}</p>
      <div className={styles.foot}>
        <Link to="/settings/plans" className={styles.link}>
          Change plan
        </Link>
      </div>
    </Stat>
  );
}

/** The month's tokens against the plan's, as a ring, and what went on the balance past them. */
function TokensStat({ tokens }: { tokens: TokenUsage }) {
  const total = tokens.used + tokens.over_used;
  const charged = tokens.models.reduce((sum, m) => sum + micros(m.charged_cents), 0);
  return (
    <Stat icon="layers" label="Tokens this month">
      <div className={styles.figure}>
        <div>
          <span className={styles.big}>{n(total)}</span>
          <span className={styles.of}>{tokens.max === null ? 'by contract' : `of ${n(tokens.max)} in your plan`}</span>
        </div>
        {tokens.max !== null && <Ring value={total} max={tokens.max} label="Tokens this month" />}
      </div>
      <p className={styles.meta}>{charged > 0 ? `${dollars(charged)} charged past the plan.` : `Starts again on ${date(tokens.resets_at)}.`}</p>
      <div className={styles.foot}>
        <Link to="/usage" className={styles.link}>
          Usage
        </Link>
      </div>
    </Stat>
  );
}

/** Ada Cloud's requests this month against the plan's, as a ring. */
function RequestsStat({ usage }: { usage: AdaUsage }) {
  const { used, max, over } = usage.requests;
  return (
    <Stat icon="monitor" label="Requests this month">
      <div className={styles.figure}>
        <div>
          <span className={styles.big}>{n(used)}</span>
          <span className={styles.of}>{max === null ? 'no limit' : `of ${n(max)} in your plan`}</span>
        </div>
        {max !== null && <Ring value={used} max={max} label="Requests this month" />}
      </div>
      <p className={styles.meta}>
        {over > 0 ? `${n(over)} past the month, billed.` : `${n(usage.precedents.used)} precedents across ${usage.models === 1 ? '1 model' : `${n(usage.models)} models`}.`}
      </p>
      <div className={styles.foot}>
        <Link to="/models" className={styles.link}>
          Models
        </Link>
      </div>
    </Stat>
  );
}

/** Home's row of numbers: the balance (or the plan), the month's tokens and Ada's requests, each as the server has them. */
export function HomeStats({ billing, usage, isAdmin }: { billing: Billing; usage: AdaUsage | undefined; isAdmin: boolean }) {
  return (
    <div className={styles.row}>
      {billing.balance ? <BalanceStat balance={billing.balance} isAdmin={isAdmin} /> : <PlanStat billing={billing} />}
      {billing.tokens && <TokensStat tokens={billing.tokens} />}
      {usage && <RequestsStat usage={usage} />}
    </div>
  );
}
