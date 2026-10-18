import { useState, type FormEvent } from 'react';
import { useCreateMachine } from '@/api/queries';
import type { MachineSize } from '@/api/types';
import { Button, Dialog } from '@/ui';
import { CreateMachineError, MachineFields } from './MachineFields';
import styles from './Machines.module.css';

/** Name a machine and pick its size; the server makes it and starts it. */
export function NewMachineDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateMachine();
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
      description="It starts once it is made, at an address of its own."
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
        <MachineFields name={name} size={size} onName={setName} onSize={setSize} />
        <CreateMachineError error={create.error} />
      </form>
    </Dialog>
  );
}
