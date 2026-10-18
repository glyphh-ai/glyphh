import { useState, type FormEvent } from 'react';
import { Link } from 'react-router';
import { useCreateMachine, useMachines, useStartMachine } from '@/api/queries';
import type { MachineSize } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { CreateMachineError, MachineFields } from '@/pages/machines/MachineFields';
import { connectorUrl } from '@/pages/machines/sizes';
import { Button, CopyField, LoadingCard } from '@/ui';
import styles from './GettingStarted.module.css';

/** Glyphh runs it: make a first machine (a name and a size), or start the first one; then the connector URL. */
export function HostedChoice() {
  const machines = useMachines();

  if (machines.isPending) return <LoadingCard lines={2} />;
  if (machines.error) return <ApiErrorNotice error={machines.error} />;

  const first = machines.data[0];
  if (!first) return <FirstMachine />;

  const connector = connectorUrl(first);
  return (
    <div className={styles.part}>
      {first.state === 'stopped' && <StartMachine id={first.id} paused={first.paused} />}
      {connector && (
        <>
          <h3 className={styles.subTitle}>Connect Claude to {first.name}</h3>
          <CopyField value={connector} label="connector URL" />
        </>
      )}
      <span className={styles.meta}>
        {connector && 'Add it in Claude as a custom connector. You’ll be asked to allow it once. '}
        <Link to="/machines">Machines</Link> shows each of yours, and makes more.
      </span>
    </div>
  );
}

function FirstMachine() {
  const create = useCreateMachine();
  const [name, setName] = useState('Main');
  const [size, setSize] = useState<MachineSize>('small');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ name: name.trim(), size });
  };

  return (
    <form className={styles.form} onSubmit={submit} aria-label="Make your machine">
      <MachineFields name={name} size={size} onName={setName} onSize={setSize} />
      <span className={styles.meta}>It starts once it is made, at an address of its own.</span>
      <div className={styles.actions}>
        <Button variant="primary" type="submit" loading={create.isPending} disabled={!name.trim()}>
          Make your machine
        </Button>
      </div>
      <CreateMachineError error={create.error} />
    </form>
  );
}

function StartMachine({ id, paused }: { id: string; paused: boolean }) {
  const start = useStartMachine();
  return (
    <>
      <div className={styles.actions}>
        <Button variant="primary" onClick={() => start.mutate(id)} loading={start.isPending} disabled={paused}>
          Start
        </Button>
      </div>
      {paused && (
        <span className={styles.meta}>
          Paused: this month’s hours are used up. See <Link to="/settings/billing">Billing</Link>.
        </span>
      )}
      <ApiErrorNotice error={start.error} />
    </>
  );
}
