import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router';
import { useCreateMachine, useMe } from '@/api/queries';
import type { MachineSize } from '@/api/types';
import { Button, Dialog } from '@/ui';
import { HostingUpsell, useNoHosting, usePlanRates } from './HostingUpsell';
import { CreateMachineError, MachineFields } from './MachineFields';
import styles from './Machines.module.css';

/** Name a machine and pick its size; the server makes it and starts it. On a plan without hosting, the plans with it. */
export function NewMachineDialog({ onClose }: { onClose: () => void }) {
  return useNoHosting() ? <NoHostingDialog onClose={onClose} /> : <MakeMachineDialog onClose={onClose} />;
}

function MakeMachineDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateMachine();
  const rates = usePlanRates();
  const [name, setName] = useState('');
  const [size, setSize] = useState<MachineSize>('small');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate({ name: name.trim(), size }, { onSuccess: onClose });
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="New machine"
      description="It starts once it is made, at an address of its own. It is billed by the second while it runs, and its disk all month."
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" form="new-machine" loading={create.isPending} disabled={!name.trim()}>
            Make machine
          </Button>
        </>
      }
    >
      <form id="new-machine" className={styles.form} onSubmit={submit}>
        <MachineFields name={name} size={size} onName={setName} onSize={setSize} rates={rates} />
        <CreateMachineError error={create.error} />
      </form>
    </Dialog>
  );
}

function NoHostingDialog({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const isAdmin = useMe().data?.role === 'admin';
  return (
    <Dialog
      open
      onClose={onClose}
      title="New machine"
      actions={
        <>
          <Button variant={isAdmin ? 'ghost' : 'secondary'} onClick={onClose}>
            {isAdmin ? 'Cancel' : 'Close'}
          </Button>
          {isAdmin && (
            <Button variant="primary" onClick={() => navigate('/settings/plans')}>
              Upgrade
            </Button>
          )}
        </>
      }
    >
      <HostingUpsell isAdmin={isAdmin} />
    </Dialog>
  );
}
