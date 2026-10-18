import { useRestartMachine, useStartMachine, useStopMachine } from '@/api/queries';
import type { Machine } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { date, money } from '@/lib/format';
import { Button, Card, Chip, CopyButton, CopyField, type ChipTone } from '@/ui';
import { useMachineCents } from './HostingUpsell';
import { StartMachineError } from './MachineFields';
import { connectorUrl, sizeLabel } from './sizes';
import styles from './Machines.module.css';

export const machineState: Record<Machine['state'], { label: string; tone: ChipTone }> = {
  online: { label: 'Running', tone: 'green' },
  offline: { label: 'Offline', tone: 'amber' },
  stopped: { label: 'Stopped', tone: 'neutral' },
};

/** One machine: its state, where it answers, what it has cost this month, and Start, Stop, Restart and Delete. */
export function MachineCard({ machine, onDelete }: { machine: Machine; onDelete: () => void }) {
  const start = useStartMachine();
  const stop = useStopMachine();
  const restart = useRestartMachine();
  const running = machine.state !== 'stopped';
  const connector = connectorUrl(machine);
  const state = machineState[machine.state];
  const cents = useMachineCents(machine.id);

  return (
    <Card as="li" aria-label={machine.name}>
      <div className={styles.head}>
        <div className={styles.titleLine}>
          <h2 className={styles.name}>{machine.name}</h2>
          <Chip tone={state.tone} dot={machine.state === 'online'}>
            {state.label}
          </Chip>
          <Chip>{sizeLabel(machine.size)}</Chip>
        </div>
        <div className={styles.actions}>
          {running ? (
            <>
              <Button size="sm" onClick={() => restart.mutate(machine.id)} loading={restart.isPending}>
                Restart
              </Button>
              <Button size="sm" onClick={() => stop.mutate(machine.id)} loading={stop.isPending}>
                Stop
              </Button>
            </>
          ) : (
            <Button size="sm" onClick={() => start.mutate(machine.id)} loading={start.isPending}>
              Start
            </Button>
          )}
          <Button size="sm" variant="ghost" icon="trash" onClick={onDelete}>
            Delete
          </Button>
        </div>
      </div>

      <div className={styles.addressLine}>
        {machine.address ?? 'Address not ready yet'}
        {machine.address && <CopyButton value={machine.address} label="address" />}
      </div>
      {connector && <CopyField value={connector} label="connector URL" />}
      <span className={styles.meta}>
        {cents !== undefined && `${money(cents)} this month · `}made {date(machine.created_at)}
      </span>
      <StartMachineError error={start.error} />
      <ApiErrorNotice error={stop.error ?? restart.error} />
    </Card>
  );
}
