import { Link } from 'react-router';
import { useRuntime, useStartRuntime } from '@/api/queries';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, CopyField, LoadingCard } from '@/ui';
import styles from './GettingStarted.module.css';

/** Glyphh runs it: the same Start as Home, then the connector URL once it has an address. */
export function HostedChoice() {
  const runtime = useRuntime();
  const start = useStartRuntime();
  const data = runtime.data;

  if (runtime.isPending) return <LoadingCard lines={2} />;
  if (runtime.error) return <ApiErrorNotice error={runtime.error} />;

  const running = data?.state === 'online' || data?.state === 'offline';
  return (
    <div className={styles.part}>
      {!running && (
        <div className={styles.actions}>
          <Button variant="primary" onClick={() => start.mutate()} loading={start.isPending} disabled={data?.paused}>
            {data?.state === 'none' ? 'Start your runtime' : 'Start'}
          </Button>
        </div>
      )}
      {data?.paused && (
        <span className={styles.meta}>
          Paused: this month’s hours are used up. See <Link to="/settings/billing">Billing</Link>.
        </span>
      )}
      {data?.state === 'none' && <span className={styles.meta}>Starting it the first time makes it, at an address of its own.</span>}
      <ApiErrorNotice error={start.error} />
      {data?.address && (
        <>
          <h3 className={styles.subTitle}>Connect Claude</h3>
          <CopyField value={`${data.address}/mcp`} label="connector URL" />
          <span className={styles.meta}>
            Add it in Claude as a custom connector. You’ll be asked to allow it once. <Link to="/">Home</Link> shows the runtime.
          </span>
        </>
      )}
    </div>
  );
}
