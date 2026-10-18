import { useState, type FormEvent } from 'react';
import { useDeleteMachine } from '@/api/queries';
import type { Machine } from '@/api/types';
import { ApiErrorNotice } from '@/components/ApiErrorNotice';
import { Button, Dialog, TextField } from '@/ui';
import styles from './Machines.module.css';

/** Deleting cannot be undone and loses the disk, so the person types the machine's name first. */
export function DeleteMachineDialog({ machine, onClose }: { machine: Machine; onClose: () => void }) {
  const remove = useDeleteMachine();
  const [typed, setTyped] = useState('');
  const matches = typed === machine.name;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!matches) return;
    remove.mutate({ id: machine.id, confirm: typed }, { onSuccess: onClose });
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Delete this machine?"
      description={
        <>
          Deleting <strong>{machine.name}</strong> destroys the machine and its disk: every model, version, precedent and file on it. Fly keeps
          daily snapshots for 5 days; Glyphh keeps no other backup. Type <strong>{machine.name}</strong> to confirm.
        </>
      }
      actions={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" type="submit" form="delete-machine" loading={remove.isPending} disabled={!matches}>
            Delete machine
          </Button>
        </>
      }
    >
      <form id="delete-machine" className={styles.form} onSubmit={submit}>
        <TextField label="Machine name" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" spellCheck={false} />
        <ApiErrorNotice error={remove.error} />
      </form>
    </Dialog>
  );
}
