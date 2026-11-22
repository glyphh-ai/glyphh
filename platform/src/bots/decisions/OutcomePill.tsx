import type { Decision } from '@/api/botDecisions';
import { cx } from '@/lib/cx';
import styles from './decisions.module.css';

/** What the gate said; corrected, what it is now in white with what it said struck through. */
export function OutcomePill({ decision }: { decision: Pick<Decision, 'outcome' | 'corrected' | 'now'> }) {
  const fixed = decision.corrected !== null && decision.corrected !== decision.outcome;
  return (
    <span className={cx(styles.outcome, fixed && styles.fixed)} title={fixed ? `Corrected from ${decision.outcome}` : undefined}>
      {fixed && <s>{decision.outcome ?? '—'}</s>}
      {decision.now ?? '—'}
    </span>
  );
}
