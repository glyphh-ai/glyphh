import { useState } from 'react';
import { Link } from 'react-router';
import { useMachines } from '@/api/queries';
import type { Machine } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { PageHeader } from '@/layout/PageHeader/PageHeader';
import { Button, EmptyState, LoadingCard } from '@/ui';
import { DeleteMachineDialog } from './DeleteMachineDialog';
import { MachineCard } from './MachineCard';
import { NewMachineDialog } from './NewMachineDialog';
import styles from './Machines.module.css';

/** The person's hosted machines: each one's address and hours, made, started, stopped, restarted and deleted here. */
export function MachinesPage() {
  const machines = useMachines();
  const [making, setMaking] = useState(false);
  const [deleting, setDeleting] = useState<Machine | null>(null);

  const newMachine = (
    <Button variant="primary" icon="plus" onClick={() => setMaking(true)}>
      New machine
    </Button>
  );

  return (
    <>
      <PageHeader
        title="Machines"
        description={
          <>
            The machines Glyphh runs for you, each at an address of its own. Claude connects to one; your apps call it with an{' '}
            <Link to="/keys">API key</Link>.
          </>
        }
        actions={newMachine}
      />

      {machines.isPending && <LoadingCard />}
      {machines.error && <ApiErrorNotice error={machines.error} />}
      {machines.data?.length === 0 && (
        <EmptyState icon="chip" title="No machines yet" action={newMachine}>
          Make one to run rrotor. Running it yourself? <Link to="/getting-started">Getting started</Link> walks you through it.
        </EmptyState>
      )}
      {machines.data && machines.data.length > 0 && (
        <ul className={styles.list} aria-label="Machines">
          {machines.data.map((machine) => (
            <MachineCard key={machine.id} machine={machine} onDelete={() => setDeleting(machine)} />
          ))}
        </ul>
      )}

      {making && <NewMachineDialog onClose={() => setMaking(false)} />}
      {deleting && <DeleteMachineDialog machine={deleting} onClose={() => setDeleting(null)} />}
    </>
  );
}
