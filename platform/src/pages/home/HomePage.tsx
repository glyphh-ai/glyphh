import { Link } from 'react-router';
import { useMe, useRuntime, useStartRuntime, useStopRuntime } from '@/api/queries';
import type { Runtime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, hours } from '@/lib/format';
import { useCopy } from '@/lib/useCopy';
import { Button, Card, Chip, CopyButton, CopyField, EmptyState, ErrorNotice, LoadingCard, ProgressBar, type ChipTone } from '@/ui';
import styles from './HomePage.module.css';

const stateChip: Record<Exclude<Runtime['state'], 'none'>, { label: string; tone: ChipTone }> = {
  online: { label: 'Running', tone: 'green' },
  offline: { label: 'Offline', tone: 'amber' },
  stopped: { label: 'Stopped', tone: 'neutral' },
};

export function HomePage() {
  const runtime = useRuntime();
  const me = useMe();
  const start = useStartRuntime();
  const stop = useStopRuntime();
  const { copied, copy } = useCopy();

  const data = runtime.data;
  const connector = data?.address ? `${data.address}/mcp` : null;
  const running = data?.state === 'online' || data?.state === 'offline';

  const actions = data && data.state !== 'none' && (
    <>
      {running ? (
        <Button onClick={() => stop.mutate()} loading={stop.isPending}>
          Stop
        </Button>
      ) : (
        <Button onClick={() => start.mutate()} loading={start.isPending} disabled={data.paused}>
          Start
        </Button>
      )}
      {connector && (
        <Button variant="primary" icon={copied ? 'check' : undefined} onClick={() => void copy(connector)}>
          {copied ? 'Copied' : 'Copy connector URL'}
        </Button>
      )}
    </>
  );

  return (
    <>
      <PageHeader
        title="Home"
        description={
          <>
            Your runtime and how to reach it. Claude connects to its address; your apps call it with an <Link to="/keys">API key</Link>.
          </>
        }
        actions={actions}
      />

      <div className={styles.stack}>
        <ApiErrorNotice error={start.error ?? stop.error} />

        {runtime.isPending && <LoadingCard />}
        {runtime.error && <ApiErrorNotice error={runtime.error} />}

        {data?.state === 'none' && (
          <EmptyState
            icon="home"
            title="No runtime yet"
            action={
              <Button variant="primary" onClick={() => start.mutate()} loading={start.isPending}>
                Start your runtime
              </Button>
            }
          >
            Starting it the first time makes it, at an address of its own. New here, or running it yourself?{' '}
            <Link to="/getting-started">Getting started</Link> walks you through it.
          </EmptyState>
        )}

        {data && data.state !== 'none' && (
          <>
            {data.paused && (
              <ErrorNotice
                message="Paused: this month’s hours are used up."
                action={<Link to="/settings/billing">Billing</Link>}
              />
            )}

            <Card>
              <div className={styles.addressLine}>
                <span className={styles.address}>{data.address ?? 'Address not ready yet'}</span>
                {data.address && <CopyButton value={data.address} label="address" />}
              </div>
              <div className={styles.chips}>
                <Chip tone={stateChip[data.state].tone} dot={data.state === 'online'}>
                  {stateChip[data.state].label}
                </Chip>
                {me.data && <Chip tone="violet">{me.data.plan.name}</Chip>}
                {data.region && <Chip>{data.region}</Chip>}
                {data.image_version && <Chip mono>{data.image_version}</Chip>}
              </div>
              {data.last_seen_at && <span className={styles.meta}>Last seen {ago(data.last_seen_at)}</span>}
            </Card>

            <div className={styles.grid}>
              {connector && (
                <Card>
                  <h2 className={styles.cardTitle}>Connect Claude</h2>
                  <CopyField value={connector} label="connector URL" />
                  <span className={styles.meta}>Add it in Claude as a custom connector. You’ll be asked to allow it once.</span>
                </Card>
              )}
              <Card>
                <h2 className={styles.cardTitle}>This month</h2>
                <div className={styles.hours}>
                  <span className={styles.hoursValue}>{hours(data.seconds_used)}</span>
                  <span className={styles.meta}>{data.hours_allowed === null ? 'hours, no limit' : `of ${data.hours_allowed} hours`}</span>
                </div>
                {data.hours_allowed !== null && (
                  <ProgressBar value={hours(data.seconds_used)} max={data.hours_allowed} label="Runtime hours used this month" />
                )}
              </Card>
            </div>
          </>
        )}
      </div>
    </>
  );
}
