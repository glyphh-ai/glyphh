import { Link, useNavigate } from 'react-router';
import { useHosting, useMe, useRuntime, useStartRuntime, useStopRuntime } from '@/api/queries';
import type { Runtime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, money } from '@/lib/format';
import { useCopy } from '@/lib/useCopy';
import { StartMachineError } from '@/pages/machines/MachineFields';
import { useMachineCents } from '@/pages/machines/HostingUpsell';
import { Button, Card, Chip, CopyButton, CopyField, EmptyState, LoadingCard, type ChipTone } from '@/ui';
import styles from './HomePage.module.css';

const stateChip: Record<Exclude<Runtime['state'], 'none'>, { label: string; tone: ChipTone }> = {
  online: { label: 'Running', tone: 'green' },
  offline: { label: 'Offline', tone: 'amber' },
  stopped: { label: 'Stopped', tone: 'neutral' },
};

/**
 * The first hosted machine: its address, state, connector URL and cost this month. While Glyphh hosts nothing there is
 * no starting one, no cost and no Machines: Getting started shows how to run rrotor yourself.
 */
export function HomePage() {
  const navigate = useNavigate();
  // Undefined until the plans and rates are read; an existing machine is shown meanwhile as hosting is on.
  const hosting = useHosting();
  const hosted = hosting !== false;
  const runtime = useRuntime();
  const me = useMe();
  const start = useStartRuntime();
  const stop = useStopRuntime();
  const { copied, copy } = useCopy();
  const cents = useMachineCents(runtime.data?.runtime_id ?? null);

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
        hosted && (
          <Button onClick={() => start.mutate()} loading={start.isPending}>
            Start
          </Button>
        )
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
            {hosting === true && (
              <>
                {' '}
                Run more than one? <Link to="/machines">Machines</Link> lists them all.
              </>
            )}
          </>
        }
        actions={actions}
      />

      <div className={styles.stack}>
        <StartMachineError error={start.error} />
        <ApiErrorNotice error={stop.error} />

        {(runtime.isPending || (data?.state === 'none' && hosting === undefined)) && <LoadingCard />}
        {runtime.error && <ApiErrorNotice error={runtime.error} />}

        {data?.state === 'none' && hosting === false && (
          <EmptyState
            icon="home"
            title="No runtime yet"
            action={
              <Button variant="primary" onClick={() => navigate('/getting-started')}>
                Run rrotor yourself
              </Button>
            }
          >
            Run it with Docker Compose, Helm or Terraform, free on every plan. <Link to="/getting-started">Getting started</Link> walks you
            through it.
          </EmptyState>
        )}

        {data?.state === 'none' && hosting === true && (
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
              {hosted && (
                <Card>
                  <h2 className={styles.cardTitle}>This month</h2>
                  <div className={styles.cost}>
                    <span className={styles.costValue}>{cents === undefined ? '—' : money(cents)}</span>
                    <span className={styles.meta}>hosting so far</span>
                  </div>
                </Card>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
