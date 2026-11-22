import { Link } from 'react-router';
import { useApprovals, useBots } from '@/api/bots';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { EmptyState, Skeleton } from '@/ui';
import { SwarmWaiting } from '../swarms/parts';
import { WaitingRun } from './parts';
import cs from '../connections/connections.module.css';
import styles from './bots.module.css';

/**
 * Every run of the org's bots waiting on someone, oldest first, each answered (one item or a batch) or cancelled here;
 * and each swarm's pull request waiting for a merge or a reject.
 */
export function ApprovalsPage() {
  const approvals = useApprovals();
  const bots = useBots();
  const names = new Map((bots.data ?? []).map((b) => [b.slug, b.name]));

  return (
    <div className={cs.page}>
      <PageHeader
        title="Approvals"
        description="Your bots wait here when a step needs your yes: a tool that needs approval, or a gate that is not sure yet. What you answer, the gates learn. Your swarms’ pull requests wait here too."
      />
      <ApiErrorNotice error={approvals.error} />
      {approvals.isPending && (
        <div className={styles.stack} aria-busy="true" aria-label="Loading approvals">
          {Array.from({ length: 2 }, (_, i) => (
            <div key={i} className={styles.waiting} aria-hidden="true">
              <Skeleton height={14} width="30%" />
              <Skeleton height={16} width="70%" />
              <Skeleton height={32} width={200} />
            </div>
          ))}
        </div>
      )}
      {approvals.data?.length === 0 && (
        <EmptyState icon="check" title="Nothing is waiting on you">
          When a bot needs your approval, it shows here. <Link to="/bots">Your bots</Link>
        </EmptyState>
      )}
      {approvals.data && approvals.data.length > 0 && (
        <div className={styles.stack} aria-label="Waiting runs" role="list">
          {approvals.data.map((run) => (
            <div key={run.id} role="listitem">
              {run.kind === 'swarm' ? <SwarmWaiting run={run} /> : <WaitingRun run={run} botName={names.get(run.bot_slug)} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
