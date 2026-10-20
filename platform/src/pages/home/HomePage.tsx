import { useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import { keys, useHosting, useMe, useRuntime, useSelfRuntimes, useStartRuntime, useStopRuntime } from '@/api/queries';
import type { Runtime } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { ago, money } from '@/lib/format';
import { useCopy } from '@/lib/useCopy';
import { StartMachineError } from '@/pages/machines/MachineFields';
import { useMachineCents } from '@/pages/machines/HostingUpsell';
import { Button, Card, Chip, CopyButton, CopyField, EmptyState, LoadingCard, type ChipTone } from '@/ui';
import { AddRuntimeDialog } from './add-runtime/AddRuntimeDialog';
import { SelfRuntimes } from './SelfRuntimes';
import styles from './HomePage.module.css';

const stateChip: Record<Exclude<Runtime['state'], 'none'>, { label: string; tone: ChipTone }> = {
  online: { label: 'Running', tone: 'green' },
  offline: { label: 'Offline', tone: 'amber' },
  stopped: { label: 'Stopped', tone: 'neutral' },
};

/**
 * Runtimes, the signed-in home: the runtimes you run yourself, with their token, licence and removal, and the hosted
 * machine with its address, state, connector URL and cost this month. While Glyphh hosts nothing there is no starting
 * one, no cost and no Machines. Add a runtime opens over the page; `?add=1` opens it on load, as the server and emails
 * link to it.
 */
export function HomePage() {
  const [params, setParams] = useSearchParams();
  const adding = params.get('add') === '1';
  const client = useQueryClient();
  const openAdd = () =>
    setParams((current) => {
      const next = new URLSearchParams(current);
      next.set('add', '1');
      return next;
    });
  const closeAdd = () => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('add');
        return next;
      },
      { replace: true },
    );
    // A runtime registered or made in it shows at once.
    void client.invalidateQueries({ queryKey: keys.selfRuntimes });
    void client.invalidateQueries({ queryKey: keys.runtime });
  };
  // Undefined until the plans and rates are read; an existing machine is shown meanwhile as hosting is on.
  const hosting = useHosting();
  const hosted = hosting !== false;
  const runtime = useRuntime();
  const me = useMe();
  const start = useStartRuntime();
  const stop = useStopRuntime();
  const { copied, copy } = useCopy();
  const cents = useMachineCents(runtime.data?.runtime_id ?? null);
  const self = useSelfRuntimes();
  const hasSelf = (self.data?.length ?? 0) > 0;

  const data = runtime.data;
  const connector = data?.address ? `${data.address}/mcp` : null;
  const running = data?.state === 'online' || data?.state === 'offline';

  const actions = (
    <>
      <Button icon="plus" onClick={openAdd}>
        Add a runtime
      </Button>
      {data && data.state !== 'none' && (
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
      )}
    </>
  );

  return (
    <>
      <PageHeader
        title="Runtimes"
        description={
          <>
            Your runtimes and how to reach them. Claude connects to a runtime’s address; your apps call it with an{' '}
            <Link to="/keys">API key</Link>.
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

        {data?.state === 'none' && hosting === false && self.data && !hasSelf && (
          <EmptyState
            icon="home"
            title="No runtime yet"
            action={
              <Button variant="primary" onClick={openAdd}>
                Run rrotor yourself
              </Button>
            }
          >
            Run it with Docker, Helm or Terraform, free on every plan.
          </EmptyState>
        )}

        {data?.state === 'none' && hosting === true && (
          <EmptyState
            icon="home"
            title="No runtime yet"
            action={
              <div className={styles.emptyActions}>
                <Button onClick={openAdd}>Run rrotor yourself</Button>
                <Button variant="primary" onClick={() => start.mutate()} loading={start.isPending}>
                  Start your runtime
                </Button>
              </div>
            }
          >
            Starting it the first time makes it, at an address of its own. Running it yourself is free on every plan.
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

        <SelfRuntimes />
      </div>

      <AddRuntimeDialog open={adding} onClose={closeAdd} />
    </>
  );
}
