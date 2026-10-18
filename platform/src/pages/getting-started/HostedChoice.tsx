import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router';
import { useCreateMachine, useMachines, useMe, useStartMachine } from '@/api/queries';
import type { MachineSize } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { HostingUpsell, useNoHosting, usePlanRates } from '@/pages/machines/HostingUpsell';
import { CreateMachineError, MachineFields, StartMachineError } from '@/pages/machines/MachineFields';
import { connectorUrl } from '@/pages/machines/sizes';
import { Button, CopyField, LoadingCard } from '@/ui';
import styles from './GettingStarted.module.css';

/**
 * Glyphh runs it: make a first machine (a name and a size, with the plan's rates), or start the first one; then the
 * connector URL. On a plan without hosting, the plans that have it.
 */
export function HostedChoice() {
  const machines = useMachines();
  const noHosting = useNoHosting();

  if (machines.isPending) return <LoadingCard lines={2} />;
  if (machines.error) return <ApiErrorNotice error={machines.error} />;

  const first = machines.data[0];
  if (!first) return noHosting ? <NoHosting /> : <FirstMachine />;

  const connector = connectorUrl(first);
  return (
    <div className={styles.part}>
      {first.state === 'stopped' && <StartMachine id={first.id} />}
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

function NoHosting() {
  const navigate = useNavigate();
  const isAdmin = useMe().data?.role === 'admin';
  return (
    <div className={styles.part}>
      <HostingUpsell isAdmin={isAdmin} />
      {isAdmin && (
        <div className={styles.actions}>
          <Button variant="primary" onClick={() => navigate('/settings/plans')}>
            Upgrade
          </Button>
        </div>
      )}
    </div>
  );
}

function FirstMachine() {
  const create = useCreateMachine();
  const rates = usePlanRates();
  const [name, setName] = useState('Main');
  const [size, setSize] = useState<MachineSize>('small');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ name: name.trim(), size });
  };

  return (
    <form className={styles.form} onSubmit={submit} aria-label="Make your machine">
      <MachineFields name={name} size={size} onName={setName} onSize={setSize} rates={rates} />
      <span className={styles.meta}>It starts once it is made, at an address of its own. It is billed by the second while it runs, and its disk all month.</span>
      <div className={styles.actions}>
        <Button variant="primary" type="submit" loading={create.isPending} disabled={!name.trim()}>
          Make your machine
        </Button>
      </div>
      <CreateMachineError error={create.error} />
    </form>
  );
}

function StartMachine({ id }: { id: string }) {
  const start = useStartMachine();
  return (
    <>
      <div className={styles.actions}>
        <Button variant="primary" onClick={() => start.mutate(id)} loading={start.isPending}>
          Start
        </Button>
      </div>
      <StartMachineError error={start.error} />
    </>
  );
}
