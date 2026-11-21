import { Link } from 'react-router';
import { useBilling } from '@/api/queries';
import type { ConnectionUsage } from '@/api/types';
import { money } from '@/lib/format';
import { Card, Icon, ProgressBar } from '@/ui';
import usageStyles from '../UsagePage.module.css';
import styles from '../tokens/tokens.module.css';

const n = (value: number) => value.toLocaleString('en-GB');

/** What those past the plan's cost, in a line; nothing priced says so, never a made-up price. */
function priceLine({ included, over, cents_a_month: cents, due_cents: due }: ConnectionUsage): string {
  if (included === null) return 'Every connection is included in your plan.';
  if (cents === null) return `Past ${n(included)}, connections are not charged yet.`;
  if (over > 0) return `${n(over)} past the plan at ${money(cents)} each: ${money(due ?? 0)} a month.`;
  return `Past ${n(included)}, ${money(cents)} a connection a month.`;
}

/** The connections card among a Usage page's meters, as /v1/billing says them; nothing from a server without them. */
export function ConnectionsMeter() {
  const connections = useBilling().data?.connections;
  return connections ? <ConnectionsCard connections={connections} /> : null;
}

/** The org's connections to other services (its bots' accounts) against its plan's, and their price past it. */
export function ConnectionsCard({ connections }: { connections: ConnectionUsage }) {
  const { used, included } = connections;
  return (
    <Card aria-label="Connections">
      <div className={usageStyles.meterHead}>
        <Icon name="external" />
        Connections
      </div>
      <div className={usageStyles.value}>
        <span className={usageStyles.used}>{n(used)}</span>
        <span className={usageStyles.of}>{included === null ? (used === 1 ? 'connection' : 'connections') : `of ${n(included)} connections`}</span>
      </div>
      {included !== null && <ProgressBar value={Math.min(used, included)} max={included} label="Connections" />}
      <p className={styles.meta}>
        {priceLine(connections)} <Link to="/connections">See them</Link>
      </p>
    </Card>
  );
}
